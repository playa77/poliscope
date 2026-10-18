import type { Readable, Writable } from 'node:stream';
import type { WireMessage } from '../../contracts/wire';
import { decodeFrame, encodeFrame, WireError } from './wire';

type Request = Extract<WireMessage, { operation: string }>;
type Response = Extract<WireMessage, { kind: 'result' | 'error' }>;
type Progress = Extract<WireMessage, { kind: 'progress' }>;
type Pending = { operation: Request['operation']; resolve: (message: Response) => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout>; progress?: (message: Progress) => void };
const resultKinds: Record<Request['operation'], string> = {
  'runtime.handshake': 'handshake', 'runtime.health': 'health',
  'runtime.operation_status': 'operation_status', 'runtime.cancel': 'cancel',
  'runtime.shutdown': 'shutdown', 'world.inspect': 'world_page', 'evidence.inspect': 'evidence_page',
};

/** One bounded session. Any ambiguous stream failure invalidates the entire session. */
export class EngineTransport {
  private buffer = Buffer.alloc(0);
  private pending = new Map<string, Pending>();
  private sequence = 0;
  private failed = false;
  private ready = false;
  constructor(private input: Readable, private output: Writable, private onFailure: (error: Error) => void, private timeout = 10_000) {
    input.on('data', (chunk: Buffer) => this.receive(chunk));
    input.on('end', () => this.fail(new Error('Engine stream ended')));
    input.on('close', () => this.fail(new Error('Engine stream closed')));
    output.on('close', () => this.fail(new Error('Engine write stream closed')));
    input.on('error', () => this.fail(new Error('Engine stream failed')));
    output.on('error', () => this.fail(new Error('Engine write failed')));
  }
  fail(error: Error) {
    if (this.failed) return;
    this.failed = true;
    this.buffer = Buffer.alloc(0);
    for (const call of this.pending.values()) { clearTimeout(call.timer); call.reject(error); }
    this.pending.clear();
    this.onFailure(error);
  }
  private receive(chunk: Buffer) {
    if (this.failed) return;
    // Never retain more than one bounded incomplete frame, including batched input.
    let offset = 0;
    while (offset < chunk.length) {
      const newline = chunk.indexOf(10, offset);
      const end = newline === -1 ? chunk.length : newline + 1;
      if (this.buffer.length + end - offset > 1_048_576) return this.fail(new WireError('MESSAGE_TOO_LARGE'));
      this.buffer = Buffer.concat([this.buffer, chunk.subarray(offset, end)]);
      offset = end;
      if (newline === -1) return;
      try {
        const message = decodeFrame(this.buffer);
        this.buffer = Buffer.alloc(0);
        if (!('kind' in message) || message.id === null) throw new WireError('INVALID_MESSAGE');
        const call = this.pending.get(message.id);
        if (!call) throw new WireError('INVALID_MESSAGE');
        if (message.kind === 'progress') { call.progress?.(message); continue; }
        if (message.kind === 'result' && message.result.kind !== resultKinds[call.operation]) throw new WireError('INVALID_MESSAGE');
        this.pending.delete(message.id);
        clearTimeout(call.timer);
        call.resolve(message);
      } catch { return this.fail(new WireError('INVALID_MESSAGE')); }
    }
  }
  async handshake() {
    const response = await this.request('runtime.handshake', { supported_protocols: [1] });
    if (response.kind !== 'result' || response.result.kind !== 'handshake') throw new Error('Handshake rejected');
    if (this.failed) throw new Error('Engine failed during handshake');
    this.ready = true;
  }
  request(operation: Request['operation'], params: Request['params'], progress?: (message: Progress) => void): Promise<Response> {
    if (this.failed || (!this.ready && operation !== 'runtime.handshake')) return Promise.reject(new Error('Engine unavailable'));
    // Refuse new work while Node has buffered a prior write; never build an unbounded queue.
    if (this.pending.size >= 64 || this.output.writableNeedDrain) return Promise.reject(new Error('Engine backpressure'));
    const id = `request:${++this.sequence}`;
    let frame: Uint8Array;
    try { frame = encodeFrame({ protocol: 1, id, operation, params } as Request); }
    catch (error) { return Promise.reject(error); }
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => this.fail(new Error('Engine request timed out')), this.timeout);
      this.pending.set(id, { operation, resolve, reject, timer, progress });
      try { this.output.write(frame); }
      catch { this.fail(new Error('Engine write failed')); }
    });
  }
}
