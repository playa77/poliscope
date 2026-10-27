import { workStatus } from './work-status';
import React, { useState, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { ExplorationQuery, ExplorationEdit, ExplorationPreview, ExplorationRow, ValueEdit, EntityEdit, EntityDTO, RelationshipDTO } from '../../contracts/exploration';
import type { WorkspaceState } from '../../contracts/workspace';
import { Inspector, valueText } from './overview';

const provenance = { origin: 'player_input' as const, source_refs: [], assumption_refs: [] };
const entityKinds: EntityDTO['entity_kind'][] = ['location', 'population_cohort', 'household_arrangement', 'community_arrangement', 'institution', 'asset', 'network', 'resource', 'service', 'account', 'external_interface', 'decision', 'event'];
const relationshipKinds: RelationshipDTO['relationship_kind'][] = ['containment', 'geographic_overlap', 'cohort_membership', 'jurisdiction', 'ownership', 'obligation', 'access', 'connectivity', 'supplies', 'consumes', 'information_channel'];
export function World({ state, scope, onDirty, onSelected, onMatrix, onDecisions, initialIdentity }: {
  state: WorkspaceState; scope: string; onDirty: (dirty: boolean) => void; onSelected: (state: WorkspaceState) => void;
  onMatrix: () => void; onDecisions: () => void; initialIdentity: string | null;
}) {
  const [projection, setProjection] = useState<ExplorationQuery['projection']>('all');
  const [identity, setIdentity] = useState(initialIdentity ?? '');
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const [seed, setSeed] = useState(1);
  const [mode, setMode] = useState<'entity' | 'relationship' | 'value'>('entity');
  const [id, setId] = useState(''); const [label, setLabel] = useState('');
  const [populationRole, setPopulationRole] = useState<EntityEdit['population_role']>(null);
  const [entityKind, setEntityKind] = useState<EntityDTO['entity_kind']>('asset');
  const [kind, setKind] = useState<RelationshipDTO['relationship_kind']>('obligation');
  const [from, setFrom] = useState(''); const [to, setTo] = useState(''); const [version, setVersion] = useState('v1');
  const [aggregation, setAggregation] = useState<'non_aggregating' | 'weight' | 'partition'>('non_aggregating');
  const [terms, setTerms] = useState<string | null>(null);
  const [weight, setWeight] = useState('');
  const [valueRow, setValueRow] = useState<ExplorationRow['value']>(null);
  const [value, setValue] = useState('');
  const [preview, setPreview] = useState<ExplorationPreview>();
  const previewGeneration = useRef(0);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false); const [draft, setDraft] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [inspector, setInspector] = useState<ExplorationRow['inspector']>(null);
  const historical = state.context.revision_id !== state.branch.context.revision_id;
  const query: ExplorationQuery = { context: state.context, scope_id: scope, projection, identity: identity || null, cursor: cursors.at(-1)! };
  const result = useQuery({ queryKey: ['world', state.context, scope, 'exploration', query], retry: false, queryFn: () => window.poliscope.exploration(query) });
  function begin() { setDraft(true); onDirty(true); setPreview(undefined); setError(''); }
  function edit(row: ExplorationRow) {
    begin(); setId(row.id); setTerms(null);
    if (row.entity) { setMode('entity'); setLabel(row.entity.label); setEntityKind(row.entity.entity_kind); setPopulationRole(null); }
    if (row.relationship) { const r = row.relationship; setMode('relationship'); setKind(r.relationship_kind); setFrom(r.from_id); setTo(r.to_id); setVersion(r.relationship_version + ':next'); setAggregation(r.aggregation.kind); setWeight(r.aggregation.kind === 'weight' ? r.aggregation.weight : r.aggregation.kind === 'partition' ? r.aggregation.partition_id : ''); }
    if (row.value) { setMode('value'); setValueRow(row.value); setValue(row.value.value.kind === 'quantity' || row.value.value.kind === 'label' ? row.value.value.value : ''); }
  }
  async function showPreview() {
    const generation = ++previewGeneration.current;
    setBusy(true); setError('');
    try {
      let change: ExplorationEdit['change'];
      if (mode === 'entity') change = { kind: 'entity', population_role: entityKind === 'population_cohort' ? populationRole : null, entity: { id, label, entity_kind: entityKind, provenance } };
      else if (mode === 'relationship') change = { kind: 'relationship', terms, relationship: { id, relationship_version: version, relationship_kind: kind, from_id: from, to_id: to, provenance,
        aggregation: aggregation === 'non_aggregating' ? { kind: aggregation } : aggregation === 'weight' ? { kind: aggregation, weight } : { kind: aggregation, partition_id: weight } } };
      else {
        if (!valueRow || !['quantity', 'label'].includes(valueRow.value.kind)) throw new Error();
        change = { kind: 'value', value_id: valueRow.id, value: { ...valueRow.value, value } as ValueEdit['value'] };
      }
      const result = await window.poliscope.previewWorld({ context: state.context, scope_id: scope, change });
      if (generation === previewGeneration.current) setPreview(result);
    } catch (error) { if (generation === previewGeneration.current) setError(workStatus(error, 'This edit could not be previewed. Check identities, relationship version, membership rule and value ownership. Saved state is unchanged.')); }
    finally { if (generation === previewGeneration.current) setBusy(false); }
  }
  async function apply() {
    if (!preview) return;
    setBusy(true); setError(''); setUncertain(true);
    try { const reply = await window.poliscope.applyWorld({ candidate_digest: preview.candidate_digest }); onDirty(false); onSelected(reply.state); }
    catch { setError('Save unconfirmed. Preview remains unsaved in this view. Retry the same Apply to recover the recorded outcome.'); }
    finally { setBusy(false); }
  }
  const rows = result.data?.items ?? [];
  const edges = rows.flatMap(r => r.relationship ? [r.relationship] : []);
  const nodes = Array.from(new Set([...rows.flatMap(r => r.entity ? [r.entity.id] : r.scope ? [r.scope.id] : []), ...edges.flatMap(r => [r.from_id, r.to_id])])).sort();
  const point = (id: string) => { let hash = seed; for (const c of id) hash = Math.imul(hash ^ c.charCodeAt(0), 16777619); return [50 + (hash >>> 0) % 620, 40 + ((hash >>> 10) % 250)]; };
  return <section className="world-exploration" aria-label="Canonical world and institutions">
    <p>Revision {state.context.revision_id} · Scope {scope} · Tick {state.effective_time.tick}</p>
    <p>One canonical entity can participate in several jurisdictions, households and networks. Geography, membership and authority are separate. Relationships below span the selected civilization; values and accounts show the selected scope unless inspecting a named entity.</p>
    <p>Local surplus does not prove access or deliverability. Connectivity alone does not calculate transport. Inspect exact local accounts and unmet claims before interpreting civilization totals.</p>
    <fieldset disabled={draft || busy}><legend>World projections</legend>
      <label>Projection<select aria-label="Projection" value={projection} onChange={e => { setProjection(e.target.value as ExplorationQuery['projection']); setCursors([null]); }}>{['all', 'geography', 'membership', 'authority', 'networks'].map(p => <option key={p}>{p}</option>)}</select></label>
      <label>Inspect canonical identity<input value={identity} maxLength={128} onChange={e => { setIdentity(e.target.value); setCursors([null]); }} /></label>
      <button onClick={() => { setIdentity(''); setCursors([null]); }}>Show all identities</button>
      <button onClick={onMatrix}>Open world relationships in matrix</button><button onClick={onDecisions}>Open scoped decisions</button>
    </fieldset>
    {result.isFetching && <p role="status">Reading canonical world…</p>}
    {result.isError && <p role="alert">World projection unavailable. <button onClick={() => void result.refetch()}>Retry world projection</button></p>}
    {result.data && <><p role="status">{result.data.total} canonical records · {rows.length} on this page</p>
      {!rows.length && <p>No recorded relationships in this projection. Missing membership or authority remains unresolved.</p>}
      <button disabled={draft} onClick={() => setSeed(s => s + 1)}>Rearrange diagram</button>
      <svg viewBox="0 0 740 340" role="img" aria-label="Topology of the current table page"><title>Current page topology. The table gives every direction and relationship.</title><defs><marker id="world-arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="currentColor" /></marker></defs>
        {edges.map(r => { const a = point(r.from_id), b = point(r.to_id); return <g key={r.id}><line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="currentColor" markerEnd="url(#world-arrow)" /><text x={(a[0]+b[0])/2} y={(a[1]+b[1])/2}>{r.relationship_kind}</text></g>; })}
        {nodes.map(id => { const p = point(id); return <g key={id}><circle cx={p[0]} cy={p[1]} r="5" fill="currentColor" /><text x={p[0]+8} y={p[1]+5}>{id.length > 28 ? id.slice(0,25) + '…' : id}</text><title>{id}</title></g>; })}
      </svg><p>Diagram positions are temporary seeded presentation state. They never enter simulation inputs. Endpoints may be listed on another page; the table records every visible edge.</p>
      <table><caption>Canonical entities, scopes, relationships and local values</caption><thead><tr><th>Identity</th><th>Kind</th><th>Meaning / direction</th><th>Inspect or edit</th></tr></thead><tbody>{rows.map(r => <tr key={JSON.stringify([r.id, r.inspector?.collection, r.entity?.entity_kind, r.relationship?.relationship_kind])}><th>{r.id}</th><td>{r.entity?.entity_kind ?? r.scope?.scope_kind ?? r.relationship?.relationship_kind ?? r.value?.partition ?? 'account'}</td><td>{r.entity?.label ?? r.scope?.label ?? (r.relationship ? `${r.relationship.from_id} → ${r.relationship.to_id} · ${r.relationship.aggregation.kind} · ${r.relationship.relationship_version}` : r.value ? `${r.value.entity_id} · ${r.value.property_id.startsWith('world:relationship:') ? 'Declared relationship terms' : r.value.property_id} · ${r.value.scope_id}: ${valueText(r.value.value)}` : 'Exact retained local account')}</td><td>
        {r.inspector && <button disabled={draft} onClick={() => setInspector(r.inspector)}>Inspect evidence {r.id}</button>}
        {(r.entity || r.relationship) && <button disabled={draft} onClick={() => { setIdentity(r.relationship?.from_id ?? r.id); setCursors([null]); }}>Explore {r.id}</button>}
        {!historical && (r.entity || r.relationship || (r.value?.partition === 'conditions' && ['quantity', 'label'].includes(r.value.value.kind))) && <button disabled={draft} onClick={() => edit(r)}>Edit {r.id}</button>}
      </td></tr>)}</tbody></table>
      <button disabled={draft || cursors.length === 1} onClick={() => setCursors(c => c.slice(0,-1))}>Previous world page</button><button disabled={draft || !result.data.next_cursor} onClick={() => setCursors(c => [...c, result.data!.next_cursor])}>Next world page</button>
    </>}
    {inspector && <Inspector key={JSON.stringify(inspector)} state={state} scope={scope} selection={{ collection: inspector.collection, id: inspector.item_id! }} close={() => setInspector(null)} />}
    {historical ? <p>Historical world is read only. Fork from History and comparison to edit.</p> : <>
      {!draft && <button onClick={() => { setMode('entity'); setEntityKind('asset'); setPopulationRole(null); setId(''); setLabel(''); begin(); }}>Add entity or relationship</button>}
      {draft && <section aria-label="World edit"><h4>Canonical world edit</h4><p>Apply records shared design content in immutable history. Declared obligations do not imply fulfillment.</p>
        <fieldset disabled={busy || uncertain}><legend>Proposed change</legend>
          <label>Edit kind<select aria-label="Edit kind" value={mode} onChange={e => { setMode(e.target.value as typeof mode); setPreview(undefined); }}><option value="entity">entity</option><option value="relationship">relationship</option>{valueRow && <option value="value">value</option>}</select></label>
          {mode !== 'value' && <label>Canonical ID<input maxLength={128} value={id} onChange={e => { setId(e.target.value); setPreview(undefined); }} /></label>}
          {mode === 'entity' && <><label>Entity kind<select aria-label="Entity kind" value={entityKind} onChange={e => { setEntityKind(e.target.value as EntityDTO['entity_kind']); setPreview(undefined); }}>{Array.from(new Set([...entityKinds, entityKind])).map(k => <option key={k}>{k}</option>)}</select></label><label>Entity label<input maxLength={256} value={label} onChange={e => { setLabel(e.target.value); setPreview(undefined); }} /></label></>}
          {mode === 'entity' && entityKind === 'population_cohort' && <label>Population role<select aria-label="Population role" value={populationRole ?? ''} onChange={e => { setPopulationRole(e.target.value as EntityEdit['population_role']); setPreview(undefined); }}><option value="">Keep existing role (required for a new cohort)</option>{['fixed_input', 'dynamic_state', 'solved_capacity_bound'].map(r => <option key={r}>{r}</option>)}</select></label>}
          {mode === 'relationship' && <><label>Relationship kind<select aria-label="Relationship kind" value={kind} onChange={e => { setKind(e.target.value as typeof kind); setPreview(undefined); }}>{Array.from(new Set([...relationshipKinds, kind])).map(k => <option key={k}>{k}</option>)}</select></label>
            <label>From identity<input value={from} maxLength={128} onChange={e => { setFrom(e.target.value); setPreview(undefined); }} /></label><label>To identity<input value={to} maxLength={128} onChange={e => { setTo(e.target.value); setPreview(undefined); }} /></label><label>Relationship version<input value={version} maxLength={128} onChange={e => { setVersion(e.target.value); setPreview(undefined); }} /></label>
            <label>Membership aggregation<select aria-label="Membership aggregation" value={aggregation} onChange={e => { setAggregation(e.target.value as typeof aggregation); setPreview(undefined); }}>{['non_aggregating', 'weight', 'partition'].map(k => <option key={k}>{k}</option>)}</select></label>
            {aggregation !== 'non_aggregating' && <label>Weight or partition ID<input value={weight} onChange={e => { setWeight(e.target.value); setPreview(undefined); }} /></label>}</>}
          {mode === 'relationship' && <label>Declared terms or obligations<textarea maxLength={4096} value={terms ?? ''} placeholder="Leave untouched to retain existing terms" onChange={e => { setTerms(e.target.value); setPreview(undefined); }} /></label>}
          {mode === 'value' && <><p>{valueRow?.property_id} · {valueRow && valueText(valueRow.value)} · Units, scope and denominator are retained.</p><label>Condition value<input value={value} maxLength={1024} onChange={e => { setValue(e.target.value); setPreview(undefined); }} /></label></>}
          <button onClick={() => void showPreview()}>Preview world edit</button>
        </fieldset>
        {preview && <section aria-label="World edit preview"><p>{preview.coverage}</p><h5>Before</h5><pre>{preview.before || 'No previous record'}</pre><h5>After</h5><pre>{preview.after}</pre><button disabled={busy} onClick={() => void apply()}>{uncertain ? 'Retry world Apply' : 'Apply world edit'}</button></section>}
        <button disabled={uncertain} onClick={() => { previewGeneration.current++; void window.poliscope.cancelWorld().then(() => { setBusy(false); setDraft(false); setPreview(undefined); onDirty(false); }); }}>Cancel world edit</button>
      </section>}
    </>}
    {busy && !uncertain && <p role="status">Computing preview. You can cancel this draft while it runs.</p>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
