"use strict";

const PHASES = [
  { id: "collection", label: "Intake" },
  { id: "discovery", label: "Discovery" },
  { id: "review", label: "Review" },
  { id: "design", label: "Design" },
  { id: "review_design", label: "Design review" },
  { id: "complete", label: "Complete" },
];

const SUGGESTIONS = [
  "Start intake for payments-api, AA number AA-1042.",
  "What do you need from me before discovery can start?",
];

const state = {
  userId: "local",
  threads: [],
  activeId: null,
  view: null,
  files: [],
  openFile: null,
  health: null,
  running: false,
  loading: false,
  error: "",
  liveText: "",
  pendingUserText: "",
  activity: "",
  startedAt: 0,
  editing: null,
  pendingAnswers: {},
  answerKey: "",
};

let stickToBottom = true;
let paintQueued = false;

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatText(value) {
  const source = String(value || "");
  const parts = source.split(/```([\s\S]*?)```/g);
  return parts
    .map((part, index) => {
      if (index % 2 === 1) {
        return `<pre><code>${escapeHtml(part.trim())}</code></pre>`;
      }
      return escapeHtml(part)
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
        .replace(/\n/g, "<br>");
    })
    .join("");
}

function detailMessage(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (item && (item.msg || item.message)) || "")
      .filter(Boolean)
      .join(" ");
  }
  return "";
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      Accept: "application/json",
      "X-Dice-User": state.userId,
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });
  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch (_error) {
      data = null;
    }
  }
  if (!response.ok) {
    throw new Error(detailMessage(data && data.detail) || response.statusText || "Request failed");
  }
  return data;
}

function canonicalPhase(phase) {
  const raw = String(phase || "").toLowerCase();
  if (raw === "completed") return "complete";
  if (!raw || raw === "intake") return "collection";
  if (raw.startsWith("rework_")) return raw.slice("rework_".length);
  return raw;
}

function phaseLabel(phase) {
  const canonical = canonicalPhase(phase);
  const match = PHASES.find((item) => item.id === canonical);
  const raw = String(phase || "");
  if (raw.toLowerCase().startsWith("rework_") && match) return `Rework · ${match.label}`;
  return match ? match.label : raw || "Intake";
}

function elapsed() {
  if (!state.startedAt) return "";
  const seconds = Math.floor((Date.now() - state.startedAt) / 1000);
  return seconds >= 1 ? `${seconds}s` : "";
}

function activityText(node) {
  const name = String(node || "").toLowerCase();
  if (!name) return "";
  if (name.includes("discovery")) return "Discovery";
  if (name.includes("design")) return "Design";
  if (name.includes("supervisor")) return "Supervisor";
  if (name === "tools" || name.includes("tool")) return "Running a tool";
  if (name === "model" || name === "agent") return "Writing";
  return "";
}

function statusText() {
  if (state.loading) return ["Opening", elapsed()].filter(Boolean).join(" · ");
  if (state.running) {
    return ["Working", activityText(state.activity), elapsed()].filter(Boolean).join(" · ");
  }
  const view = state.view;
  if (!view) return "Ready";
  if (view.status === "awaiting_input") return "Waiting for you";
  if (view.status === "complete" || canonicalPhase(view.phase) === "complete") return "Complete";
  if ((view.messages || []).some((message) => message.role === "human" || message.role === "ai")) {
    return "In progress";
  }
  return "Ready";
}

function statusState() {
  if (state.loading) return "loading";
  if (state.running) return "running";
  if (!state.view) return "idle";
  if (state.view.status === "complete" || canonicalPhase(state.view.phase) === "complete") return "complete";
  return state.view.status || "idle";
}

async function refreshThreads() {
  const data = await api("/api/threads");
  state.threads = (data && data.threads) || [];
}

async function refreshFiles() {
  if (!state.activeId) {
    state.files = [];
    state.openFile = null;
    return;
  }
  const data = await api(`/api/threads/${state.activeId}/files`);
  state.files = (data && data.files) || [];
  if (state.openFile && !state.files.includes(state.openFile.path)) state.openFile = null;
}

