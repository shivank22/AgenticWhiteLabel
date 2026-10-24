"""Minimal HITL round-trip demo without deepagents.

Builds a tiny StateGraph that calls interrupt(), then resumes with Command.
"""

from __future__ import annotations

import asyncio
from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from src.workflows.interrupts import build_interrupt_payload, extract_interrupt_payloads
from src.workflows.resume import resolve_resume_map


class DemoState(TypedDict, total=False):
    question: str
    answer: str


def ask_node(state: DemoState) -> dict[str, Any]:
    payload = build_interrupt_payload(
        interrupt_id="demo-1",
        summary=state.get("question") or "Continue?",
        interrupt_type="input",
        phase_id="review",
        node_id="demo",
        action_type="ask_user",
        raw={"options": ["yes", "no"]},
    )
    answer = interrupt(payload)
    return {"answer": str(answer)}


async def main() -> None:
    graph = StateGraph(DemoState)
    graph.add_node("ask", ask_node)
    graph.add_edge(START, "ask")
    graph.add_edge("ask", END)
    app = graph.compile(checkpointer=MemorySaver())

    config = {"configurable": {"thread_id": "demo-thread"}}
    result = await app.ainvoke({"question": "Proceed to design?"}, config)
    print("first invoke (should be interrupted):", result)

    snapshot = await app.aget_state(config)
    payloads = extract_interrupt_payloads(snapshot)
    print("open interrupts:", payloads)

    resume_map = resolve_resume_map(snapshot=snapshot, answer="yes")
    resumed = await app.ainvoke(Command(resume=resume_map), config)
    print("resumed:", resumed)


if __name__ == "__main__":
    asyncio.run(main())
