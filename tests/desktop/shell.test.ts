import { it, expect, vi } from 'vitest';
import { mkdtemp, rm, mkdir, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { DesktopShell, validateSelection } from '../../desktop/main/shell';
import { BootstrapEngine } from '../../desktop/main/engine';
import type { HistorySelection } from '../../desktop/shell';
import fixtures from '../../contracts/fixtures.json';
const summary = JSON.parse(fixtures.find(f => f.name === 'evidence:incomplete')!.frame).result;
const selection: HistorySelection = { storage_context_id: 'selected', request: { history_protocol: 1, context: summary.context, result_id: summary.result_id, collection: 'summary', offset: 0, limit: 1 } };
it('rejects malformed or path-bearing selections before opening a dialog', async () => {
  const shell = new DesktopShell(false, resolve('.'), '');
  const choose = vi.fn();
  for (const value of [null, {}, { ...selection, path: '/etc/passwd' }, { ...selection, storage_context_id: '' }, { ...selection, request: { ...selection.request, offset: 1 } }]) {
    expect(() => shell.openHistory(value, choose)).toThrow();
  }
  expect(choose).not.toHaveBeenCalled();
  expect(validateSelection(selection)).toEqual(selection);
  expect(() => shell.historyPage('sql', 0)).toThrow();
  expect(() => shell.historyPage('outputs', 0.5)).toThrow();
});
it('retains current mode on cancellation and refuses overlapping operations', async () => {
  const shell = new DesktopShell(false, resolve('.'), '');
  let finish!: (value: undefined) => void;
  const pending = shell.openHistory(selection, () => new Promise(resolve => { finish = resolve; }));
  await expect(shell.reconnect()).rejects.toThrow('busy');
  finish(undefined);
  expect(await pending).toBeNull();
  expect(shell.status.state).toBe('starting');
  await shell.stop();
  await expect(shell.reconnect()).rejects.toThrow('busy');
});
it('does not launch a historical replacement after an unconfirmed engine exit', async () => {
  const stop = vi.spyOn(BootstrapEngine.prototype, 'stop').mockRejectedValueOnce(new Error('exit unconfirmed'));
  try {
    const shell = new DesktopShell(false, resolve('.'), '');
    await expect(shell.openHistory(selection, async () => '/unused.sqlite3')).rejects.toThrow('unconfirmed');
    expect(shell.status.state).toBe('starting');
    await expect(shell.historyPage('summary', 0)).rejects.toThrow('Select');
  } finally { stop.mockRestore(); }
});
it.each([false, true])('cold reads selected store after normal engine or failed handshake (failure=%s)', async failure => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-shell-'));
  let root = resolve('.');
  if (failure) {
    root = join(directory, 'runtime');
    await mkdir(join(root, '.venv/bin'), { recursive: true });
    await writeFile(join(root, '.venv/bin/python'), `#!/usr/bin/python3\nimport os, sys, time\nif 'poliscope_engine.history' in sys.argv:\n os.execv(${JSON.stringify(resolve('.venv/bin/python'))}, [${JSON.stringify(resolve('.venv/bin/python'))}] + sys.argv[1:])\nsys.stdout.write('{}\\n'); sys.stdout.flush(); time.sleep(30)\n`, { mode: 0o755 });
  }
  const shell = new DesktopShell(false, root, '');
  const saved = { history_schema: 1, summary, outputs: [], findings: [], sources: [], assumptions: [], traces: [] };
  const setup = spawnSync(resolve('.venv/bin/python'), ['-I', '-c', `import sys\nfrom pathlib import Path\nfrom poliscope_engine.storage.store import Store\nwith Store(Path(sys.argv[1])) as s:\n with s.transaction():\n  s.add_context('selected', '{}')\n  s.retain_evidence('selected', sys.argv[2], sys.argv[3])`, directory, summary.result_id, JSON.stringify(saved)], { encoding: 'utf8', timeout: 5000 });
  try {
    expect(setup.status, setup.stderr).toBe(0);
    shell.start();
    await expect.poll(() => shell.status.state).toBe(failure ? 'failed' : 'ready');
    const result = await shell.openHistory(selection, async () => join(directory, 'poliscope.sqlite3'));
    expect(result).toEqual({ history_protocol: 1, mode: 'stored_historical', result: summary });
    expect(shell.status.state).toBe('historical');
    const page = await shell.historyPage('outputs', 0);
    expect(page && 'result' in page && page.result.kind === 'evidence_page' && page.result.page.items).toEqual([]);
    await shell.reconnect();
    await expect.poll(() => shell.status.state).toBe(failure ? 'failed' : 'ready');
    await expect(shell.historyPage('summary', 0)).rejects.toThrow('Select');
  } finally { await shell.stop(); await rm(directory, { recursive: true, force: true }); }
});
