const state = {
  configs: [],
  runtimeConfigs: [],
  serverInfo: {},
  currentRun: null,
  pollTimer: null,
  busy: false,
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
  outputDir: document.querySelector("#outputDir"),
  runId: document.querySelector("#runId"),
  providerSelect: document.querySelector("#providerSelect"),
  providerStatus: document.querySelector("#providerStatus"),
  autoCodexHandoff: document.querySelector("#autoCodexHandoff"),
  forceCodexHandoff: document.querySelector("#forceCodexHandoff"),
  dryRunCodex: document.querySelector("#dryRunCodex"),
  codexBin: document.querySelector("#codexBin"),
  codexModel: document.querySelector("#codexModel"),
  codexTimeout: document.querySelector("#codexTimeout"),
  verificationTimeout: document.querySelector("#verificationTimeout"),
  validateButton: document.querySelector("#validateButton"),
  runButton: document.querySelector("#runButton"),
  configPreview: document.querySelector("#configPreview"),
  commandPreview: document.querySelector("#commandPreview"),
  runStatus: document.querySelector("#runStatus"),
  routeTimeline: document.querySelector("#routeTimeline"),
  eventList: document.querySelector("#eventList"),
  summaryGrid: document.querySelector("#summaryGrid"),
  reportSummary: document.querySelector("#reportSummary"),
  warningList: document.querySelector("#warningList"),
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
  const body = configText ? { config_text: configText } : { config_id: els.configSelect.value };
  const providerConfig = els.providerSelect.value;
  body.output_dir = els.outputDir.value.trim() || "outputs";
  body.run_id = els.runId.value.trim();
  body.llm_provider_config_path = providerConfig || null;
  body.auto_codex_handoff = els.autoCodexHandoff.checked;
  body.force_codex_handoff = els.forceCodexHandoff.checked;
  body.dry_run_codex = els.dryRunCodex.checked;
  body.codex_bin = els.codexBin.value.trim() || "codex";
  body.codex_model = els.codexModel.value.trim();
  body.codex_timeout_seconds = Number(els.codexTimeout.value || 900);
  body.verification_timeout_seconds = Number(els.verificationTimeout.value || 60);
  return body;
}

function setBusy(isBusy) {
  state.busy = isBusy;
  updateRunAvailability();
  els.validateButton.disabled = isBusy;
  els.configSelect.disabled = isBusy;
  els.configText.disabled = isBusy;
  els.outputDir.disabled = isBusy;
  els.runId.disabled = isBusy;
  els.providerSelect.disabled = isBusy;
}

function runBlockedReason() {
  const provider = selectedProvider();
  if (provider?.live_test_env && !provider.live_test_env_enabled) {
    return `${provider.live_test_env}=1 is required on the demo server process for live ${provider.provider} calls.`;
  }
  return "";
}

function updateRunAvailability() {
  els.runButton.disabled = state.busy || Boolean(runBlockedReason());
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
  const preferredConfigIds = [
    "clean_fit.input",
    "noisy_valid_fit.input",
    "fit_window_contamination.input",
    "plateau_instability.input",
    "missing_input.input",
  ];
  const preferredConfig = preferredConfigIds
    .map((configId) => state.configs.find((item) => item.config_id === configId))
    .find(Boolean);
  if (preferredConfig) {
    els.configSelect.value = preferredConfig.config_id;
  }
  updateCommandPreview();
}

async function loadRuntimeConfigs() {
  const payload = await requestJson("/api/runtime-configs");
  state.runtimeConfigs = payload.runtime_configs || [];
  state.serverInfo = payload.server || {};
  const options = ['<option value="">none - developer deterministic mode</option>'].concat(
    state.runtimeConfigs.map(
      (item) =>
        `<option value="${escapeHtml(item.path)}">${escapeHtml(item.label)}${item.live_test_env ? ` - ${escapeHtml(item.live_test_env)}` : ""}</option>`
    )
  );
  els.providerSelect.innerHTML = options.join("");
  const recommendedProvider =
    state.runtimeConfigs.find((item) => item.recommended) ||
    state.runtimeConfigs.find((item) => item.provider_mode === "live");
  if (recommendedProvider) {
    els.providerSelect.value = recommendedProvider.path;
  }
  renderProviderStatus();
  updateCommandPreview();
}

function selectedConfig() {
  return state.configs.find((item) => item.config_id === els.configSelect.value);
}

function selectedProvider() {
  return state.runtimeConfigs.find((item) => item.path === els.providerSelect.value);
}

function renderProviderStatus() {
  const provider = selectedProvider();
  if (!provider) {
    els.providerStatus.textContent = "Developer/testing deterministic mode selected; this is not the live LLM demo route.";
    els.providerStatus.className = "status-note warn";
    updateRunAvailability();
    return;
  }
  if (provider.live_test_env && !provider.live_test_env_enabled) {
    els.providerStatus.textContent = `${provider.live_test_env}=1 is not set on this server. Restart the demo server with that env var before running live ${provider.provider} calls.`;
    els.providerStatus.className = "status-note warn";
    updateRunAvailability();
    return;
  }
  if (!provider.live_test_env) {
    els.providerStatus.textContent = `${provider.provider} testing/developer provider selected; this is not the live LLM demo route.`;
    els.providerStatus.className = provider.provider_mode === "testing" ? "status-note warn" : "status-note ok";
    updateRunAvailability();
    return;
  }
  els.providerStatus.textContent = `${provider.provider} config selected. Required live env is available.`;
  els.providerStatus.className = "status-note ok";
  updateRunAvailability();
}

function shellQuote(value) {
  const text = String(value ?? "");
  return /^[A-Za-z0-9_./:=+-]+$/.test(text) ? text : `'${text.replaceAll("'", "'\\''")}'`;
}

