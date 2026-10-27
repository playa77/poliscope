import { expect, it } from 'vitest';
import { QueryWork } from '../../desktop/main/query-work';

it('aborts superseded work and suppresses a concurrently completed stale response', async () => {
  const work = new QueryWork();
  let finish!: (value: string) => void;
  let oldSignal!: AbortSignal;
  const old = work.run('matrix', signal => { oldSignal = signal; return new Promise<string>(resolve => { finish = resolve; }); });
  const rejected = expect(old).rejects.toThrow('POLISCOPE_WORK_CANCELLED');
  expect(await work.run('matrix', async () => 'current')).toBe('current');
  expect(oldSignal.aborted).toBe(true);
  finish('stale'); await rejected;
});

it('cancellation on context change terminates reads without cancelling mutation work', async () => {
  const work = new QueryWork();
  let finish!: () => void;
  const result = work.run('preview', signal => new Promise<void>((resolve, reject) => {
    finish = resolve;
    signal.addEventListener('abort', () => reject(new Error('aborted')));
  }));
  const rejected = expect(result).rejects.toThrow('aborted');
  work.cancel(); await rejected;
  finish();
  expect(await work.run('preview', async () => 'new context')).toBe('new context');
});

it('a late old failure cannot clear a replacement cancellation token', async () => {
  const work = new QueryWork();
  let fail!: () => void, finish!: () => void;
  const old = work.run('atlas', () => new Promise((_, reject) => { fail = () => reject(new Error('old child')); }));
  const rejected = expect(old).rejects.toThrow('old child');
  let signal!: AbortSignal;
  const current = work.run('atlas', value => { signal = value; return new Promise<void>(resolve => { finish = resolve; }); });
  const cancelled = expect(current).rejects.toThrow('POLISCOPE_WORK_CANCELLED');
  fail(); await rejected;
  work.cancel('atlas'); expect(signal.aborted).toBe(true);
  finish(); await cancelled;
});

it('only fixed work-limit codes become visible and private diagnostics stay hidden', async () => {
  const { decodeWorkspace } = await import('../../desktop/main/workspace');
  const { WorkspaceWorkStopped } = await import('../../desktop/main/query-work');
  const { workStatus } = await import('../../desktop/renderer/work-status');
  expect(() => decodeWorkspace(Buffer.from('{"kind":"work_stopped","reason":"work_time_quota"}\n'), 'WorkspaceState')).toThrow(WorkspaceWorkStopped);
  expect(workStatus(new WorkspaceWorkStopped('work_time_quota'), 'fallback')).toContain('time limit');
  expect(workStatus(new WorkspaceWorkStopped('work_snapshot_byte_quota'), 'fallback')).toContain('working-data limit');
  expect(workStatus(new Error('/private/save'), 'fallback')).toBe('fallback');
  expect(() => decodeWorkspace(Buffer.from('{"kind":"work_stopped","reason":"/private/save"}\n'), 'WorkspaceState')).toThrow('Invalid workspace response');
});
