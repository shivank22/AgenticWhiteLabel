I think this is where you should move away from fully agent-driven orchestration and towards workflow-driven orchestration with agent-driven execution.

Your example is actually a good fit for a deterministic LangGraph workflow.

You have:

- Supervisor Agent – understands the request, manages the overall objective and makes decisions.
- Discovery Deep Agent – investigates the existing system, gathers facts and produces findings.
- Design Deep Agent – consumes discovery findings and produces architecture and design.
- Execution Engine – manages sequencing, parallelism, dependencies, persistence and completion.

The key principle:

The workflow decides what runs next. The agents decide how to accomplish their assigned work.

You don't need the Supervisor to repeatedly reason about whether Discovery should run before Design. That dependency is already known.

## 1. The orchestration I'd build

Suppose a user requests:

"Modernize this legacy application."

User Request

Supervisor Agent

Understand scope · Identify objectives · Create execution request

Phase 1 — Discovery Deep Agent

Parallel decomposition

Codebase

Analysis

Dependencies

Analysis

Infrastructure

Analysis

Join all discovery results into a Discovery Report

Discovery Validation Gate

Are findings complete enough to design?

Phase 2 — Design Deep Agent

Parallel decomposition

Architecture

Security

Technology

Join results into a Design Specification

Supervisor Agent

Review design · Resolve gaps · Present final outcome

Notice the distinction:

- Discovery and Design execute sequentially because Design depends on Discovery.
- Inside Discovery, its subagents can execute in parallel.
- Inside Design, its specialists can also execute in parallel.
- If Discovery finds a missing requirement, it can request an additional discovery task before the validation gate passes.

That's deterministic orchestration with dynamic execution inside phases.

## 2. How I would split responsibilities

| Component            | Responsibility                                                   | Decision-making                     |
| -------------------- | ---------------------------------------------------------------- | ----------------------------------- |
| Supervisor Agent     | Understand request, establish scope, assess final result         | LLM                                 |
| Workflow Controller  | Enforce Discovery → Design ordering                              | Deterministic                       |
| Discovery Deep Agent | Investigate, decompose, research                                 | LLM                                 |
| Discovery Join       | Wait for workers and aggregate findings                          | Deterministic                       |
| Discovery Gate       | Check completeness and decide whether more discovery is required | Rules or LLM with structured output |
| Design Deep Agent    | Create architecture and design                                   | LLM                                 |
| Design Join          | Aggregate architecture, security and technology outputs          | Deterministic                       |
| Final Supervisor     | Review and present final design                                  | LLM                                 |

This maps directly to LangGraph's distinction between workflows and agents:

- Workflows have predetermined code paths.
- Agents dynamically decide their own processes and tool usage.

LangGraph explicitly recommends combining both patterns.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://docs.langchain.com\&sz=32)

Docs by LangChain+1



## 3. Where do Deep Agents fit technically?

I'd compile Discovery and Design as independent subgraphs.

Root LangGraph

Supervisor node

Discovery subgraph

Its own Deep Agent, state and checkpointer configuration

Planner → Dynamic workers (`Send`)

Aggregator

Validation gate

Design subgraph

Independent Deep Agent, skills and tools

Planner → Architecture / Security / Technology workers

Design Aggregator

Final Supervisor

LangGraph supports compiled graphs being used as nodes inside parent graphs. When the child needs an isolated message history and a different state schema, invoke it from a wrapper node. This is particularly useful for your specialist agents.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://docs.langchain.com\&sz=32)

Docs by LangChain+1



## 4. Python implementation pattern

Assume you've already created these three Deep Agents:

```
supervisor_agent = create_deep_agent(...)discovery_agent = create_deep_agent(...)design_agent = create_deep_agent(...)
```

The root workflow invokes them explicitly.

```
from typing import TypedDict, Literalfrom langchain_core.messages import HumanMessagefrom langgraph.graph import StateGraph, START, ENDclass WorkflowState(TypedDict, total=False):    run_id: str    request: str    scope: str    discovery_report: dict    discovery_decision: str    discovery_attempts: int    design_spec: dict    final_answer: strasync def supervisor_intake(state):    result = await supervisor_agent.ainvoke({        "messages": [            HumanMessage(content=state["request"])        ]    })    return {"scope": extract_scope(result)}async def run_discovery(state):    result = await discovery_agent.ainvoke({        "messages": [            HumanMessage(content=f"""            Investigate the application.            Objective: {state['scope']}            """)        ]    })
```

The extraction and completeness-checking functions are application-specific; the orchestration structure is the important part.

## 5. Where `Send` and dynamic workers fit

Inside Discovery, you can use `Send` to create a dynamic number of workers.

For example:

```
Discovery Agent
      |
      v
Discovery Planner
      |
      | Generates 5 tasks
      v
    Send()
      |
      ├── Worker 1
      ├── Worker 2
      ├── Worker 3
      ├── Worker 4
      └── Worker 5
      |
      v
Discovery Aggregator
      |
      v
Discovery Report
```

The same applies to Design.

LangGraph supports this orchestrator-worker pattern natively, including dynamic worker creation and aggregation.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://docs.langchain.com\&sz=32)

Docs by LangChain+1



## 6. One architectural decision for your DICE platform

I would separate execution into three layers:

| Layer                  | Technology           | Owns                                                 |
| ---------------------- | -------------------- | ---------------------------------------------------- |
| Workflow orchestration | LangGraph            | Phase transitions, gates, dependencies               |
| Agent execution        | Deep Agents          | Reasoning, skills, tools, decomposition              |
| Platform runtime       | FastAPI + PostgreSQL | Runs, artifacts, events, SSE, operational visibility |

Since you've already built PostgreSQL-backed event delivery and SSE, I would reuse that infrastructure for the workflow and worker lifecycle.&#x20;

One warning: don't let both LangGraph and your custom PostgreSQL scheduler independently own the same task's retries, completion and parent joins. Pick one authoritative execution controller.

My final recommendation: Use LangGraph as the deterministic outer workflow, Deep Agents as independently configured phase-level subgraphs, and `Send` for dynamic parallel work inside those phases.

This gives you the best of both worlds: predictable enterprise execution with agentic flexibility where it actually adds value.