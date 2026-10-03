import * as THREE from "three/webgpu";
import type { Store } from "../app/store";
import type { AppState, Variant } from "../app/types";
import { assignZones } from "../app/behaviour";
import { AgentLayer } from "./agents";
import { AmbientLayer } from "./ambient";
import { cameraPose, createRig, follow, FOV_DEGREES, goHome, pan, rotate, step, zoom, type RigState } from "./camera-rig";
import { EnvironmentLoadError, loadEnvironment, type LoadedEnvironment } from "./environment";
import { createFrameSampler } from "./frame-sampler";
import { Overlay } from "./overlay";
import { createRenderer } from "./renderer";
import { LOWER_TIER, TIERS } from "./tiers";

export interface World {
  backend: "webgpu" | "webgl";
  camera: { rotate(dir: 1 | -1): void; zoom(delta: number): void; home(): void };
  /** Re-reads the host size; call after moving the viewport between layouts. */
  resize(): void;
  dispose(): void;
}

export interface WorldOptions {
  forceWebGL?: boolean;
  /** Debug: keep rendering on a timer even when the page is hidden (evidence capture). */
  renderHidden?: boolean;
  onHeading?: (yaw: number) => void;
}

declare global {
  interface Window {
    __tafwidPerf?: () => { p50: number; p95: number; count: number; tier: string; backend: string };
    __tafwidAmbientEnabled?: boolean;
    __tafwidWorldReady?: boolean;
    __tafwidStats?: () => { calls: number; triangles: number; meshes: number; instanced: number };
  }
}

const FOLLOW_DISTANCE = 30;
const reducedMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");

