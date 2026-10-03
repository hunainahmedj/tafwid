import * as THREE from "three/webgpu";
import { STATUS_LABELS, type Agent } from "../app/types";
import type { Vec3 } from "../contract/manifest";

// Constant, trusted SVG markup (no data interpolated).
const ICONS: Record<Agent["status"], string> = {
  working: '<svg viewBox="0 0 16 16"><rect x="3" y="4" width="10" height="6.5" rx="1" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M1.5 12.5h13" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
  review: '<svg viewBox="0 0 16 16"><path d="M1.5 8s2.4-4.5 6.5-4.5S14.5 8 14.5 8 12.1 12.5 8 12.5 1.5 8 1.5 8z" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="8" cy="8" r="2" fill="currentColor"/></svg>',
  ready: '<svg viewBox="0 0 16 16"><path d="M3 6h8v4a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3z" fill="currentColor"/><path d="M11 7h1.3a1.7 1.7 0 0 1 0 3.4H11" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>',
  issue: '<svg viewBox="0 0 16 16"><path d="M8 2.5v7" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/><circle cx="8" cy="13" r="1.4" fill="currentColor"/></svg>',
};

/** Status badges: DOM buttons projected above each character every frame. */
export class Overlay {
  readonly element = document.createElement("div");
  private badges = new Map<string, HTMLButtonElement>();
  private v = new THREE.Vector3();

  constructor(host: HTMLElement, private onSelect: (id: string) => void) {
    this.element.className = "badges";
    host.append(this.element);
  }

  sync(agents: Agent[], selectedId: string | null) {
    for (const [id, el] of this.badges)
      if (!agents.some((a) => a.id === id)) {
        el.remove();
        this.badges.delete(id);
      }
    for (const a of agents) {
      let el = this.badges.get(a.id);
      if (!el) {
        el = document.createElement("button");
        el.type = "button";
        el.className = "badge";
        el.dataset.agent = a.id;
        el.addEventListener("click", (e) => {
          e.stopPropagation();
          this.onSelect(a.id);
        });
        this.element.append(el);
        this.badges.set(a.id, el);
      }
      el.dataset.status = a.status;
      el.setAttribute("aria-label", `${a.name}, ${STATUS_LABELS[a.status]}`);
      el.setAttribute("aria-pressed", String(a.id === selectedId));
      const icon = document.createElement("span");
      icon.className = "badge-icon";
      icon.setAttribute("aria-hidden", "true");
      icon.innerHTML = ICONS[a.status];
      el.replaceChildren(icon, document.createTextNode(a.name));
    }
  }

  update(camera: THREE.Camera, width: number, height: number, anchorOf: (id: string) => Vec3 | null) {
    const origin = this.element.getBoundingClientRect();
    const obstacles = [...document.querySelectorAll<HTMLElement>("[data-hud-obstacle]")]
      .filter((el) => el.offsetParent !== null)
      .map((el) => el.getBoundingClientRect());
    const covered = (x: number, y: number) =>
      obstacles.some((r) => x + origin.left > r.left - 30 && x + origin.left < r.right + 30 && y + origin.top > r.top - 6 && y + origin.top < r.bottom + 26);
    const placed: { x: number; y: number; w: number; el: HTMLButtonElement }[] = [];
    for (const [id, el] of this.badges) {
      const anchor = anchorOf(id);
      if (!anchor) continue;
      this.v.set(...anchor).project(camera);
      const hidden = this.v.z > 1 || Math.abs(this.v.x) > 1.1 || Math.abs(this.v.y) > 1.1;
      el.style.visibility = hidden ? "hidden" : "visible";
      if (!hidden) placed.push({ x: ((this.v.x + 1) / 2) * width, y: ((1 - this.v.y) / 2) * height, w: el.offsetWidth || 60, el });
    }
    // Declutter: badges that would overlap are nudged upwards, nearest-to-camera first keeps its place.
    placed.sort((a, b) => b.y - a.y);
    const taken: { x: number; y: number; w: number }[] = [];
    const H = 24;
    for (const b of placed) {
      let y = b.y;
      for (let guard = 0; guard < 6; guard++) {
        const hit = taken.find((t) => Math.abs(t.x - b.x) < (t.w + b.w) / 2 + 4 && Math.abs(t.y - y) < H);
        if (!hit) break;
        y = hit.y - H;
      }
      taken.push({ x: b.x, y, w: b.w });
      b.el.style.visibility = covered(b.x, y) ? "hidden" : "visible";
      b.el.style.transform = `translate(${b.x}px, ${y}px) translate(-50%, -100%)`;
    }
  }

  dispose() {
    this.element.remove();
  }
}
