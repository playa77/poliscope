import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { WorkspaceState } from '../../contracts/workspace';
import type { RationaleReply, HistoryAction, LineagePage, ComparePage } from '../../contracts/comparison';
import { valueText } from './overview';

export function DesignHistory({ state, disabled, onSelected }: { state: WorkspaceState; disabled: boolean; onSelected: (next: WorkspaceState) => Promise<void> }) {
  const [privateNote, setPrivateNote] = useState<RationaleReply>();
  const [cursor, setCursor] = useState<string | null>(null);
  const [comparisonCursor, setComparisonCursor] = useState<string | null>(null);
  const [other, setOther] = useState('');
  const [target, setTarget] = useState('');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [pending, setPending] = useState<HistoryAction>();
  const lineage = useQuery<LineagePage>({ queryKey: ['world', state.context, 'lineage', cursor], retry: false,
    queryFn: () => window.poliscope.lineage({ context: state.context, cursor }) });
  const comparison = useQuery<ComparePage>({ queryKey: ['world', state.context, 'comparison', other, comparisonCursor], enabled: Boolean(other), retry: false,
    queryFn: () => window.poliscope.compare({ context: state.context, other: { ...state.context, revision_id: other }, cursor: comparisonCursor }) });
  const historical = state.context.revision_id !== state.branch.context.revision_id;
  const locked = disabled || busy || lineage.isFetching || comparison.isFetching || Boolean(pending);
  async function inspect(revision: string) {
    setBusy(true); setError('');
    try { await onSelected(await window.poliscope.selectWorld({ civilization_id: state.context.civilization_id, branch_id: state.context.branch_id, revision_id: revision })); }
    catch { setError('This retained revision could not be opened.'); }
    finally { setBusy(false); }
  }
  async function mutate(query: HistoryAction) {
    setBusy(true); setError(''); setPending(query);
    try { const next = await window.poliscope.historyAction(query); setPending(undefined); await onSelected(next); }
    catch { setError('History action was not confirmed. Retry the same action or reopen the folder to inspect confirmed history.'); }
    finally { setBusy(false); }
  }
  function action(kind: HistoryAction['action']) {
    return mutate({ context: state.context, expected_sequence: lineage.data!.branch.sequence, action: kind,
      target_revision_id: kind === 'fork' || kind === 'restore' ? target || state.context.revision_id : null,
      name: kind === 'fork' || kind === 'rename' ? name : null });
  }
  return <section className="design-history" aria-label="Design history">
    <p>Inspecting {state.context.revision_id}. Branch head: {lineage.data?.branch.context.revision_id ?? state.branch.context.revision_id}.</p>
    <p>Undo and restore preserve alternate futures. Comparisons use retained results; no model is rerun, no branch is ranked. A positive delta means right minus left.</p>
    {(error || lineage.isError || comparison.isError) && <p role="alert">{error || 'Saved history or comparison could not be read. Reopen the branch to retry.'}</p>}
    {pending && <button disabled={busy} onClick={() => void mutate(pending)}>Retry history action</button>}
    {historical && <button disabled={locked} onClick={() => void inspect(state.branch.context.revision_id)}>Return to branch head</button>}
    <button disabled={locked} onClick={() => { setBusy(true); setError(''); void window.poliscope.rationale({context:state.context}).then(setPrivateNote).catch(() => setError('Private rationale could not be read.')).finally(() => setBusy(false)); }}>Read private rationale for inspected revision</button>
    {privateNote && <section aria-label="Private rationale"><p>Private · local only · {privateNote.reference?.status ?? 'No rationale recorded'}</p><p>{privateNote.text ?? 'Rationale text unavailable.'}</p><button onClick={() => setPrivateNote(undefined)}>Hide private rationale</button></section>}
    <fieldset disabled={locked || historical || !lineage.data}><legend>Change the selected branch</legend>
      <button disabled={!lineage.data?.can_undo} onClick={() => void action('undo')}>Undo design change</button>
      <button disabled={!lineage.data?.branch.redo.length} onClick={() => void action('redo')}>Redo design change</button>
      <label>Branch name<input maxLength={256} value={name} onChange={e => setName(e.target.value)} /></label>
      <button disabled={!name.trim()} onClick={() => void action('rename')}>Rename branch</button>
      <label>Revision to fork or restore<input maxLength={128} value={target} onChange={e => setTarget(e.target.value)} placeholder="Current revision by default" /></label>
      <button disabled={!name.trim()} onClick={() => void action('fork')}>Fork revision</button>
      <button disabled={!target} onClick={() => void action('restore')}>Restore revision and retain current future</button>
    </fieldset>
    <table><caption>Retained design lineage · all futures in this civilization</caption><thead><tr><th scope="col">Revision and parent</th><th scope="col">Original choices and rationale</th><th scope="col">Explore</th></tr></thead><tbody>
      {lineage.data?.items.map(row => <tr key={row.context.revision_id}><td>{row.context.revision_id}<p>Parent: {row.parent_id ?? 'Initial revision'}</p><p>Accepted on branch: {row.context.branch_id}</p></td>
        <td><p>Selected: {row.selected_id ?? 'No civic choice selected'}</p><details><summary>Offered alternatives</summary>{row.alternatives.map(a => <section key={a.id}><strong>{a.id}</strong>{a.wording.map((text, i) => <p key={i}>{text}</p>)}</section>)}</details>
          <p>{row.rationale ? `Private rationale: ${row.rationale.status}. Inspect this revision to read its separately stored text.` : 'No rationale recorded.'}</p></td>
        <td><button disabled={locked} onClick={() => void inspect(row.context.revision_id)}>Inspect revision {row.context.revision_id}</button>
          <button disabled={locked} onClick={() => { setOther(row.context.revision_id); setComparisonCursor(null); }}>Compare with {row.context.revision_id}</button>
          <button disabled={locked} onClick={() => setTarget(row.context.revision_id)}>Use as fork or restore target</button></td></tr>)}
    </tbody></table>
    <button disabled={locked || !cursor} onClick={() => setCursor(null)}>First lineage page</button>
    <button disabled={locked || !lineage.data?.next_cursor} onClick={() => setCursor(lineage.data!.next_cursor)}>Next lineage page</button>
    <label>Compare with retained revision<input maxLength={128} value={other} onChange={e => { setOther(e.target.value); setComparisonCursor(null); }} /></label>
    {comparison.data && <section aria-label="Retained comparison"><h4>Left: {state.context.revision_id} · Right: {other}</h4>
      <p>Left evidence: {comparison.data.left_evidence} · Model: {comparison.data.left_versions.model_id}. Right evidence: {comparison.data.right_evidence} · Model: {comparison.data.right_versions.model_id}.</p>
      <table><caption>Exact retained outcomes and compatible deltas</caption><thead><tr><th scope="col">Indicator and scope</th><th scope="col">Left</th><th scope="col">Right</th><th scope="col">Right minus left</th></tr></thead><tbody>
        {comparison.data.items.map(row => <tr key={row.id}><th scope="row">{row.left.definition?.name ?? row.right.definition?.name ?? row.id}<p>{row.id}</p><p>{row.left.definition?.scope_id ?? row.right.definition?.scope_id}</p></th>
          {[row.left, row.right].map((v, i) => <td key={i}>{v.observation ? valueText(v.observation.value) : 'Unavailable'}<p>{v.origin === 'retained_evidence' ? 'Retained evidence' : 'Unavailable evidence'} · {v.observation?.status ?? 'Unavailable'}</p><p>Trace evidence: {v.trace_state}</p>{v.observation && <p>Tick {v.observation.effective_time.tick} · {v.observation.effective_time.calendar_id}</p>}</td>)}
          <td>{row.delta ? valueText(row.delta) : 'Not comparable'}{row.reasons.map(r => <p key={r}>{r}</p>)}</td></tr>)}
      </tbody></table>
      {comparison.data.items.length === 0 && <p>No numerical outcomes on this page. Unavailable evidence is never recomputed or replaced with zero.</p>}
      <h4>Changed choices, assumptions and evidence</h4>{comparison.data.changes.length === 0 && <p>No changes on this page.</p>}
      {comparison.data.changes.map(c => <section key={c.kind + c.id}><h5>{c.kind}: {c.id}</h5><p>Left: {c.before ?? 'Absent'}</p><p>Right: {c.after ?? 'Absent'}</p></section>)}
      <button disabled={locked || !comparisonCursor} onClick={() => setComparisonCursor(null)}>First comparison page</button>
      <button disabled={locked || !comparison.data.next_cursor} onClick={() => setComparisonCursor(comparison.data!.next_cursor)}>Next comparison page</button>
    </section>}
  </section>;
}
