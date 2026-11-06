Yes. And this is an important part of making DICE feel like an actual agentic engineering platform rather than a chatbot with a spinner.

LangGraph provides execution state, checkpoints and streaming events. Deep Agents provides task planning and subagent delegation. You need to connect these to a persistent execution ledger to give React a complete, live execution tree.

There are three different things to understand.

## 1. Where are tasks stored?

| Mechanism                        | What it stores                                        | Purpose                    |
| -------------------------------- | ----------------------------------------------------- | -------------------------- |
| LangGraph Checkpointer           | Graph state snapshots at each super-step              | Persistence and recovery   |
| Deep Agents `TodoListMiddleware` | Agent todo items and their status                     | Agent-level task tracking  |
| LangGraph streaming              | Task starts, finishes, node updates and custom events | Live UI updates            |
| Your PostgreSQL task ledger      | Explicit parent-child tasks and event history         | Complete execution-tree UI |

### A. LangGraph Checkpointer

When you compile a graph with a checkpointer, LangGraph saves state at each super-step.

For PostgreSQL:

```
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaverasync with AsyncPostgresSaver.from_conn_string(    DATABASE_URL) as checkpointer:    await checkpointer.setup()    graph = builder.compile(        checkpointer=checkpointer    )
```

Every execution uses a thread ID:

```
config = {    "configurable": {        "thread_id": "conversation-123"    }}
```

You can inspect the current state:

```
snapshot = await graph.aget_state(config)
```

Or retrieve the checkpoint history:

```
async for snapshot in graph.aget_state_history(config):    print(snapshot.values)
```

This is useful for debugging and recovery, but it isn't a purpose-built hierarchical task database.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub+1



### B. Deep Agents TodoListMiddleware

Deep Agents has a `TodoListMiddleware` that provides a `write_todos` tool.

Todo statuses include:

- `pending`
- `in_progress`
- `completed`

These tasks live in the agent's state and are persisted through the graph's checkpointing mechanism when configured.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub



But remember:

Agent todos are not the same as execution-tree nodes.

For example, Discovery might have an internal todo list, while your parent supervisor has assigned Discovery a task of its own.

You need to represent both levels in your UI.

## 2. LangGraph can stream task execution events

This is probably the most interesting part.

LangGraph supports several streaming modes:

| Stream mode   | What your UI gets                           |
| ------------- | ------------------------------------------- |
| `tasks`       | Task start, finish, result and error events |
| `updates`     | Node and task state changes                 |
| `custom`      | Custom progress events emitted by your code |
| `messages`    | LLM output tokens                           |
| `checkpoints` | Graph state checkpoint events               |
| `debug`       | Detailed execution diagnostics              |

The `tasks` stream requires a checkpointer. You can also enable `subgraphs=True` to receive events from nested graphs, including their namespace paths.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub+1



Example:

```
async for part in graph.astream(    input_state,    config=config,    stream_mode=[        "tasks",        "updates",        "custom",    ],    subgraphs=True,    version="v2",):    event_type = part["type"]    namespace = part["ns"]    payload = part["data"]    print(event_type, namespace, payload)
```

What happens?

Imagine your Discovery Deep Agent creates three parallel workers.

You will receive events representing:

```
Discovery Started

Worker 1 Started
Worker 2 Started
Worker 3 Started

Worker 2 Completed
Worker 1 Completed
Worker 3 Completed

Discovery Completed
```

The namespace helps identify which nested graph emitted an event. But don't rely on it as your business task ID or parent-child database relationship. Maintain those explicitly.

### Custom progress events

You can also emit meaningful progress from inside your own nodes and tools.

```
from langgraph.config import get_stream_writerdef discovery_worker(state):    writer = get_stream_writer()    writer({        "event": "task.progress",        "task_id": state["task_id"],        "message": "Scanning repository dependencies"    })    # Perform discovery...    writer({        "event": "task.progress",        "task_id": state["task_id"],        "message": "Dependency analysis completed"    })    return {"status": "completed"}
```

These events appear through `stream_mode="custom"`. The documented Python `get_stream_writer()` approach works with Python 3.11 and later in async applications.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub



This is what I'd use to communicate meaningful agent activity to your frontend.

## 3. My recommended PostgreSQL architecture

Since you already have PostgreSQL-based event delivery and FastAPI SSE, I'd extend your existing infrastructure rather than introduce another message broker just for UI progress.

I would maintain three logical tables.

1\. `agent_runs`

One per execution

```
run_id
thread_id
status
current_phase
started_at
completed_at
```

2\. `task_nodes`

Hierarchical execution tree

```
task_id
run_id
parent_task_id
agent_type
title
description
status
depth
started_at
completed_at
result_artifact_id
```

3\. `task_events`

Append-only event history

```
event_id
sequence_id
run_id
task_id
event_type
payload JSONB
created_at
```

The key is that `task_nodes` represents the current state of the tree, while `task_events` represents everything that happened.

### Example event types

