import {formalResultSource, resultRecords, resultWarnings} from './results.js';

const element = (tag, text) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  return node;
};
const label = view => view.run_locator.case_id+' / '+view.run_locator.run_id;
const present = value => value == null ? 'Not recorded' : String(value);

function table(headers, rows) {
  const wrap = element('div'), grid = element('table');
  wrap.className = 'result-table-wrap'; grid.className = 'result-table';
  const heading = grid.createTHead().insertRow();
  for (const text of headers) {
    const cell = element('th', text); cell.scope = 'col'; heading.append(cell);
  }
  const body = grid.createTBody();
  for (const values of rows) {
    const row = body.insertRow();
    for (const value of values) row.insertCell().textContent = present(value);
  }
  wrap.append(grid); return wrap;
}

function recordsByIdentity(view) {
  const basis = view.comparison_basis, result = view.summaries['generated_result.json'];
  const rows = new Map();
  for (const record of resultRecords(result, basis).records) {
    let key;
    if (basis.family === 'c2') {
      const fit = result.fits[record.key]; key = [fit.nstates, fit.tmin, fit.tmax];
    } else if (basis.family === 'normalization') {
      const row = result.summaries[record.key]; key = [row.mode, row.bz, row.component];
    } else {
      key = [result.observables[record.key].id];
    }
    const identity = JSON.stringify(key);
    if (key.some(v => v == null) || rows.has(identity)) throw new Error('Ambiguous numerical row identity.');
    rows.set(identity, record);
  }
  return rows;
}

export function alignedRows(current, other) {
  for (const [name, view] of [['Selected Run', current], ['Comparison Run', other]]) {
    const invalid = resultWarnings(view).find(warning => warning.code === 'generated_output_invalid');
    if (invalid) throw new Error(name+' failed the Host numerical check: '+invalid.message);
  }
  const left = current.comparison_basis, right = other.comparison_basis;
  if (!left.alignment_sha256 || left.family !== right.family || left.alignment_sha256 !== right.alignment_sha256) {
    return null;
  }
  const a = recordsByIdentity(current), b = recordsByIdentity(other);
  return [...new Set([...a.keys(), ...b.keys()])].map(key => {
    const first = a.get(key), second = b.get(key);
    return [(first || second).title, first?.detail, second?.detail];
  });
}

function compare(output, current, other, openRun) {
  const left = current.comparison_basis, right = other.comparison_basis;
  const source = formalResultSource(other);
  if (!source || !right || !other.summaries?.['generated_result.json']) {
    output.replaceChildren(element('p','No current, registered numerical output is available for the comparison Run.'));
    return;
  }
  const identity = element('details');
  identity.append(element('summary','Input and output identities'));
  const names = new Set([...Object.keys(left.dimensions), ...Object.keys(right.dimensions)]);
  const dimensions = [...names].map(name => [name, left.dimensions[name], right.dimensions[name]]);
  const program = v => v.summaries['run_result.json']?.generated_execution?.execution?.program_sha256;
  const headers = ['Identity','Selected Run','Comparison Run'];
  identity.append(table(headers, [['Run',label(current),label(other)],['Family',left.family,right.family],
    ...dimensions,['Program SHA-256',program(current),program(other)],
    ['Output SHA-256',formalResultSource(current).sha256,source.sha256]]));
  const link = element('a','Inspect comparison Run and evidence');
  link.href = '?'+new URLSearchParams({project:other.project_id, project_run:other.project_run_key});
  link.addEventListener('click', event => {
    if (event.metaKey || event.ctrlKey || event.altKey || event.shiftKey || event.button !== 0) return;
    event.preventDefault(); openRun(other);
  });
  identity.append(link);
  output.replaceChildren(identity);
  let records;
  try {
    records = alignedRows(current, other);
  } catch (error) {
    output.prepend(element('p',error.message)); identity.open = true; return;
  }
  if (records === null) {
    const differences = dimensions.filter(([,a,b]) => a == null || b == null || a !== b).map(([k]) => k);
    if (left.family !== right.family) differences.unshift('Analysis family');
    output.prepend(element('p','Row comparison unavailable. Missing or different identities: '+differences.join(', ')+'.'));
    identity.open = true;
    return;
  }
  if (!records.length) {output.append(element('p','Neither output contains numerical rows.'));return;}
  output.append(table(['Recorded quantity',label(current),label(other)], records),
    element('p','Each estimate retains the Run’s original valid replicas and uncertainty.'));
}

const displayed = new WeakMap();
export function renderComparison(container, view, projectRuns, loadRun, openRun) {
  const currentKey = view.project_run_key;
  const enabled = currentKey && view.project_id && view.run_status === 'completed' &&
    view.workflow === 'scientific' && formalResultSource(view) && view.comparison_basis;
  const peers = enabled ? projectRuns.filter(row => row.project_id === view.project_id &&
    row.project_run_key && row.project_run_key !== currentKey && row.workflow === 'scientific' &&
    row.run_status === 'completed') : [];
  if (!peers.length) {
    displayed.delete(container); container.replaceChildren(); container.hidden = true; return;
  }
  const revision = JSON.stringify([view.project_id, currentKey, view.detail_revision,
    peers.map(row => [row.project_run_key,row.sha256,row.host_available])]);
  const prior = displayed.get(container);
  if (prior?.revision === revision) return;
  const panel = element('details'), selector = element('select'), output = element('div');
  const state = {revision, currentKey, panel, selector};
  displayed.set(container, state);
  const caption = element('label','Comparison Run');
  const option = element('option','Choose a completed analysis'); option.value = ''; selector.append(option);
  for (const row of peers) {
    const option = element('option', label(row)); option.value = row.project_run_key; selector.append(option);
  }
  caption.append(selector); panel.append(element('summary','Compare analyses'),caption,output);
  container.hidden = false; container.replaceChildren(panel);
  let request = 0;
  async function select() {
    const ticket = ++request, row = peers.find(item => item.project_run_key === selector.value);
    output.replaceChildren();
    if (!row) return;
    output.append(element('p','Verifying comparison evidence…'));
    try {
      const other = await loadRun(row);
      if (displayed.get(container) !== state || ticket !== request) return;
      if (other.project_id !== view.project_id || other.project_run_key !== row.project_run_key ||
          other.run_status !== 'completed' || other.workflow !== 'scientific' || other.inspection !== 'verified') {
        throw new Error('The selected Project Run could not be verified.');
      }
      compare(output, view, other, openRun);
    } catch (error) {
      if (displayed.get(container) === state && ticket === request) {
        output.replaceChildren(element('p', 'Comparison unavailable. '+error.message));
      }
    }
  }
  selector.addEventListener('change',select);
  if (prior?.currentKey === currentKey) {
    panel.open = prior.panel.open;
    if (peers.some(row => row.project_run_key === prior.selector.value)) {
      selector.value = prior.selector.value; void select();
    }
  }
}
