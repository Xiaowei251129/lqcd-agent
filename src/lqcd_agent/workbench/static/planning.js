// Projections of a sealed preparation. The Host owns validation and admission.
const line = value => typeof value === 'string' ? value : JSON.stringify(value);
const lines = value => (Array.isArray(value) ? value : value == null ? [] : [value]).map(line);

export function planSections(plan) {
  const brief = plan.brief || {}, method = plan.method_plan || {}, config = plan.case_config || {};
  const checks = new Set([...(brief.discriminating_checks || []), ...(brief.success_criteria || [])]);
  return Object.fromEntries(Object.entries({
    'Research question': brief.physics_question || method.physics_goal,
    'Competing explanations': brief.competing_explanations,
    'Discriminating checks': brief.discriminating_checks,
    'Decision criteria': brief.success_criteria,
    'Analysis steps': method.method_steps?.filter(step => !checks.has(step)), 'Expected inputs': method.required_inputs,
    'Observables': method.target_observables, 'Deliverables': method.required_outputs, 'Programs': method.selected_analysis_programs,
    'Code task': method.coder_task_summary,
    'Data source': [config.raw_data_path, config.source_kind].filter(Boolean),
    'Frozen parameters': config.generated_program?.parameters,
    'Other implementation requirements': config.generated_program?.requirements?.filter(item => !method.method_steps?.includes(item)),
    'Assumptions and limits': plan.assumptions,
  }).map(([name, value]) => [name, lines(value)]));
}

export function planDiff(previous, current) {
  const before = {...planSections(previous), 'Open questions': lines(previous.questions)},
    after = {...planSections(current), 'Open questions': lines(current.questions)};
  return Object.keys(after).filter(key => JSON.stringify(before[key]) !== JSON.stringify(after[key]))
    .map(section => ({section, before: before[section], after: after[section]}));
}

export function planningAccess(view, project, children) {
  const actionable = Boolean(project && project.id === view.project_id && view.plan_mode && view.plan_digest &&
    view.managed && view.compatible && !view.archived && view.run_status === 'completed' && !view.plan_successor && !children.length);
  return {revise: actionable && !view.plan_exhausted && view.research_task?.remaining_runs !== 1,
    execute: actionable && !view.plan_exhausted && view.preparation?.status === 'ready' &&
      view.plan_mode === 'review' && project.sha256 === view.project_sha256,
    renew: actionable && Boolean(view.plan_exhausted)};
}

export function planFeedback(answers, instruction) {
  return [...answers.filter(({answer}) => answer.trim()).map(({question, answer}) =>
    question+'\n'+answer.trim()), instruction.trim()].filter(Boolean).join('\n\n');
}
