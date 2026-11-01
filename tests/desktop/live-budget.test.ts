import { it, expect } from 'vitest';
import { mkdtemp, rm, writeFile, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { LiveBudget } from '../live/budget';
it('one durable live budget bounds concurrent dispatches across restarts and rejects malformed receipts', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'poliscope-live-budget-'));
  try {
    let budget = await LiveBudget.acquire(directory);
    await expect(LiveBudget.acquire(directory)).rejects.toThrow();
    const first = await Promise.allSettled(Array.from({ length: 10 }, () => budget.reserve()));
    expect(first.every(r => r.status === 'fulfilled')).toBe(true);
    await budget.close();
    budget = await LiveBudget.acquire(directory);
    const final = await Promise.allSettled(Array.from({ length: 4 }, () => budget.reserve()));
    expect(final.filter(r => r.status === 'fulfilled')).toHaveLength(2);
    expect(JSON.parse(await readFile(join(directory, 'dispatches.json'), 'utf8')).posts).toBe(12);
    await budget.close();
    for (const body of ['{', '{"posts":-1}', '{"posts":13}', '{"posts":1.5}', '{"posts":"1"}']) {
      await writeFile(join(directory, 'dispatches.json'), body);
      await expect(LiveBudget.acquire(directory)).rejects.toThrow();
    }
  } finally { await rm(directory, { recursive: true, force: true }); }
});
