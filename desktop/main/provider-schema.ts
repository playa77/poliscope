/** A deliberately bounded local JSON Schema dialect. Unknown keywords reject.
 * No remote references, dynamic code, coercion, defaults or regex execution.
 */
export class StructuredError extends Error {
  constructor(public code: 'unsupported-schema' | 'invalid-schema' | 'structured-invalid') { super(code); }
}
type Node = {
  type?: string | string[]; description?: string; title?: string;
  properties?: Record<string, Node>; required?: string[]; additionalProperties?: false;
  items?: Node; anyOf?: Node[]; enum?: (string | number | boolean | null)[];
  minimum?: number; maximum?: number; minLength?: number; maxLength?: number;
  minItems?: number; maxItems?: number;
};
const types = ['object','array','string','number','integer','boolean','null'];
const keys = new Set(['type','description','title','properties','required','additionalProperties','items','anyOf','enum','minimum','maximum','minLength','maxLength','minItems','maxItems']);
const record = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === 'object' && !Array.isArray(v);
function bounded(value: unknown, depth = 0, budget = {left:100000}): boolean {
  if (depth > 64 || --budget.left < 0) return false;
  if (value === null || typeof value === 'boolean') return true;
  if (typeof value === 'number') return Number.isFinite(value);
  if (typeof value === 'string') return !/\p{Surrogate}/u.test(value);
  if (Array.isArray(value)) return value.every(v => bounded(v, depth+1, budget));
  return record(value) && Object.entries(value).every(([k,v]) => !/\p{Surrogate}/u.test(k) && bounded(v,depth+1,budget));
}
export function parseSchema(text: string): Node {
  if (Buffer.byteLength(text) > 32768) throw new StructuredError('invalid-schema');
  let value: unknown;
  try { value = JSON.parse(text); } catch { throw new StructuredError('invalid-schema'); }
  let count = 0;
  function inspect(v: unknown, depth: number): asserts v is Node {
    if (!record(v) || depth > 16 || ++count > 1024) throw new StructuredError('invalid-schema');
    if (Object.keys(v).some(k => !keys.has(k))) throw new StructuredError('unsupported-schema');
    const fail = () => { throw new StructuredError('invalid-schema'); };
    for (const k of ['title','description']) if (k in v && typeof v[k] !== 'string') fail();
    const declared = Array.isArray(v.type) ? v.type : v.type === undefined ? [] : [v.type];
    if ((!declared.length && !Array.isArray(v.anyOf)) || declared.some(t => typeof t !== 'string' || !types.includes(t)) || new Set(declared).size !== declared.length) fail();
    if ('type' in v && !declared.length) fail();
    if ('anyOf' in v) {
      if (!Array.isArray(v.anyOf) || !v.anyOf.length || v.anyOf.length > 16) fail();
      for (const child of v.anyOf as unknown[]) inspect(child, depth+1);
    }
    if ('enum' in v && (!Array.isArray(v.enum) || !v.enum.length || v.enum.length > 256 || v.enum.some(e => e !== null && !['string','number','boolean'].includes(typeof e)))) fail();
    for (const [lo,hi,kind] of [['minimum','maximum','number'],['minLength','maxLength','string'],['minItems','maxItems','array']]) {
      if ((lo in v || hi in v) && !declared.includes(kind) && !(kind === 'number' && declared.includes('integer'))) fail();
      for (const k of [lo,hi]) if (k in v && (typeof v[k] !== 'number' || !Number.isFinite(v[k]) || (kind !== 'number' && (!Number.isSafeInteger(v[k]) || (v[k] as number) < 0)))) fail();
      if (lo in v && hi in v && (v[lo] as number) > (v[hi] as number)) fail();
    }
    if (declared.includes('object')) {
      if (!record(v.properties) || v.additionalProperties !== false || !Array.isArray(v.required) || v.required.some(k => typeof k !== 'string' || !Object.hasOwn(v.properties as object,k)) || new Set(v.required).size !== v.required.length) fail();
      for (const child of Object.values(v.properties as object)) inspect(child, depth+1);
    } else if (['properties','required','additionalProperties'].some(k => k in v)) fail();
    if (declared.includes('array')) inspect(v.items,depth+1);
    else if ('items' in v) fail();
  }
  if (!bounded(value)) throw new StructuredError('invalid-schema');
  inspect(value,0);
  return value;
}
function matches(value: unknown, s: Node): boolean {
  if (s.anyOf && !s.anyOf.some(n => matches(value,n))) return false;
  if (s.enum && !s.enum.some(v => v === value)) return false;
  const declared = Array.isArray(s.type) ? s.type : s.type ? [s.type] : [];
  if (!declared.length) return true;
  return declared.some(t => {
    if (t === 'null') return value === null;
    if (t === 'boolean') return typeof value === 'boolean';
    if (t === 'number' || t === 'integer') return typeof value === 'number' && Number.isFinite(value) && (t !== 'integer' || Number.isSafeInteger(value)) && value >= (s.minimum ?? -Infinity) && value <= (s.maximum ?? Infinity);
    if (t === 'string') return typeof value === 'string' && [...value].length >= (s.minLength ?? 0) && [...value].length <= (s.maxLength ?? Infinity);
    if (t === 'array') return Array.isArray(value) && value.length >= (s.minItems ?? 0) && value.length <= (s.maxItems ?? Infinity) && value.every(v => matches(v,s.items!));
    return record(value) && s.required!.every(k => Object.hasOwn(value,k)) && Object.entries(value).every(([k,v]) => Object.hasOwn(s.properties!,k) && matches(v,s.properties![k]));
  });
}
export function validateStructured(text: string, schemaText?: string): string {
  if (Buffer.byteLength(text) > 1048576) throw new StructuredError('structured-invalid');
  let value: unknown;
  try { value = JSON.parse(text); } catch { throw new StructuredError('structured-invalid'); }
  if (!bounded(value) || (schemaText ? !matches(value,parseSchema(schemaText)) : !record(value))) throw new StructuredError('structured-invalid');
  return JSON.stringify(value);
}
