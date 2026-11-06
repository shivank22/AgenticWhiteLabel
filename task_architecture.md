# DICE Agent Orchestration Architecture

## Supervisor uses `task()` only; delegated subagents use TODO middleware

**Status:** Proposed architecture\
**Scope:** Supervisor delegation and subagent execution\
**Core decision:** The Supervisor does not maintain a TODO list. It
delegates work through `task()`. Each delegated subagent may use TODO
middleware to plan and track its own work.

------------------------------------------------------------------------

## 1. Executive summary

DICE uses a two-level execution model:

1.  **Supervisor:** Interprets the user request, selects an existing
    subagent, delegates a bounded unit of work through `task()`,
    consumes the result, and decides what to do next.
2.  **Subagent:** Executes the delegated work. If TODO middleware is
    enabled for that subagent, it creates and updates its own internal
    TODO list.

There is no Supervisor TODO list in this design. A `task()` invocation
is a delegation/execution request, not a TODO item and not, by itself, a
durable workflow record.

The architecture must keep these concepts separate:

-   **Delegation:** A Supervisor-to-subagent invocation.
-   **Subagent plan:** The delegated agent's own TODO list, if its
    middleware creates one.
-   **Execution activity:** Messages, tool calls, state changes,
    outputs, failures and approvals.
-   **Persistence:** DICE-owned records required for recovery, audit and
    UI reconstruction.

## 2. Scope and assumptions

This design assumes:

-   The Supervisor can invoke already-defined subagents through the
    supported Deep Agents `task()` mechanism.
-   Subagents are configured with TODO middleware when their work
    benefits from internal planning.
-   The Supervisor does not use `write_todos` and does not expose a
    Supervisor-level TODO list.
-   A subagent's TODO state is scoped to that subagent execution. It
    must not be treated as a global plan unless DICE explicitly builds a
    separate aggregation layer.
-   Exact `task()` registration and invocation syntax must follow the
    installed Deep Agents version and execution interface. Do not assume
    that examples for the JavaScript dynamic-subagent interpreter are
    interchangeable with Python tool-based subagent registration.

## 3. Logical architecture

``` text
User request
    |
    v
Supervisor
    |
    |-- task(existing_subagent, delegated instructions)
    |          |
    |          v
    |      Subagent runtime
    |          |
    |          |-- TODO middleware (agent-local plan)
    |          |-- tools / model calls
    |          |-- artifacts / result
    |          |
    |          v
    |      Subagent result
    |
    |-- consume result
    |-- optionally delegate another task
    |
    v
Supervisor final response

Streaming and persistence:
Supervisor + subagent runtime events
    -> DICE event normalizer
    -> durable execution records / event log
    -> SSE
    -> React execution UI
```

The Supervisor is the coordinator, but the subagent owns its internal
plan.

## 4. Supervisor responsibilities

The Supervisor should:

1.  Understand the user's request and determine whether delegation is
    needed.
2.  Select an appropriate registered subagent.
3.  Construct a clear delegation instruction with scope, constraints,
    expected output and relevant context.
4.  Invoke `task()` using the supported API for the deployed Deep Agents
    version.
5.  Wait for the result when the workflow is sequential, or use the
    supported concurrent pattern for independent work.
6.  Inspect the returned result and decide whether another delegation,
    clarification, approval or final response is required.
7.  Communicate a concise synthesis to the user.

The Supervisor should not:

-   Create a second, duplicate TODO plan for work already planned by
    subagents.
-   Pretend a delegation exists merely because it described an intention
    in natural language.
-   Infer task completion from a subagent message that does not
    represent a completed invocation.
-   Treat a subagent's internal TODO list as the Supervisor's own plan.

## 5. Subagent responsibilities

Each delegated subagent is responsible for its assigned scope.

When TODO middleware is enabled, the subagent can:

