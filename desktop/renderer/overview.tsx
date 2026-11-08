import { Commitment } from './interview';
import React, { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer } from 'recharts';
import { ArrowUpRight, Calculator, ListChecks, ScanSearch } from 'lucide-react';
import type { WorkspaceState } from '../../contracts/workspace';
import type { OverviewQuery, OverviewPage, IndicatorRow, TargetReply } from '../../contracts/overview';
import { contextKey } from './workspace';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/app/native-select';
import { DataTable, Disclosure, Field, Hint, SubHeading } from '@/components/app/form';
import { EmptyState, ErrorNote, Panel, StateBadge } from '@/components/app/blocks';

type OverviewRow = OverviewPage['items'][number];
type WorldValue = IndicatorRow['observation']['value'];
type Selection = { collection: OverviewQuery['collection']; id: string };
export function valueText(value: WorldValue | null): string {
  if (!value) return 'Unavailable';
  if (value.kind === 'unknown') return `Unknown: ${value.reason}`;
  if (value.kind === 'quantity') return `${value.value} ${value.unit_id}${value.time_basis_id ? ` / ${value.time_basis_id}` : ''}${value.denominator_scope_id ? ` per ${value.denominator_scope_id}` : ''}`;
  return value.kind === 'label' ? value.value : value.entity_id;
}
export const STATUS = { known: 'Known', partial: 'Partial coverage', missing_input: 'Missing input', unmodeled: 'Unmodeled', conflict: 'Conflict', solver_failure: 'Solver failure', not_applicable: 'Not applicable' };
const DIAGNOSTIC = { neutral: 'Neutral observation', within_named_thresholds: 'Named diagnostic condition met', flagged: 'Named diagnostic flagged', unavailable: 'Diagnostic unavailable' };
/** Semantic tone for the status badge; the word beside it always carries the meaning. */
const TONE: Record<keyof typeof STATUS, 'success' | 'warning' | 'destructive' | 'info' | 'neutral'> = {
  known: 'success', partial: 'warning', missing_input: 'warning', unmodeled: 'neutral',
  conflict: 'destructive', solver_failure: 'destructive', not_applicable: 'neutral',
};
const ACCENT: Record<IndicatorRow['tone'], string> = {
  green: 'before:bg-success', orange: 'before:bg-warning', red: 'before:bg-destructive',
  gray: 'before:bg-muted-foreground', neutral: 'before:bg-border',
};
function request(state: WorkspaceState, scope: string, collection: OverviewQuery['collection'], all = false, id: string | null = null, cursor: string | null = null): OverviewQuery {
  return { context: state.context, scope_id: scope, collection, all_scopes: all, item_id: id, cursor };
}
async function readRows(query: OverviewQuery, signal: AbortSignal) {
  const rows: OverviewRow[] = [];
  let cursor: string | null = null;
  const seen = new Set<string>();
  let envelope: OverviewPage | undefined;
  do {
    signal.throwIfAborted();
    const page = await window.poliscope.overview({ ...query, cursor });
    signal.throwIfAborted(); envelope = page; rows.push(...page.items); cursor = page.next_cursor;
    if (cursor && seen.has(cursor)) throw new Error('Repeated cursor');
    if (cursor) seen.add(cursor);
    if (rows.length > 10000) throw new Error('Overview collection exceeds limit');
  } while (cursor);
  return { ...envelope!, items: rows };
}
function useRows(state: WorkspaceState, scope: string, collection: OverviewQuery['collection'], all = false, enabled = true) {
  return useQuery({ queryKey: [...contextKey(state, scope, 'overview'), collection, all], retry: false, enabled,
    queryFn: ({ signal }) => readRows(request(state, scope, collection, all), signal) });
}
function Retry({ retry }: { retry: () => void }) {
  return <ErrorNote title="This evidence could not be read"><Button variant="outline" size="sm" onClick={retry}>Retry evidence read</Button></ErrorNote>;
}
function Target({ row, state, scope }: { row: IndicatorRow; state: WorkspaceState; scope: string }) {
  const [threshold, setThreshold] = useState('');
  const [operation, setOperation] = useState<'ge' | 'le' | 'eq'>('ge');
  const [result, setResult] = useState<TargetReply>();
  const [error, setError] = useState(false), [busy, setBusy] = useState(false);
  const d = row.definition;
  return <Disclosure title={`Try a session target for ${d.name}`} className="mt-auto bg-muted/50">
    <Hint>Compared after evaluation. This session target leaves saved goals, diagnostics and calculations unchanged.</Hint>
    <form className="flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); setBusy(true); setError(false); setResult(undefined);
      void window.poliscope.target({ context: state.context, scope_id: scope, indicator_id: row.id, operation,
        threshold: { kind: 'quantity', value: threshold, unit_id: d.unit_id, time_basis_id: d.time_basis_id, denominator_scope_id: d.denominator_scope_id } })
        .then(setResult).catch(() => setError(true)).finally(() => setBusy(false));
    }}>
      <Field label="Target comparison" className="w-36">
        <NativeSelect disabled={busy} value={operation} onChange={e => { setOperation(e.target.value as typeof operation); setResult(undefined); }}>
          <option value="ge">At least</option><option value="le">At most</option><option value="eq">Exactly</option>
        </NativeSelect>
      </Field>
      <Field label={`Target value (${d.unit_id})`} className="w-44">
        <Input disabled={busy} required maxLength={256} value={threshold} onChange={e => { setThreshold(e.target.value); setResult(undefined); }} />
      </Field>
      <Button variant="outline" disabled={busy}>Compare session target</Button>
    </form>
    {error && <ErrorNote title="This target was not compared">Enter a valid exact decimal target with this indicator’s unit and time basis.</ErrorNote>}
    {result && <p className="text-xs" aria-live="polite">{result.observation.matched === null ? `Target unavailable: ${result.observation.reason}` : result.observation.matched ? 'Within your target' : 'Outside your target'}. This is a player observation.</p>}
  </Disclosure>;
}
function Chart({ state, scope, row }: { state: WorkspaceState; scope: string; row: IndicatorRow }) {
  const chart = useQuery({ queryKey: [...contextKey(state, scope, 'distribution-chart'), row.id], retry: false,
    queryFn: () => window.poliscope.chart({ context: state.context, scope_id: scope, indicator_id: row.id }) });
  if (chart.isError) return <Retry retry={() => void chart.refetch()} />;
  const points = chart.data?.points ?? [];
  const data = points.filter(p => p.approximate !== null).map(p => ({ name: p.label, value: Number(p.approximate) }));
  return <section aria-label="Indicator distribution chart" className="rounded-xl border border-border bg-muted/40 p-4">
    <SubHeading>Distribution across named scopes</SubHeading>
    <Hint className="mt-1">Display approximation of matching named definitions ({row.definition.unit_id}). Exact observations and their scopes are in the distribution table. No spatial total is inferred.</Hint>
    {data.length > 0 && <div aria-hidden="true" className="mt-3" style={{ height: 220 }}><ResponsiveContainer width="100%" height="100%"><BarChart data={data}><XAxis dataKey="name" hide /><YAxis /><Bar dataKey="value" fill="var(--primary)" isAnimationActive={false} /></BarChart></ResponsiveContainer></div>}
    {points.some(p => p.approximate === null) && <Hint className="mt-2">Some values cannot be drawn at display precision; inspect their exact table values.</Hint>}
  </section>;
}
export function Overview({ state, scope }: { state: WorkspaceState; scope: string }) {
  const indicators = useRows(state, scope, 'indicators');
  // Findings remain visible across scopes even when indicators are hidden.
  const findings = useRows(state, scope, 'findings', true);
  const [chosen, setChosen] = useState<string[]>();
  const [selection, setSelection] = useState<Selection>();
  const [collection, setCollection] = useState<OverviewQuery['collection']>('accounts');
  const [expanded, setExpanded] = useState(false);
  const [charted, setCharted] = useState<string>();
  const extra = useRows(state, scope, collection, true, expanded);
  const rows = (indicators.data?.items ?? []).filter((r): r is IndicatorRow => r.kind === 'indicator');
  const ids = chosen ?? rows.slice(0, 4).map(r => r.id);
  const inspect = (collection: OverviewQuery['collection'], id: string) => setSelection({ collection, id });
  return <section aria-label="Diagnostic overview" className="overview flex flex-col gap-4">
    <Panel title="Conditions and diagnostics"
      description="Results are retained evidence for this revision. Coverage applies to the declared model; a successful diagnostic never establishes whole-society sufficiency."
      action={indicators.data ? <StateBadge tone="info">{STATUS[indicators.data.coverage]}</StateBadge> : undefined}>
      <div className="flex flex-col gap-3">
        {indicators.isError && <Retry retry={() => void indicators.refetch()} />}
        {indicators.isFetching && <Hint>Reading retained indicators…</Hint>}
        {indicators.data && <Hint>Retained evidence: {indicators.data.evidence_state} · model coverage: {STATUS[indicators.data.coverage]}. No whole-system sufficiency claim is made.</Hint>}
        {!indicators.isFetching && !indicators.isError && rows.length === 0 && (
          <EmptyState icon={ScanSearch} title="No retained indicator results" description="No retained indicator results are available for this scope. Starting conditions below remain inspectable; numerical social effects are unmodeled." />
        )}
        {rows.length > 0 && <Disclosure title={`Choose overview indicators (${ids.length}/8)`}>
          <fieldset className="m-0 min-w-0 border-0 p-0">
            <legend className="mb-2 text-[11px] uppercase tracking-wide text-muted-foreground">Small indicator set · this session</legend>
            <div className="grid gap-1.5 sm:grid-cols-2 xl:grid-cols-3">
              {rows.map(r => <label key={r.id} className="m-0 flex items-start gap-2 text-sm leading-relaxed">
                <input type="checkbox" className="mt-0.5 size-4 shrink-0 accent-primary" checked={ids.includes(r.id)} disabled={!ids.includes(r.id) && ids.length >= 8}
                  onChange={e => setChosen(e.target.checked ? [...ids, r.id] : ids.filter(id => id !== r.id))} />{r.definition.name}
              </label>)}
            </div>
          </fieldset>
        </Disclosure>}
        {rows.length > 0 && <div className="indicator-grid grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">{rows.filter(r => ids.includes(r.id)).map(r => (
          <section key={r.id} aria-label={r.definition.name}
            className={`indicator ${ACCENT[r.tone]} relative flex min-w-0 flex-col gap-2.5 overflow-hidden rounded-xl bg-muted/40 p-4 before:absolute before:inset-y-0 before:left-0 before:w-1`}>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <h5 className="min-w-0 text-sm font-semibold tracking-tight">{r.definition.name}</h5>
              <StateBadge tone={TONE[r.observation.status]}>{STATUS[r.observation.status]}</StateBadge>
            </div>
            <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{DIAGNOSTIC[r.observation.diagnostic]}</p>
            <Button variant="link" className="quantity h-auto w-fit justify-start p-0 text-2xl font-semibold tracking-tight tabular-nums" title="Open definition and calculation" onClick={() => inspect('indicators', r.id)}>{valueText(r.observation.value)}</Button>
            <p className="text-[11px] text-muted-foreground">Scope: {r.definition.scope_id} · Tick {r.observation.effective_time.tick} · {r.observation.effective_time.calendar_id}</p>
            <p className="text-xs leading-relaxed text-muted-foreground">{r.definition.interpretation}</p>
            <p className="text-[11px] leading-relaxed text-muted-foreground">{r.definition.diagnostics.length ? `Named thresholds: ${r.definition.diagnostics.map(d => d.name).join(', ')}` : 'No diagnostic threshold or desirable direction is defined.'}</p>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => inspect('indicators', r.id)}><ArrowUpRight aria-hidden />Inspect {r.definition.name}</Button>
              <Button variant="ghost" size="sm" onClick={() => { setCharted(r.id); setCollection('indicators'); setExpanded(true); }}><ListChecks aria-hidden />Show local/group distribution</Button>
            </div>
            <Target key={r.id} row={r} state={state} scope={scope} />
          </section>))}</div>}
      </div>
    </Panel>

    <Panel label="Findings across scopes" title="Findings across scopes" description="Local shortages and access constraints remain visible beside surplus elsewhere. Unanswered models and missing relationships are exclusions, not evidence of independence.">
      {findings.isError && <Retry retry={() => void findings.refetch()} />}
      {!findings.isFetching && findings.data?.items.length === 0 && <Hint>No findings are recorded. This does not certify complete coverage.</Hint>}
      {(findings.data?.items.length ?? 0) > 0 && <ul className="flex flex-col gap-2">{findings.data?.items.map(r => r.kind === 'finding' && (
        <li key={r.id} className="rounded-xl bg-muted/40 p-3">
          <Button variant="link" className="h-auto justify-start p-0 text-left text-sm font-medium" onClick={() => inspect('findings', r.id)}>{r.finding.category.replaceAll('_', ' ')} · {r.finding.scope_id ?? 'multiple/unspecified scopes'} · {STATUS[r.finding.status]}</Button>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{r.message}</p>
        </li>))}</ul>}
    </Panel>

    <Disclosure title="Distributions, accounts and commitments" open={expanded} onToggle={e => setExpanded(e.currentTarget.open)}
      className="rounded-card border-0 bg-card px-5 py-4 shadow-[var(--shadow-card)]">
      <Field label="Retained collection" className="w-56">
        <NativeSelect value={collection} onChange={e => { setCollection(e.target.value as typeof collection); setCharted(undefined); }}>
          {['indicators', 'accounts', 'policies', 'goals', 'conditions'].map(c => <option key={c} value={c}>{c}</option>)}
        </NativeSelect>
      </Field>
      <Hint>Each row retains its own scope, unit and time basis. Overlapping groups are not added together. Policies are selected commitments; goals are player targets.</Hint>
      {extra.isError && <Retry retry={() => void extra.refetch()} />}
      {extra.isFetching ? <Hint>Reading distribution…</Hint> : (
        <DataTable>
          <caption>Exact retained values across local and group scopes</caption>
          <thead><tr><th scope="col">Definition</th><th scope="col">Scope</th><th scope="col">Value / status</th></tr></thead>
          <tbody>{extra.data?.items.map(r => <DistributionRow key={r.id} row={r} inspect={() => inspect(collection, r.id)} />)}</tbody>
        </DataTable>
      )}
      {!extra.isFetching && extra.data?.items.length === 0 && <Hint>No {collection} are recorded.</Hint>}
      {charted && rows.find(r => r.id === charted) && <Chart state={state} scope={scope} row={rows.find(r => r.id === charted)!} />}
    </Disclosure>
    {selection && <Inspector key={JSON.stringify(selection)} state={state} scope={scope} selection={selection} close={() => setSelection(undefined)} />}
  </section>;
}
function DistributionRow({ row: r, inspect }: { row: OverviewRow; inspect: () => void }) {
  const name = r.kind === 'indicator' ? r.definition.name : r.kind === 'goal' ? r.definition.question : r.kind === 'commitment' ? r.label : r.id;
  const scope = r.kind === 'condition' || r.kind === 'commitment' ? r.condition.scope_id : r.kind === 'indicator' || r.kind === 'account' ? r.definition.scope_id : r.kind === 'policy' ? r.policy.scope_id : 'player / revision';
  let text = '';
  if (r.kind === 'indicator') text = `${valueText(r.observation.value)} · ${STATUS[r.observation.status]} · ${DIAGNOSTIC[r.observation.diagnostic]}`;
  if (r.kind === 'account') text = `${r.result.available} ${r.definition.unit_id}${r.definition.period_id ? ` / ${r.definition.period_id}` : ''} available`;
  if (r.kind === 'commitment') text = 'Qualitative selected commitment · inspect original wording';
  if (r.kind === 'condition') text = valueText(r.condition.value);
  if (r.kind === 'policy') text = `Selected commitment: ${valueText(r.policy.value)}`;
  if (r.kind === 'goal') text = `${r.observation.status}: ${r.observation.matched === true ? 'within your target' : r.observation.matched === false ? 'outside your target' : r.observation.reason}`;
  return <tr><th scope="row">{name}</th><td>{scope}</td><td><Button variant="link" className="h-auto justify-start p-0 text-left text-[0.8125rem]" onClick={inspect}>{text}</Button></td></tr>;
}
export function Inspector({ state, scope, selection, close }: { state: WorkspaceState; scope: string; selection: Selection; close: () => void }) {
  const closeButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const origin = document.activeElement;
    closeButton.current?.focus();
    return () => { if (origin instanceof HTMLElement && origin.isConnected) origin.focus(); };
  }, []);
  const detail = useQuery({ queryKey: [...contextKey(state, scope, 'inspector'), selection], retry: false,
    queryFn: () => window.poliscope.overview(request(state, scope, selection.collection, true, selection.id)) });
  const [root, setRoot] = useState<string>();
  const [reference, setReference] = useState<string>();
  const row = detail.data?.items[0];
  const refs = row?.kind === 'indicator' ? row.observation : row?.kind === 'condition' || row?.kind === 'commitment' ? row.condition.provenance : row?.kind === 'finding' ? row.finding : row?.kind === 'account' ? row.definition : undefined;
  const roots = row?.kind === 'indicator' ? row.observation.trace_refs : row?.kind === 'account' ? row.trace_refs : row?.kind === 'finding' ? row.finding.trace_refs : [];
  return <aside aria-label="Evidence inspector" className="flex min-w-0 flex-col gap-3 rounded-card bg-card p-5 shadow-[var(--shadow-card)]" onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); close(); } }}>
    <div className="flex flex-wrap items-start justify-between gap-2">
      <SubHeading as="h4">Definition and evidence</SubHeading>
      <Button ref={closeButton} variant="outline" size="sm" onClick={close}>Close evidence inspector</Button>
    </div>
    <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Revision: {state.context.revision_id} · model {state.versions.model_id} · tick {state.effective_time.tick} · scope {scope}</p>
    {detail.isFetching && <Hint>Reading definition and evidence…</Hint>}
    {detail.isError && <Retry retry={() => void detail.refetch()} />}
    {row?.kind === 'indicator' && <><SubHeading as="h5">{row.definition.name}</SubHeading><p className="text-sm">{STATUS[row.observation.status]} · {row.observation.reason} · {valueText(row.observation.value)}</p><Hint>{DIAGNOSTIC[row.observation.diagnostic]}</Hint>
      <SubHeading as="h5">Definition and inputs</SubHeading><p className="text-xs leading-relaxed">{row.definition.procedure} · {row.definition.aggregation} · {row.definition.unit_id} · scope {row.definition.scope_id} · time {row.definition.time_basis_id ?? 'stock / observation instant'} · denominator {row.definition.denominator_scope_id ?? 'none'}</p>
      <ul className="flex flex-col gap-1 text-xs">{row.definition.inputs.map(i => <li key={JSON.stringify(i.node)} className="rounded-lg bg-muted/60 px-2 py-1">{i.node.join(' → ')} · {i.scope_id}</li>)}</ul>
      <SubHeading as="h5">Source/model rationale</SubHeading><p className="text-xs leading-relaxed">{row.definition.interpretation}</p><Hint>Definition coverage: {STATUS[row.definition.coverage]}</Hint>
      <SubHeading as="h5">Named diagnostic thresholds</SubHeading>{!row.definition.diagnostics.length && <Hint>None. This observation is neutral.</Hint>}
      {row.definition.diagnostics.map(d => <section key={d.id} className="rounded-xl border border-border p-3"><strong className="text-sm">{d.name} · {d.version}</strong><p className="mt-1 text-xs">{d.operation} {valueText(d.threshold)} · {d.category}</p><p className="mt-1 text-xs leading-relaxed text-muted-foreground">{d.interpretation}</p><div className="mt-2 flex flex-wrap gap-2">{[...d.source_refs, ...d.assumption_refs].map(id => <Button key={id} variant="outline" size="xs" onClick={() => setReference(id)}>Evidence {id}</Button>)}</div></section>)}
    </>}
    {row?.kind === 'condition' && <><SubHeading as="h5">Authored condition: {row.condition.property_id}</SubHeading><p className="text-sm">{valueText(row.condition.value)}</p><Hint>Scope {row.condition.scope_id} · tick {row.condition.effective_time.tick} · entity {row.condition.entity_id} · owner {row.writer_id ?? 'unavailable'} · origin {row.condition.provenance.origin}</Hint><Hint>Player/authored input, not a calculated social outcome. No numerical calculation trace is invented for this condition.</Hint></>}
    {row?.kind === 'account' && <><SubHeading as="h5">Account: {row.id}</SubHeading><Hint>{row.definition.kind} · {row.definition.unit_id} · scope {row.definition.scope_id} · period {row.definition.period_id ?? 'stock'} · invariant {row.definition.invariant}</Hint>
      <DataTable><caption>Exact reconciled account</caption><tbody>{['opening', 'quantum', 'maximum'].map(k => <tr key={k}><th scope="row">{k}</th><td className="tabular-nums">{row.definition[k as 'opening']} {row.definition.unit_id}</td></tr>)}{['closing', 'available', 'outstanding_reserved'].map(k => <tr key={k}><th scope="row">{k}</th><td className="tabular-nums">{row.result[k as 'closing']} {row.definition.unit_id}</td></tr>)}</tbody></DataTable></>}
    {row?.kind === 'finding' && <><SubHeading as="h5">{row.finding.category.replaceAll('_', ' ')}</SubHeading><p className="text-sm">{row.message}</p><Hint>{STATUS[row.finding.status]} · scope {row.finding.scope_id ?? 'multiple/unspecified'} · rule {row.finding.rule_ref ?? 'none'}</Hint><ul className="flex flex-col gap-1 text-xs">{row.finding.values.map((v, i) => <li key={i}>{valueText(v)}</li>)}</ul></>}
    {row?.kind === 'commitment' && <><SubHeading as="h5">{row.label} · qualitative selected commitment</SubHeading>{row.condition.value.kind === 'label' ? <Commitment text={row.condition.value.value} /> : <p className="text-sm">{valueText(row.condition.value)}</p>}<Hint>Scope {row.condition.scope_id} · origin {row.condition.provenance.origin}. No numerical effects are assigned to this prose.</Hint></>}
    {row?.kind === 'policy' && <><SubHeading as="h5">Selected policy commitment</SubHeading><Hint>{row.policy.mechanism.id} · {row.policy.mechanism.version} · authority {row.policy.authority_id} · scope {row.policy.scope_id}</Hint><p className="text-sm">{row.policy.parameter_id}: {valueText(row.policy.value)}</p></>}
    {row?.kind === 'goal' && <><SubHeading as="h5">Player target / question</SubHeading><p className="text-sm">{row.definition.question}</p><Hint>{row.definition.operation} {row.definition.threshold && valueText(row.definition.threshold)}</Hint><Hint>{row.observation.status} · {row.observation.matched === true ? 'Within your target' : row.observation.matched === false ? 'Outside your target' : row.observation.reason}</Hint></>}
    {selection.collection === 'traces' && <Traces key={root ?? selection.id} state={state} scope={scope} root={root ?? selection.id} reference={setReference} follow={setRoot} />}
    {selection.collection === 'references' && <Reference state={state} scope={scope} id={selection.id} />}
    <SubHeading as="h5">Python calculation trace</SubHeading>
    {roots.map(id => <Button key={id} variant="outline" size="xs" className="w-fit" onClick={() => setRoot(id)}><Calculator aria-hidden />Open calculation {id}</Button>)}
    {row && row.kind !== 'trace' && roots.length === 0 && <Hint>No calculation trace is recorded for this object.</Hint>}
    {root && selection.collection !== 'traces' && <Traces key={root} state={state} scope={scope} root={root} reference={setReference} follow={setRoot} />}
    <SubHeading as="h5">Sources and assumptions</SubHeading>
    <div className="flex flex-wrap gap-2">{refs && [...refs.source_refs, ...('assumption_refs' in refs ? refs.assumption_refs : [])].map(id => <Button key={id} variant="outline" size="xs" onClick={() => setReference(id)}>Evidence {id}</Button>)}</div>
    {refs && refs.source_refs.length === 0 && (!('assumption_refs' in refs) || refs.assumption_refs.length === 0) && <Hint>No source or assumption references are recorded for this object.</Hint>}
    {reference && <Reference key={reference} state={state} scope={scope} id={reference} />}
    <Hint>Exclusions: only recorded model relationships and retained inputs are represented. Missing mechanisms remain unmodeled. Qualitative commitments have no invented numerical effects.</Hint>
    <SubHeading as="h5">Optional generated explanation</SubHeading><Hint>No AI explanation is attached. Authored rationale and Python traces remain separate evidence.</Hint>
  </aside>;
}
function Reference({ state, scope, id }: { state: WorkspaceState; scope: string; id: string }) {
  const data = useQuery({ queryKey: [...contextKey(state, scope, 'reference'), id], retry: false,
    queryFn: () => window.poliscope.overview(request(state, scope, 'references', true, id)) });
  const row = data.data?.items[0];
  return <section aria-label="Source or assumption" className="flex flex-col gap-2 rounded-xl border border-border bg-muted/40 p-3"><SubHeading as="h5">{id}</SubHeading>
    {data.isError && <Hint>Reference unavailable in this retained closure.</Hint>}
    {row?.kind === 'reference' && <><Hint>{row.reference.kind} · {row.reference.visibility} · {row.reference.availability}</Hint><p className="text-xs leading-relaxed">{row.reference.description}</p>
      {row.reference.source && <dl className="grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2">{Object.entries(row.reference.source).map(([k, v]) => <React.Fragment key={k}><dt className="text-muted-foreground">{k.replaceAll('_', ' ')}</dt><dd className="break-words">{Array.isArray(v) ? v.join(', ') : v}</dd></React.Fragment>)}</dl>}
      {row.reference.assumption && <dl className="grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2">{Object.entries(row.reference.assumption).map(([k, v]) => <React.Fragment key={k}><dt className="text-muted-foreground">{k.replaceAll('_', ' ')}</dt><dd className="break-words">{Array.isArray(v) ? v.join(', ') : v}</dd></React.Fragment>)}</dl>}</>}
  </section>;
}
function Traces({ state, scope, root, reference, follow }: { state: WorkspaceState; scope: string; root: string; reference: (id: string) => void; follow: (id: string) => void }) {
  const [cursor, setCursor] = useState<string | null>(null);
  const data = useQuery({ queryKey: [...contextKey(state, scope, 'trace-page'), root, cursor], retry: false,
    queryFn: () => window.poliscope.overview(request(state, scope, 'traces', true, root, cursor)) });
  return <section aria-label="Calculation trace page" className="flex flex-col gap-2">
    {data.isError && <Retry retry={() => void data.refetch()} />}{data.isFetching && <Hint>Reading trace page…</Hint>}
    {data.data?.items.map(r => r.kind === 'trace' && <Disclosure key={r.id} title={`${r.id} · ${r.trace.kind}`} open={r.id === root}>
      <Hint>Tick {r.trace.effective_time.tick} · {r.trace.effective_time.calendar_id}</Hint>
      <ul className="flex flex-col gap-1 text-xs">{r.trace.mechanisms.map(m => <li key={m.instance_id}>{m.mechanism_id} · {m.mechanism_version} · scope {m.scope_id} · entity {m.entity_id}</li>)}</ul>
      <DataTable><caption>Typed inputs and calculated results</caption><thead><tr><th scope="col">Node</th><th scope="col">Scope / entity</th><th scope="col">Status / reason</th><th scope="col">Exact value</th></tr></thead><tbody>{r.trace.members.map(m => <tr key={JSON.stringify(m.node)}><th scope="row">{m.node.join(' → ')}</th><td>{m.scope_id} / {m.entity_id}</td><td>{STATUS[m.status]} · {m.reason}</td><td className="tabular-nums">{valueText(m.value)}</td></tr>)}</tbody></DataTable>
      <Hint>Feedback edges: {r.trace.internal_edges.map(e => e.map(n => n.join(' → ')).join(' → ')).join('; ') || 'none'}</Hint>
      <div className="flex flex-wrap gap-2">{r.trace.members.flatMap(m => [...m.source_refs, ...m.assumption_refs]).filter((id, i, all) => all.indexOf(id) === i).map(id => <Button key={id} variant="outline" size="xs" onClick={() => reference(id)}>Evidence {id}</Button>)}</div>
      <Hint>Dependencies:</Hint>
      <div className="flex flex-wrap gap-2">{r.trace.dependency_refs.map(id => <Button key={id} variant="outline" size="xs" onClick={() => follow(id)}>Follow dependency {id}</Button>)}</div>
    </Disclosure>)}
    <div className="flex flex-wrap gap-2">
      {data.data?.next_cursor && <Button variant="outline" size="sm" disabled={data.isFetching} onClick={() => setCursor(data.data!.next_cursor)}>Next trace page</Button>}
      {cursor && <Button variant="ghost" size="sm" onClick={() => setCursor(null)}>First trace page</Button>}
    </div>
  </section>;
}
