const $ = id => document.getElementById(id);
const state = {token: '', host: null, selected: null, view: null, cases: [], projects: [], project: null, libraryOpen: false, tab: 'overview', busy: false, polling: false, verified: false, noticeKind: ''};
const storage = 'lqcd-workbench:';
const readable = value => String(value ?? '—').replaceAll('_', ' ');
const text = (id, value) => { $(id).textContent = value ?? '—'; };
const node = (tag, value, className) => { const e = document.createElement(tag); if (value !== undefined) e.textContent = value; if (className) e.className = className; return e; };
const notice = (message, kind = '') => { state.noticeKind = kind; text('notice', message); $('notice').hidden = !message; };
const runEndpoint = locator => '/api/runs/'+[locator.host, locator.run_locator.case_id, locator.run_locator.run_id].map(encodeURIComponent).join('/');
const projectEndpoint = id => '/api/projects/'+encodeURIComponent(id);
const endpoint = locator => locator.project_id && locator.project_run_key ? projectEndpoint(locator.project_id)+'/runs/'+encodeURIComponent(locator.project_run_key) : runEndpoint(locator);
const roleNames = {pi: 'PI', postdoc: 'Postdoc', reviewer: 'Independent Reviewer', method_planner: 'PI & Postdoc', code_agent: 'Code Researcher', analysis_engineer: 'Analysis Researcher', scientific_reviewer: 'Reviewer & PI', human_gate: 'Authorization', memory_report: 'Report'};

async function api(path, body) {
  const response = await fetch(path, {method: body === undefined ? 'GET' : 'POST', cache: 'no-store',
    headers: {'X-Workbench-Token': state.token, ...(body === undefined ? {} : {'Content-Type': 'application/json'})},
    ...(body === undefined ? {} : {body: JSON.stringify(body)})});
  const result = await response.json();
  if (!response.ok) { const error = new Error(result.detail || readable(result.error)); error.status = response.status; throw error; }
  return result;
}

async function select(locator) {
  state.libraryOpen = false; $('library-panel').hidden = true;
  if (locator.project_id) {
    if (state.project?.id !== locator.project_id) await loadProject(locator.project_id);
  } else {
    state.project = null; $('project-panel').hidden = true; $('participation').hidden = true;
    localStorage.removeItem(storage+'project');
  }
  $('project-panel').hidden = !state.project;
  state.selected = {host: locator.host, run_locator: locator.run_locator,
    ...(locator.project_id ? {project_id: locator.project_id, project_run_key: locator.project_run_key} : {})};
  localStorage.setItem(storage+'selected', JSON.stringify(state.selected));
  const url = new URL(location.href);
  for (const [name, value] of Object.entries({host: locator.host, case: locator.run_locator.case_id, run: locator.run_locator.run_id})) url.searchParams.set(name, value);
  if (locator.project_id) url.searchParams.set('project', locator.project_id); else url.searchParams.delete('project');
  if (locator.project_run_key) url.searchParams.set('project_run', locator.project_run_key); else url.searchParams.delete('project_run');
  history.replaceState(null, '', url);
  $('preview').hidden = true;
  state.view = null;
  state.verified = false;
  $('respond').disabled = true; $('cancel').disabled = true;
  $('investigation').hidden = true; $('empty').hidden = false;
  return refresh();
}

async function mutation(path, payload, target) {
  if (state.busy) return;
  if (localStorage.getItem(storage+'pending')) { await reconcile(); return; }
  state.busy = true;
  for (const id of ['start', 'project-start', 'project-continue', 'respond', 'cancel']) $(id).disabled = true;
  const pending = {path, payload: {...payload, key: crypto.randomUUID()}, target: target || {host: state.host}};
  localStorage.setItem(storage+'pending', JSON.stringify(pending));
  try {
    const result = await api(path, pending.payload);
    localStorage.removeItem(storage+'pending');
    notice(result.run_status === 'running' ? 'Control action committed. Subsequent work runs independently of this browser.' : 'Control action committed. Run is '+readable(result.run_status)+'.');
    await select({...pending.target, ...result});
  } catch (error) {
    if (error.status && error.status < 500) await reconcile();
    notice(error.status === 409 ? 'Action rejected: '+error.message+'. Refresh and inspect the current investigation before trying again.' :
      error.status ? error.message : 'Connection interrupted. Your operation key is retained; reconnect to reconcile the original submission.');
  } finally { state.busy = false; await refresh(); }
}