-   Decompose its delegated work into actionable steps.
-   Update TODO statuses as it progresses.
-   Use tools and produce intermediate outputs.
-   Return a final result to the Supervisor.

A subagent TODO list is **agent-local execution state**. It is not
automatically a cross-agent dependency graph, a durable DICE task
database, or a guarantee of deterministic progress.

If a subagent is invoked more than once, DICE should distinguish each
invocation using a unique delegation/execution identifier. Do not assume
the subagent's TODO state is isolated or persisted correctly without
verifying its checkpointer, thread/session configuration and state
lifecycle.

## 6. Sequential and parallel delegation

### Sequential

Use sequential invocation when later work depends on an earlier result.

``` text
Supervisor
  |
  | task(ResearchAgent)
  | await result
  |
  | task(ImplementationAgent, include research result)
  | await result
  |
  v
Supervisor synthesizes outcome
```

The second delegation starts after the first invocation returns. The
Supervisor should pass the relevant first-agent output explicitly to the
second agent unless the architecture provides a deliberate shared-state
mechanism.

### Parallel

Use concurrent invocation only when the delegated work is independent
and the selected `task()` interface supports concurrent execution.

``` text
                 +--> task(SecurityAgent) --+
Supervisor ----- |                           | --> collect results
                 +--> task(ResearchAgent) ---+
```

Do not use parallel execution when agents modify the same files, share
mutable resources without coordination, or depend on one another's
outputs.

### Conditional

The Supervisor may inspect a completed result and choose the next
subagent dynamically:

``` text
Supervisor
    |
    v
task(AnalysisAgent)
    |
    v
inspect result
    |
    +-- if code changes required --> task(CodingAgent)
    |
    +-- if clarification needed --> ask user
    |
    +-- otherwise --> final response
```

## 7. Runtime event and state model

DICE should distinguish framework-native stream data from DICE's
normalized application events.

Useful sources may include:

-   Root graph message events: Supervisor messages and tool-call
    messages.
-   Root graph state/update events: changes to root graph state.
-   Subgraph/subagent stream events: nested agent messages and state
    updates, when subgraph streaming is enabled and supported by the
    runtime.
-   Custom events: explicit application progress signals emitted by
    instrumented code.
-   Invocation completion/error: the authoritative result of the
    delegated invocation.

The precise stream modes, event shapes, namespace behavior and subagent
stream helpers vary by LangGraph/Deep Agents version and execution
interface. Build and test an adapter against the exact installed
versions. Do not assume that a generic `tasks` stream event is always
the lifecycle API for the Deep Agents `task()` function.

### Recommended normalized event envelope

``` json
{
  "event_id": "evt_01",
  "event_type": "delegation.started",
  "run_id": "run_123",
  "delegation_id": "del_456",
  "parent_run_id": "run_123",
  "agent_id": "research_agent",
  "agent_name": "Research Agent",
  "task_description": "Research the authentication requirements",
  "status": "running",
  "sequence": 12,
  "timestamp": "2026-11-06T20:30:00Z",
  "payload": {}
}
```

Recommended event types:

-   `delegation.created`
-   `delegation.started`
-   `delegation.completed`
-   `delegation.failed`
-   `subagent.message`
-   `subagent.tool.started`
-   `subagent.tool.completed`
-   `subagent.todo.updated`
-   `subagent.artifact.created`
-   `approval.required`

These are **DICE application event names**, not claims about built-in
LangGraph event names. The normalizer maps framework events and
lifecycle callbacks into this contract.

### Correlation identifiers

At minimum, preserve:

-   `run_id`: top-level Supervisor run.
-   `delegation_id`: unique invocation/call identifier for one `task()`
    execution.
-   `agent_id`: registered subagent identity/type.
-   `thread_id` or equivalent checkpoint/session identifier, where
    applicable.
-   `sequence` or another ordering mechanism for replay and
    deduplication.

