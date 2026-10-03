import type { Store } from "../app/store";
import type { AppState } from "../app/types";
import { h, projectName, reconcile } from "./dom";

interface ProjectChip {
  project: string;
  count: number;
}

function projectsOf(s: AppState): ProjectChip[] {
  const byProject = new Map<string, number>();
  for (const t of s.snapshot.teams) byProject.set(t.project, (byProject.get(t.project) ?? 0) + t.count);
  // The cap hides some agents from the roster; the chip still counts them.
  for (const [project, hidden] of Object.entries(s.snapshot.overflow)) if (byProject.has(project)) byProject.set(project, byProject.get(project)! + hidden);
  return [...byProject].map(([project, count]) => ({ project, count }));
}

/** One chip per project with its agent count, plus "All projects". A chip filters the roster; pressing it again clears the filter. */
export function mountTeamChips(host: HTMLElement, store: Store) {
  host.setAttribute("role", "group");
  host.setAttribute("aria-label", "Projects");

  // Chips are created once per project and updated in place, so keyboard focus survives updates.
  const all = h("button", { type: "button", class: "chip" }, h("span", { class: "chip-name", text: "All projects" }), h("span", { class: "chip-count" }));
  all.addEventListener("click", () => store.dispatch({ type: "setProjectFilter", project: null }));
  const chips = new Map<string, { button: HTMLButtonElement; count: HTMLElement; name: HTMLElement }>();
  host.append(all);

  function chipFor(project: string) {
    let chip = chips.get(project);
    if (!chip) {
      const name = h("span", { class: "chip-name", text: projectName(project) });
      const count = h("span", { class: "chip-count" });
      const button = h("button", { type: "button", class: "chip", "data-project": project }, name, count);
      button.addEventListener("click", () => {
        const current = store.get().projectFilter;
        store.dispatch({ type: "setProjectFilter", project: current === project ? null : project });
      });
      chip = { button, count, name };
      chips.set(project, chip);
    }
    return chip;
  }

  function render(s: AppState) {
    const projects = projectsOf(s);
    host.hidden = projects.length === 0;
    for (const project of [...chips.keys()]) if (!projects.some((p) => p.project === project)) chips.delete(project);
    all.setAttribute("aria-pressed", String(s.projectFilter === null));
    all.querySelector(".chip-count")!.textContent = String(projects.reduce((n, p) => n + p.count, 0));
    const wanted: Node[] = [all];
    for (const { project, count } of projects) {
      const chip = chipFor(project);
      chip.count.textContent = String(count);
      chip.button.setAttribute("aria-pressed", String(s.projectFilter === project));
      wanted.push(chip.button);
    }
    reconcile(host, wanted);
  }

  render(store.get());
  store.subscribe((s, p) => {
    if (s.snapshot !== p.snapshot || s.projectFilter !== p.projectFilter) render(s);
  });
}
