"""Unit tests for HITL payload + resume mapping (no LLM / deepagents required)."""

from __future__ import annotations

from types import SimpleNamespace

from src.workflows.interrupts import (
    build_interrupt_payload,
    extract_interrupt_payloads,
    is_approved_decision,
    make_gate_id,
    normalize_tool_review_decision,
)
from src.workflows.resume import resolve_resume_map


def test_build_interrupt_payload_defaults():
    payload = build_interrupt_payload(interrupt_id="i-1", summary="Proceed?")
    assert payload["interrupt_id"] == "i-1"
    assert payload["gate_id"] == "i-1"
    assert payload["type"] == "input"
    assert payload["summary"] == "Proceed?"
    assert payload["required_roles"] == []


def test_make_gate_id_prefix():
    gate = make_gate_id(phase_id="review", node_id="supervisor", action_type="ask_user")
    assert gate.startswith("g-review-supervisor-ask_user-")


def test_normalize_tool_review_decision():
    assert normalize_tool_review_decision("approve") == {"type": "approve"}
    assert normalize_tool_review_decision("no")["type"] == "reject"
    assert normalize_tool_review_decision({"decision": "edit"})["type"] == "edit"
    assert normalize_tool_review_decision("maybe")["type"] == "unknown"


def test_is_approved_decision():
    assert is_approved_decision("yes")
    assert is_approved_decision({"approved": True})
    assert not is_approved_decision("reject")


def test_extract_and_resolve_resume_map():
    interrupt = SimpleNamespace(
        id="runtime-1",
        value={
            "interrupt_id": "caller-1",
            "type": "tool_review",
            "options": ["approve", "reject"],
        },
    )
    task = SimpleNamespace(interrupts=[interrupt])
    snapshot = SimpleNamespace(tasks=[task])

    payloads = extract_interrupt_payloads(snapshot)
    assert payloads[0]["interrupt_id"] == "runtime-1"
    assert payloads[0]["payload_interrupt_id"] == "caller-1"

    resume = resolve_resume_map(snapshot=snapshot, answer="1")
    assert resume["runtime-1"]["type"] == "approve"


def test_resolve_text_choice_by_index():
    interrupt = SimpleNamespace(
        id="runtime-2",
        value={
            "type": "input",
            "options": ["rework_discovery", "complete"],
        },
    )
    snapshot = SimpleNamespace(tasks=[SimpleNamespace(interrupts=[interrupt])])
    resume = resolve_resume_map(snapshot=snapshot, answer="2")
    assert resume["runtime-2"] == "complete"
