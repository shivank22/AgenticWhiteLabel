# DICE Chat and Migration Document Workspace

**Implementation design brief for the DICE frontend and agent-streaming integration**  
**Version:** 1.0  
**Date:** 7 November 2026  
**Target:** React + Vite + TypeScript frontend, FastAPI backend, LangGraph v3 event streaming, Deep Agents, PostgreSQL

---

## 1. Executive recommendation

DICE should be designed as a **migration workspace with a conversational supervisor**, not as a chatbot with a file browser attached.

The current screen already has the right product structure:

1. Application navigation and conversation history on the left.
2. A supervisor-led conversation in the central pane.
3. A document explorer and generated-document preview on the right.
4. A migration phase indicator across the top.

Keep this structure. Improve the hierarchy, density, typography and event presentation rather than replacing the application wholesale.

### Product principle

- **Chat is for collaboration:** user messages, supervisor explanations, questions and final summaries.
- **Execution activity is for transparency:** agents, todos, tools, progress, approvals and failures.
- **Documents are the deliverable:** assessment, migration strategy, architecture, mappings, implementation artifacts and validation evidence.

These are connected in the user experience but should remain separate state models in the frontend and separate entities in the backend.

### Recommended visual direction

Use a Linear-inspired engineering workspace with a restrained DICE identity:

- Neutral slate/stone surfaces and strong typography.
- One primary accent for interactive/focus states.
- Meaningful status colours, not decorative colour everywhere.
- Compact, collapsible activity cards.
- A right-side document workspace with a collapsible document tree and tabbed documents.
- Small, purposeful animations instead of constant motion.

### Recommended frontend stack

| Concern | Recommendation |
|---|---|
| Framework | React + Vite + TypeScript |
| Component foundation | shadcn/ui |
| Agentic interaction patterns | shadcn AI Elements (copy/adapt into the repo) |
| Styling | Tailwind CSS and CSS variables |
| Icons | Lucide React |
| Animation | Motion for React (`motion`) |
| Client UI state | Zustand or the repository's existing store; avoid introducing a second store without need |
| Server/cache state | TanStack Query for snapshots, documents and conversation metadata |
| Streaming | FastAPI Server-Sent Events (SSE) |
| Markdown | Existing Markdown renderer or `react-markdown` with safe plugins |
| Code display | Shiki or an existing syntax-highlighter |
| Diagrams | Mermaid renderer with a safe allowlist/configuration |

**Do not introduce Bootstrap globally.** shadcn/ui is better aligned with a Tailwind-first application and gives DICE ownership of the component source. Do not combine Bootstrap's global CSS/reset/grid with Tailwind unless there is a specific isolated legacy integration requirement.

---

## 2. Current-screen assessment

The supplied screenshot shows the following areas:

- A left application sidebar with Home, Documents, Search, Help and conversation history.
- A migration phase tracker: Discover, Build, Modernize, Deploy and Release.
- A central Supervisor conversation pane.
- A document tree with folders such as design, discovery, subagents and supervisor.
- A right document preview showing a YAML artifact and nested structured metadata.

This is a good starting point. The main UX issue is not the overall concept; it is that execution lifecycle events, agent state and conversational content appear too similarly. The central pane reads like a log console, while the user needs to feel that they are talking to one supervisor who is coordinating work.

### Keep

- Existing left navigation and conversation history.
- The migration lifecycle concept.
- Split chat/document workspace.
- Document explorer and structured YAML display.
- UBS/DICE branding where required by the product.

### Change

| Current behaviour / appearance | Desired behaviour |
|---|---|
| Request received, workflow resumed, model agent, running and waiting appear as text rows | Render run state as a compact status strip or activity timeline |
| Long supervisor response fills the chat pane | Use readable message width, headings, lists and collapsible detail blocks |
| Agent activity is represented by small text labels | Use identifiable agent cards with current task and status |
| Tool activity is mixed with messages | Render tool calls as expandable trace rows/cards |
| Child todo progress is not visually hierarchical | Show global supervisor tasks, then specialist-local todos inside each agent card |
| Document tree, file metadata and preview compete for width | Make document preview primary; collapse or resize the tree |
| Many fine borders and small labels | Reduce border noise, increase spacing and typography hierarchy |
| Migration stepper consumes a large vertical band | Make the phase tracker compact and contextual |

---

## 3. Target workspace layout

### 3.1 Desktop composition

Retain the application sidebar, and make the main workspace a resizable two-pane layout:

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ DICE  / Project or Migration Name                 Phase: Discover   ● Running │
├──────────────┬───────────────────────────────┬───────────────────────────────┤
│              │                               │                               │
│ APPLICATION  │ CONVERSATION                  │ DOCUMENT WORKSPACE            │
│ SIDEBAR      │                               │                               │
│              │ User and Supervisor messages  │ Document tabs                 │
│ Home         │                               │                               │
│ Documents    │ Compact execution summaries   │ ┌───────────┬───────────────┐ │
│ Search       │                               │ │ Tree      │ Document      │ │
│ Help         │ Expandable specialist cards   │ │ / outline │ canvas        │ │
│              │                               │ │           │               │ │
│ Conversations│ Approval cards when required  │ │           │ Preview/edit  │ │
│              │                               │ │           │               │ │
│              │ Composer                       │ └───────────┴───────────────┘ │
└──────────────┴───────────────────────────────┴───────────────────────────────┘
```

### 3.2 Initial desktop sizing guidance

Treat these as starting values; use a resizable panel group and persist the user's preferred sizes.

| Region | Suggested width |
|---|---:|
| Application sidebar | 220–248 px; collapsible to 64–72 px |
| Conversation pane | 40–46% of remaining workspace |
| Document workspace | 54–60% of remaining workspace |
| Document tree inside right pane | 190–230 px; collapsible |
| Document canvas | Remaining right-pane width |

At a 1440 px desktop width, do not let the conversation or document editor become too narrow. Minimum practical widths should be enforced by the resizable panels.

### 3.3 Right document workspace

The right pane is not an execution inspector. Its primary purpose is migration deliverables.

Recommended internal structure:

1. Header with active artifact title, type, status and actions.
2. Document tabs for currently opened artifacts.
3. Optional collapsible document tree on the left inside the right pane.
4. Large document canvas/preview.
5. Optional footer/status area with version, autosave state and provenance.

Suggested top-level document categories:

```text
Migration workspace
├── 01 Assessment
│   ├── Architecture assessment
│   ├── Repository inventory
│   ├── Dependency analysis
│   └── Risk register
├── 02 Planning
│   ├── Migration strategy
│   ├── Migration roadmap
│   ├── Work package plan
│   └── Technical design
├── 03 Design and mapping
│   ├── API mapping
│   ├── Configuration mapping
│   ├── Data mapping
│   └── Architecture diagrams
├── 04 Implementation
│   ├── Source changes
│   ├── Configuration changes
│   ├── Patch/diff artifacts
│   └── Build output
└── 05 Validation and release
    ├── Test report
    ├── Compatibility report
    ├── Deployment plan
    └── Final migration report