Use the actual framework tool-call ID or invocation identifier when
available. If the runtime does not expose a stable identifier in the
required place, create a DICE correlation ID at the delegation boundary
and propagate it through subagent config/metadata where supported.

## 8. Persistence and recovery

SSE is a delivery mechanism, not the source of truth.

Persist enough information to reconstruct the execution UI after a
refresh or reconnect:

### Delegation record

-   delegation ID
-   parent run ID
-   agent ID/name
-   delegated instruction or safe/redacted summary
-   status: queued, running, completed, failed, cancelled
-   start/end timestamps
-   result reference or summarized result
-   error metadata, if failed

### Subagent TODO snapshot

When TODO middleware state is observable, persist a versioned snapshot
associated with the relevant delegation:

-   delegation ID
-   subagent thread/checkpoint identity
-   TODO item ID (DICE-generated if middleware does not provide a stable
    ID)
-   content
-   status
-   snapshot version / event sequence
-   updated timestamp

Do not assume a TODO list is durable simply because it appears in graph
state. Verify checkpointer configuration, thread identity, state
retention and how repeated invocations are isolated.

### Event log

Persist normalized events (or an equivalent replayable event history)
with a monotonic sequence per run/delegation. Use idempotent writes so
duplicate stream delivery does not create duplicate UI items.

On reconnect, the client should fetch a current snapshot and resume
streaming from a known cursor/sequence if the transport supports it.

## 9. Failure and edge cases

-   **Subagent fails:** Mark the delegation failed; preserve the last
    known TODO snapshot and error summary. The Supervisor decides
    whether to retry, choose another agent or report failure.
-   **Subagent returns with pending TODOs:** Do not mark every TODO
    completed. The delegation may have returned partial work; display
    the actual statuses and result.
-   **Supervisor disconnects:** Recover from persisted run/delegation
    state and graph checkpointing. Do not rely on in-memory SSE queues
    as durable storage.
-   **Duplicate events:** Deduplicate using event ID or
    run/delegation/sequence.
-   **Concurrent subagents:** Keep each TODO list scoped to its
    delegation; do not merge lists by agent type.
-   **Approval required:** Represent the approval as a distinct paused
    state, not as ordinary running or completed.
-   **No TODOs created:** Show the delegation and its activity without
    an empty TODO panel.

## 10. Design decisions

  -----------------------------------------------------------------------
  Concern                             Decision
  ----------------------------------- -----------------------------------
  Supervisor planning                 No TODO middleware/list in this
                                      design

  Supervisor delegation               `task()` only

  Existing subagents                  Register/configure them as
                                      supported subagent targets

  Subagent planning                   TODO middleware enabled per
                                      subagent where useful

  TODO ownership                      The subagent invocation owns its
                                      TODO state

  Cross-agent dependency              Supervisor controls it through
                                      sequential/conditional delegation

  UI                                  Supervisor timeline with expandable
                                      delegation cards

  Persistence                         DICE-owned delegation records, TODO
                                      snapshots and event history

  Transport                           SSE for live delivery;
                                      database/checkpoint state for
                                      recovery
  -----------------------------------------------------------------------

## 11. Validation checklist before production

1.  Confirm the installed Deep Agents version and the exact `task()`
    interface being used.
2.  Verify how existing compiled subagents are registered and invoked.
3.  Verify that the subagent TODO middleware is actually active in the
    delegated runtime.
4.  Capture one subagent TODO creation and subsequent status updates
    from a real stream.
5.  Confirm that subgraph events can be correlated to the correct
    delegation invocation.
6.  Test two concurrent invocations of the same subagent type and
    confirm their TODO state does not leak.
7.  Test sequential delegation and confirm the second agent receives the
    first agent's result.
8.  Test failure, retry, interrupt/approval and browser reconnect.
9.  Verify that the UI can be rebuilt from persisted records without
    replaying the entire model conversation.

------------------------------------------------------------------------

