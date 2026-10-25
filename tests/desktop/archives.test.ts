import { it, expect, vi } from 'vitest';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import type { IpcMainInvokeEvent } from 'electron';
import { WorkspaceController } from '../../desktop/main/workspace';
import { registerShellIPC, IPC_ERROR } from '../../desktop/main/ipc';
import type { DesktopShell } from '../../desktop/main/shell';

it('exports/imports through main-selected files and cold model-free historical paging', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-archives-'));
  try {
    const source = new WorkspaceController(false, resolve('.'), '');
    await source.choose(join(directory,'source'));
    await source.create({ name: 'Portable', setup: 'blank', scope_name: 'Home', population: '12', land_area: '3' });
    const file=join(directory,'portable.poliscope');
    const select=vi.fn().mockResolvedValue(file);
    const exported=await source.archive({action:'export'},select);
    expect(select).toHaveBeenCalledWith('export');
    expect(exported.summaries[0]).toMatchObject({revisions:1,branches:1,experiments:0,evidence:'complete'});
    const target=new WorkspaceController(false,resolve('.'),'');
    await target.choose(join(directory,'target'));
    const imported=await target.archive({action:'import'},select);
    expect(imported.summaries[0].id).toBe(exported.summaries[0].id);
    expect(imported.summaries[0].mode).toBe('stored_historical');
    expect(await target.archive({action:'import'},select)).toEqual(imported);
    const page=await target.archive({action:'read',archive_id:imported.summaries[0].id,offset:0},select);
    expect(page.rows?.some(r=>r.detail.includes('12'))).toBe(true);
    expect(page.heading).toContain('Revision');
    expect((await target.catalogue()).branches).toEqual([]);
    await expect(target.archive({action:'export',path:'/ungranted'},select)).rejects.toThrow();
    await expect(target.archive({action:'import'},async()=> 'relative')).rejects.toThrow();
    expect((await target.archive({action:'import'},async()=>undefined)).status).toBe('cancelled');
  } finally { await rm(directory,{recursive:true,force:true}); }
},30000);

it('rejects unauthorized/path-bearing archive IPC without opening a dialog',async()=>{
  const handlers=new Map<string,(event:IpcMainInvokeEvent,...args:unknown[])=>Promise<unknown>>();
  const archive=vi.fn(),choose=vi.fn();
  const authorize=vi.fn<() => void>(()=>{throw new Error('unauthorized');});
  registerShellIPC((name,handler)=>handlers.set(name,handler),authorize,{archive} as unknown as DesktopShell,vi.fn(),vi.fn(),choose);
  await expect(handlers.get('archive:request')!({} as IpcMainInvokeEvent,{action:'export'})).rejects.toThrow(IPC_ERROR);
  authorize.mockImplementation(()=>{});
  for(const input of [{action:'import',path:'/private'}, {action:'execute'}, {action:'export',options:{include_keys:true}}]) {
    await expect(handlers.get('archive:request')!({} as IpcMainInvokeEvent,input)).rejects.toThrow(IPC_ERROR);
  }
  expect(archive).not.toHaveBeenCalled();expect(choose).not.toHaveBeenCalled();
});