async function reconcile() {
  const raw = localStorage.getItem(storage+'pending');
  if (!raw) { $('pending-record').hidden = true; return; }
  const pending = JSON.parse(raw);
  if (pending.target.host !== state.host) {
    $('pending-record').hidden = false;
    notice('The saved submission belongs to an earlier research session. Its outcome has not been checked. Inspect the original investigation or forget only this browser record to start new work.');
    return;
  }
  $('pending-record').hidden = true;
  // Consult original authority before repeating the same retained business intent.
  try {
    try {
      const operation = await api('/api/operations/'+encodeURIComponent(pending.payload.key));
      if (operation.status === 'committed') {
        localStorage.removeItem(storage+'pending');
        await select({...pending.target, ...operation});
        notice('The original committed submission was recovered without creating another operation.');
        return;
      }
    } catch (error) { if (error.status !== 404) throw error; }
    const result = await api(pending.path, pending.payload);
    localStorage.removeItem(storage+'pending');
    await select({...pending.target, ...result});
    notice('The original submission was reconciled using its retained operation key.');
  } catch (error) {
    if (error.status && error.status < 500) localStorage.removeItem(storage+'pending');
    notice('Pending operation: '+error.message+'. No new decision was generated.');
  }
}

async function loadProject(identifier) {
  state.project = await api(projectEndpoint(identifier));
  localStorage.setItem(storage+'project', identifier);
  $('project-panel').hidden = false;
  text('project-title', state.project.title); text('project-goal', state.project.goal);
  text('project-revision', 'Project version '+state.project.revision+' · investigations retain their original version');
  $('edit-project-title').value = state.project.title; $('edit-project-goal').value = state.project.goal;
  $('edit-project-config').value = JSON.stringify(state.project.case_config, null, 2);
  $('edit-project-data').value = state.project.case_config?.raw_data_path || '';
  $('edit-project-source').value = state.project.case_config?.source_kind || '';
  $('edit-project-python').value = state.project.case_config?.generated_program?.python || '';
  $('project-live').checked = false;
  $('project-start').disabled = state.busy;
  text('project-readiness', 'A new investigation starts a new research budget. PI & Postdoc organize the question, inspect available inputs and prepare the analysis. Ready work proceeds automatically; use Continue research below to answer an existing preparation within its original budget.');
  await contributions(true);
}

async function chooseProject(identifier) {
  state.selected = null; state.view = null; state.libraryOpen = false;
  localStorage.removeItem(storage+'selected');
  $('library-panel').hidden = true; $('investigation').hidden = true; $('empty').hidden = true;
  $('gate').hidden = true; $('gate-empty').hidden = false; $('cancel-box').hidden = true;
  await loadProject(identifier);
  const url = new URL(location.href); ['host', 'case', 'run', 'project_run'].forEach(key => url.searchParams.delete(key));
  url.searchParams.set('project', identifier); history.replaceState(null, '', url);
  await refresh();
}

function projectList(projects) {
  text('project-count', projects.length);
  rows($('project-list'), projects.length ? projects.map(project => {
    const item = node('button', undefined, 'run-item'+(state.project?.id === project.id ? ' selected' : ''));
    item.append(node('strong', project.title), node('span', project.id+' · version '+project.revision));
    item.addEventListener('click', () => chooseProject(project.id).catch(error => notice(error.message)));
    return item;
  }) : [node('p', 'Create your first research project.', 'muted')]);
}

async function contributions(restore = false) {
  $('participation').hidden = !state.project || state.libraryOpen;
  if (!state.project || state.libraryOpen) return;
  const project = state.project;
  const entries = await api(projectEndpoint(project.id)+'/contributions');
  if (state.project !== project) return;
  rows($('contribution-list'), entries.map(entry => {
    const item = node('article', undefined, 'contribution');
    item.append(node('strong', readable(entry.kind)+' · '+readable(entry.author)),
      node('p', entry.body), node('small', 'Project version '+entry.project_revision+' · input '+entry.revision+
        (entry.run ? ' · Run '+entry.run.run_id.slice(-8) : ' · project-wide')),
      node('small', entry.evidence_sha256.length ? ' · evidence '+entry.evidence_sha256.join(', ') : ''));
    return item;
  }));
  const selected = state.selected?.project_id === project.id && state.verified;
  const clarification = selected && state.view.workflow === 'intake' && state.view.preparation?.status === 'needs_information';
  $('contribution-run-option').hidden = !selected || clarification;
  text('contribution-scope', selected && ['completed', 'halted', 'failed'].includes(state.view.run_status) ?
    'Attach to the selected closed investigation' : 'Limit to the selected investigation');
  if (!selected || clarification) $('contribution-run').checked = false;
  const pending = JSON.parse(localStorage.getItem(storage+'contribution') || 'null');
  $('forget-contribution').hidden = !pending;
  if (restore && pending?.project === project.id) {
    $('contribution-kind').value = pending.payload.kind;
    $('contribution-body').value = pending.payload.body;
    $('contribution-evidence').value = pending.payload.evidence_sha256.join('\n');
    $('contribution-run').checked = Boolean(pending.payload.run) && !clarification;
  }
}

