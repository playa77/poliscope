import { describe, expect, it, vi } from 'vitest';
import { PassThrough, Writable } from 'node:stream';
import { engineCommand } from '../../desktop/main/engine';
import { EngineTransport } from '../../desktop/main/transport';
import { encodeFrame } from '../../desktop/main/wire';

function fixture(timeout = 1000, output: Writable = new PassThrough()) {
  const input = new PassThrough();
  const fail = vi.fn();
  const transport = new EngineTransport(input, output, fail, timeout);
  const answer = (id: string, kind = 'health') => encodeFrame({ protocol: 1, id, kind: 'result', result: kind === 'handshake' ? { kind, versions: { application: '0.1.0', schema_version: 1, protocol: 1 } } : { kind: 'health', state: 'ready' } });
  const ready = async () => { const p = transport.handshake(); input.write(answer('request:1', 'handshake')); await p; };
  return { input, output, fail, transport, answer, ready };
}

describe('bounded protocol session', () => {
  it('rejects calls before negotiation and routes fragmented, batched out-of-order responses', async () => {
    const f = fixture();
    await expect(f.transport.request('runtime.health', {})).rejects.toThrow('unavailable');
    const handshake = f.transport.handshake();
    const frame = f.answer('request:1', 'handshake');
    for (const byte of frame) f.input.write(Buffer.from([byte]));
    await handshake;
    const a = f.transport.request('runtime.health', {}), b = f.transport.request('runtime.health', {});
    f.input.write(Buffer.concat([f.answer('request:3'), f.answer('request:2')]));
    expect((await a).id).toBe('request:2'); expect((await b).id).toBe('request:3');
    expect(f.fail).not.toHaveBeenCalled();
  });
  it.each(['malformed', 'oversize', 'protocol', 'uncorrelated', 'wrong-kind', 'invalid-utf8', 'exit'])('settles pending callers on %s', async fault => {
    const f = fixture(); await f.ready();
    const pending = f.transport.request('runtime.health', {});
    const rejected = expect(pending).rejects.toThrow();
    if (fault === 'exit') f.input.end();
    else f.input.write(fault === 'oversize' ? Buffer.alloc(1_048_577, 120) : fault === 'protocol' ? '{"protocol":2}\n' : fault === 'uncorrelated' ? f.answer('unknown') : fault === 'wrong-kind' ? f.answer('request:2', 'handshake') : fault === 'invalid-utf8' ? Buffer.from([255,10]) : 'log secret\n');
    await rejected; expect(f.fail).toHaveBeenCalledTimes(1);
    await expect(f.transport.request('runtime.health', {})).rejects.toThrow('unavailable');
  });
  it('fails the session on timeout', async () => {
    const f = fixture(10); await f.ready();
    await expect(f.transport.request('runtime.health', {})).rejects.toThrow('timed out');
  });
  it('bounds pending calls and rejects backpressure without queuing another frame', async () => {
    const f = fixture(); await f.ready();
    const calls = Array.from({ length: 64 }, () => f.transport.request('runtime.health', {}).catch(() => {}));
    await expect(f.transport.request('runtime.health', {})).rejects.toThrow('backpressure');
    f.transport.fail(new Error('done')); await Promise.all(calls);
    const blocked = new Writable({ highWaterMark: 1, write(_chunk, _encoding, _callback) {} });
    const g = fixture(1000, blocked); const p = g.transport.handshake().catch(() => {});
    await expect(g.transport.handshake()).rejects.toThrow('backpressure');
    g.transport.fail(new Error('done')); await p;
  });
  it('routes progress without completing the request, then accepts a stable error', async () => {
    const f = fixture(); await f.ready(); const progress = vi.fn();
    const p = f.transport.request('runtime.health', {}, progress);
    f.input.write(encodeFrame({ protocol: 1, id: 'request:2', kind: 'progress', operation_id: 'op:1', completed: 1, total: 2 }));
    expect(progress).toHaveBeenCalledTimes(1);
    f.input.write(encodeFrame({ protocol: 1, id: 'request:2', kind: 'error', error: { code: 'CANCELLED', message: 'Cancelled' } }));
    expect((await p).kind).toBe('error');
  });
});

import { spawn } from 'node:child_process';
import { resolve } from 'node:path';
it('exchanges actual runtime calls with the managed Python producer', async () => {
  const command = engineCommand(false, resolve('.'), '');
  const child = spawn(command.executable, command.args, { stdio: 'pipe', shell: false });
  const transport = new EngineTransport(child.stdout, child.stdin, () => child.kill());
  child.stderr.resume();
  const exit = new Promise<number | null>(resolve => child.once('exit', resolve));
  try {
    await transport.handshake();
    const health = await transport.request('runtime.health', {});
    expect(health.kind === 'result' && health.result).toEqual({ kind: 'health', state: 'ready' });
    const cancel = await transport.request('runtime.cancel', { operation_id: 'op:absent' });
    expect(cancel.kind === 'result' && cancel.result).toEqual({ kind: 'cancel', operation_id: 'op:absent', state: 'unknown' });
    const shutdown = await transport.request('runtime.shutdown', {});
    expect(shutdown.kind === 'result' && shutdown.result).toEqual({ kind: 'shutdown', state: 'stopping' });
    expect(await exit).toBe(0);
  } finally { child.kill(); }
});
it('rejects negotiation when a real child crashes', async () => {
  const child = spawn(process.execPath, ['-e', 'process.exit(7)'], { stdio: 'pipe', shell: false });
  const transport = new EngineTransport(child.stdout, child.stdin, () => child.kill());
  child.stderr.resume();
  await expect(transport.handshake()).rejects.toThrow();
});
it('never becomes ready after a handshake followed by malformed output in the same batch', async () => {
  const f = fixture();
  const handshake = f.transport.handshake();
  f.input.write(Buffer.concat([f.answer('request:1', 'handshake'), Buffer.from('unexpected log\n')]));
  await expect(handshake).rejects.toThrow('failed during handshake');
  await expect(f.transport.request('runtime.health', {})).rejects.toThrow('unavailable');
});
it('settles pending calls when a stream closes without EOF', async () => {
  const f = fixture(); await f.ready();
  const call = f.transport.request('runtime.health', {});
  f.input.destroy();
  await expect(call).rejects.toThrow('closed');
});
