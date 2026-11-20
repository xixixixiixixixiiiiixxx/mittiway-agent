'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icon = name => `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;
const state = {conversationId:null, documents:[], responses:new Map(), last:null, busy:false, filter:'all', scenario:'sales', ticketKey:null};
let toastTimer;

async function api(path,body){
  const controller = new AbortController();
  const timeout = setTimeout(()=>controller.abort(),35000);
  try{
    const response = await fetch(path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal});
    const result = await response.json();
    if(!response.ok) throw new Error(result.error || '请求未完成');
    return result;
  } finally {clearTimeout(timeout);}
}

function toast(message){
  clearTimeout(toastTimer);$('toast').textContent=message;$('toast').hidden=false;
  toastTimer=setTimeout(()=>$('toast').hidden=true,4500);
}
function view(name){
  const titles={chat:'客服助手',knowledge:'设备知识库',tickets:'会话与工单',guide:'开发与实施'};
  if(!titles[name]) name='chat';
  document.querySelectorAll('.view').forEach(el=>el.hidden=el.id!==`view-${name}`);
  document.querySelectorAll('.nav-item').forEach(el=>{const selected=el.dataset.view===name;el.classList.toggle('active',selected);if(selected)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});
  $('viewTitle').textContent=titles[name];
  if(location.hash!==`#${name}`)history.replaceState(null,'',`/#${name}`);
  if(name==='tickets') refreshRecords();
  if(name==='knowledge') renderKnowledge();
}

