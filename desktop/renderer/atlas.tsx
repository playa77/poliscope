import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { AtlasQuery, AtlasEntry } from '../../contracts/atlas';
import type { InterviewQuery } from '../../contracts/interview';
import type { WorkspaceState } from '../../contracts/workspace';

export type AtlasFilters = Omit<AtlasQuery, 'context' | 'scope_id' | 'cursor'>;
export const initialAtlasFilters: AtlasFilters = { search: '', domain_ref: null, branch_ref: null, source_ref: null, selection: 'any', modeling: null, evidence: null, issues: 'any' };
export function atlasKey(state: WorkspaceState, scope: string, query: unknown) {
  return ['world', 'atlas', state.context, state.versions, state.effective_time, scope, query];
}
export function Source({ state, identity }: { state: WorkspaceState; identity: string }) {
  const [offset, setOffset] = useState(0);
  const query = { context: state.context, source_ref: identity, offset };
  const result = useQuery({ queryKey: atlasKey(state, '', query), retry: false, queryFn: () => window.poliscope.atlasSource(query) });
  return <section aria-label="Archived source">
    {result.isPending && <p role="status">Loading archived source…</p>}
    {result.isError && <p role="alert">Archived source unavailable. <button onClick={() => void result.refetch()}>Retry source</button></p>}
    {result.data && <><p>{result.data.source.reference.repository_id} · {result.data.source.reference.document_id} · Revision {result.data.source.commit}</p>
      <pre>{result.data.text}</pre><button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 12000))}>Previous source page</button>
      <button disabled={result.data.next_offset === null} onClick={() => setOffset(result.data!.next_offset!)}>Next source page</button>
      <details><summary>Attribution and license</summary><pre>{result.data.license_text}</pre></details></>}
  </section>;
}
export function Atlas({ state, scope, active, disabled, filters, setFilters, onInterview, onHistory }: {
  state: WorkspaceState; scope: string; active: boolean; disabled: boolean;
  filters: AtlasFilters; setFilters: (filters: AtlasFilters) => void;
  onInterview: (query: InterviewQuery) => void; onHistory: () => void;
}) {
  const identity = JSON.stringify([state.context, state.versions, state.effective_time, scope, filters]);
  const [pagination, setPagination] = useState<{ identity: string; cursors: (string | null)[] }>({ identity: '', cursors: [null] });
  const cursors = pagination.identity === identity ? pagination.cursors : [null];
  const query: AtlasQuery = { context: state.context, scope_id: scope, ...filters, cursor: cursors.at(-1)! };
  const result = useQuery({ queryKey: atlasKey(state, scope, query), enabled: active && Boolean(scope), retry: false, queryFn: () => window.poliscope.atlas(query) });
  const [opened, setOpened] = useState<{ identity: string; row: AtlasEntry }>();
  const [source, setSource] = useState('');
  function update(change: Partial<AtlasFilters>) { setFilters({ ...filters, ...change }); setOpened(undefined); }
  const row = opened?.identity === identity ? opened.row : undefined;
  const data = result.data;
  return <section className="atlas" aria-label="Decision discovery">
    <p>Explore questions and every alternative. A source's historical adoption does not answer your question. Source-maintenance records are excluded.</p>
    <fieldset disabled={disabled}><legend>Atlas filters</legend>
      <label>Search full questions and alternatives<input type="search" maxLength={256} value={filters.search} onChange={e => update({ search: e.target.value })} /></label>
      <label>Atlas domain<select value={filters.domain_ref ?? ''} onChange={e => update({ domain_ref: e.target.value || null })}><option value="">All domains</option>{data?.domains.map(d => <option key={d.id} value={d.id}>{d.label}</option>)}</select></label>
      <label>Atlas branch<select value={filters.branch_ref ?? ''} onChange={e => update({ branch_ref: e.target.value || null })}><option value="">All branches</option>{data?.branches.map(d => <option key={d.id} value={d.id}>{d.label}</option>)}</select></label>
      <label>Atlas source<select value={filters.source_ref ?? ''} onChange={e => update({ source_ref: e.target.value || null })}><option value="">All sources</option>{data?.sources.map(d => <option key={d.id} value={d.id}>{d.label}</option>)}</select></label>
      <label>Player selection<select value={filters.selection} onChange={e => update({ selection: e.target.value as AtlasFilters['selection'] })}>{['any', 'selected', 'unanswered', 'proposed'].map(s => <option key={s}>{s}</option>)}</select></label>
      <label>Modeling coverage<select value={filters.modeling ?? ''} onChange={e => update({ modeling: (e.target.value || null) as AtlasFilters['modeling'] })}><option value="">All modeling</option>{['numerical', 'procedural', 'qualitative', 'partial', 'unsupported'].map(s => <option key={s}>{s}</option>)}</select></label>
      <label>Evidence coverage<select value={filters.evidence ?? ''} onChange={e => update({ evidence: (e.target.value || null) as AtlasFilters['evidence'] })}><option value="">All evidence</option>{['unreviewed', 'hypothetical', 'supported', 'disputed'].map(s => <option key={s}>{s}</option>)}</select></label>
      <label>Open issues<select value={filters.issues} onChange={e => update({ issues: e.target.value as AtlasFilters['issues'] })}>{['any', 'open', 'none'].map(s => <option key={s}>{s}</option>)}</select></label>
      <button onClick={() => setFilters(initialAtlasFilters)}>Clear atlas filters</button>
    </fieldset>
    {result.isFetching && <p role="status">Loading atlas…</p>}
    {result.isError && <p role="alert">Atlas unavailable. <button onClick={() => void result.refetch()}>Retry atlas</button></p>}
    {data && <><p role="status">{data.total} matching questions · {data.items.length} on this page · Scope {scope}</p>
      {data.total === 0 && <p>No matching questions. Change or clear the filters.</p>}
      <ul>{data.items.map(item => <li key={item.question.id}><button disabled={disabled} onClick={() => { setOpened({ identity, row: item }); setSource(''); }}>{item.question.source_decision_id ?? item.question.id} · {item.question.original_text.split('\n')[0]}</button>
        <p>{item.selected_id ? 'Player selection recorded' : 'Unanswered by player'} · {item.options.length} alternatives · {item.question.modeling} · {item.question.evidence}</p></li>)}</ul>
      <button disabled={disabled || result.isFetching || cursors.length === 1} onClick={() => { setPagination({ identity, cursors: cursors.slice(0, -1) }); setOpened(undefined); }}>Previous atlas page</button>
      <button disabled={disabled || result.isFetching || !data.next_cursor} onClick={() => { setPagination({ identity, cursors: [...cursors, data.next_cursor] }); setOpened(undefined); }}>Next atlas page</button></>}
    {row && <section aria-label="Atlas question"><h4>{row.question.id}</h4><p>Scope {scope} · Revision {state.context.revision_id} · {row.archive === 'retained' ? 'Retained original alternatives' : 'Current catalog reference'}</p>
      <pre>{row.question.original_text}</pre><p>Origin {row.question.origin} · Modeling {row.question.modeling} · Evidence {row.question.evidence}</p>
      <p>Supersedes: {row.question.supersedes_refs.join(', ') || 'None recorded'}</p>
      <p>Player's choice: {row.selected_id ?? 'Unanswered'}. Source adoption appears separately on each option.</p>
      <ol>{row.options.map(option => <li key={option.id}><strong>{option.id}{row.selected_id === option.id ? ' · Player selected' : ''}</strong><pre>{option.original_text}</pre>
        <p>Source historical status: {option.historical_status} · Origin: {option.origin} · Modeling: {option.modeling} · Evidence: {option.evidence}</p>
        <p>Supersedes: {option.supersedes_refs.join(', ') || 'None recorded'}</p></li>)}</ol>
      <details open><summary>Model gaps and open issues</summary><ul>{row.issues.map(issue => <li key={issue}>{issue}</li>)}</ul><p>Branches: {row.branch_refs.join(', ') || 'No branch mapping recorded'}</p></details>
      {[...new Set([row.question, ...row.options].flatMap(d => d.source_refs))].map(id => <button key={id} disabled={disabled} onClick={() => setSource(id)}>Inspect source {id}</button>)}
      {source && <Source key={JSON.stringify([state.context, source])} state={state} identity={source} />}
      {row.interview && <button disabled={disabled} onClick={() => onInterview(row.interview!)}>Open interview and preview</button>}
      <button disabled={disabled} onClick={onHistory}>Open history for this state</button>
    </section>}
  </section>;
}
