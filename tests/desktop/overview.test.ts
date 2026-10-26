import { it, expect, vi } from 'vitest';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import type { IpcMainInvokeEvent } from 'electron';
import { WorkspaceController, decodeWorkspace } from '../../desktop/main/workspace';
import { registerShellIPC, IPC_ERROR } from '../../desktop/main/ipc';
import type { DesktopShell } from '../../desktop/main/shell';
import { valid } from '../../desktop/main/wire';
import { STATUS, valueText } from '../../desktop/renderer/overview';

it('reads retained production observations without the saved executable model, with exact context grants', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-overview-'));
  try {
    const seed = spawnSync(resolve('.venv/bin/python'), ['tests/engine/overview_fixture.py', directory], { encoding: 'utf8' });
    expect(seed.status, seed.stderr).toBe(0);
    const controller = new WorkspaceController(false, resolve('.'), '');
    await controller.choose(directory);
    const state = await controller.select({ civilization_id: 'civ', branch_id: 'main', revision_id: null });
    const query = { context: state.context, scope_id: 'east', collection: 'indicators', item_id: null, cursor: null, all_scopes: false };
    const page = await controller.overview(query);
    expect(await controller.overview({ all_scopes: false, cursor: null, item_id: null, collection: 'indicators', scope_id: 'east', context: state.context })).toEqual(page);
    expect(page.items.find(r => r.kind === 'indicator' && r.id === 'local-reserve')).toMatchObject({ observation: { value: { value: '0' } } });
    const goal = { context: state.context, scope_id: 'east', indicator_id: 'local-reserve', operation: 'ge', threshold: { kind: 'quantity', value: '1', unit_id: 'kg', time_basis_id: null, denominator_scope_id: null } };
    expect((await controller.target(goal)).observation.matched).toBe(false);
    expect((await controller.chart({ context: state.context, scope_id: 'east', indicator_id: 'local-reserve' })).points.map(p => p.exact)).toEqual(['0', '200']);
    for (const bad of [{ ...query, path: '/etc/passwd' }, { ...query, context: { ...query.context, revision_id: 'other' } }, { ...query, scope_id: 'foreign' }]) await expect(controller.overview(bad)).rejects.toThrow();
    controller.clear();
    await expect(controller.overview(query)).rejects.toThrow();
  } finally { await rm(directory, { recursive: true, force: true }); }
}, 30_000);

it('new read-only IPC calls reject hostile callers, extra fields and unsafe target quantities', async () => {
  const handlers = new Map<string, (event: IpcMainInvokeEvent, ...args: unknown[]) => Promise<unknown>>();
  const service = { overview: vi.fn(), target: vi.fn(), chart: vi.fn() };
  const authorize = vi.fn<() => void>(() => { throw new Error('private sender'); });
  registerShellIPC((name, handler) => handlers.set(name, handler), authorize, service as unknown as DesktopShell, vi.fn());
  for (const name of ['overview:read', 'overview:target', 'overview:chart']) await expect(handlers.get(name)!({} as IpcMainInvokeEvent, {})).rejects.toThrow(IPC_ERROR);
  authorize.mockImplementation(() => undefined);
  for (const name of ['overview:read', 'overview:target', 'overview:chart']) {
    for (const args of [[], [null], [{ sql: 'select *', path: '/private' }], [{}, 'extra']]) await expect(handlers.get(name)!({} as IpcMainInvokeEvent, ...args)).rejects.toThrow(IPC_ERROR);
  }
  expect(service.overview).not.toHaveBeenCalled(); expect(service.target).not.toHaveBeenCalled(); expect(service.chart).not.toHaveBeenCalled();
  expect(() => decodeWorkspace(Buffer.from('{"overview_contract":1,"query":{},"private":"secret"}\n'), 'OverviewPage')).toThrow();
});

it('all coverage labels remain distinct and exact decimal strings never become invented zeroes', () => {
  expect(new Set(Object.values(STATUS)).size).toBe(7);
  expect(valueText({ kind: 'unknown', reason: 'Missing input' })).toBe('Unknown: Missing input');
  expect(valueText({ kind: 'quantity', value: '0.0000000000000000000000000001', unit_id: 'kg', time_basis_id: 'day', denominator_scope_id: 'group' })).toBe('0.0000000000000000000000000001 kg / day per group');
  expect(valueText({ kind: 'quantity', value: '0', unit_id: 'kg', time_basis_id: null, denominator_scope_id: null })).toBe('0 kg');
});


it('validates fixed tuple endpoints in retained feedback traces without accepting malformed edges', () => {
  const tuple = { type: 'array', minItems: 2, maxItems: 2, prefixItems: [{ type: 'array', items: { type: 'string' } }, { type: 'array', items: { type: 'string' } }] };
  expect(valid([['input', 'a', 'port'], ['output', 'a', 'port']], tuple)).toBe(true);
  expect(valid([['input'], 'malformed'], tuple)).toBe(false);
  expect(valid([['input'], ['output'], ['extra']], tuple)).toBe(false);
});