async function searchLibrary() {
  const query = new URLSearchParams({query: $('library-query').value});
  if ($('library-kind').value) query.set('kind', $('library-kind').value);
  const entries = await api('/api/library?'+query);
  rows($('library-results'), entries.length ? entries.map(entry => {
    const item = node('button', undefined, 'evidence-item');
    item.append(node('strong', entry.title), node('small', readable(entry.kind)+' · '+readable(entry.status)));
    item.addEventListener('click', async () => {
      try {
        const asset = await api('/api/library/'+encodeURIComponent(entry.kind)+'/'+encodeURIComponent(entry.id));
        text('library-title', asset.title);
        rows($('library-content'), [summaryLine('REVIEW STATUS', readable(asset.status)+' · version '+asset.revision),
          summaryLine('APPLICABILITY', asset.scope), summaryLine('CONTENT', asset.body),
          summaryLine('SOURCES', asset.sources), summaryLine('DEPENDENCY CHANGES', asset.dependency_changes)]);
        $('library-entry').hidden = false;
      } catch (error) { notice(error.message); }
    });
    return item;
  }) : [node('p', 'No matching entries yet. This library accumulates your research knowledge, skills and tested methods.', 'muted')]);
}

function rows(container, values) {
  container.replaceChildren(...values);
}

function historyList(runs) {
  text('run-count', runs.length);
  rows($('run-list'), runs.length ? runs.map(run => {
    const item = node('button', undefined, 'run-item'+(state.selected?.run_locator.run_id === run.run_locator.run_id ? ' selected' : ''));
    item.append(node('strong', (run.workflow === 'intake' ? 'Preparation · ' : '')+run.run_locator.case_id), node('span', (run.inspection === 'unavailable' ? 'Verification pending' : run.preparation ? readable(run.preparation.status) : readable(run.run_status))+' · '+run.run_locator.run_id.slice(-8)));
    item.addEventListener('click', () => select(run).catch(error => notice(error.message)));
    return item;
  }) : [node('p', 'No investigations yet.', 'muted')]);
}

function evidenceList() {
  const files = state.view.evidence.filter(item => state.tab === 'evidence' || item.slot === state.tab);
  rows($('evidence-list'), files.length ? files.map(item => {
    const button = node('button', undefined, 'evidence-item');
    button.append(node('strong', item.name), node('small', item.source+' · '+(item.current ? 'current' : 'historical')+' ↗'));
    button.addEventListener('click', async () => {
      try {
        const locator = state.selected;
        const path = state.view.archived ? projectEndpoint(locator.project_id)+'/evidence/' : runEndpoint(locator)+'/evidence/';
        const content = await api(path+encodeURIComponent(item.id));
        if (state.selected !== locator) return;
        text('preview-name', content.name); text('preview-hash', 'SHA-256 '+content.sha256);
        let value = content.text;
        if (content.name.endsWith('.json')) value = JSON.stringify(JSON.parse(value), null, 2);
        text('preview-text', value); $('preview').hidden = false;
      } catch (error) { notice(error.message); }
    });
    return button;
  }) : [node('p', 'No registered evidence for this stage yet.', 'muted')]);
}

function summaryLine(label, value) {
  const line = node('div', undefined, 'summary-line');
  const describe = item => typeof item === 'string' ? item : JSON.stringify(item, null, 2);
  line.append(node('strong', label), node('p', Array.isArray(value) ? value.map(describe).join('\n') : describe(value)));
  return line;
}

function draftConfig(config, dataPath, python, sourceKind, replaceInputs = false) {
  if (config !== null && (typeof config !== 'object' || Array.isArray(config))) throw new Error('Case configuration must be an object or null.');
  const draft = {...config};
  if (dataPath) draft.raw_data_path = dataPath;
  else if (replaceInputs) delete draft.raw_data_path;
  if (sourceKind) draft.source_kind = sourceKind;
  else if (replaceInputs) delete draft.source_kind;
  if (python || replaceInputs) {
    const program = {...draft.generated_program};
    if (python) program.python = python; else delete program.python;
    if (Object.keys(program).length) draft.generated_program = program; else delete draft.generated_program;
  }
  return Object.keys(draft).length ? draft : null;
}

function svgElement(name, attrs, value) {
  const e = document.createElementNS('http://www.w3.org/2000/svg', name);
  for (const [key, val] of Object.entries(attrs)) e.setAttribute(key, val);
  if (value !== undefined) e.textContent = value;
  return e;
}

