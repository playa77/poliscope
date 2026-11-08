import { Providers } from './providers';
import { Recovery } from './recovery';
import { Workspace, VIEWS } from './workspace';
import React, { useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import {
  Archive, BookOpenCheck, ChevronDown, Compass, Database, GitCompare, Globe2, Grid3x3, History,
  Landmark, LayoutDashboard, Map, Plug, RotateCw, X,
} from 'lucide-react';
import type { ShellAPI, HistoryReply } from '../shell';
import type { HistoryRequest } from '../../contracts/history';
import { AppShell, Brand, NavGroup, NavItem } from '@/components/app/shell';
import { ErrorNote, Panel } from '@/components/app/blocks';
import { NativeSelect } from '@/components/app/native-select';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import './style.css';
declare global { interface Window { poliscope: ShellAPI } }

const NAV: { group: string; items: { view: string; label: string; icon: typeof Globe2 }[] }[] = [
  {
    group: 'Understand',
    items: [
      { view: 'Civilization overview', label: 'Overview', icon: LayoutDashboard },
      { view: 'Society map', label: 'Society map', icon: Map },
      { view: 'Decision atlas', label: 'Decision atlas', icon: Compass },
      { view: 'Dependency matrix', label: 'Dependency matrix', icon: Grid3x3 },
      { view: 'World and institutions', label: 'World and institutions', icon: Landmark },
    ],
  },
  {
    group: 'Interpret',
    items: [
      { view: 'Uncertainty and sensitivity', label: 'Uncertainty', icon: Globe2 },
      { view: 'Timeline and experiments', label: 'Timeline', icon: History },
      { view: 'History and comparison', label: 'History and comparison', icon: GitCompare },
      { view: 'Evidence and models', label: 'Evidence and models', icon: Database },
    ],
  },
  {
    group: 'Data',
    items: [
      { view: 'Portable archives', label: 'Archives', icon: Archive },
    ],
  },
];

function App() {
  const status = useQuery({ queryKey: ['bootstrap'], queryFn: () => window.poliscope.bootstrapStatus(), refetchInterval: 500, retry: false });
  const [assistantDraft, setAssistantDraft] = useState('');
  const [providersOpen, setProvidersOpen] = useState(false);
  const [view, setView] = useState(VIEWS[0]);
  const providerOrigin = useRef<HTMLElement | null>(null);
  const providerButton = useRef<HTMLButtonElement>(null);
  const openProviders = () => { providerOrigin.current = document.activeElement instanceof HTMLElement ? document.activeElement : null; setProvidersOpen(true); requestAnimationFrame(() => document.getElementById('provider-settings')?.focus()); };
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
  const engineText = status.isError ? 'Local engine unavailable' : status.data?.detail ?? 'Starting local engine';
  return (
    <AppShell
      brand={<Brand title="Poliscope" subtitle="Local society sandbox" icon={Globe2} />}
      navigation={
        <>
          {NAV.map((section) => (
            <NavGroup key={section.group} label={section.group}>
              {section.items.map((item) => (
                <NavItem key={item.view} label={item.label} icon={item.icon} active={view === item.view}
                  disabled={draft} onSelect={() => setView(item.view)} />
              ))}
            </NavGroup>
          ))}
        </>
      }
      status={
        <div className="flex items-start gap-2 px-2 py-1">
          <span aria-hidden className={status.isError ? 'mt-1.5 size-2 shrink-0 rounded-full bg-destructive' : 'mt-1.5 size-2 shrink-0 rounded-full bg-success'} />
          <p role="status" className="min-w-0 break-words text-[11px] leading-tight text-muted-foreground">{engineText}</p>
        </div>
      }
    >
      <a className="skip-link" href="#sandbox-heading" onClick={event => { event.preventDefault(); document.getElementById('sandbox-heading')?.focus(); }}>Skip to society workspace</a>
      <main className="flex min-w-0 flex-col gap-5 pb-10">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">Poliscope</p>
            <h1 className="text-balance text-2xl font-semibold tracking-tight">A society, open to possibility.</h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" ref={providerButton} onClick={openProviders}><Plug aria-hidden />Open provider settings</Button>
            <Button variant="outline" disabled={busy || draft} onClick={() => void action(async () => { await window.poliscope.reconnect(); setResult(null); setWorkspaceGeneration(n => n + 1); })}>
              <RotateCw aria-hidden />Reconnect local engine
            </Button>
          </div>
        </div>

        <Workspace key={workspaceGeneration} view={view} onView={setView} onDraftChange={setDraft} onProviders={openProviders} onAskAssistant={text => { setAssistantDraft(text); openProviders(); }} />

        {error && <ErrorNote>{error}</ErrorNote>}

        <details className="group rounded-card bg-card px-5 py-4 shadow-[var(--shadow-card)]">
          <summary className="flex cursor-pointer items-center gap-2 text-sm font-medium"><BookOpenCheck aria-hidden className="size-4 text-primary" /> Read saved historical evidence<ChevronDown aria-hidden className="ml-auto size-4 text-muted-foreground transition-transform group-open:rotate-180" /></summary>
          <div className="mt-3 flex flex-col gap-3">
            <p className="text-xs text-muted-foreground">Supply the retained result’s identities, then choose its SQLite store. Reading stored evidence does not reproduce a simulation or enable edits. Supported saved-evidence schema: 1.</p>
            <form className="flex flex-col gap-3" onSubmit={open}>
              <fieldset disabled={busy || draft} className="m-0 grid min-w-0 gap-3 border-0 p-0 sm:grid-cols-2 xl:grid-cols-3">
                <legend className="sr-only">Saved result selection</legend>
                {['storage_context_id', 'data_store_id', 'civilization_id', 'branch_id', 'revision_id', 'result_id'].map(name => (
                  <div key={name} className="flex min-w-0 flex-col gap-1.5">
                    <Label htmlFor={`history-${name}`}>{name.replaceAll('_', ' ')}</Label>
                    <Input id={`history-${name}`} name={name} required maxLength={128} />
                  </div>
                ))}
              </fieldset>
              <div><Button type="submit" disabled={busy || draft}>Choose store and read</Button></div>
            </form>
            {result && 'error' in result && <ErrorNote title="Stored evidence unavailable">{result.error}. Original store preserved.</ErrorNote>}
          </div>
        </details>

        {saved && (
          <Panel title="Stored historical evidence — read only" description="Read from the retained SQLite store. Nothing here re-runs a simulation."
            action={<span className="rounded-full bg-muted px-2.5 py-1 text-[11px] text-muted-foreground">Read only</span>}>
            <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2 xl:grid-cols-3">
              {Object.entries({ ...saved.context, ...saved.versions, result_id: saved.result_id, scope_id: saved.scope_id,
                tick: saved.effective_time.tick, calendar: saved.effective_time.calendar_id }).map(([key, value]) => (
                <div key={key} className="min-w-0">
                  <dt className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{key.replaceAll('_', ' ')}</dt>
                  <dd className="mt-0.5 break-words text-sm">{value}</dd>
                </div>
              ))}
            </dl>
            {saved.kind === 'evaluation' ? (
              <div className="mt-4 flex flex-col gap-1 text-sm"><p>Outcome: {saved.outcome}</p><p className="text-muted-foreground">Coverage: {saved.coverage.status} — {saved.coverage.explanation}</p></div>
            ) : (
              <div className="mt-4 flex flex-col gap-2">
                <p className="text-sm">Collection: {saved.page.kind}</p>
                <pre className="max-h-80 overflow-auto rounded-xl bg-muted p-3 text-xs">{JSON.stringify(saved.page.items, null, 2)}</pre>
                {saved.page.next_cursor !== null && <div><Button variant="outline" disabled={busy || draft} onClick={() => void action(() => window.poliscope.historyPage(saved.page.kind, Number(saved.page.next_cursor)))}>Next page</Button></div>}
              </div>
            )}
            <div className="mt-4 flex flex-wrap items-end gap-3">
              <div className="flex w-56 flex-col gap-1.5">
                <Label htmlFor="history-collection">Evidence collection</Label>
                <NativeSelect id="history-collection" value={collection} onChange={event => setCollection(event.target.value as HistoryRequest['collection'])}>
                  {['summary', 'outputs', 'findings', 'sources', 'assumptions', 'traces'].map(value => <option key={value} value={value}>{value}</option>)}
                </NativeSelect>
              </div>
              <Button variant="outline" disabled={busy || draft} onClick={() => void action(() => window.poliscope.historyPage(collection, 0))}>Read collection</Button>
            </div>
          </Panel>
        )}

        <Panel title="Recovery" description="Reopen a folder, inspect confirmed worlds, or reset what this session holds.">
          <div className="legacy-ui"><Recovery locked={busy || draft} /></div>
        </Panel>
      </main>

      {providersOpen && (
        <div role="dialog" aria-modal="true" aria-label="Provider settings panel" className="fixed inset-0 z-40 flex justify-end bg-[rgb(32_35_58/0.32)] backdrop-blur-[2px]">
          <div className="flex h-full w-full max-w-3xl flex-col overflow-y-auto bg-background p-6 shadow-[var(--shadow-float)]">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold tracking-tight">Provider settings</h2>
              <Button variant="ghost" size="icon" aria-label="Close provider settings" onClick={() => { setProvidersOpen(false); (providerOrigin.current?.isConnected ? providerOrigin.current : providerButton.current)?.focus(); }}><X aria-hidden /></Button>
            </div>
            <Providers interviewDraft={assistantDraft} locked={draft} onApplied={() => setWorkspaceGeneration(n => n + 1)} />
          </div>
        </div>
      )}
    </AppShell>
  );
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={new QueryClient()}><App /></QueryClientProvider></React.StrictMode>);
