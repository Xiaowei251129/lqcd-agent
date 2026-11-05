// Loopback is a secure context. Lock only the synchronous, cross-tab read/write.
export function submissionSlot(name) {
  const read = () => JSON.parse(localStorage.getItem(name) || 'null');
  return {
    read,
    claim(candidate) {
      return navigator.locks.request(name, () => {
        const saved = read();
        if (saved) return {record: saved, replay: true};
        localStorage.setItem(name, JSON.stringify(candidate));
        return {record: candidate, replay: false};
      });
    },
    clear(key) {
      return navigator.locks.request(name, () => {
        if (read()?.payload.key !== key) return false;
        localStorage.removeItem(name);
        return true;
      });
    },
  };
}

const rejectedPost = error => [400, 404, 409, 413, 415, 422].includes(error.status);

export async function sendControl(slot, record, replay, api) {
  const key = record.payload.key;
  async function lookup() {
    try { return await api('/api/operations/'+encodeURIComponent(key)); }
    catch (error) {
      if (error.status === 404 && error.code === 'unknown_operation') return null;
      throw error;
    }
  }
  let operation = replay ? await lookup() : null;
  if (operation?.status !== 'committed') {
    if (slot.read()?.payload.key !== key) return null;
    try {
      // Keep the answer bundle and revision intent together across a lost reply.
      // The contribution is immutable and independently idempotent; only /runs dispatches.
      if (record.feedback) {
        await api('/api/projects/'+encodeURIComponent(record.target.project_id)+'/contributions', record.feedback);
        if (slot.read()?.payload.key !== key) return null;
      }
      operation = await api(record.path, record.payload);
    }
    catch (error) {
      if (!rejectedPost(error)) throw error;
      // An error while reading the ledger is not a rejection of the original intent.
      operation = await lookup();
      if (operation?.status !== 'committed') {
        if (!operation) await slot.clear(key);
        throw error;
      }
    }
  }
  await slot.clear(key);
  return operation;
}

export async function sendContribution(slot, record, api) {
  const path = '/api/projects/'+encodeURIComponent(record.project)+'/contributions';
  const key = record.payload.key;
  try { await api(path, record.payload); }
  catch (error) {
    if (rejectedPost(error)) {
      const entries = await api(path);
      if (!entries.some(entry => entry.key === key)) await slot.clear(key);
    }
    throw error;
  }
  await slot.clear(key);
}
