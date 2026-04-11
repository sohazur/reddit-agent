#!/usr/bin/env node

/**
 * reddit-agent CLI
 *
 * Thin Node.js wrapper around the Python Reddit agent.
 * Handles setup, bootstrap, and forwards commands to Python.
 *
 * Commands:
 *   reddit-agent setup       Interactive setup (credentials + bootstrap)
 *   reddit-agent run         Run one engagement cycle (default)
 *   reddit-agent feedback    Check past comments for karma/removals
 *   reddit-agent digest      Print daily performance report
 *   reddit-agent update      Pull latest version from GitHub
 *   reddit-agent status      Show current config and health
 */

const { execFileSync, execSync, spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const readline = require("readline");

const ROOT = path.resolve(__dirname, "..");
const VENV = path.join(ROOT, ".venv");
const PYTHON = path.join(VENV, "bin", "python");
const ENV_FILE = path.join(ROOT, ".env");

function isBootstrapped() {
  return fs.existsSync(PYTHON);
}

function run(cmd, args = [], opts = {}) {
  return spawnSync(cmd, args, {
    cwd: ROOT,
    stdio: "inherit",
    env: { ...process.env, ...loadShellEnv() },
    ...opts,
  });
}

function loadShellEnv() {
  // Source .bashrc/.profile to get API keys (like OpenClaw does)
  const extra = {};
  for (const rc of [
    path.join(process.env.HOME, ".bashrc"),
    path.join(process.env.HOME, ".profile"),
  ]) {
    if (!fs.existsSync(rc)) continue;
    try {
      const content = fs.readFileSync(rc, "utf8");
      for (const line of content.split("\n")) {
        const m = line.match(/^export\s+(\w+)=(.+)$/);
        if (m) {
          let val = m[2].trim().replace(/^["']|["']$/g, "");
          if (
            m[1].includes("API_KEY") ||
            m[1].includes("OPENAI") ||
            m[1].includes("ANTHROPIC")
          ) {
            extra[m[1]] = val;
          }
        }
      }
    } catch {}
  }
  return extra;
}

function ask(question) {
  return new Promise((resolve) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
    });
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer.trim());
    });
  });
}

function askHidden(question) {
  return new Promise((resolve) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
    });
    // Mute output for password
    process.stdout.write(question);
    const stdin = process.openStdin();
    let password = "";
    const onData = (char) => {
      char = char + "";
      if (char === "\n" || char === "\r" || char === "\u0004") {
        stdin.removeListener("data", onData);
        console.log();
        rl.close();
        resolve(password.trim());
      } else if (char === "\u007F" || char === "\b") {
        password = password.slice(0, -1);
      } else {
        password += char;
      }
    };
    process.stdin.setRawMode(true);
    process.stdin.resume();
    process.stdin.on("data", onData);
  });
}

function detectEnvironment() {
  // Detect what environment we're running in
  const env = {
    isOpenClaw: false,
    hasAnthropicKey: false,
    hasOpenAIKey: false,
    apiKeySource: null,
  };

  // Check OpenClaw — must have both the config dir AND the gateway/workspace
  // (just having ~/.openclaw isn't enough — it could be leftover from other tools)
  const openclawDir = path.join(process.env.HOME, ".openclaw");
  const openclawConfig = path.join(openclawDir, "openclaw.json");
  const openclawWorkspace = path.join(openclawDir, "workspace");
  env.isOpenClaw =
    fs.existsSync(openclawConfig) && fs.existsSync(openclawWorkspace);

  // Check API keys in environment
  if (process.env.ANTHROPIC_API_KEY) {
    env.hasAnthropicKey = true;
    env.apiKeySource = "environment";
  }
  if (process.env.OPENAI_API_KEY) {
    env.hasOpenAIKey = true;
    env.apiKeySource = "environment";
  }

  // Check shell profiles for API keys
  if (!env.hasAnthropicKey && !env.hasOpenAIKey) {
    const shellEnv = loadShellEnv();
    if (shellEnv.ANTHROPIC_API_KEY) {
      env.hasAnthropicKey = true;
      env.apiKeySource = "shell profile";
    }
    if (shellEnv.OPENAI_API_KEY) {
      env.hasOpenAIKey = true;
      env.apiKeySource = "shell profile";
    }
  }

  return env;
}