function updateCommandPreview() {
  const config = selectedConfig();
  const configPath = els.configText.value.trim() ? "<generated pasted config>" : config?.path || "<case config>";
  const provider = selectedProvider();
  const outputDir = els.outputDir.value.trim() || "outputs";
  const parts = ["python", "-m", "lqcd_agent.graph.run_graph", "--case", configPath, "--output-dir", outputDir];
  const runId = els.runId.value.trim();
  if (runId) {
    parts.push("--run-id", runId);
  }
  if (provider) {
    parts.push("--llm-provider-config", provider.path);
  }
  if (els.autoCodexHandoff.checked) {
    parts.push("--auto-codex-handoff");
  }
  if ((els.codexBin.value.trim() || "codex") !== "codex") {
    parts.push("--codex-bin", els.codexBin.value.trim());
  }
  if (els.codexModel.value.trim()) {
    parts.push("--codex-model", els.codexModel.value.trim());
  }
  if (Number(els.codexTimeout.value || 900) !== 900) {
    parts.push("--codex-timeout-seconds", els.codexTimeout.value);
  }
  if (Number(els.verificationTimeout.value || 60) !== 60) {
    parts.push("--verification-timeout-seconds", els.verificationTimeout.value);
  }
  if (els.forceCodexHandoff.checked) {
    parts.push("--force-codex-handoff");
  }
  if (els.dryRunCodex.checked) {
    parts.push("--dry-run-codex");
  }
  let command = parts.map(shellQuote).join(" ");
  if (provider?.live_test_env && !provider.live_test_env_enabled) {
    command = `${provider.live_test_env}=1 ${command}`;
  }
  els.commandPreview.textContent = command;
}

function renderConfigPreview(config) {
  const warnings = config.warnings?.length ? `\nWarnings:\n- ${config.warnings.join("\n- ")}` : "";
  const route = config.analysis_route || "default_mock_command";
  const routeLabel = displayRoute(route);
  const programTags = (config.analysis_program_tags || []).join(", ");
  const targetObservables = (config.target_observables || []).join(", ");
  els.configPreview.textContent = [
    `case_id: ${config.case_id}`,
    `physics_goal: ${config.physics_goal || "missing"}`,
    `analysis_route: ${routeLabel}`,
    `raw_data_path: ${config.raw_data_path || "not configured"}`,
    `raw_data_status: ${config.raw_data_status || "not_configured"}`,
    route === "analysis_commands" ? `analysis_commands: ${(config.analysis_commands || []).join(", ")}` : "",
    route === "registered_analysis_program" && programTags ? `analysis_program_tags: ${programTags}` : "",
    route === "registered_analysis_program" && targetObservables ? `target_observables: ${targetObservables}` : "",
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
  els.warningList.textContent = "No warnings.";
  const payload = await requestJson("/api/runs", {
    method: "POST",
    body: JSON.stringify(selectedRequestBody()),
  });
  renderRun(payload);
  state.pollTimer = setInterval(() => pollRun(payload.case_id, payload.run_id, selectedRequestBody().output_dir), 1200);
}

async function pollRun(caseId, runId, outputDir) {
  try {
    const query = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : "";
    const payload = await requestJson(`/api/runs/${encodeURIComponent(caseId)}/${encodeURIComponent(runId)}${query}`);
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

function displayAction(value) {
  return value === "accept_mock_result" ? "accept_result" : value;
}

function displayRoute(value) {
  return value === "default_mock_command" ? "developer_testing_fallback" : value;
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
  renderWarnings(payload);
  if (payload.command_preview) {
    els.commandPreview.textContent = payload.command_preview;
  }
  const needsApproval = payload.approval?.pending;
  els.approvalButton.classList.toggle("hidden", !needsApproval);
}

function renderSummary(payload) {
  const summary = payload.summary || {};
  const rows = [
    ["Case", payload.case_id],
    ["Run", payload.run_id],
    ["Output", payload.run_dir],
    ["Status", summary.status || payload.job_status],
    ["Risk", summary.risk_level],
    ["Action", displayAction(summary.recommended_action)],
    ["Approval", summary.human_approval_required ? "required" : "not required"],
    ["Memory", summary.memory_status],
  ];
  els.summaryGrid.innerHTML = rows
    .map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${pill(value)}</dd>`)
    .join("");
}

function renderWarnings(payload) {
  const warnings = payload.warnings || [];
  els.warningList.innerHTML = warnings.length
    ? warnings.map((warning) => `<p>${escapeHtml(warning)}</p>`).join("")
    : "No warnings.";
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
    updateCommandPreview();
  }
});
[
  els.configSelect,
  els.configText,
  els.outputDir,
  els.runId,
  els.providerSelect,
  els.autoCodexHandoff,
  els.forceCodexHandoff,
  els.dryRunCodex,
  els.codexBin,
  els.codexModel,
  els.codexTimeout,
  els.verificationTimeout,
].forEach((el) => {
  el.addEventListener("input", () => {
    renderProviderStatus();
    updateCommandPreview();
  });
  el.addEventListener("change", () => {
    renderProviderStatus();
    updateCommandPreview();
  });
});
els.approvalButton.addEventListener("click", openApprovalDialog);
els.cancelApproval.addEventListener("click", () => els.approvalDialog.close());
els.approvalForm.addEventListener("submit", (event) => submitHumanDecision(event).catch((error) => {
  els.approvalDetails.textContent = error.message || String(error);
}));

Promise.all([loadConfigs(), loadRuntimeConfigs()]).catch((error) => {
  els.configPreview.textContent = error.message || String(error);
});