function plot(title, subtitle, points, columns, data) {
  const card = node('section', undefined, 'chart-card');
  card.append(node('h3', title), node('p', subtitle));
  const svg = svgElement('svg', {viewBox: '0 0 620 230', role: 'img', 'aria-label': title});
  const valid = points.filter(p => Number.isFinite(p.value) && Number.isFinite(p.error) && p.error >= 0);
  if (valid.length) {
    const low = Math.min(...valid.map(p => p.value-p.error)), high = Math.max(...valid.map(p => p.value+p.error));
    const span = high-low || Math.max(Math.abs(high)*.1, .001);
    const y = value => 178-(value-low+span*.15)/(span*1.3)*145;
    svg.append(svgElement('line', {x1: 65, x2: 605, y1: 185, y2: 185, class: 'axis'}));
    for (let i=0; i<4; i++) {
      const value = low+(high-low)*i/3;
      svg.append(svgElement('text', {x: 5, y: y(value)+4}, value.toPrecision(4)));
    }
    valid.forEach((point, i) => {
      const x = 95+i*Math.min(480/Math.max(valid.length-1, 1), 110);
      svg.append(svgElement('line', {x1: x, x2: x, y1: y(point.value-point.error), y2: y(point.value+point.error), class: 'errorbar'}),
        svgElement('circle', {cx: x, cy: y(point.value), r: 4, class: 'point'}),
        svgElement('text', {x, y: 207, 'text-anchor': 'middle'}, point.label));
    });
    card.append(svg);
  }
  const table = node('table'); const header = node('tr');
  columns.forEach(column => header.append(node('th', column.label))); table.append(header);
  data.forEach(row => { const tr = node('tr'); columns.forEach(c => tr.append(node('td', c.format ? c.format(row[c.key]) : row[c.key]))); table.append(tr); });
  card.append(table);
  return card;
}

function collaboration(view) {
  rows($('collaboration'), (view.collaboration || []).map(exchange => {
    const card = node('section', undefined, 'collaboration-card');
    const header = node('header');
    header.append(node('h3', exchange.slot === 'plan' ? 'PI & Postdoc research discussion' : 'Independent review & PI discussion'),
      node('small', exchange.current ? 'Current' : 'Earlier round', 'muted'));
    card.append(header, node('p', exchange.summary));
    for (const issue of exchange.issues || []) {
      const item = node('div', undefined, 'issue '+issue.status);
      item.append(node('strong', readable(issue.status)+' · '+issue.question));
      if (issue.response) item.append(node('p', issue.response));
      if (issue.evidence_references?.length) item.append(node('small', 'Evidence: '+issue.evidence_references.join(', ')));
      card.append(item);
    }
    if (exchange.challenges?.length) card.append(summaryLine('QUESTIONS TO RESOLVE', exchange.challenges));
    for (const role of exchange.exchanges || []) {
      const details = node('details'); details.append(node('summary', roleNames[role.role] || readable(role.role)));
      const discussion = role.discussion || role.brief?.discussion;
      if (discussion?.summary) details.append(node('p', discussion.summary));
      if (role.brief?.physics_question) details.append(summaryLine('PHYSICS QUESTION', role.brief.physics_question));
      if (role.brief?.discriminating_checks) details.append(summaryLine('DISCRIMINATING CHECKS', role.brief.discriminating_checks));
      if (role.proposal?.summary) details.append(node('p', role.proposal.summary));
      card.append(details);
    }
    return card;
  }));
}

function summaries(view) {
  const values = [];
  for (const [name, value] of Object.entries(view.summaries)) {
    if (value.summary) values.push(summaryLine(name.includes('review') ? 'INDEPENDENT SCIENTIFIC REVIEW' : name.includes('plan') ? 'RESEARCH PLAN' : 'ANALYSIS SUMMARY', value.summary));
    if (value.method_steps?.length) values.push(summaryLine('METHOD', value.method_steps));
    if (value.warnings?.length) values.push(summaryLine('LIMITATIONS & WARNINGS', value.warnings));
    if (value.findings?.length) values.push(summaryLine('FINDINGS', value.findings));
  }
  rows($('summary'), values.length ? values : [node('p', 'Verified scientific summaries will appear as artifacts are committed.', 'muted')]);
  if (view.execution_failure) $('summary').append(node('p', view.execution_failure.summary+' · '+view.execution_failure.source, 'muted'));
  const result = view.summaries['generated_result.json'];
  const charts = [];
  if (result?.fits) {
    for (const nstates of [...new Set(result.fits.map(f => f.nstates))]) {
      const fits = result.fits.filter(f => f.nstates === nstates);
      charts.push(plot(nstates+'-state energy estimates', 'Stored E₀ ± bootstrap uncertainty by fit window. '+(result.ground_energy_fixed ? 'Ground energy is fixed; this is not an independent dispersion test.' : 'Numerical success is not scientific acceptance.'),
        fits.map(f => ({value: f.E0, error: f.E0_error, label: f.tmin+'–'+f.tmax})),
        [{key: 'tmin', label: 't min'}, {key: 'tmax', label: 't max'}, {key: 'E0', label: 'E₀'}, {key: 'E0_error', label: 'σ(E₀)'}, {key: 'chi2_dof', label: 'χ²/dof'}, {key: 'bootstrap_successes', label: 'Valid replicas'}, {key: 'bootstrap_total', label: 'Total'}], fits));
    }
  }
  if (result?.summaries) {
      const items = result.summaries;
    for (const component of ['real', 'imag']) {
      const selected = items.filter(s => s.component === component);
      charts.push(plot('Normalization · '+component, 'Stored complex-component estimates and uncertainties; original paired replicas remain authoritative.',
        selected.map(s => ({value: s.mean, error: s.error, label: s.mode+' / '+s.bz})),
        [{key: 'mode', label: 'Mode'}, {key: 'bz', label: 'bᶻ'}, {key: 'mean', label: 'Estimate'}, {key: 'error', label: 'Uncertainty'}, {key: 'n_valid', label: 'Valid samples'}], selected));
    }
  }
  rows($('charts'), charts);
}

