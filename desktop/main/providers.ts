import { mediaTokenBound } from './assistant-content';
import type { GenerationPlan } from '../../contracts/generation';
import { buildGenerationRequest, contextPayloadHash, type BuiltRequest } from './provider-requests';
import { adapterFor, metadataCode, CATALOG_TTL, type MetadataTransport } from './provider-adapters';
import type { MetadataAction, ModelMetadata, CatalogPage, EndpointMetadata } from '../../contracts/provider';
/** Main-only settings, credential vault and fixed, non-billable key tests. */
import { mkdir, open, readFile, rename, unlink, stat, readdir } from 'node:fs/promises';
import { join, isAbsolute } from 'node:path';
import { randomUUID } from 'node:crypto';
import type { ProviderProfile, ProviderReply, ProviderView, ProviderList, ProviderSave, ProviderKeyAction, ProviderReplaceKey } from '../../contracts/provider';
import schema from '../../contracts/provider.schema.json';
import { valid, type Schema } from './wire';
export type ProviderRequest = ProviderList | ProviderSave | ProviderKeyAction | ProviderReplaceKey | MetadataAction;
const defs = schema.$defs as Record<string, Schema>;
export const providerValid = (input: unknown, type: string) => valid(input, defs[type], defs);
export function providerRequestValid(input: unknown): input is ProviderRequest {
  return ['ProviderList', 'ProviderSave', 'ProviderKeyAction', 'ProviderReplaceKey', 'MetadataAction'].some(t => providerValid(input, t));
}
export interface Protection {
  isEncryptionAvailable(): boolean;
  getSelectedStorageBackend?(): string;
  encryptString(value: string): Buffer;
  decryptString(value: Buffer): string;
}
export type KeyTest = (url: string, key: string, signal: AbortSignal) => Promise<number>;
type Row = { profile: ProviderProfile; revision: number; key_ref: string };
type Status = ProviderReply['status'];
const MAX_FILE = 512 * 1024;

