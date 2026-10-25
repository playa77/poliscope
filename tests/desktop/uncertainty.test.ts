import { it, expect, vi } from 'vitest';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import type { IpcMainInvokeEvent } from 'electron';
import { WorkspaceController } from '../../desktop/main/workspace';
import { registerShellIPC, IPC_ERROR } from '../../desktop/main/ipc';
import type { DesktopShell } from '../../desktop/main/shell';
import type { UncertaintyModel } from '../../contracts/uncertainty';

const model: UncertaintyModel = { id: 'hypothetical', version: 'v1', method: 'affine-box-v1', dependence: 'declared_box',
  parameters: [{ id: 'population', version: 'v1', value_id: 'population:value', form: 'bounded_range', point: null, low: '2', high: '5',
    interpretation: 'Hypothetical population range', source_refs: [], assumption_refs: ['hypothesis'] }],
  expressions: [{ id: 'selected', version: 'v1', constant: '0', terms: [{ variable_id: 'population', coefficient: '1' }], threshold: '4', operation: 'lt', interpretation: 'Below selected threshold' }],
  factors: [], assumption_refs: ['hypothesis'], assumptions: [{ id: 'hypothesis', version: 'v1', rationale: 'Explicit hypothetical box; no inferred probability' }], state_limit: 100 };

it('runs exact reports and pure sensitivity through real selected Python/SQLite and rejects foreign/malformed grants', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-uncertainty-'));
  try {
    const host = new WorkspaceController(false, resolve('.'), '');
    await host.choose(directory);
    const state = await host.create({ name: 'Uncertainty', setup: 'blank', scope_name: 'Home', population: '10', land_area: null });
    const request = { context: state.context, model };
    const report = await host.uncertainty(request);
    expect(report.observations[0]).toMatchObject({ low: '2', high: '5', diagnostic: 'overlap', probability: null, unit_id: 'people', scope_id: 'home' });
    const comparison = await host.sensitivity({ ...request, variants: [
      { id: 'A', values: [{ variable_id: 'population', value: '2', selection_ref: 'player:low' }] },
      { id: 'B', values: [{ variable_id: 'population', value: '5', selection_ref: 'player:high' }] }] });
    expect(comparison.variants.map(v => v.selected.values[0].value)).toEqual(['2', '5']);
    expect(comparison.variants[0].physical_digest).not.toBe(comparison.variants[1].physical_digest);
    expect((await host.catalogue()).branches[0].context).toEqual(state.context);
    await expect(host.uncertainty({ ...request, context: { ...state.context, revision_id: 'foreign' } })).rejects.toThrow();
    await expect(host.uncertainty({ ...request, model: { ...model, expression: 'exec' } })).rejects.toThrow();
    await expect(host.uncertainty({ ...request, path: '/private' })).rejects.toThrow();
  } finally { await rm(directory, { recursive: true, force: true }); }
}, 30_000);

it('rejects malformed uncertainty, sensitivity and capacity IPC before any service call', async () => {
  const handlers = new Map<string, (event: IpcMainInvokeEvent, ...args: unknown[]) => Promise<unknown>>();
  const uncertainty = vi.fn(), sensitivity = vi.fn(), capacity = vi.fn();
  const authorize = vi.fn<() => void>(() => { throw new Error('unauthorized'); });
  registerShellIPC((name, handler) => handlers.set(name, handler), authorize, { uncertainty, sensitivity, capacity } as unknown as DesktopShell, vi.fn());
  for (const name of ['uncertainty:read', 'uncertainty:sensitivity', 'uncertainty:capacity']) {
    await expect(handlers.get(name)!({} as IpcMainInvokeEvent, {})).rejects.toThrow(IPC_ERROR);
  }
  authorize.mockImplementation(() => {});
  for (const name of ['uncertainty:read', 'uncertainty:sensitivity', 'uncertainty:capacity']) {
    await expect(handlers.get(name)!({} as IpcMainInvokeEvent, { script: 'execute' })).rejects.toThrow(IPC_ERROR);
  }
  expect(uncertainty).not.toHaveBeenCalled(); expect(sensitivity).not.toHaveBeenCalled(); expect(capacity).not.toHaveBeenCalled();
});
