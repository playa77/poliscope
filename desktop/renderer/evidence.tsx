import { workStatus } from './work-status';
import React, { useEffect, useState, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { WorkspaceState } from '../../contracts/workspace';
import type { WorkbenchQuery, WorkbenchRow, WorkbenchEdit, WorkbenchPreview } from '../../contracts/workbench';
import type { IndicatorRow } from '../../contracts/overview';
import { Overview, valueText } from './overview';
import { Source } from './atlas';
import { Model } from './matrix';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { NativeSelect } from '@/components/app/native-select';
import { Actions, DataTable, Field, Hint, SubHeading, Toolbar } from '@/components/app/form';
import { CheckField } from '@/components/app/form';
import { EmptyState, ErrorNote, Panel } from '@/components/app/blocks';

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
  const draftOrigin = useRef<HTMLElement | null>(null);
  const addButton = useRef<HTMLButtonElement>(null);
  const wasDraft = useRef(false);
  const editHeading = useRef<HTMLHeadingElement>(null);
  const previewHeading = useRef<HTMLHeadingElement>(null);
  const [text, setText] = useState(''); const [noteKind, setNoteKind] = useState<NoteKind>('inquiry');
  const [goalId, setGoalId] = useState(''); const [indicatorId, setIndicatorId] = useState('');
  const [operation, setOperation] = useState<'ge' | 'le' | 'eq' | 'ne' | 'gt' | 'lt'>('ge');
  const [value, setValue] = useState(''); const [remove, setRemove] = useState(false);
  const [preview, setPreview] = useState<WorkbenchPreview>();
  const previewGeneration = useRef(0);
  useEffect(() => {
    if (draft) editHeading.current?.focus();
    else if (wasDraft.current && document.activeElement === document.body) {
      (draftOrigin.current?.isConnected ? draftOrigin.current : addButton.current)?.focus();
    }
    wasDraft.current = Boolean(draft);
  }, [draft]);
  useEffect(() => { if (preview) previewHeading.current?.focus(); }, [preview]);
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
    draftOrigin.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setDraft(kind); setRow(selected); setPreview(undefined); setError(''); setRemove(false); onDirty(true);
    setText(selected?.text ?? selected?.goal?.question ?? ''); setNoteKind(selected?.note_kind ?? 'inquiry');
    setGoalId(selected?.goal?.id ?? ''); setIndicatorId(selected?.goal?.indicator_id ?? '');
    setOperation(selected?.goal?.operation ?? 'ge'); setValue(selected?.goal?.threshold?.value ?? (selected?.assumption?.value.kind === 'quantity' || selected?.assumption?.value.kind === 'label' ? selected.assumption.value.value : ''));
  }
  async function showPreview() {
    const generation = ++previewGeneration.current;
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
      const result = await window.poliscope.previewWorkbench({ context: state.context, scope_id: scope, change });
      if (generation === previewGeneration.current) setPreview(result);
    } catch (error) { if (generation === previewGeneration.current) setError(workStatus(error, 'This change could not be previewed. Check scope, exact values, target units and supported assumption ownership. Saved state is unchanged.')); }
    finally { if (generation === previewGeneration.current) setBusy(false); }
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
  return <section aria-label="Evidence and models workspace" className="flex flex-col gap-4">
    <Panel title="Evidence and models" description="Inspect retained definitions, inputs, assumptions, traces and source licenses. Historical definitions stay attached to their result. Scientific support, uncertainty and unsupported extrapolation are separate from executable status."
      footer={`Revision ${state.context.revision_id} · Scope ${scope} · Model ${state.versions.model_id} · Tick ${state.effective_time.tick}`}>
      <fieldset disabled={Boolean(draft) || busy} className="m-0 min-w-0 border-0 p-0">
        <legend className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Evidence collections</legend>
        <Toolbar>
          <Field label="Inspect evidence" className="w-52">
            <NativeSelect value={collection} onChange={e => { setCollection(e.target.value as EvidenceCollection); setCursors([null]); setSource(''); setModel(undefined); }}>{['results', 'models', 'references', 'assumptions', 'goals', 'notes', 'rationale'].map(c => <option key={c}>{c}</option>)}</NativeSelect>
          </Field>
          <Button variant="outline" onClick={onCompare}>Compare branches and assumptions</Button>
        </Toolbar>
      </fieldset>
    </Panel>

    {collection === 'results' && <Overview state={state} scope={scope} />}

    {collection !== 'results' && <Panel title={`Retained ${collection}`} description="Every row keeps its own scope, unit and time basis. Private notes are separate from shared design content.">
      {data.isFetching && <Hint>Reading retained evidence…</Hint>}
      {data.isError && <ErrorNote title="Evidence unavailable"><Button variant="outline" size="sm" className="mt-2" onClick={() => void data.refetch()}>Retry workspace evidence</Button></ErrorNote>}
      {data.data && <>
        <Hint>Physical result identity: {data.data.physical_output_digest ?? 'Unavailable'}</Hint>
        {!data.data.items.length && <EmptyState title={`No recorded ${collection}`} description={`No recorded ${collection} in this scope. Goals start empty. Missing models and evidence remain unresolved.`} />}
        {(data.data.items.length ?? 0) > 0 && <DataTable className="mt-3">
          <caption>Retained {collection}</caption>
          <thead><tr><th scope="col">Identity</th><th scope="col">Definition and content</th><th scope="col">Inspect or edit</th></tr></thead>
          <tbody>{data.data.items.map(r => <tr key={r.id}>
            <th scope="row">{r.id}</th>
            <td>
              {r.assumption && <><p>{valueText(r.assumption.value)}</p><pre className="mt-1 max-h-48 overflow-auto rounded-lg bg-muted/60 p-2 text-xs">{JSON.stringify(r.definition, null, 2)}</pre><p className="mt-1 text-[11px] text-muted-foreground">{r.editable ? 'Supported player point parameter' : 'Read only; range/distribution/qualitative or unsupported input is not a point parameter'}</p></>}
              {r.reference && <><p>{r.reference.kind} · {r.reference.visibility} · {r.reference.availability}</p><pre className="mt-1 max-h-48 overflow-auto rounded-lg bg-muted/60 p-2 text-xs">{JSON.stringify(r.reference, null, 2)}</pre></>}
              {r.model_id && <p>Retained model {r.model_id} · {r.model_version}</p>}
              {r.goal && <><p>{r.goal.question}</p><p className="text-[11px] text-muted-foreground">{r.goal.indicator_id ?? 'Narrative inquiry'} · {r.goal.operation} {valueText(r.goal.threshold)}</p><p className="text-[11px] text-muted-foreground">{r.observation?.reason} · {r.observation?.matched === null ? r.observation.status : r.observation?.matched ? 'Within player target' : 'Outside player target'}</p></>}
              {r.rationale && <><p>Private rationale · {r.status}</p><p className="text-xs leading-relaxed">{r.text}</p></>}
              {r.note && <><p>Private · {r.status} · {r.note_kind ?? 'Content unavailable'}</p><p className="text-xs leading-relaxed">{r.text}</p></>}
            </td>
            <td><Actions className="gap-1">
              {r.reference?.source && r.reference.visibility === 'public' && <Button variant="link" size="sm" className="h-auto p-0 text-left" disabled={Boolean(draft) || busy} onClick={() => setSource(r.reference!.id)}>Read archived excerpt {r.reference.id}</Button>}
              {r.model_id && <Button variant="link" size="sm" className="h-auto p-0 text-left" disabled={Boolean(draft) || busy} onClick={() => setModel({ id: r.model_id!, version: r.model_version ?? null })}>Inspect formula and mechanism {r.model_id}</Button>}
              {!historical && r.editable && <Button variant="outline" size="xs" disabled={Boolean(draft) || busy} onClick={() => begin('assumption', r)}>Edit assumption {r.id}</Button>}
              {!historical && r.goal && <Button variant="outline" size="xs" disabled={Boolean(draft) || busy} onClick={() => begin('goal', r)}>Edit target {r.id}</Button>}
              {!historical && r.note && r.status === 'available' && <Button variant="outline" size="xs" disabled={Boolean(draft) || busy} onClick={() => begin('note', r)}>Edit private note {r.id}</Button>}
              {r.rationale && r.status !== 'deleted' && <Button variant="destructive" size="xs" disabled={Boolean(draft) || busy} onClick={() => void erase(r)}>Delete active private rationale {r.id}</Button>}
              {r.note && r.status !== 'deleted' && <Button variant="destructive" size="xs" disabled={Boolean(draft) || busy} onClick={() => void erase(r)}>Delete all active versions of private note {r.id}</Button>}
            </Actions></td>
          </tr>)}</tbody>
        </DataTable>}
        <Actions className="mt-3">
          <Button variant="outline" size="sm" disabled={Boolean(draft) || busy || cursors.length === 1} onClick={() => setCursors(c => c.slice(0,-1))}>Previous evidence page</Button>
          <Button variant="outline" size="sm" disabled={Boolean(draft) || busy || !data.data.next_cursor} onClick={() => setCursors(c => [...c, data.data!.next_cursor])}>Next evidence page</Button>
        </Actions>
      </>}
      {source && <Source key={JSON.stringify([state.context, source])} state={state} identity={source} />}
      {model && <Model key={JSON.stringify([state.context, model])} state={state} kind="mechanism" identity={model.id} version={model.version} />}
      <Hint className="mt-3">Private notes are excluded from simulation and sharing by default. Deleting a note removes all active versions and owned derivatives, while history keeps noncontent references. Filesystem recovery, external backups and previously shared copies are not securely erased.</Hint>
    </Panel>}

    {historical
      ? <Panel title="Read-only retained revision" description="This retained revision is read only. Fork in History and comparison before editing."><Hint>Nothing here can change until you fork a new future.</Hint></Panel>
      : !draft && <Actions>
        <Button ref={addButton} disabled={busy} onClick={() => begin('note')} className="rounded-full">Add private inquiry or note</Button>
        <Button variant="outline" disabled={busy} onClick={() => begin('goal')} className="rounded-full">Add declared goal or target</Button>
      </Actions>}

    {draft && <section aria-label="Evidence edit" className="flex min-w-0 flex-col gap-3 rounded-card bg-card p-5 shadow-[var(--shadow-card)]">
      <div>
        <SubHeading as="h4" ref={editHeading} tabIndex={-1}>Edit evidence · unsaved</SubHeading>
        <Hint className="mt-1">A preview is conditional and unsaved. Apply records a design choice, not proof.</Hint>
      </div>
      <fieldset disabled={busy || uncertain} className="m-0 min-w-0 border-0 p-0">
        <legend className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Proposed {draft}</legend>
        <Toolbar>
          {draft === 'note' && <Field label="Private note kind" className="w-48">
            <NativeSelect value={noteKind} onChange={e => { setNoteKind(e.target.value as NoteKind); setPreview(undefined); }}>{['inquiry','expectation','observation','model_gap','proposal'].map(k => <option key={k}>{k}</option>)}</NativeSelect>
          </Field>}
          {draft !== 'assumption' && <Field label={draft === 'note' ? 'Private note text' : 'Declared goal question'} className="w-full">
            <Textarea maxLength={2048} value={text} onChange={e => { setText(e.target.value); setPreview(undefined); }} />
          </Field>}
          {draft === 'goal' && <>
            <Field label="Goal ID" className="w-52"><Input maxLength={128} disabled={Boolean(row?.goal)} value={goalId} onChange={e => { setGoalId(e.target.value); setPreview(undefined); }} /></Field>
            <Field label="Target indicator" className="w-64">
              <NativeSelect disabled={Boolean(row?.goal)} value={indicatorId} onChange={e => { setIndicatorId(e.target.value); setPreview(undefined); }}>
                <option value="">Narrative question only</option>{indicators.data?.map(i => <option key={i.id} value={i.id}>{i.definition.name} · {i.definition.unit_id}</option>)}
              </NativeSelect>
            </Field>
            {indicatorId && <Field label="Target comparison" className="w-36">
              <NativeSelect value={operation} onChange={e => { setOperation(e.target.value as typeof operation); setPreview(undefined); }}>{['ge','le','eq','ne','gt','lt'].map(o => <option key={o}>{o}</option>)}</NativeSelect>
            </Field>}
            {row?.goal && <CheckField checked={remove} onChange={v => { setRemove(v); setPreview(undefined); }} className="pb-1">Remove this target</CheckField>}
          </>}
          {(draft === 'assumption' || (draft === 'goal' && indicatorId)) && <Field label="Exact parameter or target value" className="w-52"><Input maxLength={256} value={value} onChange={e => { setValue(e.target.value); setPreview(undefined); }} /></Field>}
        </Toolbar>
        <Actions className="mt-3"><Button onClick={() => void showPreview()}>Preview evidence edit</Button></Actions>
      </fieldset>
      {preview && <section aria-label="Evidence edit preview" className="flex flex-col gap-2 rounded-xl border border-border bg-muted/40 p-3">
        <SubHeading as="h4" ref={previewHeading} tabIndex={-1}>Preview · not applied</SubHeading>
        <Hint>{preview.disclosure}</Hint>
        <pre className="max-h-56 overflow-auto rounded-lg bg-card p-3 text-xs">{JSON.stringify(preview.edit.change, null, 2)}</pre>
        <p className="text-xs">Physical result {preview.physical_before === preview.physical_after ? 'unchanged' : 'changed'} · {preview.changed_observations} changed observations</p>
        <p className="text-xs tabular-nums">Before {preview.physical_before}<br />After {preview.physical_after}</p>
        <Actions><Button disabled={busy} onClick={() => void apply()}>{uncertain ? 'Retry evidence Apply' : 'Apply evidence edit'}</Button></Actions>
      </section>}
      <Actions><Button variant="outline" disabled={uncertain} onClick={() => { previewGeneration.current++; void window.poliscope.cancelWorkbench().then(() => { setBusy(false); setDraft(undefined); setRow(undefined); setText(''); setValue(''); setPreview(undefined); onDirty(false); }).catch(() => setError('Cancel could not complete. Retry cancellation.')); }}>Cancel evidence edit</Button></Actions>
    </section>}
    {busy && !uncertain && <Hint>Computing preview. You can cancel this draft while it runs.</Hint>}
    {error && <ErrorNote>{error}</ErrorNote>}
  </section>;
}
