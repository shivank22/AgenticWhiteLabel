# TODO: reconstruct from photo edge (module docstring / lines ~1-21 not fully visible)

from __future__ import annotations

from typing import Any
from uuid import uuid4


def build_interrupt_payload(
    *,
    interrupt_id: str,
    summary: str,
    interrupt_type: str = "input",
    required_roles: list[str] | None = None,
    gate_id: str | None = None,
    node_id: str | None = None,
    phase_id: str | None = None,
    action_type: str | None = None,
    response_id: str | None = None,
    affected_contributions: list[str] | None = None,
    risk_summary: str | None = None,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the standard interrupt payload dict.

    This dict is passed directly to LangGraph's interrupt() and is surfaced
    in StateSnapshot.tasks[*].interrupts[*].value for API clients to read.

    Matches the interrupt-payload.json contract (doc 16).
    """
    return {
        "interrupt_id": interrupt_id,
        "gate_id": gate_id or interrupt_id,
        "node_id": node_id or "",
        "phase_id": phase_id or "",
        "action_type": action_type or "input",
        "response_id": response_id or "",
        "affected_contributions": affected_contributions or [],
        "risk_summary": risk_summary or "",
        "type": interrupt_type,
        "summary": summary,
        "required_roles": required_roles or [],
        "raw": raw or {},
    }


def make_gate_id(*, phase_id: str, node_id: str, action_type: str) -> str:
    """Create a deterministic, auditable HITL gate identifier prefix.

    A unique suffix avoids accidental collisions across repeated runs while
    retaining stable semantics for phase/node/action grouping.
    """
    return f"g-{phase_id}-{node_id}-{action_type}-{uuid4()}"


def _flatten_raw_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Flatten one nested raw payload level when it is itself a mapping."""
    raw = payload.get("raw")
    if not isinstance(raw, dict):
        return payload

    merged = {**raw, **payload}
    merged.pop("raw", None)
    return merged


def _payload_from_interrupt(interrupt: Any) -> dict[str, Any]:
    raw_value = getattr(interrupt, "value", None)
    base = dict(raw_value) if isinstance(raw_value, dict) else {"raw": raw_value}
    payload = _flatten_raw_payload(base)

    runtime_interrupt_id = getattr(interrupt, "id", None)
    if not runtime_interrupt_id:
        return payload

    existing = payload.get("interrupt_id")
    if existing and payload.get("payload_interrupt_id") is None:
        payload["payload_interrupt_id"] = str(existing)
    payload["interrupt_id"] = str(runtime_interrupt_id)
    return payload


def extract_interrupt_payloads(snapshot: Any) -> list[dict[str, Any]]:
    """Extract all open interrupt payloads from a LangGraph StateSnapshot.

    Returns an empty list when there are no open interrupts.

    Normalization goals (API-friendly, backwards-compatible):

    - Use the *runtime* LangGraph interrupt id as the canonical ``interrupt_id`` for resume.
    - If a payload already contains an ``interrupt_id`` (caller-provided), preserve it under
      ``payload_interrupt_id``.
    - Avoid nested ``raw`` payloads (``raw.raw``) by flattening one level.
    """
    tasks = getattr(snapshot, "tasks", None)
    if snapshot is None or not tasks:
        return []

    payloads: list[dict[str, Any]] = []
    for task in tasks:
        for interrupt in task.interrupts or []:
            payloads.append(_payload_from_interrupt(interrupt))

    return payloads


def has_open_interrupt(snapshot: Any) -> bool:
    """Return True if the snapshot has at least one open interrupt."""
    return bool(extract_interrupt_payloads(snapshot))


def is_approved_decision(value: Any) -> bool:
    """Return True when a resume decision clearly indicates approval.

    Accepted shapes:
    - "approve", "approved", "yes", "y", "ok", "proceed"
    - {"decision": "approve"}
    - {"approved": true}
    """
    if isinstance(value, bool):
        return value

    if isinstance(value, dict):
        if "approved" in value:
            return bool(value.get("approved"))
        if "decision" in value:
            token = str(value.get("decision") or "").strip().lower()
            return token in {"approve", "approved", "yes", "y", "ok", "proceed"}
        return False

    token = str(value or "").strip().lower()
    return token in {"approve", "approved", "yes", "y", "ok", "proceed"}


def _normalize_string_decision(token: str) -> dict[str, Any]:
    """Normalize a string review decision."""
    token = token.strip().lower()
    if token in {"approve", "approved", "yes", "y", "ok", "proceed"}:
        return {"type": "approve"}
    if token in {"reject", "rejected", "deny", "denied", "no", "n"}:
        return {"type": "reject", "message": "User rejected this action."}
    if token == "edit":
        return {"type": "edit", "edited_action": {"name": "", "args": {}}}
    return {"type": "unknown", "message": "Invalid review decision."}


def _normalize_dict_decision(value: dict[str, Any]) -> dict[str, Any]:
    """Normalize a dict review decision."""
    raw_type = value.get("type", value.get("decision", ""))
    decision = str(raw_type or "").strip().lower()

    # Normalize token to canonical form
    if decision in {"approved", "yes", "y", "ok", "proceed"}:
        decision = "approve"
    if decision in {"denied", "deny", "rejected", "no", "n"}:
        decision = "reject"
    if decision and decision not in {"approve", "reject", "edit"}:
        decision = "unknown"

    normalized: dict[str, Any] = {"type": decision or "unknown"}

    # Handle edit-specific fields
    if decision == "edit":
        edited = value.get("edited_action")
        if not isinstance(edited, dict):
            edited = {"name": "", "args": {}}
        normalized["edited_action"] = {
            "name": str(edited.get("name") or ""),
            "args": edited.get("args") if isinstance(edited.get("args"), dict) else {},
        }

    # Preserve message field if present
    if "message" in value:
        normalized["message"] = str(value.get("message") or "")

    return normalized


def normalize_tool_review_decision(value: Any) -> dict[str, Any]:
    """Normalize reviewer input into a canonical tool-review decision shape.

    Accepted input forms:
    - "approve" / "reject" / "edit"
    - {"type": "approve"}
    - {"decision": "approve"}
    - {"type": "edit", "edited_action": {"name": "...", "args": {...}}}

    Anything that cannot be interpreted resolves to '{"type": "unknown"}' so
    callers can re-ask. It must never fall through as an approval, and must not
    be reported to the user as an explicit rejection they never made.
    """
    if isinstance(value, str):
        return _normalize_string_decision(value)

    if isinstance(value, dict):
        return _normalize_dict_decision(value)

    if isinstance(value, bool):
        return {"type": "approve" if value else "reject"}

    return {"type": "unknown", "message": "Invalid review decision payload."}
