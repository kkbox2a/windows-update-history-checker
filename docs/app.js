const state={data:null,channel:'stable',visible:[]};
const $=id=>document.getElementById(id);
const escapeHtml=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

function normalizeData(data){
  if(data.schema_version===2&&data.channels)return data;
  return {
    schema_version:2,
    product:data.product||'Windows 11',
    generated_at:data.generated_at,
    channels:{
      stable:{
        id:'stable',label:`Windows 11 ${data.version||'25H2'}`,version:data.version||'25H2',
        channel:'General Availability',count:data.count||data.updates?.length||0,
        latest_id:data.latest_kb||data.updates?.[0]?.kb||'',updates:data.updates||[]
      },
      dev:{id:'dev',label:'Windows 11 26H2 Dev / Experimental',version:'26H2',channel:'Dev / Experimental',count:0,latest_id:'',updates:[]}
    }
  };
}

function currentChannel(){return state.data.channels[state.channel]}
function badgeClass(type){return type==='Preview'?'preview':type==='Out-of-band'?'out-of-band':type==='Dev / Experimental'?'insider':''}
function buildsText(u){return `OS Build${u.builds.length>1?'s':''} ${u.builds.join(' and ')}`}
function itemLabel(u){return u.kb?`${u.date}—${u.kb}`:`${u.date}—Windows 11 Insider Preview Build ${u.builds[0]}`}

function markdown(u){
  if(u.channel==='Dev / Experimental'||u.update_type==='Dev / Experimental'){
    const kb=u.kb?` (${u.kb})`:'';
    return `# ${u.date}—Windows 11 Insider Preview Build ${u.builds[0]}${kb}\n- Channel: Dev / Experimental\n- Version: Windows 11 ${u.version||'26H2'}\n- [Release Notes](<${u.technical_url}>)`;
  }
  const msu=u.msu_x64_url?`- [Offline Installer (MSU, x64)](<${u.msu_x64_url}>)`:'- Offline Installer (MSU, x64): 尚未取得下載連結';
  return `# ${u.date}—${u.kb} (${buildsText(u)})${u.update_type==='Security / Cumulative'?'':` ${u.update_type}`}\n${msu}\n- [Technical Documentation](<${u.technical_url}>)`;
}

async function copyText(text,label='已複製'){
  try{await navigator.clipboard.writeText(text);toast(label)}
  catch{const ta=document.createElement('textarea');ta.value=text;document.body.append(ta);ta.select();document.execCommand('copy');ta.remove();toast(label)}
}
function toast(text){const t=$('toast');t.textContent=text;t.classList.add('show');clearTimeout(t._timer);t._timer=setTimeout(()=>t.classList.remove('show'),1900)}

function card(u,latest=false){
  const isDev=u.channel==='Dev / Experimental'||u.update_type==='Dev / Experimental';
  const primaryAction=isDev
    ?`<a class="button" href="${escapeHtml(u.technical_url)}" target="_blank" rel="noopener">查看 Release Notes</a>`
    :u.msu_x64_url
      ?`<a class="button" href="${escapeHtml(u.msu_x64_url)}" target="_blank" rel="noopener">下載 MSU x64</a>`
      :`<button class="button ghost" disabled>MSU 尚未取得</button>`;
  const secondaryAction=isDev?'':`<a class="button secondary" href="${escapeHtml(u.technical_url)}" target="_blank" rel="noopener">查看 Release Notes</a>`;
  const title=itemLabel(u);
  const kbLine=isDev&&u.kb?`<span class="build-chip">${escapeHtml(u.kb)}</span>`:'';
  return `<article class="update-card ${latest?'latest-card':''}">
    <div class="card-top">
      <div>
        <h3 class="card-title">${escapeHtml(title)}</h3>
        <div class="meta">${u.builds.map(b=>`<span class="build-chip">${escapeHtml(b)}</span>`).join('')}${kbLine}<span class="version-chip">${escapeHtml(u.version||'')}</span></div>
      </div>
      <span class="badge ${badgeClass(u.update_type)}">${escapeHtml(u.update_type)}</span>
    </div>
    <div class="actions">${primaryAction}${secondaryAction}<button class="button ghost copy-md" data-id="${escapeHtml(u.id||u.kb||u.builds[0])}">複製 Discord MD</button></div>
  </article>`;
}

