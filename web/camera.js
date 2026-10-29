/* Camera frames are held in memory and sent only while live recognition runs. */
const cameraState = {parts:[], selected:null, detail:null, vision:null, stream:null, opening:false,
  session:0, loop:null, errors:0, expiry:null, previousId:null, streak:0, lastResult:0};
const cameraMain = document.querySelector('main');
const cameraSection = node('section','','camera-panel'); cameraSection.id='cameraPanel';
cameraSection.innerHTML = `<div class="camera-heading"><div><span class="eyebrow">REXTON SPORTS / LIVE VISION</span><h1>카메라로 부품 인식</h1><p>부품을 비추면 영상 프레임을 연속 분석하고 인식 후보를 갱신합니다.</p></div><span class="vehicle-label">렉스턴 스포츠 · 2023</span></div>
<div class="capture-grid"><div class="capture-card"><div class="live-heading"><div class="step-label">01 / 실시간 카메라</div><span id="liveIndicator" class="live-indicator">카메라 꺼짐</span></div><div id="liveStage" class="live-stage"><div id="cameraPlaceholder" class="camera-placeholder"><span class="camera-icon">▣</span><p>카메라를 시작하고 대상 부품을 비춰 주세요.<br>부품 전체가 선명하게 보이도록 유지하세요.</p></div><div id="videoWrap" class="live-video-wrap" hidden><video id="liveVideo" autoplay muted playsinline aria-label="실시간 부품 카메라"></video><canvas id="detectionOverlay" aria-hidden="true"></canvas></div></div><div class="capture-actions"><button id="startCamera" class="primary-button">카메라 시작</button><button id="pauseRecognition" class="secondary-button" disabled>인식 일시정지</button><button id="stopCamera" class="secondary-button" disabled>카메라 중지</button></div><label class="select-label" for="cameraFacing">사용 카메라</label><select id="cameraFacing" class="part-select"><option value="environment">후면 카메라 우선</option><option value="user">전면 카메라 우선</option></select><p id="frameStats" class="capture-help" role="status">영상 녹화·사진 저장 없이 현재 프레임만 분석합니다.</p><div id="streamPrivacy" class="photo-privacy">카메라 시작 시 권한을 요청합니다. 인식 실행 중인 프레임만 로컬 서버와 모델로 전송하며 저장하지 않습니다.</div></div>
<div class="part-card"><div class="step-label">02 / 인식 결과</div><div id="visionStatus" class="camera-status" role="status" aria-live="polite">설정을 확인하고 있습니다.</div><div id="visionCandidates" class="live-candidates"></div><p class="capture-help">YOLO 연결 시 부품 위치 상자가 표시됩니다. 후보를 확인하면 인식이 일시정지되고 해당 부품의 교범을 열 수 있습니다.</p><label class="select-label" for="partSelect">인식 부품 확인 / 직접 선택</label><select class="part-select" id="partSelect"><option value="">부품을 선택해 주세요</option></select><div id="selectedPart" class="selected-part" hidden></div></div></div><div id="partPages" class="part-pages" hidden></div><p class="tablet-note">Android 카메라는 HTTPS 또는 localhost 같은 보안 컨텍스트가 필요합니다. 개발용 USB 연결은 README의 adb reverse 안내를 참고하세요. 태블릿의 일반 HTTP LAN 주소로 접속하면 카메라가 차단될 수 있습니다.</p>`;
cameraMain.insertBefore(cameraSection,$('chatPanel'));
const cameraNav=node('button','▣ 실시간 인식','nav'); cameraNav.id='cameraTab'; $('chatTab').before(cameraNav);
const originalPanel=panel;
panel=function(library){stopCamera();cameraSection.hidden=true;cameraNav.classList.remove('active');originalPanel(library);};
function openCamera(){ $('chatPanel').hidden=true;$('libraryPanel').hidden=true;cameraSection.hidden=false;cameraNav.classList.add('active');$('chatTab').classList.remove('active');$('libraryTab').classList.remove('active');$('sectionTitle').textContent='렉스턴 스포츠 · 실시간 부품 인식'; }
cameraNav.onclick=openCamera; openCamera();
document.querySelector('.badge').textContent='LIVE VISION · 차량 정비교범';