```

The document categories should be configurable by migration type/skill. Do not hard-code Java migration names into generic workspace components.

### 3.4 Document interactions

Support:

- Open document in a tab without losing chat position.
- Close/reorder tabs.
- Collapse/expand document tree.
- Preview and edit modes.
- Markdown document rendering.
- Structured JSON/YAML tree view and raw source toggle.
- Code editor/viewer for source files and patches.
- Mermaid diagrams.
- Side-by-side version comparison.
- Version history and restore (subject to permissions).
- Comments/annotations and review status where required.
- Download/export.
- Link from a chat message or activity card to the exact artifact version.

### 3.5 Responsive behaviour

| Viewport | Behaviour |
|---|---|
| ≥1280 px | Sidebar + chat + document workspace all visible; resizable chat/document split |
| 900–1279 px | Sidebar collapsible; right document tree collapsible; maintain two primary panes where practical |
| 600–899 px | Use Conversation / Documents tabs; preserve run state when switching |
| <600 px | One pane at a time; document explorer as Sheet/Drawer; approval cards remain full-width |

Do not simply shrink desktop columns until the content is unusable. On tablet/mobile, switch modes deliberately.

---

## 4. Conversation experience

### 4.1 The supervisor owns the conversation

The user should perceive one primary conversational partner: the Supervisor.

Show in the main transcript:

- User messages.
- Supervisor assistant messages.
- Supervisor clarifying questions.
- Supervisor summaries and conclusions.
- Human approval/review cards that require the user.

Do not render every internal subagent model message as a normal conversation bubble. That creates a noisy, multi-speaker transcript and exposes internal reasoning that is not useful to the user.

### 4.2 Agent activity is a structured activity block

Place a compact activity summary inside or immediately after the supervisor message that initiated the work.

Example:

```text
Supervisor
I have completed the initial discovery. Three specialists are reviewing the
application in parallel. I will consolidate their findings into the migration plan.

Execution activity  ·  2 running / 1 completed
  ✓ Repository inventory
  ● Dependency analysis                     [2 of 4 tasks]
  ● Security and compatibility review       [1 of 3 tasks]
  ✓ Architecture discovery

[Open execution details]
```

When expanded, an agent card can show:

- Agent name and type.
- Assigned task/work package.
- Current status.
- Agent-local todo list from TodoMiddleware.
- Recent safe progress messages.
- Tool calls and their outcomes.
- Generated artifacts.
- Final result/validation.

Use an accordion/collapsible surface. Keep the latest meaningful update visible; keep verbose logs collapsed.

### 4.3 Message presentation rules

- Use a maximum readable text width within the chat pane.
- Use clear headings, lists, code blocks and citations where relevant.
- Preserve Markdown formatting while streaming.
- Show a streaming cursor/indicator only while the message is actually streaming.
- Group consecutive activity updates from the same agent rather than creating one visual card per token/event.
- Provide copy actions for code and answer content.
- Keep timestamps subtle.
- Show agent identity in execution cards, not as a competing avatar on every token.

### 4.4 Long-running operation banner

At the top of the conversation content, use a compact run banner when useful:

- Running: `Reviewing dependencies · 2 of 4 tasks complete`
- Waiting: `Waiting for approval · Security Agent`
- Completed: `Migration assessment ready`
- Failed: `Execution stopped · View failure details`

This should not be another large status area or a duplicate of the migration phase stepper.

---

## 5. Execution model visible in the UI

DICE has multiple levels of work. Keep the hierarchy intact.

```text
Conversation / User turn
└── Supervisor run (root LangGraph thread)
    ├── Supervisor TodoMiddleware plan (global todos)
    ├── task() invocation A
    │   └── Specialist Agent A
    │       ├── Specialist TodoMiddleware plan (local todos)
    │       ├── Tool calls
    │       ├── Optional nested task() / subagents
    │       └── Final structured report
    ├── task() invocation B
    │   └── Specialist Agent B
    │       ├── Specialist TodoMiddleware plan (local todos)
    │       ├── Tool calls
    │       └── Final structured report
    └── Supervisor synthesis and response
```

### 5.1 Do not conflate these concepts

| Concept | Meaning | UI representation |
|---|---|---|
| Supervisor todo | Root agent's planning step | Global plan/queue |
| `task()` call | Supervisor delegates a work package | Specialist agent card / delegation event |
| Specialist todo | Child agent's internal plan | Nested todo list inside specialist card |
| Tool call | A tool used by an agent | Expandable tool activity row |
| Message | User-facing conversational content or safe progress summary | Chat bubble or activity update |
| Artifact | Generated or modified document/file | Right-pane document item/tab |
| Interrupt | Agent execution paused for human input | Approval card and waiting state |
| Checkpoint | Persisted graph state for recovery/resume | Backend persistence concern; not itself a chat message |

### 5.2 Important TodoMiddleware boundary

The native Todo item is intentionally small:

```python
class Todo(TypedDict):
    content: str
    status: Literal["pending", "in_progress", "completed"]
```

`TodoListMiddleware` adds `write_todos`, and the `todos` list is stored in that agent's state. It is a planning/progress facility; it does not itself dispatch a `task()` subagent or guarantee task execution.

Do not add task IDs, dependency arrays, assignees, skill versions or artifact references by changing the native Todo schema. Keep a separate DICE execution-task model and link it to the relevant agent and todo snapshot.

Important current middleware behaviour: `write_todos` replaces the current list, and the middleware rejects multiple `write_todos` calls in the same model turn because parallel writes would create ambiguous precedence. Do not run parallel updates to the same agent's native todo list.

### 5.3 Global and local todo display

- Supervisor global todos appear as the high-level execution plan.
- Specialist todos appear only inside that specialist's expandable card.
- Do not flatten every todo from every agent into one list.
- Use a stable identity for a DICE task. Since native TodoMiddleware items only contain `content` and `status`, DICE can map list items to task IDs using a deterministic reconciliation strategy (for example, agent scope + normalized content + occurrence/version), or have the agent/runtime emit a parallel task manifest with explicit IDs.
- Avoid using array index as an ID when the list can be rewritten/reordered.
- If a todo disappears from a new full-list snapshot, mark the projection as removed/superseded rather than silently keeping a stale item.

---

## 6. LangGraph v3 event-streaming integration

### 6.1 Use typed projections behind a DICE adapter

For new integrations, use LangGraph event streaming (`stream_events` / `astream_events`, `version="v3"`) where supported by the installed package versions. It exposes typed projections rather than requiring the application to decode legacy stream-mode tuples.

For a Deep Agent, current documentation describes projections for messages, tool calls, values and subagents. Each delegated subagent appears through `stream.subagents` as a handle with its name, messages, tool calls and final output. A subagent handle has scoped streaming data; inspect the exact capabilities in the pinned runtime version before relying on optional projections.

**Version warning:** LangGraph v3 event streaming is experimental and may change. Isolate it behind `LangGraphStreamAdapter`; do not let React or business services depend on raw LangGraph event payloads.

### 6.2 Root and subagent projections

Conceptual Python setup for a supervisor:

```python
from deepagents import create_deep_agent
from langchain.agents.middleware import TodoListMiddleware

