"""Artifact schema validators — register validators before writing under /artifacts/."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

ValidatorFn = Callable[[str], "ValidationResult"]

_REGISTRY: dict[str, ValidatorFn] = {}


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    issues: tuple[str, ...] = field(default_factory=tuple)


def register_validator(path: str, fn: ValidatorFn) -> None:
    _REGISTRY[path.lstrip("/")] = fn


_ARTIFACTS_PREFIX = "artifacts/"


def has_validator(path: str) -> bool:
    key = path.lstrip("/")
    return key in _REGISTRY or key.startswith(_ARTIFACTS_PREFIX)


def validate_artifact(path: str, content: str) -> ValidationResult:
    key = path.lstrip("/")
    fn = _REGISTRY.get(key)
    if fn is not None:
        return fn(content)
    if key.startswith(_ARTIFACTS_PREFIX):
        return _non_empty(content)
    return ValidationResult(ok=False, issues=("No validator registered.",))


def _non_empty(content: str) -> ValidationResult:
    if not content.strip():
        return ValidationResult(ok=False, issues=("Content must not be empty.",))
    return ValidationResult(ok=True)
