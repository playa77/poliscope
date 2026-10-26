import { it, expect, vi } from 'vitest';
import { mkdtemp, readFile, writeFile, rm, rename, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { ProviderController, providerValid } from '../../desktop/main/providers';
import type { ProviderProfile } from '../../contracts/provider';
import type { MetadataTransport } from '../../desktop/main/provider-adapters';
import fixture from '../fixtures/providers/openrouter-models.json';
const key='synthetic-KEY-WP043-DO-NOT-RETURN';
const profile: ProviderProfile={id:'catalog',name:'Catalog',kind:'openrouter',endpoint:'https://openrouter.ai/api/v1',model:'future/vendor-model:preview',generation:{temperature:null,top_p:null,max_output_tokens:null},routing:{order:[],only:[],ignore:[],allow_fallbacks:false,require_parameters:true,data_collection:'unknown'},capabilities:{text:'unknown',image:'unknown',audio:'unknown',video:'unknown',tools:'unknown',structured_output:'unknown',reasoning:'unknown'}};
async function setup(run:(dir:string,controller:ProviderController,send:ReturnType<typeof vi.fn<MetadataTransport>>)=>Promise<void>){
  const dir=await mkdtemp(join(tmpdir(),'poliscope-catalog-'));
  const send=vi.fn<MetadataTransport>().mockResolvedValue({code:200,body:JSON.stringify(fixture)});
  const controller=new ProviderController(dir,{isEncryptionAvailable:()=>false,encryptString:()=>{throw Error();},decryptString:()=>{throw Error();}},async()=>200,process.platform,send);
  try {await controller.request({action:'save',profile,expected_revision:null});await controller.request({action:'replace-key',profile_id:profile.id,expected_revision:1,key});await run(dir,controller,send);}
  finally {await controller.close();await rm(dir,{recursive:true,force:true});}
}
const query=(action='refresh-catalog',extra={})=>({action,profile_id:'catalog',expected_revision:2,...extra});
it('fetches only main-owned routes; search variants, preserve removed IDs and cold offline cache with unknown fields',()=>setup(async(dir,c,send)=>{
  let reply=await c.request(query());expect(reply.status).toBe('metadata-ready');expect(providerValid(reply,'ProviderReply')).toBe(true);expect(reply.catalog?.state).toBe('fresh');
  expect(send).toHaveBeenCalledWith('https://openrouter.ai/api/v1/models',key,expect.any(AbortSignal));
  reply=await c.request(query('catalog',{search:':free'}));expect(reply.catalog?.total).toBe(1);expect(reply.catalog?.models[0].id).toBe('future/vendor-model:free');expect(send).toHaveBeenCalledTimes(1);
  send.mockResolvedValue({code:200,body:JSON.stringify({data:[{id:'unknown/new',future_changed:'retained'}]})});reply=await c.request(query());
  expect(reply.catalog?.models.find(m=>m.id==='future/vendor-model:preview')?.available).toBe(false);
  expect(reply.profiles[0].profile.model).toBe('future/vendor-model:preview');
  expect(JSON.parse(reply.catalog!.models[0].raw_json).future_changed).toBe('retained');
  await c.close();
  const cold=new ProviderController(dir,{isEncryptionAvailable:()=>false,encryptString:()=>Buffer.alloc(0),decryptString:()=>''},async()=>200);
  const offline=await cold.request(query('catalog'));expect(offline.catalog?.state).toBe('cached');expect(offline.catalog?.models).toEqual(reply.catalog?.models);expect(offline.profiles[0].key_status).toBe('missing');await cold.close();
  expect(await readFile(join(dir,'providers/catalog-catalog.json'),'utf8')).not.toContain(key);
}));
it('keeps prior cache on malformed, oversized, credential-echo and provider errors with explicit safe statuses',()=>setup(async(_dir,c,send)=>{
  const accepted=await c.request(query());
  for(const [code,body,status] of [[200,'not JSON','metadata-invalid'],[200,JSON.stringify({data:[{id:'echo',secret:key}]}),'metadata-invalid'],[200,'a'.repeat(8*1024*1024+1),'metadata-invalid'],[401,key,'unauthorized'],[429,key,'rate-limited'],[402,key,'credits-required'],[302,key,'redirect-blocked']] as const){
    send.mockResolvedValue({code,body});const reply=await c.request(query());expect(reply.status).toBe(status);expect(reply.catalog?.models).toEqual(accepted.catalog?.models);expect(JSON.stringify(reply)).not.toContain(key);
  }
  send.mockRejectedValue(new Error('Authorization Bearer '+key));expect((await c.request(query())).status).toBe('network-failed');
}));
it('never persists account data; model provider metadata uses encoded fixed routes, generic endpoints stay unknown',()=>setup(async(dir,c,send)=>{
  send.mockResolvedValue({code:200,body:JSON.stringify({data:{limit:null,limit_remaining:0,usage:2,label:'secret-fragment',organization_id:'private'}})});
  const reply=await c.request(query('key-status'));expect(reply.key_metadata?.limit_remaining).toBe('0');expect(JSON.stringify(reply)).not.toMatch(/secret-fragment|organization_id/);
  await expect(readFile(join(dir,'providers/catalog-catalog.json'))).rejects.toThrow();
  send.mockResolvedValue({code:200,body:JSON.stringify({data:{id:profile.model,endpoints:[{provider_name:'Example',supported_parameters:['tools']}]}})});
  const endpoints=await c.request(query('model-endpoints',{model_id:profile.model}));expect(providerValid(endpoints,'ProviderReply')).toBe(true);expect(endpoints.endpoints?.providers[0].capabilities.tools).toBe('supported');
  expect(send.mock.calls.at(-1)?.[0]).toBe('https://openrouter.ai/api/v1/models/future/vendor-model%3Apreview/endpoints');
  await c.request({action:'save',profile:{...profile,kind:'openai-compatible',endpoint:'https://compatible.example/v1'},expected_revision:2});
  expect((await c.request(query('catalog',{expected_revision:3}))).catalog?.state).toBe('empty');
  expect((await c.request(query('key-status',{expected_revision:3}))).status).toBe('metadata-unsupported');expect(send).toHaveBeenCalledTimes(2);
}));
it.each(['remove-key','replace-key','delete','save','close'])('%s revokes in-flight discovery and rejects late publication',action=>setup(async(dir,c,send)=>{
  let signal:AbortSignal|undefined;let started!:()=>void;const ready=new Promise<void>(r=>{started=r;});
  send.mockImplementation(async(_url,_key,s)=>{signal=s;started();return new Promise(()=>{});});
  const pending=c.request(query());await ready;
  if(action==='close')await c.close();else if(action==='save')await c.request({action,profile,expected_revision:2});else await c.request(query(action,action==='replace-key'?{key:'replacement-key'}:{}));
  expect(signal?.aborted).toBe(true);expect((await pending).status).toBe('cancelled');await expect(readFile(join(dir,'providers/catalog-catalog.json'))).rejects.toThrow();
}));
it('labels stale cache, rejects corrupt cache without network and respects endpoint binding',()=>setup(async(dir,c)=>{
  await c.request(query());await c.close();const path=join(dir,'providers/catalog-catalog.json'),saved=JSON.parse(await readFile(path,'utf8'));saved.fetched_at='2020-01-01T00:00:00Z';await writeFile(path,JSON.stringify(saved));
  const cold=()=>new ProviderController(dir,{isEncryptionAvailable:()=>false,encryptString:()=>Buffer.alloc(0),decryptString:()=>''},async()=>200);
  let next=cold();expect((await next.request(query('catalog'))).catalog?.state).toBe('stale');await next.close();
  saved.binding='other-endpoint';await writeFile(path,JSON.stringify(saved));next=cold();expect((await next.request(query('catalog'))).catalog?.state).toBe('empty');await next.close();
}));

it('cold cached provider inspection needs no credentials or network',()=>setup(async(dir,c,send)=>{
  send.mockResolvedValue({code:200,body:JSON.stringify({data:{id:profile.model,endpoints:[{provider_name:'Retained provider',context_length:2048,supported_parameters:[]}]}})});
  await c.request(query('model-endpoints',{model_id:profile.model}));await c.close();
  const cold=new ProviderController(dir,{isEncryptionAvailable:()=>false,encryptString:()=>Buffer.alloc(0),decryptString:()=>''},async()=>200);
  const result=await cold.request(query('catalog',{model_id:profile.model}));expect(result.endpoints?.providers[0].provider_name).toBe('Retained provider');expect(result.endpoints?.providers[0].capabilities.tools).toBe('unsupported');expect(send).toHaveBeenCalledTimes(1);await cold.close();
}));
it('cache save failure leaves the retained catalog intact and never reports refreshed evidence',()=>setup(async(dir,c,send)=>{
  const accepted=await c.request(query()),path=join(dir,'providers/catalog-catalog.json');
  const original=await readFile(path);await rename(path,path+'.backup');await mkdir(path);
  send.mockResolvedValue({code:200,body:JSON.stringify({data:[{id:'new-model'}]})});
  const failed=await c.request(query());expect(failed.status).toBe('storage-failed');expect(failed.catalog?.models).toEqual(accepted.catalog?.models);expect(await readFile(path+'.backup')).toEqual(original);
  const cached=await c.request(query('catalog'));expect(cached.catalog?.models).toEqual(accepted.catalog?.models);
}));
it('paginates the complete catalog, rejects stale metadata actions before send and guards inherited cache keys',()=>setup(async(_dir,c,send)=>{
  send.mockResolvedValue({code:200,body:JSON.stringify({data:Array.from({length:12},(_,n)=>({id:'model-'+n}))})});
  const first=await c.request(query());expect(first.catalog?.total).toBe(12);expect(first.catalog?.models.map(m=>m.id)).toEqual(['model-0','model-1','model-2','model-3','model-4']);
  const next=await c.request(query('catalog',{offset:5,model_id:'__proto__'}));expect(next.endpoints).toBeNull();expect(next.catalog?.models.map(m=>m.id)).toEqual(['model-5','model-6','model-7','model-8','model-9']);
  expect((await c.request(query('refresh-catalog',{expected_revision:1}))).status).toBe('stale-profile');expect(send).toHaveBeenCalledTimes(1);
}));
