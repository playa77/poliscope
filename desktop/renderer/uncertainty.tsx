import React, { useState } from 'react';
import type { WorkspaceState, PartitionValueDTO } from '../../contracts/workspace';
import type { UncertaintyModel, UncertaintyReport, SensitivityReport, CapacityReport } from '../../contracts/uncertainty';

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
  return <section aria-label="Uncertainty inspector">
    <h3>Uncertainty and sensitivity</h3>
    <p>Revision {state.context.revision_id}; day {state.effective_time.tick}. Calculations are previews. Declare assumptions explicitly; source ranges have no implied probability.</p>
    {!quantities.length && <p>No quantity parameters are available in this scope. Add a known starting condition or model parameter first.</p>}
    <fieldset disabled={locked || !selected}><legend>Parameter and assumptions</legend>
      <label>Parameter<select value={selected?.id ?? ''} onChange={e => { setIdentity(e.target.value); setReport(undefined); setVariants(undefined); setBound(undefined); }}>
        {quantities.map(v => <option key={v.id} value={v.id}>{v.id} ({v.value.kind === 'quantity' ? v.value.unit_id : ''})</option>)}</select></label>
      <label>Form<select value={form} onChange={e => setForm(e.target.value as typeof form)}><option value="bounded_range">Bounded range</option><option value="point">Point value</option><option value="distribution">Explicit finite distribution</option></select></label>
      <label>{form === 'point' ? 'Point value' : form === 'distribution' ? 'Outcome A value' : 'Lower bound'}<input value={low} onChange={e => setLow(e.target.value)} maxLength={256} /></label>
      {form !== 'point' && <label>{form === 'distribution' ? 'Outcome B value' : 'Upper bound'}<input value={high} onChange={e => setHigh(e.target.value)} maxLength={256} /></label>}
      {form === 'distribution' && <fieldset><legend>Declared probabilities, each an exact fraction</legend>
        <label>Outcome A numerator<input value={pa} onChange={e => setPa(e.target.value)} maxLength={256} /></label>
        <label>Outcome A denominator<input value={da} onChange={e => setDa(e.target.value)} maxLength={256} /></label>
        <label>Outcome B numerator<input value={pb} onChange={e => setPb(e.target.value)} maxLength={256} /></label>
        <label>Outcome B denominator<input value={db} onChange={e => setDb(e.target.value)} maxLength={256} /></label>
        <p>Declare both probabilities; they must sum exactly to one. This calculation enumerates the law without sampling.</p>
      </fieldset>}
      <label>Threshold: report values below<input value={threshold} onChange={e => setThreshold(e.target.value)} maxLength={256} /></label>
      <label>Method assumption and rationale<textarea value={rationale} onChange={e => setRationale(e.target.value)} maxLength={4096} /></label>
      <button disabled={!rationale || !low || (form !== 'point' && !high) || (form === 'distribution' && (!pa || !da || !pb || !db))} onClick={() => void run('range')}>Inspect uncertainty</button>
      <label>Explicit variant A<input value={left} onChange={e => setLeft(e.target.value)} maxLength={256} /></label>
      <label>Explicit variant B<input value={right} onChange={e => setRight(e.target.value)} maxLength={256} /></label>
      <button disabled={!rationale || !left || !right || !low || (form !== 'point' && !high) || (form === 'distribution' && (!pa || !da || !pb || !db))} onClick={() => void run('variants')}>Preview selected variants</button>
    </fieldset>
    <details><summary>Optional resource capacity bound</summary>
      <p>This selected model solves one named variable against the selected fixed resource. Its aggregate demand is fixed use plus per-unit use. The result is limited to these declared physical constraints and the selected interval.</p>
      <fieldset disabled={locked || !selected}><legend>Monotone resource model</legend>
        <label>Solved entity ID<input value={solved} onChange={e => setSolved(e.target.value)} maxLength={256} /></label>
        <label>Solved unit<input value={unit} onChange={e => setUnit(e.target.value)} maxLength={256} /></label>
        <label>Fixed resource use<input value={fixed} onChange={e => setFixed(e.target.value)} maxLength={256} /></label>
        <label>Resource use per solved unit<input value={perUnit} onChange={e => setPerUnit(e.target.value)} maxLength={256} /></label>
        <label>Search upper boundary<input value={ceiling} onChange={e => setCeiling(e.target.value)} maxLength={256} /></label>
        <label>Solved-unit quantum<input value={quantum} onChange={e => setQuantum(e.target.value)} maxLength={256} /></label>
        <button disabled={!rationale || !perUnit || !ceiling || !solved || !unit} onClick={() => void run('bound')}>Calculate capacity bound</button>
      </fieldset>
    </details>
    {busy && <p role="status">Calculating declared model…</p>}{error && <p role="alert">{error}</p>}
    {report && <div role="region" aria-label="Uncertainty report"><h4>Exact uncertainty report</h4>
      <p>Method: {report.method}. Assumptions: {report.query.model.assumptions.map(a => a.rationale).join('; ')}. Sources: {report.sources.join(', ') || 'No source evidence declared'}.</p>
      <table><caption>Range and threshold coverage</caption><thead><tr><th>Expression</th><th>Range</th><th>Unit / scope / time</th><th>Threshold</th><th>Coverage</th><th>Probability</th></tr></thead><tbody>{report.observations.map(o => <tr key={o.expression_id}>
        <td>{o.expression_id}</td><td>{o.low ?? 'Unavailable'} to {o.high ?? 'Unavailable'}</td><td>{o.unit_id}; {o.scope_id}; {o.time_basis_id ?? 'stock'}</td>
        <td>{report.query.model.expressions.find(e => e.id === o.expression_id)?.threshold ?? 'No threshold'}: {o.diagnostic}</td><td>{o.status}: {o.reason}</td><td>{o.probability ? `${o.probability.numerator}/${o.probability.denominator}` : 'No probability model'}</td></tr>)}</tbody></table>
      <p>Report identity: {report.report_digest}</p></div>}
    {variants && <div role="region" aria-label="Sensitivity report"><h4>Explicit variant comparison</h4>
      <p>{variants.query.model.assumptions.map(a => a.rationale).join('; ')}. Each variant uses the same pinned revision and model; no variant is ranked.</p>
      {variants.variants.map(v => <details key={v.id} open><summary>Variant {v.id}: {v.selected.values.map(x => `${x.variable_id} = ${x.value}`).join(', ')}; coverage {v.report.coverage}</summary>
        <p>Physical result identity: {v.physical_digest}</p>
        <ul>{v.report.measurements.map(o => <li key={o.indicator_id}>{o.indicator_id}: {o.value.kind === 'quantity' ? `${o.value.value} ${o.value.unit_id}` : o.status}; {o.diagnostic}</li>)}</ul>
        {!v.report.measurements.length && <p>No selected measurement definitions; inspect the physical trace below.</p>}
        <table><caption>Physical calculation values</caption><thead><tr><th>Calculation</th><th>Value</th><th>Coverage</th></tr></thead><tbody>{v.report.traces.flatMap(t => t.members).slice(0,100).map((m,i) => <tr key={i}><td>{m.node.join(' / ')}</td><td>{m.value?.kind === 'quantity' ? `${m.value.value} ${m.value.unit_id}` : 'Unavailable'}</td><td>{m.status}</td></tr>)}</tbody></table>
        <p>Showing at most 100 trace members; the report retains complete evidence.</p></details>)}</div>}
    {bound && <div role="region" aria-label="Capacity report"><h4>Resource capacity result</h4><p>{bound.status}: {bound.reason}. Feasible: {bound.feasible ?? 'Unavailable'}; infeasible: {bound.infeasible ?? 'Not established'} {bound.query.solved_unit_id}.</p>
      <p>{bound.query.constraints.map(c => `${c.fixed_demand} fixed + ${c.demand_per_unit} per ${c.solved_unit_id}`).join('; ')}. Sources: {bound.sources.join(', ') || 'No source evidence declared'}</p><p>Stopping rule: adjacent quantum grid points; quantum {bound.query.quantum}; iterations {bound.iterations}. {bound.query.assumptions.map(a => a.rationale).join('; ')}</p>
      <table><caption>Independent feasibility witnesses</caption><thead><tr><th>Constraint</th><th>Available</th><th>Use at feasible</th><th>Use at infeasible</th></tr></thead><tbody>{bound.witnesses.map(w => <tr key={w.constraint_id}><td>{w.constraint_id}</td><td>{w.available.value} {w.available.unit_id}</td><td>{w.demand_at_feasible ?? 'Unavailable'}</td><td>{w.demand_at_infeasible ?? 'Unavailable'}</td></tr>)}</tbody></table></div>}
  </section>;
}
