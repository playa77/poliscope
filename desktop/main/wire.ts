/** Protocol-1 schema validator. Keep the supported schema vocabulary explicit. */
import schema from '../../contracts/wire.schema.json';
import type { WireMessage } from '../../contracts/wire';

type Schema = { $ref?: string; const?: unknown; enum?: unknown[]; anyOf?: Schema[]; oneOf?: Schema[]; type?: string; properties?: Record<string, Schema>; required?: string[]; additionalProperties?: boolean; items?: Schema; minItems?: number; maxItems?: number; minLength?: number; maxLength?: number; minimum?: number; maximum?: number };
const definitions = schema.$defs as Record<string, Schema>;
function valid(value: unknown, rule: Schema): boolean {
  if (rule.$ref) return valid(value, definitions[rule.$ref.split('/').at(-1)!]);
  if ('const' in rule) return value === rule.const;
  if (rule.enum) return rule.enum.includes(value);
  if (rule.anyOf) return rule.anyOf.some(r => valid(value, r));
  if (rule.oneOf) return rule.oneOf.filter(r => valid(value, r)).length === 1;
  switch (rule.type) {
    case 'null': return value === null;
    case 'string': return typeof value === 'string' && !/\p{Surrogate}/u.test(value) && [...value].length >= (rule.minLength ?? 0) && [...value].length <= (rule.maxLength ?? Infinity);
    case 'integer': return typeof value === 'number' && Number.isSafeInteger(value) && value >= (rule.minimum ?? -Infinity) && value <= (rule.maximum ?? Infinity);
    case 'array': return Array.isArray(value) && value.length >= (rule.minItems ?? 0) && value.length <= (rule.maxItems ?? Infinity) && value.every(v => valid(v, rule.items!));
    case 'object': {
      if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
      const object = value as Record<string, unknown>;
      return (rule.required ?? []).every(k => Object.hasOwn(object, k)) && Object.entries(object).every(([k, v]) => Object.hasOwn(rule.properties ?? {}, k) ? valid(v, rule.properties![k]) : rule.additionalProperties !== false);
    }
    default: throw new Error('Unsupported wire schema vocabulary');
  }
}
export class WireError extends Error {
  constructor(public code: string) { super(code); }
}
export function decodeFrame(frame: Uint8Array): WireMessage {
  if (frame.byteLength > 1_048_576) throw new WireError('MESSAGE_TOO_LARGE');
  let raw: unknown;
  try {
    const text = new TextDecoder('utf-8', { fatal: true }).decode(frame);
    if (!text.endsWith('\n') || text.slice(0, -1).includes('\n') || text.includes('\r')) throw new Error();
    // Numeric tokens are integer spelling only; avoid rounding before validation.
    const tokens = text.match(/"(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g) ?? [];
    if (tokens.some(token => !token.startsWith('"') && (!/^-?\d+$/.test(token) || !Number.isSafeInteger(Number(token))))) throw new Error();
    raw = JSON.parse(text);
  } catch { throw new WireError('INVALID_MESSAGE'); }
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) throw new WireError('INVALID_MESSAGE');
  if (!('protocol' in raw) || raw.protocol !== 1) throw new WireError('UNSUPPORTED_PROTOCOL');
  if (!valid(raw, schema as Schema)) throw new WireError('INVALID_MESSAGE');
  return raw as WireMessage;
}
export function encodeFrame(message: WireMessage): Uint8Array {
  if (!valid(message, schema as Schema)) throw new WireError('INVALID_MESSAGE');
  const frame = new TextEncoder().encode(JSON.stringify(message) + '\n');
  decodeFrame(frame);
  return frame;
}
