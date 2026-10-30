"""Reviewed KGM part-number prices, separate from vehicle prices and repair guides."""
import json
import re
from pathlib import Path
from urllib.parse import urlparse

DATA = json.loads((Path(__file__).parent / 'data/part-prices.json').read_text(encoding='utf-8'))
PRICE = r'가격|얼마|금액|비용|단가'
SHORT_PRICE = r'^(?:그럼|그거|그것|이거)?\s*(?:가격|얼마|금액|비용|단가)(?:은|는|가|이|을|를)?\s*(?:얼마인가요|얼마예요|얼마야|알려줘|알려주세요|인가요|예요|야|요)?[?! .]*$'


def price_question(question):
    return bool(re.search(PRICE, question))


def supports(part, question):
    text = re.sub(r'\s+', '', question).lower()
    for term in sorted([part['name'], part['sgn']] + part['aliases'], key=len, reverse=True):
        text = text.replace(re.sub(r'\s+', '', term).lower(), '')
    text = re.sub(r'2023년형|2023년|2023|렉스턴스포츠|차량|부품|순정|공식|현재|최신|지금|오늘', '', text)
    text = re.sub(r'교체|교환|공임|포함|별도|가격표|가격|단가|금액|비용|얼마인가요|얼마예요|얼마야|얼마|알려주세요|알려줘|확인해주세요|확인해줘|보여주세요|보여줘', '', text)
    if part['id'] == 'wiper':
        text = re.sub(r'블레이드|모터|링케이지|링키지|암', '', text)
    if part['id'] in ('wiper', 'headlamp'):
        text = re.sub(r'운전석|동반석|조수석|왼쪽|오른쪽|좌측|우측|좌|우', '', text)
    text = re.sub(r'[은는이가을를의에요좀?!.,~]', '', text)
    return price_question(question) and not text


def records():
    return [r for r in DATA if r.get('reviewed') is True and r.get('checkedAt')
            and r.get('applicability2023') and r.get('modelCode') == 'U'
            and urlparse(r.get('url', '')).scheme == 'https'
            and urlparse(r.get('url', '')).hostname == 'www.kg-mobility.com'
            and r.get('items') and all(type(i.get('priceExVat')) is int and i['priceExVat'] > 0
                                      and i.get('partNumber') and i.get('name') for i in r['items'])]


def source(record, items=None):
    items = record['items'] if items is None else items
    lines = [f"{i['name']} · 품번 {i['partNumber']}: {i['priceExVat']:,}원 (부가세 미포함)" for i in items]
    return {**record, 'kind': 'official', 'title': record['partName'] + ' · 공식 부품 가격',
            'text': '\n'.join(lines), 'items': items}


def answer(part, question):
    if not supports(part, question):
        return None
    record = next((r for r in records() if r['partId'] == part['id']), None)
    # A complete air-cleaner housing is not the replaceable filter element.
    if part['id'] == 'air-cleaner' and re.search(r'필터|엘리먼트', question):
        record = None
    if not record:
        return {'answer': f"{part['name']}의 검토된 공식 부품 가격은 아직 등록되지 않았습니다. 정확한 품번과 차량 사양을 확인한 뒤 KGM 순정부품 조회에서 확인해 주세요. 차량 가격을 부품 가격으로 대신 안내하지 않습니다.",
                'sources': [], 'mode': 'official', 'reason': 'missing-evidence', 'partId': part['id']}
    items = record['items']
    if part['id'] == 'wiper':
        selectors = [('블레이드', '블레이드'), ('모터', '모터'), ('링케이지|링키지', '링키지'), ('암', '암')]
        for pattern, name in selectors:
            if re.search(pattern, question):
                items = [i for i in items if name in i['name']]
    if part['id'] in ('wiper', 'headlamp'):
        if re.search(r'운전석|왼쪽|좌측|(?<![가-힣])좌(?![가-힣])', question):
            items = [i for i in items if i['name'].endswith('-좌')]
        if re.search(r'동반석|조수석|오른쪽|우측|(?<![가-힣])우(?![가-힣])', question):
            items = [i for i in items if i['name'].endswith('-우')]
    if not items:
        return {'answer': '요청한 세부 품목·좌우 구분에 맞는 검토된 가격이 없습니다. 정확한 품번을 확인해 주세요.',
                'sources': [], 'mode': 'official', 'reason': 'missing-evidence', 'partId': part['id']}
    s = source(record, items)
    text = (f"{part['name']} 공식 부품 가격 · 확인일 {record['checkedAt']} (한국 시간)\n"
            f"2023년형 해당 여부: {record['applicability2023']}\n\n{s['text']}\n\n"
            '위 금액은 확인일에 조회한 부품 가격이며 부가세 미포함입니다. 공임·배송비·추가 부품을 포함한 교환 총비용이 아닙니다. '
            '가격과 품번은 일부 검토된 후보이며, 구매 전 차대번호·생산 시점·옵션으로 적용 품번을 확인해 주세요.\n'
            f"출처: {record['publisher']} · {record['url']}")
    return {'answer': text, 'sources': [s], 'mode': 'official', 'partId': part['id'],
            'notice': '공식 조회 결과를 검토해 저장한 가격입니다. 질문 시 실시간 조회하지 않으며 현재 견적이나 2023년형 호환 확정을 뜻하지 않습니다.'}
