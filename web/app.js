const $ = (id) => document.getElementById(id);
let history = [], busy = false, pdfAvailable = false;
const welcome = $('welcome');
function node(tag, text, cls) { const el = document.createElement(tag); if(text) el.textContent = text; if(cls) el.className = cls; return el; }
function panel(library) {
  $('chatPanel').hidden = library; $('libraryPanel').hidden = !library;
  $('chatTab').classList.toggle('active', !library); $('libraryTab').classList.toggle('active', library);
  $('sectionTitle').textContent = library ? '참고 문서' : '정비 지식 챗봇';
}
function showSource(source) {
  $('sourceTitle').textContent = `${source.document || '개발 제안서'} · PDF ${source.page}쪽 · ${source.title}`;
  $('sourceText').textContent = source.text;
  let image = $('sourceImage');
  if(!image) { image = document.createElement('img'); image.id = 'sourceImage'; image.alt = '출처 원문 페이지'; image.style.cssText = 'width:100%;height:auto;display:block;margin:15px 0'; $('sourceText').after(image); }
  image.hidden = !source.imageUrl;
  if(source.imageUrl) { image.src = source.imageUrl; image.onerror = () => { image.hidden = true; }; }
  $('sourceLink').hidden = !source.url && !pdfAvailable;
  $('sourceLink').href = source.url || `/document#page=${source.page}`;
  $('sourceDialog').showModal();
}
function addMessage(role, text, sources = [], notice = null) {
  const article = node('article', '', `message ${role}`);
  if(role === 'assistant') article.append(node('div','✳ 정비온','author'));
  article.append(node('div',text,'bubble'));
  if(sources.length) {
    const group = node('div','','sources');
    sources.forEach(s => { const btn = node('button',`${s.kind === 'manual' ? '정비교범 · PDF ' : ''}${s.page}쪽 · ${s.title} ↗`,'source-chip'); btn.onclick = () => showSource(s); group.append(btn); });
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
    pending.remove(); addMessage('assistant',data.answer,data.sources,data.notice);
    history.push({role:'user',content:question},{role:'assistant',content:data.answer.slice(0,4000)});
    $('mode').textContent = data.mode === 'manual' ? '정비교범 원문 발췌 · 사진 진단 결과 아님' : data.mode === 'local-model' ? '로컬 AI 모델 · 문서 검색 기반' : '제안서 발췌 모드 · API 키 없이 실행';
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
    const [status,pages] = await Promise.all([fetch('/api/status').then(r=>r.json()),fetch('/api/pages').then(r=>r.json())]);
    pdfAvailable = status.pdfAvailable;
    if(status.model) $('mode').textContent = `로컬 AI 모델 설정 · ${status.model}`;
    pages.forEach(p => { const card = node('article','','page-card'); card.append(node('h2',`${String(p.page).padStart(2,'0')} / ${p.title}`),node('p',p.text)); const btn = node('button','출처 확인 ↗','text-button'); btn.onclick = () => showSource(p); card.append(btn); $('pageList').append(card); });
  } catch { $('mode').textContent = '서버 연결을 확인해 주세요.'; }
}
init();
