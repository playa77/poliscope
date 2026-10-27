/** Main-owned cancellation for pure reads/previews. Mutations never enter here. */
export class QueryWork {
  private pending = new Map<string, AbortController>();
  cancel(key?: string) {
    for (const [name, controller] of this.pending) {
      if (key === undefined || name === key) {
        this.pending.delete(name);
        controller.abort();
      }
    }
  }
  async run<T>(key: string, action: (signal: AbortSignal) => Promise<T>): Promise<T> {
    this.cancel(key);
    const controller = new AbortController();
    this.pending.set(key, controller);
    try {
      const result = await action(controller.signal);
      // Even a child finishing concurrently with abort cannot publish stale data.
      if (controller.signal.aborted) throw new WorkspaceWorkStopped('work_cancelled');
      return result;
    } finally {
      if (this.pending.get(key) === controller) this.pending.delete(key);
    }
  }
}

export class WorkspaceWorkStopped extends Error {
  constructor(readonly reason: 'work_cancelled' | 'work_time_quota' | 'work_snapshot_byte_quota') {
    super(`POLISCOPE_${reason.toUpperCase()}`);
  }
}
