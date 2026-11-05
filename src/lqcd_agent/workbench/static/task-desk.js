/* Read-only navigation and layout. The application owns every control submission. */
const byId = id => document.getElementById(id);
const readable = value => String(value ?? '').replaceAll('_', ' ');
const runKey = run => JSON.stringify([run.host, run.run_locator.case_id, run.run_locator.run_id]);
const sameLocator = (a, b) => a?.case_id === b?.case_id && a?.run_id === b?.run_id;
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

function preparation(view, runs, project, onSelect) {
  const data = view.preparation, status = data?.status;
  const clarification = status === 'needs_information';
  const matchingProject = project && view.project_id === project.id;
  const current = runKey(view);
  putText('preparation-title', status === 'ready' ? 'Ready for analysis' : clarification ? 'Information needed' :
    closed(view) ? 'Preparation ended' : 'Preparing the investigation');
  putText('preparation-summary', data?.summary || (closed(view) ? 'No preparation summary was recorded.' :
    'PI and Postdoc are preparing the research question and analysis contract.'));
  const questions = data?.questions || [];
  updateSection('preparation-questions', [current, questions, Boolean(matchingProject), view.archived, status], () => {
    if (!questions.length) return [];
    const list = element('ol', undefined, 'questions');
    for (const question of questions) {
      const item = element('li');
      item.append(element('span', question));
      if (matchingProject && clarification) {
        // These shortcuts edit the Project draft. The Host checks the next admission.
        const field = question.includes('raw_data_path') || question.startsWith('Provide the declared research input file') ? 'data' :
          question.includes('source_kind') ? 'source' :
          question.includes('generated_program.python') || question.includes('scientific Python interpreter') ? 'python' :
          question.startsWith('Supply ns, pz') || question.startsWith('Supply target_pz') ? 'config' : null;
        if (field && !view.archived) {
          const id = 'edit-project-'+field;
          item.append(selectButton('Edit '+byId(id).labels[0].textContent, () => openField(id), 'text-button'));
        }
        item.append(selectButton('Reply', () => {
          const input = byId('contribution-body');
          if (!input.value) input.value = 'Regarding “'+question.slice(0,600)+'”\n';
          openField('contribution-body');
        }, 'text-button'));
      }
      list.append(item);
    }
    return [element('h3', 'Open questions'), list];
  });
  const assumptions = data?.assumptions || [];
  updateSection('preparation-assumptions', [current, assumptions], () => {
    if (!assumptions.length) return [];
    const details = element('details'), list = element('ul');
    for (const assumption of assumptions) list.append(element('li', assumption));
    details.append(element('summary', 'Assumptions and scope'), list); return [details];
  });
  byId('prepared-config-details').hidden = !data?.case_config;
  putText('prepared-config', data?.case_config ? JSON.stringify(data.case_config, null, 2) : '');
  const children = runs.filter(run => run.host === view.host && binding(run)?.id === view.task_binding?.id &&
    sameLocator(binding(run)?.parent, view.run_locator));
  // Replaying the same parent would consume authority: only link a recorded child here.
  byId('archived-clarification').hidden = !(clarification && view.archived);
  byId('preparation-continue').hidden = !(matchingProject && clarification && closed(view) && !view.archived && !children.length);
  const links = children.filter(run => status === 'ready' ? run.workflow === 'scientific' : clarification && run.workflow === 'intake');
  updateSection('formal-child', [current, status, links.map(runKey)], () => {
    if (links.length) return links.map(run => selectButton(run.workflow === 'scientific' ? 'Open formal analysis →' :
      'Open continued preparation →', () => onSelect(run), 'secondary'));
    if (status === 'ready') return [element('p', 'No linked formal analysis is recorded in this task’s history.', 'footnote')];
    return [];
  });
}

export function renderTaskDesk(view, runs, project, onSelect) {
  const intake = view?.workflow === 'intake';
  const clarify = intake && view.preparation?.status === 'needs_information' && project && view.project_id === project.id;
  moveTo('project-editor', clarify && !view.archived ? 'clarification-editor' : 'editor-home');
  moveTo('participation', clarify ? 'clarification-reply' : 'participation-home');
  putText('participation-label', clarify ? 'Record a scientific reply' : 'Scientific input');
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
