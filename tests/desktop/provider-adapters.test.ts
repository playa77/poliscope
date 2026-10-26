import { it, expect } from 'vitest';
import fixture from '../fixtures/providers/openrouter-models.json';
import { openRouterAdapter, compatibleAdapter, metadataCode } from '../../desktop/main/provider-adapters';
const time = '2026-10-26T10:00:00.000Z';
it('normalizes documented metadata with literal context/pricing, variants and explicit unknowns', () => {
  const [model,free,unknown] = openRouterAdapter.models(fixture,time);
  expect(model.id).toBe('future/vendor-model:preview'); expect(model.context_length).toBe(131072); expect(model.max_output_tokens).toBe(8192);
  expect(model.pricing).toEqual({prompt:'0.000000123456789',completion:'0.000002',future_price:'-1'});
  expect(model.input_modalities).toEqual(['text','image','future_sensor']);
  expect(model.capabilities).toEqual({text:'supported',image:'supported',audio:'unsupported',video:'unsupported',tools:'supported',structured_output:'supported',reasoning:'supported'});
  expect(model.source).toBe('openrouter:/models'); expect(model.observed_at).toBe(time);
  expect(JSON.parse(model.raw_json).future_metadata).toEqual({preserve:[1,'unknown']});
  expect(free.capabilities.tools).toBe('unsupported'); expect(free.pricing?.prompt).toBe('0');
  expect(Object.values(unknown.capabilities)).toEqual(Array(7).fill('unknown')); expect(unknown.context_length).toBeNull(); expect(unknown.pricing).toBeNull();
});
it('does not infer generic compatible capabilities, context, prices, routing or account endpoints', () => {
  const [model] = compatibleAdapter.models(fixture,time);
  expect(Object.values(model.capabilities)).toEqual(Array(7).fill('unknown')); expect(model.pricing).toBeNull(); expect(model.context_length).toBeNull(); expect(model.routing).toBe('unknown');
  expect(compatibleAdapter.endpointRoute('future/model')).toBeUndefined(); expect(() => compatibleAdapter.key({},time)).toThrow();
  expect(JSON.parse(model.raw_json).future_metadata).toBeDefined();
});
it('missing output metadata stays unknown; response_format alone does not establish schema output', () => {
  const [model] = openRouterAdapter.models({data:[{id:'new',architecture:{input_modalities:['text']},supported_parameters:['response_format']}]},time);
  expect(model.capabilities.image).toBe('unknown'); expect(model.capabilities.text).toBe('supported'); expect(model.capabilities.structured_output).toBe('unsupported');
});
it('fails closed on malformed, duplicate and oversized metadata', () => {
  for(const body of [null,{}, {data:{}},{data:[{id:'a'},{id:'a'}]},{data:[{id:'x',supported_parameters:'tools'}]},{data:[{id:'x',pricing:{prompt:0.1}}]},{data:[{id:'x',name:'\nunsafe'}]},{data:[{id:'x',extension:'a'.repeat(33000)}]}]) expect(()=>openRouterAdapter.models(body,time)).toThrow();
});
it('encodes fixed model endpoint routes and retains provider-specific unknown fields', () => {
  expect(openRouterAdapter.endpointRoute('vendor/model:free')).toBe('/models/vendor/model%3Afree/endpoints');
  expect(openRouterAdapter.endpointRoute('../x')).toBeUndefined(); expect(openRouterAdapter.endpointRoute('vendor/a/b')).toBeUndefined();
  const result = openRouterAdapter.endpoints({data:{id:'vendor/model',future_field:42,endpoints:[{provider_name:'Synthetic provider',context_length:4096,max_completion_tokens:512,supported_parameters:['tools'],pricing:{prompt:'0.01'},future_endpoint:true}]}},'vendor/model',time);
  expect(result.providers[0].context_length).toBe(4096); expect(result.providers[0].capabilities.tools).toBe('supported'); expect(result.providers[0].capabilities.image).toBe('unknown');
  expect(JSON.parse(result.raw_json).future_field).toBe(42); expect(()=>openRouterAdapter.endpoints({data:{id:'other',endpoints:[]}},'vendor/model',time)).toThrow();
});
it('only returns safe key-status fields, distinguishes unknown and zero, maps safe error codes', () => {
  const result=openRouterAdapter.key({data:{label:'sk-or-SECRET',key:'SECRET',organization_id:'private',limit:null,limit_remaining:0,usage:12.5,is_free_tier:false,unknown_secret:'SECRET'}},time);
  expect(result).toEqual({observed_at:time,source:'openrouter:/key',limit:null,limit_remaining:'0',usage:'12.5',is_free_tier:false}); expect(JSON.stringify(result)).not.toContain('SECRET');
  expect([401,402,429,404,302,500,200].map(metadataCode)).toEqual(['unauthorized','credits-required','rate-limited','model-unavailable','redirect-blocked','provider-rejected','metadata-ready']);
});

it('rejects incomplete listings and counts raw UTF-8 bytes without discarding prior evidence', () => {
  expect(() => openRouterAdapter.models({data:[],has_more:true},time)).toThrow('Incomplete');
  expect(() => openRouterAdapter.models({data:[{id:'unicode',extension:'語'.repeat(12000)}]},time)).toThrow('too large');
  expect(() => openRouterAdapter.endpoints({data:{id:'vendor/model',endpoints:[],extension:'語'.repeat(50000)}},'vendor/model',time)).toThrow('too large');
});
