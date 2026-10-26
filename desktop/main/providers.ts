/** Main-only settings, credential vault and fixed, non-billable key tests. */
import { mkdir, open, readFile, rename, unlink, stat, readdir } from 'node:fs/promises';
import { join, isAbsolute } from 'node:path';
import { randomUUID } from 'node:crypto';
import type { ProviderProfile, ProviderReply, ProviderView, ProviderList, ProviderSave, ProviderKeyAction, ProviderReplaceKey } from '../../contracts/provider';
import schema from '../../contracts/provider.schema.json';
import { valid, type Schema } from './wire';
export type ProviderRequest = ProviderList | ProviderSave | ProviderKeyAction | ProviderReplaceKey;
const defs = schema.$defs as Record<string, Schema>;
export const providerValid = (input: unknown, type: string) => valid(input, defs[type], defs);
export function providerRequestValid(input: unknown): input is ProviderRequest {
  return ['ProviderList', 'ProviderSave', 'ProviderKeyAction', 'ProviderReplaceKey'].some(t => providerValid(input, t));
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
async function boundedRead(path: string): Promise<Buffer> {
  const handle = await open(path, 'r');
  try {
    if ((await handle.stat()).size > MAX_FILE) throw new Error('Settings too large');
    const buffer = Buffer.alloc(MAX_FILE + 1);
    let offset = 0;
    while (offset < buffer.length) {
      const { bytesRead } = await handle.read(buffer, offset, buffer.length - offset, null);
      if (!bytesRead) break;
      offset += bytesRead;
    }
    if (offset > MAX_FILE) throw new Error('Settings too large');
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
  private tail: Promise<unknown> = Promise.resolve();
  private queued = 0;
  private loaded = false;
  private closed = false;
  private directory: string;
  constructor(directory: string, private protection: Protection, private test: KeyTest, private platform = process.platform) {
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
  private cancel(id: string) { this.tests.get(id)?.abort(); this.tests.delete(id); }
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
          if (row.profile.endpoint !== profile.endpoint || row.profile.kind !== profile.kind) await this.erase(row);
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
        if (query.action === 'delete') await this.persist(this.rows.filter(r => r !== row));
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
  async close() {
    this.closed = true;
    for (const test of this.tests.values()) test.abort();
    this.tests.clear(); this.sessions.clear();
    let timer: ReturnType<typeof setTimeout> | undefined;
    try { await Promise.race([this.tail, new Promise<void>(resolve => { timer = setTimeout(resolve, 1500); })]); }
    finally { clearTimeout(timer); this.sessions.clear(); }
  }
}