supervisor = create_deep_agent(
    name="dice-supervisor",
    model=model,
    system_prompt=SUPERVISOR_PROMPT,
    middleware=[TodoListMiddleware()],
    subagents=[
        {
            "name": "migration-specialist",
            "description": "Analyze a migration work package and return evidence.",
            "system_prompt": SPECIALIST_PROMPT,
            "middleware": [TodoListMiddleware()],
        },
        {
            "name": "security-specialist",
            "description": "Review security and compatibility risks.",
            "system_prompt": SECURITY_PROMPT,
            "middleware": [TodoListMiddleware()],
        },
    ],
    checkpointer=checkpointer,
)
```

The exact `create_deep_agent` arguments must match the pinned Deep Agents version and your compiled subagent configuration. This snippet is an architecture example, not a drop-in factory for every release.

### 6.3 Streaming from the FastAPI async service

Prefer the asynchronous event-streaming API for FastAPI. The conceptual shape is:

```python
import asyncio

async def consume_messages(messages, publisher):
    async for message_stream in messages:
        # A message stream can contain text and non-text content blocks.
        # Consume its text projection incrementally.
        async for text_delta in message_stream.text:
            await publisher.publish_message_delta(
                message_id=message_stream.id,
                text=text_delta,
            )

async def consume_subagents(subagents, publisher):
    async for child in subagents:
        child_ref = await publisher.register_subagent(
            name=child.name,
            # Assign a DICE execution ID using the correlated run/task metadata.
        )
        # The adapter should start a dedicated consumer for this child's
        # messages/tool calls as soon as its handle appears.
        asyncio.create_task(consume_child_streams(child, child_ref, publisher))

async def run_supervisor(agent, graph_input, config, publisher):
    # Method availability/signature is version-specific. Pin and test the
    # Deep Agents/LangGraph versions before implementing this adapter.
    async with await agent.astream_events(
        graph_input,
        config=config,
        version="v3",
    ) as run:
        async with asyncio.TaskGroup() as group:
            group.create_task(consume_messages(run.messages, publisher))
            group.create_task(consume_subagents(run.subagents, publisher))
            group.create_task(consume_root_tools(run.tool_calls, publisher))
            group.create_task(consume_root_values(run.values, publisher))

        final_output = await run.output
        if run.interrupted:
            await publisher.publish_interrupts(run.interrupts)
        return final_output
```

This is deliberately adapter pseudocode. Confirm the exact projection names, async context manager signature, message stream shape and tool-call fields against the installed versions. Some versions expose the async entry point as `astream_events`; some usage examples and sync paths show `stream_events`.

### 6.4 Why projections must be consumed concurrently

LangGraph v3 projections are single-consumer drainable streams. Iterating the same projection twice is not supported unless it is explicitly fanned out with the projection's tee facility. The stream is caller-driven: reading the projections drives execution. Use one consumer per projection and run those consumers concurrently (for example, with `asyncio.TaskGroup`).

Do not write:

```python
# Bad pattern: sequentially drain one projection, then another.
async for message in run.messages:
    ...
async for child in run.subagents:
    ...
```

This can delay other projections and may create backpressure. Use independent concurrent consumers, or a documented `interleave` helper where its sync/async behaviour is supported by your version.

### 6.5 Subagent stream handling

When a `task()` call creates a synchronous subagent, Deep Agents can expose a subagent handle through `run.subagents`. Handle properties documented for the Python integration include:

- `name`
- `messages`
- `tool_calls`
- `output`

Consume the root coordinator's messages and each child's streams separately. The subagent's model messages and tool calls are useful for the activity inspector; they should not automatically be appended as primary chat messages.

A normal synchronous subagent handoff returns a final report to its parent. Treat streaming activity and final handoff as distinct concepts:

- Streamed child activity is for live observation.
- The final output/report is the result used by the supervisor.
- The supervisor creates the conversational synthesis for the user.

For async/background subagents, each run has its own thread/run lifecycle and must be correlated to the parent using the DICE parent run/task identifiers. Do not assume its interrupt or resume targets the root supervisor thread.

### 6.6 Capturing TodoMiddleware updates from child agents

Do not assume the root supervisor's `values` projection contains a flattened copy of every child agent's `todos` state.

Recommended strategy:

1. Consume the root's scoped state/values for supervisor todos.
2. Consume each subagent's scoped state/values if the installed subagent handle exposes them in the pinned version.
3. If child todo state is not surfaced reliably by the installed API, add a DICE todo-event hook/custom middleware wrapper around the `write_todos` update and publish the resulting todo snapshot with the child agent identity.
4. Persist each todo snapshot under `(run_id, agent_execution_id, scope)`.
5. Send complete snapshots or versioned updates to React; do not infer child todos from the supervisor's final report.

Use an explicit event payload like:

```json
{
  "event_type": "todo.snapshot",
  "agent_execution_id": "agent-exec-42",
  "agent_name": "migration-specialist",
  "scope": "subagent",
  "todo_revision": 7,
  "todos": [
    {"content": "Inspect build configuration", "status": "completed"},
    {"content": "Check dependency compatibility", "status": "in_progress"}
  ]
}
```

The `todo_revision` is a DICE revision number. Native TodoMiddleware does not provide it; the adapter/event store assigns it.

---

## 7. DICE normalized event contract

### 7.1 Design goals

The frontend should not know whether an event came from LangGraph v3, a custom FastAPI task manager or a future execution engine.

All upstream events should pass through a normalizer and become DICE events with:

- Stable IDs.
- Monotonic ordering.
- Explicit conversation/run/agent/task identity.
- Typed event names and validated payloads.
- A schema version.
- Replay-safe semantics.

### 7.2 Recommended envelope

```typescript
export type DiceEvent = {
  schema_version: 1;
  event_id: string;
  sequence: number;
  occurred_at: string;

  conversation_id: string;
  user_turn_id: string;
  run_id: string;
  parent_run_id?: string;
  thread_id: string;

  agent_execution_id?: string;
  parent_agent_execution_id?: string;
  agent_name?: string;
  agent_role?: "supervisor" | "specialist" | "executor";

  task_id?: string;
  message_id?: string;
  tool_call_id?: string;
  artifact_id?: string;

  type: DiceEventType;
  payload: Record<string, unknown>;
};

