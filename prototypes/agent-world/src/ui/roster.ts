import { visibleAgents, type Store } from "../app/store";
import { ROLE_LABELS, STATUS_LABELS, actionText, hostLabel, type Agent, type AppState, type Filter, type SnapshotTeam } from "../app/types";
import { formatElapsed, h, projectName, reconcile } from "./dom";
import { mountTeamChips } from "./teams";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All agents" },
  { id: "working", label: "Working" },
  { id: "attention", label: "Needs you" },
];

const matches = (a: Agent, f: Filter) =>
  f === "all" || (f === "working" ? a.status === "working" : a.status === "review" || a.status === "issue");

interface TeamGroup {
  li: HTMLLIElement;
  swatch: HTMLElement;
  name: HTMLElement;
  host: HTMLElement;
  list: HTMLUListElement;
  more: HTMLElement;
}

/** The team list, grouped by team. In explore mode it is compact; in dashboard mode it adds filters and tasks. */
export function mountRoster(host: HTMLElement, store: Store) {
  const count = h("span", { class: "count" });
  const teamChips = h("div", { class: "team-chips" });
  const filters = h("div", { class: "filters", role: "group", "aria-label": "Filter agents" });
  const list = h("ul", { class: "roster-list" });
  host.append(h("div", { class: "panel-head" }, h("h2", { text: "Your team" }), count), teamChips, filters, list);
  mountTeamChips(teamChips, store);

  // Rows, groups and filter chips are created once and updated in place, so keyboard focus survives updates.
  const chips = new Map<Filter, HTMLButtonElement>();
  for (const f of FILTERS) {
    const b = h("button", { type: "button", class: "chip", text: f.label });
    b.addEventListener("click", () => store.dispatch({ type: "setFilter", filter: f.id }));
    chips.set(f.id, b);
    filters.append(b);
  }
  const rows = new Map<string, { li: HTMLLIElement; button: HTMLButtonElement }>();
  const groups = new Map<string, TeamGroup>();
  const empty = h("li", { class: "empty" });

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

  function groupFor(team: SnapshotTeam) {
    let group = groups.get(team.id);
    if (!group) {
      const swatch = h("span", { class: "swatch", "aria-hidden": "true" });
      const name = h("span", { class: "team-name" });
      const hostText = h("span", { class: "team-host" });
      const agents = h("ul", { class: "team-agents" });
      const more = h("p", { class: "more" });
      group = { li: h("li", { class: "team-group", "data-team": team.id }, h("h3", { class: "team-heading" }, swatch, name, hostText), agents, more), swatch, name, host: hostText, list: agents, more };
      groups.set(team.id, group);
    }
    return group;
  }

  function render(s: AppState) {
    count.textContent = String(visibleAgents(s.snapshot, s.projectFilter).length);
    for (const [id, chip] of chips) chip.setAttribute("aria-pressed", String(s.filter === id));
    for (const id of [...rows.keys()]) if (!s.snapshot.agents.some((a) => a.id === id)) rows.delete(id);
    for (const id of [...groups.keys()]) if (!s.snapshot.teams.some((t) => t.id === id)) groups.delete(id);

    const visible = visibleAgents(s.snapshot, s.projectFilter).filter((a) => matches(a, s.filter) || a.id === s.selectedId);
    for (const a of visible) {
      const { button } = rowFor(a);
      button.setAttribute("aria-pressed", String(a.id === s.selectedId));
      button.dataset.status = a.status;
      button.replaceChildren(
        h("span", { class: "avatar", style: `--shirt:${a.look.shirt};--skin:${a.look.skin};--hair:${a.look.hair}`, "aria-hidden": "true" }),
        h(
          "span",
          { class: "agent-text" },
          h("span", { class: "agent-line" }, h("strong", { text: a.name }), h("span", { class: "role", text: ROLE_LABELS[a.role] })),
          h("span", { class: "task", text: a.task }),
          h(
            "span",
            { class: "agent-meta" },
            h("span", { class: `status status-${a.status}`, text: STATUS_LABELS[a.status] }),
            h("span", { class: "action", text: a.status === "working" ? actionText(a) : "" }),
            h("span", { class: "elapsed", text: formatElapsed(a.elapsedMinutes) }),
          ),
        ),
      );
    }

    // The "+N more" line closes the last team of its project, which is listed even with no agent of its own on show.
    const lastTeamOf = new Map<string, string>();
    for (const t of s.snapshot.teams) lastTeamOf.set(t.project, t.id);
    const hiddenIn = (t: SnapshotTeam) => (lastTeamOf.get(t.project) === t.id ? (s.snapshot.overflow[t.project] ?? 0) : 0);

    const shown: Node[] = [];
    for (const team of s.snapshot.teams) {
      if (s.projectFilter !== null && team.project !== s.projectFilter) continue;
      const members = visible.filter((a) => a.teamId === team.id);
      const hidden = hiddenIn(team);
      if (members.length === 0 && hidden === 0) continue;
      const group = groupFor(team);
      group.swatch.style.setProperty("--accent", team.accent);
      group.name.textContent = projectName(team.project);
      group.host.textContent = `· ${hostLabel(team.host)}`;
      reconcile(group.list, members.map((a) => rowFor(a).li));
      group.more.hidden = hidden === 0;
      group.more.textContent = hidden ? `+${hidden} more in ${projectName(team.project)}` : "";
      shown.push(group.li);
    }
    if (shown.length === 0) {
      empty.textContent = s.snapshot.agents.length === 0 ? "No agents are active right now." : "No agents match this filter.";
      shown.push(empty);
    }
    reconcile(list, shown);
  }

  render(store.get());
  store.subscribe((s, p) => {
    if (s.snapshot !== p.snapshot || s.selectedId !== p.selectedId || s.filter !== p.filter || s.projectFilter !== p.projectFilter) render(s);
  });
}
