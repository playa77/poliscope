import React, { useLayoutEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Boxes, ChevronLeft, ChevronRight, Grid3x3 } from 'lucide-react';
import type { MatrixQuery, MatrixRelationship, MatrixModelQuery } from '../../contracts/matrix';
import type { InterviewQuery } from '../../contracts/interview';
import type { WorkspaceState } from '../../contracts/workspace';
import { Source, atlasKey } from './atlas';
import { Inspector, valueText } from './overview';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/app/native-select';
import { Actions, DataTable, Field, Hint, SubHeading, Toolbar } from '@/components/app/form';
import { EmptyState, ErrorNote, Panel } from '@/components/app/blocks';

export type MatrixFilters = Pick<MatrixQuery, 'axis' | 'relationship_type' | 'provenance' | 'row_id' | 'column_id'>;
export const initialMatrixFilters: MatrixFilters = { axis: 'domain', relationship_type: null, provenance: 'any', row_id: null, column_id: null };
export function Model({ state, kind, identity, version }: { state: WorkspaceState; kind: MatrixModelQuery['kind']; identity: string; version?: string | null }) {
  const query = { context: state.context, kind, identity, version: version ?? null };
  const result = useQuery({ queryKey: [...atlasKey(state, '', query), 'matrix-model'], retry: false, queryFn: () => window.poliscope.matrixModel(query) });
  return <section aria-label="Retained mechanism or rule" className="flex flex-col gap-2 rounded-xl border border-border bg-muted/40 p-3"><SubHeading as="h5">{identity}</SubHeading>
    {result.isFetching && <Hint>Reading retained model declaration…</Hint>}
    {result.isError && <ErrorNote title="Model declaration unavailable"><Button variant="outline" size="sm" onClick={() => void result.refetch()}>Retry model declaration</Button></ErrorNote>}
    {result.data?.status === 'unavailable' && <Hint>No retained declaration is available for this reference. Source prose and imported references do not authorize execution.</Hint>}
    {result.data?.status === 'retained' && <><Hint>Data-only declaration from revision {state.context.revision_id}. Registration does not establish scientific validity.</Hint>
      <Hint>Uncertainty and unsupported extrapolation require the recorded evidence and review; executable status alone does not justify them.</Hint>
      <pre className="max-h-72 overflow-auto rounded-lg bg-card p-3 text-xs">{JSON.stringify(result.data.expression_graphs, null, 2)}</pre>
      <pre className="max-h-72 overflow-auto rounded-lg bg-card p-3 text-xs">{JSON.stringify(result.data.mechanism ?? result.data.policy_rule ?? result.data.allocation_rule ?? result.data.condition_rule, null, 2)}</pre></>}
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
  const detailRef = useRef<HTMLElement>(null);
  // Focus the committed details before another keyboard action can reach a child.
  // A delayed frame could otherwise steal focus from that child's Enter key.
  useLayoutEffect(() => { if (relation) detailRef.current?.focus(); }, [relation]);
  const data = result.data;
  function update(change: Partial<MatrixFilters>) { setFilters({ ...filters, ...change }); setOpened(undefined); setInspector(undefined); setSource(''); setModel(undefined); }
  function paging(kind: 'cells' | 'details', next: boolean, token: string | null) {
    setPagination({ ...cursors, [kind]: next ? [...cursors[kind], token] : cursors[kind].slice(0, -1) });
    setOpened(undefined); setInspector(undefined); setSource(''); setModel(undefined);
  }
  return <section aria-label="Sparse relationship matrix" className="flex flex-col gap-4">
    <Panel title="Relationship matrix" description="Row → column is explicit. Requires points from consumer to prerequisite; supplies from producer to recipient. A count is a number of recorded relationships, never effect strength. Blank means no recorded relationship in this model, not independence."
      action={<StateBadgeFor data={data} />}>
      <Hint>Revision {state.context.revision_id} · Scope {scope} · Tick {state.effective_time.tick}. Documentary supersession does not activate causal dependencies or player choices.</Hint>
      <fieldset disabled={disabled} className="m-0 mt-3 min-w-0 border-0 p-0">
        <legend className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Relationship filters</legend>
        <Toolbar>
          <Field label="Matrix grouping" className="w-44">
            <NativeSelect aria-label="Matrix grouping" value={filters.axis} onChange={e => update({ axis: e.target.value as MatrixQuery['axis'], row_id: null, column_id: null })}>
              {['domain', 'branch', 'decision', 'scope', 'selected_alternative'].map(v => <option key={v}>{v}</option>)}
            </NativeSelect>
          </Field>
          <Field label="Relationship type" className="w-44">
            <NativeSelect aria-label="Relationship type" value={filters.relationship_type ?? ''} onChange={e => update({ relationship_type: e.target.value as MatrixQuery['relationship_type'] || null })}>
              <option value="">All relationship types</option>{['requires', 'supplies', 'competes', 'conflicts', 'influences', 'supersedes'].map(v => <option key={v}>{v}</option>)}
            </NativeSelect>
          </Field>
          <Field label="Relationship provenance" className="w-48">
            <NativeSelect aria-label="Relationship provenance" value={filters.provenance} onChange={e => update({ provenance: e.target.value as MatrixQuery['provenance'] })}>
              {['any', 'documentary', 'model', 'retained_execution'].map(v => <option key={v}>{v}</option>)}
            </NativeSelect>
          </Field>
          <Field label="Row identity" className="w-52"><Input maxLength={128} value={filters.row_id ?? ''} onChange={e => update({ row_id: e.target.value || null })} /></Field>
          <Field label="Column identity" className="w-52"><Input maxLength={128} value={filters.column_id ?? ''} onChange={e => update({ column_id: e.target.value || null })} /></Field>
          <Button variant="outline" onClick={() => setFilters(initialMatrixFilters)}>Clear matrix filters</Button>
        </Toolbar>
      </fieldset>
      {result.isFetching && <Hint className="mt-3">Loading relationships…</Hint>}
      {result.isError && <ErrorNote title="Relationships unavailable"><Button variant="outline" size="sm" className="mt-2" onClick={() => void result.refetch()}>Retry matrix</Button></ErrorNote>}
      {data && <>
        <p role="status" className="mt-3 text-xs tabular-nums text-muted-foreground">{data.relationship_total} recorded relationships · {data.cell_total} typed cells · {data.unmapped_count} relationships with unresolved grouping · Evidence {data.evidence_state}</p>
        {data.relationship_total === 0 && <EmptyState icon={Grid3x3} title="No recorded relationships match these filters" description="No recorded relationships match these filters. This does not establish independence." />}
        <DataTable className="mt-3">
          <caption>Sparse matrix · only recorded cells · row → column</caption>
          <thead><tr><th scope="col">Row</th><th scope="col">Column</th><th scope="col">Type</th><th scope="col">Count</th><th scope="col">Provenance</th><th scope="col">Activation</th><th scope="col">Coverage</th><th scope="col">Explore</th></tr></thead>
          <tbody>{data.cells.map((cell, i) => <tr key={i}>
            <th scope="row">{cell.row_id}</th><td>{cell.column_id}</td><td>{cell.relationship_type}</td><td className="tabular-nums">{cell.count}</td><td>{cell.provenance}</td><td>{cell.activation}</td><td>{cell.coverage}</td>
            <td><Button variant="link" size="sm" className="h-auto justify-start p-0 text-left" disabled={disabled} onClick={() => update({ row_id: cell.row_id, column_id: cell.column_id, relationship_type: cell.relationship_type, provenance: cell.provenance })}>Open cell {cell.row_id} → {cell.column_id} {cell.relationship_type}</Button></td>
          </tr>)}</tbody>
        </DataTable>
        <Actions className="mt-3">
          <Button variant="outline" size="sm" disabled={disabled || result.isFetching || cursors.cells.length === 1} onClick={() => paging('cells', false, null)}><ChevronLeft aria-hidden />Previous matrix page</Button>
          <Button variant="outline" size="sm" disabled={disabled || result.isFetching || !data.next_cursor} onClick={() => paging('cells', true, data.next_cursor)}>Next matrix page<ChevronRight aria-hidden /></Button>
        </Actions>
      </>}
    </Panel>

    {data && <Panel title="Accessible relationship list" description="Use the page controls to explore more relationships. Unmapped means no recorded grouping; it is not a domain or a model claim.">
      <ol className="flex flex-col divide-y divide-border">{data.relationships.map(r => <li key={r.id} className="flex flex-wrap items-baseline gap-x-2 gap-y-1 py-2">
        <Button variant="link" className="h-auto justify-start p-0 text-left text-[0.8125rem]" disabled={disabled} onClick={() => { setOpened({ identity, relation: r }); setSource(''); setInspector(undefined); setModel(undefined); }}>{r.row.label} → {r.column.label} · {r.relationship_type}</Button>
        <span className="text-[11px] text-muted-foreground"> · {r.provenance} · {r.coverage}</span>
      </li>)}</ol>
      <Actions className="mt-3">
        <Button variant="outline" size="sm" disabled={disabled || result.isFetching || cursors.details.length === 1} onClick={() => paging('details', false, null)}><ChevronLeft aria-hidden />Previous relationship page</Button>
        <Button variant="outline" size="sm" disabled={disabled || result.isFetching || !data.detail_next_cursor} onClick={() => paging('details', true, data.detail_next_cursor)}>Next relationship page<ChevronRight aria-hidden /></Button>
      </Actions>
    </Panel>}

    {relation && <section ref={detailRef} aria-label="Relationship details" id="matrix-detail" tabIndex={-1}
      className="flex min-w-0 flex-col gap-3 rounded-card bg-card p-5 shadow-[var(--shadow-card)]">
      <div className="flex items-start gap-2">
        <Boxes aria-hidden className="mt-0.5 size-4 shrink-0 text-primary" />
        <SubHeading as="h4">{relation.relationship_type}: {relation.row.id} → {relation.column.id}</SubHeading>
      </div>
      <p className="text-sm leading-relaxed">{relation.explanation}</p>
      <Hint>Provenance {relation.provenance} · Activation {relation.activation} · Coverage {relation.coverage}</Hint>
      <Hint>Numerical relationship magnitude: {relation.magnitude ? valueText(relation.magnitude) : 'Not recorded; inspect exact node values separately.'}</Hint>
      <Hint>Mechanisms: {relation.mechanism_refs.join(', ') || 'None recorded'} · Rules: {relation.rule_refs.join(', ') || 'None recorded'}</Hint>
      <Actions>
        {relation.mechanism_refs.map(id => <Button key={'m' + id} variant="outline" size="sm" disabled={disabled} onClick={() => setModel({ kind: 'mechanism', identity: id })}>Inspect mechanism {id}</Button>)}
        {relation.rule_refs.map(id => <Button key={'r' + id} variant="outline" size="sm" disabled={disabled} onClick={() => setModel({ kind: 'rule', identity: id })}>Inspect rule {id}</Button>)}
        {(relation.world_refs ?? []).map(id => <Button key={'w' + id} variant="outline" size="sm" disabled={disabled} onClick={() => onWorld(id)}>Inspect canonical world {id}</Button>)}
        {relation.interviews.map(q => <Button key={JSON.stringify(q)} variant="outline" size="sm" disabled={disabled} onClick={() => onInterview(q)}>Open participating choice {q.question_id}</Button>)}
        {relation.sources.map(q => <Button key={q.source_ref} variant="outline" size="sm" disabled={disabled} onClick={() => setSource(q.source_ref)}>Inspect relationship source {q.source_ref}</Button>)}
        {relation.inspectors.map(q => <Button key={JSON.stringify(q)} variant="outline" size="sm" disabled={disabled} onClick={() => setInspector({ collection: q.collection, id: q.item_id! })}>Inspect {q.collection} {q.item_id}</Button>)}
      </Actions>
      {!relation.interviews.length && <Hint>No explicit choice binding recorded.</Hint>}
      {!relation.sources.length && <Hint>No bundled source link recorded; retained public references remain available in evidence inspectors.</Hint>}
      {model && <Model key={JSON.stringify(model)} state={state} {...model} />}
      {source && <Source key={JSON.stringify([state.context, source])} state={state} identity={source} />}
      {inspector && <Inspector key={JSON.stringify(inspector)} state={state} scope={scope} selection={inspector} close={() => setInspector(undefined)} />}
    </section>}
  </section>;
}
/** The matrix has one header badge: total relationships and retained evidence state. */
function StateBadgeFor({ data }: { data?: { relationship_total: number; evidence_state: string } }) {
  if (!data) return undefined;
  return <span className="rounded-full bg-muted px-2.5 py-1 text-[11px] tabular-nums text-muted-foreground">{data.relationship_total} · {data.evidence_state}</span>;
}
