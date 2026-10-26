/** Data-only provider adapters. Catalog evidence never authorizes generation. */
import type { ModelMetadata, ProviderProfile, KeyMetadata, EndpointMetadata } from '../../contracts/provider';
export type MetadataTransport = (url: string, key: string, signal: AbortSignal) => Promise<{ code: number; body: string }>;
export const CATALOG_TTL = 24 * 60 * 60 * 1000;
export const object = (v: unknown): Record<string, unknown> => {
  if (!v || typeof v !== 'object' || Array.isArray(v)) throw new Error('Invalid metadata');
  return v as Record<string, unknown>;
};
const text = (v: unknown): string => { if (typeof v !== 'string' || !v.length || v.length > 256 || /[\u0000-\u001f\u007f]/.test(v)) throw new Error('Invalid metadata text'); return v; };
const count = (v: unknown): number | null => typeof v === 'number' && Number.isSafeInteger(v) && v > 0 ? v : null;
const strings = (v: unknown, limit = 64): string[] | null => {
  if (v === undefined || v === null) return null;
  if (!Array.isArray(v) || v.length > limit) throw new Error('Invalid metadata list');
  return v.map(text);
};
const pricing = (value: unknown): Record<string, string> | null => {
  if (value == null) return null;
  const entries = Object.entries(object(value));
  if (entries.length > 64 || entries.some(([k,v]) => { text(k); return typeof v !== 'string' || !/^-?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$/.test(v) || v.length > 256; })) throw new Error('Invalid pricing');
  return Object.fromEntries(entries) as Record<string,string>;
};
const unknown = (): ModelMetadata['capabilities'] => ({ text:'unknown', image:'unknown', audio:'unknown', video:'unknown', tools:'unknown', structured_output:'unknown', reasoning:'unknown' });
const has = (values: string[] | null, value: string): 'unknown' | 'supported' | 'unsupported' => values === null ? 'unknown' : values.includes(value) ? 'supported' : 'unsupported';
export interface MetadataAdapter {
  models(body: unknown, observed: string): ModelMetadata[];
  endpointRoute(id: string): string | undefined;
  endpoints(body: unknown, id: string, observed: string): EndpointMetadata;
  key(body: unknown, observed: string): KeyMetadata;
}
function models(body: unknown, observed: string, openrouter: boolean): ModelMetadata[] {
  const envelope = object(body), data = envelope.data;
  // A partial future listing must never mark the remaining catalog removed.
  if (envelope.has_more === true) throw new Error('Incomplete model catalog');
  if (!Array.isArray(data) || data.length > 5000) throw new Error('Invalid model catalog');
  const ids = new Set<string>();
  return data.map(value => {
    const raw = object(value), id = text(raw.id);
    if (ids.has(id)) throw new Error('Duplicate model'); ids.add(id);
    const raw_json = JSON.stringify(raw);
    if (Buffer.byteLength(raw_json) > 32768) throw new Error('Model metadata too large');
    const architecture = openrouter && raw.architecture != null ? object(raw.architecture) : {};
    const top = openrouter && raw.top_provider != null ? object(raw.top_provider) : {};
    const input = openrouter ? strings(architecture.input_modalities) : null;
    const output = openrouter ? strings(architecture.output_modalities) : null;
    const parameters = openrouter ? strings(raw.supported_parameters, 128) : null;
    const capabilities = unknown();
    if (openrouter) {
      for (const modality of ['text','image','audio','video'] as const) {
        // Either direction may supply a modality. Absence in one direction is
        // not unsupported while the other direction is unknown.
        capabilities[modality] = input?.includes(modality) || output?.includes(modality) ? 'supported' : input !== null && output !== null ? 'unsupported' : 'unknown';
      }
      capabilities.tools = has(parameters, 'tools');
      capabilities.structured_output = has(parameters, 'structured_outputs');
      capabilities.reasoning = parameters === null ? 'unknown' : parameters.some(p => p === 'reasoning' || p === 'include_reasoning') ? 'supported' : 'unsupported';
    }
    return { id, name: raw.name == null ? id : text(raw.name), available:true, observed_at:observed,
      source:openrouter ? 'openrouter:/models' : 'openai-compatible:/models',
      context_length:openrouter ? count(raw.context_length) : null, max_output_tokens:count(top.max_completion_tokens),
      input_modalities:input, output_modalities:output, supported_parameters:parameters, capabilities,
      pricing:openrouter ? pricing(raw.pricing) : null, routing:openrouter ? 'supported' : 'unknown', raw_json };
  });
}
export const openRouterAdapter: MetadataAdapter = {
  models:(body, time) => models(body, time, true),
  endpointRoute(id) {
    const parts = id.split('/');
    if (parts.length !== 2 || parts.some(p => !p || p === '.' || p === '..')) return undefined;
    return '/models/' + parts.map(encodeURIComponent).join('/') + '/endpoints';
  },
  endpoints(body, id, observed) {
    const data = object(object(body).data);
    if (data.id !== id || !Array.isArray(data.endpoints) || data.endpoints.length > 256) throw new Error('Invalid endpoints');
    const providers = data.endpoints.map(entry => {
      const row = object(entry), parameters = strings(row.supported_parameters,128), capabilities = unknown();
      capabilities.tools = has(parameters, 'tools');
      capabilities.structured_output = has(parameters, 'structured_outputs');
      capabilities.reasoning = parameters === null ? 'unknown' : parameters.some(p => p === 'reasoning' || p === 'include_reasoning') ? 'supported' : 'unsupported';
      return { provider_name:text(row.provider_name), context_length:count(row.context_length), max_output_tokens:count(row.max_completion_tokens), supported_parameters:parameters, capabilities, pricing:pricing(row.pricing) };
    });
    const raw_json = JSON.stringify(data);
    if (Buffer.byteLength(raw_json) > 131072) throw new Error('Endpoint metadata too large');
    return { model_id:id, observed_at:observed, source:'openrouter:/models/{author}/{slug}/endpoints', providers, raw_json };
  },
  key(body, observed) {
    const data = object(object(body).data);
    // Deliberate allowlist: never expose label, key fragments, organization IDs,
    // unknown account fields or server diagnostics. Limits are reported values.
    const number = (v: unknown) => typeof v === 'number' && Number.isFinite(v) && v >= 0 ? String(v) : null;
    return { observed_at:observed, source:'openrouter:/key', limit:number(data.limit), limit_remaining:number(data.limit_remaining), usage:number(data.usage), is_free_tier:typeof data.is_free_tier === 'boolean' ? data.is_free_tier : null };
  }
};
export const compatibleAdapter: MetadataAdapter = {
  models:(body, time) => models(body, time, false),
  endpointRoute:() => undefined,
  endpoints:() => { throw new Error('Unsupported metadata'); },
  key:() => { throw new Error('Unsupported metadata'); },
};
export const adapterFor = (kind: ProviderProfile['kind']) => kind === 'openrouter' ? openRouterAdapter : compatibleAdapter;
export function metadataCode(code: number) {
  if (code >= 300 && code < 400) return 'redirect-blocked';
  if (code === 401 || code === 403) return 'unauthorized';
  if (code === 402) return 'credits-required';
  if (code === 429) return 'rate-limited';
  if (code === 404) return 'model-unavailable';
  return code >= 200 && code < 300 ? 'metadata-ready' : 'provider-rejected';
}
