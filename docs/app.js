const state={data:null,visible:[]};
const $=id=>document.getElementById(id);
const escapeHtml=s=>String(s).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
function badgeClass(type){return type==='Preview'?'preview':type==='Out-of-band'?'out-of-band':''}
function buildsText(u){return `OS Build${u.builds.length>1?'s':''} ${u.builds.join(' and ')}`}
function markdown(u){
  const msu=u.msu_x64_url?`- [Offline Installer (MSU, x64)](<${u.msu_x64_url}>)`:'- Offline Installer (MSU, x64): 尚未取得下載連結';
  return `# ${u.date}—${u.kb} (${buildsText(u)})${u.update_type==='Security / Cumulative'?'':` ${u.update_type}`}\n${msu}\n- [Technical Documentation](<${u.technical_url}>)`;
}
async function copyText(text,label='已複製'){try{await navigator.clipboard.writeText(text);toast(label)}catch{const ta=document.createElement('textarea');ta.value=text;document.body.append(ta);ta.select();document.execCommand('copy');ta.remove();toast(label)}}
function toast(text){const t=$('toast');t.textContent=text;t.classList.add('show');clearTimeout(t._timer);t._timer=setTimeout(()=>t.classList.remove('show'),1900)}
function card(u,latest=false){
 const msu=u.msu_x64_url?`<a class="button" href="${escapeHtml(u.msu_x64_url)}" target="_blank" rel="noopener">下載 MSU x64</a>`:`<button class="button ghost" disabled>MSU 尚未取得</button>`;
 return `<article class="update-card ${latest?'latest-card':''}"><div class="card-top"><div><h3 class="card-title">${escapeHtml(u.date)}—${escapeHtml(u.kb)}</h3><div class="meta">${u.builds.map(b=>`<span class="build-chip">${escapeHtml(b)}</span>`).join('')}</div></div><span class="badge ${badgeClass(u.update_type)}">${escapeHtml(u.update_type)}</span></div><div class="actions">${msu}<a class="button secondary" href="${escapeHtml(u.technical_url)}" target="_blank" rel="noopener">技術文件</a><button class="button ghost copy-md" data-kb="${escapeHtml(u.kb)}">複製 Discord MD</button></div></article>`
}
function bindCopyButtons(){document.querySelectorAll('.copy-md').forEach(btn=>btn.addEventListener('click',()=>{const u=state.data.updates.find(x=>x.kb===btn.dataset.kb);copyText(markdown(u),`${u.kb} Markdown 已複製`)}))}
function render(){
 const q=$('search').value.trim().toLowerCase();const type=$('type-filter').value;
 state.visible=state.data.updates.filter(u=>{const hay=[u.kb,u.date,u.update_type,...u.builds].join(' ').toLowerCase();return(!q||hay.includes(q))&&(type==='all'||u.update_type===type)});
 $('result-count').textContent=`顯示 ${state.visible.length} / ${state.data.updates.length} 筆更新`;
 $('updates').innerHTML=state.visible.length?state.visible.map(u=>card(u)).join(''):'<div class="empty">找不到符合條件的更新。</div>';
 bindCopyButtons();
}
async function init(){
 try{
  const r=await fetch(`data/updates.json?t=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw new Error(`HTTP ${r.status}`);state.data=await r.json();
  const latest=state.data.updates[0];$('status').className='status-card ok';$('status').textContent=`已載入 ${state.data.count} 筆資料｜資料更新時間：${new Date(state.data.generated_at).toLocaleString('zh-TW')}｜最新：${state.data.latest_kb}`;
  if(latest){$('latest-section').classList.remove('hidden');$('latest-card').innerHTML=card(latest,true)}
  render();bindCopyButtons();
 }catch(e){$('status').className='status-card error';$('status').textContent=`資料載入失敗：${e.message}`}
}
$('search').addEventListener('input',render);$('type-filter').addEventListener('change',render);$('copy-visible').addEventListener('click',()=>{if(!state.visible.length)return toast('目前沒有可複製項目');copyText(state.visible.map(markdown).join('\n\n\n'),'目前顯示項目已複製')});
init();
