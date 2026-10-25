import { it, expect, vi } from 'vitest';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import type { IpcMainInvokeEvent } from 'electron';
import { WorkspaceController } from '../../desktop/main/workspace';
import { registerShellIPC, IPC_ERROR } from '../../desktop/main/ipc';
import type { DesktopShell } from '../../desktop/main/shell';

it('writes reports only to main-selected files, including cold imported evidence', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-reports-'));
  try {
    const source = new WorkspaceController(false, resolve('.'), '');
    await source.choose(join(directory, 'source'));
    await source.create({ name: 'Inquiry', setup: 'blank', scope_name: 'Home', population: '12', land_area: '3' });
    const file = join(directory, 'inquiry.md');
    const choose = vi.fn().mockResolvedValue(file);
    const receipt = await source.report({ format: 'markdown' }, choose);
    expect(choose).toHaveBeenCalledWith('markdown');
    expect(receipt).toMatchObject({ status: 'complete', format: 'markdown' });
    const text = await readFile(file, 'utf8');
    expect(text).toContain('# Poliscope inquiry report');
    expect(text).toContain('Retained historical data, not freshly reproduced');
    expect(text).toContain('"value":"12"');
    expect(text).toContain('no AI explanation');
    expect(receipt.bytes_written).toBe(Buffer.byteLength(text));
    await expect(source.report({ format: 'markdown' }, choose)).rejects.toThrow();
    expect(await readFile(file, 'utf8')).toBe(text);
    expect((await source.report({ format: 'csv' }, async () => undefined)).status).toBe('cancelled');
    await expect(source.report({ format: 'csv' }, async () => 'relative.csv')).rejects.toThrow();
    const archive = join(directory, 'portable.poliscope');
    await source.archive({ action: 'export' }, async () => archive);
    const target = new WorkspaceController(false, resolve('.'), '');
    await target.choose(join(directory, 'target'));
    const imported = await target.archive({ action: 'import' }, async () => archive);
    const csv = join(directory, 'historical.csv');
    await target.report({ format: 'csv', archive_id: imported.summaries[0].id }, async () => csv);
    expect(await readFile(csv, 'utf8')).toContain('12');
    expect((await target.catalogue()).branches).toEqual([]);
  } finally { await rm(directory, { recursive: true, force: true }); }
}, 30000);

it('rejects unauthorized, malformed and path-bearing report IPC before save selection', async () => {
  const handlers = new Map<string, (event: IpcMainInvokeEvent, ...args: unknown[]) => Promise<unknown>>();
  const report = vi.fn(), choose = vi.fn();
  const authorize = vi.fn<() => void>(() => { throw new Error('unauthorized'); });
  registerShellIPC((name, handler) => handlers.set(name, handler), authorize, { report } as unknown as DesktopShell, vi.fn(), vi.fn(), vi.fn(), choose);
  const call = (...args: unknown[]) => handlers.get('report:export')!({} as IpcMainInvokeEvent, ...args);
  await expect(call({ format: 'csv' })).rejects.toThrow(IPC_ERROR);
  authorize.mockImplementation(() => {});
  for (const input of [{ format: 'csv', path: '/private' }, { format: 'execute' }, { format: 'csv', options: { include_keys: true } }]) {
    await expect(call(input)).rejects.toThrow(IPC_ERROR);
  }
  await expect(call({ format: 'csv' }, 'extra')).rejects.toThrow(IPC_ERROR);
  expect(report).not.toHaveBeenCalled(); expect(choose).not.toHaveBeenCalled();
});
