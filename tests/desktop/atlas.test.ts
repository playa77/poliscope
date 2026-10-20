import { it, expect, vi } from 'vitest';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import type { IpcMainInvokeEvent } from 'electron';
import { WorkspaceController } from '../../desktop/main/workspace';
import { registerShellIPC, IPC_ERROR } from '../../desktop/main/ipc';
import type { DesktopShell } from '../../desktop/main/shell';
import { atlasKey } from '../../desktop/renderer/atlas';
import type { WorkspaceState } from '../../contracts/workspace';

it('discovers full source alternatives through the production selected-context grant', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-atlas-'));
  try {
    const controller = new WorkspaceController(false, resolve('.'), '');
    await controller.choose(directory);
    const state = await controller.create({ name: 'Atlas', setup: 'blank', scope_name: 'Home', population: null, land_area: null });
    const query = { context: state.context, scope_id: 'home', search: 'nutrition-complete' };
    const page = await controller.atlas(query);
    expect(page.items.map(r => r.question.id)).toContain('society:DEC-001');
    const row = page.items.find(r => r.question.id === 'society:DEC-001')!;
    expect(row.options).toHaveLength(4); expect(row.selected_id).toBeNull();
    expect(row.interview!.context).toEqual(state.context);
    const question = await controller.interview(row.interview!);
    expect(question.options.map(o => o.definition)).toEqual(row.options);
    const edit = { query: row.interview!, choice_id: 'society:DEC-001/option/D', proposal: null, population: null, land_area: null, rationale: '' };
    const preview = await controller.previewInterview(edit);
    expect(preview.alternatives).toHaveLength(4);
    const applied = await controller.applyInterview({ candidate_digest: preview.candidate_digest });
    await expect(controller.atlas(query)).rejects.toThrow('outside selected context');
    const selected = await controller.atlas({ context: applied.state.context, scope_id: 'home', selection: 'selected' });
    expect(selected.total).toBe(1); expect(selected.items[0].selected_id).toBe(edit.choice_id);
    expect(selected.items[0].archive).toBe('retained');
    expect((await controller.atlasSource({ context: applied.state.context, source_ref: 'society:source/06_global_decision_ledger.md' })).license_text).toContain('MIT License');
    await expect(controller.atlas({ ...query, context: applied.state.context, scope_id: 'foreign' })).rejects.toThrow();
    controller.clear();
    await expect(controller.atlasSource({ context: applied.state.context, source_ref: 'society:source/06_global_decision_ledger.md' })).rejects.toThrow();
  } finally { await rm(directory, { recursive: true, force: true }); }
}, 120_000);

it('rejects unauthorized and malformed atlas IPC before service calls', async () => {
  const handlers = new Map<string, (event: IpcMainInvokeEvent, ...args: unknown[]) => Promise<unknown>>();
  const service = { atlas: vi.fn(), atlasSource: vi.fn() };
  const authorize = vi.fn<() => void>(() => { throw new Error('private sender'); });
  registerShellIPC((name, handler) => handlers.set(name, handler), authorize, service as unknown as DesktopShell, vi.fn());
  for (const name of ['atlas:read', 'atlas:source']) {
    await expect(handlers.get(name)!({} as IpcMainInvokeEvent, {})).rejects.toThrow(IPC_ERROR);
    authorize.mockImplementation(() => {});
    await expect(handlers.get(name)!({} as IpcMainInvokeEvent, { path: '/etc/passwd' })).rejects.toThrow(IPC_ERROR);
    await expect(handlers.get(name)!({} as IpcMainInvokeEvent, {}, 'extra')).rejects.toThrow(IPC_ERROR);
  }
  expect(service.atlas).not.toHaveBeenCalled(); expect(service.atlasSource).not.toHaveBeenCalled();
});

it('keys late atlas replies by revision scope versions time and filters', () => {
  const state = { context: { data_store_id: 's', civilization_id: 'c', branch_id: 'b', revision_id: 'r' },
    versions: { world_schema: 1, catalog_id: 'cat', model_id: 'm', numeric_runtime_id: 'n' }, effective_time: { calendar_id: 'cal', tick: 0 } } as WorkspaceState;
  const key = atlasKey(state, 'home', { search: 'water' });
  for (const next of [ { ...state, context: { ...state.context, revision_id: 'new' } },
    { ...state, versions: { ...state.versions, catalog_id: 'new' } }, { ...state, effective_time: { ...state.effective_time, tick: 1 } } ]) {
    expect(atlasKey(next, 'home', { search: 'water' })).not.toEqual(key);
  }
  expect(atlasKey(state, 'elsewhere', { search: 'water' })).not.toEqual(key);
  expect(atlasKey(state, 'home', { search: 'food' })).not.toEqual(key);
});
