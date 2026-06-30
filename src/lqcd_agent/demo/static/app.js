const state = {
  configs: [],
  busy: false,
  currentRun: null,
};

const nodeLabels = {
  method_planner: "Method Planner",
  analysis_engineer: "Analysis Engineer",
  scientific_reviewer: "Scientific Reviewer",
  decision_coordinator: "Decision Coordinator",
  human_approval_gate: "Human Approval",
  memory_report: "Memory / Report",
  codex_handoff: "Codex Handoff",
};

const els = {
  caseSelect: document.querySelector("#caseSelect"),
  chatForm: document.querySelector("#chatForm"),
  questionInput: document.querySelector("#questionInput"),
  sendButton: document.querySelector("#sendButton"),
  messages: document.querySelector("#messages"),
  statusText: document.querySelector("#statusText"),
  summaryGrid: document.querySelector("#summaryGrid"),
  routeTimeline: document.querySelector("#routeTimeline"),
  artifactLinks: document.querySelector("#artifactLinks"),
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setBusy(value, text) {
  state.busy = value;
  els.sendButton.disabled = value;
  els.questionInput.disabled = value;
  els.caseSelect.disabled = value;
  els.statusText.textContent = text || (value ? "Running" : "Ready");
}

function addMessage(role, text) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  article.appendChild(bubble);
  els.messages.appendChild(article);
  els.messages.scrollTop = els.messages.scrollHeight;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return payload;
}

async function loadCases() {
  const payload = await requestJson("/api/configs");
  state.configs = payload.configs || [];
  els.caseSelect.innerHTML = state.configs
    .map(
      (item) =>
        `<option value="${escapeHtml(item.config_id)}">${escapeHtml(item.label)} - ${escapeHtml(
          item.source_kind || "case_config"
        )}</option>`
    )
    .join("");
  const golden = state.configs.find((item) => item.config_id === "l64c64a076_m140");
  if (golden) {
    els.caseSelect.value = golden.config_id;
  }
}

async function submitQuestion(event) {
  event.preventDefault();
  const question = els.questionInput.value.trim();
  if (!question) {
    return;
  }
  addMessage("user", question);
  els.questionInput.value = "";
  setBusy(true, "Running LangGraph");
  try {
    const payload = await requestJson("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        message: question,
        config_id: els.caseSelect.value,
      }),
    });
    addMessage("assistant", payload.content);
    renderEvidence(payload);
    setBusy(false, "Ready");
  } catch (error) {
    addMessage("assistant", error.message || String(error));
    setBusy(false, "Error");
  }
}

function pill(value) {
  const text = value === null || value === undefined || value === "" ? "none" : String(value);
  const cls = text.toLowerCase().replaceAll(" ", "_");
  return `<span class="pill ${cls}">${escapeHtml(text)}</span>`;
}

function renderEvidence(payload) {
  const run = payload.run;
  state.currentRun = run;
  if (!run) {
    return;
  }
  const summary = run.summary || {};
  const rows = [
    ["Case", run.case_id],
    ["Run", run.run_id],
    ["Status", summary.status],
    ["Risk", summary.risk_level],
    ["Action", summary.recommended_action],
    ["Approval", summary.human_approval_required ? "required" : "not required"],
    ["Memory", summary.memory_status],
  ];
  els.summaryGrid.innerHTML = rows
    .map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${pill(value)}</dd>`)
    .join("");
  renderRoute(summary.route_nodes || []);
  renderArtifacts(run.artifacts || []);
}

function renderRoute(routeNodes) {
  els.routeTimeline.innerHTML = routeNodes.length
    ? routeNodes
        .map((node) => `<li><span>${escapeHtml(nodeLabels[node] || node)}</span></li>`)
        .join("")
    : "<li><span>No route recorded</span></li>";
}

function renderArtifacts(artifacts) {
  const visible = artifacts.filter((item) =>
    ["method_plan", "run_result", "scientific_review", "decision_log", "memory_update", "final_report", "checklist"].includes(
      item.name
    )
  );
  els.artifactLinks.innerHTML = visible.length
    ? visible
        .map((item) => {
          const disabled = item.exists ? "" : "missing";
          const href = item.exists ? item.url : "#";
          return `<a class="${disabled}" href="${escapeHtml(href)}" target="_blank" rel="noreferrer">${escapeHtml(
            item.name
          )}</a>`;
        })
        .join("")
    : "<span>No artifacts yet</span>";
}

els.chatForm.addEventListener("submit", submitQuestion);
els.questionInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
    els.chatForm.requestSubmit();
  }
});

loadCases().catch((error) => addMessage("assistant", error.message || String(error)));
