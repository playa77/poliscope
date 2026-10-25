import { it, expect, vi } from 'vitest';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import type { IpcMainInvokeEvent } from 'electron';
import { WorkspaceController } from '../../desktop/main/workspace';
import { registerShellIPC, IPC_ERROR } from '../../desktop/main/ipc';
import type { DesktopShell } from '../../desktop/main/shell';
import type { TimelineRequest } from '../../contracts/timeline-workspace';

it('runs timeline through the actual main-selected Python/SQLite service and rejects foreign grants', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-timeline-'));
  try {
    const host = new WorkspaceController(false, resolve('.'), '');
    await host.choose(directory);
    const state = await host.create({ name: 'Timeline', setup: 'blank', scope_name: 'Home', population: null, land_area: null });
    expect((await host.timeline({ context: state.context, action: 'read', experiment_id: 'run', operation_id: 'initial' })).head).toBeNull();
    const query: TimelineRequest = { context: state.context, action: 'create', experiment_id: 'run', operation_id: 'create', sequence: 0,
      target_day: 0, other_id: null, source_revision_id: null, expected: null, control: null, after: null, indicator_id: null, realization_policy: 'preserve', seed: null, trace_offset: 0 };
    const initial = await host.timeline(query);
    const advanced = await host.timeline({ ...query, action: 'advance', operation_id: 'advance', expected: initial.head, target_day: 4 });
    expect(advanced.head?.day).toBe(4);
    const stopped = await host.timeline({ ...query, action: 'cancel', operation_id: 'cancel', control: advanced.control });
    expect(stopped.control?.state).toBe('cancelled');
    expect(stopped.entries.map(e => e.day)).toEqual([0, 4]);
    expect(await host.timeline(query)).toEqual(initial);
    await expect(host.timeline({ ...query, context: { ...state.context, civilization_id: 'foreign' } })).rejects.toThrow();
    await expect(host.timeline({ ...query, action: 'shell', path: '/private' })).rejects.toThrow();
  } finally { await rm(directory, { recursive: true, force: true }); }
}, 30_000);

it('authorizes the named timeline endpoint and rejects malformed commands before dispatch', async () => {
  const handlers = new Map<string, (event: IpcMainInvokeEvent, ...args: unknown[]) => Promise<unknown>>();
  const timeline = vi.fn();
  const authorize = vi.fn<() => void>(() => { throw new Error('unauthorized'); });
  registerShellIPC((name, handler) => handlers.set(name, handler), authorize, { timeline } as unknown as DesktopShell, vi.fn());
  await expect(handlers.get('timeline:request')!({} as IpcMainInvokeEvent, {})).rejects.toThrow(IPC_ERROR);
  expect(timeline).not.toHaveBeenCalled();
  authorize.mockImplementation(() => {});
  await expect(handlers.get('timeline:request')!({} as IpcMainInvokeEvent, { action: 'advance' })).rejects.toThrow(IPC_ERROR);
  expect(timeline).not.toHaveBeenCalled();
});
