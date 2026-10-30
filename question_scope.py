"""Conservative routing: approved question forms, never keyword overlap alone."""
import re

OUTSIDE = '차량 정비 및 검토된 제작사 공식 정보에 관한 질문만 안내합니다. 렉스턴 스포츠 2023의 부품 설명, 점검 또는 정비 방법을 질문해 주세요.'
MISSING = '제공된 정비자료와 검토된 안내에서 이 질문에 답할 근거를 찾지 못했습니다. 부품 이름만으로 진단이나 수리 방법을 추측하지 않습니다. 차량 사양과 구체적인 증상을 알려 주시거나 해당 항목의 정비자료를 추가해 주세요.'
VEHICLE = r'가격|금액|얼마|차량|자동차|렉스턴|엔진|시동|누유|누수|과열|토크|공기압|정비|수리|고장|교체|교환|전압|내비게이션|브레이크|타이어|변속기|경고등|냉각수|연료|와이퍼|에어컨'
OFF_TOPIC = r'레시피|요리|케이크|날씨|주식|투자|비트코인|영화|노래|소설|번역|맛집|여행|축구|대통령|수학|시를\s*써|농담|유머|휴대폰|스마트폰|노트북'
FOLLOWUP = r'^(그것|그럼|그\s*부분|이\s*부분)?\s*(더\s*)?(자세히\s*)?(알려\s*줘|알려\s*주세요|설명해\s*줘)[.!?\s]*$'

def refusal(reason):
    return {'answer': OUTSIDE if reason == 'out-of-scope' else MISSING,
            'sources': [], 'mode': 'scope', 'reason': reason}

def supported(part, question):
    """Only general overview/workflow requests and explicitly reviewed variants.

    Unconsumed text (symptoms, specifications, other tasks) fails closed.
    This deliberately prefers a missing-evidence answer over a guessed guide.
    """
    text = re.sub(r'\s+', '', question).lower()
    terms = [part['name'], part['sgn']] + part['aliases']
    for term in sorted(terms, key=len, reverse=True):
        text = text.replace(re.sub(r'\s+', '', term).lower(), '')
    if part['id'] == 'headlamp':
        # The condensation variant is separately reviewed against page 37.
        text = re.sub(r'습기|결로|계속|생겨요|생깁니다|발생해요', '', text)
    text = re.sub(r'렉스턴스포츠|2023년?|차량', '', text)
    vocabulary = r'점검|정비|교환|교체|탈거|장착|위치|구성|설명|정보|방법|절차|작업|흐름|주의사항|역할|기능|무엇|어디|어떻게|알려주세요|알려줘|설명해주세요|설명해줘|보여주세요|보여줘|자세히|안내|및|하고|그리고|해주세요|해줘'
    text = re.sub(vocabulary, '', text)
    text = re.sub(r'[은는이가을를의에와과도요좀?!.,·~:;()]', '', text)
    return not text
