import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { MatrixQuery, MatrixRelationship, MatrixModelQuery } from '../../contracts/matrix';
import type { InterviewQuery } from '../../contracts/interview';
import type { WorkspaceState } from '../../contracts/workspace';
import { Source, atlasKey } from './atlas';
import { Inspector, valueText } from './overview';

export type MatrixFilters = Pick<MatrixQuery, 'axis' | 'relationship_type' | 'provenance' | 'row_id' | 'column_id'>;
export const initialMatrixFilters: MatrixFilters = { axis: 'domain', relationship_type: null, provenance: 'any', row_id: null, column_id: null };
function Model({ state, kind, identity }: { state: WorkspaceState; kind: MatrixModelQuery['kind']; identity: string }) {
  const query = { context: state.context, kind, identity };
  const result = useQuery({ queryKey: [...atlasKey(state, '', query), 'matrix-model'], retry: false, queryFn: () => window.poliscope.matrixModel(query) });
  return <section aria-label="Retained mechanism or rule"><h5>{identity}</h5>
    {result.isFetching && <p role="status">Reading retained model declaration…</p>}
    {result.isError && <p role="alert">Model declaration unavailable. <button onClick={() => void result.refetch()}>Retry model declaration</button></p>}
    {result.data?.status === 'unavailable' && <p>No retained declaration is available for this reference. Source prose and imported references do not authorize execution.</p>}
    {result.data?.status === 'retained' && <><p>Data-only declaration from revision {state.context.revision_id}. Registration does not establish scientific validity.</p>
      <pre>{JSON.stringify(result.data.mechanism ?? result.data.policy_rule ?? result.data.allocation_rule ?? result.data.condition_rule, null, 2)}</pre></>}
  </section>;
}
export function Matrix({ state, scope, disabled, filters, setFilters, onInterview, onWorld }: {
  state: WorkspaceState; scope: string; disabled: boolean; filters: MatrixFilters;
  onWorld: (identity: string) => void; setFilters: (filters: MatrixFilters) => void; onInterview: (query: InterviewQuery) => void;
}) {
  const identity = JSON.stringify([state.context, state.versions, state.effective_time, scope, filters]);
  const [pagination, setPagination] = useState<{ identity: string; cells: (string | null)[]; details: (string | null)[] }>({ identity: '', cells: [null], details: [null] });
  const cursors = pagination.identity === identity ? pagination : { identity, cells: [null], details: [null] };
  const query: MatrixQuery = { context: state.context, scope_id: scope, ...filters, cursor: cursors.cells.at(-1)!, detail_cursor: cursors.details.at(-1)! };
  const result = useQuery({ queryKey: [...atlasKey(state, scope, query), 'matrix'], enabled: Boolean(scope), retry: false, queryFn: () => window.poliscope.matrix(query) });
  const [opened, setOpened] = useState<{ identity: string; relation: MatrixRelationship }>();
  const [source, setSource] = useState('');
  const [model, setModel] = useState<{ kind: MatrixModelQuery['kind']; identity: string }>();
  const [inspector, setInspector] = useState<{ collection: MatrixRelationship['inspectors'][number]['collection']; id: string }>();
  const relation = opened?.identity === identity ? opened.relation : undefined;
  const data = result.data;
  function update(change: Partial<MatrixFilters>) { setFilters({ ...filters, ...change }); setOpened(undefined); setInspector(undefined); setSource(''); setModel(undefined); }
  function paging(kind: 'cells' | 'details', next: boolean, token: string | null) {
    setPagination({ ...cursors, [kind]: next ? [...cursors[kind], token] : cursors[kind].slice(0, -1) });
    setOpened(undefined); setInspector(undefined); setSource(''); setModel(undefined);
  }
  return <section aria-label="Sparse relationship matrix">
    <p>Row → column is explicit. Requires points from consumer to prerequisite; supplies from producer to recipient. A count is a number of recorded relationships, never effect strength. Blank means no recorded relationship in this model, not independence.</p>
    <p>Revision {state.context.revision_id} · Scope {scope} · Tick {state.effective_time.tick}. Documentary supersession does not activate causal dependencies or player choices.</p>
    <fieldset disabled={disabled}><legend>Relationship filters</legend>
      <label>Matrix grouping<select aria-label="Matrix grouping" value={filters.axis} onChange={e => update({ axis: e.target.value as MatrixQuery['axis'], row_id: null, column_id: null })}>{['domain', 'branch', 'decision', 'scope', 'selected_alternative'].map(v => <option key={v}>{v}</option>)}</select></label>
      <label>Relationship type<select aria-label="Relationship type" value={filters.relationship_type ?? ''} onChange={e => update({ relationship_type: e.target.value as MatrixQuery['relationship_type'] || null })}><option value="">All relationship types</option>{['requires', 'supplies', 'competes', 'conflicts', 'influences', 'supersedes'].map(v => <option key={v}>{v}</option>)}</select></label>
      <label>Relationship provenance<select aria-label="Relationship provenance" value={filters.provenance} onChange={e => update({ provenance: e.target.value as MatrixQuery['provenance'] })}>{['any', 'documentary', 'model', 'retained_execution'].map(v => <option key={v}>{v}</option>)}</select></label>
      <label>Row identity<input maxLength={128} value={filters.row_id ?? ''} onChange={e => update({ row_id: e.target.value || null })} /></label>
      <label>Column identity<input maxLength={128} value={filters.column_id ?? ''} onChange={e => update({ column_id: e.target.value || null })} /></label>
      <button onClick={() => setFilters(initialMatrixFilters)}>Clear matrix filters</button>
    </fieldset>
    {result.isFetching && <p role="status">Loading relationships…</p>}
    {result.isError && <p role="alert">Relationships unavailable. <button onClick={() => void result.refetch()}>Retry matrix</button></p>}
    {data && <><p role="status">{data.relationship_total} recorded relationships · {data.cell_total} typed cells · {data.unmapped_count} relationships with unresolved grouping · Evidence {data.evidence_state}</p>
      {data.relationship_total === 0 && <p>No recorded relationships match these filters. This does not establish independence.</p>}
      <table><caption>Sparse matrix · only recorded cells · row → column</caption><thead><tr><th>Row</th><th>Column</th><th>Type</th><th>Count</th><th>Provenance</th><th>Activation</th><th>Coverage</th><th>Explore</th></tr></thead>
        <tbody>{data.cells.map((cell, i) => <tr key={i}><th>{cell.row_id}</th><td>{cell.column_id}</td><td>{cell.relationship_type}</td><td>{cell.count}</td><td>{cell.provenance}</td><td>{cell.activation}</td><td>{cell.coverage}</td><td><button disabled={disabled} onClick={() => update({ row_id: cell.row_id, column_id: cell.column_id, relationship_type: cell.relationship_type, provenance: cell.provenance })}>Open cell {cell.row_id} → {cell.column_id} {cell.relationship_type}</button></td></tr>)}</tbody></table>
      <button disabled={disabled || result.isFetching || cursors.cells.length === 1} onClick={() => paging('cells', false, null)}>Previous matrix page</button>
      <button disabled={disabled || result.isFetching || !data.next_cursor} onClick={() => paging('cells', true, data.next_cursor)}>Next matrix page</button>
      <h4>Accessible relationship list</h4><p>Use the page controls to explore more relationships. Unmapped means no recorded grouping; it is not a domain or a model claim.</p>
      <ol>{data.relationships.map(r => <li key={r.id}><button disabled={disabled} onClick={() => { setOpened({ identity, relation: r }); setSource(''); setInspector(undefined); setModel(undefined); requestAnimationFrame(() => document.getElementById('matrix-detail')?.focus()); }}>{r.row.label} → {r.column.label} · {r.relationship_type}</button><span> · {r.provenance} · {r.coverage}</span></li>)}</ol>
      <button disabled={disabled || result.isFetching || cursors.details.length === 1} onClick={() => paging('details', false, null)}>Previous relationship page</button>
      <button disabled={disabled || result.isFetching || !data.detail_next_cursor} onClick={() => paging('details', true, data.detail_next_cursor)}>Next relationship page</button>
    </>}
    {relation && <section aria-label="Relationship details" id="matrix-detail" tabIndex={-1}><h4>{relation.relationship_type}: {relation.row.id} → {relation.column.id}</h4>
      <p>{relation.explanation}</p><p>Provenance {relation.provenance} · Activation {relation.activation} · Coverage {relation.coverage}</p>
      <p>Numerical relationship magnitude: {relation.magnitude ? valueText(relation.magnitude) : 'Not recorded; inspect exact node values separately.'}</p>
      <p>Mechanisms: {relation.mechanism_refs.join(', ') || 'None recorded'} · Rules: {relation.rule_refs.join(', ') || 'None recorded'}</p>
      {relation.mechanism_refs.map(id => <button key={'m' + id} disabled={disabled} onClick={() => setModel({ kind: 'mechanism', identity: id })}>Inspect mechanism {id}</button>)}
      {relation.rule_refs.map(id => <button key={'r' + id} disabled={disabled} onClick={() => setModel({ kind: 'rule', identity: id })}>Inspect rule {id}</button>)}
      {model && <Model key={JSON.stringify(model)} state={state} {...model} />}
      {(relation.world_refs ?? []).map(id => <button key={'w' + id} disabled={disabled} onClick={() => onWorld(id)}>Inspect canonical world {id}</button>)}
      {relation.interviews.map(q => <button key={JSON.stringify(q)} disabled={disabled} onClick={() => onInterview(q)}>Open participating choice {q.question_id}</button>)}
      {!relation.interviews.length && <p>No explicit choice binding recorded.</p>}
      {relation.sources.map(q => <button key={q.source_ref} disabled={disabled} onClick={() => setSource(q.source_ref)}>Inspect relationship source {q.source_ref}</button>)}
      {!relation.sources.length && <p>No bundled source link recorded; retained public references remain available in evidence inspectors.</p>}
      {relation.inspectors.map(q => <button key={JSON.stringify(q)} disabled={disabled} onClick={() => setInspector({ collection: q.collection, id: q.item_id! })}>Inspect {q.collection} {q.item_id}</button>)}
      {source && <Source key={JSON.stringify([state.context, source])} state={state} identity={source} />}
      {inspector && <Inspector key={JSON.stringify(inspector)} state={state} scope={scope} selection={inspector} close={() => setInspector(undefined)} />}
    </section>}
  </section>;
}