async function setup() {
  console.log();
  console.log("Reddit Agent — Setup");
  console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  console.log();

  // Detect environment
  const env = detectEnvironment();
  if (env.isOpenClaw) {
    console.log("  Detected: OpenClaw environment");
  }
  if (env.hasAnthropicKey || env.hasOpenAIKey) {
    console.log(
      `  Detected: ${env.hasAnthropicKey ? "Anthropic" : "OpenAI"} API key (from ${env.apiKeySource})`
    );
  }
  console.log();

  // Bootstrap Python if needed
  if (!isBootstrapped()) {
    console.log("Setting up Python environment...");
    const result = run("node", [path.join(ROOT, "lib", "bootstrap.js")]);
    if (result.status !== 0) {
      console.error("Bootstrap failed. Check Python 3.12+ is installed.");
      process.exit(1);
    }
  }

  // ─── Reddit credentials ────────────────────────
  console.log("Reddit account:\n");
  const username = await ask("  Username: ");

  // Password — write directly via Python to avoid shell escaping
  console.log("  Password: (typing is hidden)");
  const password = await new Promise((resolve) => {
    let pw = "";
    process.stdin.setRawMode(true);
    process.stdin.resume();
    process.stdin.setEncoding("utf8");
    const onData = (key) => {
      if (key === "\r" || key === "\n" || key === "\u0004") {
        process.stdin.setRawMode(false);
        process.stdin.pause();
        process.stdin.removeListener("data", onData);
        console.log();
        resolve(pw);
      } else if (key === "\u007F" || key === "\b") {
        if (pw.length > 0) {
          pw = pw.slice(0, -1);
          process.stdout.write("\b \b");
        }
      } else if (key === "\u0003") {
        process.exit(0);
      } else {
        pw += key;
        process.stdout.write("*");
      }
    };
    process.stdin.on("data", onData);
  });

  // ─── Objective ─────────────────────────────────
  console.log();
  console.log("What's your goal on Reddit?");
  console.log("  Examples:");
  console.log("  - Promote my SaaS product to developers");
  console.log("  - Build authority in the fitness niche");
  console.log("  - Drive traffic to my blog about AI");
  console.log("  - Just build karma on a new account");
  console.log();
  const objective = await ask("  Your objective: ");

  // ─── API key (always ask if not detected) ──────
  let apiKey = "";
  let apiProvider = "";
  if (!env.hasAnthropicKey && !env.hasOpenAIKey) {
    console.log();
    console.log("  No AI API key detected in your environment.");
    console.log("  The agent needs one to generate comments and evaluate threads.");
    console.log("  Get a key from: console.anthropic.com or platform.openai.com");
    if (env.isOpenClaw) {
      console.log("  (OpenClaw may provide one at runtime — press Enter to skip)");
    }
    console.log();
    apiKey = await ask("  API key (or Enter to skip): ");
    if (apiKey) {
      apiProvider = apiKey.startsWith("sk-ant")
        ? "ANTHROPIC_API_KEY"
        : "OPENAI_API_KEY";
    }
  }

  // ─── Settings ──────────────────────────────────
  console.log();
  const maxDaily = (await ask("  Max comments/day [5]: ")) || "5";
  const engagePost =
    (await ask("  Create original posts? (y/n) [n]: ")) || "n";
  const engageDmOutreach =
    (await ask("  Proactive DM outreach to leads? (y/n) [n]: ")) || "n";

  // ─── Write .env via Python (handles special chars) ─────
  const envLines = [
    `REDDIT_USERNAME=${username}`,
    `REDDIT_PASSWORD=${password}`,
    `REDDIT_AGENT_OBJECTIVE=${objective}`,
  ];
  if (apiKey && apiProvider) {
    envLines.push(`${apiProvider}=${apiKey}`);
  }
  envLines.push(
    `MAX_COMMENTS_PER_DAY=${maxDaily}`,
    `MIN_COMMENT_INTERVAL_MINUTES=20`,
    `QUALITY_THRESHOLD=7`,
    `CYCLE_INTERVAL_HOURS=2`,
    `ENGAGE_COMMENT=true`,
    `ENGAGE_UPVOTE=true`,
    `ENGAGE_REPLY=true`,
    `ENGAGE_POST=${engagePost.toLowerCase().startsWith("y") ? "true" : "false"}`,
    `ENGAGE_BROWSE=true`,
    `ENGAGE_DM_REPLY=true`,
    `ENGAGE_DM_OUTREACH=${engageDmOutreach.toLowerCase().startsWith("y") ? "true" : "false"}`,
    `LOG_LEVEL=INFO`,
    `SCREENSHOT_ON_ERROR=true`
  );

  // Write via Python to safely handle special characters in password
  const envContent = envLines.join("\n");
  const writeScript = `
import os
env_path = ${JSON.stringify(ENV_FILE)}
with open(env_path, 'w') as f:
    f.write(${JSON.stringify(envContent + "\n")})
os.chmod(env_path, 0o600)
print('ok')
`;
  const writeResult = spawnSync(
    isBootstrapped() ? PYTHON : "python3",
    ["-c", writeScript],
    { cwd: ROOT, stdio: "pipe" }
  );
  if (writeResult.stdout && writeResult.stdout.toString().includes("ok")) {
    console.log("\n✓ Configuration saved");
  } else {
    // Fallback: write directly
    fs.writeFileSync(ENV_FILE, envContent + "\n", { mode: 0o600 });
    console.log("\n✓ Configuration saved (direct write)");
  }

  // Init DB
  run(PYTHON, ["-c", "from src.db import init_db; init_db()"]);
  console.log("✓ Database ready");

  // Run health check
  console.log();
  run(PYTHON, ["-m", "src.health"]);

  console.log();
  console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  console.log("✓ Reddit Agent is ready!");
  console.log();
  console.log("  reddit-agent run        Run one cycle");
  console.log("  reddit-agent feedback   Check past comments");
  console.log("  reddit-agent digest     Performance report");
  console.log("  reddit-agent update     Pull latest version");
  console.log();
}

