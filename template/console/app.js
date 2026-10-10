'use strict';
const $ = q => document.querySelector(q);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state = {data:null, view:'overview', role:'general-affairs', query:'', board:'circulars', filter:'open', docStack:[], docRequest:0, refreshRequest:0};
const views = {
  overview:['PEOPLE & CONNECTIONS','担当と仕事のつながり','誰が何を受け持ち、どこへ続きを頼めるか。仕事場の全体をここから。'],
  works:['WORK & OUTPUT','仕事と成果','何を頼み、どこまで進み、次に何をするか。原本から読み取ります。'],
  reports:['DAILY JOURNAL','日報・記録','一日の動きを振り返り、仕事の記録へ戻ります。'],
  boards:['SHARED BOARDS','共有板','みんなへの問いと返答、共有しておきたい情報を一か所に。'],
  guide:['GROW YOUR WORKSPACE','総えもんと、仕事場を育てる','動機を分かち合う相棒を迎え、必要な仲間を増やし、どこでも続きを。']
};
function guide(id){return state.data.guides.find(g=>g.id===id);}
function stamp(v){const d=new Date(v);return Number.isNaN(d.valueOf())?'日時未記入':d.toLocaleString('ja-JP',{timeZone:'Asia/Tokyo',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});}
function name(id){return state.data.roles.find(r=>r.id===id)?.name || id;}
function docButton(id,label='原本を読む',primary=false){return id?`<button class="button ${primary?'primary':''}" data-doc="${esc(id)}">${esc(label)} <span aria-hidden="true">↗</span></button>`:'<span class="muted">原本を確認できません</span>';}
function heading(extra=''){const [en,title,lead]=views[state.view];return `<div class="heading"><div><div class="eyebrow">${en}</div><h1>${title}</h1><p class="lead">${lead}</p></div>${extra}</div>`;}
function warnings(){return state.data.warnings.length?`<div class="notice error" role="alert"><b>読み取りに確認が必要です</b><ul>${state.data.warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ul></div>`:'';}
function job(w){return `<article class="job" id="work-${esc(w.id)}"><div class="job-head"><div><div class="eyebrow">${esc(name(w.owner))}</div><h2>${esc(w.title)}</h2></div><span class="badge">${esc(w.status)}</span></div><p>${esc(w.summary)}</p><div class="job-meta"><div><b>今回の到達点</b><p>${esc(w.doneWhen)}</p></div><div><b>成果・確認できたこと</b><p>${esc(w.result || '成果はまだ記録されていません。')}</p></div></div><div class="next"><b>次の一手</b>${esc(w.next)}</div><div class="actions">${docButton(w.document,'作業票と成果を読む',true)}${w.roles.map(r=>`<button class="button" data-role="${esc(r)}">${esc(name(r))}</button>`).join('')}</div><div class="record-time">原本の更新：${esc(stamp(w.recordedAt))} JST · 報告先：${esc(w.reportTo)}</div></article>`;}
function overview(){
  const {roles,works,reports,guides}=state.data;
  const query=state.query.toLocaleLowerCase('ja');
  const visible=roles.filter(r=>[r.name,r.purpose,r.id,r.type].join(' ').toLocaleLowerCase('ja').includes(query));
  const types=[...new Set(visible.map(r=>r.type))];
  const chosen=roles.find(r=>r.id===state.role) || roles[0];
  const related=chosen?works.filter(w=>w.roles.includes(chosen.id)):[];
  return heading(docButton(guide('start').document,'総えもんの案内を読む'))+
    `<section class="welcome" aria-label="仕事場を育てる入口"><div class="eyebrow">DOKODEMO DESK</div><h2>机の引き出しから、相棒がやってくる。</h2><p>総えもんが使い方をご案内し、必要な仲間を一緒に作ります。最初に迎えるのは、あなたの動機を受け持つ相棒です。</p><div class="journey"><span>01 やりたいことを話す</span><span>02 動機の伴走役を作る</span><span>03 仕事場づくりを画面で確かめる</span><span>04 次の担当へ相談する</span></div><div class="actions">${docButton(guide('purpose').document,'この仕事場の目的')}${docButton(guide('onboarding').document,'導入の設定と再開')}${docButton(guide('github').document,'保存・別端末で再開')}</div><p class="muted">継続する業務は専用チャットでも、同じチャットでも。総えもんが続きの頼み方を案内します。ボタンは原本を開きます。AIへの起動・通知は行いません。</p></section>`+
    `<div class="facts"><div class="fact"><strong>${roles.length}</strong><span>登録された担当</span></div><div class="fact"><strong>${works.length}</strong><span>記録された仕事</span></div><div class="fact"><strong>${reports.length}</strong><span>日報・月報</span></div></div>`+
    (state.data.mode==='example'?'<div class="notice">架空の制作室で試す練習例です。動機の伴走役・仕事・金額・日報は、実際の利用者への聞き取りや業務実績ではありません。</div>':'<div class="notice">あなた自身の仕事場です。初めてなら総えもんの案内から。導入済みなら記録を読み、次の仕事から再開できます。</div>')+
    `<div class="section-title"><div><h2>仕事を受け持つ担当</h2><p class="muted">役割の配置です。実行中の人数や指揮命令の順序ではありません。</p></div><label class="search"><span class="sr-only">担当を探す</span><input id="role-search" type="search" placeholder="担当や仕事で探す" value="${esc(state.query)}"></label></div><div class="map"><div class="role-groups">${visible.length?types.map(t=>`<section><div class="group-label">${esc(t)}<span>${visible.filter(r=>r.type===t).length}担当</span></div>${visible.filter(r=>r.type===t).map(r=>`<button class="role-card ${r.id===chosen?.id?'selected':''}" data-role="${esc(r.id)}" aria-pressed="${r.id===chosen?.id}"><strong>${esc(r.name)}</strong><p>${esc(r.purpose)}</p><small>${esc(r.state)}</small></button>`).join('')}</section>`).join(''):'<div class="empty">該当する担当がいません。別の言葉で探せます。</div>'}</div><aside class="detail" aria-label="選んだ担当">${chosen?`<span class="badge">${esc(chosen.type)}</span><h2>${esc(chosen.name)}</h2><p>${esc(chosen.purpose)}</p><div class="actions">${docButton(chosen.document,'役割を読む')}</div><div class="divider"><h3>この担当に関係する仕事</h3>${related.length?related.map(w=>`<p><button class="text-button" data-work="${esc(w.id)}">${esc(w.title)}</button></p>`).join(''):'<p>この形式で記録された仕事は、まだありません。</p>'}</div>`:'<h2>名簿から始めましょう</h2><p>総務と相談し、役割と名簿をそろえるとここに表示されます。</p>'}</aside></div><div class="section-title"><div><h2>一件の仕事から、続きをたどる</h2><p class="muted">担当 → 原本 → 成果 → 次の一手</p></div></div>${works.length?job(works[0]):emptyWork()}`;
}
function emptyWork(){return `<div class="empty"><h2>最初の仕事は、仕事場づくりから。</h2><p>まだ仕事の記録はありません。初めてなら総えもんが準備の記録を整え、担当・成果・続きの頼み方をここにつなぎます。導入済みなら、次に手伝ってほしい仕事を相談できます。</p><div class="actions">${docButton(guide('start').document,'相談の例を読む')}</div></div>`;}
function works(){return heading()+`<p class="muted">原本から ${state.data.works.length}件を読み込みました。担当が作業票を更新すると、次回の読み込みに反映されます。</p><div class="section-title"></div><div class="job-list">${state.data.works.length?state.data.works.map(job).join(''):emptyWork()}</div>`;}
function reports(){return heading()+(state.data.reports.length?`<div class="report-list">${state.data.reports.map(r=>`<button class="report-card" data-doc="${esc(r.document)}"><span class="badge">${r.kind}</span><strong>${esc(r.date)}</strong><span class="muted">原本と、その日の仕事を読む ↗</span></button>`).join('')}</div>`:'<div class="empty"><h2>日報は、まだありません。</h2><p>仕事の記録から一日の動きをまとめると、ここに表示されます。</p></div>');}
function boards(){
 const kind=state.board, data=state.data.boards;
 const list=kind==='circulars'?data.circulars.filter(i=>state.filter==='all'||i.status===state.filter):data.mail;
 return heading()+`<div class="tabs">${[['circulars','業務回覧板'],['mail','メール共有板']].map(([id,label])=>`<button class="button ${kind===id?'selected':''}" data-board="${id}" aria-pressed="${kind===id}">${label}</button>`).join('')}</div>`+
 (kind==='circulars'?`<div class="tabs">${[['open','回覧中'],['closed','終了'],['all','すべて']].map(([id,label])=>`<button class="button ${state.filter===id?'selected':''}" data-filter="${id}" aria-pressed="${state.filter===id}">${label}</button>`).join('')}</div>`:'')+
 '<p class="muted">画面を開いても、担当の既読・返答は変更されません。</p><div class="section-title"></div>'+
 (list.length?`<div class="board-grid">${list.map(i=>{const rows=kind==='circulars'?i.responses:i.receipts;return `<article class="board"><span class="badge">${kind==='circulars'?({open:'回覧中',closed:'終了',unknown:'状態不明'}[i.status]):'メール共有'}</span><h2>${esc(i.title)}</h2><p>${esc(i.author)} · ${esc(i.created || '日付未記入')}</p><details><summary>${kind==='circulars'?'対象と回答の記録':'対象と既読の記録'}</summary>${rows?`<div class="table-wrap"><table><thead><tr><th>担当</th>${kind==='circulars'?'<th>状態</th>':''}<th>日時</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(name(r.role))}</td>${kind==='circulars'?`<td>${esc(r.state)}</td>`:''}<td>${esc(r.at||'未記入')}</td></tr>`).join('')}</tbody></table></div>`:'原本の対象者の表を確認してください。'}</details><div class="actions">${docButton(i.document,'本文と返答を読む')}</div></article>`;}).join('')}</div>`:`<div class="empty"><h2>${kind==='circulars'?'この条件の回覧はありません。':'保存されたメール共有メモはありません。'}</h2><p>${kind==='mail'?'メールの取得は未接続です。受信箱を確認したという意味ではありません。':'原本に問いと返答を記録すると、ここから読めます。'}</p></div>`);
}
function guides(){return heading()+`<div class="guide-list">${state.data.guides.map((g,i)=>`<button class="guide" data-doc="${esc(g.document)}"><span>${String(i+1).padStart(2,'0')}</span><strong>${esc(g.title)} ↗</strong><p>${esc(g.description)}</p></button>`).join('')}</div><section class="limits"><h2>この版でつながっていること</h2><p>初回案内と目的・役割・作業の記録 → 原本の読み取り → この画面。ファイルを読めるAIへ、役割と作業票を渡して使います。GitHubでの保存・再開は、導入先で設定して使う手順です。</p><h2>これから接続できること</h2><p>別チャットへの通知、AIの自動起動、各アプリのモデル・使用量集計。どれも現在は未接続です。必要になった機能を一件ずつ加えます。</p></section>`;}
function render(){if(!state.data)return;$('#main').innerHTML=warnings()+({overview,works,reports,boards,guide:guides}[state.view])();document.querySelectorAll('[data-view]').forEach(a=>{if(a.dataset.view===state.view)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});}
async function api(url){const res=await fetch(url);const data=await res.json();if(!res.ok)throw new Error(data.error||'読み込めませんでした。');return data;}
async function refresh(){const request=++state.refreshRequest;$('#refresh').disabled=true;try{const data=await api('/api/snapshot');if(request!==state.refreshRequest)return;state.data=data;$('#organization').textContent=data.name;document.title='どこでもデスク｜自分たちで育てるAI仕事場 — '+data.name;$('#mode').textContent=data.mode==='example'?'練習例入りの仕事場':'あなたの仕事場';$('#updated').textContent='画面の読み込み：'+stamp(data.generated)+' JST';render();$('#announcement').textContent='原本を読み直しました。';}catch(error){$('#main').innerHTML=`<div class="notice error" role="alert">${esc(error.message)}</div>`;}finally{if(request===state.refreshRequest)$('#refresh').disabled=false;}}
function inline(raw,links){
 const decorate=text=>esc(text).replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');
 let out='',at=0;
 for(const m of raw.matchAll(/\[([^\]]+)\]\(([^)]+)\)/g)){
  out+=decorate(raw.slice(at,m.index));const label=decorate(m[1]),href=m[2];
  if(links[href])out+=`<button class="text-button" data-doc="${esc(links[href])}">${label}</button>`;
  else if(/^https?:\/\//i.test(href))out+=`<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${label}</a>`;
  else out+=label;
  at=m.index+m[0].length;
 }
 return out+decorate(raw.slice(at));
}
function markdown(text,links){
 const lines=text.replace(/^---\n[\s\S]*?\n---\n/,'').replace(/^<!--\s*\/?monku-work[^\n]*-->\s*$/gm,'').split('\n');
 let output='',paragraph=[],list=null,code=null,table=[];
 const flush=()=>{if(paragraph.length){output+=`<p>${inline(paragraph.join(' '),links)}</p>`;paragraph=[];}if(list){output+=`</${list}>`;list=null;}if(table.length){const rows=table.filter(r=>!/^\|?\s*:?-+/.test(r));output+='<div class="table-wrap"><table>'+rows.map((r,i)=>'<tr>'+r.trim().replace(/^\||\|$/g,'').split('|').map(c=>`<${i?'td':'th'}>${inline(c.trim(),links)}</${i?'td':'th'}>`).join('')+'</tr>').join('')+'</table></div>';table=[];}};
 for(const line of lines){
  if(line.startsWith('```')){flush();if(code===null)code=[];else{output+=`<pre><code>${esc(code.join('\n'))}</code></pre>`;code=null;}continue;}
  if(code!==null){code.push(line);continue;}
  if(line.startsWith('|')){if(!table.length)flush();table.push(line);continue;}
  if(table.length)flush();
  const h=line.match(/^(#{1,3})\s+(.+)/), item=line.match(/^\s*(?:([-*])|\d+\.)\s+(.+)/);
  if(!line.trim()){flush();continue;}
  if(h){flush();output+=`<h${h[1].length}>${inline(h[2],links)}</h${h[1].length}>`;}
  else if(item){if(paragraph.length)flush();const kind=item[1]?'ul':'ol';if(list&&list!==kind)flush();if(!list){list=kind;output+=`<${list}>`;}output+=`<li>${inline(item[2],links)}</li>`;}
  else if(line.startsWith('> ')){flush();output+=`<blockquote>${inline(line.slice(2),links)}</blockquote>`;}
  else{if(list)flush();paragraph.push(line);}
 }
 flush();if(code!==null)output+=`<pre>${esc(code.join('\n'))}</pre>`;return `<article class="document">${output}</article>`;
}
async function documentView(id,back=false){
 if(!$('#document-dialog').open){state.docStack=[];$('#document-dialog').showModal();}
 if(!back)state.docStack.push(id);
 const request=++state.docRequest;$('#document-body').innerHTML='<p>原本を読んでいます…</p>';
 try{const doc=await api('/api/document?id='+encodeURIComponent(id));if(request!==state.docRequest||!$('#document-dialog').open)return;$('#document-body').innerHTML=markdown(doc.body,doc.links)+`<div class="doc-source">原本：${esc(doc.source)}</div>`;$('#document-title').textContent=doc.body.match(/^# (.+)$/m)?.[1]||'原本を読む';$('#doc-back').hidden=state.docStack.length<2;$('#document-dialog').scrollTop=0;}catch(e){if(request===state.docRequest)$('#document-body').innerHTML=`<p role="alert">${esc(e.message)}</p>`;}
}
document.addEventListener('click',event=>{
 const b=event.target.closest('button');if(!b||!state.data)return;
 if(b.dataset.doc)documentView(b.dataset.doc);
 if(b.dataset.role){state.role=b.dataset.role;state.view='overview';location.hash='overview';render();}
 if(b.dataset.work){state.view='works';location.hash='works';render();document.getElementById('work-'+b.dataset.work)?.scrollIntoView({block:'start'});}
 if(b.dataset.board){state.board=b.dataset.board;render();}
 if(b.dataset.filter){state.filter=b.dataset.filter;render();}
});
document.addEventListener('input',event=>{if(event.target.id==='role-search'){const position=event.target.selectionStart;state.query=event.target.value;render();const input=$('#role-search');input.focus();try{input.setSelectionRange(position,position);}catch(_e){}}});
$('#refresh').addEventListener('click',refresh);
$('#doc-close').addEventListener('click',()=>$('#document-dialog').close());
$('#document-dialog').addEventListener('close',()=>{state.docRequest++;});
const back=document.createElement('button');back.id='doc-back';back.className='button';back.textContent='← 戻る';back.hidden=true;$('.dialog-bar').prepend(back);
back.addEventListener('click',()=>{if(state.docStack.length>1){state.docStack.pop();documentView(state.docStack.at(-1),true);}});
function route(){state.view=Object.hasOwn(views,location.hash.slice(1))?location.hash.slice(1):'overview';render();}
window.addEventListener('hashchange',route);route();refresh();
