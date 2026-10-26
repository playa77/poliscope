import React, { useEffect, useRef, useState } from 'react';
import type { ProviderProfile, ProviderReply } from '../../contracts/provider';
import type { ProviderRequest } from '../main/providers';
const empty = (): ProviderProfile => ({ id: crypto.randomUUID(), name: '', kind: 'openrouter', endpoint: 'https://openrouter.ai/api/v1', model: '',
  generation: { temperature: null, top_p: null, max_output_tokens: null },
  routing: { order: [], only: [], ignore: [], allow_fallbacks: false, require_parameters: true, data_collection: 'unknown' },
  capabilities: { text: 'unknown', image: 'unknown', audio: 'unknown', video: 'unknown', tools: 'unknown', structured_output: 'unknown', reasoning: 'unknown' } });
const messages: Record<ProviderReply['status'], string> = {
  ready: 'Provider settings ready. No request has been sent.', saved: 'Saved provider settings.', removed: 'Key or profile removed; related requests cancelled.',
  'test-accepted': 'Metadata endpoint accepted the request. Model access, generation and capabilities remain unverified.', unauthorized: 'Provider rejected authentication. Replace the key or check account access.',
  'redirect-blocked': 'Provider redirect blocked. Configure the intended endpoint explicitly before entering a key.', cancelled: 'Key test cancelled.',
  'network-failed': 'Provider connection failed. Check endpoint, proxy or network and test again deliberately.', 'provider-rejected': 'Provider rejected the metadata request. Check endpoint and account access.',
  'key-unavailable': 'Key unavailable. Enter a replacement; protected storage may be unavailable on this account.', 'storage-failed': 'Settings or key could not be saved. Check local storage and refresh before retrying.',
  'stale-profile': 'This profile changed. Refresh settings before retrying.',
};
export function Providers() {
  const [reply, setReply] = useState<ProviderReply>();
  const [profile, setProfile] = useState<ProviderProfile>(empty);
  const [selected, setSelected] = useState('');
  const [notice, setNotice] = useState('Loading provider settings…');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false), [testing, setTesting] = useState(false);
  const generation = useRef(0), keyField = useRef<HTMLInputElement>(null);
  const row = reply?.profiles.find(p => p.profile.id === selected);
  const changed = Boolean(row && JSON.stringify(profile) !== JSON.stringify(row.profile));
  async function request(query: ProviderRequest) {
    const id = ++generation.current;
    const isTest = query.action === 'test-key';
    if (isTest) setTesting(true); else setBusy(true);
    setError(''); setNotice(isTest ? 'Testing metadata endpoint…' : 'Updating settings…');
    try {
      const next = await window.poliscope.provider(query);
      if (id !== generation.current) return;
      setReply(next); setNotice(messages[next.status]);
      if (query.action === 'list' && selected) {
        const fresh = next.profiles.find(p => p.profile.id === selected);
        if (fresh) setProfile(fresh.profile); else { setSelected(''); setProfile(empty()); }
      }
      if (query.action === 'save' && next.status === 'saved') {
        const saved = next.profiles.find(p => p.profile.id === query.profile.id)!;
        setSelected(saved.profile.id); setProfile(saved.profile);
      }
      if (query.action === 'delete' && next.status === 'removed') { setSelected(''); setProfile(empty()); }
    } catch { if (id === generation.current) setError('Provider settings unavailable. Check the endpoint and local storage, then refresh. No secret diagnostics are shown.'); }
    finally { if (isTest) setTesting(false); else setBusy(false); }
  }
  useEffect(() => { void request({ action: 'list' }); return () => { generation.current++; if (keyField.current) keyField.current.value = ''; }; }, []);
  function change(next: Partial<ProviderProfile>) { setProfile(p => ({ ...p, ...next })); }
  return <section aria-label="Provider settings" id="provider-settings" tabIndex={-1}>
    <h2>Assistant and provider settings</h2>
    <p>Optional BYOK settings. Offline society tools work without a provider. Key testing sends only a fixed metadata request to the saved endpoint; no society data or generation is sent.</p>
    <p role="status">{notice}</p>{error && <p role="alert">{error}</p>}
    <p>{reply?.protection === 'os-protected' ? 'OS-protected key storage available.' : 'Session-only keys: secure OS protection is unavailable. Keys will be forgotten when the app closes.'}</p>
    <button disabled={busy || testing} onClick={() => void request({ action: 'list' })}>Refresh provider settings</button>
    <label>Provider profile<select aria-label="Provider profile" disabled={busy || testing} value={selected} onChange={e => {
      const id = e.target.value; setSelected(id); setProfile(reply?.profiles.find(p => p.profile.id === id)?.profile ?? empty());
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
          {(['temperature', 'top_p'] as const).map(field => <label key={field}>{field.replaceAll('_', ' ')}<input maxLength={10} value={profile.generation[field] ?? ''} onChange={e => change({ generation: { ...profile.generation, [field]: e.target.value || null } })} /></label>)}
          <label>Maximum output tokens<input type="number" min={1} max={2147483647} value={profile.generation.max_output_tokens ?? ''} onChange={e => change({ generation: { ...profile.generation, max_output_tokens: e.target.value ? Number(e.target.value) : null } })} /></label>
        </details>
        <details><summary>Routing preferences</summary><p>Saved preferences only. Provider support will be checked before generation becomes available.</p>
          {(['order','only','ignore'] as const).map(field => <label key={field}>Provider {field} (comma-separated)<input maxLength={8192} value={profile.routing[field].join(', ')} onChange={e => change({ routing: { ...profile.routing, [field]: e.target.value.split(',').map(s => s.trim()).filter(Boolean) } })} /></label>)}
          <label><input type="checkbox" checked={profile.routing.allow_fallbacks} onChange={e => change({ routing: { ...profile.routing, allow_fallbacks: e.target.checked } })} />Allow model/provider fallbacks</label>
          <label><input type="checkbox" checked={profile.routing.require_parameters} onChange={e => change({ routing: { ...profile.routing, require_parameters: e.target.checked } })} />Require selected parameter support</label>
          <label>Data collection preference<select value={profile.routing.data_collection} onChange={e => change({ routing: { ...profile.routing, data_collection: e.target.value as ProviderProfile['routing']['data_collection'] } })}>{['unknown','allow','deny'].map(v => <option key={v}>{v}</option>)}</select></label>
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
      <button disabled={busy || testing || changed || row.key_status === 'missing'} onClick={() => void request({ action: 'test-key', profile_id: row.profile.id, expected_revision: row.revision })}>Test saved key</button>
      <button disabled={busy} onClick={() => void request({ action: 'remove-key', profile_id: row.profile.id, expected_revision: row.revision })}>Remove key and cancel requests</button>
      <button disabled={busy} onClick={() => void request({ action: 'delete', profile_id: row.profile.id, expected_revision: row.revision })}>Delete provider profile</button>
    </>}
    <p>Removing a key deletes active stored material and cancels requests. Filesystem backups or OS recovery may retain older encrypted data; secure erasure is not promised. Key testing does not make a paid generation request.</p>
  </section>;
}
