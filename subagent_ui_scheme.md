# DICE Execution UI Scheme

## Supervisor `task()` delegation with subagent TODO middleware

**Status:** Proposed UI and event contract\
**Scope:** React UI, FastAPI SSE normalization and durable execution
state\
**Core decision:** The Supervisor is displayed as the coordinator. Each
`task()` invocation becomes a delegation card. If the delegated subagent
uses TODO middleware, its own TODO list appears nested inside that card.

------------------------------------------------------------------------

## 1. UX principles

1.  Do not show a Supervisor TODO list. The Supervisor uses `task()` for
    delegation only.
2.  Show each actual `task()` invocation as a distinct delegation.
3.  Show the delegated agent's own TODO list inside its delegation card,
    when present.
4.  Keep messages/tool activity separate from TODO state: a tool call is
    activity, not automatically a TODO.
5.  Support sequential, parallel and conditional delegation with the
    same components.
6.  Never invent progress percentages. Derive counts from actual TODO
    statuses; show a percentage only if the underlying work reports a
    meaningful measure.
7.  Treat persisted execution state as the source for refresh/reconnect.
    SSE is the live update channel.

## 2. Information hierarchy

``` text
Conversation / Run
└── Supervisor
    ├── Supervisor messages
    ├── Delegation: Research Agent (task() invocation)
    │   ├── Delegated instruction
    │   ├── Status and timing
    │   ├── Subagent TODO list (if middleware produced one)
    │   ├── Live messages / tool activity
    │   └── Artifacts / result
    ├── Delegation: Coding Agent (task() invocation)
    │   ├── Delegated instruction
    │   ├── Status and timing
    │   ├── Subagent TODO list (if middleware produced one)
    │   ├── Live messages / tool activity
    │   └── Artifacts / result
    └── Supervisor final response
```

A delegation is not a TODO. The nested TODOs belong to the subagent
execution that created them.

## 3. Main screen layout

Recommended default: a single execution timeline in the conversation
view.

### Supervisor timeline

Display:

-   Supervisor status (thinking, delegating, waiting for result,
    responding, completed, failed).
-   Supervisor user-facing messages.
-   Delegation activities in the order they were created.
-   Final Supervisor response.

A `task()` tool call should produce a delegation card once its
identity/arguments are known. Avoid rendering the raw tool-call JSON as
the primary user-facing UI; show a concise, safe summary of the
delegated instruction and target agent.

### Delegation card

Collapsed card:

``` text
+--------------------------------------------------+
| Research Agent                         COMPLETED |
| Research authentication requirements             |
| 3 internal steps completed                       |
| 2m 14s                               [Expand v]  |
+--------------------------------------------------+
```

Expanded card:

``` text
+--------------------------------------------------+
| Research Agent                         COMPLETED |
| Delegated task: Research authentication          |
|                                                  |
| INTERNAL PLAN                                    |
| [x] Review OAuth2 flows                           |
| [x] Review MSAL integration                       |
| [x] Prepare recommendations                       |
|                                                  |
| ACTIVITY                                         |
| - Searched documentation                          |
| - Compared authentication flows                  |
|                                                  |
| OUTPUT                                           |
| - research-findings.md                            |
+--------------------------------------------------+
```

For a running subagent:

``` text
+--------------------------------------------------+
| Coding Agent                             RUNNING |
| Delegated task: Implement authentication         |
|                                                  |
| INTERNAL PLAN                                    |
| [x] Create middleware                             |
| [>] Implement JWT validation                      |
| [ ] Add role-based authorization                  |
|                                                  |
| LATEST ACTIVITY                                  |
| Updating token validation logic...               |
+--------------------------------------------------+
```

If the subagent has no TODO middleware or has not created TODOs, omit
the INTERNAL PLAN section. Do not show an empty TODO panel.

## 4. Status model

### Delegation status

Suggested DICE UI states:

-   `created` / `queued`
-   `running`
-   `waiting` (only when the runtime explicitly indicates a
    wait/dependency/approval)
-   `completed`
-   `failed`
-   `cancelled`

Do not infer `waiting` merely because no token has arrived recently. Use
runtime state or explicit dependency metadata.

### TODO status

Map the middleware's actual statuses to UI labels. For example:

-   `pending` -\> Pending
-   `in_progress` -\> In progress
-   `completed` -\> Completed

Keep the original middleware status in the stored payload if the
middleware uses other values. Unknown statuses should be displayed
safely rather than silently mapped to completed.

