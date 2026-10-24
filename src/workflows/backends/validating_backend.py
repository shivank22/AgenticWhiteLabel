"""Validating StoreBackend wrapper for deepagents filesystem writes.

# TODO: reconstruct from photo edge (opening paragraphs of module docstring)

This backend closes that hole at the only place every write must pass through.
A write to an artifact path must have a registered validator and satisfy it; a
write to any other path is untouched. Failures come back as ``WriteResult(error=...)``
rather than exceptions, because deepagents surfaces those strings to the model
as the tool result, which is what lets it correct itself on the next turn.

``edit`` is refused outright on validated paths: a partial string replacement
is applied before its result can be inspected, so there is no way to reject one
without leaving the artifact corrupted. Validated artifacts are small and
structured, so rewriting them whole is the safe contract.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.validators import has_validator, validate_artifact

_ARTIFACTS_PREFIX = "artifacts/"

if TYPE_CHECKING:  # pragma: no cover - typing only
    from deepagents.backends.protocol import EditResult, WriteResult


def _normalise(file_path: str) -> str:
    """Strip the leading slash so paths match the validator registry keys."""
    return file_path.lstrip("/")


def _rejection(file_path: str, issues: tuple[str, ...]) -> str:
    """Render validator issues as a message the model can act on."""
    bullets = "\n".join(f" - {issue}" for issue in issues)
    return (
        f"Error: refused to write '{file_path}' because it does not conform to "
        f"its schema:\n{bullets}\n"
        "Fix the content and write it again. Read the matching file under "
        "/templates/ if you need the expected shape."
    )


def _edit_refusal(file_path: str) -> str:
    """Explain why in-place edits are not allowed on validated artifacts."""
    return (
        f"Error: '{file_path}' is a schema-validated artifact and cannot be "
        "edited in place. Read it, apply your change, and write the complete "
        "document back with write_file so it can be validated as a whole."
    )


def _unregistered_refusal(file_path: str) -> str:
    """Explain why an artifact path without a validator cannot be written."""
    return (
        f"Error: refused to write '{file_path}' because no validator is "
        "registered for this artifact path. Register a validator before "
        "writing under /artifacts/."
    )


def build_validating_store_backend(store_backend_cls: type) -> type:
    """Return a `StoreBackend` subclass that validates before persisting.

    The class is built at call time so importing this module does not require
    deepagents to be installed.
    """
    from deepagents.backends.protocol import (
        EditResult as _EditResult,
        WriteResult as _WriteResult,
    )

    class ValidatingStoreBackend(store_backend_cls):  # type: ignore[valid-type,misc]
        """StoreBackend with schema enforcement on write."""

        def _check(self, file_path: str, content: str) -> str | None:
            key = _normalise(file_path)
            if not has_validator(key):
                if key.startswith(_ARTIFACTS_PREFIX):
                    return _unregistered_refusal(file_path)
                return None
            result = validate_artifact(key, content)
            if result.ok:
                return None
            return _rejection(file_path, result.issues)

        def write(self, file_path: str, content: str) -> WriteResult:
            error = self._check(file_path, content)
            if error is not None:
                return _WriteResult(error=error)
            return super().write(file_path, content)

        async def awrite(self, file_path: str, content: str) -> WriteResult:
            error = self._check(file_path, content)
            if error is not None:
                return _WriteResult(error=error)
            return await super().awrite(file_path, content)

        def edit(
            self,
            file_path: str,
            old_string: str,
            new_string: str,
            replace_all: bool = False,  # noqa: FBT001, FBT002
        ) -> EditResult:
            key = _normalise(file_path)
            if key.startswith(_ARTIFACTS_PREFIX):
                if not has_validator(key):
                    return _EditResult(error=_unregistered_refusal(file_path))
                return _EditResult(error=_edit_refusal(file_path))
            return super().edit(file_path, old_string, new_string, replace_all)

        async def aedit(
            self,
            file_path: str,
            old_string: str,
            new_string: str,
            replace_all: bool = False,  # noqa: FBT001, FBT002
        ) -> EditResult:
            key = _normalise(file_path)
            if key.startswith(_ARTIFACTS_PREFIX):
                if not has_validator(key):
                    return _EditResult(error=_unregistered_refusal(file_path))
                return _EditResult(error=_edit_refusal(file_path))
            return await super().aedit(file_path, old_string, new_string, replace_all)

    return ValidatingStoreBackend
