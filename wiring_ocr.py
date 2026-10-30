"""OCR discovery with exact-glyph corrections and separately reviewed pin facts.

OCR alone never establishes which pin connects to a wire, fuse or terminal.
"""
import json
import re
import math
from difflib import SequenceMatcher
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REVIEW_PATH=ROOT/'data/wiring-review.json'
REQUEST=r'배선|회로|커넥터|커넥타|단자\s*(?:번호|배열|기능|연결)|핀\s*(?:맵|번호|배열|기능)|\d+번\s*(?:핀|단자)|접지|\b(?:SB\d+|Ef\d+|[FGS]\d{3}[A-Z]{0,2})\b'
NOTICE='OCR에는 글자·숫자 오인식이 남을 수 있습니다. 단자 방향·배선 색상·회로 연결은 원본 도면에서 확인하세요. OCR 단어의 나열로 연결 관계를 추론하지 않습니다.'


def compact(text):return re.sub(r'\s+','',text).lower()


def merge_page(ocr,glyph=None):
    text=ocr['text'];method='ocr';corrected=0
    if glyph and glyph.get('unmappedCharacters')==0:
        original=glyph.get('text','')
        if len(compact(original))>=max(40,len(compact(text))*.85):
            text=original;method='ocr-glyph-checked'
        else:
            # Only repair uniquely aligned lines. Do not guess standalone IDs or numbers.
            originals=[l for l in original.splitlines() if len(compact(l))>=12 and re.search('[가-힣]',l)]
            lines=text.splitlines()
            for i,line in enumerate(lines):
                ranked=sorted([(SequenceMatcher(None,compact(line),compact(g)).ratio(),g) for g in originals],reverse=True)
                if ranked and ranked[0][0]>=.80 and (len(ranked)==1 or ranked[0][0]-ranked[1][0]>.1):
                    if lines[i]!=ranked[0][1]:corrected+=1
                    lines[i]=ranked[0][1]
            text='\n'.join(lines)
            if corrected:method='ocr-partial-glyph-check'
    return text,method,corrected


def load_records(directory,doc):
    path=Path(directory)/'wiring-ocr.local.json'
    if not path.exists():return []
    data=json.loads(path.read_text(encoding='utf-8'))
    pages=data.get('pages',[])
    if data.get('version')!=1 or data.get('sourceHash')!=doc['sha256'] or data.get('complete') is not True or data.get('engine')!='Windows.Media.Ocr' or data.get('language')!='ko':
        return []
    if len(pages)!=doc['pages'] or {p.get('page') for p in pages}!=set(range(1,doc['pages']+1)):
        return []
    glyph_path=Path(directory)/'wiring-ocr-glyphs.local.json';glyphs={}
    if glyph_path.exists():
        check=json.loads(glyph_path.read_text(encoding='utf-8'))
        if check.get('sourceHash')==doc['sha256'] and check.get('method')=='exact-glyph-outline':
            glyphs={p['page']:p for p in check['pages']}
    records=[]
    for p in pages:
        if not isinstance(p.get('text'),str) or p.get('engine')!='Windows.Media.Ocr':continue
        text,method,corrected=merge_page(p,glyphs.get(p['page']))
        glyph=glyphs.get(p['page'],{})
        verified_text=glyph.get('text','') if glyph.get('unmappedCharacters')==0 else ''
        if verified_text and method!='ocr-glyph-checked':
            text=verified_text+'\n[아래는 추가 OCR 자동 인식 문구]\n'+text
        meaningful=re.sub(r'변\s*경\s*근\s*거|적\s*용\s*근\s*거|적용차대번호|적용자대번호','',text)
        if len(compact(meaningful))<8:continue
        records.append({'docId':'wiring','document':doc['name'],'page':p['page'],'text':text,'partIds':[],
                        'kind':'wiring','sourceHash':doc['sha256'],'textMethod':method,
                        'ocrEngine':data['engine'],'ocrCheckedAt':data['createdAt'],
                        'glyphText':verified_text,'ocrRawText':p['text'],
                        'ocrNotice':NOTICE,'correctedLines':corrected})
    return records


