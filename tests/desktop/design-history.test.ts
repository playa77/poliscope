import { it, expect, vi } from 'vitest';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { WorkspaceController } from '../../desktop/main/workspace';
import { registerShellIPC, IPC_ERROR } from '../../desktop/main/ipc';
import type { DesktopShell } from '../../desktop/main/shell';
import type { IpcMainInvokeEvent } from 'electron';

it('grants branch actions with retained futures, same-civilization comparisons and stale rejection', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-design-history-'));
  try {
    const controller = new WorkspaceController(false, resolve('.'), '');
    await controller.choose(directory);
    const root = await controller.create({ name:'History', setup:'blank', scope_name:'Home', population:null, land_area:null });
    const preview = await controller.previewInterview({ query:{ context:root.context, scope_id:'home', domain_id:'domain:1' }, choice_id:'interview:domain-1/option-1', proposal:null, population:'125', land_area:null, rationale:'Private canary' });
    const first = (await controller.applyInterview({candidate_digest:preview.candidate_digest})).state;
    const page = await controller.lineage({context:first.context,cursor:null});
    expect((await controller.rationale({context:first.context})).text).toBe('Private canary');
    expect(page.can_undo).toBe(true); expect(page.items).toHaveLength(2);
    expect(JSON.stringify(page)).not.toContain('Private canary');
    const undo = {context:first.context,expected_sequence:first.branch.sequence,action:'undo' as const,name:null,target_revision_id:null};
    const internals = controller as unknown as {request:(...args:unknown[])=>Promise<unknown>};
    const request = internals.request.bind(controller);
    vi.spyOn(internals,'request').mockImplementationOnce(async (...args) => {await request(...args);throw new Error('lost reply');});
    await expect(controller.historyAction(undo)).rejects.toThrow('lost reply');
    await expect(controller.historyAction({...undo,action:'rename',name:'Different request'})).rejects.toThrow('Resolve pending');
    const back = await controller.historyAction(undo);
    expect(back.branch.sequence).toBe(first.branch.sequence+1);
    expect(back.context.revision_id).toBe(root.context.revision_id);
    const restored = await controller.historyAction({context:back.context,expected_sequence:back.branch.sequence,action:'redo',name:null,target_revision_id:null});
    expect(restored.context.revision_id).toBe(first.context.revision_id);
    const fork = await controller.historyAction({context:restored.context,expected_sequence:restored.branch.sequence,action:'fork',name:'Past fork',target_revision_id:root.context.revision_id});
    expect(fork.context.branch_id).toMatch(/^fork:/); expect(fork.context.revision_id).toBe(root.context.revision_id);
    expect((await controller.compare({context:fork.context,other:first.context,cursor:null})).changes.some(c=>c.id === 'population:value')).toBe(true);
    await expect(controller.compare({context:fork.context,other:{...first.context,civilization_id:'foreign'},cursor:null})).rejects.toThrow();
    await expect(controller.lineage({context:first.context,cursor:null})).rejects.toThrow();
    await controller.select({civilization_id:first.context.civilization_id,branch_id:'main',revision_id:root.context.revision_id});
    await expect(controller.historyAction({context:root.context,expected_sequence:0,action:'rename',name:'Bad',target_revision_id:null})).rejects.toThrow();
    controller.clear(); await expect(controller.lineage({context:root.context,cursor:null})).rejects.toThrow();
  } finally { await rm(directory,{recursive:true,force:true}); }
}, 30_000);

it('rejects untrusted history IPC senders, extra fields and arbitrary operations', async () => {
  const handlers = new Map<string,(event:IpcMainInvokeEvent,...args:unknown[])=>Promise<unknown>>();
  const service = {lineage:vi.fn(),compare:vi.fn(),historyAction:vi.fn()};
  const authorize = vi.fn<()=>void>(()=>{throw new Error('untrusted');});
  registerShellIPC((n,h)=>handlers.set(n,h),authorize,service as unknown as DesktopShell,vi.fn());
  for(const name of ['lineage','compare','action','rationale']) await expect(handlers.get('design-history:'+name)!({} as IpcMainInvokeEvent,{})).rejects.toThrow(IPC_ERROR);
  authorize.mockImplementation(()=>undefined);
  for(const name of ['lineage','compare','action','rationale']) for(const args of [[],[null],[{sql:'delete',path:'/etc/passwd'}],[{},'extra']]) await expect(handlers.get('design-history:'+name)!({} as IpcMainInvokeEvent,...args)).rejects.toThrow(IPC_ERROR);
  expect(service.lineage).not.toHaveBeenCalled();expect(service.compare).not.toHaveBeenCalled();expect(service.historyAction).not.toHaveBeenCalled();
});
