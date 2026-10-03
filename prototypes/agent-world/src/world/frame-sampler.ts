/** Rolling frame-time statistics used for adaptive quality and the performance readout. */
export function createFrameSampler(windowSize = 120) {
  const samples: number[] = [];
  const percentile = (sorted: number[], p: number) => sorted[Math.max(0, Math.ceil((p / 100) * sorted.length) - 1)] ?? 0;
  return {
    push(ms: number) {
      samples.push(ms);
      if (samples.length > windowSize) samples.shift();
    },
    stats() {
      const sorted = [...samples].sort((a, b) => a - b);
      return { p50: percentile(sorted, 50), p95: percentile(sorted, 95), count: samples.length };
    },
    /** True once the window is full and the 95th percentile exceeds the budget. */
    shouldStepDown(budgetMs: number) {
      return samples.length >= windowSize && this.stats().p95 > budgetMs;
    },
    reset() {
      samples.length = 0;
    },
  };
}
export type FrameSampler = ReturnType<typeof createFrameSampler>;