**Final principle:** `task()` defines who executes delegated work. The
subagent's TODO middleware defines how that worker plans its own work.
DICE's execution layer connects, correlates and persists both without
inventing a Supervisor TODO list.


---

# 12. Implementation guide (Python / Deep Agents / LangGraph)

This section gives a concrete implementation pattern for the design above. It uses the **normal Deep Agents `task` tool** with precompiled subagents. It does not use the interpreter-based Dynamic Subagents feature.

## 12.1 Version and API distinctions

The examples below target the current documented Python API shape:

- Deep Agents `>=0.7.0`: TODO planning is opt-in. Add `TodoListMiddleware()` explicitly to each worker that needs it.
- LangGraph `>=1.1`: `version="v2"` gives a consistent stream-part shape (`type`, `ns`, `data`) for stream-mode APIs.
- LangGraph `v1.2` introduces typed event streaming (`stream_events` / `astream_events`, version `v3`), documented as the preferred higher-level projection API for new applications; it is experimental and should be version-pinned and integration-tested before production use.

**Do not confuse the two `task()` APIs:**

1. **Normal Deep Agents delegation (recommended here):** `task` is a tool registered by `SubAgentMiddleware`. The Supervisor's model emits a tool call. Application Python code does not call `await task(...)`.
2. **Dynamic Subagents:** an interpreter exposes a JavaScript `task()` global inside `eval` code. This is a separate, beta interpreter capability. It is not required for this design.

## 12.2 Install dependencies

Use the package versions pinned and tested by your project. A minimal install looks like:

```bash
pip install -U deepagents langgraph langchain
```

If using a Postgres checkpointer, install the appropriate LangGraph Postgres package for your deployment and use the existing DICE database/checkpointer configuration.

## 12.3 Build two existing worker agents with TODO middleware

If you are disabling the automatic `general-purpose` subagent using §12.5, run that profile-registration code **before** creating the Supervisor and workers below.

`TodoListMiddleware` is provided by LangChain's agent middleware package. Add it when each worker is created. Do not add it to the Supervisor.

```python
from deepagents import create_deep_agent
from langchain.agents.middleware import TodoListMiddleware

MODEL = "openai:YOUR_TOOL_CALLING_MODEL"

research_agent = create_deep_agent(
    model=MODEL,
    tools=[search_docs, fetch_internal_reference],
    system_prompt=(
        "You are the Research Agent. Execute only the delegated research task. "
        "For complex multi-step work, use write_todos to plan and track your "
        "own work. Return a concise report with evidence and unresolved questions."
    ),
    middleware=[
        TodoListMiddleware(),
    ],
)

coding_agent = create_deep_agent(
    model=MODEL,
    tools=[read_repository, edit_repository, run_tests],
    system_prompt=(
        "You are the Coding Agent. Execute only the delegated implementation task. "
        "For complex multi-step work, use write_todos to plan and track your "
        "own work. Report changed files, tests, and remaining risks."
    ),
    middleware=[
        TodoListMiddleware(),
    ],
)
```

Important:

- The `todos` state belongs to the worker graph that owns the middleware.
- The Supervisor does not receive a merged copy of the worker's `todos` state just because it receives the worker's final task result.
- A compiled worker is used as provided. Middleware must be installed before it is compiled; the parent cannot append middleware to an already-compiled `CompiledSubAgent`.
- A Deep Agent's default general-purpose subagent behavior is version/configuration dependent. If workers must not delegate further, disable the default general-purpose subagent through a harness profile for the model, or explicitly configure the worker's subagent policy. See §12.5.

## 12.4 Register the existing compiled workers with the Supervisor

A compiled subagent must expose a `messages` state key. `create_deep_agent` already provides this. For a custom LangGraph graph, ensure its state schema includes `messages`.

