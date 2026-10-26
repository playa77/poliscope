import { it, expect, vi } from 'vitest';
import { mkdtemp, readFile, readdir, rm, writeFile, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createCipheriv, createDecipheriv, randomBytes } from 'node:crypto';
import { ProviderController, providerEndpoint, providerRequestValid, type Protection, type KeyTest } from '../../desktop/main/providers';
import type { ProviderProfile, ProviderReply } from '../../contracts/provider';
import { registerShellIPC, IPC_ERROR } from '../../desktop/main/ipc';
import type { DesktopShell } from '../../desktop/main/shell';
import type { IpcMainInvokeEvent } from 'electron';

const secret = 'synthetic-key-NEVER-RETURN-475918';
const profile = (id = 'first', endpoint = 'https://provider.example/v1'): ProviderProfile => ({ id, name: id, endpoint, kind: 'openai-compatible', model: 'future/model:variant',
  generation: { temperature: '0.7', top_p: null, max_output_tokens: 512 },
  routing: { order: ['future/provider'], only: [], ignore: [], allow_fallbacks: false, require_parameters: true, data_collection: 'deny' },
  capabilities: { text: 'unknown', image: 'unknown', audio: 'unknown', video: 'unknown', tools: 'unknown', structured_output: 'unknown', reasoning: 'unknown' } });
function protection(available = true, backend = 'gnome_libsecret'): Protection {
  const key = randomBytes(32);
  return { isEncryptionAvailable: () => available, getSelectedStorageBackend: () => backend,
    encryptString: vi.fn(value => { const iv = randomBytes(12), cipher = createCipheriv('aes-256-gcm', key, iv); return Buffer.concat([iv, cipher.update(value), cipher.final(), cipher.getAuthTag()]); }),
    decryptString: vi.fn(buffer => { const cipher = createDecipheriv('aes-256-gcm', key, buffer.subarray(0,12)); cipher.setAuthTag(buffer.subarray(-16)); return Buffer.concat([cipher.update(buffer.subarray(12,-16)), cipher.final()]).toString(); }) };
}
const revision = (reply: ProviderReply, id = 'first') => reply.profiles.find(p => p.profile.id === id)!.revision;
async function fixture(run: (dir: string) => Promise<void>) { const dir = await mkdtemp(join(tmpdir(), 'poliscope-provider-')); try { await run(dir); } finally { await rm(dir, { recursive: true, force: true }); } }
async function enter(controller: ProviderController, p = profile()) {
  const created = await controller.request({ action: 'save', profile: p, expected_revision: null });
  return controller.request({ action: 'replace-key', profile_id: p.id, expected_revision: revision(created, p.id), key: secret });
}

it('persists preferences separately from encrypted endpoint-bound keys; restarts without exposing blobs', () => fixture(async dir => {
  const os = protection(), send = vi.fn<KeyTest>().mockResolvedValue(200);
  const controller = new ProviderController(dir, os, send);
  const entered = await enter(controller);
  expect(entered.profiles[0].key_status).toBe('protected');
  const prefs = await readFile(join(dir, 'providers/profiles.json'), 'utf8');
  expect(prefs).not.toContain(secret); expect(prefs).toContain('credential-first');
  expect(prefs).toContain('future/model:variant');
  const blob = await readFile(join(dir, 'providers/credential-first.bin'));
  expect(blob.includes(Buffer.from(secret))).toBe(false);
  expect(JSON.stringify(entered)).not.toMatch(/credential-|NEVER-RETURN|binding|\.bin/);
  await controller.close();
  const cold = new ProviderController(dir, os, send);
  expect((await cold.request({ action: 'test-key', profile_id: 'first', expected_revision: revision(entered) })).status).toBe('test-accepted');
  expect(send).toHaveBeenCalledWith('https://provider.example/v1/models', secret, expect.any(AbortSignal));
  expect(os.decryptString).toHaveBeenCalledTimes(1);
  await cold.close();
}));