function ensureBootstrapped() {
  if (!isBootstrapped()) {
    console.log("First run — setting up Python environment...");
    const result = run("node", [path.join(ROOT, "lib", "bootstrap.js")]);
    if (result.status !== 0) {
      console.error(
        "Setup failed. Run: reddit-agent setup\nOr check Python 3.12+ is installed."
      );
      process.exit(1);
    }
    // Init DB
    run(PYTHON, ["-c", "from src.db import init_db; init_db()"]);
  }
}

function runPython(args) {
  ensureBootstrapped();
  const result = run(PYTHON, ["-m", "src.main", ...args]);
  process.exit(result.status || 0);
}

function update() {
  console.log("Updating Reddit Agent...");

  // Check if this is a git repo (dev install) or npm install
  if (fs.existsSync(path.join(ROOT, ".git"))) {
    run("git", ["pull"]);
  } else {
    // npm global update
    const result = spawnSync("npm", ["update", "-g", "reddit-agent"], {
      stdio: "inherit",
    });
    if (result.status !== 0) {
      console.log("npm update failed. Try: npm i -g reddit-agent@latest");
    }
  }

  // Reinstall Python deps
  if (isBootstrapped()) {
    console.log("Updating Python dependencies...");
    run(PYTHON, ["-m", "pip", "install", "-e", ".", "--quiet"]);
  }

  console.log("✓ Updated");
}

function status() {
  ensureBootstrapped();
  console.log("Reddit Agent — Status");
  console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  console.log(`Install: ${ROOT}`);

  if (fs.existsSync(ENV_FILE)) {
    const env = fs.readFileSync(ENV_FILE, "utf8");
    const user = env.match(/REDDIT_USERNAME=(.+)/);
    const max = env.match(/MAX_COMMENTS_PER_DAY=(.+)/);
    console.log(`Account: ${user ? user[1] : "not set"}`);
    console.log(`Limit:   ${max ? max[1] : "5"}/day`);
  } else {
    console.log("Config:  not set up (run: reddit-agent setup)");
  }

  console.log();
  run(PYTHON, ["-m", "src.health"]);
}

// ─── Main ─────────────────────────────────────────

const command = process.argv[2] || "run";

switch (command) {
  case "setup":
    setup().catch(console.error);
    break;
  case "setup-password":
    (async () => {
      if (!fs.existsSync(ENV_FILE)) {
        console.log("Run reddit-agent setup first.");
        process.exit(1);
      }
      const rl3 = readline.createInterface({ input: process.stdin, output: process.stdout });
      const pw = await new Promise((resolve) => {
        rl3.question("Reddit password: ", (ans) => { rl3.close(); resolve(ans.trim()); });
      });
      let env = fs.readFileSync(ENV_FILE, "utf8");
      env = env.replace(/REDDIT_PASSWORD=.*/, `REDDIT_PASSWORD=${pw}`);
      fs.writeFileSync(ENV_FILE, env, { mode: 0o600 });
      console.log("Password updated securely.");
    })().catch(console.error);
    break;
  case "run":
    runPython([]);
    break;
  case "feedback":
  case "--feedback":
    runPython(["--feedback"]);
    break;
  case "digest":
  case "--digest":
    runPython(["--digest"]);
    break;
  case "objective":
    (async () => {
      const newObj = process.argv[3]
        ? process.argv.slice(3).join(" ")
        : await ask("New objective: ");
      if (newObj && fs.existsSync(ENV_FILE)) {
        let env = fs.readFileSync(ENV_FILE, "utf8");
        if (env.includes("REDDIT_AGENT_OBJECTIVE=")) {
          env = env.replace(/REDDIT_AGENT_OBJECTIVE=.*/, `REDDIT_AGENT_OBJECTIVE=${newObj}`);
        } else {
          env += `\nREDDIT_AGENT_OBJECTIVE=${newObj}\n`;
        }
        fs.writeFileSync(ENV_FILE, env, { mode: 0o600 });
        console.log(`Objective updated: ${newObj}`);
      } else {
        console.log("Run reddit-agent setup first.");
      }
    })().catch(console.error);
    break;
  case "update":
    update();
    break;
  case "status":
    status();
    break;
  case "help":
  case "--help":
  case "-h":
    console.log(`
Reddit Agent — Autonomous Reddit engagement

Commands:
  reddit-agent setup       Set up credentials and environment
  reddit-agent run         Run one engagement cycle (default)
  reddit-agent feedback    Check past comments for karma/removals
  reddit-agent digest      Print daily performance report
  reddit-agent objective   Change your Reddit objective/goal
  reddit-agent update      Pull latest version
  reddit-agent status      Show config and health check

Config:     ${ROOT}/.env
Subreddits: ${ROOT}/data/subreddits.yaml
Docs:       https://github.com/sohazur/reddit-agent
`);
    break;
  default:
    // Pass through to Python (handles --feedback, --digest, etc)
    runPython(process.argv.slice(2));
}
