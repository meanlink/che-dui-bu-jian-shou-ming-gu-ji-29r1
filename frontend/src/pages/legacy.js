import {legacy} from '../api/entities.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {esc,date,notify} from '../utils/dom.js';
export async function legacyPage(id){
 const chains=await legacy.chains();
 const datasetId=id?Number(id):(chains[0]?.dataset_id);
 const selected=datasetId?await legacy.chain(datasetId).catch(()=>null):null;
 return heading('07 / HISTORICAL CLAIM','封存历史与认领','迁移前先封存：旧数据不进入任何车队，仅业务负责人可见。认领按整条关联链执行，冲突时整链保持不变。')+'<div class="two-columns"><section class="panel"><div class="section-title"><h2>待认领关联链</h2><span>'+chains.length+' 条</span></div>'+(chains.length?'<div class="batch-list">'+chains.map(c=>'<a class="batch-item '+(c.dataset_id===datasetId?'selected':'')+'" href="#/legacy/'+c.dataset_id+'"><strong>'+esc(c.name)+'</strong><span>'+c.counts.jobs+' 个分析 · '+c.counts.reports+' 个计划 · '+c.counts.deliveries+' 份归档</span><small>封存于 '+date(c.sealed_at)+' · SHA256 '+esc(c.checksum.slice(0,18))+'…</small></a>').join('')+'</div>':'<p class="empty">没有待认领的封存链路。已被认领的历史不会出现在此列表。</p>')+'<p class="warning">认领后整条关联链进入「'+esc(session.fleet?.name||'')+'」；若链路中有任一数据已归属其他车队，或目标车队已有同名批次，认领被拒绝且不移动任何数据。</p></section><section class="panel"><div class="section-title"><h2 id="chain-name">'+esc(selected?.name||'暂无封存链路')+'</h2><span>只读预览</span></div>'+(selected?'<div class="chain-detail"><p>来源 '+esc(selected.source)+' · '+selected.rows+' 条样本 · 封存于 '+date(selected.sealed_at)+'</p><h3>关联链</h3><ul class="chain-list">'+selected.jobs.map(j=>'<li><span>分析</span>'+esc(j.name)+' · '+esc(j.status)+(j.approved?' · 已批准':'')+'</li>').concat(selected.reports.map(r=>'<li><span>计划</span>'+esc(r.name)+' · '+esc(r.destination)+' · '+(r.enabled?'启用':'暂停')+'</li>')).concat(selected.deliveries.map(d=>'<li><span>归档</span>'+esc(d.filename)+' · '+date(d.created_at)+'</li>')).join('')+'</ul><button class="primary" id="claim-chain" data-claim="'+selected.dataset_id+'">认领整条关联链 →</button><p class="hint">重复认领同一链路不会重复迁移；跨队冲突将保持整链不变。</p></div>':'<p class="empty">封存链路认领后，会出现在本车队的数据接入、结果复核与分发档案中。</p>')+'</section></div>';
}
export function bindLegacy(refresh){
 document.querySelector('#claim-chain')?.addEventListener('click',async e=>{
   e.target.disabled=true;
   try{const r=await legacy.claim(Number(e.target.dataset.claim));notify(r.duplicate?'该链路已由本车队认领，未重复迁移':'已认领整条关联链：'+r.counts.jobs+' 个分析、'+r.counts.reports+' 个计划、'+r.counts.deliveries+' 份归档');location.hash='#/legacy';await refresh();}
   catch(error){notify(error.message,true);e.target.disabled=false;}
 });
}
