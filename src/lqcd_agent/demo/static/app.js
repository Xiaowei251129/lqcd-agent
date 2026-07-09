const state = {
  configs: [],
  currentRun: null,
  pollTimer: null,
};

const nodeLabels = {
  START: "Start",
  method_planner: "Method Planner",
  analysis_engineer: "Analysis Engineer",
  scientific_reviewer: "Scientific Reviewer",
  decision_coordinator: "Decision Coordinator",
  human_approval_gate: "Human Approval",
  memory_report: "Memory / Report",
  codex_handoff: "Codex Handoff",
};

const els = {
  configSelect: document.querySelector("#configSelect"),
  configFile: document.querySelector("#configFile"),
  configText: document.querySelector("#configText"),
  validateButton: document.querySelector("#validateButton"),
  runButton: document.querySelector("#runButton"),
  configPreview: document.querySelector("#configPreview"),
  runStatus: document.querySelector("#runStatus"),
  routeTimeline: document.querySelector("#routeTimeline"),
  eventList: document.querySelector("#eventList"),
  summaryGrid: document.querySelector("#summaryGrid"),
  reportSummary: document.querySelector("#reportSummary"),
  artifactLinks: document.querySelector("#artifactLinks"),
  approvalButton: document.querySelector("#approvalButton"),
  approvalDialog: document.querySelector("#approvalDialog"),
  approvalForm: document.querySelector("#approvalForm"),
  approvalDetails: document.querySelector("#approvalDetails"),
  decisionSelect: document.querySelector("#decisionSelect"),
  decisionConditions: document.querySelector("#decisionConditions"),
  decisionReason: document.querySelector("#decisionReason"),
  decidedBy: document.querySelector("#decidedBy"),
  cancelApproval: document.querySelector("#cancelApproval"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
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

function selectedRequestBody() {
  const configText = els.configText.value.trim();
  return configText ? { config_text: configText } : { config_id: els.configSelect.value };
}

function setBusy(isBusy) {
  els.runButton.disabled = isBusy;
  els.validateButton.disabled = isBusy;
  els.configSelect.disabled = isBusy;
  els.configText.disabled = isBusy;
}

async function loadConfigs() {
  const payload = await requestJson("/api/configs");
  state.configs = payload.configs || [];
  els.configSelect.innerHTML = state.configs
    .map(
      (item) =>
        `<option value="${escapeHtml(item.config_id)}">${escapeHtml(item.label)} - ${escapeHtml(
          item.source_kind || "case_config"
        )}</option>`
    )
    .join("");
  const golden = state.configs.find((item) => item.config_id === "l64c64a076_m140");
  if (golden) {
    els.configSelect.value = golden.config_id;
  }
}

function renderConfigPreview(config) {
  const warnings = config.warnings?.length ? `\nWarnings:\n- ${config.warnings.join("\n- ")}` : "";
  els.configPreview.textContent = [
    `case_id: ${config.case_id}`,
    `physics_goal: ${config.physics_goal || "missing"}`,
    `analysis_commands: ${(config.analysis_commands || []).join(", ") || "default"}`,
    `expected_outputs: ${(config.expected_outputs || []).join(", ") || "default"}`,
    warnings,
  ]
    .filter(Boolean)
    .join("\n");
}

async function validateConfig() {
  els.configPreview.textContent = "Validating...";
  const payload = await requestJson("/api/configs/validate", {
    method: "POST",
    body: JSON.stringify(selectedRequestBody()),
  });
  renderConfigPreview(payload.config);
}

async function startRun() {
  clearInterval(state.pollTimer);
  setBusy(true);
  els.runStatus.textContent = "Starting";
  els.reportSummary.textContent = "Run is starting...";
  els.artifactLinks.innerHTML = "";
  const payload = await requestJson("/api/runs", {
    method: "POST",
    body: JSON.stringify(selectedRequestBody()),
  });
  renderRun(payload);
  state.pollTimer = setInterval(() => pollRun(payload.case_id, payload.run_id), 1200);
}

async function pollRun(caseId, runId) {
  try {
    const payload = await requestJson(`/api/runs/${encodeURIComponent(caseId)}/${encodeURIComponent(runId)}`);
    renderRun(payload);
    const status = payload.summary?.status;
    const jobStatus = payload.job_status;
    if (jobStatus === "failed" || ["success", "pending", "halted", "failed"].includes(status)) {
      clearInterval(state.pollTimer);
      setBusy(false);
    }
  } catch (error) {
    clearInterval(state.pollTimer);
    setBusy(false);
    els.runStatus.textContent = "Error";
    els.reportSummary.textContent = error.message || String(error);
  }
}

function pill(value) {
  const text = value === null || value === undefined || value === "" ? "none" : String(value);
  const cls = text.toLowerCase().replaceAll(" ", "_");
  return `<span class="pill ${cls}">${escapeHtml(text)}</span>`;
}

function renderRun(payload) {
  state.currentRun = payload;
  const summary = payload.summary || {};
  els.runStatus.textContent = payload.job_status || summary.status || "running";
  renderSummary(payload);
  renderRoute(summary.route_nodes || []);
  renderEvents(payload.events || []);
  renderArtifacts(payload.artifacts || []);
  els.reportSummary.textContent = payload.final_report_summary || payload.job_error || "Report not available yet.";
  const needsApproval = payload.approval?.pending;
  els.approvalButton.classList.toggle("hidden", !needsApproval);
}

function renderSummary(payload) {
  const summary = payload.summary || {};
  const rows = [
    ["Case", payload.case_id],
    ["Run", payload.run_id],
    ["Status", summary.status || payload.job_status],
    ["Risk", summary.risk_level],
    ["Action", summary.recommended_action],
    ["Approval", summary.human_approval_required ? "required" : "not required"],
    ["Memory", summary.memory_status],
  ];
  els.summaryGrid.innerHTML = rows
    .map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${pill(value)}</dd>`)
    .join("");
}

function renderRoute(routeNodes) {
  const nodes = routeNodes.length ? routeNodes : ["START"];
  els.routeTimeline.innerHTML = nodes
    .map((node) => `<li><span>${escapeHtml(nodeLabels[node] || node)}</span></li>`)
    .join("");
}

function renderEvents(events) {
  const visible = events.slice(-8).reverse();
  els.eventList.innerHTML = visible.length
    ? visible
        .map(
          (event) =>
            `<li><strong>${escapeHtml(nodeLabels[event.node] || event.node)}</strong><span>${escapeHtml(
              event.summary || event.kind || ""
            )}</span></li>`
        )
        .join("")
    : "<li><span>No events yet.</span></li>";
}

function renderArtifacts(artifacts) {
  const visibleNames = new Set([
    "method_plan",
    "run_result",
    "scientific_review",
    "decision_log",
    "approval_packet",
    "human_decision",
    "memory_update",
    "final_report",
    "graph_state",
  ]);
  const visible = artifacts.filter((item) => visibleNames.has(item.name));
  els.artifactLinks.innerHTML = visible.length
    ? visible
        .map((item) => {
          const href = item.exists ? item.url : "#";
          const cls = item.exists ? "" : "missing";
          return `<a class="${cls}" href="${escapeHtml(href)}" target="_blank" rel="noreferrer">${escapeHtml(
            item.name
          )}</a>`;
        })
        .join("")
    : "<span>No artifacts yet.</span>";
}

function openApprovalDialog() {
  const approval = state.currentRun?.approval;
  const packet = approval?.packet;
  if (!packet) {
    return;
  }
  const requested = packet.requested_decision || {};
  els.approvalDetails.innerHTML = `
    <p><strong>Risk:</strong> ${escapeHtml(requested.risk_level)}</p>
    <p><strong>Recommended action:</strong> ${escapeHtml(requested.recommended_action)}</p>
    <p><strong>Summary:</strong> ${escapeHtml(packet.human_summary || packet.summary || "")}</p>
  `;
  const options = packet.decision_options || [];
  els.decisionSelect.innerHTML = options
    .map((option) => `<option value="${escapeHtml(option.decision)}">${escapeHtml(option.decision)}</option>`)
    .join("");
  els.approvalDialog.showModal();
}

async function submitHumanDecision(event) {
  event.preventDefault();
  const run = state.currentRun;
  if (!run) {
    return;
  }
  const payload = await requestJson(
    `/api/runs/${encodeURIComponent(run.case_id)}/${encodeURIComponent(run.run_id)}/human-decision`,
    {
      method: "POST",
      body: JSON.stringify({
        decision: els.decisionSelect.value,
        conditions: els.decisionConditions.value,
        reason: els.decisionReason.value,
        decided_by: els.decidedBy.value,
      }),
    }
  );
  els.approvalDialog.close();
  renderRun(payload);
}

els.validateButton.addEventListener("click", () => validateConfig().catch((error) => (els.configPreview.textContent = error.message)));
els.runButton.addEventListener("click", () => startRun().catch((error) => {
  setBusy(false);
  els.runStatus.textContent = "Error";
  els.reportSummary.textContent = error.message || String(error);
}));
els.configFile.addEventListener("change", async () => {
  const file = els.configFile.files?.[0];
  if (file) {
    els.configText.value = await file.text();
  }
});
els.approvalButton.addEventListener("click", openApprovalDialog);
els.cancelApproval.addEventListener("click", () => els.approvalDialog.close());
els.approvalForm.addEventListener("submit", (event) => submitHumanDecision(event).catch((error) => {
  els.approvalDetails.textContent = error.message || String(error);
}));

loadConfigs().catch((error) => {
  els.configPreview.textContent = error.message || String(error);
});
