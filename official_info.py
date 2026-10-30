"""Reviewed manufacturer facts; no live search or unreviewed generated claims."""
import json
import re
from pathlib import Path
from urllib.parse import urlparse

RECORDS = json.loads((Path(__file__).parent / 'data/official-info.json').read_text(encoding='utf-8'))


def sources():
    # Fail closed if a future data edit introduces an unapproved source.
    return [r for r in RECORDS if urlparse(r['url']).scheme == 'https'
            and urlparse(r['url']).hostname in ('www.kg-mobility.com', 'm.kg-mobility.com', 'allways.kg-mobility.com')
            and r.get('checkedAt') and r.get('applicability2023') and r.get('reviewed') is True]


def answer(question):
    text = re.sub(r'\s+', '', question).lower()
    # Require the whole request to be a supported vehicle-price question.
    if not re.search(r'가격|얼마|금액', text):
        return None
    remainder = re.sub(r'202[0-9]년형?|202[0-9]|렉스턴스포츠|뉴렉스턴스포츠|칸|쿨멘|차량|신차|공식|제작사|홈페이지|출시당시|당시|현재|최신|지금|오늘|가격표|가격|얼마인가요|얼마예요|얼마야|얼마|금액|알려주세요|알려줘|보여주세요|보여줘|확인해주세요|확인해줘|와일드|프레스티지|노블레스|트림별|트림|은|는|이|가|을|를|의|에|요|좀|[?!.~,]', '', text)
    if remainder:
        return None
    years = set(re.findall(r'20\d{2}', text))
    if years - {'2023', '2025'}:
        return {'answer': '요청한 연식의 검토된 공식 가격 자료가 없습니다. 연식과 세부 모델에 맞는 공식 가격표 확인이 필요합니다.', 'sources': [], 'mode': 'official', 'reason': 'missing-evidence'}
    records = sources()
    if re.search(r'현재|최신|지금|오늘', text):
        return {'answer': '현재 판매 가격은 검증하지 못했습니다. 참고 문서의 공식 자료는 확인일에 검토한 과거 모델 안내이며 현재 견적이 아닙니다. 제작사에서 해당 월의 가격표를 확인해 주세요.', 'sources': [], 'mode': 'official', 'reason': 'missing-evidence'}
    selected = [r for r in records if r['modelYear'] in ([2025] if years == {'2025'} else [2023, 2025] if len(years) > 1 else [2023])]
    if '쿨멘' in text or ('칸' in text and years != {'2025'}):
        return {'answer': '요청한 연식의 칸·쿨멘 모델 가격은 검토된 자료만으로 확인할 수 없습니다. 일반 렉스턴 스포츠 가격을 대신 적용하지 않습니다.', 'sources': [], 'mode': 'official', 'reason': 'missing-evidence'}
    if not selected:
        return None
    paragraphs = [f"{r['title']}\n{r['text']}\n2023년형 해당 여부: {r['applicability2023']}\n출처: {r['publisher']} · {r['url']}\n확인일: {r['checkedAt']} (한국 시간)" for r in selected]
    return {'answer': '\n\n'.join(paragraphs), 'sources': selected, 'mode': 'official',
            'notice': '공식 자료를 검토해 저장한 안내입니다. 질문 시 실시간 검색하지 않으며, 확인일은 가격 적용일이 아닙니다.'}