```
[
  {
    "type": "task.created",
    "task_id": "discovery-001",
    "parent_task_id": "root"
  },
  {
    "type": "task.started",
    "task_id": "discovery-001"
  },
  {
    "type": "task.created",
    "task_id": "discovery-002",
    "parent_task_id": "discovery-001"
  },
  {
    "type": "task.waiting_children",
    "task_id": "discovery-001"
  },
  {
    "type": "task.completed",
    "task_id": "discovery-001"
  }
]
```

Important: When the planner creates child tasks, persist them immediately. Don't wait for LangGraph to finish the entire phase before creating the tree in PostgreSQL.

For every dynamically dispatched worker, pass your own `task_id` and `parent_task_id` in its input state. This gives you stable correlation across retries, pods and nested agents.

## 4. How the execution events reach your React UI

This is where I'd connect LangGraph to your existing FastAPI event architecture.

LangGraph Runtime

Tasks · Updates · Custom events · Subgraphs

Event Normalizer

Translate framework events into DICE event schema

FastAPI Event Consumer

PostgreSQL

Persist task state and events

Async Queue

Live notification

FastAPI SSE Endpoint

Replay + real-time events

React UI

Execution tree + activity timeline + artifacts

Your streaming consumer could look something like this:

```
async def execute_and_stream(    graph,    run_id,    thread_id,    initial_state):    config = {        "configurable": {            "thread_id": thread_id        }    }    async for part in graph.astream(        initial_state,        config=config,        stream_mode=[            "tasks",            "updates",            "custom"        ],        subgraphs=True,        version="v2",    ):        event = normalize_event(            run_id=run_id,            event_type=part["type"],            namespace=part["ns"],            payload=part["data"],        )        if event is None:            continue        # Persist first        saved_event = await event_repository.append(event)
```

`normalize_event()` is your application-specific adapter. It should map LangGraph runtime identifiers to your own task IDs and sanitize results before storing or publishing them.

I'd also avoid forwarding raw LLM messages, hidden reasoning or unredacted tool arguments to your UI.

## 5. How should the UI actually look?

I'd build an execution workspace with three areas.

Application Modernization

Running

Discovery phase

3 / 5 tasks completed

Execution tree

Supervisor

Completed planning

Discovery Agent

Running

Repository analysis

Done

Dependency discovery

Running

Infrastructure analysis

Pending

Design Agent

Waiting

Activity

- 14:02:12

  Repository analysis completed.
- 14:02:18

  Dependency discovery started.
- 14:02:20

  Discovery Agent spawned 3 workers.

Active workers: 1 · Pending: 1

Live execution

Illustrative UI mockup, showing the kind of view I'd build.

I'd divide the actual React application into:

| UI component     | Responsibility                        |
| ---------------- | ------------------------------------- |
| ExecutionTree    | Expandable parent-child hierarchy     |
| TaskNode         | Agent type, status, timing            |
| ActivityTimeline | Chronological execution events        |
| TaskInspector    | Selected task's details and result    |
| ArtifactPanel    | Generated reports, code and documents |
| RunHeader        | Overall execution and phase status    |

### Don't show fake progress percentages

Agent execution is unpredictable. Instead, show:

- 4 of 7 tasks completed.
- 2 workers running.
- 1 task waiting for approval.
- Discovery phase completed.
- Design phase starting.

The denominator can change as the agent discovers more work. A 60% bar that suddenly falls to 35% isn't exactly confidence-inspiring.

## 6. Handling reconnects and page refreshes

This is particularly important for your existing SSE implementation.

I would expose three API endpoints:

| Endpoint                                       | Purpose                      |
| ---------------------------------------------- | ---------------------------- |
| `GET /runs/{run_id}/tree`                      | Fetch current task hierarchy |
| `GET /runs/{run_id}/events?after={seq}`        | Replay historical events     |
| `GET /runs/{run_id}/events/stream?after={seq}` | Receive new SSE events       |

Every event should have a monotonically increasing database sequence number.

When React reconnects:

1. Fetch the latest task tree.
2. Get its last event sequence.
3. Replay events after that sequence.
4. Continue consuming live SSE events.

This means the UI can recover even if the browser closes, the SSE connection drops, or the user returns after an hour.

## 7. My final recommendation for DICE

Use each component for a clearly defined responsibility:

| Component                  | Responsibility                         |
| -------------------------- | -------------------------------------- |
| LangGraph Checkpointer     | Execution persistence and recovery     |
| Deep Agents TodoMiddleware | Agent-level todo lists                 |
| LangGraph streaming        | Runtime lifecycle events               |
| PostgreSQL `task_nodes`    | Hierarchical execution state           |
| PostgreSQL `task_events`   | Durable event history                  |
| FastAPI SSE                | Live UI delivery                       |
| React                      | Tree visualization and task inspection |

One important operational detail: treat the database as the authoritative source for the UI. The in-memory asyncio queue should only accelerate delivery; it should never be the only place an event exists.

I would also introduce a distinction between `task.status` and `task.activity`. Status changes are durable state transitions; activity messages are informational updates. That prevents every little progress message from becoming a database status transition.

Given your existing FastAPI + PostgreSQL + SSE implementation, this is an extension of what you've already built, not a completely new architecture.&#x20;

My next implementation priority would be the `task_nodes` and `task_events` schema, the LangGraph event normalizer, and a React execution-tree component. That's the core of the DICE execution experience.