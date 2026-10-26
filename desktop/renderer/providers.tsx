import { Assistant } from './assistant';
import React, { useEffect, useRef, useState } from 'react';
import type { ProviderProfile, ProviderReply } from '../../contracts/provider';
import type { ProviderRequest } from '../main/providers';
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
  return <section aria-label="Provider settings" id="provider-settings" tabIndex={-1}>
    <h2>Assistant and provider settings</h2>
    <p>Optional BYOK settings. Offline society tools work without a provider. Key testing sends only a fixed metadata request to the saved endpoint; no society data or generation is sent.</p>
    <p role="status">{notice}</p>{error && <p role="alert">{error}</p>}
    <p>{reply?.protection === 'os-protected' ? 'OS-protected key storage available.' : 'Session-only keys: secure OS protection is unavailable. Keys will be forgotten when the app closes.'}</p>
    <button disabled={busy || testing} onClick={() => void request({ action: 'list' })}>Refresh provider settings</button>
    <label>Provider profile<select aria-label="Provider profile" disabled={busy || testing} value={selected} onChange={e => {
      const id = e.target.value; setSelected(id); setMetadata(undefined); setSearch(''); setProfile(reply?.profiles.find(p => p.profile.id === id)?.profile ?? empty());
      if (keyField.current) keyField.current.value = ''; setError('');
    }}><option value="">New profile</option>{reply?.profiles.map(p => <option key={p.profile.id} value={p.profile.id}>{p.profile.name}</option>)}</select></label>
    <form onSubmit={e => { e.preventDefault(); void request({ action: 'save', profile, expected_revision: row?.revision ?? null }); }}>
      <fieldset disabled={busy || testing}><legend>Endpoint and preferences</legend>
        <label>Profile name<input required maxLength={256} value={profile.name} onChange={e => change({ name: e.target.value })} /></label>
        <label>Provider type<select aria-label="Provider type" value={profile.kind} onChange={e => change({ kind: e.target.value as ProviderProfile['kind'], endpoint: e.target.value === 'openrouter' ? 'https://openrouter.ai/api/v1' : '' })}><option value="openrouter">OpenRouter</option><option value="openai-compatible">OpenAI-compatible</option></select></label>
        <label>API base endpoint<input required maxLength={2048} type="url" value={profile.endpoint} onChange={e => change({ endpoint: e.target.value })} /></label>
        <p>HTTPS is required except for local loopback services. Changing endpoint or provider type removes its key and cancels requests.</p>
        <label>Selected model ID<input maxLength={256} value={profile.model} onChange={e => change({ model: e.target.value })} /></label>
        <details><summary>Generation preferences</summary><p>Saved for future capability-checked requests; no generation is sent.</p>
          {(['temperature', 'top_p', 'frequency_penalty', 'presence_penalty'] as const).map(field => <label key={field}>{field.replaceAll('_', ' ')}<input maxLength={20} value={profile.generation[field] ?? ''} onChange={e => change({ generation: { ...profile.generation, [field]: e.target.value || null } })} /></label>)}
          <label>Maximum output tokens<input type="number" min={1} max={2147483647} value={profile.generation.max_output_tokens ?? ''} onChange={e => change({ generation: { ...profile.generation, max_output_tokens: e.target.value ? Number(e.target.value) : null } })} /></label>
          <label>Sampling seed<input type="number" min={0} max={2147483647} value={profile.generation.seed ?? ''} onChange={e => change({generation:{...profile.generation,seed:e.target.value ? Number(e.target.value) : null}})} /></label>
          <label>Reasoning effort<select aria-label="Reasoning effort" value={profile.generation.reasoning?.effort ?? ''} onChange={e => reasoningChange({effort:e.target.value as NonNullable<ProviderProfile['generation']['reasoning']>['effort'] || null,...(e.target.value ? {max_tokens:null} : {})})}><option value="">Provider default</option>{['none','minimal','low','medium','high','xhigh','max'].map(v => <option key={v}>{v}</option>)}</select></label>
          <label>Reasoning token budget<input type="number" min={1} max={2147483647} value={profile.generation.reasoning?.max_tokens ?? ''} onChange={e => reasoningChange({max_tokens:e.target.value ? Number(e.target.value) : null,...(e.target.value ? {effort:null} : {})})} /></label>
          <label>Return reasoning<select aria-label="Return reasoning" value={profile.generation.reasoning?.exclude == null ? '' : String(profile.generation.reasoning.exclude)} onChange={e => reasoningChange({exclude:e.target.value ? e.target.value === 'true' : null})}><option value="">Provider default</option><option value="true">Exclude reasoning from replies</option><option value="false">Include when available</option></select></label>
        </details>
        <details><summary>Routing preferences</summary><p>Saved preferences only. Provider support will be checked before generation becomes available.</p>
          {(['order','only','ignore'] as const).map(field => <label key={field}>Provider {field} (comma-separated)<input maxLength={8192} value={profile.routing[field].join(', ')} onChange={e => change({ routing: { ...profile.routing, [field]: e.target.value.split(',').map(s => s.trim()).filter(Boolean) } })} /></label>)}
          <label><input type="checkbox" checked={profile.routing.allow_fallbacks} onChange={e => change({ routing: { ...profile.routing, allow_fallbacks: e.target.checked } })} />Allow provider fallbacks</label>
          <label>Model fallbacks in order (comma-separated)<input maxLength={2048} value={(profile.routing.model_fallbacks ?? []).join(', ')} onChange={e => change({routing:{...profile.routing,model_fallbacks:e.target.value.split(',').map(s => s.trim()).filter(Boolean)}})} /></label>
          <p>Only the explicitly listed models may replace the selected model. Every model must support the complete request. Provider failover alone cannot change the model.</p>
          <label><input type="checkbox" checked={profile.routing.require_parameters} onChange={e => change({ routing: { ...profile.routing, require_parameters: e.target.checked } })} />Require selected parameter support</label>
          <label>Data collection preference<select aria-label="Data collection preference" value={profile.routing.data_collection} onChange={e => change({ routing: { ...profile.routing, data_collection: e.target.value as ProviderProfile['routing']['data_collection'] } })}>{['unknown','allow','deny'].map(v => <option key={v}>{v}</option>)}</select></label>
          <label>Zero data retention<select aria-label="Zero data retention" value={profile.routing.zdr == null ? '' : String(profile.routing.zdr)} onChange={e => change({routing:{...profile.routing,zdr:e.target.value ? e.target.value === 'true' : null}})}><option value="">Unspecified</option><option value="true">Require ZDR endpoints</option><option value="false">Do not require ZDR</option></select></label>
          <label>Provider sort<select aria-label="Provider sort" value={profile.routing.sort ?? ''} onChange={e => change({routing:{...profile.routing,sort:e.target.value as ProviderProfile['routing']['sort'] || null}})}><option value="">Unspecified</option>{['price','throughput','latency'].map(v => <option key={v}>{v}</option>)}</select></label>
          <p>Maximum provider prices: USD per million prompt/completion tokens, or per request/image. These routing ceilings do not authorize spending.</p>
          {(['prompt','completion','request','image'] as const).map(field => <label key={field}>Maximum {field} price<input maxLength={20} value={profile.routing.max_price?.[field] ?? ''} onChange={e => { const prices = {...profile.routing.max_price,[field]:e.target.value || null}; change({routing:{...profile.routing,max_price:Object.values(prices).some(v => v != null) ? prices : null}}); }} /></label>)}
        </details>
        <details><summary>Declared capability preferences</summary><p>Declarations are unverified preferences; saving them does not establish model support.</p>
          {(Object.keys(profile.capabilities) as (keyof ProviderProfile['capabilities'])[]).map(field => <label key={field}>{field.replaceAll('_',' ')} capability<select value={profile.capabilities[field]} onChange={e => change({ capabilities: { ...profile.capabilities, [field]: e.target.value } })}>{['unknown','supported','unsupported'].map(v => <option key={v}>{v}</option>)}</select></label>)}
        </details><button type="submit">Save provider profile</button>
      </fieldset>
    </form>
    {row && <><p>Saved key destination: {row.profile.endpoint}</p>{changed && <p>Save endpoint and preference changes before entering or testing a key.</p>}<p>Key storage: {row.key_status}. Keys are never displayed again.</p>
      <form onSubmit={e => {
        e.preventDefault();
        const key = keyField.current?.value ?? '';
        if (keyField.current) keyField.current.value = '';
        void request({ action: 'replace-key', profile_id: row.profile.id, expected_revision: row.revision, key });
      }}><fieldset disabled={busy || testing || changed}><legend>Temporary key entry</legend>
        <label>New provider key<input ref={keyField} required type="password" autoComplete="off" spellCheck={false} maxLength={4096} /></label>
        <button type="submit">Replace provider key</button>
      </fieldset></form>
      <section aria-label="Provider metadata"><h3>Model catalog and capabilities</h3>
        <p>Metadata is provider-reported evidence, separate from live generation outcomes. Unknown or unsupported capabilities cannot authorize generation. Saved capability preferences do not override discovery.</p>
        <label>Search models and variants<input maxLength={256} value={search} onChange={e => setSearch(e.target.value)} /></label>
        <button disabled={busy || testing || changed} onClick={() => void request({action:'catalog', profile_id:row.profile.id, expected_revision:row.revision, search, model_id:row.profile.model})}>Search cached models</button>
        <button disabled={busy || testing || changed} onClick={() => void request({action:'refresh-catalog', profile_id:row.profile.id, expected_revision:row.revision, search})}>Refresh model catalog</button>
        <button disabled={busy || testing || changed || row.profile.kind !== 'openrouter'} onClick={() => void request({action:'key-status', profile_id:row.profile.id, expected_revision:row.revision})}>Inspect key limits</button>
        <button disabled={busy || testing || changed || row.profile.kind !== 'openrouter' || !row.profile.model} onClick={() => void request({action:'model-endpoints', profile_id:row.profile.id, expected_revision:row.revision, model_id:row.profile.model})}>Refresh selected model providers</button>
        {metadata?.catalog && <><p>Catalog: {metadata.catalog.state}; fetched {metadata.catalog.fetched_at ?? 'never'}. {metadata.catalog.total} matches. Cached data may be unavailable or changed at the provider; refresh before execution.</p>
          {metadata.catalog.models.map(model => <article key={model.id}><h4>{model.name}</h4><p>{model.id} — {model.available ? 'listed at last refresh' : 'removed from latest catalog'}</p>
            <p>Source {model.source}, observed {model.observed_at}. Context: {model.context_length ?? 'unknown'}; maximum output: {model.max_output_tokens ?? 'unknown'}.</p>
            <p>Inputs: {model.input_modalities?.join(', ') ?? 'unknown'}; outputs: {model.output_modalities?.join(', ') ?? 'unknown'}; routing: {model.routing}.</p>
            <dl>{Object.entries(model.capabilities).map(([name,value]) => <React.Fragment key={name}><dt>{name.replaceAll('_',' ')}</dt><dd>{value}</dd></React.Fragment>)}</dl>
            <p>Reported USD prices (prompt/completion per token): {model.pricing ? JSON.stringify(model.pricing) : 'unknown'}. Pricing may be dynamic; no quote or spending approval is implied.</p>
            <details><summary>Prices and complete provider metadata</summary><pre>{model.raw_json}</pre></details>
            <button disabled={busy || testing || !model.available} onClick={() => change({model:model.id})}>Choose {model.id}</button>
          </article>)}
          <button disabled={busy || testing || metadata.catalog.offset === 0} onClick={() => void request({action:'catalog',profile_id:row.profile.id,expected_revision:row.revision,search,model_id:row.profile.model,offset:Math.max(0,metadata.catalog!.offset-5)})}>Previous models</button>
          <button disabled={busy || testing || metadata.catalog.offset+5 >= metadata.catalog.total} onClick={() => void request({action:'catalog',profile_id:row.profile.id,expected_revision:row.revision,search,model_id:row.profile.model,offset:metadata.catalog!.offset+5})}>Next models</button>
        </>}
        {metadata?.endpoints && <><h4>Selected model providers</h4><p>{metadata.endpoints.model_id}; source {metadata.endpoints.source}; observed {metadata.endpoints.observed_at}. Retained provider metadata; refresh deliberately to check current availability. Endpoint capabilities and prices may differ from catalog aggregates.</p>{metadata.endpoints.providers.map((provider,index) => <article key={index}><h5>{provider.provider_name}</h5><p>Context: {provider.context_length ?? 'unknown'}; maximum output: {provider.max_output_tokens ?? 'unknown'}; prices: {provider.pricing ? JSON.stringify(provider.pricing) : 'unknown'}.</p><dl>{Object.entries(provider.capabilities).map(([name,value]) => <React.Fragment key={name}><dt>{name}</dt><dd>{value}</dd></React.Fragment>)}</dl></article>)}<details><summary>Complete endpoint metadata</summary><pre>{metadata.endpoints.raw_json}</pre></details></>}
        {metadata?.key_metadata && <><h4>Reported key limits</h4><p>Observed {metadata.key_metadata.observed_at}; source {metadata.key_metadata.source}. Account metadata can change and does not authorize spending.</p><p>Limit: {metadata.key_metadata.limit ?? 'unknown/unlimited'}; remaining: {metadata.key_metadata.limit_remaining ?? 'unknown/unlimited'}; usage: {metadata.key_metadata.usage ?? 'unknown'}; free tier: {String(metadata.key_metadata.is_free_tier ?? 'unknown')}.</p></>}
      </section>
      <button disabled={busy || testing || changed || row.key_status === 'missing'} onClick={() => void request({ action: 'test-key', profile_id: row.profile.id, expected_revision: row.revision })}>Test saved key</button>
      <button disabled={busy} onClick={() => void request({ action: 'remove-key', profile_id: row.profile.id, expected_revision: row.revision })}>Remove key and cancel requests</button>
      <button disabled={busy} onClick={() => void request({ action: 'delete', profile_id: row.profile.id, expected_revision: row.revision })}>Delete provider profile</button>
    </>}
    <p>Removing a key deletes active stored material and cancels requests. Filesystem backups or OS recovery may retain older encrypted data; secure erasure is not promised. Key testing does not make a paid generation request.</p>
  <Assistant interviewDraft={interviewDraft} view={row} onApplied={onApplied} disabled={locked || busy || testing || changed} />
  </section>;
}
