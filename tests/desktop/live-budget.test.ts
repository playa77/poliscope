import { it, expect } from 'vitest';
import { mkdtemp, rm, writeFile, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { LiveBudget } from '../live/budget';
it('migrates every legacy reservation and bounds concurrent exposure across models and restarts', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-live-budget-'));
  try {
    await writeFile(join(directory, 'dispatches.json'), JSON.stringify({posts:19,model:'deepseek/deepseek-v4.1-flash-1017',per_dispatch_exposure_usd:'0.5'}));
    let budget = await LiveBudget.acquire(directory, 'z-ai/glm-5.3-flash');
    expect(budget.units).toBe(95);
    await expect(LiveBudget.acquire(directory)).rejects.toThrow();
    const granted = await Promise.allSettled(Array.from({length:8},()=>budget.reserve()));
    expect(granted.filter(r=>r.status==='fulfilled')).toHaveLength(5);
    await budget.close();
    const receipt=JSON.parse(await readFile(join(directory,'dispatches.json'),'utf8'));
    expect(receipt).toMatchObject({posts:24,reserved_policy_units:100,model:'z-ai/glm-5.3-flash',authorized_budget_usd:'10'});
    budget=await LiveBudget.acquire(directory);await expect(budget.reserve()).rejects.toThrow();await budget.close();
    for (const body of ['{','{"posts":-1}','{"posts":21}','{"posts":1.5}','{"posts":"1"}','{"posts":1,"reserved_policy_units":0}','{"posts":1,"reserved_policy_units":6}','{"posts":1,"reserved_policy_units":1,"policy_unit_usd":"0.01"}']) {
      await writeFile(join(directory,'dispatches.json'),body);await expect(LiveBudget.acquire(directory)).rejects.toThrow();
    }
  } finally { await rm(directory,{recursive:true,force:true}); }
});

it('a fresh workspace cannot renew an allocation already exhausted in retained evidence',async()=>{
 const directory=await mkdtemp(join(tmpdir(),'poliscope-live-budget-floor-'));
 try {
  const budget=await LiveBudget.acquire(directory,'z-ai/glm-5.3-flash',{posts:24,units:100});
  expect(budget.posts).toBe(24);expect(budget.units).toBe(100);
  await expect(budget.reserve()).rejects.toThrow('Lifetime live exposure allocation exhausted');
  await budget.close();
 }finally{await rm(directory,{recursive:true,force:true});}
});
