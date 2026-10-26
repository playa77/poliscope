/** Pure main-only construction. This module cannot obtain keys or dispatch.
 * WP-045 consumes these plans only after sharing and spend gates are available.
 */
import { createHash } from 'node:crypto';
import type { GenerationPlan, GenerationResult } from '../../contracts/generation';
import type { ModelMetadata, ProviderView, EndpointMetadata } from '../../contracts/provider';
import generationSchema from '../../contracts/generation.schema.json';
import { valid, type Schema } from './wire';
import { providerValid, providerEndpoint } from './providers';
import { CATALOG_TTL, object } from './provider-adapters';
import { parseSchema, validateStructured } from './provider-schema';
const defs = generationSchema.$defs as Record<string,Schema>;
export class RequestError extends Error {
  constructor(public code: 'invalid-plan' | 'stale-profile' | 'stale-metadata' | 'model-unavailable' | 'capability-unknown' | 'unsupported-control' | 'invalid-control' | 'context-unknown' | 'context-exceeded' | 'parameter-enforcement-required', public parameter: string | null = null) { super(code); }
}
export interface RequestEvidence {
  profile_id: string; revision: number; endpoint: string;
  models: ModelMetadata[];
  endpoints?: EndpointMetadata[];
  /** Trusted main-owned tokenizer/bound receipts for this exact payload/model.
   * Missing tokenizers must block; byte length is not assumed to be tokens.
   */
  budgets: { model_id: string; input_tokens_upper_bound: number; payload_sha256: string; source: 'tokenizer' | 'conservative-model-bound' }[];
}
export interface BuiltRequest {
  profile_id: string; revision: number; endpoint: string;
  path: '/chat/completions'; method: 'POST'; json: string;
  selected_model: string; allowed_models: readonly string[];
  plan: GenerationPlan;
}
function fail(code: RequestError['code'], parameter: string | null = null): never { throw new RequestError(code,parameter); }
export function contextPayloadHash(plan: GenerationPlan): string {
  return createHash('sha256').update(JSON.stringify({messages:plan.messages,tools:plan.tools ?? [],response_format:plan.response_format})).digest('hex');
}
function fresh(time: string, now: number): boolean {
  const observed = Date.parse(time);
  return Number.isFinite(observed) && observed <= now && now-observed <= CATALOG_TTL;
}
function freeze<T>(value: T): T {
  if (value && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value); }
  return value;
}
export function buildGenerationRequest(view: ProviderView, plan: GenerationPlan, evidence: RequestEvidence, now = Date.now()): BuiltRequest {
  // JSON cloning prevents subsequent edits from changing an inspected request.
  if (!valid(plan,defs.GenerationPlan,defs) || !providerValid(view.profile,'ProviderProfile') || Buffer.byteLength(JSON.stringify(plan)) > 1048576) fail('invalid-plan');
  const p = structuredClone(view.profile), input = structuredClone(plan);
  const endpoint = providerEndpoint(p.endpoint,p.kind);
  if (view.revision !== input.expected_revision || p.id !== input.profile_id || evidence.profile_id !== p.id || evidence.revision !== view.revision || evidence.endpoint !== endpoint) fail('stale-profile');
  const r = p.routing, g = p.generation;
  const fallback = r.model_fallbacks ?? [];
  const ids = [p.model,...fallback];
  if (!p.model || new Set(ids).size !== ids.length) fail('invalid-control','model_fallbacks');
  const compatible = p.kind === 'openai-compatible';
  if (compatible && (fallback.length || r.order.length || r.only.length || r.ignore.length || r.allow_fallbacks || r.data_collection !== 'unknown' || r.zdr != null || r.sort != null || r.max_price != null)) fail('unsupported-control','provider');
  for (const list of [r.order,r.only,r.ignore]) if (new Set(list).size !== list.length) fail('invalid-control','provider');
  if (r.only.some(x => r.ignore.includes(x)) || r.order.some(x => r.ignore.includes(x) || (r.only.length && !r.only.includes(x))) || (r.sort && r.order.length)) fail('invalid-control','provider');
  const body: Record<string,unknown> = { model:p.model, messages:input.messages, stream:input.stream };
  const parameters = new Set<string>();
  const selected = (key: string, value: unknown) => { body[key] = value; parameters.add(key); };
  const decimal = (value: string, low: number, high: number, key: string, exclusiveLow = false) => {
    const number = Number(value);
    if (!Number.isFinite(number) || number < low || number > high || (exclusiveLow && number === low)) fail('invalid-control',key);
    return number;
  };
  if (g.temperature != null) selected('temperature',decimal(g.temperature,0,2,'temperature'));
  if (g.top_p != null) selected('top_p',decimal(g.top_p,0,1,'top_p',true));
  for (const key of ['frequency_penalty','presence_penalty'] as const) if (g[key] != null) selected(key,decimal(g[key],-2,2,key));
  if (g.seed != null) selected('seed',g.seed);
  if (g.stop != null) selected('stop',g.stop);
  if (g.max_output_tokens == null) fail('context-unknown','max_output_tokens');
  const output = g.max_output_tokens;
  // Generic compatible endpoints use the documented chat completion token field.
  selected(compatible ? 'max_completion_tokens' : 'max_tokens',output);
  const format = input.response_format;
  if (format.type === 'json_schema') {
    if (!format.name || !format.schema_text) fail('invalid-control','response_format');
    const schema = parseSchema(format.schema_text);
    if (schema.type !== 'object') fail('invalid-control','response_format');
    selected('response_format',{type:'json_schema',json_schema:{name:format.name,strict:true,schema}});
    parameters.add('structured_outputs');
  } else {
    if (format.name != null || format.schema_text != null) fail('invalid-control','response_format');
    if (format.type === 'json_object') selected('response_format',{type:'json_object'});
  }
  const tools = input.tools ?? [];
  if (new Set(tools.map(t => t.name)).size !== tools.length) fail('invalid-control','tools');
  const choice = input.tool_choice ?? 'auto';
  if (tools.length) {
    selected('tools',tools.map(t => {
      const schema = parseSchema(t.parameters_json);
      if (schema.type !== 'object') fail('invalid-control','tools');
      return {type:'function',function:{name:t.name,description:t.description,parameters:schema,strict:true}};
    }));
    if (!['auto','none','required'].includes(choice) && !tools.some(t => t.name === choice)) fail('invalid-control','tool_choice');
    selected('tool_choice',['auto','none','required'].includes(choice) ? choice : {type:'function',function:{name:choice}});
  } else if (choice !== 'auto') fail('invalid-control','tool_choice');
  if (g.reasoning != null) {
    const reasoning = Object.fromEntries(Object.entries(g.reasoning).filter(([,v]) => v != null));
    if (!Object.keys(reasoning).length || (g.reasoning.effort != null && g.reasoning.max_tokens != null) || (g.reasoning.enabled === false && ((g.reasoning.effort != null && g.reasoning.effort !== 'none') || g.reasoning.max_tokens != null)) || (g.reasoning.enabled === true && g.reasoning.effort === 'none') || (g.reasoning.max_tokens != null && g.reasoning.max_tokens >= output)) fail('invalid-control','reasoning');
    if (compatible) {
      if (g.reasoning.max_tokens != null || g.reasoning.enabled != null || g.reasoning.exclude != null || !g.reasoning.effort) fail('unsupported-control','reasoning');
      selected('reasoning_effort',g.reasoning.effort);
    } else selected('reasoning',reasoning);
  }
  if (!compatible) {
    if (!r.require_parameters && parameters.size) fail('parameter-enforcement-required','require_parameters');
    const provider: Record<string,unknown> = {order:r.order,only:r.only,ignore:r.ignore,allow_fallbacks:r.allow_fallbacks,require_parameters:r.require_parameters};
    if (r.data_collection !== 'unknown') provider.data_collection = r.data_collection;
    if (r.zdr != null) provider.zdr = r.zdr;
    if (r.sort != null) provider.sort = r.sort;
    if (r.max_price != null) {
      const prices = Object.entries(r.max_price).filter(([,v]) => v != null);
      if (!prices.length) fail('invalid-control','max_price');
      provider.max_price = Object.fromEntries(prices.map(([k,v]) => {
        const price = decimal(v!,0,999999999,'max_price');
        // Never round a user's price ceiling upward (or silently alter it).
        // This is serialization validation, not a currency/accounting rule.
        const canonical = (s: string) => {
          const [mantissa, exponent = '0'] = s.toLowerCase().split('e');
          const [whole, fraction = ''] = mantissa.split('.');
          let digits = (whole+fraction).replace(/^0+(?=\d)/,''), scale = fraction.length-Number(exponent);
          while (digits.length > 1 && digits.endsWith('0')) { digits = digits.slice(0,-1); scale--; }
          return digits === '0' ? '0' : digits+':'+scale;
        };
        if (canonical(String(price)) !== canonical(v!)) fail('invalid-control','max_price');
        return [k,price];
      }));
    }
    body.provider = provider;
    if (fallback.length) { delete body.model; body.models = ids; }
  }
  const payload = contextPayloadHash(input);
  for (const id of ids) {
    const m = evidence.models.find(m => m.id === id);
    if (!m || !providerValid(m,'ModelMetadata') || !m.available) fail('model-unavailable');
    if (!fresh(m.observed_at,now)) fail('stale-metadata');
    if ((!compatible && m.source !== 'openrouter:/models') || (compatible && !m.source.startsWith('declared:'))) fail('capability-unknown');
    if (m.input_modalities === null || m.output_modalities === null || !m.input_modalities.includes('text') || !m.output_modalities.includes('text')) fail('capability-unknown','text');
    for (const capability of ['text',...(tools.length ? ['tools'] : []),...(format.type === 'json_schema' ? ['structured_output'] : []),...(g.reasoning ? ['reasoning'] : [])] as (keyof typeof m.capabilities)[]) {
      if (p.capabilities[capability] === 'unsupported' || m.capabilities[capability] !== 'supported') fail('capability-unknown',capability);
    }
    if (!compatible && m.routing !== 'supported') fail('capability-unknown','provider');
    for (const param of parameters) if (!m.supported_parameters?.includes(param)) fail(m.supported_parameters === null ? 'capability-unknown' : 'unsupported-control',param);
    let raw: Record<string,unknown>;
    try { raw = object(JSON.parse(m.raw_json)); } catch { fail('capability-unknown'); }
    if (g.reasoning) {
      const declared = raw.reasoning == null ? {} : object(raw.reasoning);
      if ((g.reasoning.effort === 'none' || g.reasoning.enabled === false) && declared.mandatory === true) fail('unsupported-control','reasoning');
      if (g.reasoning.effort != null && declared.supported_efforts !== null && (!Array.isArray(declared.supported_efforts) || !declared.supported_efforts.includes(g.reasoning.effort))) fail('unsupported-control','reasoning');
      if (g.reasoning.max_tokens != null && declared.supports_max_tokens !== true) fail('unsupported-control','reasoning');
    }
    const budget = evidence.budgets.find(b => b.model_id === id && b.payload_sha256 === payload);
    if (!budget || !['tokenizer','conservative-model-bound'].includes(budget.source) || !Number.isSafeInteger(budget.input_tokens_upper_bound) || budget.input_tokens_upper_bound < 1 || m.context_length === null || m.max_output_tokens === null) fail('context-unknown');
    if (output > m.max_output_tokens || budget.input_tokens_upper_bound > m.context_length-output) fail('context-exceeded');
    const endpoints = evidence.endpoints?.find(e => e.model_id === id);
    if (endpoints) {
      if (!providerValid(endpoints,'EndpointMetadata') || !fresh(endpoints.observed_at,now)) fail('stale-metadata');
      // Names are display labels, not routing slugs: do not guess their mapping.
      // Routing parameter enforcement remains authoritative server-side.
    }
  }
  const result: BuiltRequest = {profile_id:p.id,revision:view.revision,endpoint,path:'/chat/completions',method:'POST',json:JSON.stringify(body),selected_model:p.model,allowed_models:ids,plan:input};
  if (Buffer.byteLength(result.json) > 1048576) fail('invalid-plan');
  return freeze(result);
}

