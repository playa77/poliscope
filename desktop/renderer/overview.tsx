import { Commitment } from './interview';
import React, { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer } from 'recharts';
import type { WorkspaceState } from '../../contracts/workspace';
import type { OverviewQuery, OverviewPage, IndicatorRow, TargetReply } from '../../contracts/overview';
import { contextKey } from './workspace';

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
function Retry({ retry }: { retry: () => void }) { return <p role="alert">This evidence could not be read. <button onClick={retry}>Retry evidence read</button></p>; }
function Target({ row, state, scope }: { row: IndicatorRow; state: WorkspaceState; scope: string }) {
  const [threshold, setThreshold] = useState('');
  const [operation, setOperation] = useState<'ge' | 'le' | 'eq'>('ge');
  const [result, setResult] = useState<TargetReply>();
  const [error, setError] = useState(false), [busy, setBusy] = useState(false);
  const d = row.definition;
  return <details><summary>Try a session target for {d.name}</summary>
    <p>Compared after evaluation. This session target leaves saved goals, diagnostics and calculations unchanged.</p>
    <form onSubmit={e => { e.preventDefault(); setBusy(true); setError(false); setResult(undefined);
      void window.poliscope.target({ context: state.context, scope_id: scope, indicator_id: row.id, operation,
        threshold: { kind: 'quantity', value: threshold, unit_id: d.unit_id, time_basis_id: d.time_basis_id, denominator_scope_id: d.denominator_scope_id } })
        .then(setResult).catch(() => setError(true)).finally(() => setBusy(false));
    }}><label>Target comparison<select disabled={busy} value={operation} onChange={e => { setOperation(e.target.value as typeof operation); setResult(undefined); }}><option value="ge">At least</option><option value="le">At most</option><option value="eq">Exactly</option></select></label>
      <label>Target value ({d.unit_id})<input disabled={busy} required maxLength={256} value={threshold} onChange={e => { setThreshold(e.target.value); setResult(undefined); }} /></label>
      <button disabled={busy}>Compare session target</button>
    </form>
    {error && <p role="alert">Enter a valid exact decimal target with this indicator’s unit and time basis.</p>}
    {result && <p aria-live="polite">{result.observation.matched === null ? `Target unavailable: ${result.observation.reason}` : result.observation.matched ? 'Within your target' : 'Outside your target'}. This is a player observation.</p>}
  </details>;
}
function Chart({ state, scope, row }: { state: WorkspaceState; scope: string; row: IndicatorRow }) {
  const chart = useQuery({ queryKey: [...contextKey(state, scope, 'distribution-chart'), row.id], retry: false,
    queryFn: () => window.poliscope.chart({ context: state.context, scope_id: scope, indicator_id: row.id }) });
  if (chart.isError) return <Retry retry={() => void chart.refetch()} />;
  const points = chart.data?.points ?? [];
  const data = points.filter(p => p.approximate !== null).map(p => ({ name: p.label, value: Number(p.approximate) }));
  return <section aria-label="Indicator distribution chart"><p>Display approximation of matching named definitions ({row.definition.unit_id}). Exact observations and their scopes are in the distribution table. No spatial total is inferred.</p>
    {data.length > 0 && <div aria-hidden="true" style={{ height: 220 }}><ResponsiveContainer width="100%" height="100%"><BarChart data={data}><XAxis dataKey="name" hide /><YAxis /><Bar dataKey="value" fill="#aac6bd" isAnimationActive={false} /></BarChart></ResponsiveContainer></div>}
    {points.some(p => p.approximate === null) && <p>Some values cannot be drawn at display precision; inspect their exact table values.</p>}
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
  return <section aria-label="Diagnostic overview" className="overview">
    <h4>Conditions and diagnostics</h4>
    <p>Results are retained evidence for this revision. Coverage applies to the declared model; a successful diagnostic never establishes whole-society sufficiency.</p>
    {indicators.isError && <Retry retry={() => void indicators.refetch()} />}
    {indicators.isFetching && <p role="status">Reading retained indicators…</p>}
    {indicators.data && <p>Retained evidence: {indicators.data.evidence_state} · model coverage: {STATUS[indicators.data.coverage]}. No whole-system sufficiency claim is made.</p>}
    {!indicators.isFetching && !indicators.isError && rows.length === 0 && <p>No retained indicator results are available for this scope. Starting conditions below remain inspectable; numerical social effects are unmodeled.</p>}
    {rows.length > 0 && <details><summary>Choose overview indicators ({ids.length}/8)</summary><fieldset><legend>Small indicator set · this session</legend>{rows.map(r => <label key={r.id}><input type="checkbox" checked={ids.includes(r.id)} disabled={!ids.includes(r.id) && ids.length >= 8}
      onChange={e => setChosen(e.target.checked ? [...ids, r.id] : ids.filter(id => id !== r.id))} />{r.definition.name}</label>)}</fieldset></details>}
    <div className="indicator-grid">{rows.filter(r => ids.includes(r.id)).map(r => <section key={r.id} className={`indicator tone-${r.tone}`} aria-label={r.definition.name}>
      <h5>{r.definition.name}</h5><p className="diagnostic-label">{STATUS[r.observation.status]} · {DIAGNOSTIC[r.observation.diagnostic]}</p>
      <button className="quantity" title="Open definition and calculation" onClick={() => inspect('indicators', r.id)}>{valueText(r.observation.value)}</button>
      <p>Scope: {r.definition.scope_id} · Tick {r.observation.effective_time.tick} · {r.observation.effective_time.calendar_id}</p>
      <p>{r.definition.interpretation}</p>
      <p>{r.definition.diagnostics.length ? `Named thresholds: ${r.definition.diagnostics.map(d => d.name).join(', ')}` : 'No diagnostic threshold or desirable direction is defined.'}</p>
      <button onClick={() => inspect('indicators', r.id)}>Inspect {r.definition.name}</button>
      <button onClick={() => { setCharted(r.id); setCollection('indicators'); setExpanded(true); }}>Show local/group distribution</button>
      <Target key={r.id} row={r} state={state} scope={scope} />
    </section>)}</div>
    <section aria-label="Findings across scopes"><h4>Findings across scopes</h4><p>Local shortages and access constraints remain visible beside surplus elsewhere. Unanswered models and missing relationships are exclusions, not evidence of independence.</p>
      {findings.isError && <Retry retry={() => void findings.refetch()} />}
      {!findings.isFetching && findings.data?.items.length === 0 && <p>No findings are recorded. This does not certify complete coverage.</p>}
      <ul>{findings.data?.items.map(r => r.kind === 'finding' && <li key={r.id}><button onClick={() => inspect('findings', r.id)}>{r.finding.category.replaceAll('_', ' ')} · {r.finding.scope_id ?? 'multiple/unspecified scopes'} · {STATUS[r.finding.status]}</button><p>{r.message}</p></li>)}</ul>
    </section>
    <details open={expanded} onToggle={e => setExpanded(e.currentTarget.open)}><summary>Distributions, accounts and commitments</summary>
      <label>Retained collection<select value={collection} onChange={e => { setCollection(e.target.value as typeof collection); setCharted(undefined); }}>{['indicators', 'accounts', 'policies', 'goals', 'conditions'].map(c => <option key={c} value={c}>{c}</option>)}</select></label>
      <p>Each row retains its own scope, unit and time basis. Overlapping groups are not added together. Policies are selected commitments; goals are player targets.</p>
      {extra.isError && <Retry retry={() => void extra.refetch()} />}
      {extra.isFetching ? <p role="status">Reading distribution…</p> : <table><caption>Exact retained values across local and group scopes</caption><thead><tr><th scope="col">Definition</th><th scope="col">Scope</th><th scope="col">Value / status</th></tr></thead><tbody>{extra.data?.items.map(r => <DistributionRow key={r.id} row={r} inspect={() => inspect(collection, r.id)} />)}</tbody></table>}
      {!extra.isFetching && extra.data?.items.length === 0 && <p>No {collection} are recorded.</p>}
      {charted && rows.find(r => r.id === charted) && <Chart state={state} scope={scope} row={rows.find(r => r.id === charted)!} />}
    </details>
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
  return <tr><th scope="row">{name}</th><td>{scope}</td><td><button onClick={inspect}>{text}</button></td></tr>;
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
  return <aside aria-label="Evidence inspector" className="evidence-inspector" onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); close(); } }}><h4>Definition and evidence</h4><button ref={closeButton} onClick={close}>Close evidence inspector</button>
    <p>Revision: {state.context.revision_id} · model {state.versions.model_id} · tick {state.effective_time.tick} · scope {scope}</p>
    {detail.isFetching && <p role="status">Reading definition and evidence…</p>}
    {detail.isError && <Retry retry={() => void detail.refetch()} />}
    {row?.kind === 'indicator' && <><h5>{row.definition.name}</h5><p>{STATUS[row.observation.status]} · {row.observation.reason} · {valueText(row.observation.value)}</p><p>{DIAGNOSTIC[row.observation.diagnostic]}</p>
      <h5>Definition and inputs</h5><p>{row.definition.procedure} · {row.definition.aggregation} · {row.definition.unit_id} · scope {row.definition.scope_id} · time {row.definition.time_basis_id ?? 'stock / observation instant'} · denominator {row.definition.denominator_scope_id ?? 'none'}</p>
      <ul>{row.definition.inputs.map(i => <li key={JSON.stringify(i.node)}>{i.node.join(' → ')} · {i.scope_id}</li>)}</ul>
      <h5>Source/model rationale</h5><p>{row.definition.interpretation}</p><p>Definition coverage: {STATUS[row.definition.coverage]}</p>
      <h5>Named diagnostic thresholds</h5>{!row.definition.diagnostics.length && <p>None. This observation is neutral.</p>}
      {row.definition.diagnostics.map(d => <section key={d.id}><strong>{d.name} · {d.version}</strong><p>{d.operation} {valueText(d.threshold)} · {d.category}</p><p>{d.interpretation}</p>{[...d.source_refs, ...d.assumption_refs].map(id => <button key={id} onClick={() => setReference(id)}>Evidence {id}</button>)}</section>)}
    </>}
    {row?.kind === 'condition' && <><h5>Authored condition: {row.condition.property_id}</h5><p>{valueText(row.condition.value)}</p><p>Scope {row.condition.scope_id} · tick {row.condition.effective_time.tick} · entity {row.condition.entity_id} · owner {row.writer_id ?? 'unavailable'} · origin {row.condition.provenance.origin}</p><p>Player/authored input, not a calculated social outcome. No numerical calculation trace is invented for this condition.</p></>}
    {row?.kind === 'account' && <><h5>Account: {row.id}</h5><p>{row.definition.kind} · {row.definition.unit_id} · scope {row.definition.scope_id} · period {row.definition.period_id ?? 'stock'} · invariant {row.definition.invariant}</p>
      <table><caption>Exact reconciled account</caption><tbody>{['opening', 'quantum', 'maximum'].map(k => <tr key={k}><th scope="row">{k}</th><td>{row.definition[k as 'opening']} {row.definition.unit_id}</td></tr>)}{['closing', 'available', 'outstanding_reserved'].map(k => <tr key={k}><th scope="row">{k}</th><td>{row.result[k as 'closing']} {row.definition.unit_id}</td></tr>)}</tbody></table></>}
    {row?.kind === 'finding' && <><h5>{row.finding.category.replaceAll('_', ' ')}</h5><p>{row.message}</p><p>{STATUS[row.finding.status]} · scope {row.finding.scope_id ?? 'multiple/unspecified'} · rule {row.finding.rule_ref ?? 'none'}</p><ul>{row.finding.values.map((v, i) => <li key={i}>{valueText(v)}</li>)}</ul></>}
    {row?.kind === 'commitment' && <><h5>{row.label} · qualitative selected commitment</h5>{row.condition.value.kind === 'label' ? <Commitment text={row.condition.value.value} /> : <p>{valueText(row.condition.value)}</p>}<p>Scope {row.condition.scope_id} · origin {row.condition.provenance.origin}. No numerical effects are assigned to this prose.</p></>}
    {row?.kind === 'policy' && <><h5>Selected policy commitment</h5><p>{row.policy.mechanism.id} · {row.policy.mechanism.version} · authority {row.policy.authority_id} · scope {row.policy.scope_id}</p><p>{row.policy.parameter_id}: {valueText(row.policy.value)}</p></>}
    {row?.kind === 'goal' && <><h5>Player target / question</h5><p>{row.definition.question}</p><p>{row.definition.operation} {row.definition.threshold && valueText(row.definition.threshold)}</p><p>{row.observation.status} · {row.observation.matched === true ? 'Within your target' : row.observation.matched === false ? 'Outside your target' : row.observation.reason}</p></>}
    {selection.collection === 'traces' && <Traces key={root ?? selection.id} state={state} scope={scope} root={root ?? selection.id} reference={setReference} follow={setRoot} />}
    {selection.collection === 'references' && <Reference state={state} scope={scope} id={selection.id} />}
    <h5>Python calculation trace</h5>{roots.map(id => <button key={id} onClick={() => setRoot(id)}>Open calculation {id}</button>)}
    {row && row.kind !== 'trace' && roots.length === 0 && <p>No calculation trace is recorded for this object.</p>}
    {root && selection.collection !== 'traces' && <Traces key={root} state={state} scope={scope} root={root} reference={setReference} follow={setRoot} />}
    <h5>Sources and assumptions</h5>{refs && [...refs.source_refs, ...('assumption_refs' in refs ? refs.assumption_refs : [])].map(id => <button key={id} onClick={() => setReference(id)}>Evidence {id}</button>)}
    {refs && refs.source_refs.length === 0 && (!('assumption_refs' in refs) || refs.assumption_refs.length === 0) && <p>No source or assumption references are recorded for this object.</p>}
    {reference && <Reference key={reference} state={state} scope={scope} id={reference} />}
    <p>Exclusions: only recorded model relationships and retained inputs are represented. Missing mechanisms remain unmodeled. Qualitative commitments have no invented numerical effects.</p>
    <h5>Optional generated explanation</h5><p>No AI explanation is attached. Authored rationale and Python traces remain separate evidence.</p>
  </aside>;
}
function Reference({ state, scope, id }: { state: WorkspaceState; scope: string; id: string }) {
  const data = useQuery({ queryKey: [...contextKey(state, scope, 'reference'), id], retry: false,
    queryFn: () => window.poliscope.overview(request(state, scope, 'references', true, id)) });
  const row = data.data?.items[0];
  return <section aria-label="Source or assumption"><h5>{id}</h5>{data.isError && <p>Reference unavailable in this retained closure.</p>}{row?.kind === 'reference' && <><p>{row.reference.kind} · {row.reference.visibility} · {row.reference.availability}</p><p>{row.reference.description}</p>{row.reference.source && <dl>{Object.entries(row.reference.source).map(([k, v]) => <React.Fragment key={k}><dt>{k.replaceAll('_', ' ')}</dt><dd>{Array.isArray(v) ? v.join(', ') : v}</dd></React.Fragment>)}</dl>}{row.reference.assumption && <dl>{Object.entries(row.reference.assumption).map(([k, v]) => <React.Fragment key={k}><dt>{k.replaceAll('_', ' ')}</dt><dd>{Array.isArray(v) ? v.join(', ') : v}</dd></React.Fragment>)}</dl>}</>}</section>;
}
function Traces({ state, scope, root, reference, follow }: { state: WorkspaceState; scope: string; root: string; reference: (id: string) => void; follow: (id: string) => void }) {
  const [cursor, setCursor] = useState<string | null>(null);
  const data = useQuery({ queryKey: [...contextKey(state, scope, 'trace-page'), root, cursor], retry: false,
    queryFn: () => window.poliscope.overview(request(state, scope, 'traces', true, root, cursor)) });
  return <section aria-label="Calculation trace page">{data.isError && <Retry retry={() => void data.refetch()} />}{data.isFetching && <p>Reading trace page…</p>}
    {data.data?.items.map(r => r.kind === 'trace' && <details key={r.id} open={r.id === root}><summary>{r.id} · {r.trace.kind}</summary>
      <p>Tick {r.trace.effective_time.tick} · {r.trace.effective_time.calendar_id}</p><ul>{r.trace.mechanisms.map(m => <li key={m.instance_id}>{m.mechanism_id} · {m.mechanism_version} · scope {m.scope_id} · entity {m.entity_id}</li>)}</ul>
      <table><caption>Typed inputs and calculated results</caption><thead><tr><th scope="col">Node</th><th scope="col">Scope / entity</th><th scope="col">Status / reason</th><th scope="col">Exact value</th></tr></thead><tbody>{r.trace.members.map(m => <tr key={JSON.stringify(m.node)}><th scope="row">{m.node.join(' → ')}</th><td>{m.scope_id} / {m.entity_id}</td><td>{STATUS[m.status]} · {m.reason}</td><td>{valueText(m.value)}</td></tr>)}</tbody></table>
      <p>Feedback edges: {r.trace.internal_edges.map(e => e.map(n => n.join(' → ')).join(' → ')).join('; ') || 'none'}</p>
      {r.trace.members.flatMap(m => [...m.source_refs, ...m.assumption_refs]).filter((id, i, all) => all.indexOf(id) === i).map(id => <button key={id} onClick={() => reference(id)}>Evidence {id}</button>)}
      <p>Dependencies:</p>{r.trace.dependency_refs.map(id => <button key={id} onClick={() => follow(id)}>Follow dependency {id}</button>)}
    </details>)}
    {data.data?.next_cursor && <button disabled={data.isFetching} onClick={() => setCursor(data.data!.next_cursor)}>Next trace page</button>}{cursor && <button onClick={() => setCursor(null)}>First trace page</button>}
  </section>;
}
