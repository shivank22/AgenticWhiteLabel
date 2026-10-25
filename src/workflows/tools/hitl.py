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
    """Update the outer-graph phase channel (supervisor / specialist handoff).

    NOTE: Prefer transition_phase() which validates prerequisites first.
    This tool bypasses checks and should only be used for recovery/override.
    """
    normalised = str(phase or "").strip().lower()
    if normalised == "completed":
        normalised = "complete"
    return Command(update={"phase": normalised})


def _extract_state_from_config(config: RunnableConfig | None) -> dict[str, Any]:
    """Extract graph state from RunnableConfig."""
    if config is None:
        return {}
    configurable = config.get("configurable", {})
    state: dict[str, Any] = {}
    for key in ("phase", "aa_number", "discovery_status", "application_id"):
        if key in configurable:
            state[key] = configurable[key]
    return state


@tool
def check_phase_readiness(
    target_phase: str,
    config: RunnableConfig = None,
) -> dict[str, Any]:
    """Check if prerequisites are met for transitioning to target_phase.

    Returns structured assessment:
    - allowed: whether transition can proceed
    - current_phase: current phase
    - target_phase: requested phase
    - checks: list of individual check results
    - message: summary message

    Call this to diagnose what's blocking a phase transition.
    """
    from src.workflows.backends import get_shared_backend
    from src.workflows.phase_requirements import check_phase_requirements

    backend = get_shared_backend()
    state = _extract_state_from_config(config)

    result = check_phase_requirements(target_phase, state, backend)
    return result.to_dict()


@tool
def transition_phase(
    target_phase: str,
    config: RunnableConfig = None,
) -> Command | dict[str, Any]:
    """Transition to a new phase after validating all prerequisites.

    Deterministically checks required files and state before allowing transition:
    - discovery: requires artifact.yaml, supervisor canvas, aa_number
    - design: requires discovery artifacts, discovery_status=complete
    - complete: requires design artifacts

    Returns Command to update phase if allowed, or a dict with failed checks
    and guidance if prerequisites are not met.
    """
    from src.workflows.backends import get_shared_backend
    from src.workflows.phase_requirements import PHASES, check_phase_requirements

    backend = get_shared_backend()
    state = _extract_state_from_config(config)

    result = check_phase_requirements(target_phase, state, backend)

    if result.allowed:
        return Command(update={"phase": result.target_phase})

    failed_checks = [c for c in result.checks if not c.passed]
    return {
        "status": "blocked",
        "allowed": False,
        "current_phase": result.current_phase,
        "target_phase": result.target_phase,
        "message": result.message,
        "failed_checks": [
            {"type": c.check_type, "target": c.target, "message": c.message}
            for c in failed_checks
        ],
        "requirements": {
            "files": PHASES.get(result.target_phase, {}).get("required_files", []),
            "state": PHASES.get(result.target_phase, {}).get("required_state", []),
            "status": PHASES.get(result.target_phase, {}).get("required_status", {}),
        },
        "guidance": (
            f"To transition to '{result.target_phase}', ensure all required "
            f"files exist and state fields are set. Use check_phase_readiness('{result.target_phase}') "
            "for detailed diagnostics."
        ),
    }
