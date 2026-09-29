import './styles.css';
import {createState,transition,type Action} from './model';
import {scenarios} from './fixtures';
import {mountDashboard} from './dashboard';
let state=createState(scenarios.active);
const dashboard=mountDashboard(document.querySelector<HTMLElement>('#app')!,dispatch);
function dispatch(action:Action){state=transition(state,action);dashboard.render(state);}
dashboard.render(state);
if(import.meta.hot)import.meta.hot.dispose(()=>dashboard.dispose());
