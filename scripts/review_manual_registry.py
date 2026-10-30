"""Rebuild a traceable topic/part registry from chapter TOCs and matching body SGNs.

Run after full-text extraction. This reviews structure, not every repair instruction.
Unmatched TOC entries are retained in the local audit instead of guessed page links.
"""
import json
import re
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def compact(s):
    return re.sub(r'\s+', '', s).lower()


BODY_NAMES = {
    303:'프런트 도어 트림',313:'리어 도어 트림',321:'프런트 콘솔',332:'프런트 콘솔',
    342:'A-필라 트림',345:'B-필라 트림',349:'쿼터 트림',353:'리어 백 센터 트림',
    358:'선바이저',361:'그립',363:'헤드라이닝',378:'로워 메인 LH 판넬',381:'클러스터 훼시아 판넬',
    385:'사이드 훼시아 판넬',392:'크래쉬 패드 몰딩',396:'로워 메인 RH 판넬',402:'인스트루먼트 판넬',
    413:'인스트루먼트 판넬 프레임',426:'프런트 도어 아웃사이드 핸들',432:'프런트 도어 래치 및 케이블',
    436:'프런트 파워 윈도우 레귤레이터',441:'프런트 도어 사이드 실',443:'아웃사이드 미러',
    448:'리어 도어 아웃사이드 핸들',452:'리어 도어 래치 및 케이블',456:'리어 파워 윈도우 레귤레이터',
    461:'리어 도어 사이드 실',464:'후드 래치',468:'카울 그릴',474:'테일게이트 트림',
    476:'테일게이트 가니쉬 및 아웃사이드 핸들',480:'테일게이트 도어록 액츄에이터',483:'테일게이트 래치',
    486:'테일게이트 크랭크',491:'데크 트림',494:'데크 트림',497:'퓨얼 필러 도어',
    504:'프런트 범퍼',510:'프런트 범퍼',516:'프런트 범퍼',526:'프런트 범퍼',
    539:'라디에이터 그릴',544:'라디에이터 그릴',547:'엠블램',551:'리어 범퍼',556:'리어 범퍼',
    565:'패션 레일',568:'프런트 사이드 실',570:'데크 로워 사이드 실',576:'휀더 판넬',
    583:'후드 판넬',587:'프런트 도어 판넬',601:'리어 도어 판넬',615:'테일게이트 판넬',
    624:'데크 판넬(숏 데크)',637:'데크 판넬(롱 데크)',
}

ALIASES = {
    '오일 펌프':['오일펌프','엔진 오일 펌프','oil pump'],
    '워터 펌프':['워터펌프','냉각수 펌프','water pump'],
    '서모스탯':['써모스탯','서모스타트','thermostat'],
    'E-VGT':['터보차저','터보 차저','터보'],
    '고압 펌프':['고압 연료 펌프','연료 고압 펌프'],
    '예열 플러그':['글로우 플러그','예열플러그'],
    '제동장치':['브레이크','제동','브레이크 시스템'],
    '서스펜션':['현가장치','현가','쇼바','서스펜션 소음'],
    '조향장치':['조향','핸들','파워 스티어링'],
    '휠 및 타이어':['타이어','휠','타이어 공기압'],
    '냉각 시스템':['엔진 과열','냉각 계통'],
    '충전 시스템':['충전 경고등','방전'],
    '시동 시스템':['시동','시동 불량','시동 안 걸림'],
    'AISIN 6 A/T':['자동변속기','오토 미션','자동 미션'],
    '수동변속기':['수동 미션'],
    '공조':['에어컨','히터','에어컨 냉방'],
    '아웃사이드 미러':['사이드미러','사이드 미러','백미러'],
    '프런트 범퍼':['앞범퍼','앞 범퍼'], '리어 범퍼':['뒷범퍼','뒤 범퍼'],
    '헤드라이닝':['천장 내장재'], '후드 판넬':['보닛','본네트'],
    '계기판':['계기판 경고등'], '스마트 키':['스마트키'],
    '리어 뷰 카메라':['후방카메라','후방 카메라'],
    'TPMS':['타이어 공기압 경고등','공기압 경고등'],
    'BCM':['도어 잠금','도어록','문이 안 잠겨','문이 안 열려'],
    'SKM':['스마트키','스마트 키 인식'],
    'AVNT(-AVM)':['내비게이션','네비게이션','내비'],
    '실외램프':['깜빡이','방향지시등','방향 지시등'],
    'SCR 시스템':['요소수 경고등'],
    'LNT & DPF 시스템':['DPF','매연저감장치','매연 저감장치'],
}

