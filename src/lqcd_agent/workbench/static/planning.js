// Projections of a sealed preparation. The Host owns validation and admission.
const line = value => typeof value === 'string' ? value : JSON.stringify(value);
const lines = value => (Array.isArray(value) ? value : value == null ? [] : [value]).map(line);

export function planSections(plan) {
  const brief = plan.brief || {}, method = plan.method_plan || {}, config = plan.case_config || {};
  const program = config.generated_program || {}, dataset = plan.dataset_identity, python = plan.interpreter_identity;
  const checks = new Set([...(brief.discriminating_checks || []), ...(brief.success_criteria || [])]);
  const groups = {
    'Scientific plan': {
      'Research goal': config.physics_goal || method.physics_goal, 'Research question': brief.physics_question,
      'Competing explanations': brief.competing_explanations, 'Discriminating checks': brief.discriminating_checks,
      'Decision criteria': brief.success_criteria, 'Assumptions and limits': plan.assumptions,
      'Analysis steps': method.method_steps?.filter(step => !checks.has(step)), 'Expected inputs': method.required_inputs,
      'Observables': method.target_observables || config.target_observables, 'Deliverables': method.required_outputs,
      'Research Worker task': method.coder_task_summary,
    },
    'Execution bindings': {
      'Data file': config.raw_data_path || dataset?.path, 'Data provenance': config.source_kind,
      'Data content SHA-256': dataset?.exists === false ? 'File missing at preparation' : dataset?.sha256,
      'Scientific interpreter': program.python || python?.path, 'Resolved interpreter': python?.realpath,
      'Interpreter SHA-256': python?.sha256, 'Result type': program.result_kind,
      'Frozen parameters': Object.entries(program.parameters || {}).map(([key,value]) => key+' = '+line(value)),
      'Numerical timeout (seconds)': program.timeout_seconds, 'Registered programs': method.selected_analysis_programs,
      'Requested program tags': config.analysis_program_tags, 'Explicit analysis commands': config.analysis_commands,
      'Allowed analysis commands': config.allowed_analysis_commands, 'Configured output checks': config.expected_outputs,
      'Reference files': config.golden_reference_files, 'Reference directory': config.golden_example_root,
      'Requested method versions': config.method_dependencies,
      'Other implementation requirements': program.requirements?.filter(item => !method.method_steps?.includes(item)),
      'Intake snapshot SHA-256': plan.profile_sha256,
    },
  };
  return Object.fromEntries(Object.entries(groups).map(([group,sections]) =>
    [group,Object.fromEntries(Object.entries(sections).map(([name,value]) => [name,lines(value)]))]));
}

export function planDiff(previous, current) {
  function comparison(plan) {
    const groups = planSections(plan);
    Object.assign(groups['Scientific plan'], {'Readiness': lines(plan.status), 'Plan summary': lines(plan.summary),
      'Open questions': lines(plan.questions), 'Proposed choices': lines(plan.choices), 'Blocking issues': lines(plan.blocking_issues),
      'Scientific input SHA-256': lines(plan.scientific_input_sha256)});
    return groups;
  }
  const before = comparison(previous), after = comparison(current), changes = [];
  for (const [group, sections] of Object.entries(after)) {
    for (const [section, values] of Object.entries(sections)) {
      if (JSON.stringify(before[group][section]) !== JSON.stringify(values)) {
        changes.push({group, section, before: before[group][section], after: values});
      }
    }
  }
  return changes;
}

export function planDraftKey(host, project, caseId, run, digest) {
  return 'lqcd-workbench:plan-draft:'+JSON.stringify([host,project,caseId,run,digest]);
}

export function planningAccess(view, project, children) {
  const actionable = Boolean(project && project.id === view.project_id && view.plan_mode && view.plan_digest &&
    view.managed && view.compatible && !view.archived && view.run_status === 'completed' && !view.plan_successor && !children.length);
  return {revise: actionable && !view.plan_exhausted && view.research_task?.remaining_runs !== 1,
    execute: actionable && !view.plan_exhausted && view.preparation?.status === 'ready' &&
      view.plan_mode === 'review' && project.sha256 === view.project_sha256,
    renew: actionable && Boolean(view.plan_exhausted)};
}

export function planFeedback({answers, instruction}) {
  const replies = answers.map(({question, choice, note}) => {
    const reply = [choice, note.trim()].filter(Boolean).join(' — ');
    return reply ? question+'\n'+reply : '';
  });
  return [...replies, instruction.trim()].filter(Boolean).join('\n\n');
}
