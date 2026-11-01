/** Durable lifetime policy units: USD 0.10 each, never provider actual costs.
 * Legacy dispatches reserve five units. New bounded dispatches reserve one.
 * The original USD 10 authorization remains 100 units across models/restarts.
 */
import { open, readFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
export class LiveBudget {
  private constructor(private directory: string, private lock: Awaited<ReturnType<typeof open>>, public posts: number, public units: number, private model: string) {}
  static async acquire(directory: string, model = 'z-ai/glm-5.3-flash'): Promise<LiveBudget> {
    const lock = await open(join(directory, 'live-run.lock'), 'wx', 0o600);
    try {
      let posts = 0, units = 0;
      try {
        const receipt = JSON.parse(await readFile(join(directory, 'dispatches.json'), 'utf8'));
        posts = receipt.posts;
        // Migration preserves every earlier USD 0.50 reservation, including
        // failed/lost replies. A model switch cannot renew any allowance.
        units = receipt.reserved_policy_units ?? posts * 5;
        if (receipt.policy_unit_usd != null && receipt.policy_unit_usd !== '0.1') throw new Error('Invalid policy unit');
      } catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw new Error('Invalid dispatch budget receipt'); }
      if (!Number.isSafeInteger(posts) || posts < 0 || posts > 100 || !Number.isSafeInteger(units) || units < posts || units > posts * 5 || units > 100) throw new Error('Invalid dispatch budget count');
      return new LiveBudget(directory, lock, posts, units, model);
    } catch (error) { await lock.close(); await rm(join(directory, 'live-run.lock')); throw error; }
  }
  private tail: Promise<void> = Promise.resolve();
  private closed = false;
  reserve(): Promise<void> {
    const result = this.tail.then(async () => {
      if (this.closed || this.units >= 100) throw new Error('Lifetime live exposure allocation exhausted');
      this.posts++; this.units++;
      const file = await open(join(this.directory, 'dispatches.json'), 'w', 0o600);
      try {
        await file.writeFile(JSON.stringify({posts: this.posts, reserved_policy_units: this.units, policy_unit_usd: '0.1', model: this.model, per_dispatch_exposure_usd: '0.1', maximum_reserved_exposure_usd: '10', authorized_budget_usd: '10'}) + '\n');
        await file.sync();
      } finally { await file.close(); }
    });
    this.tail = result.catch(() => {});
    return result;
  }
  async close() {
    this.closed = true; await this.tail; await this.lock.close();
    await rm(join(this.directory, 'live-run.lock'));
  }
}
