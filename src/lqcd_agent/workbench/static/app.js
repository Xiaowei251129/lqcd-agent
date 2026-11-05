import {renderTaskList, renderTaskDesk} from './task-desk.js';
import {submissionSlot, sendControl, sendContribution} from './submissions.js';
import {renderResults} from './results.js';
import {renderComparison} from './comparison.js';
import {referencedMember, summaryMember, evidenceButton, evidenceReader} from './evidence.js';

const $ = id => document.getElementById(id);
const state = {token: '', host: null, selected: null, view: null, cases: [], projects: [], project: null, runs: [], libraryOpen: false, tab: 'overview', busy: false, verified: false, noticeKind: ''};
const storage = 'lqcd-workbench:';
const controlSlot = submissionSlot(storage+'pending');
const inputSlot = submissionSlot(storage+'contribution');
const readable = value => String(value ?? '—').replaceAll('_', ' ');
const text = (id, value) => { $(id).textContent = value ?? '—'; };
const node = (tag, value, className) => { const e = document.createElement(tag); if (value !== undefined) e.textContent = value; if (className) e.className = className; return e; };
const notice = (message, kind = '') => { state.noticeKind = kind; text('notice', message); $('notice').hidden = !message; };
const runEndpoint = locator => '/api/runs/'+[locator.host, locator.run_locator.case_id, locator.run_locator.run_id].map(encodeURIComponent).join('/');
const projectEndpoint = id => '/api/projects/'+encodeURIComponent(id);
const endpoint = locator => locator.project_id && locator.project_run_key ? projectEndpoint(locator.project_id)+'/runs/'+encodeURIComponent(locator.project_run_key) : runEndpoint(locator);
const roleNames = {pi: 'PI', postdoc: 'Postdoc', reviewer: 'Independent Reviewer', method_planner: 'PI & Postdoc', code_agent: 'Code Researcher', analysis_engineer: 'Analysis Researcher', scientific_reviewer: 'Reviewer & PI', human_gate: 'Authorization', memory_report: 'Report'};
const revisions = new Map();
const drafts = new Map();
let draftKey, navigation = 0, refreshing = false, refreshAgain = false;
const reader = evidenceReader({
  getView: () => ({view: state.view, locator: state.selected, verified: state.verified}),
  load: (view, locator, item) => api((view.archived ? projectEndpoint(locator.project_id) : runEndpoint(locator))+'/evidence/'+encodeURIComponent(item.id)),
  loadSaved: (project, hash) => api(projectEndpoint(project)+'/evidence/'+encodeURIComponent(hash)),
  attach: attachEvidence, onError: notice,
});

function changed(section, value) {
  const key = JSON.stringify(value);
  if (revisions.get(section) === key) return false;
  revisions.set(section, key);
  return true;
}

const openRun = run => select(run).catch(error => notice(error.message));
const loadRun = run => api(endpoint(run));

async function api(path, body) {
  let response;
  try {
    response = await fetch(path, {method: body === undefined ? 'GET' : 'POST', cache: 'no-store',
      headers: {'X-Workbench-Token': state.token, ...(body === undefined ? {} : {'Content-Type': 'application/json'})},
      ...(body === undefined ? {} : {body: JSON.stringify(body)})});
  } catch (cause) { const error = new Error('Local workbench connection unavailable.', {cause}); error.network = true; throw error; }
  const result = await response.json();
  if (!response.ok) { const error = new Error(result.detail || readable(result.error)); error.status = response.status; error.code = result.error; throw error; }
  return result;
}