### Progress

Show `completed_count / total_count`, calculated from the current TODO
snapshot. If total is zero, show no progress indicator. A count is not a
reliable measure of effort or time remaining.

## 5. Sequential and parallel display

### Sequential delegation

``` text
Supervisor
   |
   +-- Research Agent     [Completed]
   |
   +-- Coding Agent       [Running]
   |
   +-- Testing Agent      [Queued]
```

Use this display when the Supervisor awaits one `task()` result before
invoking the next. If showing "depends on", use explicit dependency
metadata rather than guessing from chronological order.

### Parallel delegation

``` text
Supervisor
   |
   +-- Research Agent     [Running]
   |
   +-- Security Agent     [Completed]
   |
   +-- Documentation      [Running]
```

Show sibling delegation cards concurrently. Each card owns its own TODO
list and activity feed.

### Conditional delegation

When the Supervisor inspects a result and then decides whether to
delegate another agent, append the new card to the timeline. Optionally
display a short Supervisor transition message explaining the decision.
Do not represent an uninvoked potential agent as a real task.

## 6. Event and data flow

``` text
Deep Agents / LangGraph runtime
    |
    +-- Root messages and tool calls (Supervisor)
    |
    +-- Subagent messages / tool calls / state updates
    |
    +-- Subagent TODO state updates
    |
    +-- Invocation completion / error
              |
              v
      FastAPI event normalizer
              |
       +------+------+
       |             |
       v             v
 PostgreSQL       SSE publisher
 durable state       |
       |              v
       +----------> React event reducer
                         |
                         v
                 Supervisor timeline
```

Framework-native stream events should be adapted into a stable DICE
contract. The event names below are DICE application events, not
built-in LangGraph event names.

## 7. Suggested SSE event contract

Common envelope:

``` json
{
  "event_id": "evt_01",
  "event_type": "subagent.todo.updated",
  "run_id": "run_123",
  "delegation_id": "del_456",
  "agent_id": "coding_agent",
  "sequence": 18,
  "timestamp": "2026-11-06T20:30:00Z",
  "payload": {}
}
```

Suggested events:

  -----------------------------------------------------------------------------
  DICE event                    Meaning                 UI action
  ----------------------------- ----------------------- -----------------------
  `supervisor.message`          Supervisor message      Append/update
                                update                  Supervisor message

  `delegation.created`          A `task()` call is      Create delegation card
                                identified              

  `delegation.started`          Invocation begins       Mark card running

  `delegation.completed`        Invocation returns      Mark card completed
                                successfully            

  `delegation.failed`           Invocation fails        Mark card failed

  `subagent.message`            Subagent message update Update
                                                        activity/messages

  `subagent.tool.started`       Subagent tool begins    Add live activity item

  `subagent.tool.completed`     Subagent tool ends      Complete activity item

  `subagent.todo.updated`       Subagent TODO state     Replace/reconcile
                                changes                 nested TODO snapshot

  `subagent.artifact.created`   Output artifact is      Add artifact link
                                available               

  `approval.required`           Execution pauses for    Show approval control
                                approval                
  -----------------------------------------------------------------------------

### Example: delegation created

``` json
{
  "event_type": "delegation.created",
  "run_id": "run_123",
  "delegation_id": "del_456",
  "agent_id": "coding_agent",
  "payload": {
    "agent_name": "Coding Agent",
    "description": "Implement authentication middleware"
  }
}
```

### Example: subagent TODO snapshot

Prefer sending a complete, versioned snapshot when the middleware
exposes the full TODO state. This simplifies client reconciliation.

``` json
{
  "event_type": "subagent.todo.updated",
  "run_id": "run_123",
  "delegation_id": "del_456",
  "agent_id": "coding_agent",
  "sequence": 21,
  "payload": {
    "version": 3,
    "todos": [
      {
        "id": "todo_1",
        "content": "Create authentication middleware",
        "status": "completed"
      },
      {
        "id": "todo_2",
        "content": "Implement JWT validation",
        "status": "in_progress"
      },
      {
        "id": "todo_3",
        "content": "Add role-based authorization",
        "status": "pending"
      }
    ]
  }
}
```

If only a delta is available, define explicit add/update/remove
semantics and require a stable TODO ID. Do not assume array index is a
stable identity.

## 8. Backend normalization rules

1.  Identify the Supervisor's `task()` tool call and create one DICE
    delegation record.
2.  Correlate nested subagent events with the correct delegation ID. Use
    framework call IDs, run metadata and/or propagated DICE correlation
    metadata.