it.each([[false,'gnome_libsecret'],[true,'basic_text'],[true,'']])('uses memory only for unavailable protection %s/%s', (available, backend) => fixture(async dir => {
  const os = protection(available,backend), send = vi.fn<KeyTest>().mockResolvedValue(200);
  const controller = new ProviderController(dir, os, send);
  const saved = await enter(controller);
  expect(saved.protection).toBe('session-only'); expect(saved.profiles[0].key_status).toBe('session-only');
  expect(await readdir(join(dir,'providers'))).toEqual(['profiles.json']);
  expect(os.encryptString).not.toHaveBeenCalled(); expect(os.decryptString).not.toHaveBeenCalled();
  expect((await controller.request({ action: 'test-key', profile_id: 'first', expected_revision: revision(saved) })).status).toBe('test-accepted');
  await controller.close();
  const cold = new ProviderController(dir, os, send);
  expect((await cold.request({ action: 'list' })).profiles[0].key_status).toBe('missing');
  await cold.close();
}));

it('does not decrypt protected keys when OS protection becomes unavailable and permits deletion', () => fixture(async dir => {
  const os = protection(); const controller = new ProviderController(dir, os, vi.fn()); const saved = await enter(controller); await controller.close();
  os.isEncryptionAvailable = () => false;
  const cold = new ProviderController(dir, os, vi.fn());
  expect((await cold.request({ action: 'list' })).profiles[0].key_status).toBe('unavailable');
  expect((await cold.request({ action: 'test-key', profile_id: 'first', expected_revision: revision(saved) })).status).toBe('key-unavailable');
  expect(os.decryptString).not.toHaveBeenCalled();
  await cold.request({ action: 'remove-key', profile_id: 'first', expected_revision: revision(saved) });
  expect(await readdir(join(dir,'providers'))).toEqual(['profiles.json']); await cold.close();
}));

it('rejects unsafe endpoints and credential-bearing URLs before persistence', () => fixture(async dir => {
  const controller = new ProviderController(dir, protection(), vi.fn());
  for (const endpoint of ['http://remote.example/v1','https://user:pass@example.com/v1','file:///tmp/x','https://example.com/v1?api_key=x','https://example.com/#secret','https://example.com/a%2fb','https://example.com/\\evil']) {
    await expect(controller.request({ action: 'save', profile: profile('first',endpoint), expected_revision: null })).rejects.toThrow();
  }
  for (const endpoint of ['http://localhost:8000/v1/','http://127.0.0.1/v1','http://[::1]:8080/v1','https://example.com/v1']) expect(providerEndpoint(endpoint,'openai-compatible')).toBe(endpoint.replace(/\/+$/,''));
  expect(() => providerEndpoint('https://evil.example/api/v1','openrouter')).toThrow();
  expect(providerEndpoint('https://openrouter.ai/api/v1/','openrouter')).toBe('https://openrouter.ai/api/v1');
  expect((await controller.request({ action: 'list' })).profiles).toHaveLength(0); await controller.close();
}));

it('profile and endpoint switching cannot reuse a different bound credential', () => fixture(async dir => {
  const os = protection(), send = vi.fn<KeyTest>().mockResolvedValue(200), controller = new ProviderController(dir,os,send);
  let saved = await enter(controller);
  const next = await controller.request({ action: 'save', profile: profile('second','https://second.example/v1'), expected_revision: null });
  expect((await controller.request({ action: 'test-key', profile_id: 'second', expected_revision: revision(next,'second') })).status).toBe('key-unavailable');
  // Even a copied encrypted file cannot be used by another profile/endpoint.
  await writeFile(join(dir,'providers/credential-second.bin'), await readFile(join(dir,'providers/credential-first.bin')));
  expect((await controller.request({ action: 'test-key', profile_id: 'second', expected_revision: revision(next,'second') })).status).toBe('key-unavailable');
  saved = await controller.request({ action: 'save', profile: profile('first','https://changed.example/v1'), expected_revision: revision(saved) });
  expect(saved.profiles.find(p => p.profile.id==='first')?.key_status).toBe('missing');
  expect(send).not.toHaveBeenCalled(); await controller.close();
}));

