const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels={pendente:'Pendente',encaminhado:'Encaminhado',assinado:'Assinado',secretaria:'Secretaria',coordenador:'Coordenador',superintendente:'Superintendente',profissional:'Profissional',administrador:'Administrador'};
let state,view='documents',filters={search:'',status:'',area:''};
const dateTime = s => s ? new Date(s).toLocaleString('pt-BR') : 'Não informado';
const date = s => new Date(s).toLocaleDateString('pt-BR');
async function api(path,data){const r=await fetch('/api/'+path,{method:data?'POST':'GET',headers:data?{'Content-Type':'application/json'}:{},body:data?JSON.stringify(data):undefined});const body=await r.json();if(!r.ok){if(r.status===401&&path!=='login')showLogin();throw Error(body.error||'Não foi possível concluir a operação.');}return body;}
function toast(message){$('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').hidden=true,5000);}
function showLogin(){state=null;$('#document-dialog').close();$('#document-detail').replaceChildren();$('#page-content').replaceChildren();$('#workspace').hidden=true;$('#login-page').hidden=false;}
async function load(){state=await api('state');$('#login-page').hidden=true;$('#workspace').hidden=false;$('#user-label').textContent=state.user.name+' · '+labels[state.user.role];$('#scope').textContent=state.user.sector+' / '+state.user.area;
const real=state.integration.mode==='mv';
$('.demo-pill').textContent=real?'● MV conectado':'● Demonstração';
document.querySelectorAll('.nav').forEach(b=>{b.hidden=b.dataset.view==='access'?!state.integration.is_master:real&&!['documents','integration'].includes(b.dataset.view);});
$('.demo-banner').textContent=real?'MV · Consulta somente leitura · Documentos FECHADOS que exigem assinatura.':'Painel de demonstração · Dados fictícios. Consulta real restrita a usuários autorizados.';
if(state.integration.is_master)$('#user-label').textContent=state.user.name+' · Administrador master';
if(real&&!['documents','integration','access'].includes(view))view='documents';if(view==='access'&&!state.integration.is_master)view='documents';render();}
$('#login-form').addEventListener('submit',async e=>{e.preventDefault();const b=$('.login-submit');b.disabled=true;$('#login-error').textContent='';try{await api('login',{username:$('#username').value.trim(),password:$('#password').value});$('#password').value='';view='documents';filters={search:'',status:'',area:''};await load();}catch(err){$('#login-error').textContent=err.message;}finally{b.disabled=false;}});
$('#show-password').onclick=()=>{const p=$('#password');p.type=p.type==='password'?'text':'password';$('#show-password').textContent=p.type==='password'?'Mostrar':'Ocultar';};
$('#logout').onclick=async()=>{try{await api('logout',{});showLogin();}catch(e){toast(e.message);}};
$('#refresh').onclick=async()=>{try{await load();toast('Painel atualizado.');}catch(e){toast(e.message);}};
document.querySelectorAll('.nav').forEach(b=>b.onclick=()=>{view=b.dataset.view;filters={search:'',status:'',area:''};render();});
$('#close-dialog').onclick=()=>$('#document-dialog').close();
function render(){document.querySelectorAll('.nav').forEach(b=>b.classList.toggle('active',b.dataset.view===view));$('#page-title').textContent={documents:'Visão geral',inbox:'Minha fila',audit:'Histórico de ações',access:'Acessos e permissões',integration:'Integração com o MV'}[view];$('#page-description').textContent={documents:'Cada pendência acompanhada. Cada ação registrada.',inbox:'Documentos encaminhados diretamente para você.',audit:'Rastreabilidade dos documentos do seu escopo de acesso.',access:'Vínculos e permissões cadastrados nesta demonstração.',integration:'Conexões e próximos passos para receber os documentos.'}[view];
 if(view==='documents'&&state.integration.mode==='mv')return renderMVIntegration();
 if(view==='documents'||view==='inbox')return renderDocuments();
 if(view==='audit'){$('#page-content').innerHTML='<section class="panel">'+state.audit.map(a=>`<article class="audit-item"><b>${esc(a.action)}</b> · Documento ${esc(a.document_id)}<p>${esc(a.detail)}</p><small>${esc(a.actor_name)} · ${esc(new Date(a.created).toLocaleString('pt-BR'))}</small></article>`).join('')+'</section>';return;}
 if(view==='access'){if(!state.integration.is_master){view='documents';return render();}return renderMVAccess();}

 renderMVIntegration();
}
function renderDocuments(){const docs=state.documents.filter(d=>view!=='inbox'||d.assignee===state.user.id);const counts=status=>docs.filter(d=>d.status===status).length;$('#page-content').innerHTML=`<section class="stats" aria-label="Resumo"><article class="stat"><div class="stat-label">Documentos <i>▤</i></div><strong>${docs.length}</strong><small>No seu escopo de acesso</small></article><article class="stat"><div class="stat-label">Pendentes <i>◷</i></div><strong>${counts('pendente')}</strong><small>Aguardando encaminhamento</small></article><article class="stat"><div class="stat-label">Encaminhados <i>↗</i></div><strong>${counts('encaminhado')}</strong><small>Com responsável definido</small></article><article class="stat"><div class="stat-label">Assinados <i>✓</i></div><strong>${counts('assinado')}</strong><small>Registros fictícios de exemplo</small></article></section><section class="panel"><div class="panel-heading"><div><h2>Documentos assistenciais</h2><p>Organize as pendências da sua equipe.</p></div><span class="badge encaminhado">${esc(state.user.area)}</span></div><div class="filters"><input id="search" aria-label="Buscar documentos" placeholder="Buscar documento, profissional ou código…" value="${esc(filters.search)}"><select id="status-filter" aria-label="Filtrar situação"><option value="">Todas as situações</option>${['pendente','encaminhado','assinado'].map(s=>`<option value="${s}" ${filters.status===s?'selected':''}>${labels[s]}</option>`).join('')}</select><select id="area-filter" aria-label="Filtrar área"><option value="">Todas as áreas</option>${[...new Set(docs.map(d=>d.area))].map(a=>`<option ${filters.area===a?'selected':''}>${esc(a)}</option>`).join('')}</select></div><div class="table-scroll"><table><thead><tr><th>Documento / paciente</th><th>Autor original</th><th>Data</th><th>Situação</th><th></th></tr></thead><tbody id="rows"></tbody></table></div><div class="table-foot" id="count"></div></section>`;$('#search').oninput=e=>{filters.search=e.target.value;rows(docs);};$('#status-filter').onchange=e=>{filters.status=e.target.value;rows(docs);};$('#area-filter').onchange=e=>{filters.area=e.target.value;rows(docs);};rows(docs);}
function rows(docs){const selected=docs.filter(d=>(!filters.status||d.status===filters.status)&&(!filters.area||d.area===filters.area)&&[d.title,d.author,d.patient,d.mv_id].join(' ').toLocaleLowerCase('pt-BR').includes(filters.search.toLocaleLowerCase('pt-BR')));$('#rows').innerHTML=selected.length?selected.map(d=>`<tr><td><b>${esc(d.title)}</b><small>${esc(d.mv_id)} · ${esc(d.patient)}</small></td><td>${esc(d.author)}<small>${esc(d.area)} · ${esc(d.sector)}</small></td><td>${date(d.created)}</td><td><span class="badge ${d.status}">${labels[d.status]}</span></td><td><button class="row-action" data-document="${d.id}">${state.user.role==='secretaria'&&d.status==='pendente'?'Encaminhar':'Ver detalhes'} →</button></td></tr>`).join(''):'<tr><td colspan="5" class="empty">Nenhum documento encontrado para esta seleção.</td></tr>';$('#count').textContent=`${selected.length} documento(s) · Fonte: demonstração local`;document.querySelectorAll('[data-document]').forEach(b=>b.onclick=()=>openDocument(Number(b.dataset.document)));}
function openDocument(id){const d=state.documents.find(x=>x.id===id);const eligible=state.users.filter(u=>['coordenador','superintendente'].includes(u.role)&&u.sector===d.sector&&u.area===d.area);const canForward=state.user.role==='secretaria'&&d.status==='pendente';$('#document-detail').innerHTML=`<h2>${esc(d.title)}</h2><span class="badge ${d.status}">${labels[d.status]}</span><div class="detail-grid">${[['Código',d.mv_id],['Paciente',d.patient],['Autor original',d.author],['Setor',d.sector],['Área',d.area],['Destinatário',d.recipient||'Não atribuído']].map(([k,v])=>`<div><small>${k}</small><b>${esc(v)}</b></div>`).join('')}</div><p class="notice">Este registro é fictício. O encaminhamento não representa uma assinatura e preserva o autor original.</p>${canForward?`<form id="forward-form"><label for="recipient">Encaminhar para</label><select required id="recipient"><option value="">Selecione o responsável</option>${eligible.map(u=>`<option value="${u.id}">${esc(u.name)} · ${labels[u.role]}</option>`).join('')}</select><label for="reason">Justificativa do encaminhamento</label><textarea id="reason" minlength="10" maxlength="1000" required placeholder="Descreva o motivo (mínimo de 10 caracteres)"></textarea><p class="error" id="forward-error" role="alert"></p><div class="dialog-actions"><button class="primary" type="submit">Confirmar encaminhamento →</button></div></form>`:'<p class="notice">A assinatura real será realizada pelo mecanismo oficial do MV, após a integração. Não está disponível nesta demonstração.</p>'}`;if(canForward)$('#forward-form').onsubmit=async e=>{e.preventDefault();const button=e.target.querySelector('button');button.disabled=true;try{await api('forward',{document_id:id,recipient_id:Number($('#recipient').value),reason:$('#reason').value});$('#document-dialog').close();await load();toast('Documento encaminhado. A ação foi registrada na auditoria.');}catch(err){$('#forward-error').textContent=err.message;}finally{button.disabled=false;}};setupDocumentTabs(d);$('#document-dialog').showModal();}
let mvRequestVersion=0;
function renderMVIntegration() {
 const permitted=state.integration.mv_access;
 const dashboard=view==='documents';
 const today=new Date();
 const localDate=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
 const start=new Date(today);start.setDate(start.getDate()-6);
 $('#page-content').innerHTML=`${dashboard?`<section class="stats"><article class="stat"><div class="stat-label">Documentos nesta página</div><strong id="mv-total">—</strong><small>Consulta ao vivo no MV</small></article><article class="stat"><div class="stat-label">Pendentes nesta página</div><strong id="mv-pending">—</strong><small>Prontos para assinatura no MV</small></article><article class="stat"><div class="stat-label">Transferências</div><strong>—</strong><small>Integração em validação</small></article><article class="stat"><div class="stat-label">Assinatura</div><strong>MV</strong><small>Realizada no sistema MV</small></article></section>`:''}<section class="panel info-block"><h2>Documentos assistenciais</h2><p>Documentos prontos e aguardando assinatura, conforme o filtro aprovado.</p><div class="integration-grid" ${dashboard?'hidden':''}><div class="connection"><span class="badge encaminhado">Consulta somente leitura</span><b>Documentos FECHADOS</b><p>Somente objetos com SN_ASSINATURA = S.<br>Abertos, assinados, cancelados e importados não aparecem.</p></div><div class="connection"><span class="badge ${permitted?'assinado':'pendente'}">${permitted?'Acesso autorizado':'Aguardando vínculo'}</span><b>Consulta institucional</b><p>${permitted?'Todos os setores disponíveis para leitura. Encaminhamento exige permissão específica.':'As contas de demonstração não podem consultar documentos reais. É necessário cadastrar o usuário institucional e seus vínculos.'}</p></div></div><form id="mv-search-form"><div class="mv-query-filters"><div><label for="mv-start">Data inicial</label><input id="mv-start" type="date" required value="${localDate(start)}"></div><div><label for="mv-end">Data final</label><input id="mv-end" type="date" required value="${localDate(today)}"></div><div><label for="mv-sector">Setor MV</label><input id="mv-sector-search" placeholder="Buscar setor por nome" aria-label="Buscar setor por nome"><select id="mv-sector"><option value="">Todos os setores</option></select></div></div><p>Até 31 dias por consulta · 50 documentos por página · Ordenação por código decrescente.</p><button class="primary" ${permitted?'':'disabled'}>Consultar pendências</button></form><p class="error" id="mv-error" role="alert"></p><div id="mv-results" aria-live="polite"></div><div class="notice">A consulta não altera o MV. Transferência real em validação. A assinatura será feita somente no MV. A aba Documento apresenta o PDF disponível ou os campos reais do Editor, quando vinculados.</div></section>`;
 let next=null,query=null,currentDocuments=[],pageIndex=0,pageCursors=[null],busy=false;
 const requestVersion=++mvRequestVersion;
 const userId=state.user.id;
 if(permitted)api('mv/sectors').then(result=>{if(requestVersion!==mvRequestVersion||!state||state.user.id!==userId||!['integration','documents'].includes(view))return;const sectors=result.sectors;const paint=()=>{$('#mv-sector').innerHTML='<option value="">Todos os setores</option>'+sectors.filter(s=>s.name.toLocaleLowerCase('pt-BR').includes($('#mv-sector-search').value.toLocaleLowerCase('pt-BR'))).map(s=>`<option value="${s.id}">${esc(s.name)}</option>`).join('');};$('#mv-sector-search').oninput=paint;paint();}).catch(e=>{if(requestVersion===mvRequestVersion&&['integration','documents'].includes(view)&&state)$('#mv-error').textContent=e.message;});
 async function fetchPage(before,targetPage=0) {
  if(busy)return;busy=true;
  const button=$('#mv-search-form button');button.disabled=true;
  const previousButton=$('#mv-prev');if(previousButton)previousButton.disabled=true;
  const nextButton=$('#mv-next');if(nextButton)nextButton.disabled=true;
  $('#mv-error').textContent='';
  try {
   const params=new URLSearchParams(query);if(before)params.set('before',before);
   const result=await api('mv/documents?'+params.toString());
   if(requestVersion!==mvRequestVersion||!state||state.user.id!==userId||!['integration','documents'].includes(view))return;
   pageIndex=targetPage;pageCursors[pageIndex]=before;pageCursors.length=pageIndex+1;currentDocuments=result.documents;next=result.next_cursor;if($('#mv-total'))$('#mv-total').textContent=currentDocuments.length;if($('#mv-pending'))$('#mv-pending').textContent=currentDocuments.length;
   $('#mv-results').innerHTML=currentDocuments.length?`<div class="table-scroll"><table><thead><tr><th>Documento</th><th>Paciente / atendimento</th><th>Prestador / usuário MV</th><th>Setor</th><th>Criado em</th><th></th></tr></thead><tbody>${currentDocuments.map(d=>`<tr><td><b>${esc(d.title)}</b><small>${esc(d.id)} · FECHADO · Aguarda assinatura</small></td><td>${esc(d.patient_name||"Não informado")}<small>Paciente ${esc(d.patient_id)} · Atendimento ${esc(d.attendance_id)}</small></td><td>${esc(d.provider_name||"Não informado")}<small>Prestador ${esc(d.provider_id)} · ${esc(d.mv_user)}</small></td><td>${esc(d.sector_name||"Não informado")}</td><td>${esc(dateTime(d.created))}</td><td><button type="button" class="row-action" data-mv-id="${d.id}">Ver detalhes →</button></td></tr>`).join('')}</tbody></table></div><div class="mv-results-footer"><span>${currentDocuments.length} documento(s) nesta página · Fonte MV</span><div class="mv-pagination"><button id="mv-prev" class="secondary" ${pageIndex>0?'':'disabled'}>← Anterior</button><span>Página ${pageIndex+1}</span><button id="mv-next" class="secondary" ${next?'':'disabled'}>Próxima página →</button></div></div>`:'<p class="empty">Nenhuma pendência encontrada no período e escopo selecionados.</p>';
   if(!currentDocuments.length)$('#mv-results').innerHTML+=`<div class="mv-results-footer"><button id="mv-prev" class="secondary" ${pageIndex>0?'':'disabled'}>← Anterior</button><span>Página ${pageIndex+1}</span></div>`;
   if($('#mv-prev'))$('#mv-prev').onclick=()=>fetchPage(pageCursors[pageIndex-1],pageIndex-1);
   if($('#mv-next'))$('#mv-next').onclick=()=>fetchPage(next,pageIndex+1);
   document.querySelectorAll('[data-mv-id]').forEach(b=>b.onclick=()=>openMVDocument(currentDocuments.find(d=>String(d.id)===b.dataset.mvId)));
  } catch(error) {
   if(requestVersion===mvRequestVersion&&state&&['integration','documents'].includes(view))$('#mv-error').textContent=error.message;
  } finally {
   busy=false;
   if(requestVersion===mvRequestVersion&&state&&['integration','documents'].includes(view)){button.disabled=!permitted;if($('#mv-prev'))$('#mv-prev').disabled=pageIndex===0;if($('#mv-next'))$('#mv-next').disabled=!next;}
  }
 }
 $('#mv-search-form').onsubmit=e=>{e.preventDefault();if(busy)return;pageIndex=0;pageCursors=[null];query={start:$('#mv-start').value,end:$('#mv-end').value,sector:$('#mv-sector').value};next=null;$('#mv-results').innerHTML='';fetchPage(null);};
 if(dashboard&&permitted)$('#mv-search-form').requestSubmit();
}
function openMVDocument(d) {
 const dialog=$('#document-dialog');dialog.classList.remove('document-expanded');
 dialog.querySelector('.dialog-top .eyebrow').textContent='DOCUMENTO CLÍNICO · MV · SOMENTE LEITURA';
 $('#document-detail').innerHTML=`<div class="document-tabs" role="tablist" aria-label="Visualização do documento"><button role="tab" id="mv-detail-tab" aria-controls="mv-detail-panel" aria-selected="true">Detalhes</button><button role="tab" id="mv-document-tab" aria-controls="mv-document-panel" aria-selected="false" tabindex="-1">Documento</button></div><section id="mv-detail-panel" role="tabpanel" aria-labelledby="mv-detail-tab"><h2>${esc(d.title)}</h2><span class="badge pendente">Fechado · Aguardando assinatura</span><div class="detail-grid">${[['Documento',d.id],['Paciente',d.patient_name||'Não informado'],['Atendimento',d.attendance_id],['Usuário MV',d.mv_user],['Prestador',d.provider_name||'Não informado'],['Setor',d.sector_name||'Não informado'],['Criado em',dateTime(d.created)],['Objeto',d.object_id],['Tipo de objeto',d.object_type]].map(([k,v])=>`<div><small>${k}</small><b>${esc(v)}</b></div>`).join('')}</div></section><section id="mv-document-panel" role="tabpanel" aria-labelledby="mv-document-tab" hidden><p class="notice">Selecione esta aba para consultar o conteúdo disponível no MV.</p></section>`;
 const tabs=[$('#mv-detail-tab'),$('#mv-document-tab')];
 const panels=[$('#mv-detail-panel'),$('#mv-document-panel')];
 let loaded=false; const owner=state.user.id;
 const select=index=>{tabs.forEach((t,i)=>{t.setAttribute('aria-selected',String(i===index));t.tabIndex=i===index?0:-1;panels[i].hidden=i!==index;});if(index===1&&!loaded){loaded=true;panels[1].textContent='Carregando conteúdo do MV…';api('mv/document?id='+encodeURIComponent(d.id)).then(content=>{if(!state||state.user.id!==owner||!panels[1].isConnected||!dialog.open)return;
 if(content.kind==='pdf')panels[1].innerHTML=`<iframe class="mv-pdf" title="Documento original MV" src="/api/mv/document/file?id=${encodeURIComponent(d.id)}"></iframe>`;
 else if(content.kind==='editor')panels[1].innerHTML=`<p class="notice">${esc(content.notice)}</p>${content.partial?'<p class="error">Visualização parcial: há campos ou conteúdo além do limite de exibição.</p>':''}<div class="mv-fields">${content.fields.length?content.fields.map(f=>`<article><h3>${esc(f.label)}</h3><pre>${esc(f.value)}</pre>${f.truncated?'<small>Campo truncado.</small>':''}</article>`).join(''):'<p>Nenhum campo preenchido disponível.</p>'}</div>`;
 else panels[1].innerHTML=`<p class="notice">${esc(content.message)}</p>`;
 }).catch(e=>{if(panels[1].isConnected&&state){panels[1].textContent=e.message;loaded=false;}});}};
 tabs.forEach((t,i)=>{t.onclick=()=>select(i);t.onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();const n=e.key==='Home'?0:e.key==='End'?1:1-i;select(n);tabs[n].focus();}};});
 dialog.showModal();
}
function setupDocumentTabs(d) {
 const dialog = $('#document-dialog');
 dialog.querySelector('.dialog-top .eyebrow').textContent='DOCUMENTO CLÍNICO · DEMONSTRAÇÃO';
 dialog.classList.remove('document-expanded');
 const container = $('#document-detail');
 const details = document.createElement('section');
 details.id = 'detail-panel';
 details.setAttribute('role','tabpanel');
 details.setAttribute('aria-labelledby','detail-tab');
 while(container.firstChild) details.appendChild(container.firstChild);
 container.innerHTML = `<div class="document-tabs" role="tablist" aria-label="Visualização do documento"><button type="button" id="detail-tab" role="tab" aria-selected="true" aria-controls="detail-panel">Detalhes</button><button type="button" id="preview-tab" role="tab" aria-selected="false" aria-controls="preview-panel" tabindex="-1">Documento</button></div>`;
 container.appendChild(details);
 const preview = document.createElement('section');
 preview.id = 'preview-panel';
 preview.hidden = true;
 preview.setAttribute('role','tabpanel');
 preview.setAttribute('aria-labelledby','preview-tab');
 preview.innerHTML = `<div class="preview-toolbar"><div><b>Visualização do documento</b><small>Exemplo fictício · não recebido do MV</small></div><button type="button" class="secondary" id="expand-document" aria-pressed="false">Ampliar</button></div><div class="document-scroll" tabindex="0" role="region" aria-label="Conteúdo demonstrativo do documento"><article class="document-paper"><div class="paper-header"><b>Hospital de Referência Modelo</b><span>AssinaJA · Demonstração</span></div><p class="preview-warning">DOCUMENTO FICTÍCIO · SEM VALIDADE ASSISTENCIAL</p><h2>${esc(d.title)}</h2><dl class="paper-fields">${[['Código',d.mv_id],['Paciente',d.patient],['Autor original',d.author],['Setor / área',d.sector+' / '+d.area],['Data',date(d.created)],['Situação de demonstração',labels[d.status]]].map(([key,value])=>`<div><dt>${key}</dt><dd>${esc(value)}</dd></div>`).join('')}</dl><h3>Conteúdo de demonstração</h3><p>Esta página ilustra como o documento será apresentado dentro do AssinaJA. Não contém registro clínico, prescrição ou assinatura real.</p><h3>Registro assistencial</h3><p>O conteúdo original deste documento ainda não está disponível. A integração deverá localizar o arquivo ou a representação oficial no MV antes de permitir sua visualização.</p><h3>Responsabilidade e assinatura</h3><p>Autor original: ${esc(d.author)}.</p><p>Destinatário do encaminhamento: ${esc(d.recipient || 'Não atribuído')}.</p><p>Os dados acima são fictícios e servem apenas para verificar a apresentação. A situação exibida não comprova uma assinatura digital.</p><div class="paper-footer">Prévia de layout · Conteúdo fictício · AssinaJA</div></article></div>`;
 container.appendChild(preview);
 const tabs = [$('#detail-tab'),$('#preview-tab')];
 function selectTab(index) {
  tabs.forEach((tab,i)=>{tab.setAttribute('aria-selected',String(i===index));tab.tabIndex=i===index?0:-1;});
  details.hidden = index!==0;
  preview.hidden = index!==1;
 }
 tabs.forEach((tab,index)=>{
  tab.onclick=()=>selectTab(index);
  tab.onkeydown=event=>{
   if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
   event.preventDefault();
   const next=event.key==='Home'?0:event.key==='End'?1:1-index;
   selectTab(next);tabs[next].focus();
  };
 });
 $('#expand-document').onclick=()=>{
  const expanded=dialog.classList.toggle('document-expanded');
  $('#expand-document').textContent=expanded?'Reduzir':'Ampliar';
  $('#expand-document').setAttribute('aria-pressed',String(expanded));
 };
}
load().catch(()=>showLogin());
let directoryVersion=0;
async function renderMVAccess(){
 const version=++directoryVersion,owner=state.user.id;
 const active=()=>state&&state.user.id===owner&&view==='access'&&version===directoryVersion;
 $('#page-description').textContent='Setores e usuários ativos do MV. Permissões administradas pelo master.';
 $('#page-content').innerHTML='<section class="panel info-block"><h2>Equipe e vínculos MV</h2><p>Selecione um setor para consultar os usuários. A permissão de encaminhamento fica registrada no AssinaJA; a transferência real está em validação. A assinatura será feita somente no MV.</p><label for="directory-search">Buscar setor por nome</label><input id="directory-search" placeholder="Nome do setor"><p id="directory-error" class="error" role="alert"></p><div class="directory-layout"><div id="directory-sectors">Carregando setores…</div><div id="directory-users">Selecione um setor.</div></div></section>';
 try{const result=await api('mv/sectors');if(!active())return;
 let selection=0;
 const paint=()=>{const term=$('#directory-search').value.toLocaleLowerCase('pt-BR');$('#directory-sectors').innerHTML=result.sectors.filter(s=>s.name.toLocaleLowerCase('pt-BR').includes(term)).map(s=>`<button class="secondary sector-choice" data-sector="${s.id}">${esc(s.name)}</button>`).join('')||'<p>Nenhum setor encontrado.</p>';document.querySelectorAll('[data-sector]').forEach(button=>button.onclick=async()=>{const selected=++selection;const sector=Number(button.dataset.sector);$('#directory-users').textContent='Carregando usuários…';$('#directory-error').textContent='';try{const response=await api('mv/users?sector='+sector);if(!active()||selected!==selection)return;$('#directory-users').innerHTML=`<h3>${esc(button.textContent)}</h3><label for="directory-user-search">Buscar usuário por nome</label><input id="directory-user-search" placeholder="Nome ou usuário MV"><p id="directory-user-count" aria-live="polite"></p><div class="table-scroll"><table><thead><tr><th>Profissional / usuário MV</th><th>Perfil MV</th><th>Pode encaminhar</th></tr></thead><tbody>${response.users.map((u,i)=>`<tr><td>${esc(u.name)}<small>${esc(u.username)}</small></td><td>${esc(u.profile||'Sem perfil de prestador vinculado')}</td><td><label><input type="checkbox" data-permission="${i}" ${u.can_forward?'checked':''} ${response.can_manage?'':'disabled'} aria-label="Permitir encaminhamento para ${esc(u.name)}"> Habilitado</label></td></tr>`).join('')||'<tr><td colspan="3">Nenhum usuário ativo vinculado.</td></tr>'}</tbody></table></div>`;const userRows=[...$('#directory-users tbody').rows];const normalize=value=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('pt-BR');const filterUsers=()=>{const term=normalize($('#directory-user-search').value);let count=0;userRows.forEach((row,i)=>{const u=response.users[i];if(!u)return;row.hidden=!normalize(u.name+' '+u.username).includes(term);if(!row.hidden)count++;});$('#directory-user-count').textContent=count+' usuário(s) encontrado(s)';};$('#directory-user-search').oninput=filterUsers;filterUsers();document.querySelectorAll('[data-permission]').forEach(toggle=>toggle.onchange=async()=>{const u=response.users[Number(toggle.dataset.permission)],enabled=toggle.checked;toggle.disabled=true;try{const saved=await api('mv/permissions',{username:u.username,sector_id:sector,enabled});if(active())toast(saved.message);}catch(e){toggle.checked=!enabled;if(active())toast(e.message);}finally{if(toggle.isConnected)toggle.disabled=!response.can_manage;}});}catch(e){if(active()&&selected===selection)$('#directory-users').textContent=e.message;}});};$('#directory-search').oninput=paint;paint();
 }catch(e){if(active()){$('#directory-sectors').textContent='';$('#directory-error').textContent=e.message;}}
}
