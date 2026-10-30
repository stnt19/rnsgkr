"""Selected local workshop-manual retrieval and optional visual candidate generation."""
import io
import json
import math
import re
import threading
import service_guides
import question_scope as scope
from functools import lru_cache
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PARTS=json.loads((ROOT/'data/parts.json').read_text(encoding='utf-8'))
MANUALS=[]
RECORDS=[]
if (ROOT/'data/manuals.local.json').exists() and (ROOT/'data/manual-index.local.json').exists():
    MANUALS=json.loads((ROOT/'data/manuals.local.json').read_text(encoding='utf-8'))
    imported=json.loads((ROOT/'data/manual-index.local.json').read_text(encoding='utf-8'))
    PARTS=imported['parts']; RECORDS=imported['pages']
RENDER_LOCK=threading.Lock()

def words(text):
    chunks=re.findall(r'[가-힣]+|[a-z0-9]+',text.lower())
    return chunks+[w[i:i+2] for w in chunks if re.fullmatch('[가-힣]+',w) for i in range(len(w)-1)]

INDEX=[Counter(words(p['text'])) for p in RECORDS]
DF=Counter(t for doc in INDEX for t in doc)

def find_part(part_id):
    return next((p for p in PARTS if p['id']==part_id),None)

def infer_part(question):
    compact=re.sub(r'\s+','',question).lower()
    matches=[]
    for part in PARTS:
        for term in [part['name'],part['sgn']]+part['aliases']:
            term=re.sub(r'\s+','',term).lower()
            if term in compact:
                matches.append((len(term),part))
    return max(matches,key=lambda v:v[0])[1] if matches else None

def source(record):
    doc=next(d for d in MANUALS if d['id']==record['docId'])
    return {**record,'id':f"{record['docId']}:{record['page']}",'title':doc['title']+' · '+(record.get('printedPage') or str(record['page'])),
            'url':f"/document?doc={record['docId']}#page={record['page']}",
            'imageUrl':f"/manual-page?doc={record['docId']}&page={record['page']}"}

def public_manuals():
    return [{k:v for k,v in d.items() if k not in ('path','sha256')}|{'available':Path(d['path']).is_file()} for d in MANUALS]

def part_detail(part):
    pages=[source(r) for r in RECORDS if part['id'] in r['partIds']]
    # Precautions are shown as shared context, never silently dropped.
    relevant=set(range(13,18)) if part['docId']=='engine' else {135,136,137}
    relevant.update({'연료':{289,290},'흡기':{363},'윤활':{463,464},'냉각':{503,504}}.get(part['group'],set()))
    common=[source(r) for r in RECORDS if r['docId']==part['docId'] and not r['partIds'] and r['page'] in relevant]
    return {'part':part,'pages':pages,'precautions':common,'available':bool(pages)}

def answer_manual(question,part_id=None):
    part=find_part(part_id) if part_id else infer_part(question)
    if not part:
        return None
    if not scope.supported(part, question):
        return scope.refusal('missing-evidence')
    pool=[(r,d) for r,d in zip(RECORDS,INDEX) if part['id'] in r['partIds']]
    if not pool:
        return {'answer':f"{part['name']}의 로컬 정비자료가 아직 색인되지 않았습니다. 자료 가져오기를 실행해 주세요.",'sources':[],'mode':'manual','partId':part['id']}
    prepared=service_guides.build_guide(part,question,RECORDS,MANUALS)
    if prepared:
        guide,plain,used=prepared
        return {'answer':plain,'guide':guide,'presentation':'service-guide','sources':[source(r) for r in used],
                'mode':'manual','partId':part['id'],'notice':'차량 사양과 정비 전후 작업은 원문에서 확인하세요. 사진·증상만으로 고장을 확정하지 않습니다.'}
    query=set(words(question))
    scored=[]
    for r,doc in pool:
        score=sum(math.log(1+len(RECORDS)/(1+DF[t]))*(1+math.log(doc[t])) for t in query & doc.keys())
        if re.search(r'수리|교체|교환|탈거|장착',question) and re.search(r'탈거|장착|교환',r['text']): score+=9
        if re.search(r'진단|점검|고장|증상',question) and re.search(r'점검|진단|고장',r['text']): score+=9
        if re.search(r'위치|구성|무엇|설명|정보',question) and r['page']==part['overview']: score+=12
        scored.append((score,r))
    chosen=sorted([r for _,r in sorted(scored,key=lambda v:v[0],reverse=True)[:3]],key=lambda r:r['page'])
    return {'answer':part['name']+'의 현재 교범 버전에 맞는 정리된 안내를 제공할 수 없습니다. 자료 버전과 요약의 출처를 확인해 주세요. 아래 원문 링크에서 관련 페이지를 열 수 있습니다.',
            'sources':[source(r) for r in chosen],'mode':'manual','partId':part['id'],
            'notice':'검토한 교범 버전 또는 연결 페이지가 바뀌면 정리된 안내를 다시 검증해야 합니다.'}

@lru_cache(maxsize=32)
def render_figure(part_id,figure_id):
    part=find_part(part_id)
    fig=service_guides.figure_spec(part_id,figure_id)
    if not part or not fig:
        raise ValueError('등록되지 않은 그림입니다.')
    doc=next((d for d in MANUALS if d['id']==part['docId']),None)
    if not doc or doc.get('sha256')!=service_guides.DATA['sourceHashes'].get(part['docId']):
        raise ValueError('그림의 교범 버전이 맞지 않습니다.')
    if not any(r['docId']==part['docId'] and r['page']==fig['page'] for r in RECORDS):
        raise ValueError('색인되지 않은 그림입니다.')
    from PIL import Image
    with Image.open(io.BytesIO(render_page(part['docId'],fig['page']))) as image:
        left,top,right,bottom=fig['crop']
        if not 0<=left<right<=1 or not 0<=top<bottom<=1:
            raise ValueError('잘못된 그림 범위입니다.')
        cropped=image.crop((round(left*image.width),round(top*image.height),round(right*image.width),round(bottom*image.height)))
        output=io.BytesIO();cropped.save(output,format='PNG');cropped.close()
        return output.getvalue()

def render_page(doc_id,number):
    doc=next((d for d in MANUALS if d['id']==doc_id),None)
    if not doc or not 1<=number<=doc['pages'] or not Path(doc['path']).is_file():
        raise ValueError('존재하지 않는 문서 또는 페이지입니다.')
    import pypdfium2 as pdfium
    with RENDER_LOCK:
        pdf=pdfium.PdfDocument(doc['path'])
        page=pdf[number-1]
        bitmap=page.render(scale=1.4)
        image=bitmap.to_pil(); output=io.BytesIO(); image.save(output,format='PNG')
        image.close(); bitmap.close(); page.close(); pdf.close()
        return output.getvalue()
