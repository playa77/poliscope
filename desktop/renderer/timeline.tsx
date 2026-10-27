import React, { useEffect, useRef, useState } from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import type { WorkspaceState } from '../../contracts/workspace';
import type { TimelineReply, TimelineRequest } from '../../contracts/timeline-workspace';
import { valueText } from './overview';

export function Timeline({ state, disabled }: { state: WorkspaceState; disabled: boolean }) {
  const [reply, setReply] = useState<TimelineReply>();
  const [name, setName] = useState('experiment');
  const [child, setChild] = useState('alternate');
  const [day, setDay] = useState(1);
  const [sequence, setSequence] = useState(0);
  const [approved, setApproved] = useState('');
  const [other, setOther] = useState('');
  const [indicator, setIndicator] = useState<string | null>(null);
  const [variable, setVariable] = useState('');
  const [realization, setRealization] = useState<'preserve' | 'new_realization'>('preserve');
  const [seed, setSeed] = useState('');
  const [busy, setBusy] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [pending, setPending] = useState<TimelineRequest>();
  const [error, setError] = useState('');
  const generation = useRef(0);
  useEffect(() => { generation.current++; setReply(undefined); setPending(undefined); setError(''); return () => { generation.current++; }; }, [state.context]);
  const locked = disabled || busy || Boolean(pending);
  async function send(request: TimelineRequest) {
    const id = ++generation.current;
    setBusy(true); setError('');
    if (request.action !== 'read' && request.action !== 'preview_schedule') setPending(request);
    try {
      const next = await window.poliscope.timeline(request);
      if (id !== generation.current) return;
      setReply(next); setPending(undefined); setCancelling(false);
      if (next.head) setName(next.head.context.experiment_id);
    } catch {
      if (id === generation.current) setError('Request not confirmed. Retry the same command or inspect saved boundaries. No preview is shown as saved. Historical clocks or models may be unavailable.');
    } finally { if (id === generation.current) setBusy(false); }
  }
  function query(action: TimelineRequest['action'], after: number | null = null): TimelineRequest {
    const source = reply?.entries.find(e => e.sequence === sequence);
    const expected = action === 'fork' && source && reply?.head ? { ...reply.head, sequence: source.sequence, day: source.day, boundary_digest: source.digest } : reply?.head ?? null;
    return { context: state.context, action, experiment_id: name, operation_id: crypto.randomUUID(),
      target_day: day, sequence: action === 'schedule' || action === 'preview_schedule' ? reply?.head?.sequence ?? 0 : sequence,
      other_id: action === 'fork' || action === 'schedule' || action === 'preview_schedule' ? child : other || null,
      source_revision_id: approved || null, expected, control: reply?.control ?? null, after, indicator_id: indicator, trace_offset: 0, realization_policy: realization, seed: realization === 'new_realization' ? seed || null : null };
  }
  const traceOffset = reply?.query.trace_offset ?? 0;
  const chartId = indicator ?? reply?.indicators[0];
  const series = reply?.entries.map(e => {
    const observation = e.values.find(v => v.id === chartId)?.left.observation;
    return { day: e.day, value: observation?.status === 'known' && observation.value.kind === 'quantity' ? Number(observation.value.value) : null };
  }) ?? [];
  const distribution = reply?.distributions ?? [];
  const selectedDistribution = distribution.find(d => d.variable_id === variable) ?? distribution[0];
  const law = selectedDistribution?.distribution;
  // Presentation coordinates only; the engine retains exact integer ratios.
  const weights = law?.kind === 'bernoulli' ? [{ name: 'true', weight: law.numerator }, { name: 'false', weight: law.denominator - law.numerator }]
    : law?.kind === 'categorical' ? law.outcomes.map(o => ({ name: o.value, weight: o.weight }))
    : law?.kind === 'uniform_integer' && law.high - law.low < 100 ? Array.from({ length: law.high - law.low + 1 }, (_, i) => ({ name: String(law.low + i), weight: 1 })) : [];
  return <section aria-label="Timeline workspace">
    <h3>Timeline and experiments</h3>
    <p>Execute simulation days independently of the displayed range. Only confirmed boundaries are saved. Unsupported dynamic models produce no inferred social effects.</p>
    <fieldset disabled={locked}><legend>Open or create an experiment</legend>
      <label>Experiment ID<input maxLength={128} value={name} onChange={e => { setName(e.target.value); setReply(undefined); }} /></label>
      <button onClick={() => void send(query('read'))}>Open saved experiment</button>
      <button disabled={!name} onClick={() => void send(query('create'))}>Create experiment from selected design</button>
      {reply?.experiments.map(id => <button key={id} onClick={() => { setName(id); void send({ ...query('read'), experiment_id: id }); }}>{id}</button>)}
    </fieldset>
    {error && <p role="alert">{error}</p>}
    {busy && <p role="status">Waiting for confirmed progress…</p>}
    {busy && pending?.action === 'advance' && !cancelling && <button onClick={() => {
      setCancelling(true); void send(query('cancel'));
    }}>Cancel running advance</button>}
    {cancelling && <p role="status">Cancellation requested. The current bounded boundary may finish first; confirmed work stays saved. Inspect saved boundaries if acknowledgement is unconfirmed.</p>}
    {pending && <button disabled={busy} onClick={() => void send(pending)}>Retry same timeline command</button>}
    {pending && <button disabled={busy} onClick={() => void send(query('read'))}>Inspect saved boundaries</button>}
    {reply && <p>{reply.notice}</p>}
    {reply?.head && <>
      <p>Opening day {reply.opening?.day} · Current confirmed day {reply.head.day}, boundary sequence {reply.head.sequence} · {reply.control?.state}. Calendar: fixed-364-v1.</p>
      <p>Latest durable checkpoint: day {reply.checkpoint?.day ?? 'unavailable'}, sequence {reply.checkpoint?.sequence ?? 'unavailable'}.</p>
      <p>{reply.origin ? `Fork of ${reply.origin.context.experiment_id} at day ${reply.origin.day}; original history retained.` : 'Opened from a design revision; no parent simulation.'}</p>
      <fieldset disabled={locked}><legend>Execute or control this experiment</legend>
        <label>Target simulation day<input type="number" min={reply.head.day} max={9007199254740991} value={day} onChange={e => setDay(Number(e.target.value))} /></label>
        <button disabled={reply.control?.state !== 'ready' || day <= reply.head.day} onClick={() => void send(query('advance'))}>Advance up to 10 boundaries</button>
        <button disabled={reply.control?.state !== 'ready'} onClick={() => void send(query('pause'))}>Pause experiment</button>
        <button disabled={reply.control?.state !== 'paused'} onClick={() => void send(query('resume'))}>Resume experiment</button>
        <button disabled={reply.control?.state === 'cancelled'} onClick={() => void send(query('cancel'))}>Cancel experiment</button>
      </fieldset>
      <p>Pause and cancel take effect between bounded chunks. A confirmed chunk remains saved; cancelled experiments require a fork to continue.</p>
      <details><summary>Effective policy schedule and event origin</summary>{reply.schedule.length ? reply.schedule.map((s, i) => <pre key={i}>{s}</pre>) : <p>No dated events or policy adoptions.</p>}</details>
      <fieldset disabled={locked}><legend>Branch simulation history</legend>
        <label>New experiment ID<input maxLength={128} value={child} onChange={e => setChild(e.target.value)} /></label>
        <label>Fork realization policy<select value={realization} onChange={e => setRealization(e.target.value as typeof realization)}><option value="preserve">Preserve seed and named identities for paired comparison</option><option value="new_realization">New realization with explicit seed</option></select></label>
        {realization === 'new_realization' && <label>New realization seed<input maxLength={256} value={seed} onChange={e => setSeed(e.target.value)} /></label>}
        <label>Confirmed past sequence<input type="number" min={0} max={reply.head.sequence} value={sequence} onChange={e => setSequence(Number(e.target.value))} /></label>
        <button disabled={!reply.entries.some(e => e.sequence === sequence) || !child || child === name} onClick={() => void send(query('fork'))}>Fork selected past state</button>
        <p>A past fork starts at the selected retained state. Future scheduling starts at the current confirmed head and retains this experiment.</p>
        <label>Approved policy revision<input maxLength={256} value={approved} onChange={e => setApproved(e.target.value)} /></label>
        <button disabled={!approved || !child || child === name || day <= reply.head.day} onClick={() => void send(query('preview_schedule'))}>Preview future policy schedule</button>
        <button disabled={locked || reply.query.action !== 'preview_schedule' || reply.query.source_revision_id !== approved || reply.query.other_id !== child || reply.query.target_day !== day} onClick={() => void send({ ...reply.query, action: 'schedule', operation_id: crypto.randomUUID() })}>Schedule approved policy in new future</button>
        <p>The target simulation day is the effective adoption day. Only explicit policy differences from an accepted parent/child revision are scheduled. Stocks and pending work continue.</p>
      </fieldset>
      <label>Indicator for series and comparison<select disabled={locked} value={indicator ?? ''} onChange={e => { const id = e.target.value || null; setIndicator(id); void send({ ...query('read'), indicator_id: id }); }}><option value="">First indicators</option>{reply.indicators.map(id => <option key={id} value={id}>{id}</option>)}</select></label>
      <p>Displayed confirmed sequences {reply.entries[0]?.sequence ?? 'none'}–{reply.entries.at(-1)?.sequence ?? 'none'}. Chart coordinates approximate exact retained quantities for display; the table preserves their decimal strings.</p>
      {series.some(p => p.value !== null) && <div role="img" aria-label={`Time series for ${chartId}; exact values in table below`}><ResponsiveContainer width="100%" height={200}><LineChart data={series}><XAxis dataKey="day" /><YAxis /><Tooltip /><Line dataKey="value" connectNulls={false} isAnimationActive={false} /></LineChart></ResponsiveContainer></div>}
      <table><caption>Confirmed states, consequences and retained traces</caption><thead><tr><th scope="col">Sequence / simulation day</th><th scope="col">Coverage and outcomes by scope</th><th scope="col">Consequences and traces</th></tr></thead><tbody>{reply.entries.map(e => <tr key={e.digest}><th scope="row">{e.sequence} / {e.day}</th><td>{e.coverage}{e.values.length === 0 && <p>Measurements unavailable; no zero substituted.</p>}{e.values.map(v => <p key={v.id}>{v.id} · {v.left.definition?.scope_id}: {valueText(v.left.observation?.value ?? null)} · {v.left.observation?.status ?? 'unavailable'}</p>)}</td><td><details><summary>Inspect retained consequences</summary><p>Trace records {traceOffset + 1}–{Math.min(traceOffset + 100, e.trace_count)} of {e.trace_count}.</p>{e.consequences.map((text, i) => <pre key={i}>{text}</pre>)}{e.traces.map(t => <p key={t}>Retained trace: {t}</p>)}{e.draws.map(d => <pre key={d.spec.variable_id}>{JSON.stringify(d)}</pre>)}</details></td></tr>)}</tbody></table>
      <button disabled={locked} onClick={() => void send(query('read'))}>First saved range</button>
      <button disabled={locked || reply.next_after === null} onClick={() => void send(query('read', reply.next_after))}>Next saved range</button>
      <button disabled={locked || traceOffset === 0} onClick={() => void send({ ...query('read', reply.query.after), trace_offset: 0 })}>First retained trace range</button>
      <button disabled={locked || !reply.entries.some(e => e.trace_count > traceOffset + 100)} onClick={() => void send({ ...query('read', reply.query.after), trace_offset: traceOffset + 100 })}>Next retained trace range</button>
      <details><summary>Selected assumptions and probability distributions</summary>{reply.assumptions.map((a, i) => <pre key={i}>{a}</pre>)}
        {distribution.length > 0 && <label>Declared distribution to plot<select value={selectedDistribution?.variable_id ?? ''} onChange={e => setVariable(e.target.value)}>{distribution.map(d => <option key={d.variable_id} value={d.variable_id}>{d.variable_id}</option>)}</select></label>}
        {weights.length > 0 && <div role="img" aria-label="Declared probability weights; exact distribution and assumptions in table"><ResponsiveContainer width="100%" height={180}><BarChart data={weights}><XAxis dataKey="name" /><YAxis /><Tooltip /><Bar dataKey="weight" isAnimationActive={false} /></BarChart></ResponsiveContainer></div>}
        <table><caption>Declared distributions; realized trajectories do not estimate probabilities</caption><thead><tr><th scope="col">Variable / scope</th><th scope="col">Distribution</th><th scope="col">Dependence / assumptions</th></tr></thead><tbody>{distribution.map(d => <tr key={d.variable_id}><th scope="row">{d.variable_id} / {d.key.scope_id}</th><td>{JSON.stringify(d.distribution)}</td><td>{d.dependence} · {d.assumption_refs.join(', ')}</td></tr>)}</tbody></table>
      </details>
      <fieldset disabled={locked}><legend>Compare retained experiment states without ranking</legend>
        <label>Other experiment ID<input value={other} maxLength={128} onChange={e => setOther(e.target.value)} /></label>
        <button disabled={!other} onClick={() => void send(query('read'))}>Compare selected sequence</button>
        <p>Both sides use the confirmed sequence selected above; incompatible clocks, scopes, units or models withhold numerical deltas.</p>
      </fieldset>
      {reply.differences.map((d, i) => <pre key={i}>{d}</pre>)}
      <table><caption>Retained local and group outcomes · right minus left</caption><thead><tr><th scope="col">Indicator / scope</th><th scope="col">Left</th><th scope="col">Right</th><th scope="col">Difference / limitations</th></tr></thead><tbody>{reply.comparisons.map(c => <tr key={c.id}><th scope="row">{c.id} / {c.left.definition?.scope_id ?? c.right.definition?.scope_id}</th><td>{valueText(c.left.observation?.value ?? null)}</td><td>{valueText(c.right.observation?.value ?? null)}</td><td>{valueText(c.delta)}{c.reasons.map(r => <p key={r}>{r}</p>)}</td></tr>)}</tbody></table>
    </>}
  </section>;
}
