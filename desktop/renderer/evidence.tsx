import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { WorkspaceState } from '../../contracts/workspace';
import type { WorkbenchQuery, WorkbenchRow, WorkbenchEdit, WorkbenchPreview } from '../../contracts/workbench';
import type { IndicatorRow } from '../../contracts/overview';
import { Overview, valueText } from './overview';
import { Source } from './atlas';
import { Model } from './matrix';

type NoteKind = NonNullable<WorkbenchRow['note_kind']>;
export type EvidenceCollection = WorkbenchQuery['collection'] | 'results';
export function Evidence({ state, scope, onDirty, onSelected, onCompare, collection, setCollection }: {
  state: WorkspaceState; scope: string; onDirty: (dirty: boolean) => void;
  onSelected: (state: WorkspaceState) => void; onCompare: () => void;
  collection: EvidenceCollection; setCollection: (collection: EvidenceCollection) => void;
}) {
  const client = useQueryClient();
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const [draft, setDraft] = useState<'note' | 'goal' | 'assumption'>();
  const [row, setRow] = useState<WorkbenchRow>();
  const [text, setText] = useState(''); const [noteKind, setNoteKind] = useState<NoteKind>('inquiry');
  const [goalId, setGoalId] = useState(''); const [indicatorId, setIndicatorId] = useState('');
  const [operation, setOperation] = useState<'ge' | 'le' | 'eq' | 'ne' | 'gt' | 'lt'>('ge');
  const [value, setValue] = useState(''); const [remove, setRemove] = useState(false);
  const [preview, setPreview] = useState<WorkbenchPreview>();
  const [busy, setBusy] = useState(false); const [uncertain, setUncertain] = useState(false); const [error, setError] = useState('');
  const [source, setSource] = useState(''); const [model, setModel] = useState<{ id: string; version: string | null }>();
  const historical = state.context.revision_id !== state.branch.context.revision_id;
  const query: WorkbenchQuery = { context: state.context, scope_id: scope, collection: collection === 'results' ? 'references' : collection, cursor: cursors.at(-1)! };
  const data = useQuery({ queryKey: ['world', state.context, state.versions, state.effective_time, scope, 'workbench', query], retry: false, enabled: collection !== 'results', queryFn: () => window.poliscope.workbench(query) });
  const indicators = useQuery({ queryKey: ['world', state.context, scope, 'goal-indicators'], retry: false, enabled: draft === 'goal', queryFn: async () => {
    const rows: IndicatorRow[] = []; let cursor: string | null = null;
    do { const page = await window.poliscope.overview({ context: state.context, scope_id: scope, collection: 'indicators', cursor, all_scopes: false, item_id: null });
      rows.push(...page.items.filter((r): r is IndicatorRow => r.kind === 'indicator'));
      cursor = page.next_cursor; if (rows.length > 1000) throw new Error('Indicator limit');
    } while (cursor); return rows;
  } });
  function begin(kind: typeof draft, selected?: WorkbenchRow) {
    setDraft(kind); setRow(selected); setPreview(undefined); setError(''); setRemove(false); onDirty(true);
    setText(selected?.text ?? selected?.goal?.question ?? ''); setNoteKind(selected?.note_kind ?? 'inquiry');
    setGoalId(selected?.goal?.id ?? ''); setIndicatorId(selected?.goal?.indicator_id ?? '');
    setOperation(selected?.goal?.operation ?? 'ge'); setValue(selected?.goal?.threshold?.value ?? (selected?.assumption?.value.kind === 'quantity' || selected?.assumption?.value.kind === 'label' ? selected.assumption.value.value : ''));
  }
  async function showPreview() {
    setBusy(true); setError('');
    try {
      let change: WorkbenchEdit['change'];
      if (draft === 'note') change = { kind: 'note', id: row?.note?.id ?? null, text, note_kind: noteKind };
      else if (draft === 'assumption') {
        if (!row?.assumption || !['quantity','label'].includes(row.assumption.value.kind)) throw new Error();
        change = { kind: 'assumption', id: row.id, value: { ...row.assumption.value, value } as NonNullable<WorkbenchRow['assumption']>['value'] };
      } else {
        const indicator = indicators.data?.find(i => i.id === indicatorId);
        if (indicatorId && !indicator) throw new Error();
        change = { kind: 'goal', remove, goal: { id: goalId, kind: indicator ? 'comparison' : 'narrative', question: text,
          indicator_id: indicator?.id ?? null, operation: indicator ? operation : null,
          threshold: indicator ? { kind: 'quantity', value, unit_id: indicator.definition.unit_id, time_basis_id: indicator.definition.time_basis_id, denominator_scope_id: indicator.definition.denominator_scope_id } : null } };
      }
      setPreview(await window.poliscope.previewWorkbench({ context: state.context, scope_id: scope, change }));
    } catch { setError('This change could not be previewed. Check scope, exact values, target units and supported assumption ownership. Saved state is unchanged.'); }
    finally { setBusy(false); }
  }
  async function apply() {
    if (!preview) return;
    setBusy(true); setError(''); setUncertain(true);
    try { const reply = await window.poliscope.applyWorkbench({ candidate_digest: preview.candidate_digest }); onDirty(false); onSelected(reply.state); }
    catch { setError('Save unconfirmed. Preview remains unsaved in this view. Retry the same Apply to recover the confirmed outcome.'); }
    finally { setBusy(false); }
  }
  async function erase(note: WorkbenchRow) {
    setBusy(true); setError('');
    try { setRow(undefined); setText(''); setPreview(undefined); await window.poliscope.deleteNote({ context: state.context, scope_id: scope, id: note.id }); await client.cancelQueries({ predicate: q => q.queryKey.includes('workbench') }); client.removeQueries({ predicate: q => q.queryKey.includes('workbench') }); await data.refetch(); }
    catch { setError('Deletion could not complete. Retry deletion to finish removing active owned copies.'); }
    finally { setBusy(false); }
  }
  return <section aria-label="Evidence and models workspace">
    <p>Revision {state.context.revision_id} · Scope {scope} · Model {state.versions.model_id} · Tick {state.effective_time.tick}</p>
    <p>Inspect retained definitions, inputs, assumptions, traces and source licenses. Historical definitions stay attached to their result. Scientific support, uncertainty and unsupported extrapolation are separate from executable status.</p>
    <fieldset disabled={Boolean(draft) || busy}><legend>Evidence collections</legend>
      <label>Inspect evidence<select value={collection} onChange={e => { setCollection(e.target.value as EvidenceCollection); setCursors([null]); setSource(''); setModel(undefined); }}>{['results', 'models', 'references', 'assumptions', 'goals', 'notes', 'rationale'].map(c => <option key={c}>{c}</option>)}</select></label>
      <button onClick={onCompare}>Compare branches and assumptions</button>
    </fieldset>
    {collection === 'results' && <Overview state={state} scope={scope} />}
    {collection !== 'results' && <>
      {data.isFetching && <p role="status">Reading retained evidence…</p>}
      {data.isError && <p role="alert">Evidence unavailable. <button onClick={() => void data.refetch()}>Retry workspace evidence</button></p>}
      {data.data && <><p>Physical result identity: {data.data.physical_output_digest ?? 'Unavailable'}</p>
        {!data.data.items.length && <p>No recorded {collection} in this scope. Goals start empty. Missing models and evidence remain unresolved.</p>}
        <table><caption>Retained {collection}</caption><thead><tr><th>Identity</th><th>Definition and content</th><th>Inspect or edit</th></tr></thead><tbody>{data.data.items.map(r => <tr key={r.id}><th>{r.id}</th><td>
          {r.assumption && <><p>{valueText(r.assumption.value)}</p><pre>{JSON.stringify(r.definition, null, 2)}</pre><p>{r.editable ? 'Supported player point parameter' : 'Read only; range/distribution/qualitative or unsupported input is not a point parameter'}</p></>}
          {r.reference && <><p>{r.reference.kind} · {r.reference.visibility} · {r.reference.availability}</p><pre>{JSON.stringify(r.reference, null, 2)}</pre></>}
          {r.model_id && <p>Retained model {r.model_id} · {r.model_version}</p>}
          {r.goal && <><p>{r.goal.question}</p><p>{r.goal.indicator_id ?? 'Narrative inquiry'} · {r.goal.operation} {valueText(r.goal.threshold)}</p><p>{r.observation?.reason} · {r.observation?.matched === null ? r.observation.status : r.observation?.matched ? 'Within player target' : 'Outside player target'}</p></>}
          {r.rationale && <><p>Private rationale · {r.status}</p><p>{r.text}</p></>}
          {r.note && <><p>Private · {r.status} · {r.note_kind ?? 'Content unavailable'}</p><p>{r.text}</p></>}
        </td><td>
          {r.reference?.source && r.reference.visibility === 'public' && <button disabled={Boolean(draft) || busy} onClick={() => setSource(r.reference!.id)}>Read archived excerpt {r.reference.id}</button>}
          {r.model_id && <button disabled={Boolean(draft) || busy} onClick={() => setModel({ id: r.model_id!, version: r.model_version ?? null })}>Inspect formula and mechanism {r.model_id}</button>}
          {!historical && r.editable && <button disabled={Boolean(draft) || busy} onClick={() => begin('assumption', r)}>Edit assumption {r.id}</button>}
          {!historical && r.goal && <button disabled={Boolean(draft) || busy} onClick={() => begin('goal', r)}>Edit target {r.id}</button>}
          {!historical && r.note && r.status === 'available' && <button disabled={Boolean(draft) || busy} onClick={() => begin('note', r)}>Edit private note {r.id}</button>}
          {r.rationale && r.status !== 'deleted' && <button disabled={Boolean(draft) || busy} onClick={() => void erase(r)}>Delete active private rationale {r.id}</button>}
          {r.note && r.status !== 'deleted' && <button disabled={Boolean(draft) || busy} onClick={() => void erase(r)}>Delete all active versions of private note {r.id}</button>}
        </td></tr>)}</tbody></table>
        <button disabled={Boolean(draft) || busy || cursors.length === 1} onClick={() => setCursors(c => c.slice(0,-1))}>Previous evidence page</button><button disabled={Boolean(draft) || busy || !data.data.next_cursor} onClick={() => setCursors(c => [...c, data.data!.next_cursor])}>Next evidence page</button>
      </>}
    </>}
    {source && <Source key={JSON.stringify([state.context, source])} state={state} identity={source} />}
    {model && <Model key={JSON.stringify([state.context, model])} state={state} kind="mechanism" identity={model.id} version={model.version} />}
    <p>Private notes are excluded from simulation and sharing by default. Deleting a note removes all active versions and owned derivatives, while history keeps noncontent references. Filesystem recovery, external backups and previously shared copies are not securely erased.</p>
    {historical ? <p>This retained revision is read only. Fork in History and comparison before editing.</p> : !draft && <><button disabled={busy} onClick={() => begin('note')}>Add private inquiry or note</button><button disabled={busy} onClick={() => begin('goal')}>Add declared goal or target</button></>}
    {draft && <section aria-label="Evidence edit"><fieldset disabled={busy || uncertain}><legend>Proposed {draft}</legend>
      {draft === 'note' && <label>Private note kind<select value={noteKind} onChange={e => { setNoteKind(e.target.value as NoteKind); setPreview(undefined); }}>{['inquiry','expectation','observation','model_gap','proposal'].map(k => <option key={k}>{k}</option>)}</select></label>}
      {draft !== 'assumption' && <label>{draft === 'note' ? 'Private note text' : 'Declared goal question'}<textarea maxLength={2048} value={text} onChange={e => { setText(e.target.value); setPreview(undefined); }} /></label>}
      {draft === 'goal' && <><label>Goal ID<input maxLength={128} disabled={Boolean(row?.goal)} value={goalId} onChange={e => { setGoalId(e.target.value); setPreview(undefined); }} /></label>
        <label>Target indicator<select disabled={Boolean(row?.goal)} value={indicatorId} onChange={e => { setIndicatorId(e.target.value); setPreview(undefined); }}><option value="">Narrative question only</option>{indicators.data?.map(i => <option key={i.id} value={i.id}>{i.definition.name} · {i.definition.unit_id}</option>)}</select></label>
        {indicatorId && <label>Target comparison<select value={operation} onChange={e => { setOperation(e.target.value as typeof operation); setPreview(undefined); }}>{['ge','le','eq','ne','gt','lt'].map(o => <option key={o}>{o}</option>)}</select></label>}
        {row?.goal && <label>Remove this target<input type="checkbox" checked={remove} onChange={e => { setRemove(e.target.checked); setPreview(undefined); }} /></label>}
      </>}
      {(draft === 'assumption' || (draft === 'goal' && indicatorId)) && <label>Exact parameter or target value<input maxLength={256} value={value} onChange={e => { setValue(e.target.value); setPreview(undefined); }} /></label>}
      <button onClick={() => void showPreview()}>Preview evidence edit</button>
    </fieldset>
    {preview && <section aria-label="Evidence edit preview"><p>{preview.disclosure}</p><pre>{JSON.stringify(preview.edit.change, null, 2)}</pre><p>Physical result {preview.physical_before === preview.physical_after ? 'unchanged' : 'changed'} · {preview.changed_observations} changed observations</p><p>Before {preview.physical_before}<br />After {preview.physical_after}</p><button disabled={busy} onClick={() => void apply()}>{uncertain ? 'Retry evidence Apply' : 'Apply evidence edit'}</button></section>}
    <button disabled={busy || uncertain} onClick={() => { void window.poliscope.cancelWorkbench().then(() => { setDraft(undefined); setRow(undefined); setText(''); setValue(''); setPreview(undefined); onDirty(false); }).catch(() => setError('Cancel could not complete. Retry cancellation.')); }}>Cancel evidence edit</button>
    </section>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
