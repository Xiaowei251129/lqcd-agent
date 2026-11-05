import {planSections, planDiff, planningAccess} from './planning.js';
/* Read-only navigation and layout. The application owns every control submission. */
const byId = id => document.getElementById(id);
const readable = value => String(value ?? '').replaceAll('_', ' ');
const runKey = run => JSON.stringify([run.host, run.run_locator.case_id, run.run_locator.run_id]);
const sameLocator = (a, b) => a && b && a.case_id === b.case_id && a.run_id === b.run_id;
const closed = view => ['completed', 'failed', 'halted'].includes(view.run_status);

function element(tag, text, className) {
  const item = document.createElement(tag);
  if (text !== undefined) item.textContent = text;
  if (className) item.className = className;
  return item;
}

function binding(run) {
  // Project captures carry the frozen task binding. Global rows can omit it.
  return run.task_binding ?? (run.project_run_key ? run.research_task : null);
}

export function researchTasks(runs) {
  const groups = new Map();
  for (const run of runs) {
    const id = binding(run)?.id;
    const key = id ? JSON.stringify([run.host, id]) : runKey(run);
    if (!groups.has(key)) groups.set(key, {key, id, runs: []});
    groups.get(key).runs.push(run);
  }
  return [...groups.values()].map(group => {
    const pending = [...group.runs];
    const steps = [];
    while (pending.length) {
      // Show the captured portion of a lineage even if its parent is unavailable.
      const next = pending.findIndex(run => !pending.some(other =>
        sameLocator(other.run_locator, binding(run)?.parent)));
      const [run] = pending.splice(Math.max(next, 0), 1);
      const parent = steps.find(step => sameLocator(step.run.run_locator, binding(run)?.parent));
      const label = run.workflow === 'intake' ? (parent ? 'Clarification' : 'Preparation') :
        run.workflow === 'scientific' ? (parent?.run.workflow === 'scientific' ? 'Follow-up analysis' : 'Formal analysis') :
        readable(run.workflow) || 'Investigation';
      steps.push({run, label, depth: parent ? parent.depth + 1 : 0});
    }
    return {key: group.key, id: group.id, steps};
  });
}

function moveTo(id, target) {
  const item = byId(id), place = byId(target);
  if (item.parentElement !== place) place.append(item);
}

function selectButton(label, click, className = 'secondary') {
  const button = element('button', label, className);
  button.type = 'button'; button.addEventListener('click', click);
  return button;
}

export function renderTaskList(runs, selected, project, onSelect) {
  const home = Boolean(project && !selected);
  moveTo('task-navigation', home ? 'project-tasks' : 'sidebar-tasks');
  const tasks = researchTasks(runs), list = byId('run-list');
  byId('history-title').textContent = project ? 'Research tasks' : 'Investigations';
  byId('run-count').textContent = String(tasks.length);
  const prior = new Map([...list.children].filter(e => e.tagName === 'DETAILS').map(group => [group.dataset.key, group.open]));
  const focused = document.activeElement?.dataset.runKey;
  const selectedKey = selected && runKey(selected);
  const groups = tasks.map(task => {
    const first = task.steps[0].run;
    const group = element('details', undefined, 'task-group'); group.dataset.key = task.key;
    const heading = element('summary');
    heading.append(element('span', first.run_locator.case_id, 'task-name'), element('small',
      [first.project_revision && 'v'+first.project_revision, task.id ? 'task '+task.id.slice(0,7) : first.run_locator.run_id,
        task.steps.length+' '+(task.steps.length === 1 ? 'Run' : 'Runs')].filter(Boolean).join(' · ')));
    group.append(heading);
    const active = task.steps.some(s => runKey(s.run) === selectedKey);
    group.open = active || (prior.has(task.key) ? prior.get(task.key) : home || tasks.length === 1);
    const sequence = element('ol', undefined, 'task-steps');
    for (const {run,label,depth} of task.steps) {
      const id = runKey(run), item = element('li');
      item.classList.toggle('linked', depth > 0);
      const button = selectButton(label, () => onSelect(run), 'task-step');
      button.dataset.runKey = id;
      if (id === selectedKey) button.setAttribute('aria-current', 'page');
      const state = run.inspection === 'unavailable' ? 'Verification pending' :
        [readable(run.run_status), run.workflow === 'intake' ? readable(run.preparation?.status) :
          readable(run.scientific_outcome)].filter(Boolean).join(' · ');
      button.append(element('small', [state || 'Recorded Run', run.run_locator.run_id.slice(-8)].join(' · ')));
      item.append(button); sequence.append(item);
    }
    group.append(sequence);
    return group;
  });
  list.replaceChildren(...(groups.length ? groups : [element('p', project ? 'No tasks recorded for this project.' : 'No investigations recorded.', 'muted')]));
  if (focused) [...list.querySelectorAll('button')].find(b => b.dataset.runKey === focused)?.focus({preventScroll:true});
  const launch = byId('new-task');
  if (home && launch.dataset.project !== project.id) {
    launch.open = !tasks.length; launch.dataset.project = project.id;
  }
}

