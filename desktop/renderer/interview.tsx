import React, { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { InterviewQuery, InterviewEdit, InterviewPreview, PartitionValueDTO } from '../../contracts/interview';
import type { WorkspaceState } from '../../contracts/workspace';

function display(row: PartitionValueDTO) {
  return row.value.kind === 'quantity' ? `${row.value.value} ${row.value.unit_id}` : row.value.kind === 'unknown' ? 'Unknown' : 'Not a quantity';
}
function Commitment({ text }: { text: string }) {
  try {
    const saved: unknown = JSON.parse(text);
    if (saved && typeof saved === 'object' && 'option' in saved && saved.option && typeof saved.option === 'object' &&
        'original_text' in saved.option && typeof saved.option.original_text === 'string') {
      const option = saved.option as Record<string, unknown>;
      return <><p>{option.original_text as string}</p>
        <p>Origin: {String(option.origin ?? 'unavailable')} · Modeling: {String(option.modeling ?? 'unavailable')} · Evidence: {String(option.evidence ?? 'unavailable')}</p>
        <p>{'coverage' in saved && typeof saved.coverage === 'string' ? saved.coverage : 'Coverage unavailable'}</p></>;
    }
  } catch { /* Older data remains inspectable as plain text. */ }
  return <p>{text}</p>;
}
export function Interview({ query, versions, historical, onDirty, onConfirmed }: {
  query: InterviewQuery; versions: WorkspaceState['versions']; historical: boolean; onDirty: (dirty: boolean) => void;
  onConfirmed: (state: WorkspaceState, status: string) => void;
}) {
  const question = useQuery({ queryKey: ['interview', query, versions], retry: false, queryFn: () => window.poliscope.interview(query) });
  const [edit, setEdit] = useState<InterviewEdit>();
  const [preview, setPreview] = useState<InterviewPreview>();
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
    setBusy(true); setError('');
    try { await window.poliscope.cancelInterview(); setEdit(undefined); setPreview(undefined); setDeferred(defer); }
    catch { setError('Cancellation could not be confirmed. Retry, or resolve an uncertain Apply.'); }
    finally { setBusy(false); }
  }
  async function runPreview() {
    setBusy(true); setError(''); setPreview(undefined);
    try { setPreview(await window.poliscope.previewInterview(edit!)); }
    catch { setError('Preview unavailable. Check nonnegative decimal quantities and whole people, then retry. No revision was applied.'); }
    finally { setBusy(false); }
  }
  async function apply() {
    setBusy(true); setError(''); setUncertain(true);
    try {
      const result = await window.poliscope.applyInterview({ candidate_digest: preview!.candidate_digest });
      setUncertain(false); setEdit(undefined); setPreview(undefined); onDirty(false);
      onConfirmed(result.state, result.status === 'stale' ? 'The branch changed. Nothing from this draft was applied. Review the current state and preview again.' : 'Applied one design revision. Alternatives are retained; any supplied rationale is stored privately.');
    } catch { setError('Apply confirmation unavailable. Retry Apply with this same candidate, or reopen the confirmed branch to inspect saved history.'); }
    finally { setBusy(false); }
  }
  if (question.isPending) return <p role="status">Loading the selected interview…</p>;
  if (question.isError) return <p role="alert">Interview could not be read. <button onClick={() => void question.refetch()}>Retry interview read</button></p>;
  const q = question.data;
  return <section className="interview" aria-label="Domain interview"><h5>{q.definition.original_text}</h5>
    <p>Origin: {q.definition.origin} synthetic template · Evidence: {q.definition.evidence} · Modeling: {q.definition.modeling} · Version: {q.definition.version}</p>
    <p>Scope: {query.scope_id} · Revision: {query.context.revision_id}</p>
    <details><summary>Original wording and source</summary><p>{q.definition.original_text}</p><p>Original Poliscope synthetic template, {q.definition.id}. No external source or historical adopted option is claimed. MIT repository license. Source and assumption references: none.</p></details>
    <details><summary>Clarification and dependencies</summary><p>{q.clarification}</p><ul>{q.dependencies.map(d => <li key={d}>{d}</li>)}</ul></details>
    {q.current_commitment && <details className="current-commitment"><summary>Current qualitative commitment</summary><Commitment text={q.current_commitment} /></details>}
    {historical && <p>This is a retained revision. Open the current branch head to edit.</p>}
    <fieldset disabled={historical || busy || uncertain}><legend>Explore one alternative</legend>
      <div className="option-grid">{q.options.map(o => <label className="option-card" key={o.definition.id}>
        <input type="radio" name="interview-option" checked={edit?.choice_id === o.definition.id} onChange={() => choose(o.definition.id)} />
        <strong>{o.label}</strong><span>{o.definition.original_text}</span><span>Possible benefit: {o.benefit}</span><span>Cost and requirements: {o.cost}</span><span>{o.mechanism}</span>
      </label>)}</div>
      <label><input type="radio" name="interview-option" checked={edit?.choice_id === 'player:proposal'} onChange={() => choose('player:proposal')} />Propose a qualitative alternative</label>
      {edit && <>
        {edit.choice_id === 'player:proposal' && <label>Proposed arrangement<textarea maxLength={1024} value={edit.proposal ?? ''} onChange={e => update({ proposal: e.target.value })} /></label>}
        {query.domain_id === 'domain:1' && q.conditions.length > 0 && <><p>Parameter variant: editable conditions only. Blank stays unknown. No resource cost is calculated from these quantities.</p>
          <label>Preview population (people)<input inputMode="numeric" maxLength={256} value={edit.population ?? ''} onChange={e => update({ population: e.target.value || null })} /></label>
          <label>Preview land area (km²)<input inputMode="decimal" maxLength={256} value={edit.land_area ?? ''} onChange={e => update({ land_area: e.target.value || null })} /></label></>}
        <label>Private rationale (optional)<textarea maxLength={2048} value={edit.rationale} onChange={e => update({ rationale: e.target.value })} /></label>
        <p>The proposed arrangement becomes saved design content on Apply. Rationale is stored separately as private text. Until Apply, this draft is unsaved. Cancel clears it.</p>
        <button disabled={edit.choice_id === 'player:proposal' && !edit.proposal?.trim()} onClick={() => void runPreview()}>Preview draft</button>
      </>}
    </fieldset>
    {error && <p role="alert">{error}</p>}
    {preview && <section aria-label="Noncommitting preview"><h5>Preview · not applied</h5><p>{preview.coverage}</p>
      <p>Affected scopes: {preview.affected_scope_ids.join(', ')}. Changed values: {preview.changed_value_ids.join(', ') || 'None'}.</p>
      <p>Affected numerical accounts: {preview.accounts.length ? preview.accounts.join(', ') : 'None; numerical mechanisms are not supplied.'}</p>
      <ul>{preview.findings.map((f, i) => <li key={i}>{f}</li>)}</ul>
      <p>Alternatives retained on Apply: {preview.alternatives.map(id => q.options.find(o => o.definition.id === id)?.label ?? 'Player qualitative alternative').join(', ')}</p>
      <ul>{preview.dependencies.map(d => <li key={d}>{d}</li>)}</ul>
      {preview.before.length > 0 && <table><caption>Condition changes</caption><thead><tr><th>Condition</th><th>Before</th><th>After</th></tr></thead><tbody>{preview.before.map(row => <tr key={row.id}><th>{row.property_id}</th><td>{display(row)}</td><td>{display(preview.after.find(v => v.id === row.id)!)}</td></tr>)}</tbody></table>}
      <button disabled={busy || historical} onClick={() => void apply()}>{uncertain ? 'Retry Apply' : 'Apply draft'}</button>
    </section>}
    <button disabled={busy || uncertain || historical} onClick={() => void cancel()}>Cancel draft</button>
    <button disabled={busy || uncertain || historical} onClick={() => void cancel(true)}>Defer this question</button>
    {deferred && <p role="status">Deferred in this session. Your saved design is unchanged; enter any other domain.</p>}
    {uncertain && <button disabled={busy} onClick={() => {
      setBusy(true);
      void window.poliscope.selectWorld({ civilization_id: query.context.civilization_id, branch_id: query.context.branch_id, revision_id: null })
        .then(state => { setEdit(undefined); setPreview(undefined); setUncertain(false); onDirty(false); onConfirmed(state, 'Reopened confirmed branch. The unsaved draft was discarded; inspect the saved state before making another change.'); })
        .catch(() => setError('The confirmed branch could not be reopened. Retry.')).finally(() => setBusy(false));
    }}>Discard draft and reopen confirmed branch</button>}
  </section>;
}
