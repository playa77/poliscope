import { Archives } from './archives';
import { Uncertainty } from './uncertainty';
import { Timeline } from './timeline';
import { Evidence, type EvidenceCollection } from './evidence';
import { World } from './world';
import { Matrix, initialMatrixFilters, type MatrixFilters } from './matrix';
import { Atlas, initialAtlasFilters, type AtlasFilters } from './atlas';
import { DesignHistory } from './design-history';
import { Overview, Inspector } from './overview';
import { Interview } from './interview';
import React, { useLayoutEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Building2, ChevronRight, FolderOpen, Layers, PanelRightClose, PanelRightOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { NativeSelect } from '@/components/app/native-select';
import { EmptyState, ErrorNote, KeyValue, LoadingRows, Panel } from '@/components/app/blocks';
import { Field } from '@/components/app/form';
import type { CreateOptions, WorkspaceCatalogue, WorkspaceState, ScopeDTO, WorkspacePage, WorkspacePageRequest } from '../../contracts/workspace';

export function contextKey(state: WorkspaceState, scope: string, view: string) {
  const c = state.context, v = state.versions;
  return ['world', c.data_store_id, c.civilization_id, c.branch_id, c.revision_id,
    scope, v.world_schema, v.catalog_id, v.model_id, v.numeric_runtime_id,
    state.effective_time.calendar_id, state.effective_time.tick, view];
}

/** Sequential page loading honors the one-child controller and cancellation. */
async function pages(state: WorkspaceState, scope: string, collection: WorkspacePageRequest['collection'], signal: AbortSignal) {
  const items: WorkspacePage['result']['page']['items'] = [];
  let cursor: string | null = null;
  const seen = new Set<string>();
  do {
    signal.throwIfAborted();
    const page = await window.poliscope.worldPage({ context: state.context, scope_id: scope, collection, cursor });
    signal.throwIfAborted();
    items.push(...page.result.page.items as never[]);
    cursor = page.result.page.next_cursor;
    if (cursor && seen.has(cursor)) throw new Error('Repeated page');
    if (cursor) seen.add(cursor);
    if (items.length > 1000) throw new Error('Collection exceeds limit');
  } while (cursor);
  return items;
}

export const VIEWS = ['Civilization overview', 'Society map', 'Decision atlas', 'Dependency matrix',
  'World and institutions', 'Uncertainty and sensitivity', 'Timeline and experiments', 'History and comparison', 'Evidence and models', 'Assistant and provider settings'];

export function Workspace({ view, onView, onDraftChange, onProviders, onAskAssistant }: {
  view: string;
  onView: (view: string) => void;
  onDraftChange?: (dirty: boolean) => void;
  onProviders?: () => void;
  onAskAssistant?: (text: string) => void;
}) {
  const client = useQueryClient();
  const [dirty, setDirty] = useState(false);
  const [notice, setNotice] = useState('');
  const draftChanged = React.useCallback((value: boolean) => { setDirty(value); onDraftChange?.(value); }, [onDraftChange]);
  const [catalogue, setCatalogue] = useState<WorkspaceCatalogue>();
  const [state, setState] = useState<WorkspaceState>();
  const [scope, setScope] = useState('');
  const [domain, setDomain] = useState('');
  const [interviewFocus, setInterviewFocus] = useState(0);
  const [atlasFilters, setAtlasFilters] = useState<AtlasFilters>(initialAtlasFilters);
  const [evidenceCollection, setEvidenceCollection] = useState<EvidenceCollection>('results');
  const [worldIdentity, setWorldIdentity] = useState<string | null>(null);
  const [matrixFilters, setMatrixFilters] = useState<MatrixFilters>(initialMatrixFilters);
  const [questionId, setQuestionId] = useState<string | null>(null);
  const [inspector, setInspector] = useState(false);
  const [conditionInspector, setConditionInspector] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [options, setOptions] = useState<CreateOptions>({ name: '', setup: 'blank', scope_name: 'Home', population: null, land_area: null });
  const generation = useRef(0);
  const viewHeading = useRef<HTMLHeadingElement>(null);
  const previousView = useRef(view);
  const selectedState = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    // A replaced Apply control must not leave keyboard focus on the document body.
    if (state && document.activeElement === document.body) selectedState.current?.focus();
  }, [state]);
  useLayoutEffect(() => {
    if (previousView.current !== view) viewHeading.current?.focus();
    previousView.current = view;
  }, [view]);
  useLayoutEffect(() => {
    // Complete focus with this selection's commit; a later animation frame can
    // steal the next keyboard activation after another control has focus.
    if (interviewFocus) document.getElementById('selected-interview')?.focus();
  }, [interviewFocus]);
  function openInterview(domainId: string, question: string | null = null) {
    setDomain(domainId); setQuestionId(question); setInterviewFocus(n => n + 1);
  }
  const scopes = useQuery({ queryKey: state ? contextKey(state, 'all', 'scope-directory') : ['no-world-scopes'],
    enabled: Boolean(state), retry: false,
    queryFn: ({ signal }) => pages(state!, 'all', 'scopes', signal) as Promise<ScopeDTO[]> });
  const selectedScope = scopes.data?.some(s => s.id === scope) ? scope : scopes.data?.[0]?.id || '';
  const values = useQuery({ queryKey: state ? contextKey(state, selectedScope, view) : ['no-world-values'],
    enabled: Boolean(state && selectedScope && !scopes.isFetching), retry: false,
    queryFn: ({ signal }) => pages(state!, selectedScope, 'values', signal) });
  const loading = busy || dirty || scopes.isFetching || values.isFetching;
  async function act(work: () => Promise<void>) {
    const id = ++generation.current;
    setBusy(true); setError('');
    await client.cancelQueries({ queryKey: ['world'] });
    try { await work(); } catch { if (id === generation.current) setError('The request could not complete. Your saved history is retained. Retry the same request or reopen the folder to inspect confirmed worlds.'); }
    finally { if (id === generation.current) setBusy(false); }
  }
  function selectState(next: WorkspaceState) {
    setState(next); setScope(''); setConditionInspector(undefined);
  }
  const selectedScopeLabel = scopes.data?.find(s => s.id === selectedScope)?.label;
  return <div className="flex flex-col gap-5">
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">Local sandbox</p>
        <h2 id="sandbox-heading" tabIndex={-1} className="text-xl font-semibold tracking-tight">Design a society. Begin anywhere.</h2>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">A local folder holds your civilizations and retained history. Civic choices and goals start unanswered.</p>
      </div>
      <Button disabled={loading} onClick={() => void act(async () => {
        const next = await window.poliscope.chooseWorkspace();
        if (next) { setCatalogue(next); setState(undefined); setScope(''); client.removeQueries({ queryKey: ['world'] }); }
      })}>
        <FolderOpen aria-hidden data-icon="inline-start" />
        Choose sandbox folder
      </Button>
    </header>

    {!catalogue && (
      <div className="rounded-card bg-card px-6 py-8 shadow-[var(--shadow-card)]">
        <EmptyState icon={FolderOpen} title="No sandbox is open"
          description="A sandbox is an ordinary local folder. Poliscope never uploads it, and reading it does not start a simulation. Use “Choose sandbox folder” above to open one." />
      </div>
    )}

    {error && <ErrorNote>{error}</ErrorNote>}
    {notice && <p role="status" className="text-sm text-muted-foreground">{notice}</p>}
    {dirty && <p role="status" className="rounded-xl bg-warning/10 px-4 py-3 text-sm text-warning-foreground">Unsaved revision draft: Apply, cancel or defer before changing the selected state.</p>}

    {catalogue && <>
      <details className="inquiry-guide rounded-card bg-card px-5 py-4 shadow-[var(--shadow-card)]">
        <summary className="text-sm font-medium">Explore a question without AI</summary>
        <p className="mt-2 text-sm text-muted-foreground">Begin in any domain. There is no required order or overall society score.</p>
        <ol className="mt-2 flex list-decimal flex-col gap-2 pl-5 text-sm leading-relaxed text-foreground/90">
          <li>Predict a consequence and name the people and place it concerns.</li>
          <li>Choose a draft and preview it. A preview is unsaved and conditional on its declared model. Apply records a design choice, not proof; qualitative commitments have no calculated effects without a mechanism.</li>
          <li>In Civilization overview, inspect a shortage or unmet requirement. Read local and group outcomes as well as aggregates: a total can conceal exclusion.</li>
          <li>Open its evidence inspector to find inputs, assumptions, sources and coverage. Unknown means unavailable, not zero. A player target expresses your preference, not an engine judgment.</li>
          <li>Use History and comparison to fork an alternative and compare the same scope and time. Use Timeline and experiments for confirmed simulation states.</li>
          <li>Export a report and explain what changed, whose outcomes differ and which consequences remain unsupported. You can revise your prediction without choosing a winner.</li>
        </ol>
        <p className="mt-2 text-xs text-muted-foreground">Read the selected branch, revision, scope, model and tick above each result. A design revision, noncommitting preview and confirmed simulation state describe different evidence.</p>
      </details>

      <Panel title="Start here" description="Create a civilization, open a saved branch, or browse portable archives.">
        <div className="grid gap-5 xl:grid-cols-2">
          <section aria-labelledby="create-heading" className="min-w-0">
            <h3 id="create-heading" className="mb-2 flex items-center gap-2 text-sm font-semibold"><Building2 aria-hidden className="size-4 text-primary" /> Create a civilization</h3>
            <form className="flex flex-col gap-3" onSubmit={event => { event.preventDefault(); void act(async () => {
              const next = await window.poliscope.createWorld(options);
              selectState(next); setCatalogue(await window.poliscope.workspaceCatalogue());
            }); }}>
              <fieldset disabled={loading} className="m-0 flex min-w-0 flex-col gap-3 border-0 p-0">
                <legend className="sr-only">Named, editable starting conditions</legend>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="civ-name">Civilization name</Label>
                    <Input id="civ-name" required maxLength={256} value={options.name} onChange={e => setOptions({ ...options, name: e.target.value })} />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="civ-setup">Starting setup</Label>
                    <NativeSelect id="civ-setup" className="w-full" value={options.setup} onChange={e => {
                      const setup = catalogue.setups.find(s => s.id === e.target.value)!;
                      setOptions({ ...options, setup: setup.id, population: setup.population, land_area: setup.land_area });
                    }}>
                      {catalogue.setups.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                    </NativeSelect>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="civ-scope">Settlement name</Label>
                    <Input id="civ-scope" required maxLength={256} value={options.scope_name} onChange={e => setOptions({ ...options, scope_name: e.target.value })} />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="civ-population">Starting population (people, optional)</Label>
                    <Input id="civ-population" inputMode="numeric" maxLength={256} value={options.population ?? ''} onChange={e => setOptions({ ...options, population: e.target.value || null })} />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="civ-land">Starting land area (km², optional)</Label>
                    <Input id="civ-land" inputMode="decimal" maxLength={256} value={options.land_area ?? ''} onChange={e => setOptions({ ...options, land_area: e.target.value || null })} />
                  </div>
                </div>
                {options.setup !== 'blank' && <p className="text-xs text-muted-foreground">Explicit reference selection: synthetic conditions, editable above. No civic arrangements or goals are selected.</p>}
                <Field label="Purpose (optional, stays in this session)">
                  <Textarea maxLength={4096} placeholder="What would you like to explore?" />
                </Field>
                <p className="text-xs text-muted-foreground">Blank quantities remain unknown. Purpose does not create a target or policy.</p>
                <div><Button type="submit" disabled={loading}>Create sandbox</Button></div>
              </fieldset>
            </form>
          </section>

          <section aria-labelledby="open-heading" className="flex min-w-0 flex-col gap-3">
            <h3 id="open-heading" className="text-sm font-semibold">Open a saved branch</h3>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="open-branch">Open civilization and branch</Label>
              <NativeSelect id="open-branch" className="w-full" disabled={loading} value={state ? `${state.context.civilization_id}/${state.context.branch_id}` : ''} onChange={e => {
                const branch = catalogue.branches.find(b => `${b.context.civilization_id}/${b.context.branch_id}` === e.target.value);
                if (branch) void act(async () => selectState(await window.poliscope.selectWorld({ civilization_id: branch.context.civilization_id, branch_id: branch.context.branch_id, revision_id: null })));
              }}>
                <option value="" disabled>Select a saved branch</option>
                {catalogue.branches.map(b => <option key={`${b.context.civilization_id}/${b.context.branch_id}`} value={`${b.context.civilization_id}/${b.context.branch_id}`}>{b.name} · {b.context.branch_id}</option>)}
              </NativeSelect>
            </div>
            <div>
              <Button variant="outline" disabled={loading} onClick={() => onView('Portable archives')}>
                <Layers aria-hidden data-icon="inline-start" />
                Portable archives
              </Button>
            </div>
            {view === 'Portable archives' && <Archives key={catalogue.data_store_id} />}
          </section>
        </div>
      </Panel>

      {state && <>
        <div className="flex flex-col gap-4 rounded-card bg-card px-5 py-4 shadow-[var(--shadow-card)]" aria-label="Selected state" role="region" ref={selectedState} tabIndex={-1}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">Selected state</p>
              <p className="truncate text-sm font-semibold">{state.branch.name}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-muted px-2.5 py-1 text-[11px] text-muted-foreground">
                {state.context.revision_id === state.branch.context.revision_id ? 'Confirmed design revision' : 'Historical revision — read only'}
              </span>
              <span className="rounded-full bg-muted px-2.5 py-1 text-[11px] text-muted-foreground tabular-nums">Tick {state.effective_time.tick}</span>
            </div>
          </div>
          <p className="text-xs tabular-nums text-muted-foreground">{state.goal_count} declared goals · {state.policy_count} selected policies · {state.mechanism_count} registered mechanisms</p>
          <KeyValue items={[
            { label: 'Branch', value: state.context.branch_id },
            { label: 'Revision', value: state.context.revision_id },
            { label: 'Model', value: state.versions.model_id },
            { label: 'Calendar', value: state.effective_time.calendar_id },
            { label: 'Scope identity', value: selectedScopeLabel ? `${selectedScopeLabel} (${scopes.data?.find(s => s.id === selectedScope)?.scope_kind})` : 'Loading scope' },
          ]} />
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="scope-select">Scope</Label>
              <NativeSelect id="scope-select" aria-label="Scope" className="w-full" value={selectedScope} disabled={loading || !scopes.data?.length} onChange={e => {
                void client.cancelQueries({ queryKey: ['world'] }); setScope(e.target.value); setConditionInspector(undefined);
              }}>
                {scopes.data?.map(s => <option key={s.id} value={s.id}>{s.label} ({s.scope_kind})</option>)}
              </NativeSelect>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="revision-read">Read a retained revision (leave blank for current branch head)</Label>
              <Input key={`${state.context.civilization_id}/${state.context.branch_id}`} id="revision-read" name="revision-id" maxLength={128} placeholder="Press Enter to open the revision" onKeyDown={e => {
                if (e.key === 'Enter' && !loading) { e.preventDefault(); const revision = e.currentTarget.value;
                  void act(async () => selectState(await window.poliscope.selectWorld({ civilization_id: state.context.civilization_id, branch_id: state.context.branch_id, revision_id: revision || null })));
                }
              }} />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">Saved revisions remain attached to their original state.</p>
        </div>

        <div className="workspace-layout grid min-w-0 grid-cols-[minmax(0,1fr)] gap-5 xl:grid-cols-[minmax(0,1fr)_18rem]">
          <article className="flex min-w-0 flex-col gap-4 rounded-card bg-card px-5 py-4 shadow-[var(--shadow-card)]" aria-labelledby="workspace-view-heading">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 id="workspace-view-heading" ref={viewHeading} tabIndex={-1} className="text-base font-semibold tracking-tight">{view}</h3>
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" aria-expanded={inspector} onClick={() => setInspector(!inspector)}>
                  {inspector ? <PanelRightClose aria-hidden data-icon="inline-start" /> : <PanelRightOpen aria-hidden data-icon="inline-start" />}
                  State inspector
                </Button>
              </div>
            </div>
            <p className="text-xs text-muted-foreground">{state.mechanism_count === 0 ? 'This starting model has no numerical social mechanisms. Qualitative commitments have no calculated social effects; observations below are authored conditions.' : 'This saved model contains mechanism bindings. Synthetic qualitative interviews are available; execution requires the matching registered model.'}</p>
            {view === 'Evidence and models' && selectedScope && <Evidence collection={evidenceCollection} setCollection={setEvidenceCollection} key={JSON.stringify([state.context, selectedScope])} state={state} scope={selectedScope} onDirty={draftChanged} onSelected={next => { setState(next); void client.invalidateQueries({ queryKey: ['world'] }); }} onCompare={() => onView('History and comparison')} />}
            {view === 'Civilization overview' && selectedScope && <Overview key={JSON.stringify([state.context, selectedScope, state.versions])} state={state} scope={selectedScope} />}
            {view === 'History and comparison' && <DesignHistory key={JSON.stringify(state.context)} state={state} disabled={loading} onSelected={async next => { selectState(next); setCatalogue(await window.poliscope.workspaceCatalogue()); await client.invalidateQueries({ queryKey: ['world'] }); }} />}
            {selectedScope && <div hidden={view !== 'Decision atlas'}><Atlas state={state} scope={selectedScope} active={view === 'Decision atlas'} disabled={dirty} filters={atlasFilters} setFilters={setAtlasFilters}
              onInterview={query => { openInterview(query.domain_id, query.question_id ?? null); }} onHistory={() => onView('History and comparison')} /></div>}
            {view === 'World and institutions' && selectedScope && <World key={JSON.stringify([state.context, selectedScope, worldIdentity])} state={state} scope={selectedScope} initialIdentity={worldIdentity} onDirty={draftChanged} onSelected={next => { setState(next); setWorldIdentity(null); void client.invalidateQueries({ queryKey: ['world'] }); }} onMatrix={() => { setMatrixFilters({ ...initialMatrixFilters, axis: 'scope' }); onView('Dependency matrix'); }} onDecisions={() => onView('Decision atlas')} />}
            {view === 'Dependency matrix' && selectedScope && <Matrix onWorld={identity => { setWorldIdentity(identity); onView('World and institutions'); }} state={state} scope={selectedScope} disabled={dirty} filters={matrixFilters} setFilters={setMatrixFilters}
              onInterview={query => { openInterview(query.domain_id, query.question_id ?? null); }} />}

            <section aria-labelledby="domains-heading" className="mt-1">
              <h4 id="domains-heading" className="mb-2 text-sm font-semibold">Enter a domain</h4>
              <div className="domain-grid grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                {catalogue.domains.map(d => (
                  <button key={d.id} type="button" disabled={dirty} aria-pressed={domain === d.id} onClick={() => { openInterview(d.id); }}
                    className="group flex min-w-0 items-center justify-between gap-2 rounded-xl bg-muted/70 px-3 py-2.5 text-left text-sm transition-colors hover:bg-accent aria-pressed:bg-primary aria-pressed:text-primary-foreground">
                    <span className="min-w-0">
                      <span className="block font-medium break-words">{d.name}</span>
                      <small className="block text-[11px] font-normal leading-relaxed text-muted-foreground group-aria-pressed:text-primary-foreground/80">Synthetic interview · social mechanisms not supplied</small>
                    </span>
                    <ChevronRight aria-hidden className="size-4 shrink-0 opacity-60" />
                  </button>
                ))}
              </div>
            </section>

            {domain && <section aria-label="Selected domain" id="selected-interview" tabIndex={-1} className="mt-2 rounded-xl border border-border p-4">
              <h4 className="text-sm font-semibold">{catalogue.domains.find(d => d.id === domain)?.name ?? 'Source question · domain mapping unresolved'}</h4>
              <p className="mt-1 text-xs text-muted-foreground">Open for exploration. Select a draft, inspect it, then preview before Apply.</p>
              {selectedScope && <Interview key={JSON.stringify([state.context, selectedScope, domain, questionId])}
                query={{ context: state.context, scope_id: selectedScope, domain_id: domain, question_id: questionId }} versions={state.versions}
                historical={state.context.revision_id !== state.branch.context.revision_id} onDirty={draftChanged} onAskAssistant={onAskAssistant}
                onConfirmed={(next, message) => { draftChanged(false); setNotice(message); setState(next); void client.invalidateQueries({ queryKey: ['world'] }); }} />}</section>}

            {view === 'Uncertainty and sensitivity' && <Uncertainty key={JSON.stringify([state.context, selectedScope])} state={state} values={(values.data ?? []).filter(v => 'partition' in v)} disabled={loading} />}
            {view === 'Timeline and experiments' && <Timeline key={JSON.stringify(state.context)} state={state} disabled={loading} />}
            {view !== 'Portable archives' && view !== 'Uncertainty and sensitivity' && view !== 'Timeline and experiments' && view !== 'Evidence and models' && view !== 'Civilization overview' && view !== 'World and institutions' && view !== 'Society map' && view !== 'History and comparison' && view !== 'Decision atlas' && view !== 'Dependency matrix' && <p className="text-sm text-muted-foreground">The {view.toLowerCase()} tools are not yet available. You can continue exploring every domain and the selected state.</p>}

            <section aria-labelledby="conditions-heading" className="mt-1">
              <h4 id="conditions-heading" className="mb-2 text-sm font-semibold">Starting conditions · {selectedScopeLabel ?? 'Loading scope'}</h4>
              {(scopes.isError || values.isError) && <ErrorNote title="This state could not be read">Reopen the branch to retry.</ErrorNote>}
              {values.isFetching ? <LoadingRows label="Loading this state" /> : (
                <div className="overflow-x-auto rounded-xl border border-border">
                  <table className="w-full text-sm">
                    <caption className="sr-only">Authored conditions for the selected revision and scope</caption>
                    <thead><tr className="bg-muted/60 text-left text-[11px] uppercase tracking-wide text-muted-foreground"><th scope="col" className="px-3 py-2">Condition</th><th scope="col" className="px-3 py-2">Value</th><th scope="col" className="px-3 py-2">Meaning</th></tr></thead>
                    <tbody>{values.data?.filter(v => 'value' in v && v.partition === 'conditions').map(v => 'value' in v && <tr key={v.id} className="border-t border-border"><th scope="row" className="px-3 py-2 text-left font-medium">{v.property_id}</th><td className="px-3 py-2"><button type="button" title="Inspect authored condition" className="rounded-md px-2 py-1 text-left text-primary underline-offset-4 hover:underline" onClick={() => setConditionInspector(v.id)}>{v.value.kind === 'unknown' ? 'Unknown' : v.value.kind === 'quantity' ? `${v.value.value} ${v.value.unit_id}` : v.value.kind === 'label' ? v.value.value : v.value.entity_id}</button></td><td className="px-3 py-2 text-muted-foreground">{v.value.kind === 'unknown' ? v.value.reason : 'Player-supplied starting condition'}</td></tr>)}
                      {!values.isFetching && values.data?.filter(v => 'value' in v && v.partition === 'conditions').length === 0 && <tr><td colSpan={3} className="px-3 py-4 text-muted-foreground">No authored conditions are recorded for this scope. Unknown stays unknown; nothing is substituted.</td></tr>}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
            {conditionInspector && <Inspector key={JSON.stringify([state.context, selectedScope, conditionInspector])} state={state} scope={selectedScope} selection={{ collection: 'conditions', id: conditionInspector }} close={() => setConditionInspector(undefined)} />}
          </article>

          {inspector && <aside aria-label="State inspector" className="rounded-card bg-card px-5 py-4 shadow-[var(--shadow-card)]">
            <h3 className="text-sm font-semibold">State identity</h3>
            <dl className="mt-2 flex flex-col gap-2">{Object.entries({ ...state.context, ...state.versions, scope_id: selectedScope }).map(([key, value]) => <div key={key}><dt className="text-[11px] uppercase tracking-wide text-muted-foreground">{key.replaceAll('_', ' ')}</dt><dd className="break-words text-xs">{value}</dd></div>)}</dl>
            <p className="mt-3 text-xs text-muted-foreground">All views read the same Python-owned world. Temporary navigation and filters stay in this session.</p>
          </aside>}
        </div>
      </>}
    </>}
  </div>;
}
