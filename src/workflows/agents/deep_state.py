"""Deep-agent state schema shared by supervisor / discovery / design."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages  # type: ignore[import]

from src.workflows.state import DICEState, _keep_last


class DICEDeepAgentState(DICEState, total=False):
    """State schema passed into ``create_deep_agent``.

    Extends outer ``DICEState`` so subgraph writes land on the same channels
    the orchestrator routes on (notably ``phase`` and ``pending_interaction``).
    """

    # deepagents may inject files / todos; keep last-writer-wins for safety.
    files: Annotated[dict[str, Any] | None, _keep_last]
    todos: Annotated[list[dict[str, Any]] | None, _keep_last]
    # Re-declare messages so type checkers see the reducer on this subclass.
    messages: Annotated[list[AnyMessage], add_messages]
