import assert from 'node:assert/strict';
import test from 'node:test';
import {sendControl, sendContribution, submissionSlot} from '../src/lqcd_agent/workbench/static/submissions.js';

// Model two tabs sharing one origin. Their synchronous slot updates serialize.
const stored = new Map();
Object.defineProperty(globalThis, 'localStorage', {value: {
  getItem: key => stored.get(key) ?? null,
  setItem: (key, value) => stored.set(key, value),
  removeItem: key => stored.delete(key),
}});
Object.defineProperty(globalThis, 'navigator', {value: {locks: {
  request: async (_slot, change) => change(),
}}, configurable: true});
const record = key => ({project:'p', path:'/api/runs', target:{host:'h'}, payload:{key}});
const reject = (status, code) => Object.assign(new Error(code), {status, code});

test('unverified lookup keeps the original key until its committed control operation is found', async () => {
  const slot = submissionSlot('control-offline'), a = record('a');
  await slot.claim(a);
  for (const error of [reject(403,'invalid_session'), reject(409,'control_rejected_request'), reject(404,'evidence_or_run_missing')]) {
    await assert.rejects(sendControl(slot,a,true, async (_path, body) => {
      assert.equal(body,undefined); throw error;
    }), error);
    assert.deepEqual(slot.read(),a);
  }
  const committed = await sendControl(slot,a,true, async (_path, body) => {
    assert.equal(body,undefined); return {status:'committed'};
  });
  assert.equal(committed.status,'committed'); assert.equal(slot.read(),null);
});

test('a stale action may be corrected after its rejection and an authoritative unknown-operation result', async () => {
  const slot = submissionSlot('rejected'), a = record('a');
  await slot.claim(a);
  const calls = [];
  await assert.rejects(sendControl(slot,a,true, async (path, body) => {
    calls.push([path,body]);
    throw body ? reject(409,'stale_run_action') : reject(404,'unknown_operation');
  }), /stale_run_action/);
  assert.deepEqual(calls,[['/api/operations/a',undefined],['/api/runs',a.payload],['/api/operations/a',undefined]]);
  assert.equal(slot.read(),null);
});

test('a delayed completion or stale forget in one tab preserves the newer intent in another', async () => {
  const first = submissionSlot('shared'), other = submissionSlot('shared'), a = record('a'), b = record('b');
  assert.equal((await first.claim(a)).replay,false);
  assert.deepEqual(await other.claim(b),{replay:true,record:a});
  let finish;
  const delayed = sendControl(first,a,true, () => new Promise(resolve => { finish = resolve; }));
  await other.clear('a'); await other.claim(b);
  finish({status:'committed'}); await delayed; await first.clear('a');
  assert.deepEqual(other.read(),b);
});

test('scientific input keeps its exact payload through a session failure and releases a verified stale rejection', async () => {
  const slot = submissionSlot('input'), a = record('a');
  await slot.claim(a);
  await assert.rejects(sendContribution(slot,a,async () => { throw reject(403,'invalid_session'); }), /invalid_session/);
  assert.deepEqual(slot.read(),a);
  await assert.rejects(sendContribution(slot,a,async (_path,body) => {
    if (body) throw reject(409,'stale'); throw reject(403,'invalid_session');
  }), /invalid_session/);
  assert.deepEqual(slot.read(),a);
  await assert.rejects(sendContribution(slot,a,async (_path,body) => {
    if (body) {assert.deepEqual(body,a.payload); throw reject(409,'stale');} return [];
  }), /stale/);
  assert.equal(slot.read(),null);
});

test('lost grouped reply is replayed with its own original key before the one plan revision', async () => {
  const slot = submissionSlot('plan-revision');
  const revision = {...record('revision'),target:{host:'h',project_id:'p'},
    path:'/api/projects/p/runs',feedback:{key:'note',body:'Keep failed replicas'}};
  await slot.claim(revision);
  const recorded = new Set(), launched = [];
  let loseReply = true;
  const api = async (path, body) => {
    if (path === '/api/operations/revision') throw reject(404,'unknown_operation');
    if (path.endsWith('/contributions')) {
      recorded.add(body.key);
      if (loseReply) {loseReply = false; throw Error('lost reply');}
      return {};
    }
    launched.push(body.key); return {status:'committed'};
  };
  await assert.rejects(sendControl(slot,revision,false,api), /lost reply/);
  assert.deepEqual(slot.read(),revision); assert.deepEqual(launched,[]);
  await sendControl(slot,revision,true,api);
  assert.deepEqual([...recorded],['note']); assert.deepEqual(launched,['revision']);
  assert.equal(slot.read(),null);
});
