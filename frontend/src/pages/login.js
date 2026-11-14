import {api} from '../api/client.js';
import {session} from '../stores/session.js';
import {workspace} from '../stores/workspace.js';
import {esc} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
export function login(){
 const m=workspace.meta;
 document.querySelector('#app').innerHTML='<div class="login-scene"><section class="login-story"><div class="edition">FIELD NOTES / ANALYTICS</div><p class="eyebrow">'+esc(m.client)+'</p><h1>'+esc(m.name)+'</h1><p class="login-tag">'+esc(m.tagline)+'</p><div class="flow-lines">'+m.entities.map((v,i)=>'<div><span>0'+(i+1)+'</span><strong>'+esc(v)+'</strong></div>').join('')+'</div><p class="login-foot">从原始记录走到可复核的业务判断。</p></section><section class="login-form"><p class="eyebrow">WORKSPACE ACCESS</p><h2>进入业务现场</h2><p>选择账号后登录，进入所属车队的工作室。</p><form id="login"><label>演示账号<select name="email"><option value="admin@demo.local">林知 · 鹭湾业务负责人</option><option value="analyst@demo.local">陈舟 · 鹭湾分析员</option><option value="viewer@demo.local">周禾 · 鹭湾观察员</option><option value="owner@qingyu.local">顾岚 · 青屿业务负责人</option><option value="analyst@qingyu.local">方至 · 青屿分析员</option></select></label><label>密码<input name="password" type="password" value="Demo123!" required autocomplete="current-password"></label><button type="submit" class="primary">进入工作室 ↗</button></form><p class="hint">演示密码 Demo123! · 数据按车队隔离，跨队访问与下载均被拒绝。多车队账号登录后可在侧栏切换。</p></section></div>';
 submit(document.querySelector('#login'),async f=>{session.save(await api('/auth/login',{method:'POST',body:JSON.stringify(Object.fromEntries(f))}));location.hash='#/overview';});
}