function render(view) {
  const changed = state.view?.active_pause?.pause_id !== view.active_pause?.pause_id;
  state.view = view;
  state.verified = true;
  const closed = ['completed', 'halted', 'failed'].includes(view.run_status);
  if (state.noticeKind === 'verification') notice('');
  $('empty').hidden = true; $('investigation').hidden = false;
  const intake = view.workflow === 'intake';
  text('run-mode', intake ? (view.live ? 'PI & POSTDOC · RESEARCH PREPARATION' : 'OFFLINE PREPARATION · ENGINEERING EXERCISE') : view.live ? 'LIVE LLM RESEARCH'+(view.coding ? ' · CODEX' : '') : view.synthetic ? 'OFFLINE SYNTHETIC · ENGINEERING EXERCISE' : 'OFFLINE PLANNER & REVIEWER · SCIENTIFIC PROGRAM');
  text('run-title', view.run_locator.case_id); text('run-goal', view.goal); text('run-state', readable(view.run_status));
  text('acceptance', intake ? (view.preparation ? readable(view.preparation.status) : 'Preparing research') : view.scientific_outcome ? readable(view.scientific_outcome)+' · '+readable(view.decision_origin)+' conclusion' : closed ? 'No recorded research outcome' : 'Research in progress');
  text('activity', view.archived ? 'Saved project evidence' : intake && closed && view.preparation ? (view.preparation.status === 'ready' ? 'Preparation complete · inspect subsequent investigations' : 'Preparation complete · information needed') : closed ? 'Run closed · '+readable(view.run_status) : view.active_pause?.reason === 'human_input' ? 'Waiting for extra authorization' : readable(view.attempts.at(-1)?.kind));
  $('preparation-panel').hidden = !intake;
  if (intake) {
    const prepared = view.preparation;
    text('preparation-title', prepared?.status === 'ready' ? 'Ready for analysis' : prepared?.status === 'needs_information' ? 'Information needed' : 'Organizing the research');
    text('preparation-summary', prepared?.summary || 'PI & Postdoc are reviewing the research question and available inputs.');
    rows($('preparation-questions'), prepared?.questions?.length ? [summaryLine('QUESTIONS', prepared.questions)] : []);
    rows($('preparation-assumptions'), prepared?.assumptions?.length ? [summaryLine('ASSUMPTIONS & SCOPE', prepared.assumptions)] : []);
    $('prepared-config-details').hidden = !prepared?.case_config;
    text('prepared-config', prepared?.case_config ? JSON.stringify(prepared.case_config, null, 2) : '');
    $('preparation-continue').hidden = !(closed && prepared?.status === 'needs_information' && state.project?.id === state.selected?.project_id);
    $('project-continue').disabled = state.busy || view.archived || !view.compatible || !view.managed;
  }
  text('head', view.execution_head.slice(0, 14)+'…');
  text('run-identity', view.host+' / '+view.run_locator.run_id); text('refreshed', 'Verified '+new Date().toLocaleTimeString());
  $('compatibility').hidden = view.compatible && !view.needs_recovery && view.managed;
  text('compatibility', view.archived ? 'Saved project evidence. The original execution directory is no longer available; this record cannot resume work or accept decisions. Start a new investigation from the project to continue.' : !view.compatible ? 'Historical runtime build. Evidence remains inspectable; new work requires its original supported build. No migration or replay is performed.' : !view.managed ? 'Imported Run: read-only evidence. Use the original CLI for its control actions.' : 'An invocation started without a committed completion. Inspect its original recovery state; the workbench will not repeat uncertain work.');
  const roles = ['method_planner', ...(intake ? [] : ['code_agent', 'analysis_engineer', 'scientific_reviewer']),
    ...(view.attempts.some(a => a.kind === 'human_gate') ? ['human_gate'] : []), 'memory_report'];
  rows($('timeline'), roles.map(kind => {
    const attempt = view.attempts.filter(a => a.kind === kind).at(-1);
    const success = attempt?.status === 'succeeded', failure = attempt?.status === 'failed';
    const waiting = kind === 'human_gate' && view.active_pause?.reason === 'human_input';
    const active = !closed && attempt && (waiting || ['running', 'scheduled'].includes(attempt.status));
    const item = node('li', roleNames[kind] || readable(kind), failure ? 'failed' : active ? 'active' : success ? 'done' : '');
    item.append(node('small', attempt ? readable(attempt.status)+(closed && !success && !failure ? ' at closure' : '') : 'Not reached')); return item;
  }));
  text('progress-label', view.attempts.length+' recorded attempts');
  const job = view.coding_backend;
  $('backend-progress').hidden = !job;
  if (job) text('backend-progress', 'Codex: '+readable(job.status)+' · '+(job.tool_count ?? '—')+' observed tool calls · original timeout and budget apply');
  const budget = Object.entries(view.budget.dimensions).filter(([name]) => ['active_seconds_per_run','llm_calls_per_run','tool_calls_per_run','transitions_per_run'].includes(name)).map(([name, value]) => {
    const item = node('div'); item.append(node('span', 'Run · '+readable(name)), node('strong', value.used+' used · '+value.remaining+' remaining')); return item;
  });
  if (view.research_task) {
    const quota = view.research_task;
    for (const [label, remaining, limit] of [['model calls', quota.remaining_model_calls, quota.limits.model_calls],
      ['tokens', quota.remaining_tokens, quota.limits.tokens], ['Runs', quota.remaining_runs, quota.limits.runs]]) {
      const item = node('div'); item.append(node('span', 'Shared research task · '+label), node('strong', remaining+' remaining / '+limit)); budget.unshift(item);
    }
    if (quota.unknown_requests) budget.push(summaryLine('Reserved usage', quota.unknown_requests+' model requests retain conservative usage reservations.'));
    const unexecuted = Object.values(quota.unexecuted_experiments);
    if (unexecuted.length) budget.push(summaryLine('Additional checks not executed', unexecuted.map(item => item.parent.run_id+': '+readable(item.reason))));
  }
  rows($('budget'), budget);
  const request = view.human_request;
  $('gate').hidden = !request; $('gate-empty').hidden = Boolean(request); $('cancel-box').hidden = !view.actions.cancel;
  if (request) {
    text('gate-kind', readable(request.request_kind));
    text('gate-prompt', request.prompt ?? request.summary ?? 'Inspect the requested action and its exact authorization scope.');
    if (changed) {
      $('response-form').reset();
      rows($('decision'), [node('option', 'Choose explicitly…'), ...request.authorization_scope.allowed_decisions.map(decision => {
        const option = node('option', readable(decision)); option.value = decision; return option;
      })]); $('decision').options[0].value = '';
    }
  }
  $('respond').disabled = state.busy || !view.actions.respond;
  $('cancel').disabled = state.busy || !view.actions.cancel;
  $('start').disabled = state.busy;
  $('project-start').disabled = state.busy || !state.project;
  collaboration(view); summaries(view); evidenceList();
}