/** Canonical endpoint identity is part of the credential binding. No URL secrets. */
export function providerEndpoint(value: string, kind: ProviderProfile['kind']): string {
  const url = new URL(value);
  const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  if (url.username || url.password || url.search || url.hash || /[\s\\]/.test(value)
      || (url.protocol !== 'https:' && !(url.protocol === 'http:' && loopback))) throw new Error('Invalid provider endpoint');
  // OpenRouter is an endpoint identity, not an arbitrary compatible base URL.
  if (kind === 'openrouter' && url.href.replace(/\/+$/, '') !== 'https://openrouter.ai/api/v1') throw new Error('Invalid OpenRouter endpoint');
  // Avoid surprising URL path normalization when appending fixed metadata routes.
  if (/%(?:2f|5c|2e)/i.test(url.pathname)) throw new Error('Invalid provider path');
  url.pathname = url.pathname.replace(/\/+$/, '');
  return url.href.replace(/\/+$/, '');
}
async function boundedRead(path: string, maximum = MAX_FILE): Promise<Buffer> {
  const handle = await open(path, 'r');
  try {
    if ((await handle.stat()).size > maximum) throw new Error('Settings too large');
    const buffer = Buffer.alloc(maximum + 1);
    let offset = 0;
    while (offset < buffer.length) {
      const { bytesRead } = await handle.read(buffer, offset, buffer.length - offset, null);
      if (!bytesRead) break;
      offset += bytesRead;
    }
    if (offset > maximum) throw new Error('Settings too large');
    return buffer.subarray(0, offset);
  } finally { await handle.close(); }
}
async function atomicWrite(path: string, data: string | Buffer): Promise<void> {
  const temporary = path + '.' + randomUUID() + '.tmp';
  const handle = await open(temporary, 'wx', 0o600);
  try {
    await handle.writeFile(data); await handle.sync(); await handle.close();
    await rename(temporary, path);
  } catch {
    await handle.close().catch(() => {}); await unlink(temporary).catch(() => {});
    throw new Error('Provider settings save failed');
  }
}
const missing = (error: unknown) => (error as NodeJS.ErrnoException).code === 'ENOENT';
export class ProviderController {
  private rows: Row[] = [];
  private sessions = new Map<string, { binding: string; key: string }>();
  private tests = new Map<string, AbortController>();
  private generations = new Map<string, Set<AbortController>>();
  private tail: Promise<unknown> = Promise.resolve();
  private queued = 0;
  private loaded = false;
  private closed = false;
  private directory: string;
  private metadataCache = new Map<string, CatalogCache>();
  constructor(directory: string, private protection: Protection, private test: KeyTest, private platform = process.platform, private metadata?: MetadataTransport) {
    if (!isAbsolute(directory)) throw new Error('Invalid provider store');
    // App userData only, outside every selected civilization/archive store.
    this.directory = join(directory, 'providers');
  }
  private secure(): boolean {
    try { return this.protection.isEncryptionAvailable() && (this.platform !== 'linux' || this.protection.getSelectedStorageBackend?.() !== 'basic_text')
      && (this.platform !== 'linux' || Boolean(this.protection.getSelectedStorageBackend?.())); } catch { return false; }
  }
  private keyPath(row: Row) { return join(this.directory, row.key_ref + '.bin'); }
  private binding(row: Row) { return JSON.stringify([row.profile.id, row.profile.kind, row.profile.endpoint]); }
  private cancel(id: string) { for (const active of this.generations.get(id) ?? []) active.abort(); this.tests.get(id)?.abort(); this.tests.delete(id); }
  private serialize<T>(action: () => Promise<T>): Promise<T> {
    if (this.closed || this.queued >= 32) return Promise.reject(new Error('Provider service unavailable'));
    this.queued++;
    const pending = this.tail.then(action).finally(() => { this.queued--; });
    this.tail = pending.catch(() => {}); return pending;
  }
  private async load() {
    if (this.loaded) return;
    await mkdir(this.directory, { recursive: true, mode: 0o700 });
    // A killed exclusive write can leave encrypted staging material. There is
    // one application owner; discard only our exact interrupted-key filename.
    for (const name of await readdir(this.directory)) {
      if (/^credential-[a-zA-Z0-9_-]{1,64}\.bin\.[0-9a-f-]{36}\.tmp$/.test(name)) {
        await unlink(join(this.directory, name));
      }
    }
    let raw;
    try { raw = await boundedRead(join(this.directory, 'profiles.json')); }
    catch (error) { if (!missing(error)) throw error; this.loaded = true; return; }
    const data = JSON.parse(raw.toString('utf8'));
    if (!data || Object.keys(data).sort().join() !== 'profiles,version' || data.version !== 1 || !Array.isArray(data.profiles) || data.profiles.length > 64) throw new Error('Invalid provider settings');
    const ids = new Set<string>();
    for (const row of data.profiles) {
      if (!row || Object.keys(row).sort().join() !== 'key_ref,profile,revision' || !providerValid(row.profile, 'ProviderProfile')
          || !Number.isSafeInteger(row.revision) || row.revision < 1 || ids.has(row.profile.id)
          || row.key_ref !== 'credential-' + row.profile.id || providerEndpoint(row.profile.endpoint, row.profile.kind) !== row.profile.endpoint) throw new Error('Invalid provider settings');
      ids.add(row.profile.id);
    }
    this.rows = data.profiles; this.loaded = true;
  }
  private async persist(rows: Row[]) {
    const encoded = JSON.stringify({ version: 1, profiles: rows });
    if (Buffer.byteLength(encoded) > MAX_FILE) throw new Error('Provider settings capacity exceeded');
    await atomicWrite(join(this.directory, 'profiles.json'), encoded);
    this.rows = rows;
  }
  private async erase(row: Row) {
    this.cancel(row.profile.id); this.sessions.delete(row.profile.id);
    try { await unlink(this.keyPath(row)); } catch (error) { if (!missing(error)) throw error; }
  }
  private async snapshot(status: Status): Promise<ProviderReply> {
    const secure = this.secure();
    const profiles: ProviderView[] = [];
    for (const row of this.rows) {
      let key_status: ProviderView['key_status'] = this.sessions.has(row.profile.id) ? 'session-only' : 'missing';
      if (key_status === 'missing') {
        try { await stat(this.keyPath(row)); key_status = secure ? 'protected' : 'unavailable'; }
        catch (error) { if (!missing(error)) key_status = 'unavailable'; }
      }
      profiles.push({ profile: structuredClone(row.profile), revision: row.revision, key_status });
    }
    return { provider_contract: 1, profiles, protection: secure ? 'os-protected' : 'session-only', status };
  }
  private async secret(row: Row): Promise<string | undefined> {
    const binding = this.binding(row), session = this.sessions.get(row.profile.id);
    if (session) return session.binding === binding ? session.key : undefined;
    if (!this.secure()) return undefined;
    try {
      const saved = JSON.parse(this.protection.decryptString(await boundedRead(this.keyPath(row))));
      if (Object.keys(saved).sort().join() !== 'binding,key' || saved.binding !== binding || typeof saved.key !== 'string'
          || !/^[!-~]{1,4096}$/.test(saved.key)) return undefined;
      return saved.key;
    } catch { return undefined; }
  }
  private async runTest(row: Row, key: string): Promise<Status> {
    this.cancel(row.profile.id);
    if (this.tests.size >= 8) return 'network-failed';
    const controller = new AbortController(); this.tests.set(row.profile.id, controller);
    const timer = setTimeout(() => controller.abort(), 10_000);
    const aborted = new Promise<never>((_, reject) => controller.signal.addEventListener('abort', () => reject(new Error('Cancelled')), { once: true }));
    try {
      const route = row.profile.kind === 'openrouter' ? '/key' : '/models';
      const code = await Promise.race([this.test(row.profile.endpoint + route, key, controller.signal), aborted]);
      if (controller.signal.aborted || this.closed) return 'cancelled';
      if (code >= 300 && code < 400) return 'redirect-blocked';
      if (code === 401 || code === 403) return 'unauthorized';
      return code >= 200 && code < 300 ? 'test-accepted' : 'provider-rejected';
    } catch { return controller.signal.aborted ? 'cancelled' : 'network-failed'; }
    finally { clearTimeout(timer); if (this.tests.get(row.profile.id) === controller) this.tests.delete(row.profile.id); }
  }
  async request(input: unknown): Promise<ProviderReply> {
    if (!providerRequestValid(input) || Buffer.byteLength(JSON.stringify(input)) > 16_384) throw new Error('Invalid provider request');
    // No key-bearing request is retained on this controller or in a retry queue.
    const query = structuredClone(input);
    if (query.action === 'catalog' || query.action === 'refresh-catalog' || query.action === 'model-endpoints' || query.action === 'key-status') return this.metadataRequest(query);
    const prepared = await this.serialize(async (): Promise<{ reply?: ProviderReply; testing?: Promise<Status> }> => {
      await this.load();
      if (this.closed) throw new Error('Provider service stopped');
      if (query.action === 'list') return { reply: await this.snapshot('ready') };
      const id = query.action === 'save' ? query.profile.id : query.profile_id;
      const row = this.rows.find(r => r.profile.id === id);
      if ((row?.revision ?? null) !== query.expected_revision) return { reply: await this.snapshot('stale-profile') };
      if (query.action === 'save') {
        if (!row && this.rows.length >= 64) throw new Error('Profile limit');
        const profile = structuredClone(query.profile);
        profile.endpoint = providerEndpoint(profile.endpoint, profile.kind);
        if (row && row.revision >= Number.MAX_SAFE_INTEGER) throw new Error('Profile revision limit');
        if (row) {
          this.cancel(id);
          if (row.profile.endpoint !== profile.endpoint || row.profile.kind !== profile.kind) {
            await this.erase(row); this.metadataCache.delete(id);
            await unlink(this.cachePath(id)).catch(error => { if (!missing(error)) throw error; });
          }
        }
        const updated = { profile, revision: (row?.revision ?? 0) + 1, key_ref: 'credential-' + id };
        try { await this.persist([...this.rows.filter(r => r !== row), updated]); }
        catch { return { reply: await this.snapshot('storage-failed') }; }
        return { reply: await this.snapshot('saved') };
      }
      if (!row) return { reply: await this.snapshot('stale-profile') };
      if (query.action === 'test-key') {
        // Register transport before releasing mutation ordering, then wait outside
        // the queue so removal/replacement/shutdown can cancel in-flight work.
        const key = await this.secret(row);
        if (!key) return { reply: await this.snapshot('key-unavailable') };
        return { testing: this.runTest(row, key) };
      }
      if (row.revision >= Number.MAX_SAFE_INTEGER) throw new Error('Profile revision limit');
      try {
        await this.erase(row);
        if (query.action === 'delete') { await this.persist(this.rows.filter(r => r !== row)); this.metadataCache.delete(id); await unlink(this.cachePath(id)).catch(error => { if (!missing(error)) throw error; }); }
        else if (query.action === 'replace-key') {
          if (this.closed) throw new Error('Provider stopped');
          if (this.secure()) {
            const encrypted = this.protection.encryptString(JSON.stringify({ binding: this.binding(row), key: query.key }));
            await atomicWrite(this.keyPath(row), encrypted);
          } else this.sessions.set(id, { binding: this.binding(row), key: query.key });
        }
        if (query.action !== 'delete') await this.persist(this.rows.map(r => r === row ? { ...r, revision: r.revision + 1 } : r));
      } catch { return { reply: await this.snapshot('storage-failed') }; }
      finally { if (query.action === 'replace-key') query.key = ''; }
      return { reply: await this.snapshot(query.action === 'replace-key' ? 'saved' : 'removed') };
    });
    if (prepared.reply) return prepared.reply;
    const result = await prepared.testing!;
    // Shutdown may have closed the queue; no snapshot or key material escapes.
    if (this.closed) return { provider_contract: 1, profiles: [], protection: 'session-only', status: 'cancelled' };
    return this.serialize(() => this.snapshot(result));
  }
  private cachePath(id: string) { return join(this.directory, 'catalog-' + id + '.json'); }
  private async cache(row: Row): Promise<CatalogCache> {
    const existing = this.metadataCache.get(row.profile.id);
    if (existing?.binding === this.binding(row)) return existing;
    let cached: CatalogCache = { version:1, binding:this.binding(row), fetched_at:null, models:[], endpoints:{} };
    try {
      const parsed = JSON.parse((await boundedRead(this.cachePath(row.profile.id), 8 * 1024 * 1024)).toString('utf8'));
      if (parsed.version !== 1 || parsed.binding !== cached.binding || !Array.isArray(parsed.models) || parsed.models.length > 10000
          || !(parsed.fetched_at === null || validTime(parsed.fetched_at)) || !parsed.endpoints || typeof parsed.endpoints !== 'object' || Array.isArray(parsed.endpoints)
          || Object.keys(parsed.endpoints).length > 32 || !parsed.models.every((m: unknown) => providerValid(m, 'ModelMetadata'))
          || !Object.values(parsed.endpoints).every(e => providerValid(e, 'EndpointMetadata'))) throw new Error('Invalid cache');
      cached = parsed;
    } catch { /* Disposable metadata is never accepted-result evidence. */ }
    this.metadataCache.set(row.profile.id, cached); return cached;
  }
  private page(row: Row, cached: CatalogCache, query: MetadataAction, fresh = false): CatalogPage {
    const search = (query.search ?? '').toLowerCase();
    const models = cached.models.filter(m => (m.id + ' ' + m.name).toLowerCase().includes(search));
    return { profile_id:row.profile.id, endpoint:row.profile.endpoint, fetched_at:cached.fetched_at,
      state:cached.fetched_at === null ? 'empty' : Date.now() - Date.parse(cached.fetched_at) >= CATALOG_TTL ? 'stale' : fresh ? 'fresh' : 'cached',
      total:models.length, offset:query.offset ?? 0, models:models.slice(query.offset ?? 0, (query.offset ?? 0) + 5) };
  }
  private async metadataRequest(query: MetadataAction): Promise<ProviderReply> {
    const prepared = await this.serialize(async () => {
      await this.load();
      const row = this.rows.find(r => r.profile.id === query.profile_id);
      if (!row || row.revision !== query.expected_revision) return { reply:await this.snapshot('stale-profile') };
      const cache = await this.cache(row);
      if (query.action === 'catalog') return { reply:{ ...await this.snapshot('metadata-ready'), catalog:this.page(row, cache, query), endpoints:Object.hasOwn(cache.endpoints, query.model_id ?? '') ? cache.endpoints[query.model_id ?? ''] : null } };
      const adapter = adapterFor(row.profile.kind);
      const route = query.action === 'refresh-catalog' ? '/models' : query.action === 'key-status' ? row.profile.kind === 'openrouter' ? '/key' : undefined : adapter.endpointRoute(query.model_id ?? '');
      if (!route || !this.metadata) return { reply:await this.snapshot('metadata-unsupported') };
      const key = await this.secret(row);
      if (!key) return { reply:await this.snapshot('key-unavailable') };
      this.cancel(row.profile.id);
      if (this.tests.size >= 8) return { reply:await this.snapshot('network-failed') };
      const controller = new AbortController(); this.tests.set(row.profile.id, controller);
      // Start under mutation ordering, await outside it so removal cancels.
      const pending = this.fetchMetadata(row.profile.endpoint + route, key, controller);
      return { row, cache, adapter, controller, pending };
    });
    if (prepared.reply) return prepared.reply;
    const { row, cache, adapter, controller } = prepared;
    const result = await prepared.pending!;
    if (this.closed) return { provider_contract:1, profiles:[], protection:'session-only', status:'cancelled' };
    return this.serialize(async () => {
      const current = this.rows.find(r => r.profile.id === row!.profile.id);
      if (controller!.signal.aborted || current !== row || this.tests.get(row!.profile.id) !== controller) {
        if (this.tests.get(row!.profile.id) === controller) this.tests.delete(row!.profile.id);
        return this.snapshot('cancelled');
      }
      this.tests.delete(row!.profile.id);
      if (!result) return { ...await this.snapshot('network-failed'), catalog:this.page(row!, cache!, query) };
      const status = metadataCode(result.code);
      if (status !== 'metadata-ready') return { ...await this.snapshot(status), catalog:this.page(row!, cache!, query) };
      let next = structuredClone(cache!);
      const observed = new Date().toISOString();
      let endpoints: EndpointMetadata | null = null;
      try {
        if (query.action === 'key-status') return { ...await this.snapshot(status), key_metadata:adapter!.key(result.data, observed) };
        if (query.action === 'refresh-catalog') {
          const models = adapter!.models(result.data, observed), ids = new Set(models.map(m => m.id));
          if (!models.every(model => providerValid(model, 'ModelMetadata'))) throw new Error('Invalid normalized metadata');
          next.models = [...models, ...next.models.filter(m => !ids.has(m.id)).map(m => ({ ...m, available:false }))];
          if (next.models.length > 10000) throw new Error('Catalog history capacity');
          next.fetched_at = observed;
        } else {
          endpoints = adapter!.endpoints(result.data, query.model_id ?? '', observed);
          if (!providerValid(endpoints, 'EndpointMetadata')) throw new Error('Invalid normalized metadata');
          // Bounded endpoint cache; expired entries can be refreshed deliberately.
          const entries = Object.entries(next.endpoints).filter(([id]) => id !== query.model_id).slice(-31);
          next.endpoints = Object.fromEntries([...entries, [query.model_id ?? '', endpoints]]);
        }
        const encoded = JSON.stringify(next);
        if (Buffer.byteLength(encoded) > 8 * 1024 * 1024) throw new Error('Catalog capacity');
      } catch { return { ...await this.snapshot('metadata-invalid'), catalog:this.page(row!, cache!, query) }; }
      try { await atomicWrite(this.cachePath(row!.profile.id), JSON.stringify(next)); }
      catch { return { ...await this.snapshot('storage-failed'), catalog:this.page(row!, cache!, query) }; }
      for(const active of this.generations.get(row!.profile.id) ?? [])active.abort();
      this.metadataCache.set(row!.profile.id, next);
      return { ...await this.snapshot(status), catalog:this.page(row!, next, query, true), endpoints };
    });
  }
  private async fetchMetadata(url: string, key: string, controller: AbortController): Promise<{ code:number; data:unknown } | undefined> {
    const timer = setTimeout(() => controller.abort(), 15000);
    const aborted = new Promise<never>((_, reject) => controller.signal.addEventListener('abort', () => reject(new Error('Cancelled')), { once:true }));
    try {
      const response = await Promise.race([this.metadata!(url, key, controller.signal), aborted]);
      if (response.code < 200 || response.code >= 300) return { code:response.code, data:null };
      if (Buffer.byteLength(response.body) > 8 * 1024 * 1024) return { code:200, data:null };
      let data: unknown;
      try { data = JSON.parse(response.body); } catch { return { code:200, data:null }; }
      // Reject credential echoes, including escaped JSON strings, before either
      // raw forward-compatible model fields or allowlisted account fields escape.
      if (JSON.stringify(data).includes(JSON.stringify(key).slice(1,-1))) return { code:200, data:null };
      return { code:response.code, data };
    } catch { return undefined; }
    finally { clearTimeout(timer); }
  }
  /** Main-owned, conservative GPT byte-BPE bound, never a renderer receipt.
   * Unknown tokenizer/compatible catalog entries remain blocked. Full tokenizer
   * negotiation remains explicit; tools/history include serialized bytes plus a
   * framing reserve per message/tool. No renderer can provide a budget receipt.
   */
  private async build(row: Row, plan: GenerationPlan): Promise<BuiltRequest> {
    const cache=await this.cache(row);
    const ids=[row.profile.model,...(row.profile.routing.model_fallbacks ?? [])];
    const budgets=ids.flatMap(id=> {
      const model=cache.models.find(m=>m.id===id);
      let raw: {architecture?:{tokenizer?:string}}={};
      try {raw=JSON.parse(model?.raw_json ?? '{}');} catch {return [];}
      // GPT byte-level BPE has a base token for each UTF-8 byte; merges only
      // reduce counts. Count every serialized message, call ID/argument, tool
      // description/schema and role, with 1024 reserved per framing unit. The
      // escaped JSON byte count intentionally overestimates ordinary content.
      if(raw.architecture?.tokenizer!=='GPT' || plan.response_format.type!=='text')return [];
      let media:number;try{media=mediaTokenBound(plan.messages,id);}catch{return [];}
      const framing=1024*(plan.messages.length+(plan.tools??[]).length+1);
      const bytes=Buffer.byteLength(JSON.stringify({messages:plan.messages,tools:plan.tools??[]}));
      return [{model_id:id,input_tokens_upper_bound:bytes+framing+media,payload_sha256:contextPayloadHash(plan),source:'conservative-model-bound' as const}];
    });
    return buildGenerationRequest({profile:row.profile,revision:row.revision,key_status:'missing'},plan,{profile_id:row.profile.id,revision:row.revision,endpoint:row.profile.endpoint,models:cache.models,endpoints:Object.values(cache.endpoints),budgets});
  }
  async prepareGeneration(plan: GenerationPlan): Promise<BuiltRequest> {
    return this.serialize(async()=> {
      await this.load();
      const row=this.rows.find(r=>r.profile.id===plan.profile_id);
      if(!row || row.revision!==plan.expected_revision)throw new Error('Provider configuration changed');
      return this.build(row,plan);
    });
  }
  /** Revalidate before acquiring a credential; key removal cancels this lease. */
  async dispatchGeneration<T>(request: BuiltRequest, signal: AbortSignal, send:(key:string,signal:AbortSignal)=>Promise<T>):Promise<T> {
    const prepared=await this.serialize(async()=> {
      await this.load();
      const row=this.rows.find(r=>r.profile.id===request.profile_id);
      if(!row || signal.aborted || this.closed || row.revision!==request.revision)throw new Error('Provider configuration changed');
      const current=await this.build(row,request.plan);
      if(current.json!==request.json)throw new Error('Provider configuration changed');
      const key=await this.secret(row);if(!key)throw new Error('Provider key unavailable');
      const controller=new AbortController();
      const abort=()=>controller.abort();signal.addEventListener('abort',abort,{once:true});
      if(signal.aborted)controller.abort();
      const active=this.generations.get(row.profile.id) ?? new Set<AbortController>();
      active.add(controller);this.generations.set(row.profile.id,active);
      return {key,controller,active,abort};
    });
    try {
      if(prepared.controller.signal.aborted)throw new Error('Provider cancelled');
      return await send(prepared.key,prepared.controller.signal);
    } finally {signal.removeEventListener('abort',prepared.abort);prepared.active.delete(prepared.controller);}
  }
  async close() {
    this.closed = true;
    for (const group of this.generations.values()) for (const active of group) active.abort();
    this.generations.clear();
    for (const test of this.tests.values()) test.abort();
    this.tests.clear(); this.sessions.clear();
    let timer: ReturnType<typeof setTimeout> | undefined;
    try { await Promise.race([this.tail, new Promise<void>(resolve => { timer = setTimeout(resolve, 1500); })]); }
    finally { clearTimeout(timer); this.sessions.clear(); }
  }
}

type CatalogCache = { version:1; binding:string; fetched_at:string | null; models:ModelMetadata[]; endpoints:Record<string, EndpointMetadata> };
const validTime = (value: unknown): value is string => typeof value === 'string' && value.length <= 256 && Number.isFinite(Date.parse(value));
