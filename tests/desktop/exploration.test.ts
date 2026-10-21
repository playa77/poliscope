import { it, expect, vi } from 'vitest';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import type { IpcMainInvokeEvent } from 'electron';
import { WorkspaceController, workspaceValid } from '../../desktop/main/workspace';
import { registerShellIPC, IPC_ERROR } from '../../desktop/main/ipc';
import type { DesktopShell } from '../../desktop/main/shell';

it('world edits require the selected head and exact granted candidate; matrix and readers share committed identities', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-exploration-'));
  try {
    const controller = new WorkspaceController(false, resolve('.'), '');
    await controller.choose(directory);
    const state = await controller.create({ name: 'World', setup: 'blank', scope_name: 'Home', population: '12', land_area: '3' });
    const query = { context: state.context, scope_id: 'home' };
    expect((await controller.exploration(query)).items).toHaveLength(6);
    await expect(controller.exploration({ ...query, context: { ...state.context, revision_id: 'foreign' } })).rejects.toThrow();
    await expect(controller.applyWorld({ candidate_digest: 'sha256:' + '0'.repeat(64) })).rejects.toThrow();
    const edit = { ...query, change: { kind: 'relationship', relationship: { id: 'access', from_id: 'land', to_id: 'home', relationship_kind: 'access', relationship_version: 'v1', aggregation: { kind: 'non_aggregating' }, provenance: { origin: 'player_input', source_refs: [], assumption_refs: [] } } } };
    const preview = await controller.previewWorld(edit);
    expect(preview.after).toContain('access');
    expect((await controller.exploration(query)).items).toHaveLength(6);
    await controller.cancelWorld();
    await expect(controller.applyWorld({ candidate_digest: preview.candidate_digest })).rejects.toThrow();
    const nextPreview = await controller.previewWorld(edit);
    const committed = await controller.applyWorld({ candidate_digest: nextPreview.candidate_digest });
    expect(committed.status).toBe('applied');
    expect((await controller.exploration({ ...query, context: committed.state.context })).items.some(r => r.relationship?.id === 'access')).toBe(true);
    const relation = (await controller.matrix({ ...query, context: committed.state.context })).relationships.find(r => r.world_refs?.includes('land'))!;
    expect(relation.activation).toBe('declared');
    expect((await controller.overview(relation.inspectors[0])).items[0].id).toBe('land:value');
    await controller.select({ civilization_id: state.context.civilization_id, branch_id: 'main', revision_id: state.context.revision_id });
    await expect(controller.previewWorld(edit)).rejects.toThrow('Historical state');
    expect((await controller.exploration(query)).items).toHaveLength(6);
    controller.clear(); await expect(controller.exploration(query)).rejects.toThrow();
  } finally { await rm(directory, { recursive: true, force: true }); }
}, 120000);

it('world IPC rejects hostile senders, extra properties, layout state and malformed replies before data reaches renderer', async () => {
  const handlers = new Map<string, (event: IpcMainInvokeEvent, ...args: unknown[]) => Promise<unknown>>();
  const service = { exploration: vi.fn().mockResolvedValue({ private: 'not a reply' }), previewWorld: vi.fn(), applyWorld: vi.fn(), cancelWorld: vi.fn() };
  const authorize = vi.fn<() => void>(() => { throw new Error('sender'); });
  registerShellIPC((name, handler) => handlers.set(name, handler), authorize, service as unknown as DesktopShell, vi.fn());
  const call = (...args: unknown[]) => handlers.get('world:explore')!({} as IpcMainInvokeEvent, ...args);
  const query = { context: { data_store_id: 's', civilization_id: 'c', branch_id: 'b', revision_id: 'r' }, scope_id: 'home' };
  await expect(call(query)).rejects.toThrow(IPC_ERROR);
  authorize.mockImplementation(() => {});
  for (const args of [[], [query,'extra'], [{ ...query, projection: 'terrain' }], [{ ...query, seed: 5 }]]) await expect(call(...args)).rejects.toThrow(IPC_ERROR);
  expect(service.exploration).not.toHaveBeenCalled();
  await expect(call(query)).rejects.toThrow(IPC_ERROR);
  expect(service.exploration).toHaveBeenCalledOnce();
  expect(workspaceValid({ ...query, change: { kind: 'shell', command: 'echo' } }, 'ExplorationEdit')).toBe(false);
  await expect(handlers.get('world:preview')!({} as IpcMainInvokeEvent, query)).rejects.toThrow(IPC_ERROR);
  expect(service.previewWorld).not.toHaveBeenCalled();
});
