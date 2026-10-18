import { describe, it, expect } from 'vitest';
import numeric from '../fixtures/numeric.json';
import fixtures from '../../contracts/fixtures.json';
import { decodeFrame, encodeFrame } from '../../desktop/main/wire';
import type { WireMessage } from '../../contracts/wire';

describe('Authoritative decimal transport', () => {
  it.each(numeric.canonical)('preserves Python canonical quantity %s as %s', (_input, canonical) => {
    const payload = JSON.parse(fixtures.find(f => f.name === 'world:zero')!.frame) as WireMessage;
    if (!('result' in payload) || payload.result.kind !== 'world_page' || payload.result.page.kind !== 'values') throw new Error('Wrong fixture');
    payload.result.page.items[0].value = {
      kind: 'quantity', value: canonical, unit_id: 'kg', time_basis_id: null, denominator_scope_id: null,
    };
    const decoded = decodeFrame(encodeFrame(payload));
    if (!('result' in decoded) || decoded.result.kind !== 'world_page' || decoded.result.page.kind !== 'values') throw new Error('Wrong result');
    expect(decoded.result.page.items[0].value).toEqual(payload.result.page.items[0].value);
  });
});
