"""Extractive reference answers, never infer a repair or table value from a match."""
import math
import re

ALIASES={'오일펌프':'오일 펌프','쇼바':'쇽 업소버','브레이크':'제동','시동이 안 걸':'시동 불량','에어컨':'공조','핸들':'조향','미션':'변속기','사이드미러':'아웃사이드 미러','내비게이션':'AVNT','스마트키':'스마트 키','깜빡이':'방향 지시등'}
STOP=set('렉스턴 스포츠 차량 자동차 부품 관련 관한 내용 자료 알려 주세요 알려줘 있어 없어 있나 있나요 어떻게 무엇 정비 점검 방법 설명 작동 이상 고장 교체 수리 질문'.split())


def terms(question):
    question=question.replace('암 전류','암전류')
    for a,b in ALIASES.items():question=question.replace(a,b)
    tokens=re.findall(r'[가-힣A-Za-z0-9-]+',question.lower())
    return {re.sub(r'(에서는|에서|으로|에는|에|의|은|는|이|가|을|를)$','',t) for t in tokens if t not in STOP and len(t)>1}


def search(question,part,records,manuals):
    query=terms(question)
    names=terms(part['name']) if part else set()
    meaningful=query-names-STOP
    hashes={m['id']:m['sha256'] for m in manuals}
    scored=[]
    for r in records:
        if r['docId']=='wiring' or r.get('sourceHash')!=hashes.get(r['docId']):continue
        linked=part and part['id'] in r['partIds']
        if part and not linked:continue
        text=r['text'].lower(); compact=re.sub(r'\s+','',text)
        hits={t for t in query if t and re.sub(r'\s+','',t) in compact}
        if not linked and (not hits or not (any(len(t)>=3 for t in hits) or len(hits)>=2)):continue
        score=sum(min(len(t),8) for t in hits)
        score+=8 if linked and r['page']==part.get('overview') else 0
        score+=4 if re.search(r'고장|불량|안\s*돼|안\s*걸|이상',question) and re.search(r'고장진단|고장 진단|현상 및|점검',text) else 0
        score-=15 if text.count('...')>5 else 0
        score-=2 if r.get('kind')=='catalog' else 0
        if score>0:scored.append((score,r))
    selected=[r for _,r in sorted(scored,key=lambda v:v[0],reverse=True)[:3]]
    if not selected:return None
    # A completely generic registry-button request should still show its overview.
    heading=(part['name'] if part else '질문한 차량 항목')+' 관련 교범 원문을 찾았습니다.'
    paragraphs=[heading,'아래는 검색된 원문의 발췌입니다. 확정 진단이나 완성된 작업 절차가 아니며, 표·그림·앞뒤 주의사항은 연결된 PDF에서 함께 확인하세요.']
    for r in selected:
        lines=[l.strip() for l in r['text'].splitlines() if l.strip()]
        best=max(range(len(lines)),key=lambda i:sum(len(t) for t in meaningful|names if t in lines[i].lower())) if lines else 0
        excerpt='\n'.join(lines[max(0,best-1):best+7])[:650]
        paragraphs.append(f"{r['document']} · PDF {r['page']}쪽\n“{excerpt}”")
    if re.search(r'토크|규정|전압|몇|얼마|수명|주기',question):
        paragraphs.append('질문한 수치·조건이 정확히 일치하는지는 원문의 표와 적용 사양을 확인해야 합니다. 검색된 숫자를 차량의 규정값으로 단정하지 않습니다.')
    return '\n\n'.join(paragraphs),selected
