import * as THREE from "three/webgpu";
import { ROLE_LABELS, STATUS_LABELS, type Agent } from "../app/types";
import type { Role } from "../live/types";
import type { Vec3 } from "../contract/manifest";

// Constant, trusted SVG markup (no data interpolated): one icon per role.
// The icon's circle keeps the status colour (styles.css, by data-status).
const ROLE_ICONS: Record<Role, string> = {
  coordinator:
    '<svg viewBox="0 0 16 16"><rect x="3.5" y="3" width="9" height="11" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.6"/><rect x="6" y="1.8" width="4" height="2.6" rx="0.8" fill="currentColor"/><path d="M6 8h4M6 10.8h4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>',
  implementer:
    '<svg viewBox="0 0 16 16"><rect x="3" y="4" width="10" height="6.5" rx="1" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M1.5 12.5h13" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
  reviewer:
    '<svg viewBox="0 0 16 16"><circle cx="4.6" cy="9" r="2.8" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="11.4" cy="9" r="2.8" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M7.4 8.6h1.2" stroke="currentColor" stroke-width="1.6"/></svg>',
  documenter:
    '<svg viewBox="0 0 16 16"><path d="M3 13l1-3.5 6.5-6.5 2.5 2.5L6.5 12z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M9 4.5l2.5 2.5" stroke="currentColor" stroke-width="1.5"/></svg>',
  researcher:
    '<svg viewBox="0 0 16 16"><path d="M8 4.5C6.5 3.3 4.3 3 2 3.3v9c2.3-.3 4.5 0 6 1.2 1.5-1.2 3.7-1.5 6-1.2v-9c-2.3-.3-4.5 0-6 1.2zM8 4.5v9" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>',
  tester:
    '<svg viewBox="0 0 16 16"><rect x="2.5" y="2.5" width="11" height="11" rx="1.6" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M5 6l2 2-2 2M8.5 10.5H11" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
};

/** Badges: DOM buttons with the name and a role icon, projected above each character every frame. */
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
      el.dataset.role = a.role;
      el.setAttribute("aria-label", `${a.name}, ${ROLE_LABELS[a.role]}, ${STATUS_LABELS[a.status]}`);
      el.setAttribute("aria-pressed", String(a.id === selectedId));
      const icon = document.createElement("span");
      icon.className = "badge-icon";
      icon.setAttribute("aria-hidden", "true");
      icon.innerHTML = ROLE_ICONS[a.role];
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
      if (!anchor) {
        el.style.visibility = "hidden"; // the character has left the room
        continue;
      }
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