function syncCameraControls(){
  const live=!!cameraState.stream;
  $('startCamera').disabled=live||cameraState.opening;
  $('stopCamera').disabled=!live&&!cameraState.opening;
  $('pauseRecognition').disabled=!live||!cameraState.vision?.available;
  $('pauseRecognition').textContent=cameraState.loop?.running?'인식 일시정지':'인식 재개';
  $('cameraFacing').disabled=cameraState.opening;
  $('liveIndicator').textContent=cameraState.opening?'권한 확인 중':!live?'카메라 꺼짐':cameraState.loop?.running?'● 연속 인식 중':'● 미리보기';
  $('liveIndicator').classList.toggle('is-live',live);
}
function clearLiveResults(){
  if(cameraState.expiry)clearTimeout(cameraState.expiry);cameraState.expiry=null;
  $('visionCandidates').replaceChildren();
  const overlay=$('detectionOverlay');overlay.getContext('2d').clearRect(0,0,overlay.width,overlay.height);
  cameraState.previousId=null;cameraState.streak=0;
}
function stopRecognition(message){
  cameraState.loop?.stop();clearLiveResults();cameraState.lastResult=0;
  if(message)$('visionStatus').textContent=message;
  syncCameraControls();
}
function stopCamera(message){
  ++cameraState.session;stopRecognition();
  if(cameraState.stream)cameraState.stream.getTracks().forEach(track=>track.stop());
  cameraState.stream=null;cameraState.opening=false;
  $('liveVideo').srcObject=null;$('videoWrap').hidden=true;$('cameraPlaceholder').hidden=false;
  $('frameStats').textContent='영상 녹화·프레임 저장 없이 현재 프레임만 분석합니다.';
  $('visionStatus').textContent=message||cameraState.vision?.message||'카메라가 꺼져 있습니다.';
  syncCameraControls();
}
function cameraError(error){
  if(error.name==='NotAllowedError')return '카메라 권한이 허용되지 않았습니다. 브라우저의 사이트 권한을 확인해 주세요.';
  if(error.name==='NotFoundError')return '사용 가능한 카메라를 찾지 못했습니다.';
  if(error.name==='NotReadableError')return '카메라를 사용할 수 없습니다. 다른 앱에서 사용 중인지 확인해 주세요.';
  return '카메라를 시작하지 못했습니다. 기기·브라우저 권한과 HTTPS 또는 localhost 접속을 확인해 주세요.';
}
async function startCamera(){
  if(cameraState.stream||cameraState.opening)return;
  if(!window.isSecureContext || !navigator.mediaDevices?.getUserMedia){
    $('visionStatus').textContent='카메라는 HTTPS 또는 localhost에서 사용할 수 있습니다. USB 연결 시 adb reverse를 설정한 뒤 태블릿에서 http://127.0.0.1:8000으로 접속하세요.';return;
  }
  const session=++cameraState.session;cameraState.opening=true;syncCameraControls();
  try{
    const stream=await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:{ideal:$('cameraFacing').value},width:{ideal:1280},height:{ideal:720}}});
    if(session!==cameraState.session){stream.getTracks().forEach(t=>t.stop());return;}
    cameraState.stream=stream;const video=$('liveVideo');video.srcObject=stream;
    $('videoWrap').hidden=false;$('cameraPlaceholder').hidden=true;
    await video.play();
    if(session!==cameraState.session)return;
    stream.getVideoTracks().forEach(track=>track.onended=()=>stopCamera('카메라 연결이 종료되었습니다. 다시 시작해 주세요.'));
    cameraState.opening=false;
    if(cameraState.vision?.available)startRecognition();
    else $('visionStatus').textContent=cameraState.vision?.message||'모델 설정을 불러오는 중입니다. 카메라 미리보기만 실행합니다.';
  }catch(error){if(session===cameraState.session)stopCamera(cameraError(error));}
  finally{if(session===cameraState.session){cameraState.opening=false;syncCameraControls();}}
}
const frameCanvas=document.createElement('canvas');
function captureFrame(){
  const video=$('liveVideo');if(!cameraState.stream||video.readyState<2||!video.videoWidth)return null;
  const ratio=Math.min(1,640/Math.max(video.videoWidth,video.videoHeight));
  frameCanvas.width=Math.round(video.videoWidth*ratio);frameCanvas.height=Math.round(video.videoHeight*ratio);
  frameCanvas.getContext('2d').drawImage(video,0,0,frameCanvas.width,frameCanvas.height);
  return frameCanvas.toDataURL('image/jpeg',0.75).split(',')[1];
}
function drawDetections(detections){
  const video=$('liveVideo'),overlay=$('detectionOverlay');overlay.width=video.videoWidth;overlay.height=video.videoHeight;
  const ctx=overlay.getContext('2d');ctx.clearRect(0,0,overlay.width,overlay.height);
  const size=Math.max(16,Math.round(overlay.width/45));ctx.font=`600 ${size}px sans-serif`;ctx.lineWidth=Math.max(2,overlay.width/400);
  detections.forEach(d=>{
    const [x1,y1,x2,y2]=d.box;const x=x1*overlay.width,y=y1*overlay.height,w=(x2-x1)*overlay.width,h=(y2-y1)*overlay.height;
    ctx.strokeStyle='#d5f29c';ctx.strokeRect(x,y,w,h);
    const label=d.name;const labelWidth=Math.min(overlay.width,ctx.measureText(label).width+16);
    const labelX=Math.min(x,overlay.width-labelWidth);const labelY=Math.min(overlay.height-size-10,Math.max(0,y-size-10));
    ctx.fillStyle='#173322';ctx.fillRect(labelX,labelY,labelWidth,size+10);ctx.fillStyle='#f3ffe3';ctx.fillText(label,labelX+8,labelY+size+2);
  });
}
function updateLiveResult(data,elapsed){
  cameraState.errors=0;
  const now=performance.now();const period=cameraState.lastResult?now-cameraState.lastResult:0;cameraState.lastResult=now;
  const candidates=data.candidates||[];
  const first=candidates[0]?.id;cameraState.streak=first&&first===cameraState.previousId?cameraState.streak+1:first?1:0;cameraState.previousId=first;
  $('visionCandidates').replaceChildren();
  candidates.forEach(c=>{
    const btn=node('button',c.name+' · 이 부품으로 확인','candidate-button');
    const score=typeof c.score==='number'?`탐지 점수 ${c.score.toFixed(2)} · `:'';
    btn.append(node('small',score+(c.reason||'인식 후보')));btn.onclick=()=>confirmPart(c.id);$('visionCandidates').append(btn);
  });
  drawDetections(data.detections||[]);
  $('visionStatus').textContent=candidates.length?`${candidates.length}개 부품 후보 · ${cameraState.streak}회 연속 같은 1순위 후보. 실제 부품을 확인해 주세요.`:'인식된 부품이 없습니다. 거리·각도·조명을 조정해 주세요.';
  $('frameStats').textContent=`${data.backend==='yolo'?'YOLO 위치 탐지':'전체 프레임 비전 분석'} · 최근 분석 ${(elapsed/1000).toFixed(1)}초${period?' · 결과 갱신 '+(1000/period).toFixed(1)+'회/초':''}`;
  if(cameraState.expiry)clearTimeout(cameraState.expiry);
  cameraState.expiry=setTimeout(()=>{clearLiveResults();if(cameraState.loop?.running)$('visionStatus').textContent='이전 결과를 지우고 새 프레임 분석을 기다리고 있습니다.';},data.backend==='yolo'?1800:5000);
}
function startRecognition(){
  if(!cameraState.stream||!cameraState.vision?.available||cameraState.loop?.running)return;
  cameraState.errors=0;cameraState.previousId=null;cameraState.streak=0;
  cameraState.loop=new LiveRecognitionLoop({capture:captureFrame,intervalMs:cameraState.vision.intervalMs,timeoutMs:cameraState.vision.timeoutMs,
    infer:async(image,signal)=>{const response=await fetch('/api/identify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image}),signal});const data=await response.json();if(!response.ok){const error=new Error(data.error||'프레임 분석에 실패했습니다.');error.status=response.status;throw error;}return data;},
    onResult:updateLiveResult,
    onError:error=>{
      clearLiveResults();if(error.status!==429)cameraState.errors++;
      const message=error.name==='AbortError'?'프레임 분석 시간이 초과되었습니다.':error.message;
      if(error.status===400||error.status===503||cameraState.errors>=3){stopRecognition(message+' 인식을 일시정지했습니다.');return false;}
      $('visionStatus').textContent=message+' 다음 프레임에서 재시도합니다.';return true;
    }});
  $('visionStatus').textContent='카메라 프레임을 분석하고 있습니다…';cameraState.loop.start();syncCameraControls();
}
function confirmPart(id){
  stopRecognition(cameraState.stream&&cameraState.vision?.available?'부품을 선택했습니다. 인식 재개를 누르면 다른 부품을 계속 찾을 수 있습니다.':'선택한 부품의 교범을 확인할 수 있습니다. '+(cameraState.vision?.available?'카메라 시작으로 연속 인식을 사용할 수 있습니다.':cameraState.vision?.message||''));
  $('partSelect').value=id;selectPart(id);
}
$('startCamera').onclick=startCamera;
$('stopCamera').onclick=()=>stopCamera('카메라와 인식을 중지했습니다.');
$('pauseRecognition').onclick=()=>{if(cameraState.loop?.running)stopRecognition('인식을 일시정지했습니다. 카메라 미리보기는 계속됩니다.');else startRecognition();};
$('cameraFacing').onchange=()=>{if(cameraState.stream){stopCamera();startCamera();}};
document.addEventListener('visibilitychange',()=>{if(document.hidden)stopCamera('화면을 벗어나 카메라와 인식을 중지했습니다.');});
window.addEventListener('pagehide',()=>stopCamera());
syncCameraControls();

function sourceButton(record,label){const b=node('button',label||`PDF ${record.page}쪽${record.printedPage?' / '+record.printedPage:''}`,'secondary-button');b.onclick=()=>showSource(record);return b;}
async function selectPart(id){
  cameraState.selected=id;cameraState.detail=null;$('selectedPart').hidden=true;$('partPages').hidden=true;
  if(!id)return;
  try{
    const res=await fetch('/api/part?id='+encodeURIComponent(id));const detail=await res.json();if(!res.ok)throw new Error(detail.error);
    if(cameraState.selected!==id)return;cameraState.detail=detail;
    const part=detail.part;const box=$('selectedPart');box.replaceChildren(node('div','확인한 부품','step-label'),node('h2',part.name),node('p',`${part.group} · SGN ${part.sgn}\nSGN은 정비 작업 식별 코드이며 주문 품번이 아닙니다.`,'part-meta'));
    const overview=detail.pages.find(p=>p.page===part.overview);if(overview)box.append(sourceButton(overview,'부품 위치·구성 원문 보기 ↗'));
    box.append(node('p','카메라 영상만으로 고장을 판정하지 않습니다. 적용 엔진·변속기·옵션과 작업 주의사항을 확인해 주세요.','capture-help'));
    const label=node('label','증상 또는 확인할 내용','select-label');label.htmlFor='manualSymptom';const input=node('textarea');input.id='manualSymptom';input.className='manual-symptom';input.maxLength=1200;input.placeholder=part.questions.join('\n');
    const button=node('button','선택한 부품의 정비자료 찾기','primary-button');button.onclick=()=>askPart(input.value.trim()||part.name+' 위치 및 점검·탈거 장착 정보를 보여 주세요',id);
    box.append(label,input,button);box.hidden=false;
    const pages=$('partPages');pages.replaceChildren(node('h3',part.name+' · 선별 원문 페이지'),node('p',`PDF 뷰어 페이지와 교범 인쇄 번호는 다릅니다. 작업 전후 페이지와 공통 주의사항을 함께 확인하세요. ${detail.pages.length}쪽 연결.`));
    if(!detail.available)pages.append(node('p','로컬 정비자료 색인이 없습니다. README의 자료 가져오기를 실행해 주세요.'));
    const safety=node('div','','page-buttons');detail.precautions.forEach(p=>safety.append(sourceButton(p,`공통 주의사항 · ${p.page}쪽`)));if(detail.precautions.length)pages.append(node('h3','공통 정비·계통 주의사항'),safety);
    const refs=node('div','','page-buttons');detail.pages.forEach(p=>refs.append(sourceButton(p)));pages.append(node('h3','부품 및 관련 시스템 점검'),refs);
    if(part.catalogRefs?.length){const catalog=node('div','','page-buttons');part.catalogRefs.forEach(r=>{const a=node('a',`${r.title} · PDF ${r.page}쪽`,'source-chip');a.href=`/document?doc=catalog#page=${r.page}`;a.target='_blank';a.rel='noopener';catalog.append(a);});pages.append(node('h3','카탈로그 관련 그룹'),node('p','관련 그룹 제목으로 찾은 참조입니다. 생산 시점·옵션·차대번호와 대조하기 전에는 주문 품번을 확정하지 않습니다.'),catalog);}
    pages.hidden=false;
  }catch(error){$('visionStatus').textContent='정비자료를 불러오지 못했습니다. '+error.message;}
}
$('partSelect').onchange=e=>confirmPart(e.target.value);
async function askPart(question,id){
  if(busy)return;
  panel(false);welcome.hidden=true;busy=true;$('send').disabled=true;$('reset').disabled=true;
  const part=cameraState.parts.find(p=>p.id===id);addMessage('user',`[확인한 부품: ${part.name}] ${question}`);
  const pending=node('div','해당 부품의 정비교범을 검색하고 있습니다…','pending');$('conversation').append(pending);
  try{
    const res=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,partId:id,history:[]}),signal:AbortSignal.timeout(15000)});
    const data=await res.json();if(!res.ok)throw new Error(data.error);pending.remove();addMessage('assistant',data.answer,data.sources,data.notice,data.guide);$('mode').textContent='교범 기반 정리 안내 · 출처·그림 포함';
    // Keep the explicit part name in history for later manual-topic retrieval.
    history.push({role:'user',content:part.name+' '+question},{role:'assistant',content:data.answer.slice(0,4000)});
  }catch(error){pending.remove();addMessage('assistant','정비자료 검색에 실패했습니다. '+error.message);}
  finally{busy=false;$('send').disabled=false;$('reset').disabled=false;}
}
async function initCamera(){
  try{
    const [status,manuals]=await Promise.all([fetch('/api/parts').then(r=>r.json()),fetch('/api/manuals').then(r=>r.json())]);
    cameraState.parts=status.parts;cameraState.vision=status.vision;
    status.parts.forEach(p=>{const option=node('option',p.name+' · '+p.group);option.value=p.id;$('partSelect').append(option);});
    $('visionStatus').textContent=status.vision.message;syncCameraControls();
    if(cameraState.stream&&status.vision.available)startRecognition();
    const heading=node('h2','렉스턴 스포츠 2023 · 정비자료','manual-library-title');const list=node('div','','manual-docs');
    manuals.forEach(d=>{const row=node('article','','manual-doc');row.append(node('strong',`${d.title} · ${d.pages.toLocaleString()}쪽`),node('p',d.scope));if(d.available){const a=node('a','로컬 원본 PDF 열기 ↗');a.href='/document?doc='+encodeURIComponent(d.id);a.target='_blank';a.rel='noopener';row.append(a);}list.append(row);});
    $('pageList').before(heading,node('p',`대상 부품 ${status.parts.length}종 · 원문 ${status.indexedPages}쪽 선별 색인. 원본 파일과 추출 본문은 로컬에만 보관합니다.`),list,node('h2','프로젝트 개발 제안서'));
    document.querySelector('.scope-note').textContent='ⓘ 부품 인식과 고장 진단은 별도입니다. 적용 사양과 정비교범의 원문·주의사항을 확인하세요.';
    $('question').placeholder='부품명과 증상을 입력해 주세요. 예: 배터리 점검 방법';
    document.querySelector('.document-strip strong').textContent='렉스턴 스포츠 2023 정비교범 · 군학연계 개발 제안서';
    document.querySelector('.document-strip div > span').textContent=`차량 교범 ${manuals.length}개 · 선별 ${status.indexedPages}쪽 · 대상 부품 ${status.parts.length}종`;
    document.querySelector('.welcome p').textContent='차량 부품의 점검·탈거·장착 정보와 프로젝트 구상을 원문 근거로 확인하세요.';
  }catch{$('visionStatus').textContent='부품 설정을 읽지 못했습니다. 서버를 재시작한 뒤 새로고침해 주세요.';}
}
initCamera();
