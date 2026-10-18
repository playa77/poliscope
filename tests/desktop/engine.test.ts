import { describe, expect, it } from 'vitest';
import { engineCommand, BootstrapEngine } from '../../desktop/main/engine';
import { resolve } from 'node:path';

describe('absolute engine selection', () => {
  it('uses managed Python and never PATH, even in paths with spaces', () => {
    const command = engineCommand(false, '/tmp/project with spaces', '/unused', 'linux');
    expect(command).toEqual({ executable: '/tmp/project with spaces/.venv/bin/python', args: ['-I', '-m', 'poliscope_engine'] });
  });
  it('uses a native packaged executable with no system Python fallback', () => {
    expect(engineCommand(true, '', '/tmp/resources', 'win32')).toEqual({ executable: '/tmp/resources/poliscope-engine/poliscope-engine.exe', args: [] });
    expect(() => engineCommand(false, 'relative', '/unused')).toThrow('absolute');
  });
  it('starts and stops the actual managed engine', async () => {
    const engine = new BootstrapEngine();
    engine.start(false, resolve('.'), '');
    try {
      await expect.poll(() => engine.status.state).toBe('ready');
      expect(() => engine.start(false, resolve('.'), '')).toThrow('already');
    } finally { await engine.stop(); }
  });
  it('reports a missing managed environment as a failure', async () => {
    const engine = new BootstrapEngine();
    engine.start(false, '/nonexistent/poliscope', '');
    await expect.poll(() => engine.status.state).toBe('failed');
    await engine.stop();
  });
});

import { mkdtemp, mkdir, writeFile, chmod, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
it.runIf(process.platform !== 'win32')('kills an unresponsive child even when it ignores graceful shutdown and SIGTERM', async () => {
  const root = await mkdtemp(join(tmpdir(), 'poliscope-stubborn-'));
  const executable = join(root, '.venv/bin/python');
  await mkdir(join(root, '.venv/bin'), { recursive: true });
  await writeFile(executable, `#!${resolve('.venv/bin/python')}\nimport sys,json,signal,os\nfrom pathlib import Path\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\nPath(${JSON.stringify(join(root, 'pid'))}).write_text(str(os.getpid()))\nfor line in sys.stdin:\n r=json.loads(line)\n if r['operation']=='runtime.handshake':\n  print(json.dumps(dict(protocol=1,id=r['id'],kind='result',result=dict(kind='handshake',versions=dict(application='0.1.0',schema_version=1,protocol=1)))),flush=True)\n`);
  await chmod(executable, 0o700);
  const engine = new BootstrapEngine();
  let pid: number | undefined;
  try {
    engine.start(false, root, '');
    await expect.poll(() => engine.status.state).toBe('ready');
    pid = Number(await readFile(join(root, 'pid'), 'utf8'));
    await engine.stop();
    expect(() => process.kill(pid!, 0)).toThrow();
  } finally {
    if (pid) { try { process.kill(pid, 'SIGKILL'); } catch {} }
    await engine.stop();
    await rm(root, { recursive: true, force: true });
  }
});
