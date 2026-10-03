import type { Tier } from "../app/types";

export interface TierConfig {
  pixelRatio: number;
  shadowMapSize: number;
  /** Screen-space ambient occlusion (real-time lighting only). */
  ao: boolean;
  bloom: boolean;
  /** Tilt-shift style depth of field. */
  dof: boolean;
  /** MSAA samples for the scene pass. */
  samples: number;
  /** Step down when the 95th-percentile frame interval exceeds this (about 40 fps; 30 fps on low). */
  frameBudgetMs: number;
}

export const TIERS: Record<Tier, TierConfig> = {
  low: { pixelRatio: 1, shadowMapSize: 1024, ao: false, bloom: true, dof: false, samples: 0, frameBudgetMs: 34 },
  medium: { pixelRatio: 1.5, shadowMapSize: 2048, ao: true, bloom: true, dof: true, samples: 4, frameBudgetMs: 25 },
  high: { pixelRatio: 2, shadowMapSize: 4096, ao: true, bloom: true, dof: true, samples: 4, frameBudgetMs: 25 },
};

export const LOWER_TIER: Record<Tier, Tier | null> = { high: "medium", medium: "low", low: null };
