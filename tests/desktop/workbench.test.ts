import { it, expect, vi } from 'vitest';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import type { IpcMainInvokeEvent } from 'electron';
import { WorkspaceController, workspaceValid } from '../../desktop/main/workspace';
import { registerShellIPC, IPC_ERROR } from '../../desktop/main/ipc';
import type { DesktopShell } from '../../desktop/main/shell';
import { valid } from '../../desktop/main/wire';

it('evidence notes and goals persist through granted Preview/Apply; historical reads and deletion preserve physical identity', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-workbench-'));
  try {
    const c = new WorkspaceController(false, resolve('.'), '');
    await c.choose(directory);
    const base = await c.create({ name: 'Evidence', setup: 'blank', scope_name: 'Home', population: '12', land_area: '3' });
    const query = { context: base.context, scope_id: 'home', collection: 'notes' };
    expect((await c.workbench(query)).items).toHaveLength(0);
    const edit = { context: base.context, scope_id: 'home', change: { kind: 'note', note_kind: 'expectation', text: 'PRIVATE_CANARY: expect no new mechanisms' } };
    const preview = await c.previewWorkbench(edit);
    expect(preview.physical_before).toBe(preview.physical_after);
    await c.cancelWorkbench();
    await expect(c.applyWorkbench({ candidate_digest: preview.candidate_digest })).rejects.toThrow();
    const candidate = await c.previewWorkbench(edit);
    await expect(c.applyWorkbench({ candidate_digest: 'sha256:' + '0'.repeat(64) })).rejects.toThrow();
    const first = await c.applyWorkbench({ candidate_digest: candidate.candidate_digest });
    const note = (await c.workbench({ ...query, context: first.state.context })).items[0];
    expect(note.text).toContain('PRIVATE_CANARY');
    expect(first.state.mechanism_count).toBe(0);
    await expect(c.workbench({ ...query, context: { ...first.state.context, branch_id: 'foreign' } })).rejects.toThrow();
    await c.select({ civilization_id: base.context.civilization_id, branch_id: 'main', revision_id: base.context.revision_id });
    await expect(c.previewWorkbench(edit)).rejects.toThrow('Historical');
    expect((await c.workbench(query)).items).toHaveLength(0);
    await c.select({ civilization_id: base.context.civilization_id, branch_id: 'main', revision_id: null });
    const goal = { kind: 'goal', goal: { id: 'inquiry', kind: 'narrative', question: 'Why this arrangement?', indicator_id: null, operation: null, threshold: null } };
    const target = await c.previewWorkbench({ context: first.state.context, scope_id: 'home', change: goal });
    const second = await c.applyWorkbench({ candidate_digest: target.candidate_digest });
    expect(second.state.goal_count).toBe(1);
    expect((await c.workbench({ ...query, context: second.state.context, collection: 'goals' })).physical_output_digest).toBe(preview.physical_before);
    expect((await c.overview({ context: second.state.context, scope_id: 'home', collection: 'goals', cursor: null, all_scopes: false, item_id: null })).items[0].kind).toBe('goal');
    await c.deleteNote({ context: second.state.context, scope_id: 'home', id: note.id });
    const deleted = (await c.workbench({ ...query, context: second.state.context })).items[0];
    expect(deleted.status).toBe('deleted'); expect(deleted.text).toBeNull();
    c.clear(); await expect(c.workbench(query)).rejects.toThrow();
  } finally { await rm(directory, { recursive: true, force: true }); }
}, 120000);