it.each(['remove-key','replace-key','delete','endpoint','close'] as const)('%s cancels an in-flight test without waiting for transport', action => fixture(async dir => {
  let sent!: () => void; const started = new Promise<void>(r => { sent = r; }); let signal!: AbortSignal;
  const controller = new ProviderController(dir,protection(), (_url,_key,s) => { signal = s; sent(); return new Promise(() => {}); });
  const saved = await enter(controller);
  const pending = controller.request({ action: 'test-key', profile_id: 'first', expected_revision: revision(saved) }); await started;
  if (action === 'close') await controller.close();
  else if (action === 'endpoint') await controller.request({ action: 'save', profile: profile('first','https://new.example'), expected_revision: revision(saved) });
  else await controller.request({ action, profile_id: 'first', expected_revision: revision(saved), ...(action === 'replace-key' ? { key: 'synthetic-new-key' } : {}) });
  expect(signal.aborted).toBe(true); expect((await pending).status).toBe('cancelled'); await controller.close();
}));

it('stale revisions, corrupt blobs, backend failures and hostile errors never expose secrets', () => fixture(async dir => {
  const os = protection(), send = vi.fn<KeyTest>().mockRejectedValue(new Error('Authorization: Bearer '+secret));
  const controller = new ProviderController(dir,os,send); const saved = await enter(controller);
  const failure = await controller.request({ action: 'test-key', profile_id: 'first', expected_revision: revision(saved) });
  expect(failure.status).toBe('network-failed'); expect(JSON.stringify(failure)).not.toContain(secret);
  expect((await controller.request({ action: 'remove-key', profile_id: 'first', expected_revision: 1 })).status).toBe('stale-profile');
  await writeFile(join(dir,'providers/credential-first.bin'),'corrupt encrypted data');
  expect((await controller.request({ action: 'test-key', profile_id: 'first', expected_revision: revision(saved) })).status).toBe('key-unavailable');
  os.encryptString = () => { throw new Error(secret); };
  const failed = await controller.request({ action: 'replace-key', profile_id: 'first', expected_revision: revision(saved), key: secret });
  expect(failed.status).toBe('storage-failed'); expect(JSON.stringify(failed)).not.toContain(secret);
  await controller.close();
}));

it.each([[200,'test-accepted'],[401,'unauthorized'],[403,'unauthorized'],[302,'redirect-blocked'],[429,'provider-rejected'],[500,'provider-rejected']] as const)('maps HTTP %s without forwarding provider body or diagnostics', (code,status) => fixture(async dir => {
  const controller = new ProviderController(dir,protection(false), async () => code); const saved = await enter(controller);
  expect((await controller.request({ action: 'test-key', profile_id: 'first', expected_revision: revision(saved) })).status).toBe(status); await controller.close();
}));

it('fails closed on unknown/corrupt settings without overwriting them', () => fixture(async dir => {
  await mkdir(join(dir,'providers')); const path=join(dir,'providers/profiles.json'); await writeFile(path,'{"version":99,"profiles":[]}');
  const controller = new ProviderController(dir,protection(),vi.fn());
  await expect(controller.request({ action:'list' })).rejects.toThrow(); expect(await readFile(path,'utf8')).toContain('99'); await controller.close();
}));

it('schema and authenticated IPC reject extra paths, URL/method overrides, malformed keys and unauthorized senders', async () => {
  for (const input of [{action:'send',url:'https://evil.example'}, {action:'replace-key',profile_id:'../x',expected_revision:1,key:secret},
    {action:'replace-key',profile_id:'first',expected_revision:1,key:'x\r\nAuthorization: leak'}, {action:'test-key',profile_id:'first',expected_revision:1,url:'https://evil.example'}, {action:'list',path:'/tmp'}]) expect(providerRequestValid(input)).toBe(false);
  const handlers = new Map<string, (event:IpcMainInvokeEvent,...args:unknown[])=>Promise<unknown>>(); const request=vi.fn();
  const register = (authorize: () => void) => registerShellIPC((c,h)=>handlers.set(c,h),authorize,{} as DesktopShell,async()=>undefined,undefined,undefined,undefined,undefined,{request} as unknown as ProviderController);
  register(()=>{});
  await expect(handlers.get('provider:request')!({} as IpcMainInvokeEvent,{action:'list',key:secret})).rejects.toThrow(IPC_ERROR);
  register(()=>{throw new Error(secret);});
  await expect(handlers.get('provider:request')!({} as IpcMainInvokeEvent,{action:'list'})).rejects.toThrow(IPC_ERROR);
  expect(request).not.toHaveBeenCalled();
});

