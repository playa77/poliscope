import { describe, it, expect } from 'vitest';
import cases from '../../contracts/fixtures.json';
import { decodeFrame, encodeFrame } from '../../desktop/main/wire';
describe('Python/TypeScript protocol compatibility', () => {
  for (const fixture of cases) it(fixture.name, () => {
    const frame = new TextEncoder().encode(fixture.frame);
    if (fixture.code) expect(() => decodeFrame(frame)).toThrow(fixture.code!);
    else expect(JSON.parse(new TextDecoder().decode(encodeFrame(decodeFrame(frame))))).toEqual(JSON.parse(fixture.frame));
  });
  it('bounds bytes and rejects invalid UTF-8', () => {
    expect(() => decodeFrame(new Uint8Array(1_048_577))).toThrow('MESSAGE_TOO_LARGE');
    expect(() => decodeFrame(new Uint8Array([255, 10]))).toThrow('INVALID_MESSAGE');
  });
});
