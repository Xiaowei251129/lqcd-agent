import assert from 'node:assert/strict';
import test from 'node:test';
import {alignedRows} from '../src/lqcd_agent/workbench/static/comparison.js';

const view = (family, result, identity = 'same-input') => ({
  comparison_basis: {family, alignment_sha256: identity},
  summaries: {'generated_result.json':result},
});

test('C2 aligns identical models and windows in reordered scans, and preserves unmatched windows', () => {
  const fit = (n, t, e) => ({nstates:n, tmin:t, tmax:15, E0:e, E0_error:.01});
  const selected = view('c2',{fits:[fit(1,3,.3),fit(2,3,.4)]});
  const other = view('c2',{fits:[fit(2,3,.5),fit(1,4,.6),fit(1,3,.7)]});
  const rows = alignedRows(selected,other);
  assert.equal(rows.length,3);
  assert.match(rows[0][2],/0\.7 ±/);
  assert.match(rows[1][2],/0\.5 ±/);
  assert.equal(rows[2][1],undefined);
  assert.equal(alignedRows(selected,view('c2',{},null)),null);
  assert.equal(alignedRows(selected,view('c2',{},'other-sampling')),null);
});

test('normalization components and named observables use independent physical identities', () => {
  const ratio = (component,mean) => ({mode:'mode2',bz:3,component,mean,error:.02});
  const rows = alignedRows(view('normalization',{summaries:[ratio('real',.3)]}),
    view('normalization',{summaries:[ratio('imag',.3)]}));
  assert.equal(rows.length,2);
  assert.equal(rows[0][2],undefined);
  assert.equal(rows[1][1],undefined);
  const value = (id,mean) => ({id,mean,error:.1});
  const a = view('replica_observables',{observables:[value('A',1),value('B',2)]});
  const b = view('replica_observables',{observables:[value('B',3),value('A',4)]});
  assert.deepEqual(alignedRows(a,b).map(row=>[row[0],row[2].split(' ')[0]]),[['A','4'],['B','3']]);
});

test('a bound Host rejection on either side prevents displaying numerical estimates', () => {
  const rejected = view('c2',{fits:[]});
  rejected.result_evidence_id = 'formal';
  rejected.evidence = [{id:'formal',sha256:'actual',source:'scientific',slot:'analysis',current:true,
                        name:'analysis_outputs/generated_result.json'}];
  const diagnostics = {evidence:[{field:'sha256',value:'actual'}],
    warnings:[{code:'generated_output_invalid',message:'Missing original replica IDs.'}]};
  rejected.summaries['scientific_review_report.json'] = {generated_diagnostics:diagnostics};
  const other = view('c2',{fits:[]});
  assert.throws(()=>alignedRows(rejected,other),/Selected Run failed the Host numerical check/);
  assert.throws(()=>alignedRows(other,rejected),/Comparison Run failed the Host numerical check/);
  diagnostics.evidence[0].value = 'different-output';
  assert.deepEqual(alignedRows(other,rejected),[]);
});