```python
from deepagents import CompiledSubAgent, create_deep_agent

supervisor = create_deep_agent(
    model=MODEL,
    tools=[],
    system_prompt=(
        "You are the DICE Supervisor. You do not maintain a TODO list. "
        "Delegate bounded units of work to the available specialist agents "
        "using the task tool. Choose the agent based on its description. "
        "For dependent work, invoke one agent, wait for its result, inspect "
        "that result, and only then invoke the next agent. Do not issue "
        "multiple task calls in one turn when the work is sequential. "
        "Synthesize worker results and report incomplete work honestly."
    ),
    subagents=[
        CompiledSubAgent(
            name="research",
            description=(
                "Researches technical requirements, documentation, architecture "
                "options and evidence. Returns a concise report."
            ),
            runnable=research_agent,
        ),
        CompiledSubAgent(
            name="coding",
            description=(
                "Implements code changes, runs tests and reports changed files "
                "and test results."
            ),
            runnable=coding_agent,
        ),
    ],
)
```

The Supervisor has the `task` tool because synchronous subagents are registered. It has no `TodoListMiddleware`, so it has no Supervisor-owned `write_todos` plan.

The Supervisor's model chooses when to call `task`. The application registers available workers; it does not directly invoke the `task` tool function.

## 12.5 Control the automatic `general-purpose` subagent

Current Deep Agents documentation says a `general-purpose` synchronous subagent is added automatically unless replaced or disabled. If DICE wants the Supervisor to delegate **only** to the two named workers, disable that default for the Supervisor's model using a harness profile.

```python
from deepagents import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    register_harness_profile,
)

register_harness_profile(
    MODEL,
    HarnessProfile(
        general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
    ),
)
```

Register the profile before creating the agents. Harness profiles are keyed by provider/model, so this can also affect other agents created with the same model identifier. Test the resulting tool list at startup.

If a catch-all worker is desired, leave the default enabled or replace it with a named `general-purpose` configuration.

## 12.6 Sequential delegation

In normal tool-based delegation, sequential execution means the Supervisor emits one `task` tool call, receives its result, reasons over that result, and emits the next call in a later model turn.

```text
Supervisor model turn 1
    -> task(research)
    -> Research Agent runs
    -> task tool result returned to Supervisor

Supervisor model turn 2
    -> task(coding, including relevant research findings)
    -> Coding Agent runs
    -> task tool result returned to Supervisor

Supervisor model turn 3
    -> final synthesis
```

Use explicit prompt instructions to request one delegation at a time. A prompt is guidance, not a hard concurrency guarantee. If sequential execution is a strict invariant, enforce it in a guard/middleware around the task tool or use an explicit graph orchestration layer that controls when the next delegation can be issued.

Pass the first worker's relevant findings in the second worker's delegated description. An isolated subagent normally receives the task description, not the Supervisor's entire conversation history.

## 12.7 Parallel delegation

The normal Deep Agents `task` tool supports multiple task calls in one model turn; Deep Agents documents this as the standard parallel delegation path. The Supervisor's model can emit independent `task` calls together, and the runtime executes them concurrently.

Conceptually, the Supervisor may issue two calls in one assistant turn:

```text
task(research, "Research OAuth and MSAL requirements")
task(security, "Independently review the security implications")
```

Do not translate this into Python `asyncio.gather(task(...))`: that is not the normal Python task-tool API. If deterministic fan-out over a programmatically known collection is required, evaluate the separate Dynamic Subagents interpreter feature. It requires interpreter middleware and is currently beta.

Use parallel delegation only for independent work. Do not parallelize workers that edit the same files or depend on one another's results without explicit coordination.

## 12.8 Invoke and stream the Supervisor graph

For a self-hosted FastAPI service that owns the compiled graph, LangGraph's v2 stream format is a practical low-level integration. `subgraphs=True` is essential to receive nested worker stream events.

