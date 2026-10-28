import unittest
from server import answer, search

class DocumentAssistantTests(unittest.TestCase):
    def test_topics_retrieve_relevant_pages(self):
        for question, expected in [('폐쇄망 보안 데이터 구조',7),('8주 개발 일정 로드맵',8),('RAG 챗봇 기능',6),('정비관리 병목 문제',3)]:
            with self.subTest(question=question):
                self.assertIn(expected,[p['page'] for p in search(question)])

    def test_no_invented_repair(self):
        result = answer('엔진 시동이 안 걸릴 때 수리 방법과 토크값은?')
        self.assertIn('제공하지 않습니다',result['answer'])
        self.assertEqual(result['sources'][0]['page'],6)

    def test_unknown_question(self):
        result = answer('바나나 케이크 레시피')
        self.assertEqual(result['sources'],[])
        self.assertIn('찾지 못했습니다',result['answer'])

    def test_targets_are_not_measurements(self):
        self.assertIn('실측 결과가 아닌',answer('기대 효과와 가동률 성과')['answer'])

    def test_followup_retains_topic(self):
        result = answer('그 부분 더 자세히 알려줘',[{'role':'user','content':'8주 개발 일정'}])
        self.assertIn(8,[p['page'] for p in result['sources']])

if __name__ == '__main__':
    unittest.main()