it('evidence IPC rejects unauthorized senders, paths, extra arguments and malformed private replies', async () => {
  const handlers = new Map<string, (event: IpcMainInvokeEvent, ...args: unknown[]) => Promise<unknown>>();
  const service = { workbench: vi.fn().mockResolvedValue({ private: 'not a reply' }), previewWorkbench: vi.fn(), deleteNote: vi.fn() };
  const authorize = vi.fn<() => void>(() => { throw new Error('sender'); });
  registerShellIPC((name, handler) => handlers.set(name, handler), authorize, service as unknown as DesktopShell, vi.fn());
  const query = { context: { data_store_id: 's', civilization_id: 'c', branch_id: 'b', revision_id: 'r' }, scope_id: 'home', collection: 'notes' };
  const call = (...args: unknown[]) => handlers.get('evidence:read')!({} as IpcMainInvokeEvent, ...args);
  await expect(call(query)).rejects.toThrow(IPC_ERROR);
  authorize.mockImplementation(() => {});
  for (const args of [[], [query, 'extra'], [{ ...query, path: '/etc/passwd' }], [{ ...query, collection: 'private-files' }]]) await expect(call(...args)).rejects.toThrow(IPC_ERROR);
  expect(service.workbench).not.toHaveBeenCalled();
  await expect(call(query)).rejects.toThrow(IPC_ERROR);
  expect(service.workbench).toHaveBeenCalledOnce();
  const edit = { context: query.context, scope_id: 'home', change: { kind: 'note', note_kind: 'proposal', text: 'x'.repeat(2049) } };
  expect(workspaceValid(edit, 'WorkbenchEdit')).toBe(false);
  expect(workspaceValid({ ...edit, change: { kind: 'assumption', id: 'a', value: { kind: 'quantity', value: 3, unit_id: 'kg', time_basis_id: null, denominator_scope_id: null } } }, 'WorkbenchEdit')).toBe(false);
});

it('retained expression mappings enforce identifier keys, typed values and map bounds', () => {
  const rule = { type: 'object', maxProperties: 2, propertyNames: { minLength: 1, maxLength: 4 }, additionalProperties: { type: 'string', minLength: 1, maxLength: 4 } };
  expect(valid({ out: 'node' }, rule)).toBe(true);
  for (const bad of [{ '': 'node' }, { toolong: 'node' }, { out: 3 }, { out: 'node5' }, { a: 'a', b: 'b', c: 'c' }]) expect(valid(bad, rule)).toBe(false);
});

it('an interrupted evidence Apply retains its main-owned operation and rejects replacement previews until replay', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-evidence-retry-'));
  try {
    const controller = new WorkspaceController(false, resolve('.'), '');
    await controller.choose(directory);
    const state = await controller.create({ name: 'Retry', setup: 'blank', scope_name: 'Home', population: null, land_area: null });
    const edit = { context: state.context, scope_id: 'home', change: { kind: 'note', note_kind: 'model_gap', text: 'No transport model is supplied' } };
    const preview = await controller.previewWorkbench(edit);
    const internal = controller as unknown as { request: (operation: string, input: unknown, type: string, identity?: string) => Promise<unknown> };
    const original = internal.request.bind(controller);
    const identities: (string | undefined)[] = []; let drop = true;
    const intercepted = vi.spyOn(internal, 'request').mockImplementation(async (operation, input, type, identity) => {
      const reply = await original(operation, input, type, identity);
      if (operation === 'apply-workbench') { identities.push(identity); if (drop) { drop = false; throw new Error('lost reply'); } }
      return reply;
    });
    await expect(controller.applyWorkbench({ candidate_digest: preview.candidate_digest })).rejects.toThrow('lost reply');
    await expect(controller.previewWorkbench(edit)).rejects.toThrow('pending Apply');
    await expect(controller.cancelWorkbench()).rejects.toThrow('uncertain Apply');
    await expect(controller.previewWorld({ context: state.context, scope_id: 'home', change: { kind: 'value', value_id: 'land:value', value: { kind: 'label', value: 'bad' } } })).rejects.toThrow();
    const recovered = await controller.applyWorkbench({ candidate_digest: preview.candidate_digest });
    expect(recovered.status).toBe('applied'); expect(new Set(identities).size).toBe(1);
    expect((await controller.workbench({ context: recovered.state.context, scope_id: 'home', collection: 'notes' })).items).toHaveLength(1);
    intercepted.mockRestore();
  } finally { await rm(directory, { recursive: true, force: true }); }
}, 120000);