3.  Detect subagent TODO state updates and publish a snapshot scoped to
    that delegation.
4.  Keep messages, tool activity, TODO updates and invocation lifecycle
    as separate event types.
5.  Persist the latest delegation state and TODO snapshot before or
    reliably alongside SSE publication.
6.  Assign event sequence numbers and deduplicate repeated delivery.
7.  Redact secrets, credentials, tokens and sensitive tool arguments
    before persistence or UI publication.
8.  Treat tool-call arguments and model-generated descriptions as
    untrusted display data; sanitize and truncate appropriately.

Important: exact stream modes, namespaces and subagent helpers depend on
the installed LangGraph/Deep Agents versions. Verify the actual runtime
stream payloads with an integration test. Do not assume a generic stream
mode alone provides a stable `task()` lifecycle contract.

## 9. React component structure

``` text
AgentRunView
├── SupervisorTimeline
│   ├── SupervisorMessage
│   ├── DelegationCard
│   │   ├── DelegationHeader
│   │   ├── DelegatedInstruction
│   │   ├── DelegationStatus
│   │   ├── SubagentTodoPanel       (conditional)
│   │   │   └── TodoItem
│   │   ├── SubagentActivityPanel
│   │   │   ├── AgentMessage
│   │   │   └── ToolActivityItem
│   │   ├── ArtifactList
│   │   └── ErrorDetails
│   └── SupervisorFinalResponse
└── ApprovalPanel                  (conditional)
```

Suggested state shape:

``` typescript
type TodoStatus = "pending" | "in_progress" | "completed" | string;

interface AgentTodo {
  id: string;
  content: string;
  status: TodoStatus;
}

interface Delegation {
  delegationId: string;
  agentId: string;
  agentName: string;
  description: string;
  status:
    | "created"
    | "queued"
    | "running"
    | "waiting"
    | "completed"
    | "failed"
    | "cancelled";
  todos?: AgentTodo[];
  todoVersion?: number;
  startedAt?: string;
  completedAt?: string;
}

interface AgentRunViewState {
  runId: string;
  supervisorStatus: string;
  delegations: Record<string, Delegation>;
  delegationOrder: string[];
}
```

Use `delegationId` as the React key. Do not key cards by agent type
because the same agent may be invoked multiple times in one run.

## 10. Reconnect and hydration

On initial page load or reconnect:

1.  Fetch the run snapshot from FastAPI.
2.  Render Supervisor messages, delegation records and each delegation's
    latest TODO snapshot.
3.  Connect/resume SSE from the last known sequence or cursor, if
    supported.
4.  Apply incoming events idempotently.
5.  If a sequence gap is detected, fetch a fresh snapshot.

Do not rely on browser memory or an in-process async queue as the only
record of progress. A browser refresh must not erase the execution view.

## 11. Acceptance criteria

-   [ ] No Supervisor TODO panel is rendered.
-   [ ] Every actual `task()` invocation creates exactly one delegation
    card.
-   [ ] Multiple invocations of the same agent type render as separate
    cards.
-   [ ] A subagent TODO list appears only when the subagent has produced
    one.
-   [ ] TODOs are scoped to the correct delegation, not merely the agent
    type.
-   [ ] TODO updates change the nested list without duplicating items.
-   [ ] Sequential delegations appear in invocation order.
-   [ ] Parallel delegations can show simultaneous running states.
-   [ ] Tool activity is not misrepresented as TODO completion.
-   [ ] Failure, cancellation, approval and partial completion are
    represented accurately.
-   [ ] Refresh/reconnect restores the latest state from persistence.
-   [ ] Event payloads are redacted and safe for display.

------------------------------------------------------------------------

## 12. Final UI recommendation

Use one Supervisor execution timeline. Each `task()` call creates an
expandable delegation card. Inside the card, show the delegated
subagent's own TODO list (if TODO middleware produced one), live
messages/tool activity and artifacts.

This preserves the correct ownership model:

-   **Supervisor:** delegates and coordinates through `task()`.
-   **Subagent:** plans and tracks its own work through TODO middleware.
-   **DICE:** correlates, persists and displays the complete execution.

No global TODO list is required for this setup.


---

# 13. Implementation guide: from LangGraph stream to React UI

This section provides code-oriented guidance for the DICE setup:

