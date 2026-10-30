import unittest
from server import answer, Handler

class DocumentAssistantTests(unittest.TestCase):
    def test_removed_topics_never_return_internal_content(self):
        for question in ['폐쇄망 보안 데이터 구조', '8주 개발 일정 로드맵', 'RAG 챗봇 기능', '정비관리 병목 문제', '기대 효과와 가동률 성과']:
            with self.subTest(question=question):
                result = answer(question)
                self.assertEqual(result['sources'], [])
                self.assertEqual(result['mode'], 'scope')
                self.assertNotIn('제안서', result['answer'])

    def test_no_invented_repair(self):
        result = answer('엔진 시동이 안 걸릴 때 수리 방법과 토크값은?')
        self.assertEqual(result['reason'],'missing-evidence')
        self.assertEqual(result['sources'],[])

    def test_unknown_question(self):
        result = answer('바나나 케이크 레시피')
        self.assertEqual(result['sources'],[])
        self.assertEqual(result['reason'],'out-of-scope')

    def test_removed_followup_has_no_sources(self):
        result = answer('그 부분 더 자세히 알려줘',[{'role':'user','content':'8주 개발 일정'}])
        self.assertEqual(result['sources'], [])

if __name__ == '__main__':
    unittest.main()

class ScopeTests(unittest.TestCase):
    def test_outside_questions_even_with_part_names(self):
        for q in ['오늘 날씨', '배터리로 케이크 만드는 레시피', '배터리 점검하고 주식 추천해줘', '스마트폰 배터리 교환 방법']:
            with self.subTest(q=q):
                r=answer(q); self.assertEqual(r['reason'],'out-of-scope'); self.assertEqual(r['sources'],[])

    def test_unsupported_vehicle_requests_have_no_guide_or_sources(self):
        for q in ['배터리 가격은?', '배터리 전압 규정값은?', '배터리 수명이 몇 년인가요?', '배터리 점검 후 화성에서 충전하는 방법', '브레이크 고장 진단', '라디에이터에서 이상한 소리가 나요', '배터리와 브레이크 교환 방법', '헤드램프 밝기는 몇 루멘인가요?']:
            with self.subTest(q=q):
                r=answer(q); self.assertEqual(r['reason'],'missing-evidence'); self.assertEqual(r['sources'],[]); self.assertNotIn('guide',r)

    def test_unrelated_followup_cannot_reuse_previous_part(self):
        r=answer('그럼 영화 추천해줘',[{'role':'user','content':'배터리 점검'}])
        self.assertEqual(r['reason'],'out-of-scope')

    def test_explicit_part_cannot_bypass_evidence_gate(self):
        self.assertEqual(answer('가격 알려줘',part_id='battery')['reason'],'missing-evidence')

    def test_unsupported_previous_question_cannot_become_generic_guide(self):
        r=answer('그럼 더 자세히 알려줘',[{'role':'user','content':'배터리 가격은?'}])
        self.assertEqual(r['reason'],'missing-evidence')

class OfficialInformationTests(unittest.TestCase):
    def test_price_has_review_date_source_and_year_scope(self):
        result = answer('2023년형 렉스턴 스포츠 가격은?')
        self.assertEqual(result['mode'], 'official')
        self.assertIn('2,594', result['answer'])
        self.assertIn('3,230', result['answer'])
        self.assertIn('조건부', result['answer'])
        source = result['sources'][0]
        self.assertEqual(source['checkedAt'], '2026-10-30')
        self.assertEqual(source['modelYear'], 2023)
        self.assertTrue(source['url'].startswith('https://allways.kg-mobility.com/'))

    def test_newer_year_is_explicitly_not_2023(self):
        result = answer('2025년형 렉스턴 스포츠 가격')
        self.assertEqual(result['sources'][0]['modelYear'], 2025)
        self.assertIn('해당 없음', result['answer'])
        self.assertNotIn('2,594', result['answer'])

    def test_unreviewed_prices_do_not_reuse_other_models(self):
        for q in ['2024년형 렉스턴 스포츠 가격', '현재 렉스턴 스포츠 가격', '2023 렉스턴 스포츠 칸 가격', '2025 렉스턴 스포츠 쿨멘 가격', '렉스턴 스포츠 중고 가격', '렉스턴 스포츠 배터리 가격', '렉스턴 스포츠 가격과 수리비', '2023 렉스턴 스포츠 풀옵션 가격']:
            with self.subTest(q=q):
                self.assertEqual(answer(q)['sources'], [])

    def test_price_followup(self):
        r = answer('더 자세히 알려줘', [{'role':'user','content':'2023년형 렉스턴 스포츠 가격'}])
        self.assertEqual(r['mode'], 'official')

    def test_removed_public_routes(self):
        for path in ['/api/pages', '/document', '/data/knowledge.json']:
            h=Handler.__new__(Handler); h.path=path; sent=[]
            h.send=lambda code,data,mime='':sent.append(code)
            h.do_GET(); self.assertEqual(sent,[404])

    def test_official_library_and_status(self):
        for path in ['/api/official-sources', '/api/status']:
            h=Handler.__new__(Handler); h.path=path; sent=[]
            h.send=lambda code,data,mime='':sent.append((code,data))
            h.do_GET(); self.assertEqual(sent[0][0],200)
            self.assertNotIn('제안서', str(sent[0][1]))

    def test_no_internal_document_content_in_static_ui(self):
        from pathlib import Path
        for name in ['index.html','app.js']:
            text=(Path(__file__).resolve().parents[1]/'web'/name).read_text(encoding='utf-8')
            for removed in ['제안서','군학연계','로드맵','/api/pages','local-model']:
                self.assertNotIn(removed,text)
