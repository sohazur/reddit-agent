"""Helpers for rendering the service catalog into prompts and lookups."""

from src.config import ServiceCatalog, Service


def format_services_block(catalog: ServiceCatalog) -> str:
    """Render services as a compact, id-keyed block for the classifier prompt."""
    lines = []
    for s in catalog.services:
        solves = "; ".join(s.solves) if s.solves else ""
        signals = "; ".join(s.signals) if s.signals else ""
        lines.append(
            f"- {s.id} — {s.name}\n"
            f"    solves: {solves}\n"
            f"    signals: {signals}\n"
            f"    how we help: {s.pitch}"
        )
    return "\n".join(lines) if lines else "(no services configured)"


def service_by_id(catalog: ServiceCatalog, sid: str) -> Service | None:
    for s in catalog.services:
        if s.id == sid:
            return s
    return None


def valid_service_ids(catalog: ServiceCatalog) -> set[str]:
    return {s.id for s in catalog.services}


def pitches_for(catalog: ServiceCatalog, ids: list[str]) -> list[str]:
    """Map matched service ids to their human 'how we help' pitch lines."""
    out = []
    for sid in ids:
        svc = service_by_id(catalog, sid)
        if svc and svc.pitch:
            out.append(f"{svc.name}: {svc.pitch}")
    return out