it('cleans only interrupted encrypted staging files before key removal', () => fixture(async dir => {
  const os=protection(), controller=new ProviderController(dir,os,vi.fn()); const saved=await enter(controller); await controller.close();
  const staged=join(dir,'providers/credential-first.bin.00000000-0000-4000-a000-000000000000.tmp');
  await writeFile(staged,await readFile(join(dir,'providers/credential-first.bin')));
  await writeFile(join(dir,'providers/unrelated.tmp'),'preserve');
  const cold=new ProviderController(dir,os,vi.fn());
  await cold.request({action:'remove-key',profile_id:'first',expected_revision:revision(saved)});
  expect((await readdir(join(dir,'providers'))).sort()).toEqual(['profiles.json','unrelated.tmp']); await cold.close();
}));

it('a failed vault deletion reports failure and cancels transport without pretending removal succeeded', () => fixture(async dir => {
  const controller=new ProviderController(dir,protection(),vi.fn());const saved=await enter(controller);
  await rm(join(dir,'providers/credential-first.bin'));await mkdir(join(dir,'providers/credential-first.bin'));
  const reply=await controller.request({action:'remove-key',profile_id:'first',expected_revision:revision(saved)});
  expect(reply.status).toBe('storage-failed');expect(JSON.stringify(reply)).not.toContain(secret);await controller.close();
}));

it('never writes a profile set larger than the bounded cold reader can reopen', () => fixture(async dir => {
  const os=protection(), controller=new ProviderController(dir,os,vi.fn());
  let failed=false, count=0;
  for(let i=0;i<64;i++) {
    const p=profile('large-'+i);p.routing.order=Array(32).fill('x'.repeat(256));p.routing.only=Array(16).fill('y'.repeat(256));
    const result=await controller.request({action:'save',profile:p,expected_revision:null});
    if(result.status==='storage-failed'){failed=true;break;}
    count++;
  }
  expect(failed).toBe(true);expect((await readFile(join(dir,'providers/profiles.json'))).length).toBeLessThanOrEqual(512*1024);
  await controller.close();const cold=new ProviderController(dir,os,vi.fn());
  expect((await cold.request({action:'list'})).profiles).toHaveLength(count);await cold.close();
}),30000);

it('cold-reopens explicit WP-044 controls without conflating provider and model fallback', () => fixture(async dir => {
  const p=profile(); p.kind='openrouter'; p.endpoint='https://openrouter.ai/api/v1';
  Object.assign(p.routing,{model_fallbacks:['future/alternate:free'],zdr:true,sort:'price',max_price:{prompt:'1.25',completion:'0'}});
  Object.assign(p.generation,{frequency_penalty:'-1.5',presence_penalty:'0.1',seed:0,stop:['END'],reasoning:{effort:'low',exclude:true}});
  const controller=new ProviderController(dir,protection(false),vi.fn());
  const saved=await controller.request({action:'save',profile:p,expected_revision:null}); await controller.close();
  const cold=new ProviderController(dir,protection(false),vi.fn());
  const reply=await cold.request({action:'list'}); expect(reply.profiles[0].profile).toEqual(p);
  expect(reply.profiles[0].revision).toBe(saved.profiles[0].revision);
  expect(reply.profiles[0].profile.routing.allow_fallbacks).toBe(false);
  expect(reply.profiles[0].profile.routing.model_fallbacks).toEqual(['future/alternate:free']); await cold.close();
}));
