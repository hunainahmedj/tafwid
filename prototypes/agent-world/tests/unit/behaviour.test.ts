import { describe, expect, it } from "vitest";
import valid from "./fixtures/manifest.valid.json";
import { assignZones } from "../../src/app/behaviour";
import { createFixtureSource } from "../../src/app/fixtures";
import type { EnvironmentManifest } from "../../src/contract/manifest";
import type { Agent } from "../../src/app/types";

const manifest = valid as unknown as EnvironmentManifest;
const seats = manifest.seating.flatMap((group) => group.seats);
const agents = () => structuredClone(createFixtureSource("productive-day").current().agents);
const withStatus = (list: Agent[], id: string, status: Agent["status"]) =>
  list.map((a) => (a.id === id ? { ...a, status } : a));

describe("assignZones", () => {
  it("working agents sit at the seat matching their roster index", () => {
    const list = agents();
    const result = assignZones(list, manifest);
    const ada = list.findIndex((a) => a.id === "ada");
    expect(result.get("ada")).toMatchObject({ zone: seats[ada], pose: "seated-typing" });
  });

  it("issue agents stand alert at their own seat", () => {
    const list = agents();
    const rex = list.findIndex((a) => a.id === "rex");
    expect(assignZones(list, manifest).get("rex")).toMatchObject({
      zone: seats[rex],
      pose: "standing-alert",
    });
  });

  it("review agents share review[0] with distinct offsets", () => {
    const list = withStatus(agents(), "ada", "review");
    const result = assignZones(list, manifest);
    const cleo = result.get("cleo")!, ada = result.get("ada")!;
    expect(cleo.zone).toBe(manifest.zones.review[0]);
    expect(ada.zone).toBe(manifest.zones.review[0]);
    expect(cleo.pose).toBe("standing-wave");
    expect(cleo.offset).not.toEqual(ada.offset);
  });

  it("ready agents wander the lounge loop", () => {
    expect(assignZones(agents(), manifest).get("noor")).toMatchObject({
      zone: manifest.zones.lounge[0],
      pose: "wander",
    });
  });

  it("done agents wander the lounge like ready ones", () => {
    const list = withStatus(agents(), "ada", "done");
    expect(assignZones(list, manifest).get("ada")).toMatchObject({ zone: manifest.zones.lounge[0], pose: "wander" });
  });

  it("uncertain agents stay seated like working ones", () => {
    const list = withStatus(agents(), "ada", "uncertain");
    const ada = list.findIndex((a) => a.id === "ada");
    expect(assignZones(list, manifest).get("ada")).toMatchObject({ zone: seats[ada], pose: "seated-typing" });
  });

  it("throws a named error when there are more agents than seats", () => {
    const list = agents();
    const many = Array.from({ length: seats.length + 1 }, (_, i) => ({ ...list[i % list.length], id: `agent-${i}` }));
    expect(() => assignZones(many, manifest)).toThrow(
      "13 agents but only 12 seats in this environment",
    );
  });
});