async function refresh() {
  if (state.polling) return;
  state.polling = true;
  try {
    state.projects = await api('/api/projects'); projectList(state.projects);
    const runs = await api(state.project ? projectEndpoint(state.project.id)+'/runs' : '/api/runs'); historyList(runs);
    text('history-title', state.project ? 'Project investigations' : 'Investigations');
    const selected = state.selected;
    if (selected && !state.libraryOpen) { const view = await api(endpoint(selected)); if (selected === state.selected) render(view); }
    $('project-start').disabled = state.busy || !state.project;
    await contributions();
    text('connection', 'Connected · local control'); $('connection').classList.remove('offline');
  } catch (error) {
    state.verified = false; $('respond').disabled = true; $('cancel').disabled = true; $('project-continue').disabled = true;
    text('connection', error.status === 409 ? 'Connected · checkpoint verification pending' : 'Disconnected · reconnecting'); $('connection').classList.add('offline');
    if (error.status === 403) await session();
    else if (error.status === 409) notice('Waiting for a fully verified checkpoint. The last verified snapshot is retained for inspection; actions are disabled. If the worker stopped, inspect original control recovery.', 'verification');
    else if (error.status) notice(error.message);
  } finally { state.polling = false; }
}

async function session() { const value = await api('/api/session'); state.token = value.token; state.host = value.host; }
$('forget-pending').addEventListener('click', () => {
  if (state.busy) return;
  localStorage.removeItem(storage+'pending');
  $('pending-record').hidden = true;
  notice('This browser record was forgotten. No investigation, decision or history was changed.');
});
$('forget-contribution').addEventListener('click', () => {
  localStorage.removeItem(storage+'contribution');
  $('forget-contribution').hidden = true;
  notice('Unconfirmed browser form forgotten. Existing scientific input remains recorded.');
});
$('contribution-form').addEventListener('submit', async event => {
  event.preventDefault(); if (!state.project) return;
  const selected = state.selected?.project_id === state.project.id && state.verified;
  const run = $('contribution-run').checked && selected ? {host: state.view.host,
    ...state.view.run_locator, execution_head: state.view.execution_head} : null;
  const payload = {expected_digest: state.project.sha256, kind: $('contribution-kind').value,
    body: $('contribution-body').value, evidence_sha256: $('contribution-evidence').value.split('\n').map(s => s.trim()).filter(Boolean), run};
  let pending = JSON.parse(localStorage.getItem(storage+'contribution') || 'null');
  if (pending && (pending.project !== state.project.id || Boolean(pending.payload.run) !== Boolean(run) ||
      run && pending.payload.run && ['host', 'case_id', 'run_id'].some(k => pending.payload.run[k] !== run[k]) || ['kind', 'body', 'evidence_sha256'].some(k => JSON.stringify(pending.payload[k]) !== JSON.stringify(payload[k])))) {
    notice('An unconfirmed scientific input is retained. Restore its Project to retry, or forget its browser form before submitting a new input.'); return;
  }
  if (!pending) {
    pending = {project: state.project.id, payload: {...payload, key: crypto.randomUUID()}};
    localStorage.setItem(storage+'contribution', JSON.stringify(pending));
  }
  $('contribution-save').disabled = true;
  try {
    await api(projectEndpoint(pending.project)+'/contributions', pending.payload);
    localStorage.removeItem(storage+'contribution'); $('contribution-form').reset();
    notice(state.view?.preparation?.status === 'needs_information' ?
      'Reply recorded. Continue research when ready; it uses the original remaining budget and deadline.' :
      'Scientific input recorded for the next research checkpoint. It does not grant additional authority.');
    await contributions();
  } catch (error) {
    if (error.status && error.status < 500) localStorage.removeItem(storage+'contribution');
    notice(error.status === 409 ? 'The Project or Run changed. Refresh before submitting again.' : error.message);
    $('forget-contribution').hidden = !localStorage.getItem(storage+'contribution');
  } finally { $('contribution-save').disabled = false; }
});
$('project-create-form').addEventListener('submit', async event => {
  event.preventDefault(); $('project-create').disabled = true;
  try {
    const config = draftConfig($('project-case').value ? await api('/api/cases/'+encodeURIComponent($('project-case').value)) : null,
      $('project-data-input').value.trim(), $('project-python-input').value.trim(), $('project-source-input').value.trim());
    const project = await api('/api/projects', {id: $('project-id').value, title: $('project-title-input').value,
      goal: $('project-goal-input').value, case_config: config});
    $('project-create-form').reset(); await chooseProject(project.id); notice('Project created. Its knowledge and results will accumulate in this repository.');
  } catch (error) { notice(error.message); } finally { $('project-create').disabled = false; }
});
$('project-edit-form').addEventListener('submit', async event => {
  event.preventDefault(); if (!state.project) return; $('project-save').disabled = true;
  try {
    const project = await api(projectEndpoint(state.project.id), {expected_digest: state.project.sha256,
      title: $('edit-project-title').value, goal: $('edit-project-goal').value,
      case_config: draftConfig(JSON.parse($('edit-project-config').value || 'null'),
        $('edit-project-data').value.trim(), $('edit-project-python').value.trim(), $('edit-project-source').value.trim(), true)});
    await loadProject(project.id); notice('Project version saved. Existing investigations retain their original inputs.');
  } catch (error) { notice(error.status === 409 ? 'Project changed. Refresh the project before saving your edits again.' : error.message); }
  finally { $('project-save').disabled = false; }
});
$('edit-project-config').addEventListener('input', () => {
  try {
    const draft = JSON.parse($('edit-project-config').value || 'null');
    $('edit-project-data').value = draft?.raw_data_path || '';
    $('edit-project-source').value = draft?.source_kind || '';
    $('edit-project-python').value = draft?.generated_program?.python || '';
  } catch { /* Preserve partially typed JSON until the user completes the edit. */ }
});
$('project-start').addEventListener('click', () => {
  if (!state.project) return;
  if (!$('project-live').checked) { notice('Select Use live research agents to start PI/Postdoc preparation and the subsequent authorized analysis.'); return; }
  mutation(projectEndpoint(state.project.id)+'/runs', {expected_digest: state.project.sha256, live: $('project-live').checked}, {host: state.host, project_id: state.project.id});
});
$('project-continue').addEventListener('click', () => {
  const view = state.view;
  if (!state.project || !state.verified || view?.preparation?.status !== 'needs_information' ||
      view.archived || !view.compatible || !view.managed || state.selected?.project_id !== state.project.id) return;
  mutation(projectEndpoint(state.project.id)+'/runs', {expected_digest: state.project.sha256, live: view.live,
    intake_parent: view.run_locator.run_id, case: view.run_locator.case_id},
    {host: view.host, project_id: state.project.id});
});
$('refresh-project').addEventListener('click', () => { if (state.project) loadProject(state.project.id).catch(error => notice(error.message)); });
$('open-library').addEventListener('click', () => {
  state.libraryOpen = true; $('library-panel').hidden = false; $('project-panel').hidden = true; $('participation').hidden = true;
  $('investigation').hidden = true; $('empty').hidden = true; $('gate').hidden = true; $('gate-empty').hidden = false; $('cancel-box').hidden = true;
  searchLibrary().catch(error => notice(error.message));
});
$('library-search-form').addEventListener('submit', event => { event.preventDefault(); searchLibrary().catch(error => notice(error.message)); });
$('case').addEventListener('change', () => {
  const entry = state.cases.find(c => c.id === $('case').value);
  if (entry) { $('goal').value = entry.goal; $('live').checked = false; }
});
$('start-form').addEventListener('submit', event => {
  event.preventDefault(); const entry = state.cases.find(c => c.id === $('case').value);
  if (entry?.requires_live && !$('live').checked) { notice('This case requires explicit live LLM and Codex activation.'); return; }
  mutation('/api/runs', {case: $('case').value, goal: $('goal').value, live: $('live').checked}, null);
});
$('open-form').addEventListener('submit', event => {
  event.preventDefault(); try { const value = JSON.parse($('locator').value); if (!value.host || !value.run_locator?.case_id || !value.run_locator?.run_id) throw new Error('Paste the complete CLI status JSON.'); select(value); } catch (error) { notice(error.message); }
});
$('response-form').addEventListener('submit', event => {
  event.preventDefault(); if (!state.verified) return; const view = state.view;
  mutation(runEndpoint(state.selected)+'/respond', {pause: view.active_pause.pause_id, head: view.execution_head,
    decision: $('decision').value, conditions: $('conditions').value.split('\n').map(s => s.trim()).filter(Boolean), reason: $('reason').value}, state.selected);
});
$('cancel').addEventListener('click', () => {
  if (!state.verified) return;
  const view = state.view;
  mutation(runEndpoint(state.selected)+'/cancel', {pause: view.active_pause.pause_id, head: view.execution_head}, state.selected);
});
$('close-preview').addEventListener('click', () => { $('preview').hidden = true; });
$('tabs').addEventListener('click', event => {
  const tab = event.target.dataset.tab; if (!tab) return; state.tab = tab;
  for (const button of $('tabs').children) button.classList.toggle('active', button.dataset.tab === tab);
  $('overview').hidden = tab !== 'overview'; $('evidence-pane').hidden = tab === 'overview'; $('preview').hidden = true;
  if (state.view) evidenceList();
});
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
async function init() {
  await session(); state.cases = await api('/api/cases');
  for (const entry of state.cases) { for (const selector of ['case', 'project-case']) { const option = node('option', entry.case_id+(entry.requires_live ? ' · Codex' : '')); option.value = entry.id; $(selector).append(option); } }
  const url = new URL(location.href), params = url.searchParams;
  if (params.has('host') && params.has('case') && params.has('run')) state.selected = {host: params.get('host'), run_locator: {case_id: params.get('case'), run_id: params.get('run')}};
  else if (localStorage.getItem(storage+'selected')) state.selected = JSON.parse(localStorage.getItem(storage+'selected'));
  const project = params.get('project') || state.selected?.project_id || localStorage.getItem(storage+'project');
  if (project) {
    await loadProject(project);
    if (state.selected && !state.selected.project_run_key) {
      const runs = await api(projectEndpoint(project)+'/runs');
      const saved = runs.find(run => run.host === state.selected.host && run.run_locator.case_id === state.selected.run_locator.case_id && run.run_locator.run_id === state.selected.run_locator.run_id);
      if (saved) state.selected = {host: saved.host, run_locator: saved.run_locator, project_id: project, project_run_key: saved.project_run_key};
    }
  }
  await reconcile(); await refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, 2000);
}
init().catch(error => notice('Unable to connect: '+error.message+'. Reload after the local server is available.'));
