import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight, Compass, Search } from 'lucide-react';
import type { AtlasQuery, AtlasEntry } from '../../contracts/atlas';
import type { InterviewQuery } from '../../contracts/interview';
import type { WorkspaceState } from '../../contracts/workspace';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/app/native-select';
import { Actions, DataTable, Disclosure, Field, Hint, SubHeading, Toolbar } from '@/components/app/form';
import { EmptyState, ErrorNote, Panel, StateBadge } from '@/components/app/blocks';

export type AtlasFilters = Omit<AtlasQuery, 'context' | 'scope_id' | 'cursor'>;
export const initialAtlasFilters: AtlasFilters = { search: '', domain_ref: null, branch_ref: null, source_ref: null, selection: 'any', modeling: null, evidence: null, issues: 'any' };
export function atlasKey(state: WorkspaceState, scope: string, query: unknown) {
  return ['world', 'atlas', state.context, state.versions, state.effective_time, scope, query];
}
export function Source({ state, identity }: { state: WorkspaceState; identity: string }) {
  const [offset, setOffset] = useState(0);
  const query = { context: state.context, source_ref: identity, offset };
  const result = useQuery({ queryKey: atlasKey(state, '', query), retry: false, queryFn: () => window.poliscope.atlasSource(query) });
  return <section aria-label="Archived source" className="flex flex-col gap-2 rounded-xl border border-border bg-muted/40 p-3">
    {result.isPending && <Hint>Loading archived source…</Hint>}
    {result.isError && <ErrorNote title="Archived source unavailable"><Button variant="outline" size="sm" onClick={() => void result.refetch()}>Retry source</Button></ErrorNote>}
    {result.data && <>
      <Hint>{result.data.source.reference.repository_id} · {result.data.source.reference.document_id} · Revision {result.data.source.commit}</Hint>
      <pre className="max-h-96 overflow-auto rounded-lg bg-card p-3 text-xs leading-relaxed">{result.data.text}</pre>
      <Actions>
        <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 12000))}><ChevronLeft aria-hidden />Previous source page</Button>
        <Button variant="outline" size="sm" disabled={result.data.next_offset === null} onClick={() => setOffset(result.data!.next_offset!)}>Next source page<ChevronRight aria-hidden /></Button>
      </Actions>
      <Disclosure title="Attribution and license" className="bg-card"><pre className="max-h-72 overflow-auto rounded-lg bg-muted p-3 text-xs leading-relaxed">{result.data.license_text}</pre></Disclosure>
    </>}</section>;
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
  return <section aria-label="Decision discovery" className="flex flex-col gap-4">
    <Panel title="Decision discovery" description="Explore questions and every alternative. A source's historical adoption does not answer your question. Source-maintenance records are excluded.">
      <fieldset disabled={disabled} className="m-0 min-w-0 border-0 p-0">
        <legend className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Atlas filters</legend>
        <Toolbar>
          <Field label="Search full questions and alternatives" className="min-w-56 flex-1">
            <div className="relative flex min-w-0 items-center">
              <Search aria-hidden className="pointer-events-none absolute left-2.5 size-3.5 text-muted-foreground" />
              <Input type="search" maxLength={256} className="pl-8" value={filters.search} onChange={e => update({ search: e.target.value })} />
            </div>
          </Field>
          <Field label="Atlas domain" className="w-40">
            <NativeSelect value={filters.domain_ref ?? ''} onChange={e => update({ domain_ref: e.target.value || null })}><option value="">All domains</option>{data?.domains.map(d => <option key={d.id} value={d.id}>{d.label}</option>)}</NativeSelect>
          </Field>
          <Field label="Atlas branch" className="w-40">
            <NativeSelect value={filters.branch_ref ?? ''} onChange={e => update({ branch_ref: e.target.value || null })}><option value="">All branches</option>{data?.branches.map(d => <option key={d.id} value={d.id}>{d.label}</option>)}</NativeSelect>
          </Field>
          <Field label="Atlas source" className="w-40">
            <NativeSelect value={filters.source_ref ?? ''} onChange={e => update({ source_ref: e.target.value || null })}><option value="">All sources</option>{data?.sources.map(d => <option key={d.id} value={d.id}>{d.label}</option>)}</NativeSelect>
          </Field>
          <Field label="Player selection" className="w-40">
            <NativeSelect value={filters.selection} onChange={e => update({ selection: e.target.value as AtlasFilters['selection'] })}>{['any', 'selected', 'unanswered', 'proposed'].map(s => <option key={s}>{s}</option>)}</NativeSelect>
          </Field>
          <Field label="Modeling coverage" className="w-36">
            <NativeSelect value={filters.modeling ?? ''} onChange={e => update({ modeling: (e.target.value || null) as AtlasFilters['modeling'] })}><option value="">All modeling</option>{['numerical', 'procedural', 'qualitative', 'partial', 'unsupported'].map(s => <option key={s}>{s}</option>)}</NativeSelect>
          </Field>
          <Field label="Evidence coverage" className="w-36">
            <NativeSelect value={filters.evidence ?? ''} onChange={e => update({ evidence: (e.target.value || null) as AtlasFilters['evidence'] })}><option value="">All evidence</option>{['unreviewed', 'hypothetical', 'supported', 'disputed'].map(s => <option key={s}>{s}</option>)}</NativeSelect>
          </Field>
          <Field label="Open issues" className="w-32">
            <NativeSelect value={filters.issues} onChange={e => update({ issues: e.target.value as AtlasFilters['issues'] })}>{['any', 'open', 'none'].map(s => <option key={s}>{s}</option>)}</NativeSelect>
          </Field>
          <Button variant="outline" onClick={() => setFilters(initialAtlasFilters)}>Clear atlas filters</Button>
        </Toolbar>
      </fieldset>
      {result.isFetching && <Hint className="mt-3">Loading atlas…</Hint>}
      {result.isError && <ErrorNote title="Atlas unavailable"><Button variant="outline" size="sm" className="mt-2" onClick={() => void result.refetch()}>Retry atlas</Button></ErrorNote>}
      {data && <>
        <p role="status" className="mt-3 text-xs tabular-nums text-muted-foreground">{data.total} matching questions · {data.items.length} on this page · Scope {scope}</p>
        {data.total === 0 && <EmptyState icon={Compass} title="No matching questions" description="No matching questions. Change or clear the filters." />}
        {(data.items.length ?? 0) > 0 && <ul className="mt-3 flex flex-col gap-2">{data.items.map(item => <li key={item.question.id} className="rounded-xl bg-muted/40 p-3">
          <Button variant="link" className="h-auto justify-start p-0 text-left text-[0.8125rem] font-medium" disabled={disabled} onClick={() => { setOpened({ identity, row: item }); setSource(''); }}>{item.question.source_decision_id ?? item.question.id} · {item.question.original_text.split('\n')[0]}</Button>
          <p className="mt-1 text-[11px] text-muted-foreground">{item.selected_id ? 'Player selection recorded' : 'Unanswered by player'} · {item.options.length} alternatives · {item.question.modeling} · {item.question.evidence}</p>
        </li>)}</ul>}
        <Actions className="mt-3">
          <Button variant="outline" size="sm" disabled={disabled || result.isFetching || cursors.length === 1} onClick={() => { setPagination({ identity, cursors: cursors.slice(0, -1) }); setOpened(undefined); }}><ChevronLeft aria-hidden />Previous atlas page</Button>
          <Button variant="outline" size="sm" disabled={disabled || result.isFetching || !data.next_cursor} onClick={() => { setPagination({ identity, cursors: [...cursors, data.next_cursor] }); setOpened(undefined); }}>Next atlas page<ChevronRight aria-hidden /></Button>
        </Actions>
      </>}
    </Panel>

    {row && <section aria-label="Atlas question" className="flex min-w-0 flex-col gap-3 rounded-card bg-card p-5 shadow-[var(--shadow-card)]">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <SubHeading as="h4">{row.question.id}</SubHeading>
        <StateBadge tone="info">{row.question.modeling}</StateBadge>
      </div>
      <Hint>Scope {scope} · Revision {state.context.revision_id} · {row.archive === 'retained' ? 'Retained original alternatives' : 'Current catalog reference'}</Hint>
      <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-xl bg-muted/60 p-3 text-xs leading-relaxed">{row.question.original_text}</pre>
      <Hint>Origin {row.question.origin} · Modeling {row.question.modeling} · Evidence {row.question.evidence}</Hint>
      <Hint>Supersedes: {row.question.supersedes_refs.join(', ') || 'None recorded'}</Hint>
      <p className="text-sm">Player&apos;s choice: {row.selected_id ?? 'Unanswered'}. Source adoption appears separately on each option.</p>
      <ol className="flex flex-col gap-2">{row.options.map(option => <li key={option.id} className="rounded-xl border border-border p-3">
        <strong className="text-sm">{option.id}{row.selected_id === option.id ? ' · Player selected' : ''}</strong>
        <pre className="mt-2 whitespace-pre-wrap rounded-lg bg-muted/60 p-3 text-xs leading-relaxed">{option.original_text}</pre>
        <p className="mt-2 text-[11px] text-muted-foreground">Source historical status: {option.historical_status} · Origin: {option.origin} · Modeling: {option.modeling} · Evidence: {option.evidence}</p>
        <p className="mt-1 text-[11px] text-muted-foreground">Supersedes: {option.supersedes_refs.join(', ') || 'None recorded'}</p>
      </li>)}</ol>
      <Disclosure title="Model gaps and open issues" open>
        <ul className="flex flex-col gap-1 text-xs leading-relaxed">{row.issues.map(issue => <li key={issue} className="rounded-lg bg-card px-2 py-1">{issue}</li>)}</ul>
        <Hint>Branches: {row.branch_refs.join(', ') || 'No branch mapping recorded'}</Hint>
      </Disclosure>
      <Actions>
        {[...new Set([row.question, ...row.options].flatMap(d => d.source_refs))].map(id => <Button key={id} variant="outline" size="sm" disabled={disabled} onClick={() => setSource(id)}>Inspect source {id}</Button>)}
        {row.interview && <Button disabled={disabled} onClick={() => onInterview(row.interview!)}>Open interview and preview</Button>}
        <Button variant="outline" disabled={disabled} onClick={onHistory}>Open history for this state</Button>
      </Actions>
      {source && <Source key={JSON.stringify([state.context, source])} state={state} identity={source} />}
    </section>}
  </section>;
}
