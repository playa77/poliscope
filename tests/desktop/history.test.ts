import { describe, expect, it } from 'vitest';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { HistoricalReader, historyCommand, decodeHistory } from '../../desktop/main/history';
import type { HistoryRequest } from '../../contracts/history';
import fixtures from '../../contracts/fixtures.json';
const summary = JSON.parse(fixtures.find(f => f.name === 'evidence:incomplete')!.frame).result;
const request: HistoryRequest = { history_protocol: 1, context: summary.context, result_id: summary.result_id, collection: 'summary', offset: 0, limit: 1 };
const frame = (value: unknown) => Buffer.from(JSON.stringify(value) + '\n');
const response = () => ({ history_protocol: 1, mode: 'stored_historical', result: structuredClone(summary) });

describe('independent history protocol', () => {
  it('selects bundled reader or isolated managed module', () => {
    expect(historyCommand(false, '/tmp/root', '').args).toEqual(['-I', '-m', 'poliscope_engine.history']);
    expect(historyCommand(true, '', '/tmp/resources').args).toEqual(['--history-read']);
    expect(() => historyCommand(false, 'relative', '')).toThrow();
  });
  it('validates original evidence identities and explicit historical mode', () => {
    expect(decodeHistory(frame(response()), request)).toEqual(response());
    const wrong = response(); wrong.result.context.revision_id = 'different';
    expect(() => decodeHistory(frame(wrong), request)).toThrow('binding');
    expect(() => decodeHistory(Buffer.from(JSON.stringify(response()).replace(/(\"tick\":)([0-9]+)/, '$1$2.0') + '\n'), request)).toThrow();
    const fresh = { ...response(), mode: 'reproduced' };
    expect(() => decodeHistory(frame(fresh), request)).toThrow();
    expect(() => decodeHistory(frame(response()), { ...request, collection: 'outputs' })).toThrow();
  });
  it.each([Buffer.from('{}\n'), Buffer.from([255, 10]), Buffer.alloc(1048577), Buffer.from('{}\n{}\n')])('rejects unsafe output', value => {
    expect(() => decodeHistory(value, request)).toThrow();
  });
  it('rejects schema drift and limits and correlates pages', () => {
    const page = JSON.parse(fixtures.find(f => f.name === 'evidence:outputs')!.frame).result;
    expect(() => decodeHistory(frame({ ...response(), result: page }), { ...request, collection: 'outputs' })).toThrow('page');
    expect(decodeHistory(frame({ history_protocol: 1, error: 'UNREADABLE_HISTORY' }), request)).toEqual({ history_protocol: 1, error: 'UNREADABLE_HISTORY' });
  });
});

it('cold-reads real SQLite via trusted main, with concurrency and grant checks', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-history-'));
  const reader = new HistoricalReader();
  const command = historyCommand(false, resolve('.'), '');
  const saved = { history_schema: 1, summary, outputs: [], findings: [], sources: [], assumptions: [], traces: [] };
  const setup = spawnSync(resolve('.venv/bin/python'), ['-I', '-c', `import sys\nfrom pathlib import Path\nfrom poliscope_engine.storage.store import Store\nwith Store(Path(sys.argv[1])) as s:\n with s.transaction():\n  s.add_context('selected', '{}')\n  s.retain_evidence('selected', sys.argv[2], sys.argv[3])`, directory, request.result_id, JSON.stringify(saved)], { timeout: 5000, encoding: 'utf8' });
  try {
    expect(setup.status, setup.stderr).toBe(0);
    const result = reader.read(command, join(directory, 'poliscope.sqlite3'), 'selected', request, request);
    await expect(reader.read(command, join(directory, 'poliscope.sqlite3'), 'selected', request, request)).rejects.toThrow('active');
    expect(await result).toEqual(response());
    await expect(reader.read(command, join(directory, 'poliscope.sqlite3'), 'selected', request, { ...request, result_id: 'other' })).rejects.toThrow('denied');
    await expect(reader.read(command, 'relative', 'selected', request, request)).rejects.toThrow('launch');
    expect(await reader.read(command, join(directory, 'absent'), 'selected', request, request)).toEqual({ history_protocol: 1, error: 'UNREADABLE_HISTORY' });
    await expect(reader.read({ executable: '/nonexistent', args: [] }, join(directory, 'poliscope.sqlite3'), 'selected', request, request)).rejects.toThrow('preserve');
  } finally { await rm(directory, { recursive: true, force: true }); }
});

it('bounds an untrusted child output and resets controller after failure', async () => {
  const reader = new HistoricalReader();
  await expect(reader.read({ executable: process.execPath, args: ['-e', 'process.stdout.write("x".repeat(2100000))', '--'] }, '/tmp/unused', 'selected', request, request)).rejects.toThrow();
  await expect(reader.read({ executable: process.execPath, args: ['-e', 'process.exit(1)', '--'] }, '/tmp/unused', 'selected', request, request)).rejects.toThrow('preserve');
});
