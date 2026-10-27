import React, { useState } from 'react';
import type { RecoveryRequest, RecoveryReply, RecoveryBranch } from '../../contracts/recovery';
export function Recovery({ locked }: { locked: boolean }) {
  const [reply, setReply] = useState<RecoveryReply>();
  const [branches, setBranches] = useState<RecoveryBranch[]>([]);
  const [selected, setSelected] = useState<RecoveryBranch>();
  const [revision, setRevision] = useState('');
  const [name, setName] = useState('Migrated comparison');
  const [archive, setArchive] = useState(false);
  const [item, setItem] = useState(0);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [uncertain, setUncertain] = useState<RecoveryRequest>();
  async function act(action: RecoveryRequest['action'], detail_offset = 0) {
    const query: RecoveryRequest = uncertain ?? { recovery_contract: 1, action, context: selected ? { ...selected.context, revision_id: revision || selected.context.revision_id } : null, offset: action === 'archive-open' ? 0 : item, detail_offset, name };
    setBusy(true); setError('');
    try {
      const result = await window.poliscope.recovery(query); setReply(result); setUncertain(undefined);
      if (action === 'inspect' && result.status === 'complete') { setBranches(result.branches ?? []); setSelected(undefined); setRevision(''); setArchive(false); }
      if (action === 'archive-open' && result.status === 'complete') { setArchive(true); setBranches([]); setSelected(undefined); setRevision(''); }
    } catch {
      if (['migrate-model', 'archive-migrate'].includes(query.action)) setUncertain(query);
      setError('Request unconfirmed. Your original history is preserved. Retry the identical migration to recover its saved outcome; do not reset the civilization.');
    } finally { setBusy(false); }
  }
  return <section aria-label="Recovery and historical inspection"><h2>Recovery and historical inspection</h2>
    <p>Open a database or portable archive even when the simulation engine is unavailable. All inspection is read only: retained evidence is not freshly reproduced. Computation and edits are unavailable here.</p>
    <p>Backups include confirmed history, accepted results, redaction status and operation replay identities. Separate private notes, rationale payloads and keys are excluded. Deleted private payloads and derivatives are removed from active stores; older backups, WAL files, filesystem recovery and shared copies may retain material. Dispose of backups yourself when appropriate; secure erasure is not promised.</p>
    <fieldset disabled={busy || locked || Boolean(uncertain)}><legend>Select and preserve history</legend>
      <button onClick={() => void act('inspect')}>Inspect database without model</button>
      <button onClick={() => { setItem(0); void act('archive-open'); }}>Inspect archive without model</button>
      {!archive && branches.length > 0 && <>
        <label>Historical branch<select value={selected ? branches.indexOf(selected) : ''} onChange={e => { const b = branches[Number(e.target.value)]; setSelected(b); setRevision(b?.context.revision_id ?? ''); }}>
          <option value="">Choose branch</option>{branches.map((b,i) => <option key={JSON.stringify(b.context)} value={i}>{b.name} · {b.model_id} · {b.execution}</option>)}
        </select></label>
        <label>Retained revision ID<input value={revision} maxLength={128} onChange={e => setRevision(e.target.value)} /></label>
        <button disabled={!selected} onClick={() => void act('read')}>Read retained revision</button>
      </>}
      {!archive && <><button onClick={() => void act('backup')}>Back up selected database</button>
        <button onClick={() => void act('restore')}>Restore selected backup into new folder</button>
        <button onClick={() => void act('migrate-schema')}>Back up and upgrade schema 1 to 2</button></>}
      {archive && <><label>Archive entry number<input type="number" min={0} max={10000} value={item} onChange={e => setItem(Number(e.target.value))} /></label>
        <button onClick={() => void act('archive-read')}>Read archive entry</button></>}
      <label>New comparison branch name<input value={name} maxLength={256} onChange={e => setName(e.target.value)} /></label>
      <p>Explicit migration validates the selected design against the installed workspace model, then computes new results on a separate comparison branch. Missing mechanisms are rejected. Original branches and historical results remain readable. This is a new computation, not reproduction of the old result.</p>
      <button disabled={!name.trim() || (!archive && !selected)} onClick={() => void act(archive ? 'archive-migrate' : 'migrate-model')}>Create compatible model comparison</button>
    </fieldset>
    {busy && <p role="status">Reading or preserving local history…</p>}
    {error && <p role="alert">{error}</p>}
    {uncertain && <button disabled={busy} onClick={() => void act(uncertain.action)}>Retry identical migration</button>}
    {reply && <><p role={reply.status === 'failed' ? 'alert' : 'status'}>{reply.status}: {reply.diagnostic}. {reply.detail}</p>
      <table><caption>Retained historical facts</caption><thead><tr><th scope="col">Fact</th><th scope="col">Value</th></tr></thead><tbody>{(reply.rows ?? []).map((r,i) => <tr key={i}><th scope="row">{r.label}</th><td style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{r.detail}</td></tr>)}</tbody></table>
      {reply.next_offset !== null && <button disabled={busy || locked} onClick={() => void act(archive ? 'archive-read' : 'read', reply.next_offset!)}>More retained facts</button>}
    </>}
  </section>;
}
