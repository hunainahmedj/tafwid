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

  // Rows and filter chips are created once and updated in place, so keyboard focus survives updates.
  const chips = new Map<Filter, HTMLButtonElement>();
  for (const f of FILTERS) {
    const b = h("button", { type: "button", class: "chip", text: f.label });
    b.addEventListener("click", () => store.dispatch({ type: "setFilter", filter: f.id }));
    chips.set(f.id, b);
    filters.append(b);
  }
  const rows = new Map<string, { li: HTMLLIElement; button: HTMLButtonElement }>();
  const empty = h("li", { class: "empty", text: "No agents match this filter." });

  function rowFor(a: Agent) {
    let row = rows.get(a.id);
    if (!row) {
      const button = h("button", { type: "button", class: "agent-row", "data-agent": a.id });
      button.addEventListener("click", () => store.dispatch({ type: "select", id: store.get().selectedId === a.id ? null : a.id }));
      row = { li: h("li", {}, button), button };
      rows.set(a.id, row);
    }
    return row;
  }

  function render(s: AppState) {
    count.textContent = String(s.snapshot.agents.length);
    for (const [id, chip] of chips) chip.setAttribute("aria-pressed", String(s.filter === id));
    for (const id of [...rows.keys()]) if (!s.snapshot.agents.some((a) => a.id === id)) rows.delete(id);
    const visible = s.snapshot.agents.filter((a) => matches(a, s.filter) || a.id === s.selectedId);
    for (const a of visible) {
      const { button } = rowFor(a);
      button.setAttribute("aria-pressed", String(a.id === s.selectedId));
      button.replaceChildren(
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
    }
    // Reorder only when the visible set changes; moving a focused node would drop focus.
    const wanted: HTMLLIElement[] = visible.length ? visible.map((a) => rowFor(a).li) : [empty];
    const current = [...list.children];
    if (wanted.length !== current.length || wanted.some((li, i) => li !== current[i])) list.replaceChildren(...wanted);
  }

  render(store.get());
  store.subscribe((s, p) => {
    if (s.snapshot !== p.snapshot || s.selectedId !== p.selectedId || s.filter !== p.filter) render(s);
  });
}