async function select(locator) {
  const version = ++navigation;
  leaveRun();
  state.libraryOpen = false; $('library-panel').hidden = true;
  if (locator.project_id) {
    if (state.project?.id !== locator.project_id) {
      state.project = null; $('project-panel').hidden = true;
      await loadProject(locator.project_id, version);
    }
    if (version !== navigation) return;
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
  switchDraft();
  return refresh();
}

function leaveRun() {
  reader.close(false);
  state.selected = null; state.view = null; state.verified = false;
  revisions.clear(); state.tab = 'overview'; showTab('overview');
  $('respond').disabled = true; $('cancel').disabled = true; $('project-continue').disabled = true;
  $('gate').hidden = true; $('cancel-box').hidden = true; $('comparison').hidden = true; $('empty').hidden = true;
  $('participation').hidden = true; $('contribution-list').replaceChildren();
  $('investigation').hidden = true;
  renderTaskDesk(null, [], state.project, openRun);
}

function forgetControlOption(record) {
  $('pending-record').hidden = !record;
  $('forget-pending').dataset.key = record?.payload.key || '';
}

function forgetInputOption(record) {
  $('forget-contribution').hidden = !record;
  $('forget-contribution').dataset.key = record?.payload.key || '';
}

async function finishControl(pending, replay, version) {
  const sameHost = () => pending.target.host === state.host;
  if (!sameHost()) {
    forgetControlOption(pending);
    notice('The saved submission belongs to an earlier Host. Inspect the original investigation or forget the saved browser record.');
    return;
  }
  let result;
  try {
    result = await sendControl(controlSlot, pending, replay, (path, body) => {
      if (!sameHost()) throw new Error('The original Host changed during reconciliation.');
      return api(path, body);
    });
  } catch (error) {
    const saved = controlSlot.read();
    forgetControlOption(saved);
    notice(saved?.payload.key === pending.payload.key ?
      'Original submission retained. Reconnect and retry to check its outcome. '+error.message :
      'Control action rejected. '+error.message);
    return;
  }
  forgetControlOption(controlSlot.read());
  if (result && version === navigation) {
    notice(replay ? 'The original submission was reconciled using its retained key.' : 'Control action committed.');
    try { await select({...pending.target, ...result}); }
    catch (error) { notice('The action was committed. Opening the Run failed. '+error.message); }
  }
}

async function mutation(path, payload, target) {
  if (state.busy) return;
  const version = navigation;
  state.busy = true;
  for (const id of ['start','project-start','project-continue','respond','cancel']) $(id).disabled = true;
  try {
    const {record, replay} = await controlSlot.claim({path, payload: {...payload, key: crypto.randomUUID()},
      target: target || {host: state.host}});
    await finishControl(record, replay, version);
  } catch (error) { notice(error.message); }
  finally { state.busy = false; await refresh(); }
}

async function reconcile() {
  const record = controlSlot.read();
  if (record) await finishControl(record, true, navigation);
  else forgetControlOption(null);
}

async function loadProject(identifier, version = navigation) {
  const project = await api(projectEndpoint(identifier));
  if (version !== navigation) return;
  state.project = project;
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
}

async function chooseProject(identifier) {
  const version = ++navigation;
  leaveRun(); state.libraryOpen = false;
  localStorage.removeItem(storage+'selected');
  $('library-panel').hidden = true; $('investigation').hidden = true; $('empty').hidden = true;
  $('gate').hidden = true; $('cancel-box').hidden = true;
  state.project = null; $('project-panel').hidden = true;
  await loadProject(identifier, version);
  if (version !== navigation) return;
  switchDraft();
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

async function contributions() {
  if (!state.project || state.libraryOpen) { $('participation').hidden = true; return; }
  const project = state.project;
  const entries = await api(projectEndpoint(project.id)+'/contributions');
  if (state.project !== project || state.libraryOpen) return;
  $('participation').hidden = false;
  if (changed('contributions', [project.id, entries.at(-1)?.sha256])) rows($('contribution-list'), entries.map(entry => {
    const item = node('article', undefined, 'contribution');
    item.append(node('strong', readable(entry.kind)+' · '+readable(entry.author)),
      node('p', entry.body), node('small', 'Project version '+entry.project_revision+' · input '+entry.revision+
        (entry.run ? ' · Run '+entry.run.run_id.slice(-8) : ' · project-wide')));
    for (const hash of entry.evidence_sha256) item.append(evidenceButton('Open cited evidence · '+hash.slice(0,10),
      () => reader.openSaved(project.id, hash, 'Evidence cited by input '+entry.revision)));
    return item;
  }));
  const selected = state.selected?.project_id === project.id && state.verified;
  const clarification = selected && state.view.workflow === 'intake' && state.view.preparation?.status === 'needs_information';
  $('contribution-run-option').hidden = !selected || clarification;
  text('contribution-scope', selected && ['completed', 'halted', 'failed'].includes(state.view.run_status) ?
    'Attach to the selected closed investigation' : 'Limit to the selected investigation');
  if (!state.selected || clarification) $('contribution-run').checked = false;
  forgetInputOption(inputSlot.read());

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

function evidenceList() {
  const files = state.view.evidence.filter(item => state.tab === 'evidence' || item.slot === state.tab);
  rows($('evidence-list'), files.length ? files.map(item => {
    const trial = item.slot === 'code' && item.name.split('/').at(-1) === 'numerical_trials.json';
    const button = evidenceButton(trial ? 'Development trials · '+item.name : item.name, () => reader.open(item));
    button.className = 'evidence-item';
    button.append(node('small', item.source+' · '+(item.current ? 'current' : 'historical')+' ↗'));
    return button;
  }) : [node('p', 'No registered evidence for this stage yet.', 'muted')]);
}

function selectedEvidence() {
  return Array.from($('contribution-evidence').selectedOptions, option => option.value);
}

function attachmentPicker(selected = selectedEvidence()) {
  const items = new Map();
  for (const item of state.view?.evidence || []) items.set(item.sha256, item.name);
  for (const hash of selected) if (!items.has(hash)) items.set(hash, 'Retained attachment');
  rows($('contribution-evidence'), Array.from(items, ([hash, label]) => {
    const option = node('option', label+' · '+hash.slice(0, 10));
    option.value = hash; option.selected = selected.includes(hash); return option;
  }));
  attachmentSummary();
}

function attachmentSummary() {
  text('selected-evidence', Array.from($('contribution-evidence').selectedOptions, o => o.textContent).join(' · '));
}

function switchDraft() {
  const key = JSON.stringify([state.project?.id, state.selected?.host, state.selected?.run_locator]);
  if (draftKey === key) return;
  if (draftKey) drafts.set(draftKey, {body: $('contribution-body').value, kind: $('contribution-kind').value,
    evidence_sha256: selectedEvidence(), scoped: $('contribution-run').checked});
  draftKey = key;
  const pending = inputSlot.read();
  const run = pending?.payload.run;
  const restore = pending && pending.project === state.project?.id && (!run ||
    (run.host === state.selected?.host && run.run_id === state.selected?.run_locator.run_id && run.case_id === state.selected?.run_locator.case_id));
  const draft = restore ? {...pending.payload, scoped: Boolean(run)} : drafts.get(key);
  $('contribution-form').reset();
  $('contribution-body').value = draft?.body || '';
  $('contribution-kind').value = draft?.kind || 'question';
  $('contribution-run').checked = Boolean(draft?.scoped);
  attachmentPicker(draft?.evidence_sha256 || []);
}

function attachEvidence(item, context) {
  if (!state.verified || !state.project || state.project.id !== state.selected?.project_id ||
      !state.view.evidence.some(row => row.id === item.id && row.sha256 === item.sha256)) return;
  if (inputSlot.read()) { notice('Reconcile the unconfirmed scientific input before attaching more evidence.'); return; }
  reader.close(false);
  attachmentPicker([...new Set([...selectedEvidence(), item.sha256])]);
  const body = $('contribution-body');
  if (context && !body.value.split('\n').includes(context)) body.value = [body.value, context].filter(Boolean).join('\n');
  $('contribution-run').checked = state.view.preparation?.status !== 'needs_information';
  $('participation').open = true;
  body.focus();
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

function collaboration(view) {
  rows($('collaboration'), (view.collaboration || []).filter(exchange => exchange.slot === state.tab).map(exchange => {
    const filename = exchange.slot === 'plan' ? 'method_plan.json' : 'scientific_review_report.json';
    const sourceReport = view.evidence.find(e => e.source === 'artifact' && e.artifact_id === exchange.artifact_id &&
      e.slot === exchange.slot && e.name.split('/').at(-1) === filename);
    const card = node('section', undefined, 'collaboration-card');
    const header = node('header');
    header.append(node('h3', exchange.slot === 'plan' ? 'PI & Postdoc research discussion' : 'Independent review & PI discussion'),
      node('small', exchange.current ? 'Current' : 'Earlier round', 'muted'));
    card.append(header, node('p', exchange.summary));
    for (const issue of exchange.issues || []) {
      const item = node('div', undefined, 'issue '+issue.status);
      item.append(node('strong', readable(issue.status)+' · '+issue.question));
      if (issue.response) item.append(node('p', issue.response));
      for (const ref of issue.evidence_references || []) {
        const source = referencedMember(view, ref);
        item.append(source ? evidenceButton('Inspect '+source.name, () => reader.open(source, issue.question)) :
          node('small', 'Research reference · '+ref, 'unresolved-reference'));
      }
      if (sourceReport && view.project_id && view.project_id === state.selected?.project_id) {
        item.append(evidenceButton('Discuss this question', () => attachEvidence(sourceReport, issue.question)));
      }
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
    for (const warning of value.warnings || []) {
      const message = typeof warning === 'string' ? warning : warning.message || warning.code;
      const line = summaryLine('Scientific limitation', message);
      const source = summaryMember(view, name);
      if (source) line.append(evidenceButton('Inspect '+source.name.split('/').at(-1), () => reader.open(source, message)));
      values.push(line);
    }
    if (value.findings?.length) values.push(summaryLine('FINDINGS', value.findings));
  }
  const empty = view.workflow === 'intake' ? 'Open Plan to inspect the preparation record.' :
    ['completed','failed','halted'].includes(view.run_status) ? 'No scientific summary was registered at this checkpoint.' :
      'Scientific summaries appear when the Host registers them.';
  rows($('summary'), values.length ? values : [node('p', empty, 'muted')]);
  if (view.execution_failure) $('summary').append(node('p', view.execution_failure.summary+' · '+view.execution_failure.source, 'muted'));
  renderResults($('charts'), view, {openEvidence: reader.open,
    contribute: view.project_id && state.selected?.project_id === view.project_id ? attachEvidence : null});

}

function render(view, detailChanged) {
  const newPause = state.view?.active_pause?.pause_id !== view.active_pause?.pause_id;
  state.view = view;
  state.verified = view.inspection === 'verified';
  const closed = ['completed', 'halted', 'failed'].includes(view.run_status);
  if (state.noticeKind === 'verification') notice('');
  $('empty').hidden = true; $('investigation').hidden = false;
  const intake = view.workflow === 'intake';
  if (changed('desk', [view.detail_revision, view.run_status, view.next_action, view.attempts.at(-1)?.kind, view.active_pause?.pause_id,
    state.project?.sha256, state.runs.map(r => [r.project_run_key, r.execution_head])])) {
    renderTaskDesk(view, state.runs, state.project, openRun);
  }
  $('project-continue').disabled = state.busy || !state.verified || view.archived || !view.compatible || !view.managed;
  text('head', view.execution_head.slice(0, 14)+'…');
  text('run-identity', view.host+' / '+view.run_locator.run_id); text('refreshed', 'Checkpoint checked '+new Date().toLocaleTimeString());
  $('compatibility').hidden = view.compatible && !view.needs_recovery && view.managed;
  text('compatibility', view.archived ? 'Archived evidence · The original Host is unavailable. You can inspect results and record scientific comments. New research starts from the Project.' : !view.compatible ? 'Historical runtime build. Use its original supported build for control actions.' : !view.managed ? 'Imported Run · Use its original CLI for control actions.' : 'An invocation started without a committed completion. Inspect its original recovery state.');
  const roles = ['method_planner', ...(intake ? [] : ['code_agent', 'analysis_engineer', 'scientific_reviewer']),
    ...(view.attempts.some(a => a.kind === 'human_gate') ? ['human_gate'] : []), 'memory_report'];
  if (changed('timeline', [roles, view.attempts, closed, view.active_pause?.reason])) rows($('timeline'), roles.map(kind => {
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
  if (changed('budget', [view.budget, view.research_task, view.archived])) renderBudget(view);
  renderAuthorization(view, newPause);
  if (detailChanged) {
    attachmentPicker(); summaries(view); showTab(state.tab);
  }
  renderComparison($('comparison'), view, state.runs, loadRun, openRun);
}

function renderBudget(view) {
  const budget = Object.entries(view.budget.dimensions).filter(([name]) => ['active_seconds_per_run','llm_calls_per_run','tool_calls_per_run','transitions_per_run'].includes(name)).map(([name, value]) => {
    const item = node('div'); item.append(node('span', 'Run · '+readable(name)), node('strong', value.used+' used · '+value.remaining+' remaining')); return item;
  });
  if (view.archived) budget.unshift(node('p', 'Saved Run budget. Remaining shared-task quota was not captured.', 'muted'));
  if (view.research_task && !view.archived) {
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
}

function renderAuthorization(view, newPause) {
  const request = view.human_request;
  $('gate').hidden = !request; $('cancel-box').hidden = !view.actions.cancel;
  if (request) {
    text('gate-kind', readable(request.request_kind));
    const scope = request.authorization_scope;
    text('gate-prompt', request.prompt ?? request.summary ?? (scope.work_target ?
      'Requested work: '+(roleNames[scope.work_target] || readable(scope.work_target))+'.' :
      'A decision is requested for the recorded scope.'));
    text('gate-scope', JSON.stringify(scope, null, 2));
    if (newPause) {
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

}

async function refresh() {
  if (refreshing) { refreshAgain = true; return; }
  refreshing = true;
  const version = navigation, project = state.project, selected = state.selected;
  try {
    const [projects, runs] = await Promise.all([api('/api/projects'),
      api(project ? projectEndpoint(project.id)+'/runs' : '/api/runs')]);
    if (version !== navigation || project !== state.project || selected !== state.selected) return;
    state.projects = projects; state.runs = runs;
    if (changed('projects', [projects.map(p => [p.id, p.sha256]), project?.id])) projectList(projects);
    const history = runs.map(r => [r.host, r.run_locator, r.project_revision, r.workflow, r.task_binding || r.research_task?.id,
      r.research_task?.parent, r.run_status, r.preparation?.status, r.scientific_outcome, r.inspection]);
    if (changed('history', [project?.id, history, selected])) renderTaskList(runs, selected, project, openRun);
    const current = projects.find(p => p.id === project?.id);
    if (current && current.sha256 !== project.sha256) {
      text('project-revision', 'A newer Project version is available. Refresh the Project to load it before submitting changes.');
    }
    if (selected && !state.libraryOpen) {
      const path = endpoint(selected);
      let detailChanged = !state.view;
      let view = await api(path+(detailChanged ? '' : '?details=false'));
      if (version !== navigation) return;
      if (!detailChanged && view.detail_revision !== state.view.detail_revision) {
        detailChanged = true;
        view = await api(path);
        if (version !== navigation) return;
      }
      if (view.host !== selected.host || view.run_locator.run_id !== selected.run_locator.run_id ||
          view.run_locator.case_id !== selected.run_locator.case_id ||
          selected.project_id && selected.project_id !== view.project_id) throw new Error('Run identity does not match the selection.');
      render(detailChanged ? view : {...state.view, ...view}, detailChanged);
    }
    $('project-start').disabled = state.busy || !project;
    await contributions();
    if (version !== navigation) return;
    text('connection', 'Connected · local'); $('connection').classList.remove('offline');
  } catch (error) {
    if (version !== navigation) return;
    state.verified = false; $('respond').disabled = true; $('cancel').disabled = true; $('project-continue').disabled = true;
    text('connection', error.network ? 'Disconnected · reconnecting' : error.status === 409 ?
      'Checkpoint unavailable' : 'View unavailable');
    $('connection').classList.toggle('offline', Boolean(error.network));
    if (error.status === 403) await session();
    else if (error.status === 409) notice('Checkpoint verification: '+error.message+'. Control actions are disabled.', 'verification');
    else notice(error.message, 'verification');
  } finally {
    refreshing = false;
    if (refreshAgain) { refreshAgain = false; void refresh(); }
  }
}

function showTab(tab) {
  state.tab = tab;
  for (const button of $('tabs').querySelectorAll('[data-tab]')) {
    button.classList.toggle('active', button.dataset.tab === tab);
    button.setAttribute('aria-pressed', String(button.dataset.tab === tab));
  }
  $('overview').hidden = tab !== 'overview';
  $('evidence-pane').hidden = tab === 'overview';
  $('collaboration').hidden = !['plan', 'review'].includes(tab);
  if (!state.view) return;
  if (!$('collaboration').hidden && changed('discussion', [state.view.detail_revision, tab])) collaboration(state.view);
  if (tab !== 'overview' && changed('files', [state.view.detail_revision, tab])) evidenceList();
}

async function session() { const value = await api('/api/session'); state.token = value.token; state.host = value.host; }
$('forget-pending').addEventListener('click', async event => {
  if (state.busy) return;
  const forgotten = await controlSlot.clear(event.currentTarget.dataset.key);
  forgetControlOption(controlSlot.read());
  notice(forgotten ? 'Saved browser submission forgotten.' : 'The saved submission changed. Refresh to inspect the current record.');
});
$('forget-contribution').addEventListener('click', async event => {
  const forgotten = await inputSlot.clear(event.currentTarget.dataset.key);
  forgetInputOption(inputSlot.read());
  notice(forgotten ? 'Unconfirmed browser form forgotten.' : 'The saved form changed. Refresh to inspect the current record.');
});
$('contribution-form').addEventListener('submit', async event => {
  event.preventDefault(); if (!state.project) return;
  const selected = state.selected?.project_id === state.project.id && state.verified;
  if ($('contribution-run').checked && !selected) { notice('Wait for the selected investigation to be verified before recording this Run-specific input.'); return; }
  const originalDraft = draftKey, projectId = state.project.id;
  const run = $('contribution-run').checked ? {host: state.view.host,
    ...state.view.run_locator, execution_head: state.view.execution_head} : null;
  const payload = {expected_digest: state.project.sha256, kind: $('contribution-kind').value,
    body: $('contribution-body').value, evidence_sha256: selectedEvidence(), run};
  $('contribution-save').disabled = true;
  try {
    const {record: pending} = await inputSlot.claim({project: projectId, payload: {...payload, key: crypto.randomUUID()}});
    if (pending.project !== projectId || Boolean(pending.payload.run) !== Boolean(run) ||
        run && ['host', 'case_id', 'run_id'].some(k => pending.payload.run[k] !== run[k]) ||
        ['kind', 'body', 'evidence_sha256'].some(k => JSON.stringify(pending.payload[k]) !== JSON.stringify(payload[k]))) {
      forgetInputOption(pending);
      notice('An unconfirmed scientific input is retained. Restore its Project to retry, or forget its browser form before submitting a new input.');
      return;
    }
    await sendContribution(inputSlot, pending, api);
    drafts.delete(originalDraft);
    if (draftKey !== originalDraft) return;
    $('contribution-form').reset(); attachmentPicker([]);
    notice(state.view?.preparation?.status === 'needs_information' ?
      'Reply recorded. Continue research when ready; it uses the original remaining budget and deadline.' :
      'Scientific input recorded for the next research checkpoint. It does not grant additional authority.');
    await contributions();
  } catch (error) {
    notice(error.status === 409 ? 'The Project or Run changed. Refresh before submitting again.' : error.message);
    forgetInputOption(inputSlot.read());
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
  const version = navigation;
  try {
    const project = await api(projectEndpoint(state.project.id), {expected_digest: state.project.sha256,
      title: $('edit-project-title').value, goal: $('edit-project-goal').value,
      case_config: draftConfig(JSON.parse($('edit-project-config').value || 'null'),
        $('edit-project-data').value.trim(), $('edit-project-python').value.trim(), $('edit-project-source').value.trim(), true)});
    if (navigation !== version) return;
    await loadProject(project.id, version);
    if (navigation !== version) return;
    await refresh(); notice('Project version saved for future investigations.');
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
$('project-overview-button').addEventListener('click', () => {
  if (state.project) chooseProject(state.project.id).catch(error => notice(error.message));
});
$('open-library').addEventListener('click', () => {
  ++navigation; leaveRun(); state.libraryOpen = true; $('library-panel').hidden = false; $('project-panel').hidden = true; $('participation').hidden = true;
  $('investigation').hidden = true; $('empty').hidden = true; $('gate').hidden = true; $('cancel-box').hidden = true;
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
  event.preventDefault(); try { const value = JSON.parse($('locator').value); if (!value.host || !value.run_locator?.case_id || !value.run_locator?.run_id) throw new Error('Paste the complete CLI status JSON.'); openRun(value); } catch (error) { notice(error.message); }
});
$('response-form').addEventListener('submit', event => {
  event.preventDefault(); if (!state.verified || !state.view?.actions.respond || !state.view.active_pause) return; const view = state.view;
  mutation(runEndpoint(state.selected)+'/respond', {pause: view.active_pause.pause_id, head: view.execution_head,
    decision: $('decision').value, conditions: $('conditions').value.split('\n').map(s => s.trim()).filter(Boolean), reason: $('reason').value}, state.selected);
});
$('cancel').addEventListener('click', () => {
  if (!state.verified || !state.view?.actions.cancel || !state.view.active_pause) return;
  const view = state.view;
  mutation(runEndpoint(state.selected)+'/cancel', {pause: view.active_pause.pause_id, head: view.execution_head}, state.selected);
});
$('contribution-evidence').addEventListener('change', attachmentSummary);
$('tabs').addEventListener('click', event => {
  const tab = event.target.closest('[data-tab]')?.dataset.tab;
  if (tab) { reader.close(false); showTab(tab); }
});
document.addEventListener('visibilitychange', () => { if (!document.hidden && state.token) refresh(); });
async function restoreSelection() {
  const params = new URL(location.href).searchParams;
  const direct = ['host','case','run'].some(key => params.has(key));
  const explicit = direct || params.has('project') || params.has('project_run');
  if (direct) {
    if (!['host','case','run'].every(key => params.get(key))) throw new Error('Incomplete investigation link.');
    state.selected = {host: params.get('host'), run_locator: {case_id: params.get('case'), run_id: params.get('run')}};
  } else if (!explicit) state.selected = JSON.parse(localStorage.getItem(storage+'selected') || 'null');
  const project = explicit ? params.get('project') : state.selected?.project_id || (!state.selected && localStorage.getItem(storage+'project'));
  if (params.has('project_run') && !project) throw new Error('The saved Run link requires its Project.');
  if (project) {
    await loadProject(project);
    if (params.has('project_run') || state.selected && !state.selected.project_run_key) {
      const runs = await api(projectEndpoint(project)+'/runs');
      const saved = runs.find(run => (!params.has('project_run') || run.project_run_key === params.get('project_run')) &&
        (!state.selected || run.host === state.selected.host && run.run_locator.case_id === state.selected.run_locator.case_id && run.run_locator.run_id === state.selected.run_locator.run_id));
      if (!saved) throw new Error('The investigation link does not match this Project’s saved Run.');
      state.selected = {host: saved.host, run_locator: saved.run_locator, project_id: project, project_run_key: saved.project_run_key};
    }
    $('empty').hidden = true;
  }
}
async function init() {
  await session(); state.cases = await api('/api/cases');
  for (const entry of state.cases) { for (const selector of ['case', 'project-case']) { const option = node('option', entry.case_id+(entry.requires_live ? ' · Codex' : '')); option.value = entry.id; $(selector).append(option); } }
  try { await restoreSelection(); }
  catch (error) {
    if (error.network) throw error;
    state.selected = null;
    $('empty').hidden = Boolean(state.project);
    notice('Could not open the saved selection. '+error.message);
  }
  switchDraft(); await reconcile(); await refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, 2000);
}
init().catch(error => {
  text('connection', error.network ? 'Disconnected' : 'Workspace unavailable');
  notice(error.message);
});
