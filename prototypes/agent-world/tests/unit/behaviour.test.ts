import { describe, expect, it } from "vitest";
import valid from "./fixtures/manifest.valid.json";
import { assignZones } from "../../src/app/behaviour";
import { createFixtureSource } from "../../src/app/fixtures";
import type { EnvironmentManifest } from "../../src/contract/manifest";
import type { Agent } from "../../src/app/types";

const zones = (valid as unknown as EnvironmentManifest).zones;
const agents = () => structuredClone(createFixtureSource("productive-day").current().agents);
const withStatus = (list: Agent[], id: string, status: Agent["status"]) =>
  list.map((a) => (a.id === id ? { ...a, status } : a));

describe("assignZones", () => {
  it("working agents sit at the workstation matching their roster index", () => {
    const list = agents();
    const result = assignZones(list, zones);
    const ada = list.findIndex((a) => a.id === "ada");
    expect(result.get("ada")).toMatchObject({ zone: zones.workstation[ada], pose: "seated-typing" });
  });

  it("issue agents stand alert at their own workstation", () => {
    const list = agents();
    const rex = list.findIndex((a) => a.id === "rex");
    expect(assignZones(list, zones).get("rex")).toMatchObject({
      zone: zones.workstation[rex],
      pose: "standing-alert",
    });
  });

  it("review agents share review[0] with distinct offsets", () => {
    const list = withStatus(agents(), "ada", "review");
    const result = assignZones(list, zones);
    const cleo = result.get("cleo")!, ada = result.get("ada")!;
    expect(cleo.zone).toBe(zones.review[0]);
    expect(ada.zone).toBe(zones.review[0]);
    expect(cleo.pose).toBe("standing-wave");
    expect(cleo.offset).not.toEqual(ada.offset);
  });

  it("ready agents wander the lounge loop", () => {
    expect(assignZones(agents(), zones).get("noor")).toMatchObject({
      zone: zones.lounge[0],
      pose: "wander",
    });
  });

  it("throws a named error when there are more agents than workstations", () => {
    const list = agents();
    const many = [...list, ...list.map((a) => ({ ...a, id: a.id + "-2" }))];
    expect(() => assignZones(many, zones)).toThrow(
      "10 agents but only 6 workstations in this environment",
    );
  });
});