function putText(id, value) {
  const item = byId(id), text = String(value ?? '');
  if (item.textContent !== text) item.textContent = text;
}

// Keep open disclosures and keyboard focus when polling changes only another part of the view.
const rendered = new WeakMap();
function updateSection(id, key, build) {
  const item = byId(id), version = JSON.stringify(key);
  if (rendered.get(item) === version) return;
  item.replaceChildren(...build()); rendered.set(item, version);
}

function openField(field) {
  const input = byId(field);
  for (let panel = input.closest('details'); panel; panel = panel.parentElement.closest('details')) panel.open = true;
  input.focus();
}

function section(name, values) {
  const group = element('div', undefined, 'plan-section'), list = element('ul');
  for (const value of values) list.append(element('li', value));
  group.append(element('h3', name), list);
  return group;
}

function answerField(question, choice, index) {
  const field = element('fieldset', undefined, 'plan-question');
  field.dataset.question = question;
  field.append(element('legend', question));
  if (choice) {
    for (const option of [...choice.options, {label: 'Delegate this choice to PI', consequence: 'PI will explain the choice in the revised plan.'}]) {
      const label = element('label', undefined, 'check'), input = element('input');
      input.type = 'radio'; input.name = 'answer-'+index; input.value = option.label;
      const content = element('span', option.label+(option.label === choice.recommended ? ' (recommended)' : ''));
      content.append(element('small', option.consequence)); label.append(input, content); field.append(label);
    }
  }
  const label = element('label', choice ? 'Your answer or additional context' : 'Supply the missing information');
  const text = element('textarea'); text.id = 'plan-answer-'+index; label.htmlFor = text.id;
  text.rows = 2; text.maxLength = 3000; field.append(label, text);
  return field;
}

function preparation(view, runs, project, onSelect) {
  const data = view.preparation, status = data?.status;
  const children = runs.filter(run => run.host === view.host &&
    (sameLocator(run.research_task?.parent, view.run_locator) || sameLocator(run.run_locator,view.plan_successor)));
  const previous = view.previous_plan;
  const matched = project?.id === view.project_id;
  const access = planningAccess(view, project, children);
  const current = runKey(view);
  putText('preparation-title', status === 'needs_information' ? 'Questions for you' : status === 'ready' ?
    (view.plan_mode === 'review' && !children.length ? 'Plan ready for review' : 'Prepared plan') :
    closed(view) ? 'Preparation ended' : 'PI is preparing the plan');
  putText('preparation-summary', data?.summary || '');
  const version = view.plan_digest;
  putText('plan-version', version ? 'Plan '+version.slice(0,12)+' · '+(view.plan_mode === 'auto' ? 'Automatic execution' :
    view.plan_mode === 'review' ? 'Review before execution' : 'Recorded plan') : '');
  updateSection('plan-sections', [current,version,data,view.intake_profile], () => {
    const sections = planSections(data || {}), profile = view.intake_profile;
    const facts = profile ? [profile.format, ...Object.entries(profile.shapes || {}).map(([field,shape]) =>
      field+' · '+shape.join(' × ')), ...Object.entries(profile.metadata || {}).map(([name,value]) =>
      name+' = '+JSON.stringify(value))].filter(Boolean) : [];
    return Object.entries({'Verified input profile':facts, ...sections})
      .filter(([,values]) => values.length).map(([name, values]) => section(name, values));
  });
  updateSection('plan-diff', [current,version,previous?.plan_sha256], () => {
    if (!previous?.proposal || !data) return [];
    const diff = planDiff(previous.proposal, data), details = element('details', undefined, 'fold');
    details.append(element('summary', 'Changes from previous plan ('+diff.length+')'));
    for (const change of diff) {
      const group = element('section'); group.append(element('h3', change.section),
        section('Previously', change.before.length ? change.before : ['—']),
        section('Now', change.after.length ? change.after : ['—'])); details.append(group);
    }
    return [details];
  });
  updateSection('preparation-questions', [current,version,data?.questions,access.revise], () => {
    const questions = data?.questions || [];
    if (!questions.length) return [];
    if (!access.revise) return [section('Recorded questions', questions)];
    const first = questions.slice(0,3).map((q,i) => answerField(q, data.choices?.find(c => c.question === q), i));
    if (questions.length > 3) first.push(section('Other open prerequisites', questions.slice(3)));
    return first;
  });
  const revision = byId('plan-revision');
  if (revision.dataset.plan !== current+version) {
    revision.open = status === 'needs_information'; revision.dataset.plan = current+version;
    byId('plan-feedback').value = '';
  }
  byId('plan-actions').hidden = !access.revise && !access.execute && !access.renew;
  byId('plan-execute').hidden = !access.execute;
  revision.hidden = !access.revise;
  byId('plan-renew-block').hidden = !access.renew;
  byId('prepared-config-details').hidden = !data?.case_config;
  putText('prepared-config', data?.case_config ? JSON.stringify(data.case_config, null, 2) : '');
  updateSection('formal-child', [current,version,view.archived,view.plan_mode,access,children.map(runKey),project?.sha256], () => {
    if (children.length) return children.map(run => selectButton(run.workflow === 'scientific' ?
      'Open formal analysis →' : 'Open revised plan →', () => onSelect(run)));
    if (view.research_task?.remaining_runs === 1 && !view.plan_exhausted && !view.plan_successor) {
      return [element('p', 'The final Run slot is reserved for formal analysis. To revise this plan, open Project overview → Start a new investigation for a new task budget.', 'footnote')];
    }
    if (view.plan_successor) return [element('p','A successor was admitted. Its Project record is being captured.', 'footnote')];
    if (view.archived) return [element('p','Saved evidence. Start a new plan from the Project to resume research.', 'footnote')];
    if (matched && data?.status === 'ready' && !access.execute && !access.renew && view.project_sha256 !== project.sha256) {
      return [element('p','Project inputs changed. Request a revised plan before execution.', 'footnote')];
    }
    return [];
  });
}

