import { it, expect, vi } from 'vitest';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import type { IpcMainInvokeEvent } from 'electron';
import { WorkspaceController, workspaceValid } from '../../desktop/main/workspace';
import { registerShellIPC, IPC_ERROR } from '../../desktop/main/ipc';
import type { DesktopShell } from '../../desktop/main/shell';

it('projects documentary direction through the selected grant and preserves choice/source routes', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-matrix-'));
  try {
    const controller = new WorkspaceController(false, resolve('.'), '');
    await controller.choose(directory);
    const state = await controller.create({ name: 'Matrix', setup: 'blank', scope_name: 'Home', population: null, land_area: null });
    const query = { context: state.context, scope_id: 'home', axis: 'decision' as const };
    const result = await controller.matrix(query);
    expect(result.relationship_total).toBe(1);
    expect(result.cells[0]).toMatchObject({ row_id: 'society:DEC-003', column_id: 'unmapped', relationship_type: 'supersedes', count: 1, activation: 'documentary' });
    expect(result.relationships[0].magnitude).toBeNull();
    const relation = result.relationships[0];
    expect((await controller.interview(relation.interviews[0])).query.question_id).toBe('society:DEC-003');
    expect((await controller.atlasSource(relation.sources[0])).license_text).toContain('MIT License');
    expect((await controller.matrix({ ...query, provenance: 'retained_execution' })).cells).toEqual([]);
    await expect(controller.matrix({ ...query, context: { ...state.context, revision_id: 'foreign' } })).rejects.toThrow('outside selected context');
    await expect(controller.matrix({ ...query, scope_id: 'foreign' })).rejects.toThrow();
    expect(workspaceValid({ ...query, axis: 'bad' }, 'MatrixQuery')).toBe(false);
    expect(workspaceValid({ ...query, path: '/etc/passwd' }, 'MatrixQuery')).toBe(false);
    const modelQuery = { context: state.context, kind: 'mechanism' as const, identity: 'unknown' };
    expect((await controller.matrixModel(modelQuery)).status).toBe('unavailable');
    await expect(controller.matrixModel({ ...modelQuery, context: { ...state.context, revision_id: 'foreign' } })).rejects.toThrow();
    controller.clear(); await expect(controller.matrix(query)).rejects.toThrow();
  } finally { await rm(directory, { recursive: true, force: true }); }
}, 120000);

it('rejects hostile matrix IPC before dispatch and validates response shapes', async () => {
  const handlers = new Map<string, (event: IpcMainInvokeEvent, ...args: unknown[]) => Promise<unknown>>();
  const service = { matrix: vi.fn().mockResolvedValue({ arbitrary: 'private path' }), matrixModel: vi.fn() };
  const authorize = vi.fn<() => void>(() => { throw new Error('sender'); });
  registerShellIPC((name, handler) => handlers.set(name, handler), authorize, service as unknown as DesktopShell, vi.fn());
  const call = (...args: unknown[]) => handlers.get('matrix:read')!({} as IpcMainInvokeEvent, ...args);
  const query = { context: { data_store_id: 's', civilization_id: 'c', branch_id: 'b', revision_id: 'r' }, scope_id: 'home' };
  await expect(call(query)).rejects.toThrow(IPC_ERROR);
  authorize.mockImplementation(() => {});
  for (const args of [[], [query, 'extra'], [{ ...query, execute: 'code' }], [{ ...query, relationship_type: 'causes' }]]) await expect(call(...args)).rejects.toThrow(IPC_ERROR);
  expect(service.matrix).not.toHaveBeenCalled();
  await expect(call(query)).rejects.toThrow(IPC_ERROR);
  expect(service.matrix).toHaveBeenCalledOnce();
  await expect(handlers.get('matrix:model')!({} as IpcMainInvokeEvent, { ...query, identity: 'x', kind: 'execute' })).rejects.toThrow(IPC_ERROR);
  expect(service.matrixModel).not.toHaveBeenCalled();
});
