// Resolve links only against this Run's verified registry, including historical versions.
export function referencedMember(view, reference) {
  const matches = view.evidence.filter(item => item.id === reference || item.sha256 === reference);
  return matches.length === 1 ? matches[0] : null;
}

export function summaryMember(view, filename) {
  const matches = view.evidence.filter(item => item.current && item.name.split('/').at(-1) === filename &&
    (item.source === 'scientific' || filename === 'memory_update.json'));
  return matches.length === 1 ? matches[0] : null;
}

export function evidenceButton(label, action) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'text-button';
  button.textContent = label;
  button.addEventListener('click', action);
  return button;
}

export function evidenceReader({getView, load, loadSaved, attach, onError}) {
  const byId = id => document.getElementById(id);
  const pane = byId('preview');
  let opened = null;

  function close(restoreFocus = true) {
    if (!opened) return;
    const {trigger} = opened;
    opened = null;
    pane.hidden = true;
    byId('preview-text').textContent = '';
    if (restoreFocus && trigger?.isConnected) trigger.focus();
  }

  async function show(item, context, read, attachable, pointer) {
    const entry = {item, context, trigger: document.activeElement};
    opened = entry;
    pane.hidden = false;
    byId('preview-name').textContent = context || item.name;
    byId('preview-hash').textContent = 'SHA-256 '+item.sha256;
    byId('preview-text').textContent = 'Reading registered evidence…';
    byId('preview-comment').hidden = true;
    byId('preview-back').focus();
    try {
      const content = await read();
      if (opened !== entry) return;
      if (content.sha256 !== item.sha256) throw new Error('The evidence identity changed. Refresh this investigation.');
      const name = item.name || content.name;
      let preview = content.text;
      if (pointer) {
        // Retain original numeric tokens, including replica IDs beyond Number's safe range.
        const preserve = typeof JSON.rawJSON === 'function';
        let field = JSON.parse(content.text, preserve ? (_, value, token) =>
          typeof value === 'number' ? JSON.rawJSON(token.source) : value : undefined);
        for (const key of pointer.slice(1).split('/').map(part => part.replaceAll('~1','/').replaceAll('~0','~'))) {
          if (!field || typeof field !== 'object' || !Object.hasOwn(field,key)) throw new Error('The cited field is absent: '+pointer);
          field = field[key];
        }
        preview = pointer+'\n'+(preserve ? JSON.stringify(field,null,2)+'\n\n' : '')+'Full registered source\n'+content.text;
      }
      byId('preview-text').textContent = preview;
      byId('preview-hash').textContent = name+' · SHA-256 '+content.sha256;
      entry.attachable = attachable;
      byId('preview-comment').hidden = !attachable;
    } catch (error) {
      if (opened !== entry) return;
      byId('preview-text').textContent = 'Evidence unavailable: '+error.message;
      onError(error.message);
    }
  }

  function open(item, context = '', pointer) {
    const {view, locator, verified} = getView();
    if (!verified || !view?.evidence.some(row => row.id === item.id && row.sha256 === item.sha256)) return;
    return show(item, context, () => load(view, locator, item), Boolean(locator.project_id), pointer);
  }

  function openSaved(project, hash, context, pointer) {
    return show({sha256: hash}, context, () => loadSaved(project, hash), false, pointer);
  }

  byId('preview-back').addEventListener('click', () => close());
  byId('close-preview').addEventListener('click', () => close());
  byId('preview-comment').addEventListener('click', () => {
    if (!opened?.attachable || !getView().verified) return;
    attach(opened.item, opened.context || opened.item.name);
  });
  return {open, openSaved, close};
}