export type DiceEventType =
  | "run.started"
  | "run.status"
  | "run.completed"
  | "run.failed"
  | "run.waiting"
  | "run.resumed"
  | "message.started"
  | "message.delta"
  | "message.completed"
  | "agent.started"
  | "agent.progress"
  | "agent.completed"
  | "agent.failed"
  | "todo.snapshot"
  | "tool.started"
  | "tool.input.delta"
  | "tool.completed"
  | "tool.failed"
  | "approval.requested"
  | "approval.decided"
  | "artifact.created"
  | "artifact.updated"
  | "artifact.review_requested"
  | "artifact.approved"
  | "test.started"
  | "test.completed"
  | "test.failed";
```

### 7.3 Correlation keys

Do not use `agent_name` as the unique ID. The same specialist can be invoked multiple times in a run.

Use:

- `conversation_id`: durable user conversation.
- `user_turn_id`: one submitted user turn.
- `run_id`: one supervisor invocation.
- `thread_id`: LangGraph checkpoint thread.
- `agent_execution_id`: one specific child-agent invocation.
- `parent_agent_execution_id`: the delegating agent invocation.
- `task_id`: DICE task/work package identifier.
- `message_id`: one logical message, stable across delta events.
- `tool_call_id`: one tool invocation.
- `artifact_id`: document/file identity; version is a separate field.

Use LangGraph's subagent name metadata and the subagent handle/cause/trigger metadata available in the pinned version to correlate events. Where the framework does not supply a durable DICE task ID, create one in your orchestration layer and preserve the mapping.

### 7.4 Event mapping

| LangGraph/Deep Agents source | DICE normalized event | UI result |
|---|---|---|
| Root model text stream | `message.delta` | Append to supervisor message |
| Root message finished | `message.completed` | Finalize supervisor bubble |
| Subagent handle appears | `agent.started` | Create specialist card |
| Subagent message stream | `agent.progress` or internal activity record | Update agent timeline; not primary chat |
| Subagent final output | `agent.completed` | Show result summary and artifacts |
| Todo state update | `todo.snapshot` | Replace that agent's todo projection |
| Tool call begins | `tool.started` | Add tool activity item |
| Tool call args stream (if exposed) | `tool.input.delta` | Optional input preview |
| Tool result | `tool.completed` | Expandable result/evidence |
| Tool error | `tool.failed` | Failure row with safe details |
| LangGraph interrupt | `approval.requested` | HITL card and waiting state |
| Human response | `approval.decided` | Decision timeline entry |
| Artifact generated | `artifact.created` | Add to document tree/open tab |
| Artifact new version | `artifact.updated` | Refresh selected document version |
| Final graph output | `run.completed` plus `message.completed` | Final supervisor answer |

Not every framework callback maps one-to-one to a user-visible event. Normalize only meaningful lifecycle changes.

---

## 8. FastAPI SSE and event persistence

### 8.1 Recommended flow

```text
LangGraph / Deep Agents v3 streams
            │
            ▼
LangGraphStreamAdapter
            │
            ▼
DICE Event Normalizer
            │
            ├── Validate schema / redact secrets
            ├── Resolve conversation, run, agent and task IDs
            ├── Assign event_id and sequence
            └── Persist event
            │
            ▼
PostgreSQL event store / outbox
            │
            ├── Live publisher → SSE connection
            └── Replay API → reconnecting client
            │
            ▼
React event reducer
```

### 8.2 Persist before publish

Persist an event before publishing it to SSE. For stronger delivery reliability, use a transactional outbox or an equivalent durable publication mechanism:

1. Insert event row and outbox row in the same DB transaction.
2. A publisher reads committed outbox rows and sends them to connected clients.
3. Mark outbox row delivered (or retain a replayable log with delivery cursor).
4. Reconnecting clients replay by sequence/event ID.

Do not claim exactly-once delivery. Design for at-least-once delivery with idempotent consumers.

### 8.3 SSE format

```python
import json

def encode_sse(event: dict) -> str:
    return (
        f"id: {event['sequence']}\n"
        f"event: {event['type']}\n"
        f"data: {json.dumps(event, separators=(',', ':'))}\n\n"
    )
```

Example FastAPI endpoint sketch:

```python
from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

router = APIRouter()

