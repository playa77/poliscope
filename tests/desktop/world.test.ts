import { describe, it, expect } from 'vitest';
import fixtures from '../../contracts/fixtures.json';
import { decodeFrame, encodeFrame } from '../../desktop/main/wire';
import type { WireMessage } from '../../contracts/wire';

function message(name: string): WireMessage {
  return JSON.parse(fixtures.find(f => f.name === 'world:' + name)!.frame) as WireMessage;
}

describe('World outbound boundary', () => {
  it('preserves decimal spelling beyond Number precision', () => {
    const payload = message('state-partitions');
    const decoded = decodeFrame(encodeFrame(payload));
    if (!('result' in decoded) || decoded.result.kind !== 'world_page' || decoded.result.page.kind !== 'values') throw new Error('Wrong fixture');
    expect(decoded.result.page.items[0].value).toMatchObject({ kind: 'quantity', value: '125.0000000000000000000000001' });
  });

  it('rejects caller-forged outbound quantities', () => {
    const payload = message('zero');
    if (!('result' in payload) || payload.result.kind !== 'world_page' || payload.result.page.kind !== 'values') throw new Error('Wrong fixture');
    payload.result.page.items[0].value = { kind: 'quantity', value: 'NaN', unit_id: 'L', time_basis_id: null, denominator_scope_id: null };
    expect(() => encodeFrame(payload)).toThrow('INVALID_MESSAGE');
  });

  it('bounds combined byte size even when every item passes the schema', () => {
    const payload = message('bounded-full-page');
    if (!('result' in payload) || payload.result.kind !== 'world_page' || payload.result.page.kind !== 'entities') throw new Error('Wrong fixture');
    for (const item of payload.result.page.items) item.provenance.source_refs = Array(100).fill('source:' + 'x'.repeat(249));
    expect(() => encodeFrame(payload)).toThrow('MESSAGE_TOO_LARGE');
  });
});
