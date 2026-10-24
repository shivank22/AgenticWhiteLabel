"""Deferred domain-tool stubs.

Each stub is a real langchain-compatible tool that raises until you implement it.
Agent builders import the names they need; HITL tools are the only live ones.
"""

from __future__ import annotations

from typing import Any


def _deferred(name: str) -> Any:
    def _tool(*_args: Any, **_kwargs: Any) -> str:
        raise NotImplementedError(
            f"Tool '{name}' is deferred — implement it under "
            f"src/workflows/agents/*/tools.py (or replace this stub)."
        )

    _tool.__name__ = name
    _tool.__doc__ = f"Deferred DICE tool: {name}."
    return _tool


# --- supervisor ---
get_application_template = _deferred("get_application_template")
instantiate_application = _deferred("instantiate_application")
read_artifact = _deferred("read_artifact")
write_artifact = _deferred("write_artifact")
list_application_migrations = _deferred("list_application_migrations")
create_application_migration = _deferred("create_application_migration")
update_application_migration = _deferred("update_application_migration")

# --- discovery ---
# call_authenticated_api lives in discovery/tools/authenticated_api.py
select_repositories = _deferred("select_repositories")
proteas_code_analysis = _deferred("proteas_code_analysis")
populate_discovery_artifacts_from_servers = _deferred(
    "populate_discovery_artifacts_from_servers"
)

# --- design ---
read_discovery_artifact = _deferred("read_discovery_artifact")
populate_design_artifacts = _deferred("populate_design_artifacts")