# TOC SGNs occasionally disagree with the body or repeat for different variants.
# These PDF-page anchors were checked against both headings and printed page labels.
ANCHORS={
    ('engine','리어 머플러 컴플리트(숏 데크)'):420,
    ('chassis','셀렉터 포지션 스위치'):131,
    ('chassis','수동변속기 오버홀(2WD)'):183,
    ('chassis','리어 프로펠러 샤프트 어셈블리 (숏 데크)'):440,
    ('chassis','주차 브레이크 슈(리프)'):845,
    ('chassis','리어 디퍼렌셜 캐리어 어셈블리 (리프 스프링/LD)'):364,
    ('chassis','리어 디퍼렌셜 캐리어 어셈블리 (리프 스프링/NON-LSD)'):370,
}


def main():
    all_pages = json.loads((ROOT/'data/manual-fulltext.local.json').read_text(encoding='utf-8'))
    manuals = {d['id']:d for d in json.loads((ROOT/'data/manuals.local.json').read_text(encoding='utf-8'))}
    curated = json.loads((ROOT/'data/service-guides.json').read_text(encoding='utf-8'))['parts']
    parts = [p for p in json.loads((ROOT/'data/parts.json').read_text(encoding='utf-8')) if p['id'] in curated]
    for p in parts:
        p['coverage']='reviewed-guide'; p['locations']=[]
    audit={'unmatched':[], 'documents':{}, 'reviewDate':'2026-10-31'}
    added=[]
    for doc_id, manual in manuals.items():
        pages=[p for p in all_pages if p['docId']==doc_id]
        audit['documents'][doc_id]={'pages':len(pages),'mode':'diagram-only' if doc_id=='wiring' else 'catalog-reference' if doc_id=='catalog' else 'full-text'}
        if doc_id in ('wiring','catalog'):continue
        tocs=[p for p in pages if sum('...' in l for l in p['lines'])>=3 and not re.match(r'^\d{2}-\d+',p['lines'][0] if p['lines'] else '')]
        grouped=[]
        for toc in tocs:
            if grouped and toc['page']==grouped[-1].get('lastPage',grouped[-1]['page'])+1:
                grouped[-1]['lines']+=toc['lines'][1:]
                grouped[-1]['lastPage']=toc['page']
            else:grouped.append(dict(toc,lines=list(toc['lines'])))
        tocs=grouped
        for ti,toc in enumerate(tocs):
            chapter_end=tocs[ti+1]['page']-1 if ti+1<len(tocs) else manual['pages']
            body=[p for p in pages if toc['page']<p['page']<=chapter_end]
            chapter=toc['lines'][0]
            if len(chapter)>45:continue
            added.append({'name':chapter,'sgn':'','start':toc['page']+2,'end':chapter_end,'docId':doc_id,'chapter':chapter,'type':'system'})
            entries=[]
            for i,line in enumerate(toc['lines']):
                m=re.match(r'^(\d{6})\s+(.+)',line)
                if not m:continue
                title=m[2]
                if '..' not in title and i+1<len(toc['lines']):
                    nxt=toc['lines'][i+1]
                    if not re.match(r'^\d|일반사항|개요|구성|작동',nxt) and '..' in nxt:title+=' '+nxt
                title=re.sub(r'\.{2,}.*$','',title).strip().rstrip('.')
                if m[1]=='000000' and title in ('시스템 점검','점검','고장진단'):continue
                entries.append((m[1],title))
            code_pages=[p for p in body if re.search(r'(?m)^\d{6}(?:\s|$)',p['text'])]
            for code,title in entries:
                candidates=[p for p in code_pages if re.search(r'(?m)^'+code+r'(?:\s|$)',p['text'])]
                anchor=ANCHORS.get((doc_id,title))
                if anchor:
                    candidates=[p for p in body if p['page']==anchor]
                if not candidates:
                    audit['unmatched'].append({'docId':doc_id,'tocPage':toc['page'],'name':title,'sgn':code});continue
                # Repeated SGNs refer to variants, sensors, or overhaul; title agreement wins.
                terms=[t for t in re.findall(r'[가-힣A-Za-z0-9]+',title) if t not in ('어셈블리','시스템','및')]
                ranked=sorted(candidates,key=lambda p:(-sum(len(t) for t in terms if compact(t) in compact(' '.join(p['lines'][:18]))),p['page']))
                if code=='000000' and not all(compact(t) in compact(ranked[0]['text']) for t in terms):
                    audit['unmatched'].append({'docId':doc_id,'tocPage':toc['page'],'name':title,'sgn':code});continue
                start=ranked[0]['page']
                if anchor:
                    actual=re.search(r'(?m)^(\d{6})\s*$',ranked[0]['text'])
                    if actual:code=actual[1]
                next_pages=[p['page'] for p in code_pages if p['page']>start]
                end=min(next_pages)-1 if next_pages else chapter_end
                added.append({'name':title,'sgn':code,'start':start,'end':end,'docId':doc_id,'chapter':chapter,'type':'part'})
        if doc_id=='body-hvac':
            starts=sorted(BODY_NAMES)
            for j,start in enumerate(starts):
                page=next(p for p in pages if p['page']==start)
                codes=re.findall(r'(?m)^\d{6}\s*$',page['text'])
                if not codes:raise ValueError(f'Missing reviewed body SGN at {start}')
                added.append({'name':BODY_NAMES[start],'sgn':codes[0].strip(),'start':start,'end':starts[j+1]-1 if j+1<len(starts) else 650,'docId':doc_id,'chapter':'바디','type':'part'})
    # Merge identical titles across chapters, preserving all locations/variants.
    by_name={compact(p['name']):p for p in parts}
    for a in added:
        name=re.sub(r'\s*어셈블리','',a['name']).strip()
        if name in ('구성 및 요소','현상 및 조치','공기빼기 작업','일반사항'):
            name=a['chapter']+' '+name
        if a['start']>a['end']:continue
        if name.endswith('(') or len(name)<2:continue
        key=compact(name)
        existing=by_name.get(key)
        if existing is None:
            suffix=hashlib.sha256(name.encode()).hexdigest()[:6]
            existing={'id':f"{a['docId']}-{a['sgn'] or 'system'}-{a['start']}-{suffix}",'name':name,'aliases':[],
                      'docId':a['docId'],'sgn':a['sgn'] if a['sgn']!='000000' else '','pages':[a['start'],a['end']],'diagnosis':None,
                      'overview':a['start'],'group':a['chapter'],'questions':[], 'coverage':'original-reference','type':a['type'],'locations':[]}
            parts.append(existing);by_name[key]=existing
        loc={'docId':a['docId'],'start':a['start'],'end':a['end'],'section':a['chapter'],'sourceHash':manuals[a['docId']]['sha256']}
        if loc not in existing['locations']:existing['locations'].append(loc)
        existing['aliases']=list(dict.fromkeys(existing['aliases']+ALIASES.get(name,[])))
    for p in parts:
        if not p['locations']:
            p['locations']=[{'docId':p['docId'],'start':p['pages'][0],'end':p['pages'][1],'section':p['group'],'sourceHash':manuals[p['docId']]['sha256']}]
    for prefix,aliases in [('조향장치',['핸들','스티어링']),('계기판',['계기판 경고등'])]:
        variants=[p for p in parts if p['name'].startswith(prefix+'(') and p.get('type')=='system']
        if variants:
            base=variants[0]
            parts.append({**base,'id':'system-'+hashlib.sha256(prefix.encode()).hexdigest()[:8],
                          'name':prefix,'aliases':aliases,'locations':[l for p in variants for l in p['locations']]})
    audit['registeredCount']=len(parts)
    (ROOT/'data/parts.json').write_text(json.dumps(parts,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'data/manual-audit.local.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'parts':len(parts),'unmatched':len(audit['unmatched'])},ensure_ascii=False))


if __name__=='__main__':main()
