import type { SnapshotSource } from "../app/fixtures";
import { deriveStats, type Store } from "../app/store";
import type { AppState, Mode, Tier, Variant } from "../app/types";
import { mountCameraControls, type CameraActions } from "./camera-controls";
import { mountDetails } from "./details";
import { h } from "./dom";
import { mountRoster } from "./roster";

export interface EnvironmentChoice {
  id: string;
  name: string;
  variants: { id: Variant; label: string }[];
}

const UNAVAILABLE = "The 3D world is unavailable on this device. Your team is still here in Dashboard mode.";

/**
 * One layout, two modes. The viewport never moves: explore floats every
 * panel over a full-screen world; dashboard arranges the same panels in a grid.
 */
export function mountShell(root: HTMLElement, store: Store, source: SnapshotSource, environment: EnvironmentChoice) {
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
  const stepButton = h("button", { type: "button", class: "ghost-button", text: "Step the sample day" });
  stepButton.addEventListener("click", () => source.advance());

  const topbar = h(
    "header",
    { class: "topbar" },
    h(
      "div",
      { class: "bar-group" },
      h("span", { class: "brand" }, h("span", { class: "brand-mark", "aria-hidden": "true" }), "Tafwid"),
      h("span", { class: "place", text: environment.name }),
      variantGroup,
    ),
    h("div", { class: "bar-group sample" }, h("span", { class: "sample-pill", text: "Sample data" }), stepButton),
    h("div", { class: "bar-group" }, quality, modeGroup),
  );

  const stats = h("section", { class: "stats", "aria-label": "Team summary" });
  const worldStatus = h("div", { class: "world-status", role: "status" });
  const cameraHost = h("div", { class: "camera-controls", role: "group", "aria-label": "Camera" });
  const viewport = h("div", { class: "viewport" }, worldStatus, cameraHost);
  const rosterPanel = h("aside", { class: "roster-panel", "aria-label": "Your team" });
  const details = h("section", { class: "details", "aria-live": "polite" });
  const hint = h("p", { class: "hint", text: "Drag to pan · scroll to zoom · Q/E to rotate · click an agent to follow" });
  const app = h("div", { class: "app" }, topbar, stats, h("main", { class: "stage" }, viewport, rosterPanel), details, hint);
  root.replaceChildren(app);

  const setHeading = mountCameraControls(cameraHost, () => camera);
  mountRoster(rosterPanel, store);
  mountDetails(details, store);

  function renderSegmented(group: HTMLElement, items: { id: string; label: string }[], current: string, onPick: (id: string) => void, disabled = new Set<string>()) {
    group.replaceChildren(
      ...items.map((item) => {
        const b = h("button", {
          type: "button",
          "aria-pressed": String(item.id === current),
          disabled: disabled.has(item.id),
          title: disabled.has(item.id) ? UNAVAILABLE : undefined,
          text: item.label,
        });
        b.addEventListener("click", () => onPick(item.id));
        return b;
      }),
    );
  }

  function render(s: AppState) {
    app.dataset.mode = s.mode;
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
    stats.replaceChildren(
      ...[
        ["working", st.working, "Working now"],
        ["review", st.review, "Awaiting review"],
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
      worldStatus.dataset.state = "ready";
      worldStatus.textContent = "";
    },
  };
}
