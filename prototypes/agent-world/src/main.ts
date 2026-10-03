import "./styles.css";
import { createFixtureSource, type SnapshotSource } from "./app/fixtures";
import { createStore, initialState } from "./app/store";
import type { SourceId, Variant } from "./app/types";
import { createLiveSource, parseLiveMessage, toSnapshot, type LiveMessage, type LiveSource } from "./live/live-source";
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

const SNAPSHOT_URL = "/api/world/snapshot";

/** Asks the bridge whether live activity is on; null when it cannot be reached. */
async function fetchLive(): Promise<LiveMessage | null> {
  try {
    const res = await fetch(SNAPSHOT_URL, { cache: "no-store", signal: AbortSignal.timeout(3000) });
    return res.ok ? parseLiveMessage(await res.text()) : null;
  } catch {
    return null;
  }
}

const sample = createFixtureSource(params.get("scenario") === "quiet-morning" ? "quiet-morning" : "productive-day");
// Live is the default; it falls back to the sample day when the bridge says it is off or cannot be reached.
const first = await fetchLive();
const startLive = params.get("source") !== "sample" && first?.enabled === true;

let live: LiveSource | null = null;
let unsubscribe = () => {};
let startedSwitch = 0;

function openLive(message: LiveMessage): LiveSource | null {
  try {
    return createLiveSource(undefined, { initial: message });
  } catch (e) {
    console.warn("Live stream unavailable:", (e as Error).message);
    return null;
  }
}

if (startLive) live = openLive(first!);
const active: SnapshotSource = live ?? sample;

const store = createStore(
  initialState(active.current(), {
    environmentId: environment.id,
    variant,
    mode: params.get("mode") === "dashboard" ? "dashboard" : "explore",
    source: live ? "live" : "sample",
    liveEnabled: first?.enabled === true,
  }),
);

function follow(next: SnapshotSource) {
  unsubscribe();
  unsubscribe = next.subscribe((snapshot) => {
    store.dispatch({ type: "snapshot", snapshot });
    if (!live || next !== live) return;
    store.dispatch({ type: "setLiveEnabled", enabled: live.enabled() });
    if (!live.enabled()) void setSource("sample"); // switched off while watching
  });
}
follow(active);

async function setSource(next: SourceId) {
  const request = ++startedSwitch;
  if (next === "sample") {
    live?.stop();
    live = null;
    follow(sample);
    store.dispatch({ type: "setSource", source: "sample", snapshot: sample.current() });
    return;
  }
  if (store.get().source === "live") return;
  const message = await fetchLive();
  if (request !== startedSwitch) return; // a later choice wins
  store.dispatch({ type: "setLiveEnabled", enabled: message?.enabled === true });
  if (!message?.enabled) return; // stay on the sample day; the notice explains
  live = openLive(message);
  if (!live) return;
  follow(live);
  store.dispatch({ type: "setSource", source: "live", snapshot: live.current() });
}

const shell = mountShell(
  document.querySelector<HTMLElement>("#app")!,
  store,
  { step: () => sample.advance(), setSource: (id) => void setSource(id) },
  environment,
);

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
