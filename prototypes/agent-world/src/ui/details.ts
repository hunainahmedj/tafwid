import type { Store } from "../app/store";
import { ROLE_LABELS, STATUS_LABELS, actionText, type AppState } from "../app/types";
import { formatElapsed, h, projectName } from "./dom";

/** The selected agent's card: "Following" in explore mode, "In focus" in dashboard mode. */
export function mountDetails(host: HTMLElement, store: Store) {
  function render(s: AppState) {
    const a = s.snapshot.agents.find((x) => x.id === s.selectedId);
    host.hidden = !a && s.mode === "explore";
    if (!a) {
      host.replaceChildren(h("p", { class: "placeholder", text: "Select an agent to see what they are working on." }));
      return;
    }
    const field = (label: string, ...value: (Node | string)[]) =>
      h("div", { class: "field" }, h("span", { class: "label", text: label }), h("span", { class: "value" }, ...value));
    const hint = s.mode === "explore" ? [h("span", { class: "dismiss-hint", text: "Esc or drag to stop following" })] : [];
    host.replaceChildren(
      h(
        "div",
        { class: "who" },
        h("span", { class: "avatar", style: `--shirt:${a.look.shirt};--skin:${a.look.skin};--hair:${a.look.hair}`, "aria-hidden": "true" }),
        h(
          "div",
          {},
          h("span", { class: "label", text: s.mode === "explore" ? "Following" : "In focus" }),
          h("span", { class: "agent-line" }, h("strong", { text: a.name }), h("span", { class: "role", text: ROLE_LABELS[a.role] })),
          h("span", { class: "provider", text: `${a.provider} · ${projectName(a.project)}` }),
        ),
      ),
      field("Current task", a.task),
      field("Current action", actionText(a)),
      field("Status", h("span", { class: `status status-${a.status}`, text: STATUS_LABELS[a.status] }), ` · ${formatElapsed(a.elapsedMinutes)}`),
      ...(a.next ? [field("What happens next", a.next)] : []),
      ...hint,
    );
  }
  render(store.get());
  store.subscribe((s, p) => {
    if (s.snapshot !== p.snapshot || s.selectedId !== p.selectedId || s.mode !== p.mode) render(s);
  });
}
