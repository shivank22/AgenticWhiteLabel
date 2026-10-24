# TODO: reconstruct from photo edge (module docstring / lines ~1-17 not fully visible)

from __future__ import annotations

from typing import Any

from src.workflows.interrupts import (
    extract_interrupt_payloads,
    normalize_tool_review_decision,
)

REVIEW_INTERRUPT_TYPES = frozenset({"tool_review", "tool_approval"})

APPROVE_TOKENS = frozenset(
    {"approve", "approved", "yes", "y", "ok", "okay", "proceed", "confirm", "accept"}
)
REJECT_TOKENS = frozenset(
    {"reject", "rejected", "deny", "denied", "no", "n", "cancel", "decline"}
)
EDIT_TOKENS = frozenset({"edit", "modify", "change"})

APPROVE_ALL_TOKENS = frozenset(
    {"approve all", "approve_all", "approve-all", "yes to all", "yes all", "all"}
)
REJECT_ALL_TOKENS = frozenset(
    {"reject all", "reject_all", "reject-all", "deny all", "no to all"}
)

NO_REVIEW_DECISION_MESSAGE = "No review decision was provided."


def _option_labels(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("allowed_decisions") or payload.get("options") or []
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw]


def _option_from_index(token: str, options: list[str]) -> str | None:
    """Return the option selected by a 1-based numeric answer."""
    if not options or not token.isdigit():
        return None
    index = int(token)
    if 1 <= index <= len(options):
        return options[index - 1]
    return None


def _option_from_label(token: str, options: list[str]) -> str | None:
    for option in options:
        if option.strip().lower() == token:
            return option
    return None


def _decision_from_token(token: str) -> dict[str, Any] | None:
    if token in APPROVE_ALL_TOKENS or token in APPROVE_TOKENS:
        return {"type": "approve"}
    if token in REJECT_ALL_TOKENS or token in REJECT_TOKENS:
        return {"type": "reject", "message": "User rejected this action."}
    if token in EDIT_TOKENS:
        return {"type": "edit", "edited_action": {"name": "", "args": {}}}
    return None


def _resolve_dict_decision(value: dict[str, Any]) -> dict[str, Any]:
    """Resolve a dict-shaped review decision."""
    if "type" in value or "decision" in value:
        token = str(value.get("type") or value.get("decision") or "").strip().lower()
        # Check for bulk approve/reject
        if token in APPROVE_ALL_TOKENS or token in REJECT_ALL_TOKENS:
            bulk = _decision_from_token(token)
            if bulk is not None:
                return bulk
        return normalize_tool_review_decision(value)
    return {"type": "unknown", "message": NO_REVIEW_DECISION_MESSAGE}


def _resolve_string_decision(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Resolve a string token as a review decision, with option mapping."""
    token = token.strip().lower()
    if not token:
        return {"type": "unknown", "message": NO_REVIEW_DECISION_MESSAGE}

    # Try direct token mapping
    direct = _decision_from_token(token)
    if direct is not None:
        return direct

    # Try option mapping (index or label)
    options = _option_labels(payload)
    selected = _option_from_index(token, options) or _option_from_label(token, options)
    if selected is not None:
        mapped = _decision_from_token(selected.strip().lower())
        if mapped is not None:
            return mapped

    return {
        "type": "unknown",
        "message": f"Could not interpret '{token}' as a review decision.",
    }


def _resolve_decision(payload: dict[str, Any], value: Any) -> dict[str, Any]:
    """Resolve a reviewer answer into a canonical tool-review decision."""
    if value is None:
        return {"type": "unknown", "message": NO_REVIEW_DECISION_MESSAGE}

    if isinstance(value, bool):
        return {"type": "approve" if value else "reject"}

    if isinstance(value, dict):
        return _resolve_dict_decision(value)

    return _resolve_string_decision(str(value), payload)


def _resolve_text(payload: dict[str, Any], value: Any) -> Any:
    """Resolve a free-text/choice answer, mapping option indexes to labels."""
    if isinstance(value, dict):
        for key in ("response", "answer", "text", "value"):
            if key in value:
                value = value[key]
                break
        else:
            return value

    if not isinstance(value, str):
        return value
    token = value.strip().lower()
    options = _option_labels(payload)
    selected = _option_from_index(token, options)
    if selected is not None:
        return selected
    return value


def _answer_for(
    answer: Any,
    interrupt_id: str,
    interrupt_index: int = 0,
) -> Any:
    """Pick the portion of the answer that targets a specific interrupt."""
    if isinstance(answer, list):
        return answer[interrupt_index] if interrupt_index < len(answer) else answer

    if not isinstance(answer, dict):
        return answer

    if interrupt_id in answer:
        return answer[interrupt_id]

    if "type" in answer or "decision" in answer:
        return answer

    # An interrupt-id keyed map whose key no longer matches the live interrupt
    # (for example a stale id from an earlier snapshot). Unwrap it rather than
    # handing the raw mapping to the gate, which would read as "no decision".
    if len(answer) == 1:
        return next(iter(answer.values()), answer)

    return answer


def resolve_resume_map(*, snapshot: Any, answer: Any) -> dict[str, Any]:
    """Build a resume map covering every open interrupt on the snapshot."""
    resume_map: dict[str, Any] = {}

    for interrupt_index, payload in enumerate(extract_interrupt_payloads(snapshot)):
        interrupt_id = str(payload.get("interrupt_id") or "").strip()
        if not interrupt_id:
            continue

        targeted = _answer_for(answer, interrupt_id, interrupt_index)
        interrupt_type = str(payload.get("type") or "").strip().lower()

        if interrupt_type in REVIEW_INTERRUPT_TYPES:
            resume_map[interrupt_id] = _resolve_decision(payload, targeted)
        else:
            resume_map[interrupt_id] = _resolve_text(payload, targeted)

    return resume_map
