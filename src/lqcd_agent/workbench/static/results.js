// Present sealed Analysis outputs. The browser does not fit, combine or grade estimates.
const finite = Number.isFinite;
const list = value => Array.isArray(value) ? value : [];
const number = value => finite(value) ? String(Number(value.toPrecision(6))) : 'Not recorded';
const element = (tag, className, ...children) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  node.append(...children);
  return node;
};
const button = (label, className, action) => {
  const node = element('button', className, label);
  node.type = 'button'; node.addEventListener('click', action);
  return node;
};
const pair = (mean, error) => finite(mean) && finite(error) ? number(mean)+' ± '+number(error) : 'Estimate unavailable';
const counts = (valid, total) => finite(valid) && finite(total) ? valid+' / '+total : 'Not recorded';

// Keep the original array index for citations when presenting a different sort order.
export function resultRecords(result, basis) {
  if (basis.family === 'c2') {
    const records = list(result.fits).map((fit, index) => {
      const window = '['+number(fit.tmin)+', '+number(fit.tmax)+']';
      const group = number(fit.nstates)+'-state';
      return {pointer: '/fits/'+index, fields: Object.keys(fit), context: 'fits['+index+']: '+group+' fit, t/a = '+window,
        key: index, title: group+' fit · '+window, cells: [window, group, number(fit.E0), number(fit.E0_error),
          number(fit.chi2_dof), counts(fit.bootstrap_successes, fit.bootstrap_total)],
        x: fit.tmin, end: fit.tmax, series: fit.nstates, y: fit.E0, error: fit.E0_error,
        detail: 'aE₀ = '+pair(fit.E0, fit.E0_error)+' · χ²/dof = '+number(fit.chi2_dof)+
          ' · valid replicas '+counts(fit.bootstrap_successes, fit.bootstrap_total), failed: fit.failed_sample_ids};
    }).sort((a,b)=>a.end-b.end || a.x-b.x || a.series-b.series);
    return {title:'C2 fit-window stability', headers:['Window t/a','Model','aE₀','σ(aE₀)','χ²/dof','Valid / total'], records,
      note: result.ground_energy_fixed === true ? 'Fixed ground energy. The estimate and its uncertainty are conditional on the input constraint. This fit does not independently test dispersion.' : '',
      plots: [...new Set(records.map(r=>r.end))].map(end=>({name:'Window end tmax/a = '+number(end),
        horizontal:'Window start tmin/a', vertical:'Ground-state energy aE₀ ± bootstrap uncertainty', series:[1,2], labels:['1-state','2-state'],
        records: records.filter(r=>r.end===end)}))};
  }
  if (basis.family === 'normalization') {
    // Both complex components share the exact paired replica mask for each mode and separation.
    const failures = new Map();
    for (const sample of list(result.results)) {
      if (sample.success !== false) continue;
      const key = JSON.stringify([sample.mode,sample.bz]);
      if (!failures.has(key)) failures.set(key,[]);
      failures.get(key).push(sample.sample_id);
    }
    const records = list(result.summaries).map((row,index)=>{
      const label = row.mode+' · '+row.component+' · bᶻ = '+number(row.bz);
      return {context:'summaries['+index+']: '+label, key:index, title:label,
        cells:[row.mode,number(row.bz),row.component,number(row.mean),number(row.error),number(row.n_valid)],
        x:row.bz,y:row.mean,error:row.error,series:row.mode,component:row.component,
        detail:'16–84% percentile midpoint ± half-width: '+pair(row.mean,row.error)+' · valid paired replicas '+number(row.n_valid),
        failed:Array.isArray(result.results) ? (failures.get(JSON.stringify([row.mode,row.bz])) || []) : null};
    }).sort((a,b)=>a.x-b.x || a.series.localeCompare(b.series) || a.component.localeCompare(b.component));
    return {title:'Complex normalization',headers:['Mode','bᶻ','Component','Midpoint','Half-width','Valid replicas'],records,
      plots:['real','imag'].map(component=>({name:component === 'real' ? 'Real component' : 'Imaginary component',
        horizontal:'Recorded separation bᶻ',vertical:'16–84% midpoint ± half-width',
        series:['mode2','mode3'],labels:['Mode 2','Mode 3'],records:records.filter(r=>r.component===component)}))};
  }
  if (basis.family === 'replica_observables') {
    const contracts = new Map(list(basis.observable_contracts).map(c=>[c.id,c]));
    const groups = new Map(list(basis.replica_groups).map(g=>[g.id,g]));
    const records = list(result.observables).map((row,index)=>{
      const contract = contracts.get(row.id), group = groups.get(contract?.group);
      const failed = Array.isArray(row.samples) ? row.samples.filter(r=>r.value===null).map(r=>r.sample_id) : null;
      const replicas = failed ? counts(row.samples.length-failed.length,row.samples.length) : 'Not recorded';
      return {context:'observables['+index+']: '+row.id,key:index,title:row.id,
        cells:[row.id,contract?.unit || 'Not recorded',number(row.mean),number(row.error),replicas],
        detail:pair(row.mean,row.error)+(contract ? ' '+contract.unit : '')+' · valid replicas '+replicas,
        metadata:[['Definition',contract?.definition],['Kinematics',contract && JSON.stringify(contract.kinematics)],
          ['Replica group',contract?.group],['Resampling',group?.method],['Provenance',group?.provenance]],failed};
    });
    return {title:'Replica observables',headers:['Observable','Unit','Mean','Error','Valid / total'],records,plots:[]};
  }
  return {title:'Formal analysis output',headers:[],records:[],plots:[]};
}

