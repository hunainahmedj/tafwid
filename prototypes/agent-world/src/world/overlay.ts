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
    for (const [id, el] of this.badges) {
      const anchor = anchorOf(id);
      if (!anchor) continue;
      this.v.set(...anchor).project(camera);
      const hidden = this.v.z > 1 || Math.abs(this.v.x) > 1.1 || Math.abs(this.v.y) > 1.1;
      el.style.visibility = hidden ? "hidden" : "visible";
      el.style.transform = `translate(${((this.v.x + 1) / 2) * width}px, ${((1 - this.v.y) / 2) * height}px) translate(-50%, -100%)`;
    }
  }

  dispose() {
    this.element.remove();
  }
}
