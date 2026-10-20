import { Atlas, initialAtlasFilters, type AtlasFilters } from './atlas';
import { DesignHistory } from './design-history';
import { Overview, Inspector } from './overview';
import { Interview } from './interview';
import React, { useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
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
const VIEWS = ['Civilization overview', 'Society map', 'Decision atlas', 'Dependency matrix',
  'World and institutions', 'Timeline and experiments', 'History and comparison', 'Evidence and models', 'Assistant and provider settings'];

export function Workspace({ onDraftChange }: { onDraftChange?: (dirty: boolean) => void }) {
  const client = useQueryClient();
  const [dirty, setDirty] = useState(false);
  const [notice, setNotice] = useState('');
  const draftChanged = React.useCallback((value: boolean) => { setDirty(value); onDraftChange?.(value); }, [onDraftChange]);
  const [catalogue, setCatalogue] = useState<WorkspaceCatalogue>();
  const [state, setState] = useState<WorkspaceState>();
  const [scope, setScope] = useState('');
  const [view, setView] = useState(VIEWS[0]);
  const [domain, setDomain] = useState('');
  const [atlasFilters, setAtlasFilters] = useState<AtlasFilters>(initialAtlasFilters);
  const [questionId, setQuestionId] = useState<string | null>(null);
  const [inspector, setInspector] = useState(false);
  const [conditionInspector, setConditionInspector] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [options, setOptions] = useState<CreateOptions>({ name: '', setup: 'blank', scope_name: 'Home', population: null, land_area: null });
  const generation = useRef(0);
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
  return <section className="sandbox" aria-labelledby="sandbox-heading">
    <header className="workspace-header"><div><p className="eyebrow">Local sandbox</p><h2 id="sandbox-heading">Design a society. Begin anywhere.</h2></div>
      <button disabled={loading} onClick={() => void act(async () => {
        const next = await window.poliscope.chooseWorkspace();
        if (next) { setCatalogue(next); setState(undefined); setScope(''); client.removeQueries({ queryKey: ['world'] }); }
      })}>Choose sandbox folder</button></header>
    <p>A local folder holds your civilizations and retained history. Civic choices and goals start unanswered.</p>
    {error && <p role="alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {dirty && <p>Unsaved interview draft: Apply, cancel or defer before changing the selected state.</p>}
    {catalogue && <>
      <details open={!state}><summary>Create a civilization</summary>
        <form onSubmit={event => { event.preventDefault(); void act(async () => {
          const next = await window.poliscope.createWorld(options);
          selectState(next); setCatalogue(await window.poliscope.workspaceCatalogue());
        }); }}><fieldset disabled={loading}><legend>Named, editable starting conditions</legend>
          <label>Civilization name<input required maxLength={256} value={options.name} onChange={e => setOptions({ ...options, name: e.target.value })} /></label>
          <label>Starting setup<select value={options.setup} onChange={e => {
            const setup = catalogue.setups.find(s => s.id === e.target.value)!;
            setOptions({ ...options, setup: setup.id, population: setup.population, land_area: setup.land_area });
          }}>{catalogue.setups.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
          {options.setup !== 'blank' && <p>Explicit reference selection: synthetic conditions, editable below. No civic arrangements or goals are selected.</p>}
          <label>Settlement name<input required maxLength={256} value={options.scope_name} onChange={e => setOptions({ ...options, scope_name: e.target.value })} /></label>
          <label>Starting population (people, optional)<input inputMode="numeric" maxLength={256} value={options.population ?? ''} onChange={e => setOptions({ ...options, population: e.target.value || null })} /></label>
          <label>Starting land area (km², optional)<input inputMode="decimal" maxLength={256} value={options.land_area ?? ''} onChange={e => setOptions({ ...options, land_area: e.target.value || null })} /></label>
          <label>Purpose (optional, stays in this session)<textarea maxLength={4096} placeholder="What would you like to explore?" /></label>
          <p>Blank quantities remain unknown. Purpose does not create a target or policy.</p>
          <button type="submit">Create sandbox</button>
        </fieldset></form>
      </details>
      <label>Open civilization and branch<select disabled={loading} value={state ? `${state.context.civilization_id}/${state.context.branch_id}` : ''} onChange={e => {
        const branch = catalogue.branches.find(b => `${b.context.civilization_id}/${b.context.branch_id}` === e.target.value);
        if (branch) void act(async () => selectState(await window.poliscope.selectWorld({ civilization_id: branch.context.civilization_id, branch_id: branch.context.branch_id, revision_id: null })));
      }}><option value="" disabled>Select a saved branch</option>{catalogue.branches.map(b => <option key={`${b.context.civilization_id}/${b.context.branch_id}`} value={`${b.context.civilization_id}/${b.context.branch_id}`}>{b.name} · {b.context.branch_id}</option>)}</select></label>
      {state && <>
        <div className="state-banner" aria-label="Selected state"><strong>{state.branch.name}</strong>
          <span>Branch: {state.context.branch_id} · {state.context.revision_id === state.branch.context.revision_id ? 'Confirmed design revision' : 'Historical revision — read only'}</span>
          <span>Revision: {state.context.revision_id}</span><span>Model: {state.versions.model_id} · Tick: {state.effective_time.tick} · Calendar: {state.effective_time.calendar_id}</span>
          <label>Scope<select disabled={loading || !scopes.data?.length} value={selectedScope} onChange={e => {
            void client.cancelQueries({ queryKey: ['world'] }); setScope(e.target.value); setConditionInspector(undefined);
          }}>{scopes.data?.map(s => <option key={s.id} value={s.id}>{s.label} ({s.scope_kind})</option>)}</select></label>
          <label>Read a retained revision (leave blank for current branch head)<input key={`${state.context.civilization_id}/${state.context.branch_id}`} name="revision-id" maxLength={128} onKeyDown={e => {
            if (e.key === 'Enter' && !loading) { e.preventDefault(); const revision = e.currentTarget.value;
              void act(async () => selectState(await window.poliscope.selectWorld({ civilization_id: state.context.civilization_id, branch_id: state.context.branch_id, revision_id: revision || null })));
            }
          }} /></label><p>Press Enter to open the revision. Saved revisions remain attached to their original state.</p>
        </div>
        <div className="workspace-layout"><nav aria-label="Workspaces">{VIEWS.map(name => <button key={name} disabled={dirty} aria-current={view === name ? 'page' : undefined} onClick={() => setView(name)}>{name}</button>)}</nav>
          <article className="workspace-body"><h3>{view}</h3>
            <p>{state.goal_count} declared goals · {state.policy_count} selected policies · {state.mechanism_count} registered mechanisms</p>
            <p>{state.mechanism_count === 0 ? 'This starting model has no numerical social mechanisms. Qualitative commitments have no calculated social effects; observations below are authored conditions.' : 'This saved model contains mechanism bindings. Synthetic qualitative interviews are available; execution requires the matching registered model.'}</p>
            {view === 'Civilization overview' && selectedScope && <Overview key={JSON.stringify([state.context, selectedScope, state.versions])} state={state} scope={selectedScope} />}
            {view === 'History and comparison' && <DesignHistory key={JSON.stringify(state.context)} state={state} disabled={loading} onSelected={async next => { selectState(next); setCatalogue(await window.poliscope.workspaceCatalogue()); await client.invalidateQueries({ queryKey: ['world'] }); }} />}
            {selectedScope && <div hidden={view !== 'Decision atlas'}><Atlas state={state} scope={selectedScope} active={view === 'Decision atlas'} disabled={dirty} filters={atlasFilters} setFilters={setAtlasFilters}
              onInterview={query => { setDomain(query.domain_id); setQuestionId(query.question_id ?? null); requestAnimationFrame(() => document.getElementById('selected-interview')?.focus()); }} onHistory={() => setView('History and comparison')} /></div>}
            <h4>Enter a domain</h4><div className="domain-grid">{catalogue.domains.map(d => <button key={d.id} disabled={dirty} aria-pressed={domain === d.id} onClick={() => { setDomain(d.id); setQuestionId(null); }}>{d.name}<small>Synthetic interview · social mechanisms not supplied</small></button>)}</div>
            {domain && <section aria-label="Selected domain" id="selected-interview" tabIndex={-1}><h4>{catalogue.domains.find(d => d.id === domain)?.name ?? 'Source question · domain mapping unresolved'}</h4><p>Open for exploration. Select a draft, inspect it, then preview before Apply.</p>
              {selectedScope && <Interview key={JSON.stringify([state.context, selectedScope, domain, questionId])}
                query={{ context: state.context, scope_id: selectedScope, domain_id: domain, question_id: questionId }} versions={state.versions}
                historical={state.context.revision_id !== state.branch.context.revision_id} onDirty={draftChanged}
                onConfirmed={(next, message) => { draftChanged(false); setNotice(message); setState(next); void client.invalidateQueries({ queryKey: ['world'] }); }} />}</section>}
            {view !== 'Civilization overview' && view !== 'World and institutions' && view !== 'Society map' && view !== 'History and comparison' && view !== 'Decision atlas' && <p>The {view.toLowerCase()} tools are not yet available. You can continue exploring every domain and the selected state.</p>}
            <h4>Starting conditions · {scopes.data?.find(s => s.id === selectedScope)?.label ?? 'Loading scope'}</h4>
            {(scopes.isError || values.isError) && <p role="alert">This state could not be read. Reopen the branch to retry.</p>}
            {values.isFetching ? <p>Loading this state…</p> : <table><caption>Authored conditions for the selected revision and scope</caption><thead><tr><th>Condition</th><th>Value</th><th>Meaning</th></tr></thead><tbody>{values.data?.filter(v => 'value' in v && v.partition === 'conditions').map(v => 'value' in v && <tr key={v.id}><th>{v.property_id}</th><td><button title="Inspect authored condition" onClick={() => setConditionInspector(v.id)}>{v.value.kind === 'unknown' ? 'Unknown' : v.value.kind === 'quantity' ? `${v.value.value} ${v.value.unit_id}` : v.value.kind === 'label' ? v.value.value : v.value.entity_id}</button></td><td>{v.value.kind === 'unknown' ? v.value.reason : 'Player-supplied starting condition'}</td></tr>)}</tbody></table>}
            {conditionInspector && <Inspector key={JSON.stringify([state.context, selectedScope, conditionInspector])} state={state} scope={selectedScope} selection={{ collection: 'conditions', id: conditionInspector }} close={() => setConditionInspector(undefined)} />}
            <button aria-expanded={inspector} onClick={() => setInspector(!inspector)}>State inspector</button>
          </article>
          {inspector && <aside aria-label="State inspector"><h3>State identity</h3><dl>{Object.entries({ ...state.context, ...state.versions, scope_id: selectedScope }).map(([key, value]) => <React.Fragment key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{value}</dd></React.Fragment>)}</dl><p>All views read the same Python-owned world. Temporary navigation and filters stay in this session.</p></aside>}
        </div>
      </>}
    </>}
  </section>;
}
