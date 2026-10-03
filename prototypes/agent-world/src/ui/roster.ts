import type { Store } from "../app/store";
import { STATUS_LABELS, type Agent, type AppState, type Filter } from "../app/types";
import { formatElapsed, h } from "./dom";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All agents" },
  { id: "working", label: "Working" },
  { id: "attention", label: "Needs you" },
];

const matches = (a: Agent, f: Filter) =>
  f === "all" || (f === "working" ? a.status === "working" : a.status === "review" || a.status === "issue");

/** The team list. In explore mode it is compact; in dashboard mode it adds filters and tasks. */
export function mountRoster(host: HTMLElement, store: Store) {
  const count = h("span", { class: "count" });
  const filters = h("div", { class: "filters", role: "group", "aria-label": "Filter agents" });
  const list = h("ul", { class: "roster-list" });
  host.append(h("div", { class: "panel-head" }, h("h2", { text: "Your team" }), count), filters, list);

  function render(s: AppState) {
    count.textContent = String(s.snapshot.agents.length);
    filters.replaceChildren(
      ...FILTERS.map((f) => {
        const b = h("button", { type: "button", class: "chip", "aria-pressed": String(s.filter === f.id), text: f.label });
        b.addEventListener("click", () => store.dispatch({ type: "setFilter", filter: f.id }));
        return b;
      }),
    );
    const visible = s.snapshot.agents.filter((a) => matches(a, s.filter) || a.id === s.selectedId);
    list.replaceChildren(
      ...visible.map((a) => {
        const button = h(
          "button",
          { type: "button", class: "agent-row", "aria-pressed": String(a.id === s.selectedId), "data-agent": a.id },
          h("span", { class: "avatar", style: `--shirt:${a.look.shirt};--skin:${a.look.skin};--hair:${a.look.hair}`, "aria-hidden": "true" }),
          h(
            "span",
            { class: "agent-text" },
            h("span", { class: "agent-line" }, h("strong", { text: a.name }), h("span", { class: "role", text: a.role })),
            h("span", { class: "task", text: a.task }),
            h(
              "span",
              { class: "agent-meta" },
              h("span", { class: `status status-${a.status}`, text: STATUS_LABELS[a.status] }),
              h("span", { class: "elapsed", text: formatElapsed(a.elapsedMinutes) }),
            ),
          ),
        );
        button.addEventListener("click", () =>
          store.dispatch({ type: "select", id: store.get().selectedId === a.id ? null : a.id }),
        );
        return h("li", {}, button);
      }),
    );
    if (!visible.length) list.append(h("li", { class: "empty", text: "No agents match this filter." }));
  }

  render(store.get());
  store.subscribe((s, p) => {
    if (s.snapshot !== p.snapshot || s.selectedId !== p.selectedId || s.filter !== p.filter) render(s);
  });
}
