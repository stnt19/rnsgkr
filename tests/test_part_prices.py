import unittest
from unittest.mock import patch

import part_prices
from server import answer


class PartPriceTests(unittest.TestCase):
    def test_reviewed_groups_return_part_numbers_not_vehicle_prices(self):
        for record in part_prices.records():
            with self.subTest(part=record['partId']):
                result=answer(record['partName']+' 가격은?')
                self.assertEqual(result['mode'],'official')
                self.assertEqual(result['partId'],record['partId'])
                self.assertIn('품번',result['answer'])
                self.assertIn('부가세 미포함',result['answer'])
                self.assertIn('2023년형 해당 여부: 미확정',result['answer'])
                self.assertIn('2026-10-31',result['answer'])
                self.assertNotIn('2,594만',result['answer'])
                self.assertNotIn('guide',result)

    def test_wiper_motor_does_not_return_blade_price(self):
        result=answer('와이퍼 모터 가격')
        self.assertEqual([i['partNumber'] for i in result['sources'][0]['items']],['8610036000'])
        self.assertIn('55,900원',result['answer'])
        self.assertNotIn('18,900원',result['answer'])

    def test_side_selection(self):
        result=answer('와이퍼 운전석 블레이드 가격')
        self.assertEqual([i['partNumber'] for i in result['sources'][0]['items']],['7831536000'])
        result=answer('헤드라이트 오른쪽 가격')
        self.assertTrue(all(i['name'].endswith('-우') for i in result['sources'][0]['items']))

    def test_labor_is_not_silently_included(self):
        result=answer('와이퍼 모터 공임 포함 교환 비용')
        self.assertIn('교환 총비용이 아닙니다',result['answer'])

    def test_typo_and_short_price_followup(self):
        result=answer('베터리 가격은?')
        self.assertEqual(result['partMatch']['partId'],'battery')
        for previous in ['와이퍼 모터 점검 방법','와이퍼 모터 가격']:
            result=answer('그럼 가격은?', [{'role':'user','content':previous}])
            self.assertEqual(result['sources'][0]['items'][0]['partNumber'],'8610036000')
            self.assertEqual(len(result['sources'][0]['items']),1)

    def test_ambiguous_part_and_unreviewed_price(self):
        self.assertEqual(answer('필터 가격은?')['reason'],'ambiguous-part')
        result=answer('퓨즈박스 가격')
        self.assertEqual(result['reason'],'missing-evidence')
        self.assertIn('공식 부품 가격',result['answer'])

    def test_other_year_or_unreviewed_requests_do_not_get_prices(self):
        for q in ['2025년형 배터리 가격','배터리 중고 가격','와이퍼 모터 가격과 전압',
                  '배터리와 와이퍼 가격','와이퍼 커버 가격','리어 와이퍼 가격','에어필터 가격']:
            with self.subTest(q=q):
                self.assertEqual(answer(q)['sources'],[])

    def test_failed_context_does_not_become_part_price(self):
        result=answer('가격은?', [{'role':'user','content':'배터리와 브레이크 교환 방법'}])
        self.assertNotEqual(result.get('partId'),'battery')

    def test_invalid_source_or_unreviewed_data_is_not_served(self):
        sample=part_prices.DATA[0]
        for change in [{'reviewed':False},{'url':'https://example.com/price'}, {'checkedAt':''},
                       {'items':[{'partNumber':'x','name':'x','priceExVat':0}]}]:
            with patch.object(part_prices,'DATA',[{**sample,**change}]):
                self.assertEqual(part_prices.records(),[])

    def test_vehicle_price_route_is_preserved(self):
        result=answer('2023년형 렉스턴 스포츠 가격')
        self.assertIn('2,594',result['answer'])
        self.assertNotIn('partId',result)

    def test_price_without_subject_requests_clarification(self):
        self.assertEqual(answer('가격은?')['reason'],'ambiguous-price')


if __name__=='__main__':
    unittest.main()