export function renderTaskDesk(view, runs, project, onSelect) {
  const intake = view?.workflow === 'intake';
  const edit = intake && view.preparation && project && view.project_id === project.id;
  moveTo('project-editor', edit && !view.archived ? 'clarification-editor' : 'editor-home');
  byId('project-panel').classList.toggle('compact', Boolean(view && project));
  if (!view) {
    byId('navigation-toggle').setAttribute('aria-expanded', 'false');
    return;
  }
  const goal = String(view.goal || view.run_locator.case_id).trim();
  const lead = goal.split(/\r?\n/)[0];
  putText('run-title', lead.length > 175 ? lead.slice(0,172)+'…' : lead);
  byId('goal-details').hidden = goal === byId('run-title').textContent; putText('run-goal', goal);
  putText('run-mode', [view.archived && 'Archived', intake ? 'Project preparation' : view.run_locator.case_id,
    view.live ? 'Live agents' : 'Offline', !intake && view.synthetic && 'Synthetic data'].filter(Boolean).join(' · '));
  putText('run-state', readable(view.run_status));
  putText('outcome-label', intake ? 'Preparation' : 'Scientific outcome');
  putText('acceptance', intake ? readable(view.preparation?.status || 'pending') :
    view.scientific_outcome ? readable(view.scientific_outcome)+' · '+readable(view.decision_origin) :
      (closed(view) ? 'No recorded conclusion' : 'Pending review'));
  putText('activity', view.archived ? 'Saved checkpoint' : view.human_request ? 'Extra authorization requested' :
    closed(view) ? 'Run closed' : readable(view.attempts?.at(-1)?.kind || 'Admitted'));
  byId('preparation-panel').hidden = !intake;
  if (intake) preparation(view, runs, project, onSelect);
  const review = (view.collaboration || []).find(item => item.current && item.slot === 'review');
  const terminal = view.summaries?.['memory_update.json'];
  const failure = view.execution_failure?.summary || (view.outcome_source === 'control_closure' &&
    'The Host recorded an execution closure without a scientific final report.');
  const reason = failure || review?.summary || view.summaries?.['scientific_review_report.json']?.summary ||
    terminal?.classification_reason;
  const outstanding = (review?.issues || []).filter(issue => ['open','blocked'].includes(issue.status));
  const show = Boolean(!intake && closed(view) && (reason || outstanding.length));
  byId('conclusion-box').hidden = !show;
  if (show) {
    putText('conclusion-label', failure ? 'Execution finding' : 'Conclusion and limits');
    putText('conclusion-text', reason);
    updateSection('open-questions', outstanding.map(i => i.question), () => outstanding.map(i => element('li', i.question)));
    byId('inspect-review').hidden = !review && !(view.evidence || []).some(entry => entry.slot === 'review');
  }
}

byId('navigation-toggle').addEventListener('click', event => {
  const button = event.currentTarget;
  button.setAttribute('aria-expanded', String(button.getAttribute('aria-expanded') !== 'true'));
});
byId('empty-create').addEventListener('click', () => {
  byId('navigation-toggle').setAttribute('aria-expanded', 'true');
  openField('project-id');
});
byId('inspect-review').addEventListener('click', () => {
  const tab = byId('tabs').querySelector('[data-tab="review"]');
  tab.click(); tab.focus();
});
