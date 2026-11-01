/** One live-run lock and durable dispatch count, independent of provider usage.
 * A lost reply or restart cannot restore permission to spend. No credentials,
 * prompts, completions or account metadata are accepted by this receipt.
 */
import { open, readFile, writeFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
export class LiveBudget {
  private constructor(private directory: string, private lock: Awaited<ReturnType<typeof open>>, public posts: number) {}
  static async acquire(directory: string): Promise<LiveBudget> {
    const lock = await open(join(directory, 'live-run.lock'), 'wx', 0o600);
    try {
      let posts = 0;
      try { posts = JSON.parse(await readFile(join(directory, 'dispatches.json'), 'utf8')).posts; }
      catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw new Error('Invalid dispatch budget receipt'); }
      if (!Number.isSafeInteger(posts) || posts < 0 || posts > 12) throw new Error('Invalid dispatch budget count');
      return new LiveBudget(directory, lock, posts);
    } catch (error) { await lock.close(); await rm(join(directory, 'live-run.lock')); throw error; }
  }
  private tail: Promise<void> = Promise.resolve();
  private closed = false;
  reserve(): Promise<void> {
    const result = this.tail.then(async () => {
      if (this.closed || this.posts >= 12) throw new Error('Lifetime live dispatch count exhausted');
      this.posts++;
      // Persist before returning permission to transmit. A partial write on a
      // crash produces an unreadable receipt and blocks future sends.
      const file = await open(join(this.directory, 'dispatches.json'), 'w', 0o600);
      try {
        await file.writeFile(JSON.stringify({ posts: this.posts, model: 'deepseek/deepseek-v4.1-flash-1017', per_dispatch_exposure_usd: '0.5', maximum_reserved_exposure_usd: '6', authorized_budget_usd: '10' }) + '\n');
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
