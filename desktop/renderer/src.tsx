import { Providers } from './providers';
import { Recovery } from './recovery';
import { Workspace } from './workspace';
import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import type { ShellAPI, HistoryReply } from '../shell';
import type { HistoryRequest } from '../../contracts/history';
import './style.css';
declare global { interface Window { poliscope: ShellAPI } }
function App() {
  const status = useQuery({ queryKey: ['bootstrap'], queryFn: () => window.poliscope.bootstrapStatus(), refetchInterval: 500, retry: false });
  const [providersOpen, setProvidersOpen] = useState(false);
  const openProviders = () => { setProvidersOpen(true); requestAnimationFrame(() => document.getElementById('provider-settings')?.focus()); };
  const [draft, setDraft] = useState(false);
  const [workspaceGeneration, setWorkspaceGeneration] = useState(0);
  const [result, setResult] = useState<HistoryReply>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [collection, setCollection] = useState<HistoryRequest['collection']>('outputs');
  async function action(work: () => Promise<HistoryReply | void>) {
    setBusy(true); setError('');
    try { const next = await work(); if (next) { setResult(next); setWorkspaceGeneration(n => n + 1); } }
    catch { setResult(null); setError('The request could not complete. Your original store is preserved. Retry or select another store.'); }
    finally { setBusy(false); void status.refetch(); }
  }
  function open(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void action(() => window.poliscope.openHistory({ storage_context_id: String(data.get('storage_context_id')), request: {
      history_protocol: 1, context: { data_store_id: String(data.get('data_store_id')), civilization_id: String(data.get('civilization_id')),
        branch_id: String(data.get('branch_id')), revision_id: String(data.get('revision_id')) },
      result_id: String(data.get('result_id')), collection: 'summary', offset: 0, limit: 1,
    } }));
  }
  const saved = result && 'result' in result ? result.result : undefined;
  return <main><p className="eyebrow">Poliscope</p><h1>A society, open to possibility.</h1>
    <button onClick={openProviders}>Open provider settings</button>
    {providersOpen && <Providers />}
    <Workspace key={workspaceGeneration} onDraftChange={setDraft} onProviders={openProviders} />
    <p role="status">{status.isError ? 'Local engine unavailable' : status.data?.detail ?? 'Starting local engine'}</p>
    <button disabled={busy || draft} onClick={() => void action(async () => { await window.poliscope.reconnect(); setResult(null); setWorkspaceGeneration(n => n + 1); })}>Reconnect local engine</button>
    <Recovery locked={busy || draft} />
    <section aria-labelledby="history-heading"><h2 id="history-heading">Read saved historical evidence</h2>
      <p>Supply the retained result’s identities, then choose its SQLite store. Reading stored evidence does not reproduce a simulation or enable edits. Supported saved-evidence schema: 1.</p>
      <form onSubmit={open}><fieldset disabled={busy || draft}><legend>Saved result selection</legend>
        {['storage_context_id', 'data_store_id', 'civilization_id', 'branch_id', 'revision_id', 'result_id'].map(name => <label key={name}>{name.replaceAll('_', ' ')}<input name={name} required maxLength={128} /></label>)}
        <button type="submit">Choose store and read</button>
      </fieldset></form>
    </section>
    {error && <p role="alert">{error}</p>}
    {result && 'error' in result && <p role="alert">Stored evidence unavailable: {result.error}. Original store preserved.</p>}
    {saved && <section aria-labelledby="saved-heading"><h2 id="saved-heading">Stored historical evidence — read only</h2>
      <dl>{Object.entries({ ...saved.context, ...saved.versions, result_id: saved.result_id, scope_id: saved.scope_id,
        tick: saved.effective_time.tick, calendar: saved.effective_time.calendar_id }).map(([key, value]) => <React.Fragment key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{value}</dd></React.Fragment>)}</dl>
      {saved.kind === 'evaluation' ? <><p>Outcome: {saved.outcome}</p><p>Coverage: {saved.coverage.status} — {saved.coverage.explanation}</p></> : <><p>Collection: {saved.page.kind}</p><pre>{JSON.stringify(saved.page.items, null, 2)}</pre>
        {saved.page.next_cursor !== null && <button disabled={busy || draft} onClick={() => void action(() => window.poliscope.historyPage(saved.page.kind, Number(saved.page.next_cursor)))}>Next page</button>}</>}
      <label>Evidence collection<select value={collection} onChange={event => setCollection(event.target.value as HistoryRequest['collection'])}>
        {['summary', 'outputs', 'findings', 'sources', 'assumptions', 'traces'].map(value => <option key={value}>{value}</option>)}
      </select></label>
      <button disabled={busy || draft} onClick={() => void action(() => window.poliscope.historyPage(collection, 0))}>Read collection</button>
    </section>}
  </main>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={new QueryClient()}><App /></QueryClientProvider></React.StrictMode>);
