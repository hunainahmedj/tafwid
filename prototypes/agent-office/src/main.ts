import './styles.css';
import {createOffice} from './office';
import {createState,transition,type Action} from './model';
import {scenarios} from './fixtures';
import {mountDashboard} from './dashboard';
let state=createState(scenarios.active);
const dashboard=mountDashboard(document.querySelector<HTMLElement>('#app')!,dispatch);
const office=createOffice(dashboard.sceneHost,id=>dispatch({type:'select',id,source:'scene'}));
function dispatch(action:Action){state=transition(state,action);dashboard.render(state);office.update(state);}
dashboard.render(state);office.update(state);
if(import.meta.hot)import.meta.hot.dispose(()=>{office.dispose();dashboard.dispose();});
