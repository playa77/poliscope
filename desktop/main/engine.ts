import { EngineTransport } from './transport';
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
  private transport?: EngineTransport;
  start(packaged: boolean, root: string, resources: string) {
    if (this.child) throw new Error('Engine already started');
    const { executable, args } = engineCommand(packaged, root, resources);
    const child = spawn(executable, args, { shell: false, windowsHide: true, stdio: 'pipe', env: Object.fromEntries(['SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'LANG', 'LC_ALL'].flatMap(key => process.env[key] === undefined ? [] : [[key, process.env[key]!]])) });
    this.child = child;
    const transport = new EngineTransport(child.stdout, child.stdin, () => {
      if (!this.stopping) this.status = { state: 'failed', detail: 'Local engine transport failed' };
      child.kill();
      const escalation = setTimeout(() => { if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL'); }, 1000);
      escalation.unref();
      child.once('exit', () => clearTimeout(escalation));
    });
    this.transport = transport;
    child.on('error', () => transport.fail(new Error('Managed engine could not start')));
    void transport.handshake().then(() => {
      if (!this.stopping) this.status = { state: 'ready', detail: 'Local engine ready' };
    }).catch(() => transport.fail(new Error('Engine handshake failed')));
    // Drain diagnostics, never forward uncontrolled child output to the renderer.
    child.stderr.resume();
    child.on('exit', () => {
      transport.fail(new Error('Local engine stopped'));
      if (!this.stopping) this.status = { state: 'failed', detail: 'Local engine stopped' };
    });
  }
  stop(): Promise<void> {
    this.stopping = true;
    const child = this.child;
    if (!child || !child.pid || child.exitCode !== null || child.signalCode !== null) return Promise.resolve();
    return new Promise((resolve, reject) => {
      let finished = false;
      const finish = () => { if (finished) return; finished = true; clearTimeout(terminate); clearTimeout(kill); clearTimeout(deadline); resolve(); };
      const terminate = setTimeout(() => child.kill(), 1500);
      const kill = setTimeout(() => child.kill('SIGKILL'), 2500);
      const deadline = setTimeout(() => {
        if (finished) return;
        finished = true;
        clearTimeout(terminate); clearTimeout(kill);
        reject(new Error('Engine exit unconfirmed'));
      }, 3500);
      child.once('exit', finish);
      void this.transport?.request('runtime.shutdown', {}).finally(() => child.stdin.end()).catch(() => {});
    });
  }
}
