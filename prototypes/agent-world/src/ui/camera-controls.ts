import { h } from "./dom";

export interface CameraActions {
  rotate(dir: 1 | -1): void;
  zoom(delta: number): void;
  home(): void;
}

/** The on-screen camera cluster; returns a setter for the compass heading. */
export function mountCameraControls(host: HTMLElement, getActions: () => CameraActions | null) {
  const needle = h("span", { class: "needle" });
  const button = (label: string, glyph: string, action: (a: CameraActions) => void) => {
    const b = h("button", { type: "button", class: "cam-button", "aria-label": label, title: label, text: glyph });
    b.addEventListener("click", (e) => {
      e.stopPropagation();
      const actions = getActions();
      if (actions) action(actions);
    });
    return b;
  };
  host.append(
    button("Rotate left (Q)", "⟲", (a) => a.rotate(1)),
    button("Zoom in", "+", (a) => a.zoom(-5)),
    button("Rotate right (E)", "⟳", (a) => a.rotate(-1)),
    h("span", { class: "compass", role: "img", "aria-label": "Camera heading" }, needle),
    button("Zoom out", "−", (a) => a.zoom(5)),
    button("Reset view", "⌂", (a) => a.home()),
  );
  return (yaw: number) => {
    needle.style.transform = `rotate(${yaw}rad)`;
    host.dataset.heading = yaw.toFixed(3);
  };
}
