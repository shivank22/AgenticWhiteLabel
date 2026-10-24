from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph  # type: ignore[import]

from src.workflows.state import DICEState


def _normalise_phase(raw_phase: Any) -> str:
    phase = str(raw_phase or "").strip().lower()
    if phase == "completed":
        return "complete"
    return phase


def _route_from_start(state: dict[str, Any]) -> str:
    """Entry routing: supervisor owns the workflow unless already complete."""
    phase = _normalise_phase(state.get("phase"))
    if phase == "complete":
        return END
    return "supervisor"


def _route_after_supervisor(_state: dict[str, Any]) -> str:
    """Supervisor delegates to discovery-agent / design-agent via task() and exits to END."""
    return END


async def build_orchestrator_graph(
    *, checkpointer: Any, store: Any | None = None
) -> Any:
    """Build and compile the DICE hierarchical Deep Agent orchestrator graph."""
    from src.llm.factory import get_llm
    from src.workflows.agents.design.agent import build_design_agent
    from src.workflows.agents.discovery.agent import build_discovery_agent
    from src.workflows.agents.supervisor.agent import build_supervisor_agent

    llm = get_llm()

    discovery_agent = await build_discovery_agent(llm=llm, store=store)
    design_agent = await build_design_agent(llm=llm, store=store)
    supervisor_agent = await build_supervisor_agent(
        llm=llm,
        store=store,
        discovery_agent=discovery_agent,
        design_agent=design_agent,
    )

    graph: StateGraph = StateGraph(DICEState)
    graph.add_node("supervisor", supervisor_agent)

    graph.add_conditional_edges(
        START,
        _route_from_start,
        {
            "supervisor": "supervisor",
            END: END,
        },
    )
    graph.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {END: END},
    )

    compile_kwargs: dict[str, Any] = {"checkpointer": checkpointer}
    if store is not None:
        compile_kwargs["store"] = store

    return graph.compile(**compile_kwargs)
