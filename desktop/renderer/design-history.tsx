import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { GitBranch, GitCompare, Lock } from 'lucide-react';
import type { WorkspaceState } from '../../contracts/workspace';
import type { RationaleReply, HistoryAction, LineagePage, ComparePage } from '../../contracts/comparison';
import { valueText } from './overview';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Actions, DataTable, Disclosure, Field, Hint, SubHeading, Toolbar } from '@/components/app/form';
import { ErrorNote, Panel, StateBadge } from '@/components/app/blocks';

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
  return <section aria-label="Design history" className="flex flex-col gap-4">
    <Panel title="Design history" description="Undo and restore preserve alternate futures. Comparisons use retained results; no model is rerun, no branch is ranked. A positive delta means right minus left."
      action={historical ? <StateBadge tone="warning">Historical revision — read only</StateBadge> : <StateBadge tone="success">Confirmed design revision</StateBadge>}>
      <Hint>Inspecting {state.context.revision_id}. Branch head: {lineage.data?.branch.context.revision_id ?? state.branch.context.revision_id}.</Hint>
      {(error || lineage.isError || comparison.isError) && <ErrorNote title="Saved history could not be read">{error || 'Saved history or comparison could not be read. Reopen the branch to retry.'}</ErrorNote>}
      <Actions className="mt-3">
        {pending && <Button variant="outline" size="sm" disabled={busy} onClick={() => void mutate(pending)}>Retry history action</Button>}
        {historical && <Button variant="outline" size="sm" disabled={locked} onClick={() => void inspect(state.branch.context.revision_id)}>Return to branch head</Button>}
        <Button variant="outline" size="sm" disabled={locked} onClick={() => { setBusy(true); setError(''); void window.poliscope.rationale({context:state.context}).then(setPrivateNote).catch(() => setError('Private rationale could not be read.')).finally(() => setBusy(false)); }}>
          <Lock aria-hidden />Read private rationale for inspected revision
        </Button>
      </Actions>
      {privateNote && <section aria-label="Private rationale" className="mt-3 rounded-xl border border-warning/40 bg-warning/5 p-3">
        <SubHeading as="h5">Private rationale</SubHeading>
        <Hint className="mt-1">Private · local only · {privateNote.reference?.status ?? 'No rationale recorded'}</Hint>
        <p className="mt-1 text-xs leading-relaxed">{privateNote.text ?? 'Rationale text unavailable.'}</p>
        <Actions className="mt-2"><Button variant="outline" size="sm" onClick={() => setPrivateNote(undefined)}>Hide private rationale</Button></Actions>
      </section>}
      <fieldset disabled={locked || historical || !lineage.data} className="m-0 mt-4 min-w-0 border-0 p-0">
        <legend className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Change the selected branch</legend>
        <Actions>
          <Button variant="outline" disabled={!lineage.data?.can_undo} onClick={() => void action('undo')}>Undo design change</Button>
          <Button variant="outline" disabled={!lineage.data?.branch.redo.length} onClick={() => void action('redo')}>Redo design change</Button>
        </Actions>
        <Toolbar className="mt-3">
          <Field label="Branch name" className="w-56"><Input maxLength={256} value={name} onChange={e => setName(e.target.value)} /></Field>
          <Button variant="outline" disabled={!name.trim()} onClick={() => void action('rename')}>Rename branch</Button>
          <Field label="Revision to fork or restore" className="w-56"><Input maxLength={128} value={target} onChange={e => setTarget(e.target.value)} placeholder="Current revision by default" /></Field>
          <Button variant="outline" disabled={!name.trim()} onClick={() => void action('fork')}>Fork revision</Button>
          <Button variant="outline" disabled={!target} onClick={() => void action('restore')}>Restore revision and retain current future</Button>
        </Toolbar>
      </fieldset>
    </Panel>

    <Panel label="Design lineage" title="Retained design lineage" description="Every future in this civilization stays attached to its original revision. Inspecting a revision is a read, never a reproduction.">
      <DataTable>
        <caption>Retained design lineage · all futures in this civilization</caption>
        <thead><tr><th scope="col">Revision and parent</th><th scope="col">Original choices and rationale</th><th scope="col">Explore</th></tr></thead>
        <tbody>
          {lineage.data?.items.map(row => <tr key={row.context.revision_id}>
            <td><span className="tabular-nums">{row.context.revision_id}</span><p className="mt-1 text-xs text-muted-foreground">Parent: {row.parent_id ?? 'Initial revision'}</p><p className="text-xs text-muted-foreground">Accepted on branch: {row.context.branch_id}</p></td>
            <td><p className="text-xs">Selected: {row.selected_id ?? 'No civic choice selected'}</p>
              <Disclosure title="Offered alternatives" className="mt-2 bg-card">{row.alternatives.map(a => <section key={a.id}><strong className="text-xs">{a.id}</strong>{a.wording.map((text, i) => <p key={i} className="mt-1 text-xs leading-relaxed">{text}</p>)}</section>)}</Disclosure>
              <p className="mt-2 text-xs text-muted-foreground">{row.rationale ? `Private rationale: ${row.rationale.status}. Inspect this revision to read its separately stored text.` : 'No rationale recorded.'}</p></td>
            <td><Actions className="gap-1">
              <Button variant="link" size="sm" className="h-auto p-0 text-left" disabled={locked} onClick={() => void inspect(row.context.revision_id)}>Inspect revision {row.context.revision_id}</Button>
              <Button variant="link" size="sm" className="h-auto p-0 text-left" disabled={locked} onClick={() => { setOther(row.context.revision_id); setComparisonCursor(null); }}>Compare with {row.context.revision_id}</Button>
              <Button variant="ghost" size="xs" disabled={locked} onClick={() => setTarget(row.context.revision_id)}>Use as fork or restore target</Button>
            </Actions></td>
          </tr>)}
        </tbody>
      </DataTable>
      <Actions className="mt-3">
        <Button variant="outline" size="sm" disabled={locked || !cursor} onClick={() => setCursor(null)}>First lineage page</Button>
        <Button variant="outline" size="sm" disabled={locked || !lineage.data?.next_cursor} onClick={() => setCursor(lineage.data!.next_cursor)}>Next lineage page</Button>
      </Actions>
      <Toolbar className="mt-3">
        <Field label="Compare with retained revision" className="w-64"><Input maxLength={128} value={other} onChange={e => { setOther(e.target.value); setComparisonCursor(null); }} /></Field>
      </Toolbar>
    </Panel>

    {comparison.data && <Panel label="Retained comparison" title="Retained comparison" action={<StateBadge tone="info"><GitCompare aria-hidden />Retained results</StateBadge>}>
      <div className="flex flex-wrap items-baseline gap-x-2">
        <SubHeading as="h4">Left: {state.context.revision_id}</SubHeading>
        <span className="text-xs text-muted-foreground">· Right: {other}</span>
      </div>
      <Hint className="mt-1">Left evidence: {comparison.data.left_evidence} · Model: {comparison.data.left_versions.model_id}. Right evidence: {comparison.data.right_evidence} · Model: {comparison.data.right_versions.model_id}.</Hint>
      <DataTable className="mt-3">
        <caption>Exact retained outcomes and compatible deltas</caption>
        <thead><tr><th scope="col">Indicator and scope</th><th scope="col">Left</th><th scope="col">Right</th><th scope="col">Right minus left</th></tr></thead>
        <tbody>
          {comparison.data.items.map(row => <tr key={row.id}>
            <th scope="row">{row.left.definition?.name ?? row.right.definition?.name ?? row.id}<p className="mt-1 text-xs text-muted-foreground">{row.id}</p><p className="text-xs text-muted-foreground">{row.left.definition?.scope_id ?? row.right.definition?.scope_id}</p></th>
            {[row.left, row.right].map((v, i) => <td key={i}>{v.observation ? valueText(v.observation.value) : 'Unavailable'}<p className="mt-1 text-xs text-muted-foreground">{v.origin === 'retained_evidence' ? 'Retained evidence' : 'Unavailable evidence'} · {v.observation?.status ?? 'Unavailable'}</p><p className="text-xs text-muted-foreground">Trace evidence: {v.trace_state}</p>{v.observation && <p className="text-xs text-muted-foreground">Tick {v.observation.effective_time.tick} · {v.observation.effective_time.calendar_id}</p>}</td>)}
            <td>{row.delta ? valueText(row.delta) : 'Not comparable'}{row.reasons.map(r => <p key={r} className="mt-1 text-xs text-muted-foreground">{r}</p>)}</td>
          </tr>)}
        </tbody>
      </DataTable>
      {comparison.data.items.length === 0 && <Hint className="mt-2">No numerical outcomes on this page. Unavailable evidence is never recomputed or replaced with zero.</Hint>}
      <SubHeading as="h4" className="mt-4">Changed choices, assumptions and evidence</SubHeading>
      {comparison.data.changes.length === 0 && <Hint>No changes on this page.</Hint>}
      <div className="mt-2 flex flex-col gap-2">{comparison.data.changes.map(c => <section key={c.kind + c.id} className="rounded-xl bg-muted/40 p-3">
        <SubHeading as="h5">{c.kind}: {c.id}</SubHeading>
        <p className="mt-1 text-xs">Left: {c.before ?? 'Absent'}</p><p className="text-xs">Right: {c.after ?? 'Absent'}</p>
      </section>)}</div>
      <Actions className="mt-3">
        <Button variant="outline" size="sm" disabled={locked || !comparisonCursor} onClick={() => setComparisonCursor(null)}>First comparison page</Button>
        <Button variant="outline" size="sm" disabled={locked || !comparison.data.next_cursor} onClick={() => setComparisonCursor(comparison.data!.next_cursor)}>Next comparison page</Button>
      </Actions>
    </Panel>}
  </section>;
}