- Supervisor has the normal Deep Agents `task` tool, but no `TodoListMiddleware`.
- Each compiled worker has `TodoListMiddleware`.
- The worker's `todos` are displayed inside that worker's delegation card.
- The root Supervisor conversation and worker activity remain separate.

## 13.1 Important ownership rule

Do not read `stream.values?.todos` on the root stream and expect it to contain subagent TODOs. In this architecture, the Supervisor does not own TODO state.

Instead:

- Root namespace (`ns == ()`): Supervisor state/messages/tool calls.
- Non-empty namespace (`ns != ()`): nested graph/subagent events.
- Nested worker `values` / `updates`: worker TODO state, if exposed by the compiled worker's middleware and the runtime stream configuration.

The LangGraph stream must be started with `subgraphs=True` to receive nested subgraph events in the v2 stream-mode API.

## 13.2 Recommended normalized event types

Use a small set of DICE events, regardless of the underlying LangGraph stream shape:

```text
supervisor.message
delegation.created
delegation.started
delegation.completed
delegation.failed
subagent.message
subagent.tool.started
subagent.tool.completed
subagent.todo.snapshot
subagent.artifact.created
approval.required
```

These are DICE event names, not built-in LangGraph event names.

Prefer full TODO snapshots initially. A full snapshot is easier to reconcile than partial patches and is small for ordinary task lists.

## 13.3 FastAPI stream adapter example

The following is a starting point for an in-process graph stream. It demonstrates the key LangGraph fields: `type`, `ns`, and `data`.

```python
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage, HumanMessage

async def stream_dice_run(
    graph,
    user_message: str,
    thread_id: str,
) -> AsyncIterator[dict[str, Any]]:
    config = {"configurable": {"thread_id": thread_id}}

    # Local map: Supervisor task tool-call ID -> DICE delegation record.
    # Persist this mapping in PostgreSQL in production.
    delegations: dict[str, dict[str, Any]] = {}

    async for part in graph.astream(
        {"messages": [HumanMessage(content=user_message)]},
        config=config,
        stream_mode=["messages", "updates", "values"],
        subgraphs=True,
        version="v2",
    ):
        kind = part["type"]
        namespace = list(part["ns"])
        data = part["data"]

        if kind == "messages":
            message_chunk, metadata = data
            if message_chunk.content:
                yield {
                    "event_type": "subagent.message" if namespace else "supervisor.message",
                    "namespace": namespace,
                    "agent_name": metadata.get("lc_agent_name"),
                    "node_name": metadata.get("langgraph_node"),
                    "content": message_chunk.content,
                }

        elif kind == "updates":
            # updates data is {node_name: partial_state_update}
            for node_name, update in data.items():
                if not isinstance(update, dict):
                    continue

                # Root messages include the Supervisor's completed AIMessage
                # tool-call records and corresponding ToolMessage results.
                if not namespace:
                    for message in update.get("messages", []):
                        if isinstance(message, AIMessage):
                            for call in message.tool_calls:
                                if call.get("name") == "task":
                                    call_id = call["id"]
                                    delegation = {
                                        "delegation_id": call_id,
                                        "agent_name": call.get("args", {}).get(
                                            "subagent_type"
                                        ),
                                        "description": call.get("args", {}).get(
                                            "description"
                                        ),
                                        "status": "created",
                                    }
                                    delegations[call_id] = delegation
                                    yield {
                                        "event_type": "delegation.created",
                                        **delegation,
                                    }

                        elif isinstance(message, ToolMessage):
                            call_id = message.tool_call_id
                            if call_id in delegations:
                                delegation = delegations[call_id]
                                delegation["status"] = (
                                    "failed"
                                    if getattr(message, "status", None) == "error"
                                    else "completed"
                                )
                                yield {
                                    "event_type": (
                                        "delegation.failed"
                                        if delegation["status"] == "failed"
                                        else "delegation.completed"
                                    ),
                                    "delegation_id": call_id,
                                    "result": message.content,
                                }

                # Subagent TODO middleware updates may appear in nested updates.
                if namespace and "todos" in update:
                    yield {
                        "event_type": "subagent.todo.snapshot",
                        "namespace": namespace,
                        "node_name": node_name,
                        "todos": update["todos"],
                    }

        elif kind == "values":
            # A full state snapshot for the scope identified by namespace.
            if namespace and isinstance(data, dict) and "todos" in data:
                yield {
                    "event_type": "subagent.todo.snapshot",
                    "namespace": namespace,
                    "todos": data["todos"],
                }
```

