import assert from 'node:assert/strict';
import test from 'node:test';
import {planningAccess, planDiff, planDraftKey, planFeedback} from '../src/lqcd_agent/workbench/static/planning.js';

const current = {project_id:'p', project_sha256:'frozen', managed:true, compatible:true, plan_mode:'review',
  plan_digest:'plan', run_status:'completed', preparation:{status:'ready'}};
const project = {id:'p', sha256:'frozen'};

test('manual execution selects only a current, ready plan with unchanged inputs', () => {
  assert.deepEqual(planningAccess(current,project,[]),{revise:true,execute:true,renew:false});
  assert.equal(planningAccess(current,{...project,sha256:'edited'},[]).execute,false);
  assert.equal(planningAccess({...current,plan_mode:'auto'},project,[]).execute,false);
  assert.equal(planningAccess({...current,preparation:{status:'needs_information'}},project,[]).execute,false);
  for (const change of [{managed:false},{compatible:false},{archived:true},{plan_digest:null}]) {
    assert.deepEqual(planningAccess({...current,...change},project,[]),{revise:false,execute:false,renew:false});
  }
  assert.deepEqual(planningAccess(current,project,[{}]),{revise:false,execute:false,renew:false});
  assert.deepEqual(planningAccess({...current,plan_exhausted:true},project,[]),{revise:false,execute:false,renew:true});
});

test('the final slot can execute a ready plan but cannot revise one with missing facts', () => {
  const last = {...current, research_task:{remaining_runs:1}};
  assert.deepEqual(planningAccess(last,project,[]),{revise:false, execute:true, renew:false});
  assert.deepEqual(planningAccess({...last, preparation:{status:'needs_information'}},project,[]),
    {revise:false, execute:false, renew:false});
});

test('revision compares scientific rules and content-bound execution details, including unchanged paths', () => {
  const v1 = {brief:{success_criteria:['Choose a central value']}, assumptions:['Known ensemble'],
    dataset_identity:{path:'raw_data/data.json',exists:true,sha256:'old-data'},
    interpreter_identity:{path:'/env/python',realpath:'/opt/python',sha256:'old-python'},
    case_config:{generated_program:{python:'/env/python',result_kind:'c2',parameters:{tmax:12}},
      method_dependencies:[{id:'fit',revision:1,sha256:'old-method'}]}};
  const v2 = {...v1,brief:{success_criteria:['Compare windows']},
    dataset_identity:{...v1.dataset_identity,sha256:'new-data'},interpreter_identity:{...v1.interpreter_identity,sha256:'new-python'},
    case_config:{generated_program:{...v1.case_config.generated_program,result_kind:'normalization',parameters:{tmax:13}},
      method_dependencies:[{id:'fit',revision:2,sha256:'new-method'}]}};
  assert.deepEqual(planDiff(v1,v1), []);
  assert.deepEqual(planDiff({case_config:{method_dependencies:'unresolved'}},{}).map(row=>row.before), [['unresolved']]);
  assert.deepEqual(planDiff(v1,v2).map(row => [row.group,row.section,row.before,row.after]), [
    ['Scientific plan','Decision criteria',['Choose a central value'],['Compare windows']],
    ['Execution bindings','Data content SHA-256',['old-data'],['new-data']],
    ['Execution bindings','Interpreter SHA-256',['old-python'],['new-python']],
    ['Execution bindings','Result type',['c2'],['normalization']],
    ['Execution bindings','Frozen parameters',['tmax = 12'],['tmax = 13']],
    ['Execution bindings','Requested method versions',[JSON.stringify(v1.case_config.method_dependencies[0])],
      [JSON.stringify(v2.case_config.method_dependencies[0])]],
  ]);
});

test('registered CSV execution overrides and validation inputs are visible independently of program selection', () => {
  const plan = {case_config:{analysis_program_tags:['two_point'], expected_outputs:['effective_mass.json'],
    golden_reference_files:['reference.json'], golden_example_root:'reference-v1'}};
  const revised = {...plan.case_config, analysis_commands:['mock:fit'], allowed_analysis_commands:['mock:fit'],
    analysis_program_tags:['correlator'], expected_outputs:['fit.json'], golden_reference_files:['fit-reference.json'],
    golden_example_root:'reference-v2'};
  const rows = planDiff(plan,{case_config:revised});
  assert.deepEqual(rows.map(row=>[row.section,row.before,row.after]), [
    ['Requested program tags',['two_point'],['correlator']], ['Explicit analysis commands',[],['mock:fit']],
    ['Allowed analysis commands',[],['mock:fit']], ['Configured output checks',['effective_mass.json'],['fit.json']],
    ['Reference files',['reference.json'],['fit-reference.json']], ['Reference directory',['reference-v1'],['reference-v2']],
  ]);
});

test('draft scopes include Host, Project, Run and version; revision submits a single answered batch', () => {
  const scope = ['host','project','case','run','plan'], key = planDraftKey(...scope);
  scope.forEach((_,index) => {
    const other = [...scope]; other[index] += '-other'; assert.notEqual(planDraftKey(...other),key);
  });
  const draft = {answers:[{question:'Fit goal?',choice:'Stability',note:' Compare windows '},
    {question:'Scope?',choice:'',note:''}],instruction:'Keep all replicas'};
  assert.equal(planFeedback(draft),'Fit goal?\nStability — Compare windows\n\nKeep all replicas');
  assert.equal(planFeedback({answers:[],instruction:'  '}),'');
});
