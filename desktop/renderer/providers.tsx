import { Assistant } from './assistant';
import React, { useEffect, useRef, useState } from 'react';
import { KeyRound, RefreshCw, ShieldCheck, Trash2 } from 'lucide-react';
import type { ProviderProfile, ProviderReply } from '../../contracts/provider';
import type { ProviderRequest } from '../main/providers';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/app/native-select';
import { Actions, CheckField, Disclosure, Field, Hint, SubHeading, Toolbar } from '@/components/app/form';
import { ErrorNote, Panel, StateBadge } from '@/components/app/blocks';

const empty = (): ProviderProfile => ({ id: crypto.randomUUID(), name: '', kind: 'openrouter', endpoint: 'https://openrouter.ai/api/v1', model: '',
  generation: { temperature: null, top_p: null, max_output_tokens: null },
  routing: { order: [], only: [], ignore: [], allow_fallbacks: false, require_parameters: true, data_collection: 'unknown' },
  capabilities: { text: 'unknown', image: 'unknown', audio: 'unknown', video: 'unknown', tools: 'unknown', structured_output: 'unknown', reasoning: 'unknown' } });
const messages: Record<ProviderReply['status'], string> = {
  'metadata-ready': 'Metadata loaded. Discovery does not verify generation suitability.', 'metadata-invalid': 'Provider metadata schema was not understood. Retained catalog preserved; refresh deliberately after checking provider compatibility.',
  'metadata-unsupported': 'This adapter does not declare this metadata endpoint. Capability and account information remain unknown.',
  'rate-limited': 'Provider rate limit reached. Wait and refresh deliberately.', 'credits-required': 'Provider requires credits. Check your account before retrying.',
  'model-unavailable': 'Model or metadata endpoint unavailable. Your saved model choice is preserved.',
  ready: 'Provider settings ready. No request has been sent.', saved: 'Saved provider settings.', removed: 'Key or profile removed; related requests cancelled.',
  'test-accepted': 'Metadata endpoint accepted the request. Model access, generation and capabilities remain unverified.', unauthorized: 'Provider rejected authentication. Replace the key or check account access.',
  'redirect-blocked': 'Provider redirect blocked. Configure the intended endpoint explicitly before entering a key.', cancelled: 'Provider metadata request cancelled or timed out.',
  'network-failed': 'Provider connection failed. Check endpoint, proxy or network and test again deliberately.', 'provider-rejected': 'Provider rejected the metadata request. Check endpoint and account access.',
  'key-unavailable': 'Key unavailable. Enter a replacement; protected storage may be unavailable on this account.', 'storage-failed': 'Settings or key could not be saved. Check local storage and refresh before retrying.',
  'stale-profile': 'This profile changed. Refresh settings before retrying.',
};
export function Providers({locked=false,onApplied,interviewDraft}:{locked?:boolean;onApplied?:()=>void;interviewDraft?:string}) {
  const [reply, setReply] = useState<ProviderReply>();
  const [profile, setProfile] = useState<ProviderProfile>(empty);
  const [metadata, setMetadata] = useState<ProviderReply>();
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState('');
  const [notice, setNotice] = useState('Loading provider settings…');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false), [testing, setTesting] = useState(false);
  const generation = useRef(0), keyField = useRef<HTMLInputElement>(null);
  const row = reply?.profiles.find(p => p.profile.id === selected);
  const changed = Boolean(row && JSON.stringify(profile) !== JSON.stringify(row.profile));
  async function request(query: ProviderRequest) {
    const id = ++generation.current;
    const isTest = ['test-key','refresh-catalog','model-endpoints','key-status'].includes(query.action);
    if (isTest) setTesting(true); else setBusy(true);
    setError(''); setNotice(isTest ? 'Testing metadata endpoint…' : 'Updating settings…');
    try {
      const next = await window.poliscope.provider(query);
      if (id !== generation.current) return;
      setReply(next); setNotice(messages[next.status]);
      if (query.action === 'catalog' || query.action === 'refresh-catalog' || query.action === 'model-endpoints' || query.action === 'key-status') setMetadata(next);
      if (query.action === 'replace-key' || query.action === 'remove-key') setMetadata(previous => previous ? {...previous, key_metadata:null} : undefined);
      if (query.action === 'list' && selected) {
        const fresh = next.profiles.find(p => p.profile.id === selected);
        if (fresh) setProfile(fresh.profile); else { setSelected(''); setProfile(empty()); }
      }
      if (query.action === 'save' && next.status === 'saved') {
        setMetadata(undefined);
        const saved = next.profiles.find(p => p.profile.id === query.profile.id)!;
        setSelected(saved.profile.id); setProfile(saved.profile);
      }
      if (query.action === 'delete' && next.status === 'removed') { setSelected(''); setProfile(empty()); }
    } catch { if (id === generation.current) setError('Provider settings unavailable. Check the endpoint and local storage, then refresh. No secret diagnostics are shown.'); }
    finally { if (isTest) setTesting(false); else setBusy(false); }
  }
  useEffect(() => { void request({ action: 'list' }); return () => { generation.current++; if (keyField.current) keyField.current.value = ''; }; }, []);
  function change(next: Partial<ProviderProfile>) { setProfile(p => ({ ...p, ...next })); }
  function reasoningChange(fields: Partial<NonNullable<ProviderProfile['generation']['reasoning']>>) {
    const next = {...profile.generation.reasoning,...fields};
    change({generation:{...profile.generation,reasoning:Object.values(next).some(v => v != null) ? next : null}});
  }
  return <section aria-label="Provider settings" id="provider-settings" tabIndex={-1} className="flex flex-col gap-4">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h2 className="text-lg font-semibold tracking-tight">Assistant and provider settings</h2>
        <Hint className="mt-1 max-w-3xl">Optional settings for your own provider key. Offline society tools work without a provider. Key testing sends only a fixed metadata request to the saved endpoint; no society data or generation is sent.</Hint>
      </div>
      <StateBadge tone={reply?.protection === 'os-protected' ? 'success' : 'warning'}>
        <ShieldCheck aria-hidden />{reply?.protection === 'os-protected' ? 'OS-protected key storage' : 'Session-only keys'}
      </StateBadge>
    </div>
    <p role="status" className="text-xs leading-relaxed text-muted-foreground">{notice}</p>
    {error && <ErrorNote title="Provider settings unavailable">{error}</ErrorNote>}
    <Hint>{reply?.protection === 'os-protected' ? 'OS-protected key storage available.' : 'Session-only keys: secure OS protection is unavailable. Keys will be forgotten when the app closes.'}</Hint>

    <Panel title="Provider profile" description="Endpoint and preferences. Changing endpoint or provider type removes its key and cancels requests."
      action={<Button variant="outline" size="sm" disabled={busy || testing} onClick={() => void request({ action: 'list' })}><RefreshCw aria-hidden />Refresh provider settings</Button>}>
      <Field label="Provider profile" className="w-72">
        <NativeSelect aria-label="Provider profile" disabled={busy || testing} value={selected} onChange={e => {
          const id = e.target.value; setSelected(id); setMetadata(undefined); setSearch(''); setProfile(reply?.profiles.find(p => p.profile.id === id)?.profile ?? empty());
          if (keyField.current) keyField.current.value = ''; setError('');
        }}><option value="">New profile</option>{reply?.profiles.map(p => <option key={p.profile.id} value={p.profile.id}>{p.profile.name}</option>)}</NativeSelect>
      </Field>
      <form className="mt-3" onSubmit={e => { e.preventDefault(); void request({ action: 'save', profile, expected_revision: row?.revision ?? null }); }}>
        <fieldset disabled={busy || testing} className="m-0 min-w-0 border-0 p-0">
          <legend className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Endpoint and preferences</legend>
          <Toolbar>
            <Field label="Profile name" className="w-64"><Input required maxLength={256} value={profile.name} onChange={e => change({ name: e.target.value })} /></Field>
            <Field label="Provider type" className="w-52">
              <NativeSelect aria-label="Provider type" value={profile.kind} onChange={e => change({ kind: e.target.value as ProviderProfile['kind'], endpoint: e.target.value === 'openrouter' ? 'https://openrouter.ai/api/v1' : '' })}><option value="openrouter">OpenRouter</option><option value="openai-compatible">OpenAI-compatible</option></NativeSelect>
            </Field>
            <Field label="API base endpoint" className="min-w-72 flex-1"><Input required maxLength={2048} type="url" value={profile.endpoint} onChange={e => change({ endpoint: e.target.value })} /></Field>
            <Field label="Selected model ID" className="w-64"><Input maxLength={256} value={profile.model} onChange={e => change({ model: e.target.value })} /></Field>
          </Toolbar>
          <Hint className="mt-2">HTTPS is required except for local loopback services. Changing endpoint or provider type removes its key and cancels requests.</Hint>
          <Disclosure title="Generation preferences" className="mt-3">
            <Hint>Saved for future capability-checked requests; no generation is sent.</Hint>
            <Toolbar>
              {(['temperature', 'top_p', 'frequency_penalty', 'presence_penalty'] as const).map(field => <Field key={field} label={field.replaceAll('_', ' ')} className="w-36"><Input maxLength={20} value={profile.generation[field] ?? ''} onChange={e => change({ generation: { ...profile.generation, [field]: e.target.value || null } })} /></Field>)}
              <Field label="Maximum output tokens" className="w-40"><Input type="number" min={1} max={2147483647} value={profile.generation.max_output_tokens ?? ''} onChange={e => change({ generation: { ...profile.generation, max_output_tokens: e.target.value ? Number(e.target.value) : null } })} /></Field>
              <Field label="Sampling seed" className="w-36"><Input type="number" min={0} max={2147483647} value={profile.generation.seed ?? ''} onChange={e => change({generation:{...profile.generation,seed:e.target.value ? Number(e.target.value) : null}})} /></Field>
              <Field label="Reasoning effort" className="w-40">
                <NativeSelect aria-label="Reasoning effort" value={profile.generation.reasoning?.effort ?? ''} onChange={e => reasoningChange({effort:e.target.value as NonNullable<ProviderProfile['generation']['reasoning']>['effort'] || null,...(e.target.value ? {max_tokens:null} : {})})}><option value="">Provider default</option>{['none','minimal','low','medium','high','xhigh','max'].map(v => <option key={v}>{v}</option>)}</NativeSelect>
              </Field>
              <Field label="Reasoning token budget" className="w-44"><Input type="number" min={1} max={2147483647} value={profile.generation.reasoning?.max_tokens ?? ''} onChange={e => reasoningChange({max_tokens:e.target.value ? Number(e.target.value) : null,...(e.target.value ? {effort:null} : {})})} /></Field>
              <Field label="Return reasoning" className="w-56">
                <NativeSelect aria-label="Return reasoning" value={profile.generation.reasoning?.exclude == null ? '' : String(profile.generation.reasoning.exclude)} onChange={e => reasoningChange({exclude:e.target.value ? e.target.value === 'true' : null})}><option value="">Provider default</option><option value="true">Exclude reasoning from replies</option><option value="false">Include when available</option></NativeSelect>
              </Field>
            </Toolbar>
          </Disclosure>
          <Disclosure title="Routing preferences" className="mt-2">
            <Hint>Saved preferences only. Provider support will be checked before generation becomes available.</Hint>
            <Toolbar>
              {(['order','only','ignore'] as const).map(field => <Field key={field} label={`Provider ${field} (comma-separated)`} className="w-64"><Input maxLength={8192} value={profile.routing[field].join(', ')} onChange={e => change({ routing: { ...profile.routing, [field]: e.target.value.split(',').map(s => s.trim()).filter(Boolean) } })} /></Field>)}
              <CheckField checked={profile.routing.allow_fallbacks} onChange={v => change({ routing: { ...profile.routing, allow_fallbacks: v } })} className="w-full">Allow provider fallbacks</CheckField>
              <Field label="Model fallbacks in order (comma-separated)" className="w-full"><Input maxLength={2048} value={(profile.routing.model_fallbacks ?? []).join(', ')} onChange={e => change({routing:{...profile.routing,model_fallbacks:e.target.value.split(',').map(s => s.trim()).filter(Boolean)}})} /></Field>
            </Toolbar>
            <Hint className="mt-2">Only the explicitly listed models may replace the selected model. Every model must support the complete request. Provider failover alone cannot change the model.</Hint>
            <Toolbar className="mt-2">
              <CheckField checked={profile.routing.require_parameters} onChange={v => change({ routing: { ...profile.routing, require_parameters: v } })} className="w-full">Require selected parameter support</CheckField>
              <Field label="Data collection preference" className="w-44">
                <NativeSelect aria-label="Data collection preference" value={profile.routing.data_collection} onChange={e => change({ routing: { ...profile.routing, data_collection: e.target.value as ProviderProfile['routing']['data_collection'] } })}>{['unknown','allow','deny'].map(v => <option key={v}>{v}</option>)}</NativeSelect>
              </Field>
              <Field label="Zero data retention" className="w-56">
                <NativeSelect aria-label="Zero data retention" value={profile.routing.zdr == null ? '' : String(profile.routing.zdr)} onChange={e => change({routing:{...profile.routing,zdr:e.target.value ? e.target.value === 'true' : null}})}><option value="">Unspecified</option><option value="true">Require ZDR endpoints</option><option value="false">Do not require ZDR</option></NativeSelect>
              </Field>
              <Field label="Provider sort" className="w-40">
                <NativeSelect aria-label="Provider sort" value={profile.routing.sort ?? ''} onChange={e => change({routing:{...profile.routing,sort:e.target.value as ProviderProfile['routing']['sort'] || null}})}><option value="">Unspecified</option>{['price','throughput','latency'].map(v => <option key={v}>{v}</option>)}</NativeSelect>
              </Field>
            </Toolbar>
            <Hint className="mt-2">Maximum provider prices: USD per million prompt/completion tokens, or per request/image. These routing ceilings do not authorize spending.</Hint>
            <Toolbar className="mt-2">
              {(['prompt','completion','request','image'] as const).map(field => <Field key={field} label={`Maximum ${field} price`} className="w-40"><Input maxLength={20} value={profile.routing.max_price?.[field] ?? ''} onChange={e => { const prices = {...profile.routing.max_price,[field]:e.target.value || null}; change({routing:{...profile.routing,max_price:Object.values(prices).some(v => v != null) ? prices : null}}); }} /></Field>)}
            </Toolbar>
          </Disclosure>
          <Disclosure title="Declared capability preferences" className="mt-2">
            <Hint>Declarations are unverified preferences; saving them does not establish model support.</Hint>
            <Toolbar>
              {(Object.keys(profile.capabilities) as (keyof ProviderProfile['capabilities'])[]).map(field => <Field key={field} label={`${field.replaceAll('_',' ')} capability`} className="w-40">
                <NativeSelect value={profile.capabilities[field]} onChange={e => change({ capabilities: { ...profile.capabilities, [field]: e.target.value } })}>{['unknown','supported','unsupported'].map(v => <option key={v}>{v}</option>)}</NativeSelect>
              </Field>)}
            </Toolbar>
          </Disclosure>
          <Actions className="mt-3"><Button type="submit">Save provider profile</Button></Actions>
        </fieldset>
      </form>
    </Panel>

    {row && <Panel title="Key storage" description="Keys are never displayed again. Testing sends a fixed metadata request to the saved endpoint only."
      action={<StateBadge tone={row.key_status === 'missing' ? 'warning' : 'success'}>{row.key_status}</StateBadge>}>
      <Hint>Saved key destination: {row.profile.endpoint}</Hint>
      {changed && <Hint>Save endpoint and preference changes before entering or testing a key.</Hint>}
      <p className="mt-1 text-xs text-muted-foreground">Key storage: {row.key_status}. Keys are never displayed again.</p>
      <form className="mt-3" onSubmit={e => {
        e.preventDefault();
        const key = keyField.current?.value ?? '';
        if (keyField.current) keyField.current.value = '';
        void request({ action: 'replace-key', profile_id: row.profile.id, expected_revision: row.revision, key });
      }}>
        <fieldset disabled={busy || testing || changed} className="m-0 min-w-0 border-0 p-0">
          <legend className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Temporary key entry</legend>
          <Toolbar>
            <Field label="New provider key" className="min-w-72 flex-1"><Input ref={keyField} required type="password" autoComplete="off" spellCheck={false} maxLength={4096} /></Field>
            <Button type="submit"><KeyRound aria-hidden />Replace provider key</Button>
          </Toolbar>
        </fieldset>
      </form>
      <Actions className="mt-3">
        <Button variant="outline" disabled={busy || testing || changed || row.key_status === 'missing'} onClick={() => void request({ action: 'test-key', profile_id: row.profile.id, expected_revision: row.revision })}>Test saved key</Button>
        <Button variant="destructive" disabled={busy} onClick={() => void request({ action: 'remove-key', profile_id: row.profile.id, expected_revision: row.revision })}><Trash2 aria-hidden />Remove key and cancel requests</Button>
        <Button variant="outline" disabled={busy} onClick={() => void request({ action: 'delete', profile_id: row.profile.id, expected_revision: row.revision })}>Delete provider profile</Button>
      </Actions>
      <Hint className="mt-3">Removing a key deletes active stored material and cancels requests. Filesystem backups or OS recovery may retain older encrypted data; secure erasure is not promised. Key testing does not make a paid generation request.</Hint>
    </Panel>}

    {row && <Panel title="Model catalog and capabilities" description="Metadata is provider-reported evidence, separate from live generation outcomes. Unknown or unsupported capabilities cannot authorize generation. Saved capability preferences do not override discovery.">
      <Toolbar>
        <Field label="Search models and variants" className="min-w-64 flex-1"><Input maxLength={256} value={search} onChange={e => setSearch(e.target.value)} /></Field>
        <Button variant="outline" disabled={busy || testing || changed} onClick={() => void request({action:'catalog', profile_id:row.profile.id, expected_revision:row.revision, search, model_id:row.profile.model})}>Search cached models</Button>
        <Button variant="outline" disabled={busy || testing || changed} onClick={() => void request({action:'refresh-catalog', profile_id:row.profile.id, expected_revision:row.revision, search})}>Refresh model catalog</Button>
        <Button variant="ghost" disabled={busy || testing || changed || row.profile.kind !== 'openrouter'} onClick={() => void request({action:'key-status', profile_id:row.profile.id, expected_revision:row.revision})}>Inspect key limits</Button>
        <Button variant="ghost" disabled={busy || testing || changed || row.profile.kind !== 'openrouter' || !row.profile.model} onClick={() => void request({action:'model-endpoints', profile_id:row.profile.id, expected_revision:row.revision, model_id:row.profile.model})}>Refresh selected model providers</Button>
      </Toolbar>
      {metadata?.catalog && <div className="mt-4 flex flex-col gap-2">
        <Hint>Catalog: {metadata.catalog.state}; fetched {metadata.catalog.fetched_at ?? 'never'}. {metadata.catalog.total} matches. Cached data may be unavailable or changed at the provider; refresh before execution.</Hint>
        <div className="flex flex-col gap-3">{metadata.catalog.models.map(model => <article key={model.id} className="rounded-xl border border-border bg-muted/30 p-3">
          <SubHeading as="h4">{model.name}</SubHeading>
          <Hint className="mt-1">{model.id} — {model.available ? 'listed at last refresh' : 'removed from latest catalog'}</Hint>
          <Hint>Source {model.source}, observed {model.observed_at}. Context: {model.context_length ?? 'unknown'}; maximum output: {model.max_output_tokens ?? 'unknown'}.</Hint>
          <Hint>Inputs: {model.input_modalities?.join(', ') ?? 'unknown'}; outputs: {model.output_modalities?.join(', ') ?? 'unknown'}; routing: {model.routing}.</Hint>
          <dl className="mt-2 grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2">{Object.entries(model.capabilities).map(([name,value]) => <React.Fragment key={name}><dt className="text-muted-foreground">{name.replaceAll('_',' ')}</dt><dd>{value}</dd></React.Fragment>)}</dl>
          <Hint className="mt-2">Reported USD prices (prompt/completion per token): {model.pricing ? JSON.stringify(model.pricing) : 'unknown'}. Pricing may be dynamic; no quote or spending approval is implied.</Hint>
          <Disclosure title="Prices and complete provider metadata" className="mt-2 bg-card"><pre className="max-h-64 overflow-auto rounded-lg bg-muted/60 p-2 text-xs">{model.raw_json}</pre></Disclosure>
          <Actions className="mt-2"><Button variant="outline" size="sm" disabled={busy || testing || !model.available} onClick={() => change({model:model.id})}>Choose {model.id}</Button></Actions>
        </article>)}</div>
        <Actions>
          <Button variant="outline" size="sm" disabled={busy || testing || metadata.catalog.offset === 0} onClick={() => void request({action:'catalog',profile_id:row.profile.id,expected_revision:row.revision,search,model_id:row.profile.model,offset:Math.max(0,metadata.catalog!.offset-5)})}>Previous models</Button>
          <Button variant="outline" size="sm" disabled={busy || testing || metadata.catalog.offset+5 >= metadata.catalog.total} onClick={() => void request({action:'catalog',profile_id:row.profile.id,expected_revision:row.revision,search,model_id:row.profile.model,offset:metadata.catalog!.offset+5})}>Next models</Button>
        </Actions>
      </div>}
      {metadata?.endpoints && <div className="mt-4 flex flex-col gap-2">
        <SubHeading as="h4">Selected model providers</SubHeading>
        <Hint>{metadata.endpoints.model_id}; source {metadata.endpoints.source}; observed {metadata.endpoints.observed_at}. Retained provider metadata; refresh deliberately to check current availability. Endpoint capabilities and prices may differ from catalog aggregates.</Hint>
        {metadata.endpoints.providers.map((provider,index) => <article key={index} className="rounded-xl border border-border p-3">
          <SubHeading as="h5">{provider.provider_name}</SubHeading>
          <Hint className="mt-1">Context: {provider.context_length ?? 'unknown'}; maximum output: {provider.max_output_tokens ?? 'unknown'}; prices: {provider.pricing ? JSON.stringify(provider.pricing) : 'unknown'}.</Hint>
          <dl className="mt-2 grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2">{Object.entries(provider.capabilities).map(([name,value]) => <React.Fragment key={name}><dt className="text-muted-foreground">{name}</dt><dd>{value}</dd></React.Fragment>)}</dl>
        </article>)}
        <Disclosure title="Complete endpoint metadata" className="bg-card"><pre className="max-h-64 overflow-auto rounded-lg bg-muted/60 p-2 text-xs">{metadata.endpoints.raw_json}</pre></Disclosure>
      </div>}
      {metadata?.key_metadata && <div className="mt-4 flex flex-col gap-1">
        <SubHeading as="h4">Reported key limits</SubHeading>
        <Hint>Observed {metadata.key_metadata.observed_at}; source {metadata.key_metadata.source}. Account metadata can change and does not authorize spending.</Hint>
        <Hint>Limit: {metadata.key_metadata.limit ?? 'unknown/unlimited'}; remaining: {metadata.key_metadata.limit_remaining ?? 'unknown/unlimited'}; usage: {metadata.key_metadata.usage ?? 'unknown'}; free tier: {String(metadata.key_metadata.is_free_tier ?? 'unknown')}.</Hint>
      </div>}
    </Panel>}
    <Assistant interviewDraft={interviewDraft} view={row} onApplied={onApplied} disabled={locked || busy || testing || changed} />
  </section>;
}
