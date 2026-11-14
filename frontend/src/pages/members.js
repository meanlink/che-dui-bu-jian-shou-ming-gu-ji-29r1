import {fleets} from '../api/entities.js';
import {heading} from '../components/common/shell.js';
import {Role} from '../constants/enums.js';
import {esc,date,notify} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
export async function membersPage(){
 const response=await fleets.list();const members=await fleets.members();
 const roleOptions=role=>Object.entries(Role).map(([value,label])=>'<option value="'+value+'" '+(value===role?'selected':'')+'>'+esc(label)+'</option>').join('');
 return heading('06 / ACCESS','成员与权限','成员归属单一车队；角色限制沿用原有规则。移出成员会立即作废其登录，并停止其安排的待发简报。')+'<div class="two-columns"><section class="panel"><div class="section-title"><h2>'+esc(response.current.name)+' 成员</h2><span>'+members.length+' 人</span></div><div class="member-list">'+members.map(m=>'<article class="member"><div><strong>'+esc(m.name)+'</strong><p>'+esc(m.email||'（仅负责人可见联系方式）')+'</p><small>加入于 '+date(m.created_at)+'</small></div><div class="member-actions"><select data-role="'+m.membership_id+'">'+roleOptions(m.role)+'</select><button class="text-button" data-remove="'+m.membership_id+'">移出</button></div></article>').join('')+'</div><p class="warning">仅业务负责人可调整角色或移出成员；车队负责人不能被移出，也不能被降级。</p></section><section class="panel"><div class="section-title"><h2>添加成员</h2><span>可邀请已有账号，也可新建</span></div><form id="member-form"><label>邮箱<input name="email" type="email" required placeholder="analyst@fleet.local"></label><label>姓名<input name="name" maxlength="80" placeholder="新成员姓名"></label><label>初始密码<input name="password" type="password" minlength="8" placeholder="新账号至少 8 位；已有账号留空"></label><label>角色<select name="role">'+Object.entries(Role).map(([value,label])=>'<option value="'+value+'" '+(value==='analyst'?'selected':'')+'>'+esc(label)+'</option>').join('')+'</select></label><button type="submit" class="primary">加入本车队</button><p class="hint">角色仅在本车队生效；同一账号可属于多个车队，各自独立授权。</p></form></section></div>';
}
export function bindMembers(refresh){
 submit(document.querySelector('#member-form'),async f=>{await fleets.add({email:f.get('email'),name:f.get('name'),password:f.get('password'),role:f.get('role')});notify('成员已加入本车队');await refresh();});
 document.querySelectorAll('[data-role]').forEach(select=>select.onchange=async()=>{try{await fleets.role(select.dataset.role,select.value);notify('角色已更新');await refresh();}catch(e){notify(e.message,true);await refresh();}});
 document.querySelectorAll('[data-remove]').forEach(button=>button.onclick=async()=>{try{const r=await fleets.remove(button.dataset.remove);notify('成员已移出；旧登录已失效，停止 '+r.reports_disabled+' 个待发简报');await refresh();}catch(e){notify(e.message,true);}});
}
