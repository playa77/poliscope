import React, { useState } from 'react';
import { Sigma } from 'lucide-react';
import type { WorkspaceState, PartitionValueDTO } from '../../contracts/workspace';
import type { UncertaintyModel, UncertaintyReport, SensitivityReport, CapacityReport } from '../../contracts/uncertainty';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { NativeSelect } from '@/components/app/native-select';
import { Actions, DataTable, Disclosure, Field, Hint, SubHeading, Toolbar } from '@/components/app/form';
import { EmptyState, ErrorNote, Panel, StateBadge } from '@/components/app/blocks';

export function Uncertainty({ state, values, disabled }: { state: WorkspaceState; values: PartitionValueDTO[]; disabled: boolean }) {
  const quantities = values.filter(v => v.value.kind === 'quantity' && ['conditions', 'design', 'assumptions'].includes(v.partition));
  const [identity, setIdentity] = useState('');
  const selected = quantities.find(v => v.id === identity) ?? quantities[0];
  const [form, setForm] = useState<'point' | 'bounded_range' | 'distribution'>('bounded_range');
  const [low, setLow] = useState(''); const [high, setHigh] = useState('');
  const [pa, setPa] = useState(''); const [da, setDa] = useState('');
  const [pb, setPb] = useState(''); const [db, setDb] = useState('');
  const [threshold, setThreshold] = useState(''); const [rationale, setRationale] = useState('');
  const [left, setLeft] = useState(''); const [right, setRight] = useState('');
  const [report, setReport] = useState<UncertaintyReport>();
  const [variants, setVariants] = useState<SensitivityReport>();
  const [bound, setBound] = useState<CapacityReport>();
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const [solved, setSolved] = useState('population'); const [unit, setUnit] = useState('people');
  const [fixed, setFixed] = useState('0'); const [perUnit, setPerUnit] = useState('');
  const [ceiling, setCeiling] = useState(''); const [quantum, setQuantum] = useState('1');
  function model(): UncertaintyModel {
    return { id: 'player:uncertainty', version: 'v1', method: form === 'distribution' ? 'finite-factorization-v1' : 'affine-box-v1', dependence: form === 'distribution' ? 'declared_factorization' : 'declared_box',
      parameters: [{ id: 'parameter', version: 'v1', value_id: selected!.id, form, point: form === 'point' ? low : null,
        low: form === 'bounded_range' ? low : null, high: form === 'bounded_range' ? high : null,
        interpretation: rationale, source_refs: selected!.provenance.source_refs, assumption_refs: ['player:method-assumption'] }],
      expressions: [{ id: 'selected-parameter', version: 'v1', constant: '0', terms: [{ variable_id: 'parameter', coefficient: '1' }],
        threshold: threshold || null, operation: 'lt', interpretation: 'Below the explicitly selected threshold' }], factors: form === 'distribution' ? [{ id: 'player:finite-law', version: 'v1', variables: ['parameter'], parents: [], rows: [{ given: {}, outcomes: [
          { values: { parameter: low }, probability: { numerator: pa, denominator: da } },
          { values: { parameter: high }, probability: { numerator: pb, denominator: db } }] }], interpretation: rationale, assumption_refs: ['player:method-assumption'] }] : [],
      assumption_refs: ['player:method-assumption'], assumptions: [{ id: 'player:method-assumption', version: 'v1', rationale }], state_limit: 1000 };
  }
  async function run(action: 'range' | 'variants' | 'bound') {
    setBusy(true); setError(''); setReport(undefined); setVariants(undefined); setBound(undefined);
    try {
      if (action === 'range') setReport(await window.poliscope.uncertainty({ context: state.context, model: model() }));
      else if (action === 'variants') setVariants(await window.poliscope.sensitivity({ context: state.context, model: model(),
        variants: [{ id: 'A', values: [{ variable_id: 'parameter', value: left, selection_ref: 'player:variant-A' }] },
          { id: 'B', values: [{ variable_id: 'parameter', value: right, selection_ref: 'player:variant-B' }] }] }));
      else if (selected?.value.kind === 'quantity') setBound(await window.poliscope.capacity({ context: state.context, method: 'linear-resource-capacity-v1',
        solved_entity_id: solved, solved_unit_id: unit, scope_id: selected.scope_id, time_basis_id: selected.value.time_basis_id,
        lower: '0', upper: ceiling, quantum, iteration_limit: 1024,
        assumptions: [{ id: 'player:method-assumption', version: 'v1', rationale }],
        constraints: [{ id: 'selected-resource', available_value_id: selected.id, fixed_demand: fixed, demand_per_unit: perUnit,
          resource_unit_id: selected.value.unit_id, solved_unit_id: unit, interpretation: rationale,
          source_refs: selected.provenance.source_refs, assumption_refs: ['player:method-assumption'] }] }));
    } catch { setError('The declared calculation is unavailable. Check decimal inputs, bounds, units and variable roles. A fixed or evolving population cannot also be solved. Your saved design has not changed.'); }
    finally { setBusy(false); }
  }
  const locked = disabled || busy;
  return <section aria-label="Uncertainty inspector" className="flex flex-col gap-4">
    <Panel title="Uncertainty and sensitivity" description="Calculations are previews. Declare assumptions explicitly; source ranges have no implied probability."
      action={<StateBadge tone="neutral">Preview only</StateBadge>}
      footer={`Revision ${state.context.revision_id}; day ${state.effective_time.tick}`}>
      {!quantities.length && <EmptyState icon={Sigma} title="No quantity parameters in this scope" description="No quantity parameters are available in this scope. Add a known starting condition or model parameter first." />}
      <fieldset disabled={locked || !selected} className="m-0 min-w-0 border-0 p-0">
        <legend className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Parameter and assumptions</legend>
        <Toolbar>
          <Field label="Parameter" className="min-w-56 flex-1">
            <NativeSelect value={selected?.id ?? ''} onChange={e => { setIdentity(e.target.value); setReport(undefined); setVariants(undefined); setBound(undefined); }}>
              {quantities.map(v => <option key={v.id} value={v.id}>{v.id} ({v.value.kind === 'quantity' ? v.value.unit_id : ''})</option>)}
            </NativeSelect>
          </Field>
          <Field label="Form" className="w-60">
            <NativeSelect value={form} onChange={e => setForm(e.target.value as typeof form)}>
              <option value="bounded_range">Bounded range</option><option value="point">Point value</option><option value="distribution">Explicit finite distribution</option>
            </NativeSelect>
          </Field>
          <Field label={form === 'point' ? 'Point value' : form === 'distribution' ? 'Outcome A value' : 'Lower bound'} className="w-36">
            <Input value={low} onChange={e => setLow(e.target.value)} maxLength={256} />
          </Field>
          {form !== 'point' && <Field label={form === 'distribution' ? 'Outcome B value' : 'Upper bound'} className="w-36">
            <Input value={high} onChange={e => setHigh(e.target.value)} maxLength={256} />
          </Field>}
          <Field label="Threshold: report values below" className="w-44">
            <Input value={threshold} onChange={e => setThreshold(e.target.value)} maxLength={256} />
          </Field>
          <Field label="Method assumption and rationale" className="w-full">
            <Textarea value={rationale} onChange={e => setRationale(e.target.value)} maxLength={4096} placeholder="Player-selected method assumption, with no implied probability." />
          </Field>
        </Toolbar>
        {form === 'distribution' && <div className="mt-3 flex flex-col gap-2 rounded-xl border border-border bg-muted/40 p-3">
          <SubHeading as="h5">Declared probabilities, each an exact fraction</SubHeading>
          <Toolbar>
            <Field label="Outcome A numerator" className="w-40"><Input value={pa} onChange={e => setPa(e.target.value)} maxLength={256} /></Field>
            <Field label="Outcome A denominator" className="w-40"><Input value={da} onChange={e => setDa(e.target.value)} maxLength={256} /></Field>
            <Field label="Outcome B numerator" className="w-40"><Input value={pb} onChange={e => setPb(e.target.value)} maxLength={256} /></Field>
            <Field label="Outcome B denominator" className="w-40"><Input value={db} onChange={e => setDb(e.target.value)} maxLength={256} /></Field>
          </Toolbar>
          <Hint>Declare both probabilities; they must sum exactly to one. This calculation enumerates the law without sampling.</Hint>
        </div>}
        <Actions className="mt-3">
          <Button disabled={!rationale || !low || (form !== 'point' && !high) || (form === 'distribution' && (!pa || !da || !pb || !db))} onClick={() => void run('range')}>Inspect uncertainty</Button>
        </Actions>
        <div className="mt-4 border-t border-border pt-3">
          <SubHeading as="h5">Explicit variants</SubHeading>
          <Hint className="mt-1">Each variant pins the same revision and model. No variant is ranked.</Hint>
          <Toolbar className="mt-2">
            <Field label="Explicit variant A" className="w-40"><Input value={left} onChange={e => setLeft(e.target.value)} maxLength={256} /></Field>
            <Field label="Explicit variant B" className="w-40"><Input value={right} onChange={e => setRight(e.target.value)} maxLength={256} /></Field>
            <Button variant="outline" disabled={!rationale || !left || !right || !low || (form !== 'point' && !high) || (form === 'distribution' && (!pa || !da || !pb || !db))} onClick={() => void run('variants')}>Preview selected variants</Button>
          </Toolbar>
        </div>
      </fieldset>
    </Panel>

    <Disclosure title="Optional resource capacity bound" className="rounded-card border-0 bg-card px-5 py-4 shadow-[var(--shadow-card)]">
      <Hint>This selected model solves one named variable against the selected fixed resource. Its aggregate demand is fixed use plus per-unit use. The result is limited to these declared physical constraints and the selected interval.</Hint>
      <fieldset disabled={locked || !selected} className="m-0 min-w-0 border-0 p-0">
        <legend className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Monotone resource model</legend>
        <Toolbar>
          <Field label="Solved entity ID" className="w-44"><Input value={solved} onChange={e => setSolved(e.target.value)} maxLength={256} /></Field>
          <Field label="Solved unit" className="w-32"><Input value={unit} onChange={e => setUnit(e.target.value)} maxLength={256} /></Field>
          <Field label="Fixed resource use" className="w-36"><Input value={fixed} onChange={e => setFixed(e.target.value)} maxLength={256} /></Field>
          <Field label="Resource use per solved unit" className="w-48"><Input value={perUnit} onChange={e => setPerUnit(e.target.value)} maxLength={256} /></Field>
          <Field label="Search upper boundary" className="w-44"><Input value={ceiling} onChange={e => setCeiling(e.target.value)} maxLength={256} /></Field>
          <Field label="Solved-unit quantum" className="w-40"><Input value={quantum} onChange={e => setQuantum(e.target.value)} maxLength={256} /></Field>
        </Toolbar>
        <Actions className="mt-3"><Button variant="outline" disabled={!rationale || !perUnit || !ceiling || !solved || !unit} onClick={() => void run('bound')}>Calculate capacity bound</Button></Actions>
      </fieldset>
    </Disclosure>

    {busy && <Hint>Calculating declared model…</Hint>}
    {error && <ErrorNote title="The declared calculation is unavailable">{error}</ErrorNote>}
    {report && <Panel label="Uncertainty report" title="Exact uncertainty report"
      description="Declared ranges stay ranges. A threshold changes the reported diagnostic, not the probability of anything.">
      <Hint>Method: {report.method}. Assumptions: {report.query.model.assumptions.map(a => a.rationale).join('; ')}. Sources: {report.sources.join(', ') || 'No source evidence declared'}.</Hint>
      <DataTable className="mt-3">
        <caption>Range and threshold coverage</caption>
        <thead><tr><th scope="col">Expression</th><th scope="col">Range</th><th scope="col">Unit / scope / time</th><th scope="col">Threshold</th><th scope="col">Coverage</th><th scope="col">Probability</th></tr></thead>
        <tbody>{report.observations.map(o => <tr key={o.expression_id}>
          <td>{o.expression_id}</td><td className="tabular-nums">{o.low ?? 'Unavailable'} to {o.high ?? 'Unavailable'}</td><td>{o.unit_id}; {o.scope_id}; {o.time_basis_id ?? 'stock'}</td>
          <td>{report.query.model.expressions.find(e => e.id === o.expression_id)?.threshold ?? 'No threshold'}: {o.diagnostic}</td><td>{o.status}: {o.reason}</td><td>{o.probability ? `${o.probability.numerator}/${o.probability.denominator}` : 'No probability model'}</td></tr>)}</tbody>
      </DataTable>
      <Hint className="mt-2">Report identity: {report.report_digest}</Hint>
    </Panel>}
    {variants && <Panel label="Sensitivity report" title="Explicit variant comparison" description="Each variant uses the same pinned revision and model; no variant is ranked.">
      <Hint>{variants.query.model.assumptions.map(a => a.rationale).join('; ')}.</Hint>
      <div className="mt-3 flex flex-col gap-2">{variants.variants.map(v => <Disclosure key={v.id} title={`Variant ${v.id}: ${v.selected.values.map(x => `${x.variable_id} = ${x.value}`).join(', ')}; coverage ${v.report.coverage}`} open className="bg-muted/40">
        <Hint>Physical result identity: {v.physical_digest}</Hint>
        <ul className="flex flex-col gap-1 text-xs">{v.report.measurements.map(o => <li key={o.indicator_id}>{o.indicator_id}: {o.value.kind === 'quantity' ? `${o.value.value} ${o.value.unit_id}` : o.status}; {o.diagnostic}</li>)}</ul>
        {!v.report.measurements.length && <Hint>No selected measurement definitions; inspect the physical trace below.</Hint>}
        <DataTable>
          <caption>Physical calculation values</caption>
          <thead><tr><th scope="col">Calculation</th><th scope="col">Value</th><th scope="col">Coverage</th></tr></thead>
          <tbody>{v.report.traces.flatMap(t => t.members).slice(0,100).map((m,i) => <tr key={i}><td>{m.node.join(' / ')}</td><td className="tabular-nums">{m.value?.kind === 'quantity' ? `${m.value.value} ${m.value.unit_id}` : 'Unavailable'}</td><td>{m.status}</td></tr>)}</tbody>
        </DataTable>
        <Hint>Showing at most 100 trace members; the report retains complete evidence.</Hint>
      </Disclosure>)}</div>
    </Panel>}
    {bound && <Panel label="Capacity report" title="Resource capacity result" description="The bound is limited to the declared physical constraints and the selected interval.">
      <p className="text-sm">{bound.status}: {bound.reason}. Feasible: {bound.feasible ?? 'Unavailable'}; infeasible: {bound.infeasible ?? 'Not established'} {bound.query.solved_unit_id}.</p>
      <Hint className="mt-1">{bound.query.constraints.map(c => `${c.fixed_demand} fixed + ${c.demand_per_unit} per ${c.solved_unit_id}`).join('; ')}. Sources: {bound.sources.join(', ') || 'No source evidence declared'}</Hint>
      <Hint>Stopping rule: adjacent quantum grid points; quantum {bound.query.quantum}; iterations {bound.iterations}. {bound.query.assumptions.map(a => a.rationale).join('; ')}</Hint>
      <DataTable className="mt-3">
        <caption>Independent feasibility witnesses</caption>
        <thead><tr><th scope="col">Constraint</th><th scope="col">Available</th><th scope="col">Use at feasible</th><th scope="col">Use at infeasible</th></tr></thead>
        <tbody>{bound.witnesses.map(w => <tr key={w.constraint_id}><td>{w.constraint_id}</td><td className="tabular-nums">{w.available.value} {w.available.unit_id}</td><td className="tabular-nums">{w.demand_at_feasible ?? 'Unavailable'}</td><td className="tabular-nums">{w.demand_at_infeasible ?? 'Unavailable'}</td></tr>)}</tbody>
      </DataTable>
    </Panel>}
  </section>;
}
