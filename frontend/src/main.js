import {api} from '../api/client.js';
import {session} from '../stores/session.js';
import {fleets} from '../api/entities.js';
import {workspace} from '../stores/workspace.js';
import {shell} from '../components/common/shell.js';
import {route} from '../router/index.js';
import {login} from './pages/login.js';
import {overview} from './pages/overview.js';
import {dataPage,bindData} from './pages/datasets.js';
import {workbench,bindWorkbench} from './pages/workbench.js';
import {results,bindResults} from './pages/results.js';
import {reportPage,bindReports} from './pages/reports.js';
import {membersPage,bindMembers} from './pages/members.js';
import {legacyPage,bindLegacy} from './pages/legacy.js';
import {esc,notify} from './utils/dom.js';
async function render(){
 const app=document.querySelector('#app');
 try{
   if(!workspace.meta){workspace.meta=await api('/meta');document.title=workspace.meta.name;document.documentElement.style.setProperty('--accent',workspace.meta.accent||'oklch(48% 0.13 145)');document.body.dataset.style=workspace.meta.style||'ledger';}
   const {page,id}=route();
   if(!session.token||page==='login'){login();return;}
   // Re-read the membership on every navigation: role changes and removals
   // take effect immediately, not at the next login.
   const me=await fleets.me();session.update({user:{name:me.name,role:me.role,email:me.email},fleet:me.fleet,fleets:me.fleets});
   const ownerPages=['members','legacy'];
   const page_=session.user.role==='admin'||!ownerPages.includes(page)?page:'overview';
   const pages={overview,datasets:dataPage,workbench,results:()=>results(id),reports:reportPage,members:membersPage,legacy:()=>legacyPage(id)};
   const content=await (pages[page_]||overview)();app.innerHTML=shell(page_,content);
   document.querySelector('#logout').onclick=()=>{session.clear();location.hash='#/login';render();};
   document.querySelector('#fleet-switch')?.addEventListener('change',async e=>{
     try{const next=await fleets.switch(Number(e.target.value));session.save(next);workspace.datasets=[];workspace.jobs=[];workspace.reports=[];workspace.selectedJob=null;notify('已切换到 '+next.fleet.name);location.hash='#/overview';render();}
     catch(error){notify(error.message,true);}
   });
   if(page_==='datasets')bindData(render);if(page_==='workbench')bindWorkbench();if(page_==='results')bindResults(render);if(page_==='reports')bindReports(render);if(page_==='members')bindMembers(render);if(page_==='legacy')bindLegacy(render);
 }catch(e){if(!session.token){login();return;}app.innerHTML='<div class="fatal"><h1>暂时无法打开工作室</h1><p>'+esc(e.message)+'</p><button onclick="location.reload()">重新连接</button></div>';}
}
addEventListener('hashchange',render);render();