function findItem(id){return currentChannel().updates.find(x=>(x.id||x.kb||x.builds[0])===id)}
function bindCopyButtons(){document.querySelectorAll('.copy-md').forEach(btn=>btn.addEventListener('click',()=>{const u=findItem(btn.dataset.id);if(u)copyText(markdown(u),`${u.id||u.kb||u.builds[0]} Markdown 已複製`)}))}

function updateTypeOptions(){
  const select=$('type-filter');
  if(state.channel==='dev'){
    select.innerHTML='<option value="all">全部 Dev / Experimental</option>';
    select.disabled=true;
  }else{
    select.innerHTML='<option value="all">全部類型</option><option value="Security / Cumulative">正式更新</option><option value="Preview">Preview</option><option value="Out-of-band">Out-of-band</option>';
    select.disabled=false;
  }
}

function render(){
  const channel=currentChannel();
  const q=$('search').value.trim().toLowerCase();
  const type=$('type-filter').value;
  state.visible=channel.updates.filter(u=>{
    const hay=[u.id,u.kb,u.date,u.update_type,u.channel,u.version,u.title,...u.builds].join(' ').toLowerCase();
    return(!q||hay.includes(q))&&(type==='all'||u.update_type===type);
  });
  $('result-count').textContent=`顯示 ${state.visible.length} / ${channel.updates.length} 筆更新`;
  $('updates').innerHTML=state.visible.length?state.visible.map(u=>card(u)).join(''):'<div class="empty">找不到符合條件的更新。</div>';
  const latest=channel.updates[0];
  $('latest-heading').textContent=state.channel==='dev'?'最新 Dev / Experimental Build':'目前最新正式版本';
  $('archive-heading').textContent=state.channel==='dev'?'26H2 Dev / Experimental 歷史 Build':'25H2 過往版本';
  if(latest){$('latest-section').classList.remove('hidden');$('latest-card').innerHTML=card(latest,true)}else{$('latest-section').classList.add('hidden');$('latest-card').innerHTML=''}
  bindCopyButtons();
}

function switchChannel(channelId){
  if(!state.data.channels[channelId])return;
  state.channel=channelId;
  document.querySelectorAll('.channel-tab').forEach(btn=>btn.classList.toggle('active',btn.dataset.channel===channelId));
  $('search').value='';
  updateTypeOptions();
  render();
}

async function init(){
  try{
    const r=await fetch(`data/updates.json?t=${Date.now()}`,{cache:'no-store'});
    if(!r.ok)throw new Error(`HTTP ${r.status}`);
    state.data=normalizeData(await r.json());
    const stable=state.data.channels.stable;
    const dev=state.data.channels.dev;
    const stableLatest=stable.updates?.[0];
    const stableBuild=stableLatest?.builds?.find(build=>String(build).startsWith('26200.'))||stableLatest?.builds?.[0]||'';
    const stableStatus=stable.latest_id
      ?`${stable.latest_id}${stableBuild?` / Build ${stableBuild}`:''}`
      :'尚無資料';
    $('status').className='status-card ok';
    $('status').innerHTML=`<strong>資料已載入</strong><span>更新時間：${new Date(state.data.generated_at).toLocaleString('zh-TW')}</span><span>25H2：${escapeHtml(stableStatus)}</span><span>26H2 Dev：${escapeHtml(dev.latest_id||'尚無資料')}</span>`;
    switchChannel('stable');
  }catch(e){$('status').className='status-card error';$('status').textContent=`資料載入失敗：${e.message}`}
}

document.querySelectorAll('.channel-tab').forEach(btn=>btn.addEventListener('click',()=>switchChannel(btn.dataset.channel)));
$('search').addEventListener('input',render);
$('type-filter').addEventListener('change',render);
$('copy-visible').addEventListener('click',()=>{if(!state.visible.length)return toast('目前沒有可複製項目');copyText(state.visible.map(markdown).join('\n\n\n'),'目前顯示項目已複製')});
init();