"""Bounded public KGM model-U queries; no PDF registration prerequisite."""
import json
import re
import threading
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError
import part_prices

ENDPOINT='https://web.kg-mobility.com/app/network/getGenuPratList.do'
SOURCE='https://www.kg-mobility.com/sr/service-network/search-parts'
CACHE={}
LOCK=threading.Lock()
TTL=900


def keyword(question,part=None):
    number=re.search(r'(?<![A-Za-z0-9])[A-Z0-9]{10,14}(?![A-Za-z0-9])',question)
    if number:return number[0],'B'
    text=re.sub(r'202\d년형?|렉스턴\s*스포츠(?:\s*칸)?|차량|자동차|순정|공식|부품|현재|최신|지금|오늘',' ',question)
    text=re.sub(r'(?:가격|얼마|금액|비용|단가).*','',text)
    text=re.sub(r'교체|교환|공임|포함|별도|그럼',' ',text)
    text=re.sub(r'[?!.,]','',text).strip()
    text=re.sub(r'(의|은|는|이|가|을|를)$','',text).strip()
    if not text and part:text=part['name']
    replacements={'헤드라이트':'헤드 램프','헤드램프':'헤드 램프','사이드미러':'아웃사이드 미러','에어컨 필터':'에어컨 필터','와셔 노즐':'와셔 노즐','엔진오일':'엔진 오일'}
    for a,b in replacements.items():text=text.replace(a,b)
    if not re.fullmatch(r'[가-힣A-Za-z0-9 ()-]{2,60}',text):return None
    if re.fullmatch(r'렉스턴|스포츠|칸|쿨멘|중고|풀옵션|그거|그것|이거|차',text):return None
    text=re.sub(r'(와이퍼|오일|워터|연료|와셔|블로워)(모터|펌프|필터|노즐)',r'\1 \2',text)
    for a,b in {'운전석':'좌','왼쪽':'좌','좌측':'좌','동반석':'우','조수석':'우','오른쪽':'우','우측':'우','블로워':'블로어','프런트':'프론트','헤드램프':'헤드 램프','배터리':'배터리','링케이지':'링키지'}.items():text=text.replace(a,b)
    return ' '.join(text.split()),'A'


def lookup(term,kind):
    key=(term,kind)
    with LOCK:
        cached=CACHE.get(key)
        if cached and time.monotonic()-cached[0]<TTL:return cached[1]
    tokens=term.split()
    search_term=next((t for t in reversed(tokens) if t not in ('좌','우','엔진','어셈블리')),term) if kind=='A' else term
    rows=[]
    for page in range(1,4):
        params=urlencode({'pageIdx':page,'rowsPerPage':20,'modelCd':'U','schType':kind,'schTxt':search_term})
        req=Request(ENDPOINT+'?'+params,headers={'Origin':'https://www.kg-mobility.com','Referer':'https://www.kg-mobility.com/','User-Agent':'Mozilla/5.0'})
        with urlopen(req,timeout=6) as response:raw=response.read(500001)
        if len(raw)>500000:raise ValueError('Oversized response')
        data=json.loads(raw)
        if str(data.get('code'))!='0000':raise ValueError('KGM response code')
        batch=data.get('body',{}).get('genuPratInfoList')
        if not isinstance(batch,list):raise ValueError('KGM response rows')
        rows.extend(batch[:20])
        if len(batch)<20 or len(rows)>=int(data.get('paginationInfo',{}).get('totalCount',0)):break
    items=[]
    for row in rows:
        if not isinstance(row,dict):continue
        if 'U' not in str(row.get('modelCd','')).split():continue
        price=str(row.get('salePrce',''))
        name=row.get('partNm');number=row.get('partNo')
        if not isinstance(name,str) or not isinstance(number,str) or not re.fullmatch(r'[A-Za-z0-9-]{5,25}',number):continue
        if not re.fullmatch(r'\d+(?:\.0+)?',price) or not 0<float(price)<100000000:continue
        # Validate matching too: never let an unrelated server result become a quote.
        if kind=='B' and number!=term:continue
        normalized=lambda s:re.sub(r'[^가-힣a-z0-9]','',s.lower())
        if kind=='A' and not all(normalized(t) in normalized(name) for t in tokens):continue
        if kind=='A' and any(t in ('좌','우') and not name.endswith('-'+t) for t in tokens):continue
        items.append({'name':name[:160],'partNumber':number,'priceExVat':int(float(price))})
    result={'items':list({i['partNumber']:i for i in items}.values())[:20],'checkedAt':datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M'),
            'totalCount':data.get('paginationInfo',{}).get('totalCount',len(rows))}
    with LOCK:
        if len(CACHE)>256:CACHE.clear()
        CACHE[key]=(time.monotonic(),result)
    return result


def answer(question,part=None):
    query=keyword(question,part)
    if not query:return None
    error=False
    try:result=lookup(*query)
    except (URLError,OSError,TimeoutError,ValueError,TypeError,AttributeError):
        error=True;result=None
    if not result or not result['items']:
        fallback=part_prices.answer(part,question) if part else None
        if fallback and fallback.get('sources'):
            fallback['answer']=('공식 실시간 조회에 연결하지 못해' if error else '해당 검색어의 실시간 결과가 없어')+' 저장된 확인일의 가격을 표시합니다.\n\n'+fallback['answer']
            return fallback
        return {'answer':('공식 부품 가격 조회에 연결하지 못했습니다.' if error else '이 검색어에 일치하는 렉스턴 스포츠 공식 가격을 찾지 못했습니다.')+' 정확한 품번이나 다른 부품명으로 다시 조회해 주세요. 가격은 임의로 추정하지 않습니다.\n공식 조회: '+SOURCE,
                'sources':[],'mode':'official','reason':'price-unavailable','partId':part['id'] if part else None}
    record={**result,'partName':query[0],'publisher':'KG 모빌리티','url':SOURCE,'modelCode':'U','applicability2023':'미확정 — 렉스턴 스포츠 차종 조회 결과이며 2023년형의 차대번호·옵션별 호환은 별도 확인 필요'}
    source=part_prices.source(record)
    text=f"공식 부품 가격 후보 · 확인일 {result['checkedAt']} (한국 시간)\n2023년형 해당 여부: {record['applicability2023']}\n\n{source['text']}\n\n부가세·공임·배송비 별도입니다. 품번이 다른 후보는 서로 대체 가능한 부품이라는 뜻이 아닙니다. 최대 20개 후보를 표시하며 세부 품명이나 품번으로 좁힐 수 있습니다.\n출처: KG 모빌리티 · {SOURCE}"
    return {'answer':text,'sources':[source],'mode':'official','partId':part['id'] if part else None,
            'notice':'제작사 공식 부품 검색 결과입니다. 같은 검색어는 최대 15분간 캐시하며 실제 조회 시각을 표시합니다.'}