// Use the real abscissa and a common domain covering every displayed error bar.
export function plotScale(records) {
  const valid = records.filter(r=>finite(r.x) && finite(r.y) && finite(r.error) && r.error>=0 &&
    finite(r.y-r.error) && finite(r.y+r.error));
  if (!valid.length) return null;
  const xs = [...new Set(valid.map(r=>r.x))].sort((a,b)=>a-b);
  let low = Infinity, high = -Infinity;
  for (const r of valid) {low = Math.min(low, r.y-r.error); high = Math.max(high, r.y+r.error);}
  const span = high-low || Math.max(Math.abs(high)*.1,.001);
  low -= span*.1; high += span*.1;
  if (!finite(high-low)) return null;
  const xmin=xs[0], xmax=xs.at(-1);
  const x = v=>xmax===xmin ? 50 : 5+90*(v-xmin)/(xmax-xmin);
  const y = v=>100*(high-v)/(high-low);
  const ticks = [xmin];
  for (const v of xs.slice(1,-1)) {
    if (x(v)-x(ticks.at(-1)) >= 20 && x(xmax)-x(v)>=20) ticks.push(v);
  }
  if (xmax!==xmin) ticks.push(xmax);
  return {valid, x, y, ticks, low, high};
}

function intervalPlot(model, select) {
  const figure=element('figure','result-plot',element('figcaption',null,model.name));
  const scale=plotScale(model.records);
  if (!scale) {figure.append(element('p','result-muted','No finite error bars to draw. See the recorded values below.'));return figure;}
  const legend=element('div','result-legend');
  model.labels.forEach((label,i)=>legend.append(element('span',null,
    element('i','result-symbol series-'+i),label)));
  const frame=element('div','result-frame');
  figure.append(legend,element('div','result-axis-title',model.vertical),frame);
  for (const part of [0,.5,1]) {
    const tick=element('div','result-gridline',element('span',null,number(scale.high-part*(scale.high-scale.low))));
    tick.style.top=(100*part)+'%';frame.append(tick);
  }
  for (const value of scale.ticks) {
    const tick=element('span','result-x-tick',number(value));tick.style.left=scale.x(value)+'%';frame.append(tick);
  }
  for (const r of scale.valid) {
    const x=scale.x(r.x)+'%', series='series-'+model.series.indexOf(r.series);
    const whisker=element('span','result-whisker '+series);
    whisker.style.left=x;whisker.style.top=scale.y(r.y+r.error)+'%';
    whisker.style.height=(scale.y(r.y-r.error)-scale.y(r.y+r.error))+'%';
    const mark=button('','result-mark '+series,()=>select(r));mark.dataset.record=String(r.key);
    mark.setAttribute('aria-label',r.title+', '+model.vertical+', '+pair(r.y,r.error));mark.title=mark.getAttribute('aria-label');
    mark.style.left=x;mark.style.top=scale.y(r.y)+'%';frame.append(whisker,mark);
  }
  figure.append(element('div','result-x-title',model.horizontal));
  return figure;
}

