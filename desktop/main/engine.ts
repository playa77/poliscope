import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import { isAbsolute, join } from 'node:path';

export type BootstrapStatus = { state: 'starting' | 'ready' | 'failed'; detail: string };
export function engineCommand(packaged: boolean, root: string, resources: string, platform = process.platform) {
  const base = packaged ? resources : root;
  if (!isAbsolute(base)) throw new Error('Engine base path must be absolute');
  if (packaged) return { executable: join(resources, 'poliscope-engine', `poliscope-engine${platform === 'win32' ? '.exe' : ''}`), args: [] };
  return { executable: join(root, '.venv', platform === 'win32' ? 'Scripts/python.exe' : 'bin/python'), args: ['-I', '-m', 'poliscope_engine'] };
}

export class BootstrapEngine {
  status: BootstrapStatus = { state: 'starting', detail: 'Starting local engine' };
  private child?: ChildProcessWithoutNullStreams;
  private stopping = false;
  start(packaged: boolean, root: string, resources: string) {
    if (this.child) throw new Error('Engine already started');
    const { executable, args } = engineCommand(packaged, root, resources);
    const child = spawn(executable, args, { shell: false, windowsHide: true, stdio: 'pipe' });
    this.child = child;
    const timer = setTimeout(() => fail('Engine startup timed out'), 10_000);
    let received = false;
    let buffer = '';
    const fail = (detail: string) => {
      clearTimeout(timer);
      this.status = { state: 'failed', detail };
      child.kill();
    };
    child.on('error', () => fail('Managed engine could not start; run frozen uv setup'));
    child.stdout.on('data', (data: Buffer) => {
      if (received) return fail('Unexpected bootstrap output');
      buffer += data.toString('utf8');
      if (Buffer.byteLength(buffer) > 1024) return fail('Engine bootstrap output exceeded limit');
      if (!buffer.includes('\n')) return;
      try {
        const identity: unknown = JSON.parse(buffer.trim());
        if (!identity || typeof identity !== 'object' ||
            Object.keys(identity).sort().join(',') !== 'kind,version' ||
            !('kind' in identity) || identity.kind !== 'bootstrap-ready' ||
            !('version' in identity) || identity.version !== '0.1.0') throw new Error();
        received = true;
        clearTimeout(timer);
        this.status = { state: 'ready', detail: 'Local engine ready' };
      } catch { fail('Invalid engine bootstrap identity'); }
    });
    // Drain diagnostics, never forward uncontrolled child output to the renderer.
    child.stderr.resume();
    child.on('exit', () => {
      clearTimeout(timer);
      if (!this.stopping) this.status = { state: 'failed', detail: 'Local engine stopped' };
    });
  }
  stop(): Promise<void> {
    this.stopping = true;
    const child = this.child;
    if (!child || child.exitCode !== null || child.signalCode !== null) return Promise.resolve();
    return new Promise((resolve) => {
      const timer = setTimeout(() => child.kill(), 1500);
      child.once('exit', () => { clearTimeout(timer); resolve(); });
      child.once('error', () => { clearTimeout(timer); resolve(); });
      child.stdin.end();
    });
  }
}
