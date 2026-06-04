"""Optional push of discovered opportunities to your platform (e.g. ReachLLM).

If REACHLLM_OPPORTUNITIES_URL is unset this is a silent no-op, so the agent
runs fine without any endpoint. When set, new opportunities are POSTed as JSON
with an optional bearer token, and successfully-delivered ones are marked
'pushed' so they aren't sent twice.
"""

import requests

from src.config import Config, load_service_catalog
from src.log import get_logger
from src.research import store
from src.research.report import build_payload

log = get_logger("reachllm")


def push_new_opportunities(config: Config, max_batch: int = 50) -> dict:
    """POST 'new' opportunities to the configured endpoint.

    Returns {"pushed": n, "skipped": bool, "ok": bool}. Never raises into the
    cycle — a delivery failure must not stop research.
    """
    result = {"pushed": 0, "skipped": False, "ok": True}

    if not config.reachllm_opportunities_url:
        result["skipped"] = True
        return result

    new_opps = store.get_opportunities(status="new", limit=max_batch)
    if not new_opps:
        return result

    catalog = load_service_catalog()
    payload = build_payload(new_opps, catalog)

    headers = {"Content-Type": "application/json"}
    if config.reachllm_api_token:
        headers["Authorization"] = f"Bearer {config.reachllm_api_token}"

    try:
        resp = requests.post(
            config.reachllm_opportunities_url,
            json=payload,
            headers=headers,
            timeout=20,
        )
        if 200 <= resp.status_code < 300:
            store.mark_opportunities_pushed([o["id"] for o in new_opps])
            result["pushed"] = len(new_opps)
            log.info(f"Pushed {len(new_opps)} opportunities to platform")
        else:
            result["ok"] = False
            log.error(f"Opportunity push failed: HTTP {resp.status_code}")
    except requests.RequestException as e:
        result["ok"] = False
        log.error(f"Opportunity push error: {e}")

    return result
