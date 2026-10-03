import "./styles.css";
import { createFixtureSource } from "./app/fixtures";
import { createStore, initialState } from "./app/store";
import type { Variant } from "./app/types";
import { mountShell, type EnvironmentChoice } from "./ui/shell";

const ENVIRONMENTS: Record<string, EnvironmentChoice> = {
  cafe: {
    id: "cafe",
    name: "Café on the square",
    // Baked is the shipped look (ADR-0007); the kit is the real-time preview.
    variants: [
      { id: "baked", label: "Scene · baked light" },
      { id: "kit", label: "Kit · real-time light" },
    ],
  },
  placeholder: { id: "placeholder", name: "Placeholder room", variants: [{ id: "kit", label: "Kit · real-time light" }] },
};

const params = new URLSearchParams(location.search);
const environment = ENVIRONMENTS[params.get("env") ?? "cafe"] ?? ENVIRONMENTS.cafe;
const requestedVariant = params.get("variant") as Variant | null;
const variant = environment.variants.some((v) => v.id === requestedVariant) ? requestedVariant! : environment.variants[0].id;

const source = createFixtureSource(params.get("scenario") === "quiet-morning" ? "quiet-morning" : "productive-day");
const store = createStore(
  initialState(source.current(), {
    environmentId: environment.id,
    variant,
    mode: params.get("mode") === "dashboard" ? "dashboard" : "explore",
  }),
);
source.subscribe((snapshot) => store.dispatch({ type: "snapshot", snapshot }));

const shell = mountShell(document.querySelector<HTMLElement>("#app")!, store, source, environment);

async function startWorld() {
  if (params.has("forceNoWebGL")) throw new Error("WebGL disabled for testing");
  const { createWorld } = await import("./world/world");
  const world = await createWorld(shell.viewport, store, {
    forceWebGL: params.has("forceWebGL"),
    renderHidden: params.has("renderHidden"),
    onHeading: shell.setHeading,
  });
  shell.attachCamera(world.camera);
  return world;
}

startWorld().catch((e: Error) => {
  console.warn("3D world unavailable:", e.message);
  store.dispatch({ type: "worldUnavailable", reason: e.message });
});
