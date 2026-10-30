const $ = (id) => document.getElementById(id);
let history = [], busy = false;
const welcome = $('welcome');
function node(tag, text, cls) { const el = document.createElement(tag); if(text) el.textContent = text; if(cls) el.className = cls; return el; }
function panel(library) {
  $('chatPanel').hidden = library; $('libraryPanel').hidden = !library;
  $('chatTab').classList.toggle('active', !library); $('libraryTab').classList.toggle('active', library);
  $('sectionTitle').textContent = library ? '참고 문서' : '정비 지식 챗봇';
}
function showSource(source) {
  $('sourceTitle').textContent = source.kind === 'official' ? `${source.publisher} · ${source.title}` : `${source.document || '정비교범'} · PDF ${source.page}쪽 · ${source.title}`;
  $('sourceText').textContent = source.kind === 'official' ? `${source.text}\n\n확인일: ${source.checkedAt} (한국 시간)\n2023년형 해당 여부: ${source.applicability2023}` : source.text;
  let image = $('sourceImage');
  if(!image) { image = document.createElement('img'); image.id = 'sourceImage'; image.alt = '출처 원문 페이지'; image.style.cssText = 'width:100%;height:auto;display:block;margin:15px 0'; $('sourceText').after(image); }
  image.hidden = !source.imageUrl;
  if(source.imageUrl) { image.src = source.imageUrl; image.onerror = () => { image.hidden = true; }; }
  $('sourceLink').hidden = !source.url;
  $('sourceLink').href = source.url || '#';
  $('sourceLink').textContent = source.kind === 'official' ? '제작사 공식 원문 확인 ↗' : '원본 PDF에서 확인 ↗';
  $('sourceDialog').showModal();
}
function guideRef(source){
  const button=node('button',`원문 ${source.page}쪽`,'guide-ref');
  button.onclick=()=>showSource(source);return button;
}
function renderGuide(guide,sources){
  const root=node('div','','service-guide');const byId=new Map(sources.map(s=>[s.id,s]));
  const header=node('div','','guide-heading');header.append(node('span','REXTON SPORTS 2023','guide-kicker'),node('h2',guide.title),node('p',guide.subtitle));root.append(header);
  if(guide.question)root.append(node('p','입력한 내용: '+guide.question,'guide-question'));
  function addClaim(container,claim,tag='p'){
    const item=node(tag);item.append(node('span',claim.text));
    const refs=node('span','','guide-refs');(claim.refs||[]).forEach(id=>{if(byId.has(id))refs.append(guideRef(byId.get(id)));});item.append(refs);container.append(item);
  }
  function addFigures(placement){
    guide.figures.filter(f=>f.placement===placement).forEach(f=>{
      const record=byId.get(f.ref);if(!record)return;
      const figure=node('figure','','guide-figure'),button=node('button','','guide-image-button');
      button.setAttribute('aria-label',f.caption+' 원문 크게 보기');button.onclick=()=>showSource(record);
      const image=node('img');image.alt=f.caption;image.src=f.src;image.loading='lazy';image.decoding='async';
      image.onerror=()=>{button.replaceChildren(node('span','그림을 불러오지 못했습니다. 눌러 원문을 확인하세요.','guide-image-error'));};
      button.append(image);const caption=node('figcaption',f.caption+' · 교범 사진/도해 일부');caption.append(guideRef(record));figure.append(button,caption);root.append(figure);
    });
  }
  addClaim(root,guide.description);addFigures('description');
  for(const section of guide.sections){
    if(section.id==='steps'&&guide.warnings?.length){const caution=node('section','','guide-caution');caution.append(node('h3','작업 전 주의사항'));const list=node('ul');guide.warnings.forEach(c=>addClaim(list,c,'li'));caution.append(list);root.append(caution);}
    const block=node('section','','guide-section');block.append(node('h3',section.title));
    if(section.id==='steps')block.append(node('p','점검 후 해당 작업이 필요하다고 확인된 경우에 참고하는 개요입니다. 전체 절차는 원문에서 확인하세요.','guide-section-note'));
    const list=node(section.ordered?'ol':'ul');section.items.forEach(c=>addClaim(list,c,'li'));block.append(list);root.append(block);addFigures(section.id);
  }
  if(guide.followUp?.length){const block=node('section','','guide-followup');block.append(node('h3','추가로 확인하면 좋은 정보'));const list=node('ul');guide.followUp.forEach(q=>list.append(node('li',q)));block.append(list);root.append(block);}
  root.append(node('p',guide.scope,'guide-scope'));
  const details=node('details','','guide-originals');details.append(node('summary',`근거 원문 전체 보기 · ${sources.length}쪽`));
  const refs=node('div','','sources');sources.forEach(s=>{const button=node('button',`${s.document} · PDF ${s.page}쪽`,'source-chip');button.onclick=()=>showSource(s);refs.append(button);});details.append(refs);root.append(details);
  return root;
}
function addMessage(role, text, sources = [], notice = null, guide = null) {
  const article = node('article', '', `message ${role}`);
  if(role === 'assistant') article.append(node('div','✳ 정비온','author'));
  const bubble=node('div',guide?'':text,'bubble');
  if(guide){bubble.classList.add('guide-bubble');bubble.append(renderGuide(guide,sources));}
  article.append(bubble);
  if(sources.length&&!guide) {
    const group = node('div','','sources');
    sources.forEach(s => { const btn = node('button',s.kind === 'official' ? `${s.publisher} · 확인일 ${s.checkedAt} · ${s.title} ↗` : `정비교범 · PDF ${s.page}쪽 · ${s.title} ↗`,'source-chip'); btn.onclick = () => showSource(s); group.append(btn); });
    if(sources.some(s=>s.kind==='manual')) article.insertBefore(group,article.querySelector('.bubble'));
    else article.append(group);
  }
  if(notice) article.append(node('div',notice,'notice'));
  $('conversation').append(article);
  article.scrollIntoView({block:'nearest',behavior:'smooth'});
}
async function ask(question) {
  if(busy || !question.trim()) return;
  busy = true; $('send').disabled = true; $('reset').disabled = true; panel(false); welcome.hidden = true;
  addMessage('user',question); $('question').value = ''; $('question').style.height = '';
  const pending = node('div','문서에서 근거를 찾고 있습니다…','pending'); pending.setAttribute('role','status'); $('conversation').append(pending);
  try {
    const response = await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,history:history.slice(-6)}),signal:AbortSignal.timeout(55000)});
    const data = await response.json(); if(!response.ok) throw new Error(data.error || '답변 요청에 실패했습니다.');
    pending.remove(); addMessage('assistant',data.answer,data.sources,data.notice,data.guide);
    history.push({role:'user',content:question},{role:'assistant',content:data.answer.slice(0,4000)});
    $('mode').textContent = data.mode === 'manual' ? '교범 기반 정리 안내 · 출처·그림 포함' : data.mode === 'official' ? '제작사 공식 자료 · 출처·확인일·연식 구분' : '검토된 자료 기반 안내';
  } catch(error) { pending.remove(); addMessage('assistant',`답변을 가져오지 못했습니다. ${error.name === 'TimeoutError' ? '응답 시간이 초과되었습니다.' : error.message} 다시 질문해 주세요.`); }
  finally { busy = false; $('send').disabled = false; $('reset').disabled = false; $('question').focus(); }
}
$('chatForm').onsubmit = e => { e.preventDefault(); ask($('question').value.trim()); };
$('question').onkeydown = e => { if(e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); if(!busy) $('chatForm').requestSubmit(); } };
$('question').oninput = () => { $('question').style.height = 'auto'; $('question').style.height = Math.min($('question').scrollHeight,160)+'px'; };
document.querySelectorAll('[data-question]').forEach(btn => btn.onclick = () => ask(btn.dataset.question));
$('chatTab').onclick = () => panel(false); $('libraryTab').onclick = () => panel(true); $('viewDocument').onclick = () => panel(true);
$('reset').onclick = () => { history = []; $('conversation').replaceChildren(welcome); welcome.hidden = false; $('question').value = ''; $('question').focus(); };
$('closeDialog').onclick = () => $('sourceDialog').close();
async function init() {
  try {
    const [official,parts,manuals] = await Promise.all([fetch('/api/official-sources').then(r=>r.json()),fetch('/api/parts').then(r=>r.json()),fetch('/api/manuals').then(r=>r.json())]);
    official.forEach(p => { const card = node('article','','page-card'); card.append(node('h2',p.title),node('p',p.text),node('p',`출처: ${p.publisher} · 확인일: ${p.checkedAt} (한국 시간)`),node('p',`2023년형 해당 여부: ${p.applicability2023}`)); const btn = node('button','공식 출처 확인 ↗','text-button'); btn.onclick = () => showSource(p); card.append(btn); $('pageList').append(card); });
    const heading=node('h2','렉스턴 스포츠 2023 · 정비교범','manual-library-title');
    const list=node('div','','manual-docs');manuals.forEach(d=>{const card=node('article','','manual-doc');card.append(node('strong',`${d.title} · ${d.pages.toLocaleString()}쪽`),node('p',d.scope));if(d.available){const link=node('a','원본 PDF 열기 ↗');link.href='/document?doc='+encodeURIComponent(d.id);link.target='_blank';link.rel='noopener';card.append(link);}list.append(card);});
    $('pageList').before(heading,list,node('h2','제작사 공식 자료','manual-library-title'));
    document.querySelector('.badge').textContent='렉스턴 스포츠 2023 · 교범·공식 자료';
    document.querySelector('.document-strip strong').textContent='렉스턴 스포츠 2023 정비교범 · 제작사 공식 정보';
    document.querySelector('.document-strip div > span').textContent=`차량 교범 ${manuals.length}개 · 선별 ${parts.indexedPages}쪽 · 대상 부품 ${parts.parts.length}종`;
    document.querySelector('.welcome p').textContent='부품 설명·점검 방법과 검토된 제작사 공식 가격 정보를 확인하세요.';
    document.querySelector('.scope-note').textContent='ⓘ 차량 사양과 정비교범의 원문·주의사항을 확인하세요. 증상만으로 고장을 확정하지 않습니다.';
    document.querySelector('#libraryPanel > p').textContent='정비교범과 검토된 제작사 공식 자료입니다. 공식 정보는 출처·확인일·2023년형 해당 여부를 확인하세요. 실시간 검색 결과가 아닙니다.';
    $('question').placeholder='예: 배터리 점검 방법, 2023년형 렉스턴 스포츠 가격';
    $('mode').textContent='교범·공식 자료 기반 안내 · API 키 없이 실행';
    const examples=[['배터리 점검 방법을 알려 주세요','01 / 충전 계통','배터리 점검 방법'],['에어컨 필터 교환 방법을 알려 주세요','02 / 필터 교환','에어컨 필터 교환'],['헤드램프에 결로가 계속 생겨요','03 / 램프 정비','헤드 램프 결로 확인'],['2023년형 렉스턴 스포츠 가격은?','04 / 공식 가격 정보','2023년형 가격 확인']];
    document.querySelectorAll('.prompt-grid button').forEach((b,i)=>{b.dataset.question=examples[i][0];b.querySelector('span').textContent=examples[i][1];b.querySelector('strong').textContent=examples[i][2];});
    document.querySelectorAll('.side-prompt').forEach((b,i)=>{const example=examples[i===2?3:i];b.dataset.question=example[0];b.replaceChildren(node('span','↗'));b.prepend(document.createTextNode(example[2]+' '));});
  } catch { $('mode').textContent = '서버 연결을 확인해 주세요.'; }
}
init();
