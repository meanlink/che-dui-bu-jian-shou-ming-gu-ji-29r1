import {api} from './client.js';
export const datasets={list:()=>api('/datasets'),get:id=>api('/datasets/'+id),create:data=>api('/datasets',{method:'POST',body:JSON.stringify(data)})};
export const jobs={list:()=>api('/jobs'),get:id=>api('/jobs/'+id),create:data=>api('/jobs',{method:'POST',body:JSON.stringify(data)}),approve:id=>api('/jobs/'+id+'/approve',{method:'POST'})};
export const reports={list:()=>api('/reports'),create:data=>api('/reports',{method:'POST',body:JSON.stringify(data)}),toggle:id=>api('/reports/'+id+'/toggle',{method:'POST'}),deliveries:()=>api('/deliveries')};
export const fleets={list:()=>api('/fleets'),members:()=>api('/fleets/members'),add:data=>api('/fleets/members',{method:'POST',body:JSON.stringify(data)}),role:(id,role)=>api('/fleets/members/'+id,{method:'PATCH',body:JSON.stringify({role})}),remove:id=>api('/fleets/members/'+id,{method:'DELETE'}),switch:id=>api('/auth/switch',{method:'POST',body:JSON.stringify({fleet_id:id})}),me:()=>api('/auth/me')};
export const legacy={chains:()=>api('/legacy/chains'),chain:id=>api('/legacy/chains/'+id),claim:id=>api('/legacy/chains/'+id+'/claim',{method:'POST'})};