const prompts={sales:[
  {icon:'box',title:'查一台设备的参数',detail:'MTW-Z15 标准折盒机',question:'MTW-Z15 的参数是什么？'},
  {icon:'flow',title:'了解包装整线方案',detail:'从开箱、套袋到封箱码垛',question:'油脂行业包装整线怎么配置？'},
  {icon:'search',title:'找到合适的套袋设备',detail:'说说物料、容器和目标节拍',question:'纸箱内套袋设备怎么选？'},
  {icon:'building',title:'认识迈特威的产品',detail:'企业背景与主要设备系列',question:'迈特威有哪些主要设备？'}
],service:[
  {icon:'tools',title:'设备出现报警',detail:'先收集型号、报警和现象',question:'MTW-T50 报警 E001 怎么处理？'},
  {icon:'book',title:'查找维护资料',detail:'了解手册与 SOP 的资料缺口',question:'MTW-T50 的保养周期是多少？'},
  {icon:'shield',title:'安全问题如何升级',detail:'涉及安全联锁时交由专业人员',question:'能短接安全门继续运行吗？'},
  {icon:'ticket',title:'申请人工协助',detail:'记录咨询，创建本地模拟工单',question:'我需要联系工程师'}
]};
function renderPrompts(){
  $('promptGrid').innerHTML=prompts[state.scenario].map(p=>`<button class="prompt-card" data-ask="${esc(p.question)}">${icon(p.icon)}<span><strong>${esc(p.title)}</strong><small>${esc(p.detail)}</small></span></button>`).join('');
}
function formatInline(text){return esc(text).replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');}
function formatAnswer(text){
  return text.split(/\n\s*\n/).map(block=>{
    const lines=block.trim().split('\n');
    if(lines.length>2 && lines[0].trim().startsWith('|') && /^\|?[-:|\s]+\|?$/.test(lines[1].trim())){
      const rows=lines.filter((_,i)=>i!==1).map(line=>line.trim().replace(/^\||\|$/g,'').split('|').map(x=>x.trim()));
      return `<div class="answer-table-wrap" tabindex="0" aria-label="设备资料对比表"><table class="answer-table"><thead><tr>${rows[0].map(c=>`<th scope="col">${formatInline(c)}</th>`).join('')}</tr></thead><tbody>${rows.slice(1).map(row=>`<tr>${row.map(c=>`<td>${formatInline(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
    }
    return `<p>${lines.map(formatInline).join('<br>')}</p>`;
  }).join('');
}
function addUser(text){
  const wrapper=document.createElement('div');wrapper.className='message user-message';
  const bubble=document.createElement('div');bubble.className='user-bubble';bubble.textContent=text;wrapper.append(bubble);$('transcript').append(wrapper);
}
function uniqueSources(sources){const seen=new Set();return sources.filter(s=>{if(seen.has(s.id))return false;seen.add(s.id);return true;});}
function addAssistant(result,id){
  const key=id||`temp-${Date.now()}`;state.responses.set(key,result);
  const sources=uniqueSources(result.citations||[]);
  const wrapper=document.createElement('article');wrapper.className='message assistant-message';wrapper.dataset.message=key;
  const warning=['handoff','conflict'].includes(result.status);
  wrapper.innerHTML=`<div class="assistant-meta"><img src="/favicon.svg" alt="" width="25" height="25"><strong>迈特威设备助手</strong><span class="response-status ${warning?'warning':''}">${esc(result.status_label||'资料答复')}</span></div><div class="assistant-body">${formatAnswer(result.answer)}${sources.length?`<div class="citation-list">${sources.slice(0,3).map((s,i)=>`<button class="citation-button" data-source="${esc(key)}" data-source-index="${i}">${icon(s.type==='web'?'globe':'file')}<span>${esc(s.type==='catalog'?s.locator:s.title)}</span></button>`).join('')}${sources.length>3?`<button class="citation-button" data-all-sources="${esc(key)}">全部 ${sources.length} 个出处</button>`:''}</div>`:''}${result.notes?.length?`<p class="generation-note">${esc(result.notes.join(' '))}</p>`:''}<div class="response-actions"><button class="feedback-button" data-feedback="helpful" data-id="${esc(key)}" aria-label="这条回答有帮助" aria-pressed="false">${icon('thumb')}<span>有帮助</span></button><button class="feedback-button negative" data-feedback="unhelpful" data-id="${esc(key)}" aria-label="这条回答需改进" aria-pressed="false">${icon('thumb')}<span>需改进</span></button>${result.can_create_ticket?'<button class="ticket-link" data-ticket="true">创建本地模拟工单</button>':''}</div></div>`;
  $('transcript').append(wrapper);
}
function renderTrace(result){
  $('traceStatus').textContent=result.status_label;
  $('trace').innerHTML=result.trace.map(t=>`<div class="trace-step ${t.status==='warning'?'warning':''}"><span class="trace-dot">${icon(t.status==='warning'?'alert':t.status==='skipped'?'clock':'check')}</span><div><strong>${esc(t.label)}</strong><p>${esc(t.detail)}</p></div></div>`).join('');
  const labels={models:'设备型号',industry:'物料／行业',container:'容器',size:'容器规格',throughput:'目标节拍',alarm:'报警代码'};
  const entries=Object.entries(result.slots||{}).filter(([k])=>labels[k]);
  $('slotSection').hidden=entries.length===0;
  $('slotList').innerHTML=entries.map(([key,value])=>`<dt>${labels[key]}</dt><dd>${esc(Array.isArray(value)?value.join('、'):value)}</dd>`).join('');
  $('suggestions').innerHTML=(result.suggestions||[]).map(s=>`<button ${s==='创建本地模拟工单'?'data-ticket="true"':`data-ask="${esc(s)}"`}>${esc(s)}</button>`).join('');
}
function scrollChat(){requestAnimationFrame(()=>$('chatViewport').scrollTop=$('chatViewport').scrollHeight);}
function setBusy(busy){
  state.busy=busy;$('sendButton').disabled=busy;$('sendButton').textContent=busy?'查找中…':'发送';$('messageInput').disabled=busy;$('newConversation').disabled=busy;
}
async function ask(text){
  if(state.busy || !text.trim())return;
  view('chat');const question=text.trim();
  $('welcome').hidden=true;$('messageInput').value='';$('suggestions').innerHTML='';addUser(question);setBusy(true);
  const loader=document.createElement('div');loader.className='loading-message';loader.innerHTML='正在核对资料 <span></span><span></span><span></span>';$('transcript').append(loader);scrollChat();
  try{
    const result=await api('/api/chat',{message:question,conversation_id:state.conversationId});
    state.conversationId=result.conversation_id;localStorage.setItem('mittiway_conversation',state.conversationId);state.last=result;
    loader.remove();addAssistant(result,result.message_id);renderTrace(result);$('exportConversation').disabled=false;
  } catch(error){
    loader.remove();toast(error.name==='AbortError'?'请求等待超时，请稍后重新载入会话确认。':error.message);$('messageInput').value=question;
    const errorBlock=document.createElement('p');errorBlock.className='info-banner';errorBlock.textContent='本次请求未完成，请检查本地服务后重试。';$('transcript').append(errorBlock);
  } finally {setBusy(false);scrollChat();$('messageInput').focus();}
}
function resetConversationUI(){
  $('transcript').innerHTML='';$('suggestions').innerHTML='';$('welcome').hidden=false;$('messageInput').value='';$('exportConversation').disabled=true;state.last=null;state.responses.clear();$('traceStatus').textContent='等待提问';$('trace').innerHTML=`<div class="trace-placeholder">${icon('flow')}<p>提问后，查看资料检索、<br>证据检查和下一步处理。</p></div>`;$('slotSection').hidden=true;$('slotList').innerHTML='';$('chatViewport').scrollTop=0;
}
async function newConversation(){
  if(state.busy)return;
  try{const conv=await api('/api/conversations',{});state.conversationId=conv.id;localStorage.setItem('mittiway_conversation',conv.id);resetConversationUI();view('chat');$('messageInput').focus();}catch(e){toast(e.message);}
}
async function loadConversation(cid){
  const conv=await api(`/api/conversations/${encodeURIComponent(cid)}`);state.conversationId=conv.id;localStorage.setItem('mittiway_conversation',conv.id);resetConversationUI();
  if(conv.messages.length){$('welcome').hidden=true;for(const m of conv.messages){if(m.role==='user')addUser(m.content);else if(m.payload){addAssistant(m.payload,m.id);state.last=m.payload;}}if(state.last)renderTrace(state.last);$('exportConversation').disabled=false;}
  view('chat');scrollChat();
}
function safeSourceUrl(url){
  try{const value=new URL(url,location.origin);return ['http:','https:'].includes(value.protocol)?value.href:'#';}catch{return '#';}
}
function openSources(title,sources,text=''){
  $('sourceTitle').textContent=title;
  const unique=uniqueSources(sources);
  $('sourceContent').innerHTML=`${text?`<div class="source-excerpt">${esc(text)}</div>`:''}${unique.map(s=>`<div class="source-entry"><h3>${esc(s.title)}</h3><p>${esc(s.locator)}<br>${esc(s.version)}<br>检索／核对日期：${esc(s.accessed_at||'2026-11-20')}</p><a href="${esc(safeSourceUrl(s.url))}" target="_blank" rel="noopener noreferrer">${s.type==='catalog'?'查看原始 PDF 对应页':s.type==='web'?'查看官网来源':'查看演示范围说明'}</a></div>`).join('')}<p class="source-review">核心条目由演示开发过程人工转录与核对，尚未经企业正式审核。营销资料不替代设备铭牌、合同技术协议或经批准的操作手册。</p>`;
  if(!$('sourceDialog').open)$('sourceDialog').showModal();
}
function openKnowledge(id){
  const d=state.documents.find(d=>d.id===id);if(d)openSources(`${d.model||''} ${d.title}`.trim(),d.sources,d.text+(d.note?`\n\n资料提示：${d.note}`:''));
}
function renderKnowledge(){
  const query=$('knowledgeSearch').value.trim().toUpperCase();
  const all=state.documents.filter(d=>d.kind==='product');
  const docs=all.filter(d=>(state.filter==='all'||d.category===state.filter)&&(!query||`${d.model} ${d.title} ${d.text}`.toUpperCase().includes(query)));
  $('knowledgeCount').textContent=`${all.length} 个设备条目`;
  $('knowledgeGrid').innerHTML=docs.length?docs.map(d=>`<article class="product-card"><div class="card-top"><span class="card-icon">${icon(d.category==='折盒成型'?'box':d.category==='套袋封口'?'flow':'tools')}</span><span class="tag">${esc(d.category)}</span></div><span class="card-model">${esc(d.model)}</span><h2>${esc(d.title)}</h2><p class="card-summary">${esc(d.summary)}</p><div class="card-spec"><span>参考速度</span><strong>${esc(d.specs['参考速度'])}</strong></div><div class="card-source">${esc(d.sources[0].type==='catalog'?d.sources[0].locator:'官网资料 · 2026.11.20')}</div><div class="card-buttons"><button class="button button-outline" data-knowledge="${esc(d.id)}">查看依据</button><button class="button button-outline" data-ask="${esc(d.model)} 的参数是什么？">咨询此设备</button></div></article>`).join(''):`<div class="empty-state">没有找到匹配设备。请核对型号或尝试其他关键词。</div>`;
}
function dateString(value){return new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});}
async function refreshRecords(){
  try{
    const [convs,tickets]=await Promise.all([api('/api/conversations'),api('/api/tickets')]);
    $('conversationList').innerHTML=convs.conversations.length?convs.conversations.map(c=>`<button class="conversation-record" data-conversation="${esc(c.id)}"><strong>${esc(c.title)}</strong><span class="record-date">${esc(dateString(c.updated_at))} · 打开会话</span></button>`).join(''):`<div class="empty-state">${icon('chat')}<p>还没有咨询记录。<br>从客服助手开始一次提问。</p></div>`;
    const category={consultation:'产品咨询',selection:'选型与整线',fault:'故障与维护'};
    $('ticketList').innerHTML=tickets.tickets.length?tickets.tickets.map(t=>`<article class="ticket-record"><div class="ticket-header"><strong class="ticket-number">${esc(t.id)}</strong><span class="local-status">本地待人工确认</span></div><h3>${esc(t.summary)}</h3><p>${esc(category[t.category])}${t.slots.models?` · ${esc(t.slots.models.join('、'))}`:''}</p>${t.details?`<p>${esc(t.details)}</p>`:''}<span class="record-date">${esc(dateString(t.created_at))} · 未发送厂家</span></article>`).join(''):`<div class="empty-state">${icon('ticket')}<p>暂无本地工单。<br>在咨询中整理信息后按需创建。</p></div>`;
  }catch(e){toast(e.message);}
}
async function openTicket(){
  if(state.busy)return;
  if(!state.conversationId){const c=await api('/api/conversations',{});state.conversationId=c.id;localStorage.setItem('mittiway_conversation',c.id);}
  state.ticketKey=crypto.randomUUID();$('ticketDetails').value='';$('ticketError').textContent='';$('saveTicket').disabled=false;$('saveTicket').textContent='保存到本机';
  $('ticketCategory').value=['fault','maintenance','safety'].includes(state.last?.intent)?'fault':['selection','solution','quote'].includes(state.last?.intent)?'selection':'consultation';
  $('ticketDialog').showModal();
}
async function saveTicket(event){
  event.preventDefault();$('saveTicket').disabled=true;$('saveTicket').textContent='正在保存…';$('ticketError').textContent='';
  try{
    const result=await api('/api/tickets',{conversation_id:state.conversationId,category:$('ticketCategory').value,details:$('ticketDetails').value,idempotency_key:state.ticketKey});
    $('ticketDialog').close();toast(`工单 ${result.id} 已保存在本机，未发送厂家。`);
  }catch(e){$('ticketError').textContent=e.message;$('saveTicket').disabled=false;$('saveTicket').textContent='重试保存';}
}
async function feedback(button){
  try{await api('/api/feedback',{message_id:button.dataset.id,rating:button.dataset.feedback});const article=button.closest('.assistant-message');article.querySelectorAll('[data-feedback]').forEach(b=>{const selected=b===button;b.classList.toggle('selected',selected);b.setAttribute('aria-pressed',String(selected));});toast('反馈已记录在本机。');}catch(e){toast(e.message);}
}

const phases=[
  ['企业诊断','3–5 天','访谈业务与一线人员，盘点授权资料，确认一个设备类别和服务流程。','输出：范围、授权、资料清单与基线'],
  ['知识加工','原型期第 1 周','扫描件 OCR 与表格校对；整理型号、版本、权限、生效状态和知识缺口。','输出：可审查知识片段与词表'],
  ['工作流原型','原型期第 2–3 周','接入检索、受约束答复、追问、人工升级、反馈与会话状态。','输出：可运行原型与回归问题集'],
  ['离线验证','试点前','测试型号混淆、引用支持、未知报警、资料冲突、越权和危险问题。','输出：人工复核与问题修复记录'],
  ['受控试点','3–4 周','限定用户与设备，记录查找耗时、有效反馈、升级和实际运行成本。','输出：质量与业务价值评估'],
  ['交付评审','1–2 周','确认知识维护人、系统接口、培训与运维责任，决定继续、调整或停止。','输出：验收、交接与后续实施范围']
];
function renderRoadmap(){$('roadmap').innerHTML=phases.map(p=>`<article class="roadmap-card"><span class="phase">${esc(p[1])}</span><h3>${esc(p[0])}</h3><p>${esc(p[2])}</p><div class="deliverable">${esc(p[3])}</div></article>`).join('');}

document.addEventListener('click',async event=>{
  const button=event.target.closest('button');if(!button)return;
  if(button.dataset.view){view(button.dataset.view);return;}
  if(button.dataset.ask){ask(button.dataset.ask);return;}
  if(button.dataset.ticket){try{await openTicket();}catch(e){toast(e.message);}return;}
  if(button.dataset.knowledge){openKnowledge(button.dataset.knowledge);return;}
  if(button.dataset.scenario){state.scenario=button.dataset.scenario;document.querySelectorAll('[data-scenario]').forEach(b=>{const active=b===button;b.classList.toggle('selected',active);b.setAttribute('aria-pressed',String(active));});renderPrompts();return;}
  if(button.dataset.filter){state.filter=button.dataset.filter;document.querySelectorAll('[data-filter]').forEach(b=>{const active=b===button;b.classList.toggle('selected',active);b.setAttribute('aria-pressed',String(active));});renderKnowledge();return;}
  if(button.dataset.source){const result=state.responses.get(button.dataset.source);const source=uniqueSources(result.citations)[Number(button.dataset.sourceIndex)];const related=result.citations.filter(c=>c.document_id===source.document_id);openSources(source.document_title,related,source.excerpt);return;}
  if(button.dataset.allSources){const result=state.responses.get(button.dataset.allSources);openSources('本轮采用的资料来源',result.citations);return;}
  if(button.dataset.conversation){try{await loadConversation(button.dataset.conversation);}catch(e){toast(e.message);}return;}
  if(button.dataset.feedback){feedback(button);return;}
});
$('chatForm').addEventListener('submit',e=>{e.preventDefault();ask($('messageInput').value);});
$('messageInput').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();ask(e.target.value);}});
$('newConversation').addEventListener('click',newConversation);
$('knowledgeSearch').addEventListener('input',renderKnowledge);
$('refreshRecords').addEventListener('click',refreshRecords);
$('learnFlow').addEventListener('click',()=>view('guide'));
$('exportConversation').addEventListener('click',()=>{if(state.conversationId)location.assign(`/api/export/${encodeURIComponent(state.conversationId)}`);});
$('catalogOverview').addEventListener('click',()=>{const sources=state.documents.filter(d=>['company','families'].includes(d.id)).flatMap(d=>d.sources).filter(s=>s.type==='catalog');openSources('2026 迈特威画册',sources,'23 页扫描画册已逐页视觉核对，核心产品条目已人工转录。保留 PDF 物理页和印刷页两种定位；当前并未将整份扫描件自动 OCR 成生产知识库。');});
$('websiteOverview').addEventListener('click',()=>{const sources=state.documents.flatMap(d=>d.sources).filter(s=>s.type==='web');openSources('迈特威官方产品资料',sources,'2026 年 11 月 20 日搜索并核对官网公司介绍、产品列表及典型型号参数。网页与画册存在差异时保留两个来源，等待企业确认适用配置。');});
$('closeSource').addEventListener('click',()=>$('sourceDialog').close());
['closeTicket','cancelTicket'].forEach(id=>$(id).addEventListener('click',()=>$('ticketDialog').close()));
$('ticketForm').addEventListener('submit',saveTicket);
window.addEventListener('hashchange',()=>view(location.hash.slice(1)));
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='k'){e.preventDefault();view('chat');$('messageInput').focus();}});

async function init(){
  renderPrompts();renderRoadmap();
  const initialView=location.pathname==='/guide'?'guide':location.hash.slice(1)||'chat';
  try{
    const boot=await api('/api/bootstrap');
    $('modeBadge').textContent=boot.mode==='offline'?'本地模拟':'模型已配置';$('productCount').textContent=boot.products;$('recordCount').textContent=boot.knowledge_records;$('welcomeCount').textContent=`${boot.products} 个设备条目 · 画册与官网资料`;
    const data=await api('/api/knowledge');state.documents=data.documents;
    const saved=localStorage.getItem('mittiway_conversation');if(saved){try{await loadConversation(saved);}catch{localStorage.removeItem('mittiway_conversation');}}
    view(initialView);
  }catch(e){toast('本地服务尚未就绪，请按 README 启动后刷新。');}
}
init();
