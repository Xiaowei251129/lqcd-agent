import assert from 'node:assert/strict';
import test from 'node:test';
import {resultRecords, plotScale, formalResultSource, renderResults, replicaIdsLabel} from '../src/lqcd_agent/workbench/static/results.js';

test('an archived result citation binds its specific producer path despite shared content identity', () => {
  const file='analysis_outputs/generated_result.json';
  const expected={id:'same-bytes',slot:'analysis',current:true,source:'scientific',attempt_id:'a',name:'domain/a/c/r/'+file};
  const other={...expected,name:'domain/a/c/r/other.json'};
  const view={archived:true,run_locator:{case_id:'c',run_id:'r'},result_evidence_id:'same-bytes',evidence:[other,expected]};
  assert.equal(formalResultSource(view),expected);
  assert.equal(formalResultSource({...view,evidence:[other]}),null);
});

test('C2 compares both models on real window coordinates and cites original source indices', () => {
  const fits = [
    {nstates:2,tmin:12,tmax:18,E0:.3,E0_error:.02,chi2_dof:1,bootstrap_successes:199,bootstrap_total:200,failed_sample_ids:[7]},
    {nstates:1,tmin:4,tmax:18,E0:.5,E0_error:.05},
    {nstates:2,tmin:6,tmax:18,E0:.35,E0_error:.01},
    {nstates:1,tmin:12,tmax:18,E0:null,E0_error:null},
  ];
  const projection=resultRecords({fits},{family:'c2'});
  assert.equal(projection.plots.length,1);
  const scale=plotScale(projection.plots[0].records);
  assert.equal((scale.x(6)-scale.x(4))/(scale.x(12)-scale.x(4)),.25);
  assert(scale.high>=.55 && scale.low<=.28);
  assert.equal(scale.valid.length,3);
  assert.equal(projection.records.length,4); // The missing estimate remains in the table.
  const selected=projection.records.find(row=>row.title==='2-state fit · [12, 18]');
  assert.equal(selected.context,'fits[0]: 2-state fit, t/a = [12, 18]');
  assert.deepEqual(selected.failed,[7]);
  const fixed=resultRecords({fits:[{...fits[0],E0_error:0}],ground_energy_fixed:true},{family:'c2'});
  assert.match(fixed.note,/conditional on the input constraint/);
  assert.equal(fixed.records[0].cells[3],'0');
  assert.equal(plotScale(fixed.records).y(.3),50);
});

test('normalization retains missing estimates and failure masks for the exact mode and separation', () => {
  const result={results:[
    {mode:'mode2',bz:1,sample_id:11,success:false},{mode:'mode2',bz:1,sample_id:12,success:true},
    {mode:'mode3',bz:1,sample_id:12,success:false},{mode:'mode3',bz:2,sample_id:13,success:false}],
    summaries:[
      {mode:'mode2',bz:1,component:'real',n_valid:1,mean:0,error:0},
      {mode:'mode3',bz:1,component:'imag',n_valid:0,mean:null,error:null}]};
  const projection=resultRecords(result,{family:'normalization'});
  const [real,imag]=projection.records;
  assert.deepEqual(real.failed,[11]);
  assert.deepEqual(imag.failed,[12]);
  assert.equal(real.cells[3],'0');assert.equal(imag.cells[3],'Not recorded');
  assert.equal(plotScale(projection.plots[1].records),null);
});

test('replica observables keep separate units, typed IDs and deliberately absent uncertainties', () => {
  const result={observables:[{id:'matrix',samples:[{sample_id:'7',value:null},{sample_id:7,value:3}],mean:null,error:null}]};
  const projection=resultRecords(result,{family:'replica_observables',
    observable_contracts:[{id:'matrix',definition:'Matrix element',group:'blocked',unit:'dimensionless',kinematics:{pz:1}}],
    replica_groups:[{id:'blocked',method:'jackknife',provenance:'Original ensemble blocks'}]});
  const [record]=projection.records;
  assert.equal(record.cells[1],'dimensionless');assert.equal(record.cells[4],'1 / 2');
  assert(record.metadata.some(([k,v])=>k==='Resampling' && v==='jackknife'));
  assert.deepEqual(record.failed,['7']);assert.match(record.detail,/Estimate unavailable/);
  assert.equal(replicaIdsLabel([7,'7']), '[7,"7"]');
  assert.match(replicaIdsLabel(JSON.parse('[9223372036854775807]')),/source record/);
});

test('opening preparation before formal output exists leaves an empty results area', () => {
  let cleared = 0;
  const container = {replaceChildren(){cleared++;}};
  const view = {run_locator:{case_id:'intake',run_id:'first'},summaries:{},evidence:[]};
  renderResults(container,view,{});
  renderResults(container,view,{});
  assert.equal(cleared,1);
});
