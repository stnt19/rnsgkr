import unittest
from server import answer, search

class DocumentAssistantTests(unittest.TestCase):
    def test_topics_retrieve_relevant_pages(self):
        for question, expected in [('폐쇄망 보안 데이터 구조',7),('8주 개발 일정 로드맵',8),('RAG 챗봇 기능',6),('정비관리 병목 문제',3)]:
            with self.subTest(question=question):
                self.assertIn(expected,[p['page'] for p in search(question)])

    def test_no_invented_repair(self):
        result = answer('엔진 시동이 안 걸릴 때 수리 방법과 토크값은?')
        self.assertEqual(result['reason'],'missing-evidence')
        self.assertEqual(result['sources'],[])

    def test_unknown_question(self):
        result = answer('바나나 케이크 레시피')
        self.assertEqual(result['sources'],[])
        self.assertEqual(result['reason'],'out-of-scope')

    def test_targets_are_not_measurements(self):
        self.assertIn('실측 결과가 아닌',answer('기대 효과와 가동률 성과')['answer'])

    def test_followup_retains_topic(self):
        result = answer('그 부분 더 자세히 알려줘',[{'role':'user','content':'8주 개발 일정'}])
        self.assertIn(8,[p['page'] for p in result['sources']])

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