**Adapt this parser to your actual stream payloads.** Depending on the graph and version, `updates` may represent message changes differently, and subagent namespace segments are runtime paths, not guaranteed to equal the `task` tool-call ID. Capture real payloads in an integration test before finalizing the correlation logic.

For production correlation, prefer a stable invocation identifier exposed by the runtime. Keep the raw namespace, `lc_agent_name` metadata and root tool-call ID. Do not infer a join by comparing strings unless a test proves the relationship for your pinned versions.

## 13.4 FastAPI SSE transport

```python
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()

@router.post("/runs/{thread_id}/events")
async def run_events(thread_id: str, body: RunRequest):
    async def generate():
        async for event in stream_dice_run(
            graph=supervisor,
            user_message=body.message,
            thread_id=thread_id,
        ):
            # Production: redact, persist, sequence and deduplicate first.
            yield f"event: {event['event_type']}\n"
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

Because this uses POST, consume it with `fetch()` and a `ReadableStream` parser. Native browser `EventSource` only supports GET. Alternatively, use a two-step API: POST to create/start a run, then GET an event stream for the returned run ID.

## 13.5 React state model

Use the delegation ID as the identity of a card. Do not use `agentName` as the key: the same worker can be called several times in one Supervisor run.

```typescript
type TodoStatus = "pending" | "in_progress" | "completed" | string;

interface AgentTodo {
  id: string;
  content: string;
  status: TodoStatus;
}

interface DelegationCardState {
  delegationId: string;
  agentName?: string;
  description?: string;
  status: "created" | "running" | "completed" | "failed" | "cancelled";
  todos: AgentTodo[];
  namespace?: string[];
  latestActivity?: string;
  result?: unknown;
}

interface RunUIState {
  supervisorMessages: string[];
  delegations: Record<string, DelegationCardState>;
  delegationOrder: string[];
}
```

If the middleware's TODO objects do not include stable IDs, DICE can assign IDs when normalizing the snapshot. Do not use array positions as persistent identities because the model can reorder or rewrite the plan.

## 13.6 React reducer

```typescript
type DiceEvent =
  | {
      event_type: "supervisor.message";
      content: string;
    }
  | {
      event_type: "delegation.created";
      delegation_id: string;
      agent_name?: string;
      description?: string;
    }
  | {
      event_type: "delegation.completed" | "delegation.failed";
      delegation_id: string;
      result?: unknown;
    }
  | {
      event_type: "subagent.todo.snapshot";
      delegation_id: string;
      todos: AgentTodo[];
    }
  | {
      event_type: "subagent.message";
      delegation_id: string;
      content: string;
    };

