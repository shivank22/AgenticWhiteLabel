"""Phase transition requirements - deterministic checks before phase handoff.

Each phase defines:
- required_files: paths that must exist and be non-empty
- required_state: state fields that must be set
- required_status: specific status values to check
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PHASES: dict[str, dict[str, Any]] = {
    "intake": {
        "required_files": [],
        "required_state": [],
        "description": "Initial intake - collect application identity",
    },
    "discovery": {
        "required_files": [
            "/artifacts/artifact.yaml",
            "/scratch/supervisor/canvas.md",
        ],
        "required_state": ["aa_number"],
        "description": "Application discovery - gather estate and code signals",
    },
    "design": {
        "required_files": [
            "/artifacts/artifact.yaml",
            "/artifacts/discovery/discovery-details.yaml",
            "/scratch/discovery/canvas.md",
        ],
        "required_state": ["aa_number"],
        "required_status": {"discovery_status": "complete"},
        "description": "Migration design - platform selection and planning",
    },
    "complete": {
        "required_files": [
            "/artifacts/artifact.yaml",
            "/artifacts/discovery/discovery-details.yaml",
            "/artifacts/design/design.yaml",
            "/scratch/design/canvas.md",
        ],
        "required_state": ["aa_number"],
        "description": "Workflow complete - all phases finished",
    },
}

PHASE_ORDER = ("intake", "discovery", "design", "complete")


@dataclass(frozen=True)
class CheckResult:
    """Result of a single requirement check."""

    check_type: str
    target: str
    passed: bool
    message: str


@dataclass(frozen=True)
class TransitionResult:
    """Result of a phase transition attempt."""

    allowed: bool
    current_phase: str
    target_phase: str
    checks: tuple[CheckResult, ...]
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "current_phase": self.current_phase,
            "target_phase": self.target_phase,
            "checks": [
                {
                    "type": c.check_type,
                    "target": c.target,
                    "passed": c.passed,
                    "message": c.message,
                }
                for c in self.checks
            ],
            "message": self.message,
        }


def _check_file_exists(path: str, backend: Any) -> CheckResult:
    """Check that a file exists and is non-empty."""
    result = backend.read(path)
    if result.error:
        return CheckResult(
            check_type="file",
            target=path,
            passed=False,
            message=f"File not found: {path}",
        )
    content = result.file_data.get("content", "") if result.file_data else ""
    if not content.strip():
        return CheckResult(
            check_type="file",
            target=path,
            passed=False,
            message=f"File is empty: {path}",
        )
    return CheckResult(
        check_type="file",
        target=path,
        passed=True,
        message=f"File exists: {path}",
    )


def _check_state_field(field: str, state: dict[str, Any]) -> CheckResult:
    """Check that a state field is set and non-empty."""
    value = state.get(field)
    if not value:
        return CheckResult(
            check_type="state",
            target=field,
            passed=False,
            message=f"State field not set: {field}",
        )
    return CheckResult(
        check_type="state",
        target=field,
        passed=True,
        message=f"State field set: {field}={value}",
    )


def _check_status_value(
    field: str, expected: str, state: dict[str, Any]
) -> CheckResult:
    """Check that a state field has a specific value."""
    value = state.get(field)
    if value != expected:
        return CheckResult(
            check_type="status",
            target=field,
            passed=False,
            message=f"Status mismatch: {field}='{value}', expected '{expected}'",
        )
    return CheckResult(
        check_type="status",
        target=field,
        passed=True,
        message=f"Status correct: {field}={expected}",
    )


def check_phase_requirements(
    target_phase: str,
    state: dict[str, Any],
    backend: Any,
) -> TransitionResult:
    """Check all requirements for transitioning to target_phase."""
    current_phase = str(state.get("phase") or "intake").strip().lower()
    target = target_phase.strip().lower()
    if target == "completed":
        target = "complete"

    if target not in PHASES:
        return TransitionResult(
            allowed=False,
            current_phase=current_phase,
            target_phase=target,
            checks=(),
            message=f"Unknown phase: {target}. Valid phases: {', '.join(PHASES.keys())}",
        )

    requirements = PHASES[target]
    checks: list[CheckResult] = []

    for path in requirements.get("required_files", []):
        checks.append(_check_file_exists(path, backend))

    for field in requirements.get("required_state", []):
        checks.append(_check_state_field(field, state))

    for field, expected in requirements.get("required_status", {}).items():
        checks.append(_check_status_value(field, expected, state))

    failed = [c for c in checks if not c.passed]
    if failed:
        failed_items = "; ".join(c.message for c in failed)
        return TransitionResult(
            allowed=False,
            current_phase=current_phase,
            target_phase=target,
            checks=tuple(checks),
            message=f"Cannot transition to '{target}': {failed_items}",
        )

    return TransitionResult(
        allowed=True,
        current_phase=current_phase,
        target_phase=target,
        checks=tuple(checks),
        message=f"Ready to transition from '{current_phase}' to '{target}'",
    )
