from __future__ import annotations

from pathlib import Path
from typing import Any

from src.config.settings import get_settings
from src.io.filesystem import filesystem_namespace
from src.workflows.backends.validating_backend import build_validating_store_backend

# Stable backend root anchored to the DICE service root, not process CWD.
# parents[3] = project root for src/ structure
SERVICE_ROOT = Path(__file__).resolve().parents[3]
BASE_DIR = SERVICE_ROOT / "data"

# Read-only mount for artifact templates, exposed to agents as /templates/*.
TEMPLATES_MOUNT = "/templates/"
TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "templates"

_shared_backend: Any | None = None


def _resolve_skills_dir(configured_path: str) -> Path:
    """Resolve skills dir robustly for both local and container CWDs.

    `skills_base_path` is typically `skills` and is intended to be relative
    to the DICE service root (`.../dice`), not necessarily the process CWD.
    """
    raw = Path(configured_path)
    if raw.is_absolute():
        return raw

    # Resolve against service root: /.../dice
    service_root = Path(__file__).resolve().parents[3]
    candidate = (service_root / raw).resolve()
    if candidate.exists():
        return candidate

    # Fallback to current working directory resolution.
    return raw.resolve()


def get_shared_backend() -> Any:
    """Return a singleton deepagents CompositeBackend.

    Notes:
    - deepagents 0.7+ no longer supports backend callables/factories.
    - Default backend is StoreBackend with user/thread namespace isolation,
      wrapped to reject writes that fail a registered artifact validator.
    - Skills are mounted via /skills/* using a dedicated FilesystemBackend.
    - Artifact templates are mounted via /templates/* the same way, so agents
      read them with the built-in ``read_file`` instead of a template tool.
    """
    global _shared_backend
    if _shared_backend is not None:
        return _shared_backend

    try:
        from deepagents.backends import (  # type: ignore[import]
            CompositeBackend,
            FilesystemBackend,
            StoreBackend,
        )
    except ImportError as exc:
        raise RuntimeError(
            "deepagents is not installed. Run: pip install deepagents",
        ) from exc

    settings = get_settings()
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    skills_src = _resolve_skills_dir(settings.skills_base_path)
    if not skills_src.exists() or not skills_src.is_dir():
        raise RuntimeError(
            f"Configured skills path does not exist or is not a directory: {skills_src}",
        )
    if not TEMPLATES_DIR.exists() or not TEMPLATES_DIR.is_dir():
        raise RuntimeError(
            f"Artifact templates path does not exist or is not a directory: {TEMPLATES_DIR}",
        )

    validating_store_cls = build_validating_store_backend(StoreBackend)

    _shared_backend = CompositeBackend(
        default=validating_store_cls(namespace=filesystem_namespace),
        routes={
            "/skills/": FilesystemBackend(
                root_dir=skills_src,
                virtual_mode=True,
            ),
            TEMPLATES_MOUNT: FilesystemBackend(
                root_dir=TEMPLATES_DIR,
                virtual_mode=True,
            ),
        },
    )
    return _shared_backend
