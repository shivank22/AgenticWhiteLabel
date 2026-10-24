"""Shared human-in-the-loop tool helpers."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.types import Command, interrupt  # type: ignore[import]

_INPUT_TYPES = {"text", "choice"}
_APPROVAL_OPTIONS = ["approve", "deny"]
_REVIEW_DECISIONS = ["approve", "edit", "reject"]


def _ask_user_interrupt(
    *,
    question: str,
    phase: str,
    input_type: str = "text",
    options: list[str] | None = None,
) -> Any:
    normalized_type = input_type.strip().lower() or "text"
    if normalized_type not in _INPUT_TYPES:
        raise ValueError("input_type must be 'text' or 'choice'")
    if normalized_type == "choice" and not options:
        raise ValueError("options are required when input_type is 'choice'")

    answer = interrupt(
        {
            "type": "question",
            "input_type": normalized_type,
            "question": question,
            "options": list(options or []),
            "phase": phase,
        }
    )
    if isinstance(answer, dict):
        for key in ("response", "answer", "text", "value"):
            if key in answer:
                return answer[key]
    return answer


@tool
def ask_user_interrupt(
    question: str,
    phase: str,
    input_type: str = "text",
    options: list[str] | None = None,
) -> Any:
    """Ask the user a required question and pause until they answer.

    Use input_type "text" or "choice". Choice requires options.
    Pass the current phase.
    """
    return _ask_user_interrupt(
        question=question,
        phase=phase,
        input_type=input_type,
        options=options,
    )


@tool
def ask_user(
    question: str,
    input_type: str = "text",
    options: list[str] | None = None,
    phase: str = "intake",
    config: RunnableConfig = None,
) -> str:
    """Ask the user a question and pause execution until a reply is provided.

    Use input_type="choice" only when options are provided.
    """
    normalized_phase = str(phase or "").strip()
    if not normalized_phase:
        cfg = dict((config or {}).get("configurable", {}))
        normalized_phase = str(cfg.get("phase") or "").strip() or "intake"

    return _ask_user_interrupt(
        question=question,
        phase=normalized_phase,
        input_type=input_type,
        options=options,
    )


@tool
def request_tool_approval(action: str, reason: str, tool_name: str = "") -> str:
    """Ask the user to approve or deny a sensitive tool action."""
    answer = interrupt(
        {
            "type": "tool_approval",
            "input_type": "approval",
            "question": "Approve this action?",
            "action": action,
            "reason": reason,
            "tool_name": tool_name,
            "options": _APPROVAL_OPTIONS,
            "phase": "discovery",
        }
    )
    return str(answer)


def request_tool_review(
    *,
    action: dict[str, Any],
    reason: str,
    tool_name: str,
    phase: str = "discovery",
    allowed_decisions: list[str] | None = None,
) -> Any:
    """Pause execution and request a structured human review decision.

    This helper is intended for side-effecting tool calls where reviewers may
    approve, edit arguments, or reject the action.
    """
    decisions = list(allowed_decisions or _REVIEW_DECISIONS)
    answer = interrupt(
        {
            "type": "tool_review",
            "input_type": "tool_review",
            "question": "Review this tool call before execution.",
            "tool_name": tool_name,
            "action_request": action,
            "reason": reason,
            "allowed_decisions": decisions,
            "options": decisions,
            "phase": phase,
        }
    )
    return answer


def review_tool_call(
    *,
    action: dict[str, Any],
    reason: str,
    tool_name: str,
    phase: str = "discovery",
    allowed_decisions: list[str] | None = None,
    max_reasks: int = 1,
    request_fn: Any | None = None,
) -> dict[str, Any]:
    """Run a review gate and return a canonical decision.

    An answer that cannot be interpreted re-opens the gate instead of falling
    through to execution. Once the re-ask budget is spent the call is denied,
    so an ambiguous reply can never authorise a side-effecting call.

    `request_fn` lets callers pass their own module-level
    `request_tool_review` reference so it stays patchable in tests.
    """
    from src.workflows.interrupts import normalize_tool_review_decision

    ask = request_fn or request_tool_review
    current_reason = reason
    for _ in range(max(0, max_reasks) + 1):
        answer = ask(
            action=action,
            reason=current_reason,
            tool_name=tool_name,
            phase=phase,
            allowed_decisions=allowed_decisions,
        )
        decision = normalize_tool_review_decision(answer)
        if str(decision.get("type") or "").strip().lower() != "unknown":
            return decision
        current_reason = (
            f"{reason} The previous reply was not a valid decision. "
            f"Reply with one of: {', '.join(allowed_decisions or _REVIEW_DECISIONS)}."
        )

    return {
        "type": "reject",
        "message": "No valid review decision was provided.",
    }


def is_approval(value: Any) -> bool:
    return str(value or "").strip().lower() in {"approve", "approved", "yes", "y"}


@tool
def set_phase(phase: str) -> Command:
    """Update the outer-graph phase channel (supervisor / specialist handoff)."""
    normalised = str(phase or "").strip().lower()
    if normalised == "completed":
        normalised = "complete"
    return Command(update={"phase": normalised})
