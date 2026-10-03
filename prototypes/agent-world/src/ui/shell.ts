import { deriveStats, type Store } from "../app/store";
import type { AppState, Mode, SourceId, Tier, Variant } from "../app/types";
import { mountCameraControls, type CameraActions } from "./camera-controls";
import { mountDetails } from "./details";
import { h } from "./dom";
import { mountRoster } from "./roster";

export interface EnvironmentChoice {
  id: string;
  name: string;
  variants: { id: Variant; label: string }[];
}

export interface ShellControls {
  /** Steps the scripted sample day. */
  step(): void;
  /** Switches between the live stream and the sample day. */
  setSource(source: SourceId): void;
}

const UNAVAILABLE = "The 3D world is unavailable on this device. Your team is still here in Dashboard mode.";
const LIVE_OFF = "Live activity is off";
// The activity switch lives in the plugin; this is where to find its script.
const WORLD_COMMAND = "python3 plugins/tafwid/skills/delegate/scripts/world.py on";

/**
 * One layout, two modes. The viewport never moves: explore floats every
 * panel over a full-screen world; dashboard arranges the same panels in a grid.
 */
export function mountShell(root: HTMLElement, store: Store, controls: ShellControls, environment: EnvironmentChoice) {
  let camera: CameraActions | null = null;

  const variantGroup = h("div", { class: "segmented", role: "group", "aria-label": `${environment.name} lighting` });
  const modeGroup = h("div", { class: "segmented", role: "group", "aria-label": "View mode" });
  const quality = h("select", { class: "quality", "aria-label": "Rendering quality" });
  for (const [value, label] of [["auto", "Quality: auto"], ["high", "High"], ["medium", "Medium"], ["low", "Low"]])
    quality.append(h("option", { value, text: label }));
  quality.addEventListener("change", () => {
    const v = quality.value;
    if (v === "auto") store.dispatch({ type: "setQuality", tier: "high", auto: true });
    else store.dispatch({ type: "setQuality", tier: v as Tier, auto: false });
  });
  const sourceGroup = h("div", { class: "segmented", role: "group", "aria-label": "Data source" });
  const samplePill = h("span", { class: "sample-pill", text: "Sample data" });
  const stepButton = h("button", { type: "button", class: "ghost-button", text: "Step the sample day" });
  stepButton.addEventListener("click", () => controls.step());

  const topbar = h(
    "header",
    { class: "topbar" },
    h(
      "div",
      { class: "bar-group", "data-hud-obstacle": "" },
      h("span", { class: "brand" }, h("span", { class: "brand-mark", "aria-hidden": "true" }), "Tafwid"),
      h("span", { class: "place", text: environment.name }),
      variantGroup,
    ),
    h("div", { class: "bar-group sample", "data-hud-obstacle": "" }, sourceGroup, samplePill, stepButton),
    h("div", { class: "bar-group", "data-hud-obstacle": "" }, quality, modeGroup),
  );

  const liveNotice = h(
    "p",
    { class: "live-notice", role: "status", "data-hud-obstacle": "" },
    "Live activity is off. Run ",
    h("code", { text: WORLD_COMMAND }),
    ".",
  );
  const stats = h("section", { class: "stats", "aria-label": "Team summary", "data-hud-obstacle": "" });
  const worldStatus = h("div", { class: "world-status", role: "status" });
  const cameraHost = h("div", { class: "camera-controls", role: "group", "aria-label": "Camera", "data-hud-obstacle": "" });
  const viewport = h("div", { class: "viewport" }, worldStatus, cameraHost);
  const rosterPanel = h("aside", { class: "roster-panel", "aria-label": "Your team", "data-hud-obstacle": "" });
  const details = h("section", { class: "details", "aria-live": "polite", "data-hud-obstacle": "" });
  const hint = h("p", { class: "hint", text: "Drag to pan · scroll to zoom · Q/E to rotate · click an agent to follow", "data-hud-obstacle": "" });
  const app = h("div", { class: "app" }, topbar, liveNotice, stats, h("main", { class: "stage" }, viewport, rosterPanel), details, hint);
  root.replaceChildren(app);

  const setHeading = mountCameraControls(cameraHost, () => camera);
  mountRoster(rosterPanel, store);
  mountDetails(details, store);

  // Segmented buttons are created once and updated in place, so keyboard focus survives updates.
  function renderSegmented(
    group: HTMLElement,
    items: { id: string; label: string }[],
    current: string,
    onPick: (id: string) => void,
    disabled = new Set<string>(),
    disabledTitle = UNAVAILABLE,
  ) {
    if (group.children.length !== items.length) {
      group.replaceChildren(
        ...items.map((item) => {
          const b = h("button", { type: "button", "data-id": item.id, text: item.label });
          b.addEventListener("click", () => onPick(item.id));
          return b;
        }),
      );
    }
    for (const b of group.querySelectorAll<HTMLButtonElement>("button")) {
      const id = b.dataset.id!;
      b.setAttribute("aria-pressed", String(id === current));
      b.disabled = disabled.has(id);
      if (disabled.has(id)) b.title = disabledTitle;
      else b.removeAttribute("title");
    }
  }

  function render(s: AppState) {
    app.dataset.mode = s.mode;
    app.dataset.source = s.source;
    // Live stays pressable while off: choosing it asks the bridge again, so turning the switch on needs no reload.
    renderSegmented(sourceGroup, [{ id: "live", label: "Live" }, { id: "sample", label: "Sample" }], s.source, (id) => controls.setSource(id as SourceId));
    const liveButton = sourceGroup.querySelector<HTMLButtonElement>('[data-id="live"]')!;
    if (s.liveEnabled) liveButton.removeAttribute("title");
    else liveButton.title = `${LIVE_OFF}. Choosing Live checks again.`;
    samplePill.hidden = s.source !== "sample";
    stepButton.hidden = s.source !== "sample";
    liveNotice.hidden = s.liveEnabled;
    renderSegmented(variantGroup, environment.variants, s.variant, (v) => store.dispatch({ type: "setVariant", variant: v as Variant }));
    renderSegmented(
      modeGroup,
      [{ id: "explore", label: "Explore" }, { id: "dashboard", label: "Dashboard" }],
      s.mode,
      (m) => store.dispatch({ type: "setMode", mode: m as Mode }),
      s.worldAvailable ? new Set() : new Set(["explore"]),
    );
    quality.value = s.qualityAuto ? "auto" : s.quality;
    const st = deriveStats(s.snapshot);
    // Live agents are never "awaiting review"; they are ready for the next message instead.
    const second = s.source === "live" ? ["ready", st.ready, "Ready"] : ["review", st.review, "Awaiting review"];
    stats.replaceChildren(
      ...[
        ["working", st.working, "Working now"],
        second,
        ["issue", st.attention, "Needs attention"],
        ["done", st.completed, "Completed this session"],
      ].map(([kind, n, label]) =>
        h("div", { class: `stat stat-${kind}` }, h("span", { class: "dot", "aria-hidden": "true" }), h("strong", { text: String(n) }), h("span", { text: String(label) })),
      ),
    );
    if (!s.worldAvailable) {
      worldStatus.textContent = UNAVAILABLE;
      worldStatus.dataset.state = "unavailable";
    } else if (s.worldError) {
      worldStatus.textContent = s.worldError;
      worldStatus.dataset.state = "error";
    } else if (worldStatus.dataset.state === "error") {
      worldStatus.dataset.state = "ready";
      worldStatus.textContent = "";
    } else if (worldStatus.dataset.state !== "ready") {
      worldStatus.textContent = `Loading ${environment.name}…`;
      worldStatus.dataset.state = "loading";
    }
  }

  render(store.get());
  store.subscribe(render);

  return {
    viewport,
    setHeading,
    attachCamera(actions: CameraActions) {
      camera = actions;
      if (store.get().worldError) return; // keep a load error visible
      worldStatus.dataset.state = "ready";
      worldStatus.textContent = "";
    },
  };
}
