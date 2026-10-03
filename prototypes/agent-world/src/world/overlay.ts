import * as THREE from "three/webgpu";
import { STATUS_LABELS, type Agent } from "../app/types";
import type { Vec3 } from "../contract/manifest";

const ICONS: Record<Agent["status"], string> = { working: "⌨", review: "👁", ready: "☕", issue: "!" };

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
      icon.textContent = ICONS[a.status];
      el.replaceChildren(icon, document.createTextNode(a.name));
    }
  }

  update(camera: THREE.Camera, width: number, height: number, anchorOf: (id: string) => Vec3 | null) {
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
      b.el.style.transform = `translate(${b.x}px, ${y}px) translate(-50%, -100%)`;
    }
  }

  dispose() {
    this.element.remove();
  }
}