async function openThread(id) {
  if (!id || state.running) return;
  state.activeId = id;
  state.loading = true;
  state.startedAt = Date.now();
  state.error = "";
  state.openFile = null;
  state.liveText = "";
  state.pendingUserText = "";
  stickToBottom = true;
  if (location.hash !== `#${id}`) history.replaceState(null, "", `#${id}`);
  renderAll();
  try {
    state.view = await api(`/api/threads/${id}`);
    await refreshFiles();
    await refreshThreads();
  } catch (error) {
    state.error = error.message;
    if (!state.view) {
      const thread = state.threads.find((item) => item.thread_id === id);
      state.view = {
        title: (thread && thread.title) || "New migration",
        phase: (thread && thread.phase) || "collection",
        status: "idle",
        messages: [],
        interrupts: [],
        todos: [],
        errors: [],
      };
    }
  } finally {
    state.loading = false;
    renderAll();
    const draft = document.getElementById("draft");
    if (draft && !draft.disabled) draft.focus();
  }
}

async function createThread() {
  if (state.running || state.loading) return;
  const thread = await api("/api/threads", { method: "POST", body: "{}" });
  await refreshThreads();
  await openThread(thread.thread_id);
}

async function removeThread() {
  if (!state.activeId || state.running || state.loading) return;
  const title = (state.view && state.view.title) || "this migration";
  if (!window.confirm(`Remove “${title}” from the sidebar?`)) return;
  const id = state.activeId;
  await api(`/api/threads/${id}`, { method: "DELETE" });
  if (location.hash === `#${id}`) history.replaceState(null, "", location.pathname);
  await refreshThreads();
  state.activeId = null;
  state.view = null;
  state.files = [];
  state.openFile = null;
  if (state.threads.length) await openThread(state.threads[0].thread_id);
  else renderAll();
}

async function openFile(path) {
  try {
    state.openFile = await api(
      `/api/threads/${state.activeId}/files/content?path=${encodeURIComponent(path)}`,
    );
    state.error = "";
  } catch (error) {
    state.error = error.message;
  }
  renderRail();
  renderProblems();
}

async function readSse(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";
    for (const chunk of chunks) {
      if (!chunk.trim()) continue;
      let event = "message";
      const dataLines = [];
      for (const line of chunk.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (!dataLines.length) continue;
      onEvent(event, JSON.parse(dataLines.join("\n")));
    }
  }
}

function queueTranscriptPaint() {
  if (paintQueued) return;
  paintQueued = true;
  requestAnimationFrame(() => {
    paintQueued = false;
    renderTranscript();
  });
}

