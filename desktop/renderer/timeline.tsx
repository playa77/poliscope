import React, { useEffect, useRef, useState } from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { Clock } from 'lucide-react';
import type { WorkspaceState } from '../../contracts/workspace';
import type { TimelineReply, TimelineRequest } from '../../contracts/timeline-workspace';
import { valueText } from './overview';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/app/native-select';
import { Actions, DataTable, Disclosure, Field, Hint, SubHeading, Toolbar } from '@/components/app/form';
import { EmptyState, ErrorNote, Panel, StateBadge } from '@/components/app/blocks';

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
  const control = reply?.control?.state;
  return <section aria-label="Timeline workspace" className="flex flex-col gap-4">
    <Panel title="Timeline and experiments" description="Execute simulation days independently of the displayed range. Only confirmed boundaries are saved. Unsupported dynamic models produce no inferred social effects."
      action={reply?.head ? <StateBadge tone={control === 'ready' ? 'success' : control === 'paused' ? 'warning' : 'neutral'}>{control ?? 'no control'}</StateBadge> : undefined}>
      <fieldset disabled={locked} className="m-0 min-w-0 border-0 p-0">
        <legend className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Open or create an experiment</legend>
        <Toolbar>
          <Field label="Experiment ID" className="w-56"><Input maxLength={128} value={name} onChange={e => { setName(e.target.value); setReply(undefined); }} /></Field>
          <Button variant="outline" onClick={() => void send(query('read'))}>Open saved experiment</Button>
          <Button disabled={!name} onClick={() => void send(query('create'))}>Create experiment from selected design</Button>
        </Toolbar>
        {!!reply?.experiments.length && <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <Hint className="mr-1">Saved experiments:</Hint>
          {reply.experiments.map(id => <Button key={id} variant="outline" size="xs" onClick={() => { setName(id); void send({ ...query('read'), experiment_id: id }); }}>{id}</Button>)}
        </div>}
      </fieldset>
      {error && <ErrorNote title="Request not confirmed">{error}</ErrorNote>}
      {busy && <Hint className="mt-3">Waiting for confirmed progress…</Hint>}
      {busy && pending?.action === 'advance' && !cancelling && <Actions className="mt-2"><Button variant="outline" size="sm" onClick={() => { setCancelling(true); void send(query('cancel')); }}>Cancel running advance</Button></Actions>}
      {cancelling && <Hint className="mt-2">Cancellation requested. The current bounded boundary may finish first; confirmed work stays saved. Inspect saved boundaries if acknowledgement is unconfirmed.</Hint>}
      {pending && <Actions className="mt-2">
        <Button variant="outline" size="sm" disabled={busy} onClick={() => void send(pending)}>Retry same timeline command</Button>
        <Button variant="ghost" size="sm" disabled={busy} onClick={() => void send(query('read'))}>Inspect saved boundaries</Button>
      </Actions>}
    </Panel>

    {!reply && <Panel title="No experiment open" description="Create an experiment from the selected design or open a saved one. A preview is never shown as a saved boundary.">
      <EmptyState icon={Clock} title="No confirmed timeline in this session" description="Nothing is loaded yet. Only confirmed boundaries are saved; unsupported dynamic models produce no inferred social effects." />
    </Panel>}

    {reply && <>
      <Panel title="Confirmed state" description={reply.notice}>
        {reply.head ? <>
          <Hint>Opening day {reply.opening?.day} · Current confirmed day {reply.head.day}, boundary sequence {reply.head.sequence} · {reply.control?.state}. Calendar: fixed-364-v1.</Hint>
          <Hint>Latest durable checkpoint: day {reply.checkpoint?.day ?? 'unavailable'}, sequence {reply.checkpoint?.sequence ?? 'unavailable'}.</Hint>
          <Hint>{reply.origin ? `Fork of ${reply.origin.context.experiment_id} at day ${reply.origin.day}; original history retained.` : 'Opened from a design revision; no parent simulation.'}</Hint>
          <fieldset disabled={locked} className="m-0 mt-3 min-w-0 border-0 p-0">
            <legend className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Execute or control this experiment</legend>
            <Toolbar>
              <Field label="Target simulation day" className="w-40"><Input type="number" min={reply.head.day} max={9007199254740991} value={day} onChange={e => setDay(Number(e.target.value))} /></Field>
              <Button disabled={reply.control?.state !== 'ready' || day <= reply.head.day} onClick={() => void send(query('advance'))}>Advance up to 10 boundaries</Button>
              <Button variant="outline" disabled={reply.control?.state !== 'ready'} onClick={() => void send(query('pause'))}>Pause experiment</Button>
              <Button variant="outline" disabled={reply.control?.state !== 'paused'} onClick={() => void send(query('resume'))}>Resume experiment</Button>
              <Button variant="destructive" disabled={reply.control?.state === 'cancelled'} onClick={() => void send(query('cancel'))}>Cancel experiment</Button>
            </Toolbar>
            <Hint className="mt-2">Pause and cancel take effect between bounded chunks. A confirmed chunk remains saved; cancelled experiments require a fork to continue.</Hint>
          </fieldset>
          <Disclosure title="Effective policy schedule and event origin" className="mt-3">
            {reply.schedule.length ? reply.schedule.map((s, i) => <pre key={i} className="max-h-60 overflow-auto rounded-lg bg-card p-3 text-xs">{s}</pre>) : <Hint>No dated events or policy adoptions.</Hint>}
          </Disclosure>
        </> : <Hint>{reply.notice}</Hint>}
      </Panel>

      <Panel title="Branch simulation history" description="A past fork starts at the selected retained state. Future scheduling starts at the current confirmed head and retains this experiment.">
        <fieldset disabled={locked} className="m-0 min-w-0 border-0 p-0">
          <legend className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Fork or schedule a future</legend>
          <Toolbar>
            <Field label="New experiment ID" className="w-48"><Input maxLength={128} value={child} onChange={e => setChild(e.target.value)} /></Field>
            <Field label="Fork realization policy" className="w-72">
              <NativeSelect value={realization} onChange={e => setRealization(e.target.value as typeof realization)}>
                <option value="preserve">Preserve seed and named identities for paired comparison</option><option value="new_realization">New realization with explicit seed</option>
              </NativeSelect>
            </Field>
            {realization === 'new_realization' && <Field label="New realization seed" className="w-44"><Input maxLength={256} value={seed} onChange={e => setSeed(e.target.value)} /></Field>}
            <Field label="Confirmed past sequence" className="w-40"><Input type="number" min={0} max={reply.head?.sequence ?? 0} value={sequence} onChange={e => setSequence(Number(e.target.value))} /></Field>
            <Field label="Approved policy revision" className="w-56"><Input maxLength={256} value={approved} onChange={e => setApproved(e.target.value)} /></Field>
          </Toolbar>
          <Actions className="mt-3">
            <Button variant="outline" disabled={!reply.entries.some(e => e.sequence === sequence) || !child || child === name} onClick={() => void send(query('fork'))}>Fork selected past state</Button>
            <Button variant="outline" disabled={!approved || !child || child === name || !reply.head || day <= reply.head.day} onClick={() => void send(query('preview_schedule'))}>Preview future policy schedule</Button>
            <Button disabled={locked || reply.query.action !== 'preview_schedule' || reply.query.source_revision_id !== approved || reply.query.other_id !== child || reply.query.target_day !== day} onClick={() => void send({ ...reply.query, action: 'schedule', operation_id: crypto.randomUUID() })}>Schedule approved policy in new future</Button>
          </Actions>
          <Hint className="mt-2">The target simulation day is the effective adoption day. Only explicit policy differences from an accepted parent/child revision are scheduled. Stocks and pending work continue.</Hint>
        </fieldset>
      </Panel>

      <Panel title="Confirmed sequences" description="Displayed confirmed sequences preserve their exact decimal strings; chart coordinates are display approximations."
        action={<Field label="Indicator for series and comparison" className="w-56">
          <NativeSelect disabled={locked} value={indicator ?? ''} onChange={e => { const id = e.target.value || null; setIndicator(id); void send({ ...query('read'), indicator_id: id }); }}>
            <option value="">First indicators</option>{reply.indicators.map(id => <option key={id} value={id}>{id}</option>)}
          </NativeSelect>
        </Field>}>
        <Hint>Displayed confirmed sequences {reply.entries[0]?.sequence ?? 'none'}–{reply.entries.at(-1)?.sequence ?? 'none'}. Chart coordinates approximate exact retained quantities for display; the table preserves their decimal strings.</Hint>
        {series.some(p => p.value !== null) && <div role="img" aria-label={`Time series for ${chartId}; exact values in table below`} className="mt-3 rounded-xl border border-border bg-muted/30 p-3"><ResponsiveContainer width="100%" height={200}><LineChart data={series}><XAxis dataKey="day" /><YAxis /><Tooltip /><Line dataKey="value" connectNulls={false} isAnimationActive={false} stroke="var(--primary)" /></LineChart></ResponsiveContainer></div>}
        <DataTable className="mt-3">
          <caption>Confirmed states, consequences and retained traces</caption>
          <thead><tr><th scope="col">Sequence / simulation day</th><th scope="col">Coverage and outcomes by scope</th><th scope="col">Consequences and traces</th></tr></thead>
          <tbody>{reply.entries.map(e => <tr key={e.digest}>
            <th scope="row" className="tabular-nums">{e.sequence} / {e.day}</th>
            <td>{e.coverage}{e.values.length === 0 && <p className="text-xs text-muted-foreground">Measurements unavailable; no zero substituted.</p>}{e.values.map(v => <p key={v.id} className="text-xs tabular-nums">{v.id} · {v.left.definition?.scope_id}: {valueText(v.left.observation?.value ?? null)} · {v.left.observation?.status ?? 'unavailable'}</p>)}</td>
            <td><Disclosure title="Inspect retained consequences" className="bg-card">
              <Hint>Trace records {traceOffset + 1}–{Math.min(traceOffset + 100, e.trace_count)} of {e.trace_count}.</Hint>
              {e.consequences.map((text, i) => <pre key={i} className="max-h-48 overflow-auto rounded-lg bg-muted/60 p-2 text-xs">{text}</pre>)}
              {e.traces.map(t => <p key={t} className="text-xs">Retained trace: {t}</p>)}
              {e.draws.map(d => <pre key={d.spec.variable_id} className="max-h-48 overflow-auto rounded-lg bg-muted/60 p-2 text-xs">{JSON.stringify(d)}</pre>)}
            </Disclosure></td>
          </tr>)}</tbody>
        </DataTable>
        <Actions className="mt-3">
          <Button variant="outline" size="sm" disabled={locked} onClick={() => void send(query('read'))}>First saved range</Button>
          <Button variant="outline" size="sm" disabled={locked || reply.next_after === null} onClick={() => void send(query('read', reply.next_after))}>Next saved range</Button>
          <Button variant="ghost" size="sm" disabled={locked || traceOffset === 0} onClick={() => void send({ ...query('read', reply.query.after), trace_offset: 0 })}>First retained trace range</Button>
          <Button variant="ghost" size="sm" disabled={locked || !reply.entries.some(e => e.trace_count > traceOffset + 100)} onClick={() => void send({ ...query('read', reply.query.after), trace_offset: traceOffset + 100 })}>Next retained trace range</Button>
        </Actions>
      </Panel>

      <Disclosure title="Selected assumptions and probability distributions" className="rounded-card border-0 bg-card px-5 py-4 shadow-[var(--shadow-card)]">
        {reply.assumptions.map((a, i) => <pre key={i} className="max-h-48 overflow-auto rounded-lg bg-muted/60 p-3 text-xs">{a}</pre>)}
        {distribution.length > 0 && <Field label="Declared distribution to plot" className="mt-2 w-56">
          <NativeSelect value={selectedDistribution?.variable_id ?? ''} onChange={e => setVariable(e.target.value)}>{distribution.map(d => <option key={d.variable_id} value={d.variable_id}>{d.variable_id}</option>)}</NativeSelect>
        </Field>}
        {weights.length > 0 && <div role="img" aria-label="Declared probability weights; exact distribution and assumptions in table" className="mt-3 rounded-xl border border-border bg-muted/30 p-3"><ResponsiveContainer width="100%" height={180}><BarChart data={weights}><XAxis dataKey="name" /><YAxis /><Tooltip /><Bar dataKey="weight" fill="var(--primary)" isAnimationActive={false} /></BarChart></ResponsiveContainer></div>}
        <DataTable className="mt-3">
          <caption>Declared distributions; realized trajectories do not estimate probabilities</caption>
          <thead><tr><th scope="col">Variable / scope</th><th scope="col">Distribution</th><th scope="col">Dependence / assumptions</th></tr></thead>
          <tbody>{distribution.map(d => <tr key={d.variable_id}><th scope="row">{d.variable_id} / {d.key.scope_id}</th><td className="text-xs">{JSON.stringify(d.distribution)}</td><td className="text-xs">{d.dependence} · {d.assumption_refs.join(', ')}</td></tr>)}</tbody>
        </DataTable>
      </Disclosure>

      <Panel title="Compare retained experiment states" description="Both sides use the confirmed sequence selected above; incompatible clocks, scopes, units or models withhold numerical deltas.">
        <fieldset disabled={locked} className="m-0 min-w-0 border-0 p-0">
          <legend className="sr-only">Comparison experiment</legend>
          <Toolbar>
            <Field label="Other experiment ID" className="w-56"><Input value={other} maxLength={128} onChange={e => setOther(e.target.value)} /></Field>
            <Button variant="outline" disabled={!other} onClick={() => void send(query('read'))}>Compare selected sequence</Button>
          </Toolbar>
        </fieldset>
        {reply.differences.map((d, i) => <pre key={i} className="mt-3 max-h-48 overflow-auto rounded-lg bg-muted/60 p-3 text-xs">{d}</pre>)}
        <DataTable className="mt-3">
          <caption>Retained local and group outcomes · right minus left</caption>
          <thead><tr><th scope="col">Indicator / scope</th><th scope="col">Left</th><th scope="col">Right</th><th scope="col">Difference / limitations</th></tr></thead>
          <tbody>{reply.comparisons.map(c => <tr key={c.id}><th scope="row">{c.id} / {c.left.definition?.scope_id ?? c.right.definition?.scope_id}</th><td className="tabular-nums">{valueText(c.left.observation?.value ?? null)}</td><td className="tabular-nums">{valueText(c.right.observation?.value ?? null)}</td><td className="tabular-nums">{valueText(c.delta)}{c.reasons.map(r => <p key={r} className="text-xs text-muted-foreground">{r}</p>)}</td></tr>)}</tbody>
        </DataTable>
      </Panel>
    </>}
  </section>;
}