function applyDiceEvent(state: RunUIState, event: DiceEvent): RunUIState {
  switch (event.event_type) {
    case "supervisor.message":
      return {
        ...state,
        supervisorMessages: [...state.supervisorMessages, event.content],
      };

    case "delegation.created":
      return {
        ...state,
        delegationOrder: state.delegationOrder.includes(event.delegation_id)
          ? state.delegationOrder
          : [...state.delegationOrder, event.delegation_id],
        delegations: {
          ...state.delegations,
          [event.delegation_id]: {
            delegationId: event.delegation_id,
            agentName: event.agent_name,
            description: event.description,
            status: "created",
            todos: [],
          },
        },
      };

    case "delegation.completed":
    case "delegation.failed": {
      const current = state.delegations[event.delegation_id];
      if (!current) return state;

      return {
        ...state,
        delegations: {
          ...state.delegations,
          [event.delegation_id]: {
            ...current,
            status:
              event.event_type === "delegation.completed" ? "completed" : "failed",
            result: event.result,
          },
        },
      };
    }

    case "subagent.todo.snapshot": {
      const current = state.delegations[event.delegation_id];
      if (!current) return state;

      return {
        ...state,
        delegations: {
          ...state.delegations,
          [event.delegation_id]: {
            ...current,
            todos: event.todos,
          },
        },
      };
    }

    case "subagent.message": {
      const current = state.delegations[event.delegation_id];
      if (!current) return state;

      return {
        ...state,
        delegations: {
          ...state.delegations,
          [event.delegation_id]: {
            ...current,
            latestActivity: event.content,
          },
        },
      };
    }
  }
}
```

The example contract includes `delegation_id` on subagent events. The stream adapter above deliberately preserves `namespace` instead of pretending that it is the Supervisor tool-call ID. Before publishing to React, your FastAPI normalizer must resolve `delegation_id` from verified runtime correlation metadata. If the runtime does not expose a reliable join, persist the raw subgraph event under a runtime execution key and link it when the task call/result relationship is established. Do not guess.

## 13.7 Render the nested TODO panel

```tsx
function DelegationCard({ delegation }: {
  delegation: DelegationCardState;
}) {
  const hasTodos = delegation.todos.length > 0;
  const completed = delegation.todos.filter(
    (todo) => todo.status === "completed"
  ).length;

  return (
    <section className="delegation-card">
      <header>
        <strong>{delegation.agentName ?? "Subagent"}</strong>
        <span>{delegation.status}</span>
      </header>

      <p>{delegation.description}</p>

      {hasTodos && (
        <div className="subagent-todos">
          <div className="todo-heading">
            <strong>Agent plan</strong>
            <span>{completed}/{delegation.todos.length} completed</span>
          </div>

          <ul>
            {delegation.todos.map((todo) => (
              <li key={todo.id} data-status={todo.status}>
                {todo.content}
              </li>
            ))}
          </ul>
        </div>
      )}

      {delegation.latestActivity && (
        <p className="latest-activity">{delegation.latestActivity}</p>
      )}
    </section>
  );
}
```

If the worker has not created a TODO list, omit the plan section. Do not show an empty panel or imply that the worker is idle.

## 13.8 Frontend options from LangChain

For an application using LangGraph Agent Server and the LangChain frontend SDK, the Deep Agents frontend documentation describes:

- `stream.messages`: coordinator conversation/final synthesis.
- `stream.subagents`: live discovery of specialist workers and task metadata.
- `stream.values`: shared state values.
- tool-call state: tool cards and progress.
- interrupts: approvals and missing-input pauses.

It also documents `useMessages(stream, subagent)` for selecting subagent messages. This is a useful reference implementation pattern.

For DICE's own FastAPI SSE service, the custom normalizer above gives more control over PostgreSQL persistence, event IDs, permissions and the React contract. Do not assume the root `stream.values.todos` contains a worker's private TODO state; inspect the nested worker stream/state.

## 13.9 Durable state and reconnect

Persist at least:

- Run record: run ID, thread ID, user/tenant, status, timestamps.
- Delegation record: delegation ID, parent run, agent identity, task description, status, start/end times, result/error reference.
- Latest TODO snapshot: delegation ID, version, list of items, updated time.
- Event history: event ID, sequence, event type, delegation ID, payload after redaction.

On reconnect:

1. React fetches the latest run snapshot.
2. React renders Supervisor messages and delegation cards with the latest TODO snapshots.
3. React connects to SSE from a sequence cursor.
4. FastAPI replays events after that cursor and then streams live events.
5. React deduplicates by event ID and applies events in sequence.

Do not rely on an in-memory queue in one FastAPI pod as the only source of truth.

## 13.10 Official code/documentation references

- [Deep Agents subagents](https://docs.langchain.com/oss/python/deepagents/subagents)
- [Deep Agents frontend overview](https://docs.langchain.com/oss/python/deepagents/frontend)
- [LangGraph streaming and subgraph events](https://docs.langchain.com/oss/python/langgraph/streaming)
- [LangGraph event streaming](https://docs.langchain.com/oss/python/langgraph/event-streaming)
- [TodoListMiddleware API](https://reference.langchain.com/python/langchain/agents/middleware/todo/TodoListMiddleware)
- [Deep Agents 0.7.0 changelog](https://github.com/langchain-ai/deepagents/blob/main/libs/deepagents/CHANGELOG.md)

---

## 14. Final implementation summary

```text
Supervisor (no TodoListMiddleware)
    |
    | normal Deep Agents task tool call
    |
    +--> ResearchAgent (TodoListMiddleware)
    |       |
    |       +--> worker-local todos
    |       +--> messages / tools / artifacts
    |
    +--> CodingAgent (TodoListMiddleware)
            |
            +--> worker-local todos
            +--> messages / tools / artifacts

LangGraph stream with subgraphs=True
    |
    v
FastAPI normalizer
    |
    +--> PostgreSQL: delegation records + TODO snapshots + event log
    |
    +--> SSE: live normalized events
              |
              v
React:
  Supervisor timeline
    +-- Research delegation card
    |     +-- Research TODOs
    |     +-- Research activity
    +-- Coding delegation card
          +-- Coding TODOs
          +-- Coding activity
```

The Supervisor delegates. Each worker plans its own work. DICE correlates and persists both. React displays them hierarchically.