```python
from langchain_core.messages import HumanMessage

async def run_supervisor(supervisor, user_text: str, thread_id: str):
    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    async for part in supervisor.astream(
        {"messages": [HumanMessage(content=user_text)]},
        config=config,
        stream_mode=["messages", "updates", "values"],
        subgraphs=True,
        version="v2",
    ):
        event_type = part["type"]
        namespace = part["ns"]       # () means root; non-empty means nested scope
        payload = part["data"]

        if event_type == "messages":
            message_chunk, metadata = payload
            # Use metadata and namespace to classify Supervisor vs worker tokens.
            # Forward only the safe fields needed by the DICE UI.
            yield {
                "kind": "message_chunk",
                "namespace": list(namespace),
                "agent_name": metadata.get("lc_agent_name"),
                "node": metadata.get("langgraph_node"),
                "content": message_chunk.content,
            }

        elif event_type == "values":
            # Full state snapshot for the scope that emitted this event.
            # A worker's TODO state may appear here when the worker's
            # middleware state is streamed from its subgraph.
            if namespace and isinstance(payload, dict) and "todos" in payload:
                yield {
                    "kind": "subagent_todo_snapshot",
                    "namespace": list(namespace),
                    "todos": payload["todos"],
                }

        elif event_type == "updates":
            # Node-level partial updates. Inspect updates for TODO changes too.
            if namespace:
                for node_name, update in payload.items():
                    if isinstance(update, dict) and "todos" in update:
                        yield {
                            "kind": "subagent_todo_snapshot",
                            "namespace": list(namespace),
                            "node": node_name,
                            "todos": update["todos"],
                        }
```

This is an adapter skeleton, not a drop-in production parser. The exact `namespace`, node names and message metadata depend on the actual graph and Deep Agents version. Capture representative runs and verify the shapes before writing the normalizer.

### What each stream mode contributes

- `messages`: token/message chunks from Supervisor and, with `subgraphs=True`, nested worker model calls.
- `updates`: state keys changed by a node/step; useful for detecting a `todos` update.
- `values`: full state snapshots for the scope that emitted the event; useful for rebuilding the latest worker TODO list.
- `tasks`: LangGraph task start/finish events. This mode requires a checkpointer. It is useful for graph-runtime diagnostics, but do not assume it alone is the authoritative lifecycle for every Deep Agents `task` tool call.
- `custom`: application-defined progress events emitted by instrumented nodes/tools.

For production, consider adding `tasks` and `custom` after verifying their payloads with your graph/checkpointer combination. Avoid `debug` in the normal user-facing stream because it exposes detailed runtime data.

## 12.9 Capture the Supervisor's `task` call and result

The Supervisor's tool call is represented in its assistant message. The matching tool result is represented by a tool message. The tool-call ID is the natural correlation key between the request and result. The Python tool argument is commonly named `subagent_type`; keep the parser tolerant of naming differences across pinned versions.

A simplified state-update inspection pattern:

```python
from langchain_core.messages import AIMessage, ToolMessage

def inspect_root_messages(update: dict):
    for message in update.get("messages", []):
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                if call["name"] == "task":
                    yield {
                        "event": "delegation.created",
                        "tool_call_id": call["id"],
                        "tool_name": call["name"],
                        "arguments": call["args"],
                    }

        elif isinstance(message, ToolMessage):
            yield {
                "event": "delegation.result",
                "tool_call_id": message.tool_call_id,
                "status": getattr(message, "status", None),
                "content": message.content,
            }
```

Use this as a parsing pattern, not as a guarantee that every runtime version emits the same update shape. In the main stream adapter, inspect root (`ns == ()`) updates for Supervisor messages. A tool result with the matching `tool_call_id` closes the delegation. Preserve the raw namespace and worker metadata for correlating nested worker events.

**Correlation warning:** Do not assume that a namespace segment's runtime ID is identical to the Supervisor tool-call ID. Confirm this with a real trace. If the runtime does not expose a direct join key, add DICE correlation metadata at the delegation boundary or use the typed Deep Agents subagent projection where available.

