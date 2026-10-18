import { it, expect } from 'vitest';
import fixtures from '../../contracts/fixtures.json';
import { decodeFrame, encodeFrame } from '../../desktop/main/wire';
import type { WireMessage } from '../../contracts/wire';

function message(name: string): WireMessage {
  return JSON.parse(fixtures.find(f => f.name === 'evidence:' + name)!.frame) as WireMessage;
}

it('preserves precise evidence quantities and unknown outputs', () => {
  const decoded = decodeFrame(encodeFrame(message('outputs')));
  if (!('result' in decoded) || decoded.result.kind !== 'evidence_page' || decoded.result.page.kind !== 'outputs') throw new Error('Wrong fixture');
  expect(decoded.result.page.items[0].observation.value).toMatchObject({ kind: 'quantity', value: '125.0000000000000000000000001' });
  expect(decoded.result.page.items[2].observation.value).toEqual({ kind: 'unknown', reason: 'Synthetic unavailable output' });
});

it('bounds combined evidence size and rejects forged outbound quantities', () => {
  const payload = message('traces');
  if (!('result' in payload) || payload.result.kind !== 'evidence_page' || payload.result.page.kind !== 'traces') throw new Error('Wrong fixture');
  const item = payload.result.page.items[0];
  item.child_refs = Array(100).fill('trace:' + 'x'.repeat(250));
  payload.result.page.items = Array(100).fill(item);
  expect(() => encodeFrame(payload)).toThrow('MESSAGE_TOO_LARGE');
  item.child_refs = [];
  payload.result.page.items = [item];
  item.inputs[0].value = { kind: 'quantity', value: 'NaN', unit_id: 'L', time_basis_id: null, denominator_scope_id: null };
  expect(() => encodeFrame(payload)).toThrow('INVALID_MESSAGE');
});
