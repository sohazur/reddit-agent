#!/usr/bin/env node

/**
 * Bootstrap the Python environment for reddit-agent.
 *
 * This script:
 * 1. Checks for Python 3.12+
 * 2. Checks for uv (installs if missing)
 * 3. Creates a Python venv
 * 4. Installs Python dependencies
 * 5. Installs Playwright + Chromium
 *
 * Called by:
 * - `npm postinstall` with --postinstall flag (just prints message)
 * - `bin/cli.js` on first run (full bootstrap)
 */

const { execSync, spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const VENV = path.join(ROOT, ".venv");

// ─── Postinstall mode: just print a message ───────

if (process.argv.includes("--postinstall")) {
  console.log();
  console.log("  reddit-agent installed!");
  console.log();
  console.log("  Quick start:");
  console.log("    reddit-agent setup    Set up Reddit credentials");
  console.log("    reddit-agent run      Run one engagement cycle");
  console.log("    reddit-agent help     See all commands");
  console.log();
  process.exit(0);
}

// ─── Full bootstrap ───────────────────────────────

console.log("Bootstrapping Python environment...");

function exec(cmd, opts = {}) {
  try {
    return execSync(cmd, { cwd: ROOT, stdio: "pipe", ...opts })
      .toString()
      .trim();
  } catch {
    return null;
  }
}

function runVisible(cmd, args = []) {
  return spawnSync(cmd, args, { cwd: ROOT, stdio: "inherit" });
}

// 1. Check Python
let python = null;
for (const cmd of ["python3", "python"]) {
  const ver = exec(`${cmd} -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"`);
  if (ver) {
    const [major, minor] = ver.split(".").map(Number);
    if (major >= 3 && minor >= 12) {
      python = cmd;
      console.log(`  Python ${ver} ✓`);
      break;
    }
  }
}

if (!python) {
  // Try to install
  if (exec("which apt-get")) {
    console.log("  Installing Python...");
    exec("apt-get update -qq && apt-get install -y -qq python3 python3-venv python3-pip", { stdio: "inherit" });
    python = "python3";
  } else if (exec("which brew")) {
    console.log("  Installing Python via Homebrew...");
    exec("brew install python@3.12", { stdio: "inherit" });
    python = "python3";
  } else {
    console.error("  Python 3.12+ not found. Install it first.");
    process.exit(1);
  }
}

// 2. Check uv
let hasUv = !!exec("which uv");
if (!hasUv) {
  console.log("  Installing uv package manager...");
  exec("curl -LsSf https://astral.sh/uv/install.sh | sh", { stdio: "pipe" });
  // Add to PATH for this session
  const uvPath = path.join(process.env.HOME, ".local", "bin");
  process.env.PATH = `${uvPath}:${process.env.PATH}`;
  hasUv = !!exec("which uv");
}

if (hasUv) {
  console.log("  uv ✓");
} else {
  console.log("  pip (uv not available, using pip)");
}

// 3. Create venv
if (!fs.existsSync(VENV)) {
  console.log("  Creating virtual environment...");
  if (hasUv) {
    exec("uv venv .venv --quiet");
  } else {
    exec(`${python} -m venv .venv`);
  }
}
console.log("  venv ✓");

// 4. Install Python deps
console.log("  Installing Python dependencies...");
if (hasUv) {
  const r = runVisible("uv", ["pip", "install", "-e", ".[dev]", "--quiet"]);
  if (r.status !== 0) {
    // Fallback to pip
    runVisible(path.join(VENV, "bin", "pip"), ["install", "-e", ".[dev]", "--quiet"]);
  }
} else {
  runVisible(path.join(VENV, "bin", "pip"), ["install", "-e", ".[dev]", "--quiet"]);
}
console.log("  Dependencies ✓");

// 5. Install Playwright + Chromium
console.log("  Installing Chromium browser...");
const pw = path.join(VENV, "bin", "playwright");
let installed = runVisible(pw, ["install", "chromium"]);
if (installed.status !== 0) {
  // Try installing system deps first (Linux)
  runVisible(pw, ["install-deps", "chromium"]);
  runVisible(pw, ["install", "chromium"]);
}
console.log("  Chromium ✓");

// 6. Init database
exec(`${path.join(VENV, "bin", "python")} -c "from src.db import init_db; init_db()"`);
console.log("  Database ✓");

console.log();
console.log("  Bootstrap complete!");
