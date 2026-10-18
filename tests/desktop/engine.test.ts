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
