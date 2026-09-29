import * as T from 'three';
import {RoundedBoxGeometry} from 'three/addons/geometries/RoundedBoxGeometry.js';
import type {Agent} from './model';
export const positions:[number,number][]=[[-2.65,-1.05],[1.65,-1.05],[-2.65,2.05],[1.65,2.05]];
const mat=(color:T.ColorRepresentation)=>new T.MeshStandardMaterial({color,roughness:.88,flatShading:true});
function box(g:T.Group,x:number,y:number,z:number,w:number,h:number,d:number,color:T.ColorRepresentation,r=.035){const m=new T.Mesh(r?new RoundedBoxGeometry(w,h,d,2,r):new T.BoxGeometry(w,h,d),mat(color));m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;g.add(m);return m;}
function cyl(g:T.Group,x:number,y:number,z:number,rt:number,rb:number,h:number,color:T.ColorRepresentation,segments=10){const m=new T.Mesh(new T.CylinderGeometry(rt,rb,h,segments),mat(color));m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;g.add(m);return m;}
function sphere(g:T.Group,x:number,y:number,z:number,r:number,color:T.ColorRepresentation){const m=new T.Mesh(new T.IcosahedronGeometry(r,1),mat(color));m.position.set(x,y,z);m.castShadow=true;g.add(m);return m;}
function plant(g:T.Group,x:number,z:number,scale=1){const p=new T.Group();cyl(p,0,.25,0,.27,.2,.48,'#e7c9a8');cyl(p,0,.49,0,.23,.23,.02,'#685c48');cyl(p,0,.95,0,.035,.05,1,'#68806a',6);const leaves=[[0,1.4,0],[.25,1.1,.06],[-.25,.98,0],[.04,.85,.22]];leaves.forEach(([lx,ly,lz],i)=>{const m=sphere(p,lx,ly,lz,.33,i%2?'#739982':'#91b49a');m.scale.set(.7,1.5,.65);m.rotation.z=lx>0?-.5:.4;});p.scale.setScalar(scale);p.position.set(x,.13,z);g.add(p);}
function book(g:T.Group,x:number,y:number,z:number,color:string,rot=0){const b=box(g,x,y,z,.35,.065,.46,color,.01);b.rotation.y=rot;}
export function createRoom():T.Group {
 const g=new T.Group();
 box(g,0,-.25,0,12.2,.55,10,'#d5d1e2',.16);
 box(g,0,.04,0,12,.14,9.8,'#e7dfd8',.07);
 for(let i=-5;i<=5;i++)box(g,i,.116,0,.012,.005,9.5,'#d9d0c9',0);
 // Tall rear wall, low return wall: an open cutaway rather than a closed box.
 box(g,0,1.6,-4.7,12,.0+3.2,.22,'#e1def0',.05);
 box(g,-5.9,.63,0,.22,1.25,9.7,'#dddbea',.04);
 box(g,0,.28,-4.52,11.7,.28,.12,'#f3f0f6',.02);
 box(g,-5.73,.28,0,.12,.28,9.4,'#f3f0f6',.02);
 // Window alcove with broad white mullions.
 box(g,-2.45,1.98,-4.51,4.25,2.1,.16,'#f8f7fc',.07);
 box(g,-2.45,1.98,-4.4,3.91,1.77,.055,'#c2dce7',.025);
 box(g,-2.45,1.98,-4.35,.09,1.85,.075,'#fcfaf9',.012);
 box(g,-2.45,2.04,-4.34,3.98,.07,.075,'#fcfaf9',.012);
 box(g,-2.45,.87,-4.29,4.43,.12,.45,'#f6f4f9',.025);
 // Pin board and restrained abstract wall artwork.
 box(g,1.18,2.04,-4.49,1.45,1.61,.13,'#f4ede6',.025);
 box(g,1.18,2.04,-4.40,1.21,1.36,.02,'#b2a4d7',0);
 const art=cyl(g,1.18,2.13,-4.36,.37,.37,.025,'#f2dac6',24);art.rotation.x=Math.PI/2;
 box(g,1.18,1.77,-4.34,.7,.17,.015,'#8181b2',0);
 box(g,3.48,2.12,-4.49,1.42,.88,.12,'#ebe6dd',.03);
 for(let i=0;i<3;i++)box(g,3.04+i*.4,2.15,-4.39,.25,.34,.02,['#f2c889','#aabed9','#bbabd9'][i],.005);
 // Bookcase and a small break corner.
 box(g,4.9,.85,-3.6,1.25,1.45,.65,'#eee9e2',.05);
 for(const y of [.26,.87,1.54])box(g,4.9,y,-3.54,1.25,.075,.72,'#cbbdab',.015);
 for(let i=0;i<5;i++)box(g,4.47+i*.18,1.16,-3.52,.12,.48,.39,['#91acb6','#d5af8d','#afa1cd','#718b82','#d6c4a9'][i],.01);
 book(g,4.74,.36,-3.52,'#b7aacd');book(g,4.77,.43,-3.52,'#d8c0a2');
 plant(g,-5.03,-3.65,.9);plant(g,5.08,3.65,.82);
 // Soft lavender rug under workstations.
 box(g,-.43,.135,.65,8.76,.028,6.4,'#cbc9df',.15);
 // A rounded apricot bench beside the desks.
 box(g,4.8,.47,.65,1.22,.72,2.52,'#d89e7a',.15);
 box(g,5.29,.96,.65,.24,.83,2.6,'#e9b894',.11);
 for(const z of [-.2,1.45])box(g,4.8,.83,z,1.03,.14,.94,'#edc7a8',.07);
 box(g,4.89,1.04,-.22,.54,.35,.48,'#f1dcc6',.09);
 const table=cyl(g,4.57,.54,2.65,.45,.45,.12,'#f0e5d9',16);cyl(g,4.57,.3,2.65,.085,.15,.5,'#bda994');
 cyl(g,4.57,.69,2.65,.075,.065,.17,'#7e9aa1');
 return g;
}
export function createWorkstation(agent:Agent):T.Group {
 const g=new T.Group();const color=agent.color;
 // Broad desk, light wood supports, monitor and personal props.
 box(g,0,1.05,0,2.58,.15,1.35,'#f3e7d6',.09);
 for(const x of [-1.03,1.03])for(const z of [-.42,.42])box(g,x,.54,z,.11,1.0,.11,'#c9b7a3',.02);
 box(g,-.29,1.5,-.28,1.04,.65,.08,'#535771',.04);
 box(g,-.29,1.52,-.225,.91,.5,.018,'#a9c4d6',.016);
 for(let i=0;i<3;i++)box(g,-.44+i*.06,1.62-i*.12,-.21,.44+i*.13,.026,.006,['#e6eff3','#c2dada','#7798b4'][i],0);
 cyl(g,-.29,1.23,-.27,.055,.06,.26,'#81849a',8);box(g,-.29,1.14,-.25,.43,.035,.23,'#81849a',.01);
 box(g,-.33,1.15,.3,.76,.035,.26,'#c7cbd6',.025);
 for(let i=0;i<5;i++)box(g,-.6+i*.13,1.171,.29,.07,.007,.17,'#eef0f4',0);
 book(g,.72,1.16,-.3,color,.1);book(g,.75,1.23,-.31,'#f5eddf',-.05);
 cyl(g,.83,1.24,.3,.09,.08,.22,color,10);
 // Ergonomic chair and an approachable geometric character.
 box(g,.25,.67,1.07,.7,.16,.68,color,.1);box(g,.25,1.06,1.38,.7,.72,.14,color,.09);
 cyl(g,.25,.37,1.07,.06,.09,.58,'#696b7b',8);
 for(let i=0;i<4;i++){const b=box(g,.25,.16,1.07,.7,.07,.07,'#777989',.02);b.rotation.y=i*Math.PI/2;}
 const person=new T.Group();person.position.set(.25,0,1.0);
 box(person,0,.98,0,.49,.57,.36,color,.12);
 for(const x of [-.15,.15]){box(person,x,.57,-.18,.16,.43,.19,'#5c6278',.05);box(person,x,.36,-.29,.2,.13,.34,'#f4f0e9',.05);}
 cyl(person,0,1.32,0,.105,.115,.17,'#e4b994');
 const skin=agent.id==='noor'?'#b98a65':agent.id==='ada'?'#dca780':'#edc7a5';
 box(person,0,1.61,0,.47,.51,.42,skin,.12);
 box(person,0,1.84,-.02,.5,.16,.43,agent.id==='cleo'?'#b88154':agent.id==='noor'?'#514538':'#484654',.07);
 box(person,-.23,1.72,-.045,.08,.25,.4,agent.id==='cleo'?'#b88154':'#484654',.025);
 // Faces look toward the open room; hands rest near the desk.
 for(const x of [-.09,.09])sphere(person,x,1.65,.212,.023,'#3e4050');
 box(person,0,1.53,.218,.08,.017,.006,'#aa7867',.003);
 for(const x of [-.31,.31]){const arm=box(person,x,1.1,-.05,.15,.42,.17,color,.06);arm.rotation.x=-.6;sphere(person,x,.96,-.21,.085,skin);}
 if(agent.id==='ada'){const hoop=new T.Mesh(new T.TorusGeometry(.29,.035,6,12,Math.PI),mat('#41495f'));hoop.position.set(0,1.73,0);person.add(hoop);for(const x of [-.27,.27])box(person,x,1.64,0,.10,.22,.2,'#41495f',.04);}
 if(agent.id==='cleo'){for(const x of [-.105,.105]){const rim=new T.Mesh(new T.TorusGeometry(.083,.013,4,12),mat('#786549'));rim.position.set(x,1.65,.236);person.add(rim);}box(person,0,1.66,.237,.055,.016,.015,'#786549',0);}
 if(agent.id==='noor')sphere(person,0,1.94,-.09,.15,'#514538');
 g.add(person);
 g.traverse(o=>{o.userData.agentId=agent.id;});
 const ring=new T.Mesh(new T.RingGeometry(1.2,1.26,48),new T.MeshBasicMaterial({color:'#6776cf',side:T.DoubleSide,transparent:true,opacity:.65}));ring.rotation.x=-Math.PI/2;ring.position.set(0,.158,.32);ring.name='selection-ring';g.add(ring);
 return g;
}
