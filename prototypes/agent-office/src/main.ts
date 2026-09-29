import "./styles.css";
import type { createOffice } from "./office";
import { createState, transition, type Action } from "./model";
import { scenarios } from "./fixtures";
import { mountDashboard } from "./dashboard";
let state = createState(scenarios.active);
let office: ReturnType<typeof createOffice> | undefined;
let disposed = false;
const dashboard = mountDashboard(
  document.querySelector<HTMLElement>("#app")!,
  dispatch,
);
function dispatch(action: Action) {
  state = transition(state, action);
  dashboard.render(state);
  office?.update(state);
}
dashboard.render(state);
void import("./office")
  .then(({ createOffice }) => {
    if (disposed) return;
    office = createOffice(dashboard.sceneHost, (id) =>
      dispatch({ type: "select", id, source: "scene" }),
    );
    office.update(state);
  })
  .catch(() => {
    if (disposed) return;
    dashboard.sceneHost.innerHTML =
      '<div class="scene-fallback"><strong>The 3D view is unavailable</strong><p>Select an agent in the roster to explore their work.</p></div>';
  });
if (import.meta.hot)
  import.meta.hot.dispose(() => {
    disposed = true;
    office?.dispose();
    dashboard.dispose();
  });
