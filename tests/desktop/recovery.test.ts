import { it, expect, vi } from 'vitest';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { WorkspaceController } from '../../desktop/main/workspace';
import { RecoveryController } from '../../desktop/main/recovery';
import { registerShellIPC, IPC_ERROR } from '../../desktop/main/ipc';
import type { DesktopShell } from '../../desktop/main/shell';
import type { IpcMainInvokeEvent } from 'electron';

it('cold discovers, backs up, restores and idempotently migrates from main file grants', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-recovery-'));
  try {
    const source = join(directory, 'source'), database = join(source, 'poliscope.sqlite3');
    const workspace = new WorkspaceController(false, resolve('.'), '');
    await workspace.choose(source);
    const state = await workspace.create({ name: 'Retained', setup: 'blank', scope_name: 'Home', population: '12', land_area: null });
    const cold = new RecoveryController(false, resolve('.'), '');
    const choose = vi.fn().mockResolvedValue(database);
    const catalogue = await cold.request({ action: 'inspect' }, choose);
    expect(catalogue.branches?.[0].context).toEqual(state.context);
    expect(choose).toHaveBeenCalledWith('source');
    const read = await cold.request({ action: 'read', context: state.context }, choose);
    expect(read.detail).toContain('not freshly reproduced');
    const backup = join(directory, 'backup.sqlite3'); choose.mockResolvedValue(backup);
    expect((await cold.request({ action: 'backup' }, choose)).status).toBe('complete');
    const bytes = await readFile(backup);
    expect((await cold.request({ action: 'backup' }, choose)).diagnostic).toBe('save_failed');
    expect(await readFile(backup)).toEqual(bytes);
    const restored = join(directory, 'restored'); choose.mockResolvedValue(restored);
    expect((await cold.request({ action: 'restore' }, choose)).status).toBe('complete');
    expect((await cold.request({ action: 'restore' }, choose)).status).toBe('failed');
    const first = await cold.request({ action: 'migrate-model', context: state.context, name: 'New comparison' }, choose);
    expect(first.status).toBe('complete');
    const restarted = new RecoveryController(false, resolve('.'), '');
    await restarted.request({ action: 'inspect' }, async () => database);
    const replay = await restarted.request({ action: 'migrate-model', context: state.context, name: 'New comparison', offset: 9, detail_offset: 7 }, choose);
    expect(replay).toEqual(first);
    expect((await workspace.catalogue()).branches).toHaveLength(2);
    await expect(cold.request({ action: 'read', context: { ...state.context, civilization_id: 'other' } }, choose)).rejects.toThrow();
  } finally { await rm(directory, { recursive: true, force: true }); }
}, 30000);

it('rejects path-bearing IPC and unauthorized recovery before dialogs or launches', async () => {
  const handlers = new Map<string, (event: IpcMainInvokeEvent, ...args: unknown[]) => Promise<unknown>>();
  const recovery = vi.fn(), choose = vi.fn();
  registerShellIPC((c,h) => handlers.set(c,h), () => {}, { recovery } as unknown as DesktopShell, choose);
  for (const input of [{ action: 'inspect', path: '/etc/passwd' }, { action: 'sql' }, { action: 'read', offset: -1 }]) {
    await expect(handlers.get('recovery:request')!({} as IpcMainInvokeEvent,input)).rejects.toThrow(IPC_ERROR);
  }
  expect(recovery).not.toHaveBeenCalled(); expect(choose).not.toHaveBeenCalled();
});