export async function createWorld(host: HTMLElement, store: Store, options: WorldOptions = {}): Promise<World> {
  const canvas = document.createElement("canvas");
  canvas.className = "world-canvas";
  canvas.setAttribute("aria-label", "3D view of your agents. Use the roster or badges to select an agent.");
  host.prepend(canvas);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(FOV_DEGREES, 16 / 9, 0.5, 400);
  const view = await createRenderer(canvas, scene, camera, store.get().quality, options.forceWebGL);
  const agents = new AgentLayer(scene);
  const ambient = new AmbientLayer(scene);
  const overlay = new Overlay(host, (id) => store.dispatch({ type: "select", id }));
  const sampler = createFrameSampler(120);
  const raycaster = new THREE.Raycaster();

  let env: LoadedEnvironment | null = null;
  let rig: RigState | null = null;
  let loading: Promise<void> | null = null;
  let disposed = false;
  let lastHeading = NaN;

  /** Frames all agents (dashboard mode): centre on their bounding box, distance from its size. */
  function fitAgents() {
    if (!rig || !env) return;
    const pts = store.get().snapshot.agents.map((a) => agents.groundOf(a.id)).filter((p): p is [number, number] => !!p);
    if (!pts.length) return;
    const xs = pts.map((p) => p[0]), zs = pts.map((p) => p[1]);
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cz = (Math.min(...zs) + Math.max(...zs)) / 2;
    const spread = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...zs) - Math.min(...zs));
    const [lo, hi] = env.manifest.camera.zoom;
    rig = { ...rig, followId: null, glideTo: [cx, cz + 1.5], distanceGoal: Math.min(hi, Math.max(lo, spread * 2.1 + 16)) };
  }

  async function setEnvironment(id: string, variant: Variant) {
    store.dispatch({ type: "worldError", message: null });
    try {
      const next = await loadEnvironment(`${import.meta.env.BASE_URL}environments/${id}/${variant}`);
      if (disposed) return next.dispose();
      env?.dispose();
      env = next;
      scene.add(next.root);
      view.setEnvironment(next.manifest);
      agents.setEnvironment(next);
      ambient.setEnvironment(next);
      const keepFollow = rig?.followId ?? null;
      rig = follow(createRig(next.manifest.camera.home), keepFollow);
      syncAgents(store.get());
      window.__tafwidWorldReady = true;
    } catch (e) {
      const message = e instanceof EnvironmentLoadError ? e.message : `The environment could not be shown: ${(e as Error).message}`;
      store.dispatch({ type: "worldError", message });
    }
  }

  function syncAgents(s: AppState) {
    overlay.sync(s.snapshot.agents, s.selectedId);
    if (!env) return;
    try {
      agents.sync(s.snapshot.agents, assignZones(s.snapshot.agents, env.manifest.zones));
    } catch (e) {
      store.dispatch({ type: "worldError", message: (e as Error).message });
    }
  }

  store.subscribe((s, prev) => {
    if (s.snapshot !== prev.snapshot || s.selectedId !== prev.selectedId) syncAgents(s);
    if (s.selectedId !== prev.selectedId && rig) {
      rig = follow(rig, s.selectedId);
      // Frame the followed agent closely enough to read their pose.
      if (s.selectedId && env && rig.distanceGoal > FOLLOW_DISTANCE) rig = zoom(rig, FOLLOW_DISTANCE - rig.distanceGoal, env.manifest.camera.zoom);
    }
    agents.selectedId = s.selectedId;
    if (s.mode !== prev.mode) {
      view.setFocusRangeScale(s.mode === "dashboard" ? 3 : 1);
      if (s.mode === "dashboard" && !s.selectedId) fitAgents();
      else if (s.mode === "explore" && !s.selectedId) api.camera.home();
    }
    if (s.quality !== prev.quality) {
      view.setTier(s.quality);
      sampler.reset();
    }
    if (s.variant !== prev.variant || s.environmentId !== prev.environmentId)
      loading = setEnvironment(s.environmentId, s.variant);
  });

  // Input: drag to pan, click to select, wheel to zoom, Q/E to rotate.
  let drag: { x: number; y: number; moved: number } | null = null;
  canvas.addEventListener("pointerdown", (e) => {
    drag = { x: e.clientX, y: e.clientY, moved: 0 };
    canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!drag || !rig || !env) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    drag = { x: e.clientX, y: e.clientY, moved: drag.moved + Math.abs(dx) + Math.abs(dy) };
    if (drag.moved < 4) return;
    if (rig.followId) store.dispatch({ type: "select", id: null });
    rig = pan(rig, dx, dy, canvas.clientHeight, env.manifest.camera.bounds);
  });
  canvas.addEventListener("pointerup", (e) => {
    const wasClick = drag && drag.moved < 4;
    drag = null;
    if (!wasClick) return;
    const r = canvas.getBoundingClientRect();
    raycaster.setFromCamera(
      new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1),
      camera,
    );
    store.dispatch({ type: "select", id: agents.pick(raycaster) });
  });
  canvas.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault();
      if (rig && env) rig = zoom(rig, e.deltaY * 0.03, env.manifest.camera.zoom);
    },
    { passive: false },
  );
  const onKey = (e: KeyboardEvent) => {
    const tag = (e.target as HTMLElement)?.tagName;
    if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
    if (e.key === "Escape") return store.dispatch({ type: "select", id: null });
    if (!host.matches(":hover") && !host.contains(document.activeElement)) return;
    if (e.key === "q" || e.key === "Q") api.camera.rotate(1);
    else if (e.key === "e" || e.key === "E") api.camera.rotate(-1);
  };
  window.addEventListener("keydown", onKey);

  const resizeObserver = new ResizeObserver(() => api.resize());
  resizeObserver.observe(host);

  let last = performance.now();
  function frame() {
    const now = performance.now();
    const dtMs = now - last;
    last = now;
    const dt = Math.min(dtMs / 1000, 0.25);
    const time = now / 1000;
    const reduced = reducedMotionQuery.matches;
    ambient.setEnabled(!reduced);
    window.__tafwidAmbientEnabled = ambient.isEnabled;
    agents.update(dt, time);
    ambient.update(dt, time);
    if (rig) {
      rig = step(rig, dt, rig.followId ? agents.groundOf(rig.followId) : null, reduced);
      const pose = cameraPose(rig);
      camera.position.set(...pose.position);
      camera.lookAt(...pose.lookAt);
      view.setFocus(rig.distance);
      if (!(Math.abs(rig.yaw - lastHeading) <= 0.001)) {
        lastHeading = rig.yaw;
        options.onHeading?.(rig.yaw);
      }
    }
    view.render();
    overlay.update(camera, canvas.clientWidth, canvas.clientHeight, (id) => agents.badgeAnchor(id));
    sampler.push(dtMs);
    const s = store.get();
    if (s.qualityAuto && !timer && sampler.shouldStepDown(TIERS[s.quality].frameBudgetMs)) {
      const lower = LOWER_TIER[s.quality];
      if (lower) store.dispatch({ type: "setQuality", tier: lower, auto: true });
      sampler.reset();
    }
  }

  let timer = 0;
  const setLoop = () => {
    last = performance.now();
    clearInterval(timer);
    if (document.hidden && options.renderHidden) {
      view.renderer.setAnimationLoop(null);
      timer = window.setInterval(frame, 16);
    } else view.renderer.setAnimationLoop(document.hidden ? null : frame);
  };
  document.addEventListener("visibilitychange", setLoop);

  window.__tafwidPerf = () => ({ ...sampler.stats(), tier: store.get().quality, backend: view.backend });
  window.__tafwidStats = () => {
    let meshes = 0, instanced = 0;
    scene.traverse((o) => {
      if ((o as THREE.InstancedMesh).isInstancedMesh) instanced++;
      else if ((o as THREE.Mesh).isMesh) meshes++;
    });
    const r = view.renderer.info.render;
    return { calls: r.drawCalls ?? (r as { calls?: number }).calls ?? 0, triangles: r.triangles, meshes, instanced };
  };

  const api: World = {
    backend: view.backend,
    camera: {
      rotate: (dir) => rig && (rig = rotate(rig, dir)),
      zoom: (delta) => rig && env && (rig = zoom(rig, delta, env.manifest.camera.zoom)),
      home: () => {
        if (!rig || !env) return;
        store.dispatch({ type: "select", id: null });
        rig = goHome(rig, env.manifest.camera.home);
      },
    },
    resize() {
      const w = host.clientWidth, h = host.clientHeight;
      if (w && h) view.resize(w, h);
    },
    dispose() {
      disposed = true;
      clearInterval(timer);
      view.renderer.setAnimationLoop(null);
      document.removeEventListener("visibilitychange", setLoop);
      window.removeEventListener("keydown", onKey);
      resizeObserver.disconnect();
      env?.dispose();
      agents.dispose();
      ambient.dispose();
      overlay.dispose();
      view.dispose();
      canvas.remove();
    },
  };

  api.resize();
  const s = store.get();
  loading = setEnvironment(s.environmentId, s.variant);
  await loading;
  setLoop();
  return api;
}
