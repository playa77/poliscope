import { it, expect, vi } from 'vitest';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import type { IpcMainInvokeEvent } from 'electron';
import { QueryClient, QueryObserver } from '@tanstack/react-query';
import { WorkspaceController, decodeWorkspace } from '../../desktop/main/workspace';
import { registerShellIPC, IPC_ERROR } from '../../desktop/main/ipc';
import type { DesktopShell } from '../../desktop/main/shell';
import { contextKey } from '../../desktop/renderer/workspace';
import type { WorkspaceState } from '../../contracts/workspace';
const options = { name: 'Unanswered civilization', setup: 'blank', scope_name: 'Home', population: null, land_area: null };

// This integration test starts multiple real Python processes and opens SQLite
// stores; its total budget must allow for shared CI runner startup contention.
it('runs production create/reopen/pages with main-selected path and exact context grants', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-workspace-'));
  try {
    const controller = new WorkspaceController(false, resolve('.'), '');
    await expect(controller.create(options)).rejects.toThrow();
    expect((await controller.choose(directory)).branches).toEqual([]);
    const first = await controller.create(options);
    expect(first.goal_count).toBe(0); expect(first.policy_count).toBe(0); expect(first.mechanism_count).toBe(0);
    const query = { context: first.context, scope_id: 'home', collection: 'values', cursor: null };
    const page = await controller.page(query);
    expect(page.result.page.items).toHaveLength(2);
    expect(page.result.page.items.every(v => 'value' in v && v.value.kind === 'unknown')).toBe(true);
    await expect(controller.page({ ...query, scope_id: 'foreign' })).rejects.toThrow();
    await expect(controller.create({ ...options, path: '/private/path' })).rejects.toThrow();
    await expect(controller.select({ civilization_id: 'other', branch_id: 'main', revision_id: null })).rejects.toThrow();
    const second = await controller.create({ ...options, name: 'Second' });
    expect(second.context.civilization_id).not.toBe(first.context.civilization_id);
    await expect(controller.page(query)).rejects.toThrow('outside selected context');
    const reopened = new WorkspaceController(false, resolve('.'), '');
    const catalogue = await reopened.choose(directory);
    expect(catalogue.branches).toHaveLength(2); expect(catalogue.domains).toHaveLength(12);
    const selection = { civilization_id: first.context.civilization_id, branch_id: 'main', revision_id: null };
    expect(await reopened.select(selection)).toEqual(first);
    expect(await reopened.page(query)).toEqual(page);
    reopened.clear();
    await expect(reopened.page(query)).rejects.toThrow();
  } finally { await rm(directory, { recursive: true, force: true }); }
}, 30_000);

it('authorizes every new named IPC endpoint and rejects malformed input before invoking services', async () => {
  const handlers = new Map<string, (event: IpcMainInvokeEvent, ...args: unknown[]) => Promise<unknown>>();
  const service = { chooseWorkspace: vi.fn(), workspaceCatalogue: vi.fn(), createWorld: vi.fn(), selectWorld: vi.fn(), worldPage: vi.fn() };
  const authorize = vi.fn<() => void>(() => { throw new Error('private sender'); });
  registerShellIPC((channel, handler) => handlers.set(channel, handler), authorize, service as unknown as DesktopShell, vi.fn());
  for (const channel of ['workspace:choose', 'workspace:catalogue', 'workspace:create', 'workspace:select', 'workspace:page']) {
    await expect(handlers.get(channel)!({} as IpcMainInvokeEvent, options)).rejects.toThrow(IPC_ERROR);
  }
  authorize.mockImplementation(() => {});
  for (const [channel, args] of [ ['workspace:choose', ['path']], ['workspace:catalogue', [{}]],
    ['workspace:create', [{ ...options, path: '/etc/passwd' }]], ['workspace:select', [null]],
    ['workspace:page', [{ sql: 'select *' }]], ['workspace:create', [options, 'extra']] ] as [string, unknown[]][]) {
    await expect(handlers.get(channel)!({} as IpcMainInvokeEvent, ...args)).rejects.toThrow(IPC_ERROR);
  }
  for (const action of Object.values(service)) expect(action).not.toHaveBeenCalled();
});

it('rejects malformed, oversized and privately extended service responses', () => {
  for (const frame of ['{}\n', '{}\n{}\n', '{}', 'x'.repeat(1_048_577), '{"private_path":"/etc"}\n']) {
    expect(() => decodeWorkspace(Buffer.from(frame), 'WorkspaceState')).toThrow();
  }
});

it('late old-state responses stay in their own query cache when branch, scope or model changes', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const state = { context: { data_store_id: 'store', civilization_id: 'civ', branch_id: 'main', revision_id: 'r1' },
    versions: { world_schema: 1, catalog_id: 'catalog', model_id: 'model', numeric_runtime_id: 'runtime' },
    effective_time: { calendar_id: 'calendar', tick: 0 } } as WorkspaceState;
  let finish!: (value: string) => void;
  const old = new QueryObserver(client, { queryKey: contextKey(state, 'east', 'overview'), queryFn: () => new Promise<string>(resolve => { finish = resolve; }) });
  const unsubscribe = old.subscribe(() => {});
  const current = { ...state, context: { ...state.context, branch_id: 'alternative', revision_id: 'r2' }, versions: { ...state.versions, model_id: 'new-model' } };
  old.setOptions({ queryKey: contextKey(current, 'west', 'overview'), queryFn: async () => 'current-west' });
  await vi.waitFor(() => expect(old.getCurrentResult().data).toBe('current-west'));
  finish('old-east');
  await vi.waitFor(() => expect(client.getQueryData(contextKey(state, 'east', 'overview'))).toBe('old-east'));
  expect(old.getCurrentResult().data).toBe('current-west');
  for (const field of ['data_store_id', 'civilization_id', 'branch_id', 'revision_id'] as const) {
    expect(contextKey({ ...state, context: { ...state.context, [field]: 'changed' } }, 'east', 'overview')).not.toEqual(contextKey(state, 'east', 'overview'));
  }
  unsubscribe(); client.clear();
});