function sourceActions(source, context, state, pointer) {
  const bar=element('div','result-actions');
  bar.append(button('View source record','result-link',()=>state.actions.openEvidence(source,context,pointer)));
  if (state.actions.contribute) bar.append(button('Discuss this record','result-link',()=>state.actions.contribute(source,context)));
  return bar;
}

export function replicaIdsLabel(ids) {
  if (!Array.isArray(ids)) return 'Not recorded';
  // Parsed JSON can round a numeric ID outside the browser's safe integer range.
  if (ids.some(id=>typeof id==='number' && !Number.isSafeInteger(id))) return 'Open the source record to read the exact replica IDs.';
  return ids.length ? JSON.stringify(ids) : 'None recorded';
}

function recordInspector(node, record, source, state) {
  node.replaceChildren(element('h4',null,record.title),element('p',null,record.detail));
  const meta=element('dl','result-meta');
  for (const [label,value] of record.metadata || []) if (value) meta.append(element('dt',null,label),element('dd',null,value));
  meta.append(element('dt',null,'Failed replica IDs'),element('dd',null,replicaIdsLabel(record.failed)));
  node.append(meta,sourceActions(source,record.context,state,record.pointer));
  if (record.pointer && state.actions.correct) {
    const field = element('select');
    field.setAttribute('aria-label','Correction target');
    const options = [['','Whole fit'],['E0','Ground-state energy'],['E0_error','Ground-state uncertainty'],
      ['chi2_dof','χ²/dof'],['tmin','Window start'],['tmax','Window end'],['nstates','State count'],
      ['bootstrap_successes','Successful replicas'],['bootstrap_total','Total replicas'],['failed_sample_ids','Failed replica IDs']];
    for (const [key,label] of options) {
      if (key && !record.fields.includes(key)) continue;
      const option = element('option',null,label);
      option.value = key ? record.pointer+'/'+key : record.pointer;
      field.append(option);
    }
    node.append(element('div','result-actions',field,
      button('Record a correction','result-link',()=>state.actions.correct(source,field.value))));
  }
}

const displayed = new WeakMap();
export function formalResultSource(view) {
  if (!view.result_evidence_id) return null;
  const filename='analysis_outputs/generated_result.json';
  // Archived member IDs are content hashes. Equal bytes can have other producers.
  const matches=list(view.evidence).filter(item=>item.id===view.result_evidence_id && item.current &&
    item.slot==='analysis' && item.source==='scientific' && item.name===(view.archived
      ? ['domain',item.attempt_id,view.run_locator.case_id,view.run_locator.run_id,filename].join('/')
      : filename));
  return matches.length===1 ? matches[0] : null;
}

export function renderC2Conclusion(container, view, reader) {
  container.replaceChildren();
  const chain = view.summaries?.['memory_update.json']?.c2_evidence;
  const source = formalResultSource(view);
  if (!chain) {
    if (source && view.comparison_basis?.family === 'c2' && view.summaries?.['memory_update.json']) {
      container.append(element('p','result-muted','This report contains no structured fit selection or criterion citations.'));
    }
    return;
  }
  if (!source || source.sha256 !== chain.result_sha256) {
    container.append(element('p','result-warning','Could not verify the Analysis source for the recorded decision.'));
    return;
  }
  const fits = new Map(chain.fits.map(row=>[row.pointer,row]));
  const fitLink = (row) => button(row.nstates+'-state ['+row.tmin+', '+row.tmax+'] · '+row.estimate+
    ' · replicas '+row.replicas,'result-link',()=>reader.open(source,'Sealed C2 fit',row.pointer));
  const preferred = fits.get(chain.selection.fit_pointer);
  container.append(element('h3',null,'Fit selection'));
  if (chain.selection.status === 'selected' && preferred) {
    container.append(element('p',null,'Research Manager’s preferred fit · ',fitLink(preferred)));
  } else {
    container.append(element('p',null,chain.selection.status === 'no_preference'
      ? 'The Research Manager reported no preferred ground-state energy.' : 'Fit preference was not assessed.'));
  }
  if (chain.fixed_ground_energy) container.append(element('p','result-warning','Fixed ground energy. The quoted uncertainty is conditional on the input constraint.'));
  if (!chain.criteria.length) return;
  container.append(element('h3',null,'Scientific decision criteria'));
  const plan = list(view.evidence).find(item=>item.sha256===chain.plan_sha256 && item.name.endsWith('method_plan.json'));
  const rows = element('ol','criterion-list');
  for (const criterion of chain.criteria) {
    const row = element('li',null,element('strong',null,criterion.text),element('p',null,
      criterion.assessment ? 'Research Manager assessment · '+criterion.assessment : 'No recorded assessment'));
    if (plan || view.project_id) row.append(button('Read selected criterion','result-link',()=>plan
      ? reader.open(plan,'Selected plan criterion',criterion.pointer)
      : reader.openSaved(view.project_id,chain.plan_sha256,'Selected plan criterion',criterion.pointer)));
    for (const pointer of criterion.fit_pointers) {
      if (fits.has(pointer)) row.append(fitLink(fits.get(pointer)));
    }
    rows.append(row);
  }
  container.append(rows);
}

