/** Only fixed, nonprivate main error codes become user-facing work status. */
export function workStatus(error: unknown, fallback: string): string {
  const message = error instanceof Error ? error.message : '';
  if (message.includes('POLISCOPE_WORK_TIME_QUOTA')) return 'The calculation reached its time limit. No partial result is shown. Inspect saved boundaries before retrying an Apply.';
  if (message.includes('POLISCOPE_WORK_SNAPSHOT_BYTE_QUOTA')) return 'The calculation reached its working-data limit. No truncated result is shown. Saved history is retained.';
  if (message.includes('POLISCOPE_WORK_CANCELLED')) return 'Calculation cancelled. Saved history is retained.';
  return fallback;
}