@router.get("/conversations/{conversation_id}/events")
async def stream_conversation_events(
    conversation_id: str,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    async def event_generator():
        # 1. Replay persisted events after last_event_id/sequence.
        # 2. Subscribe to live events without a replay/live gap.
        # 3. Emit heartbeat comments periodically.
        # 4. Stop on disconnect and release subscription resources.
        async for event in event_service.replay_then_subscribe(
            conversation_id=conversation_id,
            after_event_id=last_event_id,
        ):
            yield encode_sse(event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

The pseudocode's `replay_then_subscribe` must avoid the race between replay completion and live subscription. Implement it with a durable high-watermark/sequence and subscription protocol.

### 8.4 Event-store tables

Suggested relational model (adjust to existing migrations/schema):

- `conversations`
- `conversation_turns`
- `execution_runs`
- `agent_executions`
- `execution_tasks`
- `execution_events`
- `execution_approvals`
- `artifacts`
- `artifact_versions`
- `execution_snapshots`
- `event_outbox` (if using transactional outbox)

`execution_events` should include:

```text
id / event_id
conversation_id
run_id
sequence
agent_execution_id (nullable)
task_id (nullable)
event_type
schema_version
payload_json
occurred_at
persisted_at
```

Use a unique constraint for `(run_id, sequence)` or the relevant conversation-level ordering key. Decide whether ordering is per run or per conversation; the frontend should receive an unambiguous cursor. If events from multiple concurrent runs share a conversation, use a conversation-level sequence or a composite cursor.

### 8.5 Snapshot and replay

For long conversations:

1. Build a materialized UI snapshot after a configured event threshold or major lifecycle point.
2. Snapshot contains chat messages, active run state, agents, latest todos, approvals and artifact references.
3. Store `last_sequence` on the snapshot.
4. On page load fetch snapshot, then replay events after `last_sequence`.
5. Subscribe to live events.

Snapshot is a UI projection, not the authoritative LangGraph checkpoint. LangGraph checkpointer state remains the source for resuming graph execution.

---

## 9. React state and event reduction

### 9.1 Separate state domains

Use one event stream, but separate client projections:

```typescript
type DiceWorkspaceState = {
  conversation: ConversationState;
  execution: ExecutionProjection;
  documents: DocumentWorkspaceState;
  connection: StreamConnectionState;
};
```

- `conversation`: user and supervisor messages.
- `execution`: root run, agent executions, task state, tool activity, approvals.
- `documents`: document tabs, tree, selected artifact, versions, edit state.
- `connection`: connecting/live/reconnecting/offline and last sequence.

### 9.2 Reducer example

```typescript
function reduceDiceEvent(
  state: DiceWorkspaceState,
  event: DiceEvent,
): DiceWorkspaceState {
  if (state.connection.seenEventIds.has(event.event_id)) return state;

  switch (event.type) {
    case "message.delta":
      return appendMessageDelta(state, event);

    case "message.completed":
      return finalizeMessage(state, event);

    case "agent.started":
      return upsertAgent(state, event, { status: "running" });

    case "agent.progress":
      return appendAgentActivity(state, event);

    case "agent.completed":
      return upsertAgent(state, event, { status: "completed" });

    case "todo.snapshot":
      return replaceAgentTodos(state, event);

    case "tool.started":
      return upsertToolCall(state, event, { status: "running" });

    case "tool.completed":
      return upsertToolCall(state, event, { status: "completed" });

    case "tool.failed":
      return upsertToolCall(state, event, { status: "failed" });

    case "approval.requested":
      return addApproval(state, event);

    case "approval.decided":
      return updateApproval(state, event);

    case "artifact.created":
    case "artifact.updated":
      return updateArtifactReference(state, event);

    case "run.completed":
    case "run.failed":
    case "run.waiting":
    case "run.resumed":
      return updateRunStatus(state, event);

    default:
      return rememberEventCursor(state, event);
  }
}
```

This is a conceptual reducer. Implement immutable updates and keep the event-specific payload schemas in a validated TypeScript discriminated union or Zod schema.

### 9.3 Critical client correctness rules

- Deduplicate by `event_id`.
- Track sequence and detect gaps.
- Apply `message.delta` to a stable `message_id`, not by appending new bubbles.
- Apply `todo.snapshot` as a replacement for the relevant agent's todo list, not as a new todo row every time.
- Upsert tool calls by `tool_call_id` so start, input, completion and failure update the same UI row.
- Upsert agents by `agent_execution_id`, not by name.
- Apply artifact updates by `artifact_id` and version.
- Ignore duplicate/older snapshots when a newer revision is already applied.
- If a sequence gap is detected, request replay or fetch a fresh materialized snapshot.
- Do not store huge raw tool outputs in the main Zustand store; keep summaries and fetch detailed output on demand.

### 9.4 Scrolling behaviour

- Auto-scroll only when the user is already near the bottom of the conversation.
- If the user scrolls up, show a small “New activity” / “Jump to latest” affordance.
- Do not steal scroll focus because a background agent emitted a todo event.
- Keep document pane scroll independent of chat scroll.

---

## 10. Component architecture

Suggested component hierarchy; adapt to repository conventions rather than creating duplicate layers if equivalents already exist.

```text
src/
  app/
    DICEWorkspace.tsx
  features/
    conversations/
      ConversationPanel.tsx
      ConversationTimeline.tsx
      MessageItem.tsx
      SupervisorMessage.tsx
      UserMessage.tsx
      MessageComposer.tsx
      ApprovalCard.tsx
    execution/
      ExecutionSummary.tsx
      SupervisorPlan.tsx
      AgentExecutionCard.tsx
      AgentTodoList.tsx
      AgentActivityTimeline.tsx
      ToolCallCard.tsx
      AgentResultCard.tsx
      RunStatusBanner.tsx
    documents/
      DocumentWorkspace.tsx
      DocumentExplorer.tsx
      DocumentTabs.tsx
      ArtifactRenderer.tsx
      MarkdownArtifact.tsx
      StructuredDataArtifact.tsx
      CodeArtifact.tsx
      DiagramArtifact.tsx
      DiffArtifact.tsx
      DocumentVersionHistory.tsx
    streaming/
      useDiceEventStream.ts
      diceEventReducer.ts
      streamClient.ts
      schemas.ts
      eventSelectors.ts
    layout/
      AppSidebar.tsx
      WorkspaceHeader.tsx
      MigrationPhaseStepper.tsx
      ResizableWorkspace.tsx
  components/
    ui/                # shadcn/ui components
    ai-elements/       # selected AI Elements copied/adapted into app
```

### 10.1 Layout shell

```tsx
function DICEWorkspace() {
  return (
    <div className="h-dvh overflow-hidden bg-background text-foreground">
      <WorkspaceHeader />
      <div className="flex min-h-0 h-[calc(100dvh-var(--workspace-header-height))]">
        <AppSidebar />
        <ResizablePanelGroup direction="horizontal" className="min-w-0 flex-1">
          <ResizablePanel defaultSize={44} minSize={34}>
            <ConversationPanel />
          </ResizablePanel>
          <ResizableHandle withHandle />
          <ResizablePanel defaultSize={56} minSize={42}>
            <DocumentWorkspace />
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>
    </div>
  );
}
```

Check the exact shadcn `Resizable` API/component naming in the version installed in the repository. Persist panel sizes per user/workspace if users need a remembered layout.

### 10.2 Agent card

```tsx
function AgentExecutionCard({ agent }: { agent: AgentExecution }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card className="overflow-hidden">
      <button
        type="button"
        className="flex w-full items-center gap-3 p-3 text-left"
        aria-expanded={expanded}
        onClick={() => setExpanded(value => !value)}
      >
        <AgentAvatar role={agent.role} />
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium">{agent.displayName}</div>
          <div className="truncate text-sm text-muted-foreground">
            {agent.currentActivity ?? agent.description}
          </div>
        </div>
        <AgentStatusBadge status={agent.status} />
        <ChevronDown className={expanded ? "rotate-180" : ""} />
      </button>

      {expanded && (
        <div className="border-t px-3 pb-3">
          <AgentTodoList todos={agent.todos} />
          <AgentActivityTimeline items={agent.recentActivity} />
          <AgentArtifacts artifacts={agent.artifacts} />
        </div>
      )}
    </Card>
  );
}
```

Do not expose private model reasoning. `recentActivity` should contain user-safe status summaries, tool lifecycle events and explicit progress updates.

### 10.3 Tool call component

Display:

- Tool name and icon.
- Running/completed/failed state.
- Short description of what the tool is doing.
- Duration, where known.
- Collapsed input preview and safe output summary.
- “View details” for raw structured payloads (redacted and permission checked).

Never render untrusted tool output as raw HTML. Escape content and sanitize Markdown.

### 10.4 Todo list component

Display a clear status icon and short todo text. The native TodoMiddleware has three statuses: pending, in progress, completed. Map those to visual states; do not invent blocked/failed native statuses. DICE can show blocked/failed at the execution-task layer if it has reliable evidence for those states.

Example:

```tsx
function AgentTodoList({ todos }: { todos: Todo[] }) {
  return (
    <div className="space-y-2">
      {todos.map(todo => (
        <div key={todo.diceTaskId} className="flex items-start gap-2 text-sm">
          <TodoStatusIcon status={todo.status} />
          <span className={todo.status === "completed" ? "text-muted-foreground" : ""}>
            {todo.content}
          </span>
        </div>
      ))}
    </div>
  );
}
```

`diceTaskId` is provided by DICE reconciliation/enrichment, not the native `Todo` schema.

---

## 11. Documents and artifacts: backend contract

### 11.1 Documents are not chat messages

Do not stream an entire long migration document as a string inside the chat transcript. Send artifact lifecycle events and let the right pane load the artifact through a document API.

Example event:

```json
{
  "type": "artifact.created",
  "artifact_id": "artifact-123",
  "payload": {
    "title": "Java 8 to Java 17 Migration Strategy",
    "artifact_type": "markdown",
    "category": "planning",
    "version": 1,
    "status": "draft",
    "uri": "/api/artifacts/artifact-123/versions/1"
  }
}
```

Example document object:

```typescript
type Artifact = {
  id: string;
  workspaceId: string;
  title: string;
  type: "markdown" | "yaml" | "json" | "code" | "diagram" | "diff" | "pdf";
  category: string;
  status: "draft" | "in_review" | "approved" | "superseded";
  currentVersion: number;
  updatedAt: string;
  createdByAgentExecutionId?: string;
  sourceTaskIds: string[];
};
```

### 11.2 Artifact lifecycle

Recommended events:

- `artifact.created`
- `artifact.updated`
- `artifact.review_requested`
- `artifact.approved`
- `artifact.rejected`
- `artifact.superseded`

Every update should reference an artifact ID and version. Keep document content/versioning in the artifact service; keep the event stream as a lifecycle/change notification.

### 11.3 Renderer registry

```tsx
const artifactRenderers = {
  markdown: MarkdownArtifact,
  yaml: StructuredDataArtifact,
  json: StructuredDataArtifact,
  code: CodeArtifact,
  diagram: DiagramArtifact,
  diff: DiffArtifact,
  pdf: PdfArtifact,
} as const;

function ArtifactRenderer({ artifact }: { artifact: ArtifactWithContent }) {
  const Renderer = artifactRenderers[artifact.type] ?? UnsupportedArtifact;
  return <Renderer artifact={artifact} />;
}
```

Use an explicit allowlist. Validate/sanitize Markdown, HTML previews, Mermaid and code output.

### 11.4 Artifact interactions from chat

A supervisor message can reference an artifact:

```json
{
  "artifact_id": "artifact-123",
  "version": 2,
  "title": "Migration Strategy"
}
```

Render an inline artifact link/card. Clicking it should open the exact version in the right pane and preserve the current chat scroll position.

---

## 12. HITL approval and resume

### 12.1 UI flow

1. An agent reaches an action that requires approval.
2. LangGraph raises an interrupt.
3. The backend normalizes it into `approval.requested` and persists the approval record.
4. The run enters `waiting` state.
5. React renders an approval card in the conversation pane and a waiting indicator on the run/agent card.
6. The user approves, rejects or edits the requested input, depending on allowed decisions.
7. The backend validates authorization and the decision, then resumes the correct graph/thread.
8. The new streaming execution emits `run.resumed` and subsequent events.

Example approval payload:

```json
{
  "approval_id": "approval-123",
  "target_thread_id": "langgraph-thread-or-child-thread",
  "target_run_id": "run-456",
  "agent_execution_id": "agent-exec-42",
  "action": "Apply source transformation",
  "description": "Apply the generated Java migration patch to the working branch.",
  "allowed_decisions": ["approve", "reject", "edit"],
  "status": "pending"
}
```

### 12.2 Resume API

```python
from langgraph.types import Command

async def resume_graph(graph, thread_id: str, decision: dict):
    config = {"configurable": {"thread_id": thread_id}}

    async with await graph.astream_events(
        Command(resume=decision),
        config=config,
        version="v3",
    ) as run:
        # Attach the same event consumers used for a normal run.
        await consume_and_publish(run)
        return await run.output
```

The same `thread_id`/checkpoint is required. Use a durable checkpointer in production. The node containing `interrupt()` restarts from the beginning when resumed; make side effects before the interrupt idempotent or move them after the approval point.

### 12.3 Synchronous child vs async child approval

- If the interrupt occurs in a synchronous nested child graph, verify how the installed Deep Agents/LangGraph version surfaces the child interrupt through the parent stream before assuming the root thread can be resumed.
- If the child is a separately running async subagent, store its own thread/run ID and resume that child execution, not the supervisor thread by default.
- The approval record must identify the exact target execution/checkpoint.
- Do not let React choose thread IDs. The backend resolves the approval record to the correct checkpoint.

### 12.4 Security

- Check user authorization for the conversation, workspace, artifact and approval.
- Treat approval IDs as opaque identifiers, not authorization tokens.
- Persist who approved/rejected, when, decision and any edited input.
- Make decision submission idempotent.
- Never replay a decision against a completed or superseded interrupt.

---

## 13. Motion and interaction design

Use Motion for React for selective transitions. Keep the app responsive and avoid animating large layout surfaces continuously.

Recommended animations:

| Interaction | Animation |
|---|---|
| Agent card opens/closes | Height/opacity with layout transition |
| New agent appears | Short fade + slight vertical movement |
| Todo status changes | Icon crossfade / subtle colour transition |
| Document tab changes | Short fade or shared-layout underline |
| Approval card arrives | Subtle slide/fade and focus announcement |
| Artifact created | Brief highlight/pulse on document tab or tree item |
| Streaming message | Text appears naturally; small cursor only |
| Sidebar/resizable panel changes | Use panel library behaviour; do not animate width manually unless necessary |

Example:

```tsx
import { AnimatePresence, motion, useReducedMotion } from "motion/react";

function AgentDetails({ open, children }: Props) {
  const reduceMotion = useReducedMotion();

  return (
    <AnimatePresence initial={false}>
      {open && (
        <motion.div
          key="agent-details"
          initial={reduceMotion ? false : { opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduceMotion ? undefined : { opacity: 0, y: -4 }}
          transition={{ duration: 0.16, ease: "easeOut" }}
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
```

Respect `prefers-reduced-motion`. Use stable React keys. Do not animate every event or token. For frequent updates, prefer CSS transitions and update only the smallest changed component.

---

## 14. shadcn/ui and AI Elements integration

### 14.1 Recommended shadcn components

| Component | DICE usage |
|---|---|
| `Resizable` | Chat/document split |
| `Sidebar` | Existing left navigation |
| `Tabs` | Open migration documents |
| `Collapsible` / `Accordion` | Specialist details and document folders |
| `ScrollArea` | Chat/document explorer scrolling |
| `Card` | Agent, artifact and approval surfaces |
| `Badge` | Status labels |
| `Progress` | Coarse execution/task progress |
| `Breadcrumb` | Artifact location |
| `Sheet` / `Drawer` | Responsive document tree / mobile navigation |
| `Command` | Search and switch documents |
| `Dialog` / `AlertDialog` | Confirm destructive or approval actions |
| `DropdownMenu` | Document actions and version menu |
| `Tooltip` | Compact toolbar actions |
| `Separator` | Structural separation; use sparingly |

### 14.2 AI Elements to inspect/adapt

The official AI Elements collection provides patterns for agentic UI composed from shadcn components. It is copied into the application; there is no separate AI Elements runtime package to install.

Useful patterns for DICE:

- Message / Chat / Message Scroller.
- Plan and Queue.
- Task.
- Subagent.
- Tool.
- Trace.
- Confirmation.
- File Tree.
- Terminal.
- Test Results.
- Stack Trace.

Use these as visual/interaction starting points. Adapt them to DICE's event contract and store. **Do not adopt the Vercel AI SDK solely to use AI Elements.** The UI components can be adapted to FastAPI SSE and the DICE normalized events.

### 14.3 Bootstrap guidance

Bootstrap is not recommended as the primary UI framework for this redesign. Mixing Bootstrap CSS, Bootstrap resets and Tailwind utilities can create conflicting typography, form controls, sizing and spacing.

If a legacy Bootstrap widget must remain:

- Isolate it in a wrapper/component boundary.
- Avoid importing its global Reboot styles if possible.
- Namespace/customize its CSS.
- Do not use Bootstrap grid and Tailwind grid for the same layout.
- Prefer shadcn components for all new DICE components.

---

## 15. Accessibility and enterprise UX

- All expandable cards must support keyboard interaction and expose `aria-expanded`.
- Use visible focus rings.
- Do not rely on colour alone for status; use icon + label.
- Announce important events (approval required, run failed, completed) using an appropriate live region. Do not announce every token or tool log.
- Preserve focus after opening a document or approval dialog.
- Ensure code blocks, document tree and tabs are keyboard navigable.
- Respect reduced-motion settings.
- Provide clear loading, empty, error and disconnected states.
- Avoid showing sensitive source/tool payloads without authorization and redaction.
- Support copy, download and accessible names on icon-only controls.

---

## 16. Performance and reliability

### React

- Keep the SSE connection in a service/hook layer, not inside every component.
- Batch high-frequency message deltas (e.g. animation frame or short micro-batch) before state updates.
- Do not re-render the entire workspace for every token.
- Select only relevant slices from Zustand or use memoized selectors.
- Virtualize very long conversation timelines and execution logs if needed.
- Lazy-load heavyweight artifact renderers such as PDF, Mermaid or code editor.
- Keep large tool outputs outside the global UI store; fetch when expanded.

### Backend

- Persist before publish.
- Use bounded queues and disconnect slow consumers safely.
- Provide heartbeat events/comments.
- Resume via event replay, not by restarting an already-running execution.
- Make event writes and artifact updates idempotent.
- Limit concurrency at the execution manager, not just in the UI.
- Record run failure, cancellation, interrupt and resume lifecycle explicitly.

### State correctness

The LangGraph checkpointer stores graph execution state. The DICE event store stores the user-visible event history and UI projection. These are related but not interchangeable.

- A checkpoint is not a chat transcript.
- An event log is not the authoritative graph checkpoint.
- A UI snapshot is not the authoritative artifact version.
- Artifact storage is not a todo ledger.

---

## 17. API contract proposal

Use existing project endpoint conventions if present. Suggested API surface:

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/conversations/{id}/messages` | Submit a user message/start a turn |
| `GET` | `/conversations/{id}/events` | Replay and stream conversation/run events via SSE |
| `GET` | `/conversations/{id}/snapshot` | Fetch conversation and execution UI projection |
| `GET` | `/executions/{run_id}` | Fetch run details/status |
| `GET` | `/executions/{run_id}/agents` | Fetch agent hierarchy |
| `GET` | `/executions/{run_id}/tasks` | Fetch DICE execution tasks/todo projections |
| `POST` | `/approvals/{approval_id}/decision` | Submit approve/reject/edit decision |
| `GET` | `/artifacts/{artifact_id}` | Fetch artifact metadata/current version |
| `GET` | `/artifacts/{artifact_id}/versions/{version}` | Fetch exact artifact version/content |
| `POST` | `/artifacts/{artifact_id}/comments` | Add document review comment (if supported) |

The frontend should not call LangGraph directly. FastAPI owns auth, execution, event normalization, resume targeting and document authorization.

---

## 18. Implementation phases for the coding agent

The coding agent should inspect the existing repository first and create a codebase-specific implementation map. Do not perform a large visual rewrite before understanding current routes, stores, styles, SSE hooks and artifact APIs.

### Phase 0 — Repository discovery

- Identify current React/Vite entry point, route structure and design tokens.
- Identify whether Tailwind and shadcn are already installed/configured.
- Identify the current chat component, document explorer and artifact preview.
- Identify existing SSE client, event schema, event store and snapshot/replay endpoints.
- Identify state management (Zustand/Redux/context) and current message/document models.
- Identify available LangGraph and Deep Agents versions in lock files and Python dependency manifests.
- Document gaps; do not duplicate existing abstractions.

**Deliverable:** `docs/frontend/current-architecture.md` with component map, existing data flow and migration recommendations.

### Phase 1 — Visual workspace shell

- Refactor only the layout shell into sidebar, conversation pane and document workspace.
- Add resizable conversation/document panel.
- Move document tree inside the right workspace and make it collapsible.
- Compact the migration phase stepper.
- Establish spacing, typography, borders, colours and responsive breakpoints.
- Preserve existing functionality and branding.

**Acceptance:** Existing conversations and documents still load; panel resizing and responsive modes work.

### Phase 2 — Document workspace

- Add document tabs and stable artifact selection.
- Implement renderer registry for Markdown, YAML/JSON, code, diagram and diff.
- Add preview/edit switch where editing is supported.
- Add artifact version and status display.
- Add chat-to-artifact deep links.

**Acceptance:** User can switch between multiple artifacts without losing chat scroll or run state.

### Phase 3 — Conversation and execution activity

- Separate supervisor messages from execution events.
- Add global supervisor plan.
- Add specialist agent cards.
- Add agent-local todo snapshots.
- Add tool call cards and recent activity summaries.
- Keep verbose details collapsed by default.

**Acceptance:** A root run with at least two specialist subagents renders the correct hierarchy without mixing their todos/messages.

### Phase 4 — LangGraph v3 adapter and DICE event contract

- Pin and verify versions of LangGraph, Deep Agents and LangChain.
- Implement typed projection consumers in the backend adapter.
- Consume coordinator messages, tool calls, values and subagent handles concurrently.
- Capture root and child todo snapshots from the correct scope.
- Normalize events to the DICE schema.
- Persist events and publish SSE.
- Add replay and gap recovery.

**Acceptance:** A test run can stream supervisor text, a `task()` subagent, tool activity, child todos and final handoff; reload/reconnect restores the same UI projection.

### Phase 5 — HITL and resume

- Add approval persistence and approval card.
- Map interrupt payload to DICE approval schema.
- Resume the correct thread/checkpoint.
- Handle synchronous child interrupts and async child threads explicitly.
- Add audit history and idempotent decisions.

**Acceptance:** Approve, reject and edit decisions work; refresh while waiting does not lose the approval; the correct run resumes exactly once.

### Phase 6 — Polish, accessibility and performance

- Add Motion transitions and reduced-motion mode.
- Add keyboard and screen-reader behaviour.
- Add virtualized activity/message rendering if required.
- Add error/reconnect states and telemetry.
- Run responsive and browser tests.

**Acceptance:** No major layout shifts during streaming; chat and document scrolling remain independent; performance is stable under long runs.

---

## 19. Test scenarios

The implementation is not complete until these scenarios are tested:

1. **Simple supervisor response:** no todos, no subagents, ordinary assistant response.
2. **Supervisor todos only:** root todo snapshots update in place.
3. **One synchronous `task()` call:** child card appears, child messages/tools stream, final report is shown.
4. **Two parallel synchronous tasks:** each child has a separate agent execution ID and todo scope.
5. **Nested specialist delegation:** child agent can have its own child activity where configured; UI preserves parent-child hierarchy.
6. **Todo rewrite:** new full-list snapshot reorders/removes/revises items without duplicates or stale rows.
7. **Tool failure:** tool card shows failed state; supervisor can recover; run is not falsely marked complete.
8. **Long message streaming:** deltas append to the same message ID; no duplicate bubbles.
9. **Approval wait:** interrupt becomes durable approval; run shows waiting state.
10. **Approval resume:** same checkpoint thread resumes; events continue in order.
11. **Async child approval:** approval is routed to the child execution's thread/checkpoint.
12. **Artifact generated during execution:** document appears in tree and can be opened in right pane.
13. **Artifact version update:** selected doc refreshes to a new version without losing tab context.
14. **SSE disconnect/reconnect:** Last-Event-ID replay fills the gap with no duplicate visible activity.
15. **Browser refresh during run:** snapshot + event replay reconstructs chat, agents, todos, approvals and documents.
16. **Reduced motion:** animations are suppressed or minimized.
17. **Mobile/tablet:** chat and documents switch modes cleanly; no unusable narrow columns.

---

## 20. Coding-agent instructions / non-goals

### Required approach

1. Inspect the repository and summarize the current implementation before editing.
2. Reuse existing stores, hooks, endpoints, components and design tokens where practical.
3. Create a small implementation plan with files to change.
4. Implement in phases; keep each phase buildable.
5. Do not invent backend events. If an event is not available, report the missing source and propose the smallest backend addition.
6. Pin and verify the LangGraph/Deep Agents API against the installed version. Treat v3 event-streaming as experimental and isolate it.
7. Add tests for event ordering, deduplication, todo replacement, subagent identity, approval resume and document state.
8. Run lint, typecheck, unit tests and production build.
9. Provide screenshots or a short visual changelog showing before/after.

### Non-goals

- Do not replace the whole frontend framework.
- Do not add Bootstrap as a second global design system.
- Do not stream every child-agent thought/message into the primary conversation.
- Do not flatten supervisor and child todos into one unscoped list.
- Do not treat TodoMiddleware as a task dispatcher.
- Do not use the React client to resume LangGraph directly.
- Do not stream full artifact contents through chat events when an artifact reference will do.
- Do not make animations more important than clarity or accessibility.

---

## 21. Definition of done

DICE is ready when a user can:

- Start a migration conversation with the Supervisor.
- See the Supervisor's response stream naturally.
- Understand what work is being delegated and to which agents.
- Expand any specialist and inspect its own todos and safe tool activity.
- Distinguish a plan from actual execution.
- Respond to an approval request and watch the correct execution resume.
- Open generated migration documents in the right pane while the chat stays in place.
- Switch between Markdown, YAML/JSON, code, diagram and diff artifacts.
- Reconnect or refresh without losing the event timeline or document selection.
- Understand final results, outstanding risks and next steps without reading raw logs.

**The resulting product should feel like a polished engineering workspace: conversation on the left, migration deliverables on the right, and transparent agent execution woven into the conversation without overwhelming it.**

---

## 22. Official references

Use these sources when implementing version-specific APIs. Re-check them against the packages pinned in the repository.

### LangGraph and Deep Agents

- [LangGraph streaming concepts](https://docs.langchain.com/oss/python/langgraph/streaming)
- [LangGraph event streaming](https://docs.langchain.com/oss/python/langgraph/event-streaming)
- [LangGraph Python `stream_events` reference](https://reference.langchain.com/python/langgraph/pregel/main/Pregel/stream_events)
- [LangGraph interrupt and resume](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [Deep Agents overview](https://docs.langchain.com/oss/python/deepagents/overview)
- [Deep Agents subagents and streaming](https://docs.langchain.com/oss/python/deepagents/subagents)
- [TodoListMiddleware reference](https://reference.langchain.com/python/langchain/agents/middleware/todo)
- [Todo state source](https://github.com/langchain-ai/langchain/blob/master/libs/langchain_v1/langchain/agents/middleware/todo.py)

### Frontend

- [shadcn/ui documentation](https://ui.shadcn.com/docs)
- [shadcn AI Elements](https://ui.shadcn.com/docs/ai-elements)
- [shadcn Resizable](https://ui.shadcn.com/docs/components/resizable)
- [Motion for React](https://motion.dev/docs/react)
- [Motion AnimatePresence](https://motion.dev/docs/react-animate-presence)

---

**End of design brief.**
