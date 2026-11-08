import { workStatus } from './work-status';
import { assistantQuestion } from './assistant-question';
import React, { useEffect, useState, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { MessageSquare, Sparkles } from 'lucide-react';
import type { InterviewQuery, InterviewEdit, InterviewPreview, PartitionValueDTO } from '../../contracts/interview';
import type { WorkspaceState } from '../../contracts/workspace';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Actions, DataTable, Disclosure, Field, Hint, SubHeading, Toolbar } from '@/components/app/form';
import { ErrorNote, StateBadge } from '@/components/app/blocks';

function display(row: PartitionValueDTO) {
  return row.value.kind === 'quantity' ? `${row.value.value} ${row.value.unit_id}` : row.value.kind === 'unknown' ? 'Unknown' : 'Not a quantity';
}
export function Commitment({ text }: { text: string }) {
  try {
    const saved: unknown = JSON.parse(text);
    if (saved && typeof saved === 'object' && 'option' in saved && saved.option && typeof saved.option === 'object' &&
        'original_text' in saved.option && typeof saved.option.original_text === 'string') {
      const option = saved.option as Record<string, unknown>;
      return <><p className="text-sm leading-relaxed">{option.original_text as string}</p>
        <p className="text-[11px] text-muted-foreground">Origin: {String(option.origin ?? 'unavailable')} · Modeling: {String(option.modeling ?? 'unavailable')} · Evidence: {String(option.evidence ?? 'unavailable')}</p>
        <p className="text-[11px] text-muted-foreground">{'coverage' in saved && typeof saved.coverage === 'string' ? saved.coverage : 'Coverage unavailable'}</p></>;
    }
  } catch { /* Older data remains inspectable as plain text. */ }
  return <p className="text-sm leading-relaxed">{text}</p>;
}
export function Interview({ query, versions, historical, onDirty, onConfirmed, onAskAssistant }: {
  query: InterviewQuery; versions: WorkspaceState['versions']; historical: boolean; onDirty: (dirty: boolean) => void;
  onAskAssistant?: (text:string)=>void;
  onConfirmed: (state: WorkspaceState, status: string) => void;
}) {
  const question = useQuery({ queryKey: ['interview', query, versions], retry: false, queryFn: () => window.poliscope.interview(query) });
  const [edit, setEdit] = useState<InterviewEdit>();
  const [preview, setPreview] = useState<InterviewPreview>();
  const previewGeneration = useRef(0);
  const previewHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { if (preview) previewHeading.current?.focus(); }, [preview]);
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState('');
  const [deferred, setDeferred] = useState(false);
  useEffect(() => { onDirty(Boolean(edit) || busy); }, [edit, busy, onDirty]);
  function choose(choice_id: string) {
    const conditions = question.data?.conditions ?? [];
    const quantity = (id: string) => { const row = conditions.find(v => v.id === id); return row?.value.kind === 'quantity' ? row.value.value : null; };
    setEdit({ query, choice_id, proposal: choice_id === 'player:proposal' ? (edit?.proposal ?? '') : null,
      population: edit ? edit.population : quantity('population:value'),
      land_area: edit ? edit.land_area : quantity('land:value'), rationale: edit?.rationale ?? '' });
    setPreview(undefined); setError(''); setDeferred(false);
  }
  function update(change: Partial<InterviewEdit>) { setEdit({ ...edit!, ...change }); setPreview(undefined); setError(''); }
  async function cancel(defer = false) {
    previewGeneration.current++;
    setBusy(true); setError('');
    try { await window.poliscope.cancelInterview(); setEdit(undefined); setPreview(undefined); setDeferred(defer); }
    catch { setError('Cancellation could not be confirmed. Retry, or resolve an uncertain Apply.'); }
    finally { setBusy(false); }
  }
  async function runPreview() {
    const generation = ++previewGeneration.current;
    setBusy(true); setError(''); setPreview(undefined);
    try { const result = await window.poliscope.previewInterview(edit!);
      if (generation === previewGeneration.current) setPreview(result); }
    catch (error) { if (generation === previewGeneration.current) setError(workStatus(error, 'Preview unavailable. Check nonnegative decimal quantities and whole people, then retry. No revision was applied.')); }
    finally { if (generation === previewGeneration.current) setBusy(false); }
  }
  async function apply() {
    setBusy(true); setError(''); setUncertain(true);
    try {
      const result = await window.poliscope.applyInterview({ candidate_digest: preview!.candidate_digest });
      setUncertain(false); setEdit(undefined); setPreview(undefined); onDirty(false);
      onConfirmed(result.state, result.status === 'stale' ? 'The branch changed. Nothing from this draft was applied. Review the current state and preview again.' : 'Applied one design revision. Alternatives are retained; any supplied rationale is stored privately.');
    } catch { setError('Save unconfirmed. Preview remains unsaved in this view. Retry Apply with this same candidate, or reopen the confirmed branch to inspect saved history.'); }
    finally { setBusy(false); }
  }
  if (question.isPending) return <Hint>Loading the selected interview…</Hint>;
  if (question.isError) return <ErrorNote title="Interview could not be read"><Button variant="outline" size="sm" onClick={() => void question.refetch()}>Retry interview read</Button></ErrorNote>;
  const q = question.data;
  const assistantDraft=assistantQuestion(q);
  const locked = historical || busy || uncertain;
  return <section className="interview flex flex-col gap-3" aria-label="Domain interview">
    <div className="flex flex-wrap items-start justify-between gap-2">
      <SubHeading as="h5" className="max-w-3xl text-sm leading-snug">{q.definition.original_text}</SubHeading>
      <StateBadge tone="info">{q.definition.modeling}</StateBadge>
    </div>
    <Hint>Origin: {q.definition.origin} · Evidence: {q.definition.evidence} · Modeling: {q.definition.modeling} · Version: {q.definition.version}</Hint>
    <Hint>Scope: {query.scope_id} · Revision: {query.context.revision_id}</Hint>
    <Disclosure title="Original wording and source">
      <p className="text-xs leading-relaxed">{q.definition.original_text}</p>
      <Hint>Definition {q.definition.id}. Source adoption is historical context; only Apply records a player choice. Inspect source text and license in the Decision atlas. Source references: {q.definition.source_refs.join(', ') || 'none'}. Assumption references: {q.definition.assumption_refs.join(', ') || 'none'}.</Hint>
    </Disclosure>
    {onAskAssistant&&<Actions>
      <Button variant="outline" size="sm" disabled={busy||Boolean(edit)||!assistantDraft} onClick={()=>onAskAssistant(assistantDraft!)}><Sparkles aria-hidden />Review this question with optional assistance</Button>
      <Hint className="max-w-md">Copies authored wording and public references for local review only. No private rationale, draft or current commitment is included; nothing is sent automatically.</Hint>
    </Actions>}
    <Disclosure title="Clarification and dependencies">
      <p className="text-xs leading-relaxed">{q.clarification}</p>
      <ul className="flex flex-col gap-1 text-xs">{q.dependencies.map(d => <li key={d} className="rounded-lg bg-card px-2 py-1">{d}</li>)}</ul>
    </Disclosure>
    {q.current_commitment && <details className="current-commitment group rounded-xl border border-primary/30 bg-primary-wash/60 px-4 py-3">
      <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-foreground">Current qualitative commitment<MessageSquare aria-hidden className="ml-auto size-4 text-primary" /></summary>
      <div className="mt-2 flex flex-col gap-1"><Commitment text={q.current_commitment} /></div>
    </details>}
    {historical && <Hint>This is a retained revision. Open the current branch head to edit.</Hint>}
    <fieldset disabled={locked} className="m-0 min-w-0 border-0 p-0">
      <legend className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Explore one alternative</legend>
      <div className="option-grid grid gap-2 sm:grid-cols-2">
        {q.options.filter(o => o.definition.id !== 'player:proposal').map(o => <label className="option-card m-0 flex cursor-pointer items-start gap-2.5 rounded-xl border border-border bg-card p-3 text-sm leading-relaxed transition-colors hover:border-primary/40 has-[:checked]:border-primary has-[:checked]:bg-primary-wash/50" key={o.definition.id}>
          <input type="radio" name="interview-option" className="mt-1 size-4 shrink-0 accent-primary" checked={edit?.choice_id === o.definition.id} onChange={() => choose(o.definition.id)} />
          <span className="min-w-0">
            <strong className="block text-sm font-medium">{o.label}</strong>
            <span className="mt-1 block text-xs leading-relaxed text-muted-foreground">{o.definition.original_text}</span>
            <span className="mt-1 block text-[11px] text-muted-foreground">Possible benefit: {o.benefit}</span>
            <span className="block text-[11px] text-muted-foreground">Cost and requirements: {o.cost}</span>
            <span className="mt-1 block text-[11px] text-muted-foreground">{o.mechanism}</span>
          </span>
        </label>)}
      </div>
      <label className="m-0 mt-3 flex items-start gap-2 rounded-xl bg-muted/50 p-3 text-sm">
        <input type="radio" name="interview-option" className="mt-1 size-4 shrink-0 accent-primary" checked={edit?.choice_id === 'player:proposal'} onChange={() => choose('player:proposal')} />Propose a qualitative alternative
      </label>
      {edit && <div className="mt-3 flex flex-col gap-3">
        {edit.choice_id === 'player:proposal' && <Field label="Proposed arrangement" className="w-full">
          <Textarea maxLength={1024} value={edit.proposal ?? ''} onChange={e => update({ proposal: e.target.value })} />
        </Field>}
        {query.domain_id === 'domain:1' && q.conditions.length > 0 && <>
          <Hint>Parameter variant: editable conditions only. Blank stays unknown. No resource cost is calculated from these quantities.</Hint>
          <Toolbar>
            <Field label="Preview population (people)" className="w-48"><Input inputMode="numeric" maxLength={256} value={edit.population ?? ''} onChange={e => update({ population: e.target.value || null })} /></Field>
            <Field label="Preview land area (km²)" className="w-48"><Input inputMode="decimal" maxLength={256} value={edit.land_area ?? ''} onChange={e => update({ land_area: e.target.value || null })} /></Field>
          </Toolbar>
        </>}
        <Field label="Private rationale (optional)" className="w-full">
          <Textarea maxLength={2048} value={edit.rationale} onChange={e => update({ rationale: e.target.value })} />
        </Field>
        <Hint>The proposed arrangement becomes saved design content on Apply. Rationale is stored separately as private text. Until Apply, this draft is unsaved. Cancel clears it.</Hint>
        <Actions><Button disabled={edit.choice_id === 'player:proposal' && !edit.proposal?.trim()} onClick={() => void runPreview()}>Preview draft</Button></Actions>
      </div>}
    </fieldset>
    {busy && !uncertain && <Hint>Computing preview. You can cancel this draft while it runs.</Hint>}
    {error && <ErrorNote>{error}</ErrorNote>}
    {preview && <section aria-label="Noncommitting preview" className="flex flex-col gap-2 rounded-xl border border-primary/30 bg-card p-4">
      <SubHeading as="h5" ref={previewHeading} tabIndex={-1}>Preview · not applied</SubHeading>
      <Hint>{preview.coverage}</Hint>
      <p className="text-xs">Affected scopes: {preview.affected_scope_ids.join(', ')}. Changed values: {preview.changed_value_ids.join(', ') || 'None'}.</p>
      <p className="text-xs">Affected numerical accounts: {preview.accounts.length ? preview.accounts.join(', ') : 'None; numerical mechanisms are not supplied.'}</p>
      <ul className="flex flex-col gap-1 text-xs">{preview.findings.map((f, i) => <li key={i} className="rounded-lg bg-muted/60 px-2 py-1">{f}</li>)}</ul>
      <p className="text-xs">Alternatives retained on Apply: {preview.alternatives.map(id => q.options.find(o => o.definition.id === id)?.label ?? 'Player qualitative alternative').join(', ')}</p>
      <ul className="flex flex-col gap-1 text-xs">{preview.dependencies.map(d => <li key={d}>{d}</li>)}</ul>
      {preview.before.length > 0 && <DataTable>
        <caption>Condition changes</caption>
        <thead><tr><th scope="col">Condition</th><th scope="col">Before</th><th scope="col">After</th></tr></thead>
        <tbody>{preview.before.map(row => <tr key={row.id}><th scope="row">{row.property_id}</th><td>{display(row)}</td><td>{display(preview.after.find(v => v.id === row.id)!)}</td></tr>)}</tbody>
      </DataTable>}
      <Actions><Button disabled={busy || historical} onClick={() => void apply()}>{uncertain ? 'Retry Apply' : 'Apply draft'}</Button></Actions>
    </section>}
    <Actions>
      <Button variant="outline" disabled={uncertain || historical} onClick={() => void cancel()}>Cancel draft</Button>
      <Button variant="ghost" disabled={uncertain || historical} onClick={() => void cancel(true)}>Defer this question</Button>
    </Actions>
    {deferred && <p role="status" className="text-xs text-muted-foreground">Deferred in this session. Your saved design is unchanged; enter any other domain.</p>}
    {uncertain && <Actions><Button variant="outline" disabled={busy} onClick={() => {
      setBusy(true);
      void window.poliscope.selectWorld({ civilization_id: query.context.civilization_id, branch_id: query.context.branch_id, revision_id: null })
        .then(state => { setEdit(undefined); setPreview(undefined); setUncertain(false); onDirty(false); onConfirmed(state, 'Reopened confirmed branch. The unsaved draft was discarded; inspect the saved state before making another change.'); })
        .catch(() => setError('The confirmed branch could not be reopened. Retry.')).finally(() => setBusy(false));
    }}>Discard draft and reopen confirmed branch</Button></Actions>}
  </section>;
}