def search(question,records,manuals):
    doc=next((d for d in manuals if d['id']=='wiring'),None)
    if not doc:return None
    pool=[r for r in records if r['docId']=='wiring' and r.get('kind')=='wiring' and r.get('sourceHash')==doc['sha256'] and r.get('textMethod','').startswith('ocr')]
    if not pool:return None
    review=json.loads(REVIEW_PATH.read_text(encoding='utf-8')) if REVIEW_PATH.exists() else {}
    query=compact(question)
    selected=[];claims=[]
    if review.get('sourceHash')==doc['sha256']:
        for item in review['entries']:
            if any(compact(k) in query for k in item.get('exclude',[])):continue
            if not any(compact(k) in query for k in item['queries']):continue
            if item.get('requires') and not any(compact(k) in query for k in item['requires']):continue
            record=next((r for r in pool if r['page']==item['page']),None)
            if not record or not all(compact(s) in compact(record['text']) for s in item['anchors']):continue
            selected.append(record);claims.append(item['title']+' · PDF '+str(item['page'])+'쪽\n'+item['answer'])
    if claims:
        return {'answer':'원본 그림·표와 대조한 배선도 안내입니다.\n\n'+'\n\n'.join(claims)+'\n\n단품 측과 와이어링 측은 보는 방향이 다릅니다. 단자 번호의 방향과 적용 사양을 원본 사진에서 함께 확인하세요.',
                'records':list({r['page']:r for r in selected}.values()),'reviewed':True}
    from manual_search import terms
    aliases={'헤드라이트':'헤드 램프','헤드램프':'헤드 램프','전조등':'헤드 램프','블로워':'블로어','접지선':'접지','퓨즈박스':'퓨즈 박스'}
    translated=question
    for a,b in aliases.items():translated=translated.replace(a,b)
    query_terms=terms(translated)-{'배선','배선도','회로','회로도','커넥터','단자','핀','맵','번호','배열','기능','알려','번'}
    identifiers=re.findall(r'\b(?:SB\d+|Ef\d+|[FGS]\d{3}[A-Z]{0,2})\b',question,re.I)
    ranked=[]
    for r in pool:
        if len(set(re.findall(r'\b\d{6}\b',r['text'])))>=8:continue
        text=compact(r['text']);hits=[t for t in query_terms if t in text]
        if identifiers and not all(compact(i) in text for i in identifiers):continue
        if query_terms and not hits:continue
        score=sum(min(len(t),8)+2*math.log1p(text.count(t)) for t in hits)
        heading=compact('\n'.join(r['text'].splitlines()[:7]))
        score+=8*sum(t in heading for t in query_terms)
        if not query_terms and '회로' in text:score=1
        if '핀' in question and '핀맵' in text:score+=8
        if re.search(r'배선도|회로도',question):
            pin_table='핀맵' in text or ('단품측' in text and '와이어링측' in text and '기능' in text)
            if pin_table:score-=14
            if re.search(r'(?m)^\d{6}\s*$',r['ocrRawText']) and not pin_table:score+=12
        if r['text'].count('...')>4:score-=20
        if score>0:ranked.append((score,r))
    selected=[r for _,r in sorted(ranked,key=lambda s:(-s[0],s[1]['page']))[:3]]
    if not selected:return None
    answer=['질문과 관련된 배선도 페이지를 OCR 검색으로 찾았습니다.']
    for r in selected:
        lines=[l for l in r['text'].splitlines() if re.search('[가-힣]',l) and not re.search(r'변\s*경\s*근\s*거|적\s*용\s*근\s*거|차대번호',l)]
        lines=sorted(lines,key=lambda l:sum(len(t) for t in query_terms if t in compact(l)),reverse=True)
        answer.append(f"PDF {r['page']}쪽 · 검색된 문구: "+' / '.join(lines[:3])[:220])
    answer.append('검색된 문구는 위치를 찾기 위한 참고입니다. 이 결과만으로 핀 번호·퓨즈 용량·배선 연결을 확정하지 않습니다. 아래 원본 그림을 열어 확인하세요.')
    return {'answer':'\n\n'.join(answer),'records':selected,'reviewed':False}
