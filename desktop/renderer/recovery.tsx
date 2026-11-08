import React, { useState } from 'react';
import { Database, FolderInput, RotateCcw } from 'lucide-react';
import type { RecoveryRequest, RecoveryReply, RecoveryBranch } from '../../contracts/recovery';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/app/native-select';
import { Actions, DataTable, Field, Hint, SubHeading, Toolbar } from '@/components/app/form';
import { ErrorNote, Panel, StateBadge } from '@/components/app/blocks';

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
  return <section aria-label="Recovery and historical inspection" className="flex flex-col gap-4">
    <div>
      <h2 className="text-lg font-semibold tracking-tight">Recovery and historical inspection</h2>
      <Hint className="mt-1 max-w-3xl">Open a database or portable archive even when the simulation engine is unavailable. All inspection is read only: retained evidence is not freshly reproduced. Computation and edits are unavailable here.</Hint>
    </div>
    <Panel title="Preserve and inspect history" description="Backups include confirmed history, accepted results, redaction status and operation replay identities. Separate private notes, rationale payloads and keys are excluded."
      action={<StateBadge tone="neutral"><Database aria-hidden />Local only</StateBadge>}
      footer="Deleted private payloads and derivatives are removed from active stores; older backups, WAL files, filesystem recovery and shared copies may retain material. Dispose of backups yourself when appropriate; secure erasure is not promised.">
      <fieldset disabled={busy || locked || Boolean(uncertain)} className="m-0 min-w-0 border-0 p-0">
        <legend className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Select and preserve history</legend>
        <Actions>
          <Button variant="outline" onClick={() => void act('inspect')}><FolderInput aria-hidden />Inspect database without model</Button>
          <Button variant="outline" onClick={() => { setItem(0); void act('archive-open'); }}>Inspect archive without model</Button>
        </Actions>
        {!archive && branches.length > 0 && <div className="mt-3 flex flex-col gap-2 rounded-xl bg-muted/40 p-3">
          <SubHeading as="h5">Retained branches</SubHeading>
          <Toolbar>
            <Field label="Historical branch" className="min-w-72 flex-1">
              <NativeSelect value={selected ? branches.indexOf(selected) : ''} onChange={e => { const b = branches[Number(e.target.value)]; setSelected(b); setRevision(b?.context.revision_id ?? ''); }}>
                <option value="">Choose branch</option>{branches.map((b,i) => <option key={JSON.stringify(b.context)} value={i}>{b.name} · {b.model_id} · {b.execution}</option>)}
              </NativeSelect>
            </Field>
            <Field label="Retained revision ID" className="min-w-64 flex-1"><Input value={revision} maxLength={128} onChange={e => setRevision(e.target.value)} /></Field>
            <Button variant="outline" disabled={!selected} onClick={() => void act('read')}>Read retained revision</Button>
          </Toolbar>
        </div>}
        {!archive && <Actions className="mt-3">
          <Button variant="outline" onClick={() => void act('backup')}>Back up selected database</Button>
          <Button variant="outline" onClick={() => void act('restore')}><RotateCcw aria-hidden />Restore selected backup into new folder</Button>
          <Button variant="ghost" onClick={() => void act('migrate-schema')}>Back up and upgrade schema 1 to 2</Button>
        </Actions>}
        {archive && <Toolbar className="mt-3">
          <Field label="Archive entry number" className="w-40"><Input type="number" min={0} max={10000} value={item} onChange={e => setItem(Number(e.target.value))} /></Field>
          <Button variant="outline" onClick={() => void act('archive-read')}>Read archive entry</Button>
        </Toolbar>}
        <div className="mt-4 border-t border-border pt-3">
          <SubHeading as="h5">Explicit model migration</SubHeading>
          <Hint className="mt-1">Explicit migration validates the selected design against the installed workspace model, then computes new results on a separate comparison branch. Missing mechanisms are rejected. Original branches and historical results remain readable. This is a new computation, not reproduction of the old result.</Hint>
          <Toolbar className="mt-2">
            <Field label="New comparison branch name" className="w-72"><Input value={name} maxLength={256} onChange={e => setName(e.target.value)} /></Field>
            <Button disabled={!name.trim() || (!archive && !selected)} onClick={() => void act(archive ? 'archive-migrate' : 'migrate-model')}>Create compatible model comparison</Button>
          </Toolbar>
        </div>
      </fieldset>
      {busy && <Hint className="mt-3">Reading or preserving local history…</Hint>}
      {error && <ErrorNote title="Request unconfirmed">{error}</ErrorNote>}
      {uncertain && <Actions className="mt-3"><Button variant="outline" disabled={busy} onClick={() => void act(uncertain.action)}>Retry identical migration</Button></Actions>}
    </Panel>

    {reply && <Panel title="Retained historical facts" description="Stored facts are read from disk. Nothing here is recomputed.">
      <p role={reply.status === 'failed' ? 'alert' : 'status'} className="rounded-xl bg-muted/50 px-3 py-2 text-xs leading-relaxed">{reply.status}: {reply.diagnostic}. {reply.detail}</p>
      <DataTable className="mt-3">
        <caption>Retained historical facts</caption>
        <thead><tr><th scope="col">Fact</th><th scope="col">Value</th></tr></thead>
        <tbody>{(reply.rows ?? []).map((r,i) => <tr key={i}><th scope="row">{r.label}</th><td className="whitespace-pre-wrap break-words">{r.detail}</td></tr>)}</tbody>
      </DataTable>
      {reply.next_offset !== null && <Actions className="mt-3"><Button variant="outline" size="sm" disabled={busy || locked} onClick={() => void act(archive ? 'archive-read' : 'read', reply.next_offset!)}>More retained facts</Button></Actions>}
    </Panel>}
  </section>;
}