async function sendTurn(body) {
  if (state.running || state.loading || !state.activeId) return;
  const previous = JSON.stringify({
    status: state.view && state.view.status,
    count: state.view && state.view.messages ? state.view.messages.length : 0,
  });
  state.running = true;
  state.error = "";
  state.liveText = "";
  state.activity = "";
  state.editing = null;
  state.pendingUserText = typeof body.content === "string" ? body.content.trim() : "";
  state.startedAt = Date.now();
  stickToBottom = true;
  const draft = document.getElementById("draft");
  if (draft && body.content && draft.value.trim() === body.content.trim()) draft.value = "";
  resizeDraft();
  renderAll();
  let sawSnapshot = false;
  try {
    const response = await fetch(`/api/threads/${state.activeId}/turns/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        "X-Dice-User": state.userId,
      },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      let message = response.statusText;
      try {
        const data = await response.json();
        message = detailMessage(data.detail) || message;
      } catch (_error) {
        /* keep the status text */
      }
      throw new Error(message || "Request failed");
    }
    await readSse(response, (event, data) => {
      if (event === "token") {
        state.liveText += (data && data.text) || "";
        queueTranscriptPaint();
      } else if (event === "activity") {
        state.activity = (data && data.node) || "";
        renderStatus();
      } else if (event === "snapshot") {
        sawSnapshot = true;
        state.view = data;
        state.liveText = "";
      } else if (event === "error") {
        throw new Error((data && data.message) || "The workflow failed.");
      }
    });
    if (!sawSnapshot) throw new Error("The workflow ended without a result.");
    await refreshThreads();
    await refreshFiles();
  } catch (error) {
    state.error = error.message;
    try {
      const fresh = await api(`/api/threads/${state.activeId}`);
      const now = JSON.stringify({
        status: fresh.status,
        count: fresh.messages ? fresh.messages.length : 0,
      });
      state.view = fresh;
      if (now !== previous) state.error = "";
    } catch (_refreshError) {
      /* keep the original error */
    }
  } finally {
    const restore = state.error ? state.pendingUserText : "";
    state.running = false;
    state.liveText = "";
    state.pendingUserText = "";
    state.activity = "";
    if (restore && draft && !draft.value.trim()) draft.value = restore;
    renderAll();
    resizeDraft();
    syncComposer();
    if (draft && !draft.disabled) draft.focus();
  }
}

function speakerName(message) {
  const name = String((message && message.name) || "").toLowerCase();
  if (name.includes("supervisor")) return "Supervisor";
  if (name.includes("discovery")) return "Discovery";
  if (name.includes("design")) return "Design";
  return "Agent";
}

function interruptPrompt(interrupt) {
  return String(interrupt.question || interrupt.summary || "The workflow needs your input.");
}

function blocksFor(message) {
  if (!message || message.role === "system") return [];
  if (message.role === "tool") return [{ kind: "tool", message }];
  if (message.role === "human") {
    return message.content
      ? [{ kind: "human", text: message.content, displayOnly: Boolean(message.display_only) }]
      : [];
  }
  const blocks = [];
  const speaker = speakerName(message);
  const openQuestions = new Set((state.view?.interrupts || []).map((item) => interruptPrompt(item).trim()));
  const shown = new Set();
  if (message.content) {
    const text = String(message.content);
    const hidden = state.view?.status === "awaiting_input" && openQuestions.has(text.trim());
    if (!hidden) {
      blocks.push({ kind: "agent", speaker, text });
      shown.add(text.trim());
    }
  }
  for (const call of message.tool_calls || []) {
    if (call.name === "ask_user" && call.args && call.args.question) {
      const question = String(call.args.question);
      if (shown.has(question.trim())) continue;
      if (state.view?.status === "awaiting_input" && openQuestions.has(question.trim())) continue;
      blocks.push({ kind: "agent", speaker, text: question });
      shown.add(question.trim());
      continue;
    }
    blocks.push({ kind: "call", call });
  }
  return blocks;
}

function echoOfReply(block, previous) {
  const name = (block.message && block.message.name) || "";
  if (name !== "ask_user" && name !== "request_tool_approval") return false;
  const prior = previous[previous.length - 1];
  if (!prior || prior.kind !== "human" || !prior.displayOnly) return false;
  if (name === "request_tool_approval") return true;
  return prior.text.trim() === String(block.message.content || "").trim();
}

function visibleBlocks(messages) {
  const blocks = [];
  for (const message of messages) {
    for (const block of blocksFor(message)) {
      if (block.kind === "tool" && echoOfReply(block, blocks)) continue;
      blocks.push(block);
    }
  }
  return blocks;
}

function renderBlock(block) {
  if (block.kind === "human") {
    return `<article class="bubble human"><span class="who">You</span><div class="body">${formatText(block.text)}</div></article>`;
  }
  if (block.kind === "agent") {
    return `<article class="bubble agent"><span class="who">${escapeHtml(block.speaker || "Agent")}</span><div class="body">${formatText(block.text)}</div></article>`;
  }
  if (block.kind === "call") {
    const name = escapeHtml(block.call.name || "tool");
    const args = escapeHtml(JSON.stringify(block.call.args || {}, null, 2));
    return `<details class="tool"><summary>${name}</summary><pre>${args}</pre></details>`;
  }
  const name = escapeHtml((block.message && block.message.name) || "tool");
  const note = block.message && block.message.truncated
    ? `<p class="truncated">Showing the first part of this result.</p>`
    : "";
  return `<details class="tool"><summary>${name}</summary><div class="body">${formatText(block.message.content || "")}</div>${note}</details>`;
}

function setupHint() {
  const health = state.health;
  if (!health) return "";
  if (!health.llm_installed) return 'Install the model client with: pip install -e ".[web]"';
  if (!health.llm_configured) return "Add OPENAI_API_KEY to .env, then restart the server.";
  return "";
}

function welcomeHtml() {
  const hint = setupHint();
  const suggestions = state.activeId
    ? `<div class="chips">${SUGGESTIONS.map(
        (text) => `<button type="button" class="chip" data-suggestion="${escapeHtml(text)}">${escapeHtml(text)}</button>`,
      ).join("")}</div>`
    : `<button type="button" class="primary" data-new-thread>New migration</button>`;
  return `<div class="welcome">
    <p class="eyebrow">Supervisor</p>
    <h2>Start a migration</h2>
    <p>The supervisor collects intake, runs discovery and design, and stops when a decision is yours.</p>
    ${hint ? `<p class="hint-block">${escapeHtml(hint)}</p>` : ""}
    ${suggestions}
  </div>`;
}

function workingRow(label) {
  return `<div class="working"><span>${escapeHtml(label)}</span><i></i><i></i><i></i></div>`;
}

function transcriptHtml() {
  const messages = (state.view && state.view.messages) || [];
  let blocks = visibleBlocks(messages);
  if (state.running && state.pendingUserText) {
    const last = blocks[blocks.length - 1];
    if (!last || last.kind !== "human" || last.text.trim() !== state.pendingUserText) {
      blocks = blocks.concat([{ kind: "human", text: state.pendingUserText, displayOnly: true }]);
    }
  }
  if (!blocks.length && !state.running && !state.loading) return welcomeHtml();
  let html = blocks.map(renderBlock).join("");
  if (state.loading && !state.running) html += workingRow("Opening the workflow");
  if (state.running) {
    html += workingRow("Working");
    if (state.liveText) html += renderBlock({ kind: "agent", speaker: "Agent", text: state.liveText });
  }
  return html;
}

function optionsOf(interrupt) {
  const raw = interrupt.options || interrupt.allowed_decisions || [];
  return Array.isArray(raw) ? raw : [];
}

function optionLabel(option) {
  if (typeof option === "string") return option;
  if (option && typeof option === "object") {
    return String(option.label || option.value || JSON.stringify(option));
  }
  return String(option);
}

function isReview(interrupt) {
  const type = String(interrupt.type || "").toLowerCase();
  return type === "tool_review" || String(interrupt.input_type || "") === "tool_review";
}

function interruptKey(view) {
  return ((view && view.interrupts) || []).map((item) => item.interrupt_id || "").join("|");
}

function selectionKey() {
  return Object.entries(state.pendingAnswers)
    .map(([id, picked]) => `${id}:${picked.label}`)
    .sort()
    .join("|");
}

function pressed(rawId, label) {
  const selected = state.pendingAnswers[rawId];
  return selected && selected.label === label ? "true" : "false";
}

function interruptCard(interrupt, index, total) {
  const rawId = String(interrupt.interrupt_id || "");
  const id = escapeHtml(rawId);
  const phase = phaseLabel(interrupt.phase || (state.view && state.view.phase));
  let kicker = `Needs your answer · ${phase}`;
  if (isReview(interrupt)) kicker = `Review tool call · ${phase}`;
  else if (String(interrupt.type || "").includes("approval")) kicker = `Approval · ${phase}`;
  if (total > 1) kicker += ` · ${index + 1} of ${total}`;
  const disabled = state.running ? "disabled" : "";
  let extra = "";
  if (interrupt.tool_name) extra += `<p class="tool-name">${escapeHtml(String(interrupt.tool_name))}</p>`;
  if (interrupt.reason) extra += `<p class="reason">${escapeHtml(String(interrupt.reason))}</p>`;
  const action = interrupt.action_request || interrupt.action;
  if (action && typeof action === "object") {
    extra += `<pre class="action">${escapeHtml(JSON.stringify(action, null, 2))}</pre>`;
  }
  let controls = "";
  if (state.editing === rawId && isReview(interrupt)) {
    const prefill = escapeHtml(JSON.stringify(action || { name: interrupt.tool_name || "", args: {} }, null, 2));
    controls = `<textarea id="edit-json" class="edit-json" ${disabled}>${prefill}</textarea>
      <div class="ask-actions">
        <button type="button" class="sage" data-submit-edit data-interrupt-id="${id}" ${disabled}>Use edited call</button>
        <button type="button" data-cancel-edit ${disabled}>Cancel</button>
      </div>`;
  } else if (isReview(interrupt)) {
    controls = `<div class="ask-actions">
      <button type="button" class="sage" data-decision="approve" data-interrupt-id="${id}" aria-pressed="${pressed(rawId, "approve")}" ${disabled}>Approve</button>
      <button type="button" class="danger" data-decision="reject" data-interrupt-id="${id}" aria-pressed="${pressed(rawId, "reject")}" ${disabled}>Reject</button>
      <button type="button" data-edit data-interrupt-id="${id}" ${disabled}>Edit arguments</button>
    </div>`;
  } else {
    const options = optionsOf(interrupt);
    if (options.length) {
      controls = `<div class="ask-actions">${options
        .map((option, optionIndex) => {
          const label = optionLabel(option);
          return `<button type="button" class="choice" data-choice-index="${optionIndex}" data-interrupt-id="${id}" aria-pressed="${pressed(rawId, label)}" ${disabled}>${escapeHtml(label)}</button>`;
        })
        .join("")}</div>`;
    }
    if (total > 1 && !options.length) {
      const value = (state.pendingAnswers[rawId] && state.pendingAnswers[rawId].value) || "";
      controls += `<input class="text-answer" data-text-for="${id}" value="${escapeHtml(String(value))}" placeholder="Your answer" ${disabled} />`;
    }
  }
  return `<section class="ask">
    <p class="ask-kicker">${escapeHtml(kicker)}</p>
    <h3>${escapeHtml(interruptPrompt(interrupt))}</h3>
    ${extra}
    ${controls}
  </section>`;
}

function interruptHtml() {
  const interrupts = (state.view && state.view.interrupts) || [];
  if (!interrupts.length) return "";
  const cards = interrupts.map((item, index) => interruptCard(item, index, interrupts.length)).join("");
  if (interrupts.length < 2) return cards;
  const disabled = state.running ? "disabled" : "";
  return `${cards}<button type="button" class="sage submit-all" data-submit-all ${disabled}>Continue</button>`;
}

function captureTextAnswers() {
  document.querySelectorAll("[data-text-for]").forEach((field) => {
    const id = field.getAttribute("data-text-for");
    const text = field.value.trim();
    if (id && text) state.pendingAnswers[id] = { value: text, label: text };
  });
}

function renderInterrupt() {
  const host = document.getElementById("interrupt");
  const nextIds = interruptKey(state.view);
  if (state.answerKey !== nextIds) {
    state.answerKey = nextIds;
    state.pendingAnswers = {};
    state.editing = null;
  } else {
    captureTextAnswers();
  }
  const key = `${nextIds}|${state.editing || ""}|${state.running ? "1" : "0"}|${selectionKey()}`;
  if (host.dataset.key === key) return;
  host.dataset.key = key;
  host.innerHTML = interruptHtml();
}

function commit(interrupt, value, label) {
  const interrupts = (state.view && state.view.interrupts) || [];
  if (interrupts.length < 2) {
    state.editing = null;
    if (typeof value === "string") sendTurn({ content: value });
    else sendTurn({ content: label, answer: value });
    return;
  }
  state.pendingAnswers[String(interrupt.interrupt_id)] = { value, label };
  state.editing = null;
  renderInterrupt();
}

function submitEdit(interrupt) {
  const field = document.getElementById("edit-json");
  let parsed;
  try {
    parsed = JSON.parse(field.value);
  } catch (_error) {
    state.error = "Edited call must be valid JSON.";
    renderProblems();
    return;
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    state.error = "Edited call must be a JSON object.";
    renderProblems();
    return;
  }
  const edited = parsed.name
    ? parsed
    : { name: String(interrupt.tool_name || ""), args: parsed.args || parsed };
  state.error = "";
  commit(interrupt, { type: "edit", edited_action: edited }, "edit");
}

function submitCollected() {
  const interrupts = (state.view && state.view.interrupts) || [];
  captureTextAnswers();
  const answer = {};
  const labels = [];
  for (const item of interrupts) {
    const picked = state.pendingAnswers[String(item.interrupt_id || "")];
    if (!picked || picked.value == null || picked.value === "") {
      state.error = "Answer each open question before continuing.";
      renderProblems();
      return;
    }
    answer[item.interrupt_id] = picked.value;
    labels.push(picked.label);
  }
  state.error = "";
  sendTurn({ answer, content: labels.join(" · ") });
}

function onInterruptClick(event) {
  const button = event.target.closest("button");
  if (!button || state.running) return;
  if (button.hasAttribute("data-submit-all")) {
    submitCollected();
    return;
  }
  if (button.hasAttribute("data-cancel-edit")) {
    state.editing = null;
    renderInterrupt();
    return;
  }
  const id = button.getAttribute("data-interrupt-id");
  const interrupt = ((state.view && state.view.interrupts) || []).find(
    (item) => String(item.interrupt_id) === id,
  );
  if (button.hasAttribute("data-edit")) {
    state.editing = id;
    renderInterrupt();
    return;
  }
  if (!interrupt) return;
  if (button.hasAttribute("data-submit-edit")) {
    submitEdit(interrupt);
    return;
  }
  if (button.hasAttribute("data-decision")) {
    const decision = button.getAttribute("data-decision");
    commit(interrupt, { type: decision }, decision);
    return;
  }
  if (button.hasAttribute("data-choice-index")) {
    const option = optionsOf(interrupt)[Number(button.getAttribute("data-choice-index"))];
    const label = optionLabel(option);
    commit(interrupt, label, label);
  }
}

function phaseRailHtml() {
  const phase = (state.view && state.view.phase) || "";
  const canonical = canonicalPhase(phase);
  const index = PHASES.findIndex((item) => item.id === canonical);
  const steps = PHASES.map((item, step) => {
    let mark = "";
    if (index > step) mark = "done";
    if (index === step) mark = "current";
    return `<li class="step ${mark}"><span class="dot"></span><span>${item.label}</span></li>`;
  }).join("");
  const rework = String(phase).toLowerCase().startsWith("rework_");
  const note = rework
    ? `<p class="rework">${escapeHtml(phaseLabel(phase))}</p>`
    : index < 0 && phase
      ? `<p class="rework">${escapeHtml(String(phase))}</p>`
      : "";
  return `<section><h2>Phase</h2><ol class="steps">${steps}</ol>${note}</section>`;
}

function todoLabel(todo) {
  if (typeof todo === "string") return todo;
  return String(todo.content || todo.title || todo.task || JSON.stringify(todo));
}

function todoDone(todo) {
  if (!todo || typeof todo !== "object") return false;
  const status = String(todo.status || "").toLowerCase();
  return status === "completed" || status === "done" || todo.completed === true;
}

function todosHtml() {
  const todos = (state.view && state.view.todos) || [];
  if (!todos.length) return "";
  const items = todos
    .map((todo) => `<li class="${todoDone(todo) ? "done" : ""}">${escapeHtml(todoLabel(todo))}</li>`)
    .join("");
  return `<section><h3>Tasks</h3><ul class="todos">${items}</ul></section>`;
}

function filesHtml() {
  const files = state.files || [];
  const items = files.length
    ? files
        .map((path, index) => {
          const active = state.openFile && state.openFile.path === path ? " active" : "";
          return `<button type="button" class="file${active}" data-file-index="${index}">${escapeHtml(path)}</button>`;
        })
        .join("")
    : `<p class="empty">Artifacts and scratch notes land here.</p>`;
  const viewer = state.openFile
    ? `<div class="viewer"><div class="viewer-bar"><span>${escapeHtml(state.openFile.path)}</span><button type="button" data-close-file>Close</button></div><pre>${escapeHtml(state.openFile.content || "")}</pre></div>`
    : "";
  return `<section><h3>Workspace</h3><div class="files">${items}</div>${viewer}</section>`;
}

function identityHtml() {
  const view = state.view;
  if (!view) return "";
  const rows = [
    ["Application", view.application_id],
    ["Artifact", view.artifact_id],
    ["Discovery", view.discovery_status],
  ].filter(([, value]) => value);
  if (!rows.length) return "";
  const body = rows
    .map(([label, value]) => `<div><dt>${label}</dt><dd>${escapeHtml(String(value))}</dd></div>`)
    .join("");
  return `<section><h3>Record</h3><dl class="record">${body}</dl></section>`;
}

function notesHtml() {
  const errors = (state.view && state.view.errors) || [];
  if (!errors.length) return "";
  return `<section><h3>Notes</h3>${errors
    .map((item) => `<p class="note">${escapeHtml(String(item))}</p>`)
    .join("")}</section>`;
}

function renderRail() {
  const meta = state.activeId
    ? `<p class="thread-meta">Thread <code>${escapeHtml(state.activeId)}</code></p>`
    : "";
  document.getElementById("rail-body").innerHTML = [
    phaseRailHtml(),
    identityHtml(),
    todosHtml(),
    filesHtml(),
    notesHtml(),
    meta,
  ].join("");
}

function renderThreads() {
  const list = document.getElementById("thread-list");
  if (!state.threads.length) {
    list.innerHTML = `<li class="empty-threads">No migrations yet</li>`;
    return;
  }
  list.innerHTML = state.threads
    .map((thread) => {
      const current = thread.thread_id === state.activeId ? ' aria-current="page"' : "";
      return `<li><button type="button" class="thread" data-thread-id="${thread.thread_id}"${current}><span class="thread-title">${escapeHtml(thread.title || "New migration")}</span><span class="thread-phase">${escapeHtml(phaseLabel(thread.phase))}</span></button></li>`;
    })
    .join("");
}

function renderHeader() {
  const title = document.getElementById("thread-title");
  const phase = document.getElementById("phase-kicker");
  const remove = document.getElementById("remove-thread");
  if (!state.view) {
    title.textContent = state.activeId ? "Opening…" : "No migration selected";
    phase.textContent = "";
    remove.hidden = !state.activeId;
  } else {
    title.textContent = state.view.title || "New migration";
    phase.textContent = phaseLabel(state.view.phase);
    remove.hidden = false;
  }
  remove.disabled = state.running || state.loading;
  document.title = state.view && state.view.title ? `${state.view.title} · DICE` : "DICE workflow";
}

function renderStatus() {
  const pill = document.getElementById("status-pill");
  pill.textContent = statusText();
  pill.dataset.state = statusState();
  document.querySelector("main").setAttribute("aria-busy", state.running || state.loading ? "true" : "false");
}

function renderProblems() {
  const banner = document.getElementById("banner");
  if (!state.error) {
    banner.hidden = true;
    banner.textContent = "";
    return;
  }
  banner.hidden = false;
  banner.textContent = state.error;
}

function renderTranscript() {
  const host = document.getElementById("transcript");
  const stick = stickToBottom || state.running || state.loading;
  host.innerHTML = transcriptHtml();
  if (stick) host.scrollTop = host.scrollHeight;
}

function resizeDraft() {
  const draft = document.getElementById("draft");
  draft.style.height = "auto";
  draft.style.height = `${Math.min(draft.scrollHeight, 180)}px`;
}

function syncComposer() {
  const draft = document.getElementById("draft");
  const send = document.getElementById("send");
  const interrupts = (state.view && state.view.interrupts) || [];
  const multi = interrupts.length > 1;
  const complete = Boolean(
    state.view && (state.view.status === "complete" || canonicalPhase(state.view.phase) === "complete"),
  );
  draft.disabled = state.running || state.loading || complete || !state.activeId || multi;
  send.disabled = draft.disabled || !draft.value.trim();
  document.getElementById("new-thread").disabled = state.running || state.loading;
  if (!state.activeId) draft.placeholder = "Start a migration first";
  else if (complete) draft.placeholder = "This migration is complete";
  else if (multi) draft.placeholder = "Answer each question above";
  else if (interrupts.length === 1) draft.placeholder = "Reply to the question";
  else draft.placeholder = "Tell the supervisor what to do";
}

function renderAll() {
  renderThreads();
  renderHeader();
  renderStatus();
  renderProblems();
  renderTranscript();
  renderInterrupt();
  renderRail();
  syncComposer();
}

function bind() {
  document.getElementById("new-thread").addEventListener("click", () => {
    createThread().catch((error) => {
      state.error = error.message;
      renderProblems();
    });
  });
  document.getElementById("remove-thread").addEventListener("click", () => {
    removeThread().catch((error) => {
      state.error = error.message;
      renderProblems();
    });
  });
  document.getElementById("thread-list").addEventListener("click", (event) => {
    const button = event.target.closest("[data-thread-id]");
    if (!button || state.running) return;
    openThread(button.dataset.threadId);
  });
  document.getElementById("transcript").addEventListener("click", (event) => {
    if (event.target.closest("[data-new-thread]")) {
      createThread().catch((error) => {
        state.error = error.message;
        renderProblems();
      });
      return;
    }
    const suggestion = event.target.closest("[data-suggestion]");
    if (!suggestion) return;
    const draft = document.getElementById("draft");
    draft.value = suggestion.getAttribute("data-suggestion") || "";
    resizeDraft();
    syncComposer();
    draft.focus();
  });
  document.getElementById("transcript").addEventListener("scroll", () => {
    const host = document.getElementById("transcript");
    stickToBottom = host.scrollHeight - host.scrollTop - host.clientHeight < 120;
  });
  document.getElementById("interrupt").addEventListener("click", onInterruptClick);
  document.getElementById("rail").addEventListener("click", (event) => {
    const fileButton = event.target.closest("[data-file-index]");
    if (fileButton) {
      const path = state.files[Number(fileButton.dataset.fileIndex)];
      if (path) openFile(path);
      return;
    }
    if (event.target.closest("[data-close-file]")) {
      state.openFile = null;
      renderRail();
    }
  });
  const form = document.getElementById("composer");
  const draft = document.getElementById("draft");
  draft.addEventListener("input", () => {
    resizeDraft();
    syncComposer();
  });
  draft.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = draft.value.trim();
    if (!text || state.running || draft.disabled) return;
    draft.value = "";
    resizeDraft();
    sendTurn({ content: text });
  });
  window.addEventListener("hashchange", () => {
    const id = location.hash.replace("#", "");
    if (id && id !== state.activeId && !state.running) openThread(id);
  });
  setInterval(() => {
    if (state.running || state.loading) renderStatus();
  }, 1000);
}

async function boot() {
  state.userId = localStorage.getItem("dice.user") || "local";
  document.getElementById("user-label").textContent = state.userId;
  bind();
  try {
    state.health = await api("/api/health");
  } catch (error) {
    state.error = error.message;
  }
  try {
    await refreshThreads();
  } catch (error) {
    state.error = error.message;
  }
  const wanted = location.hash.replace("#", "");
  const match = state.threads.find((thread) => thread.thread_id === wanted);
  renderAll();
  if (match) await openThread(match.thread_id);
  else if (state.threads[0]) await openThread(state.threads[0].thread_id);
}

boot().catch((error) => {
  state.error = error.message || "The page failed to start.";
  renderAll();
});