## 12.10 FastAPI SSE endpoint

A simple endpoint can translate normalized events into Server-Sent Events:

```python
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

router = APIRouter()

@router.post("/runs/{thread_id}/stream")
async def stream_run(thread_id: str, request: RunRequest):
    async def event_generator():
        async for event in run_supervisor(
            supervisor=supervisor,
            user_text=request.message,
            thread_id=thread_id,
        ):
            # In production: persist before publish, redact payloads,
            # assign a per-run sequence, and make delivery idempotent.
            yield f"event: {event['kind']}\n"
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

For production, add authentication/authorization, disconnect handling, cancellation policy, heartbeat frames, event IDs, bounded buffering, redaction, and replay from durable storage. A POST request is valid for this server-side streaming pattern when the frontend uses `fetch()` and reads the response stream; browser `EventSource` itself is GET-only.

## 12.11 What the Supervisor receives from a worker

With a normal isolated `CompiledSubAgent`, the parent receives the worker's final result as the `task` tool result. The parent does not automatically receive every intermediate worker message or the worker's entire `todos` state as its own state.

That is why DICE should use two channels of information:

- **Task result:** worker's final answer returned to the Supervisor.
- **Nested stream/state:** worker messages, tools and TODO state used to update the UI.

Do not rely on the Supervisor's root `values` snapshot to contain the worker's private `todos`. Read the nested subgraph scope when it is streamed, or explicitly publish the worker TODO state through a custom event/persistence mechanism.

## 12.12 Optional: typed event streaming

LangGraph v1.2 documents a higher-level typed event-streaming API (`stream_events` / `astream_events`, version `v3`) with projections for messages, values, tools, lifecycle and discovered subgraphs. Deep Agents' current frontend guidance also exposes coordinator messages and subagent handles separately.

This is attractive for a new UI because it avoids hand-parsing every raw stream chunk. However, the v3 event-streaming API is experimental. Pin compatible versions of `langgraph`, `langgraph-sdk` / `langgraph-api` where relevant, and test the exact in-process API before adopting it for DICE. The v2 stream-mode example above is the compatibility-oriented implementation path in this document.

## 12.13 Verification tests

Before connecting React, create a small integration test that proves:

1. Supervisor tool list contains `task` and does not contain `write_todos`.
2. Research and Coding worker tool lists contain `write_todos`.
3. A `task` call starts the intended compiled worker.
4. Worker `values`/`updates` streams expose `todos` in a non-empty subgraph namespace.
5. Root Supervisor state does not accidentally display the worker's private TODOs as Supervisor TODOs.
6. The root `task` ToolMessage has the same tool-call ID as the originating AIMessage tool call.
7. Two invocations of the same worker type can be distinguished as separate delegations.
8. Sequential instructions produce one delegation result before the next delegation call.
9. Parallel calls are independently correlated.
10. Failure and interrupt paths produce accurate statuses.

---

## 13. Official implementation references

- [Deep Agents: Subagents](https://docs.langchain.com/oss/python/deepagents/subagents)
- [Deep Agents: Task planning](https://docs.langchain.com/oss/python/deepagents/overview#task-planning)
- [Deep Agents: Streaming and subagent progress](https://docs.langchain.com/oss/python/deepagents/subagents#streaming)
- [Deep Agents: Dynamic subagents](https://docs.langchain.com/oss/python/deepagents/dynamic-subagents)
- [Deep Agents: Harness profiles](https://docs.langchain.com/oss/python/deepagents/profiles)
- [LangGraph: Streaming](https://docs.langchain.com/oss/python/langgraph/streaming)
- [LangGraph: Event streaming](https://docs.langchain.com/oss/python/langgraph/event-streaming)
- [LangChain: TodoListMiddleware reference](https://reference.langchain.com/python/langchain/agents/middleware/todo/TodoListMiddleware)

