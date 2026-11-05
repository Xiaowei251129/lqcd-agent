import assert from 'node:assert/strict';
import test from 'node:test';
import {evidenceReader} from '../src/lqcd_agent/workbench/static/evidence.js';

test('cited evidence preserves exact numeric text and a late read cannot replace another citation', async t => {
  const controls = new Map();
  const byId = id => {
    if (!controls.has(id)) controls.set(id, {addEventListener() {}, focus() {}});
    return controls.get(id);
  };
  globalThis.document = {getElementById: byId};
  t.after(() => { delete globalThis.document; });
  let finishEarlier;
  const earlier = new Promise(resolve => { finishEarlier = resolve; });
  const text = '{"sample_id":9007199254740993,"estimate":1e-999}\n';
  const reader = evidenceReader({
    loadSaved: (_, hash) => hash === 'earlier' ? earlier : {name:'record.json', sha256:hash, text},
    onError: error => assert.fail(error),
  });
  const opening = reader.openSaved('project', 'earlier', 'First citation');
  await reader.openSaved('project', 'current', 'Second citation');
  finishEarlier({name:'old.json', sha256:'earlier', text:'{}'});
  await opening;
  assert.equal(byId('preview-text').textContent, text);
  assert.equal(byId('preview-name').textContent, 'Second citation');
  assert.equal(byId('preview-comment').hidden, true);
});
