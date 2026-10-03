import type { EnvironmentManifest, Vec2, Zone } from "../contract/manifest";
import type { Agent } from "./types";

export type Pose = "seated-typing" | "standing-wave" | "wander" | "standing-alert";

export interface Assignment {
  zone: Zone;
  pose: Pose;
  /** World-space offset so agents sharing a zone do not overlap. */
  offset: Vec2;
}

// Spots around a shared zone, in world units.
const SHARED_OFFSETS: Vec2[] = [[0, 0], [0.9, 0.3], [-0.9, 0.3], [0.5, 1], [-0.5, 1]];

/**
 * Maps status to a place: each agent owns the workstation at its roster
 * index; review agents share the review spot; ready agents walk the lounge.
 */
export function assignZones(agents: Agent[], zones: EnvironmentManifest["zones"]): Map<string, Assignment> {
  if (agents.length > zones.workstation.length)
    throw new Error(
      `${agents.length} agents but only ${zones.workstation.length} workstations in this environment`,
    );
  const result = new Map<string, Assignment>();
  let reviewers = 0;
  let loungers = 0;
  agents.forEach((agent, index) => {
    const desk = zones.workstation[index];
    switch (agent.status) {
      case "working":
        result.set(agent.id, { zone: desk, pose: "seated-typing", offset: [0, 0] });
        break;
      case "issue":
        result.set(agent.id, { zone: desk, pose: "standing-alert", offset: [0, 0] });
        break;
      case "review": {
        const i = reviewers++;
        result.set(agent.id, {
          zone: zones.review[i % zones.review.length],
          pose: "standing-wave",
          offset: SHARED_OFFSETS[Math.floor(i / zones.review.length) % SHARED_OFFSETS.length],
        });
        break;
      }
      case "ready": {
        const i = loungers++;
        result.set(agent.id, {
          zone: zones.lounge[i % zones.lounge.length],
          pose: "wander",
          offset: SHARED_OFFSETS[Math.floor(i / zones.lounge.length) % SHARED_OFFSETS.length],
        });
        break;
      }
    }
  });
  return result;
}