/** Safe completion normalization. SSE assembly is the WP-045 consumer. */
export function normalizeGenerationResponse(request: BuiltRequest, value: unknown, httpStatus = 200): GenerationResult {
  const result: GenerationResult = {generation_contract:1,selected_model:request.selected_model,actual_model:null,actual_provider:null,finish_reason:null,status:'response-invalid',validated_json:null,text:null,parameter:null};
  const label = (v: unknown): string | null => typeof v === 'string' && v.length > 0 && v.length <= 256 && !/[\u0000-\u001f\u007f]/.test(v) && !/\p{Surrogate}/u.test(v) ? v : null;
  try {
    if (Buffer.byteLength(JSON.stringify(value)) > 2097152) return result;
    const body = object(value);
    if (httpStatus < 200 || httpStatus >= 300 || body.error != null) {
      result.status = 'provider-rejected';
      // Only known parameter names survive. Never expose provider error prose.
      const error = body.error == null ? {} : object(body.error);
      const allowed = ['temperature','top_p','max_tokens','max_completion_tokens','frequency_penalty','presence_penalty','seed','stop','tools','tool_choice','response_format','reasoning','reasoning_effort','provider'];
      if (allowed.includes(error.param as string)) { result.status = 'unsupported-parameter'; result.parameter = error.param as string; }
      return result;
    }
    result.actual_model = label(body.model); result.actual_provider = label(body.provider);
    if (result.actual_model && !request.allowed_models.includes(result.actual_model)) return result;
    if (!Array.isArray(body.choices) || body.choices.length !== 1) return result;
    const choice = object(body.choices[0]), message = object(choice.message);
    result.finish_reason = label(choice.finish_reason);
    if (message.refusal != null) { result.status = 'refused'; return result; }
    if (typeof message.content !== 'string' || Buffer.byteLength(message.content) > 1048576 || /\p{Surrogate}/u.test(message.content)) return result;
    if (result.finish_reason !== 'stop') { result.status = 'incomplete'; return result; }
    if (request.plan.response_format.type !== 'text') {
      try { result.validated_json = validateStructured(message.content,request.plan.response_format.schema_text ?? undefined); }
      catch { result.status = 'structured-invalid'; return result; }
    }
    result.status = 'complete'; result.text = message.content;
    return result;
  } catch { return result; }
}
