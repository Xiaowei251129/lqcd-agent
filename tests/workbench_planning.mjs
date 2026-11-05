import assert from 'node:assert/strict';
import test from 'node:test';
import {planningAccess, planDiff, planFeedback} from '../src/lqcd_agent/workbench/static/planning.js';

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

test('a plan revision identifies changed science and batches the actual answers', () => {
  const v1 = {brief:{success_criteria:['Choose a central value']},assumptions:['Known ensemble']};
  const v2 = {...v1,brief:{success_criteria:['Compare windows']}};
  assert.deepEqual(planDiff(v1,v2),[{section:'Decision criteria',before:['Choose a central value'],after:['Compare windows']}]);
  assert.equal(planFeedback([{question:'Fit goal?',answer:' Compare stability '},{question:'Scope?',answer:''}],
    'Keep all replicas'),'Fit goal?\nCompare stability\n\nKeep all replicas');
});