export function resultWarnings(view, source=formalResultSource(view)) {
  const review=view.summaries?.['scientific_review_report.json']?.generated_diagnostics;
  return source && list(review?.evidence).some(e=>e.field==='sha256' && e.value===source.sha256)
    ? list(review.warnings).filter(w=>w.message) : [];
}

export function renderResults(container, view, actions) {
  const result=view.summaries?.['generated_result.json'];
  const source=formalResultSource(view);
  const warnings=resultWarnings(view,source);
  const basis=view.comparison_basis || {};
  const previous=displayed.get(container);
  const origin=JSON.stringify([view.host,view.run_locator,source?.id]);
  const key=JSON.stringify([origin,source?.sha256,Boolean(result),warnings,
    basis.family,Boolean(actions.contribute),Boolean(actions.correct)]);
  if (previous?.key===key) {previous.actions=actions;return;}
  const state={key,origin,actions,selected:previous?.origin===origin ? previous.selected : null};
  displayed.set(container,state);container.replaceChildren();
  if (!result) return;
  if (!source) {
    container.append(element('p','result-warning','The current result has no unique registered Analysis source.'));
    return;
  }
  const invalid = warnings.find(w=>w.code==='generated_output_invalid');
  if (invalid) {
    container.append(element('p','result-warning','Host numerical validation failed. '+invalid.message),
      sourceActions(source,'Formal analysis output',state));return;
  }
  let model;
  try {model=resultRecords(result,basis);}
  catch (error) {
    if (!(error instanceof TypeError)) throw error;
    container.append(element('p','result-warning','The stored result could not be displayed with the declared contract.'),
      sourceActions(source,'Formal analysis output',state));return;
  }
  const section=element('section','result-view',element('h3',null,model.title));container.append(section);
  if (model.note) section.append(element('p','result-warning',model.note));
  for (const warning of warnings) {
    if (model.note && warning.code==='fixed_energy_constraint') continue;
    section.append(element('p','result-warning','Host finding · '+warning.message));
  }
  for (const note of [...list(result.assumptions),...list(result.limitations),...list(result.warnings)]) {
    if (typeof note==='string') section.append(element('p','result-muted',note));
  }
  if (!model.records.length) {
    section.append(element('p','result-muted',result.status==='needs_more_info' ? 'Additional input is required. No estimate was produced.' :
      'No tabulated estimates in this result.'),sourceActions(source,'Formal analysis output',state));return;
  }
  const inspector=element('div','result-inspector');inspector.setAttribute('aria-live','polite');
  function select(record) {
    state.selected=record.key;
    for (const choice of section.querySelectorAll('[data-record]')) choice.setAttribute('aria-pressed',String(choice.dataset.record===String(record.key)));
    recordInspector(inspector,record,source,state);
  }
  const plots=element('div','result-plots');
  for (const plot of model.plots) plots.append(intervalPlot(plot,select));
  if (model.plots.length) section.append(element('div','result-grid',plots,inspector));
  else section.append(inspector);
  const table=element('table','result-table'), row=element('tr');
  for (const label of model.headers) {const th=element('th',null,label);th.scope='col';row.append(th);}
  table.setAttribute('aria-label',model.title+' records');
  const body=element('tbody');table.append(element('thead',null,row),body);
  for (const record of model.records) {
    const choose=button(record.cells[0],'result-record',()=>select(record));
    choose.dataset.record=String(record.key);choose.setAttribute('aria-label','Inspect '+record.title);
    body.append(element('tr',null,element('td',null,choose),...record.cells.slice(1).map(v=>element('td',null,v))));
  }
  section.append(element('div','result-table-wrap',table));
  select(model.records.find(r=>r.key===state.selected) || model.records[0]);
}
