import io
import json
import unittest
from unittest.mock import patch
from urllib.error import URLError
import live_prices
import maintenance
from server import answer


def response(rows,total=None,code='0000'):
    return io.BytesIO(json.dumps({'code':code,'body':{'genuPratInfoList':rows},'paginationInfo':{'totalCount':len(rows) if total is None else total}}).encode())


def row(name='노즐 어셈블리-윈드실드 와셔',number='7845036000',price='4600.0',model='U'):
    return {'partNm':name,'partNo':number,'salePrce':price,'modelCd':model}


class LivePriceTests(unittest.TestCase):
    def setUp(self):live_prices.CACHE.clear()

    def test_pdf_unregistered_part_has_live_price(self):
        self.assertIsNone(maintenance.infer_part('와셔 노즐'))
        with patch('live_prices.urlopen',return_value=response([row()])):
            r=answer('와셔 노즐 가격')
        self.assertIn('4,600원',r['answer'])
        self.assertIsNone(r['partId'])
        self.assertIn('2023년형 해당 여부: 미확정',r['answer'])
        self.assertIn('부가세 미포함',r['sources'][0]['text'])
        self.assertTrue(r['sources'][0]['checkedAt'])

    def test_reordered_official_names_are_filtered_by_all_terms(self):
        rows=[row('펌프 어셈블리-오일','6711800701','88000'),row('펌프 어셈블리-요소수')]
        with patch('live_prices.urlopen',return_value=response(rows)) as fetch:
            result=live_prices.lookup('오일 펌프','A')
        self.assertEqual(len(result['items']),1)
        self.assertEqual(result['items'][0]['priceExVat'],88000)
        self.assertEqual(fetch.call_args.kwargs['timeout'],6)
        self.assertTrue(fetch.call_args.args[0].full_url.startswith(live_prices.ENDPOINT))

    def test_wrong_model_bad_price_wrong_part_are_discarded(self):
        rows=[row(model='X'),row(price='-1'),row(price='nan'),row(price='1.2'),row(number='<script>'),row(name='볼트')]
        with patch('live_prices.urlopen',return_value=response(rows)):
            self.assertEqual(live_prices.lookup('와셔 노즐','A')['items'],[])

    def test_part_number_search_and_mixed_model_membership(self):
        with patch('live_prices.urlopen',return_value=response([row(number='268A036000',name='배터리',model='A U X'),row(number='268A036001')])):
            result=live_prices.lookup('268A036000','B')
        self.assertEqual(len(result['items']),1)
        self.assertEqual(live_prices.keyword('268A036000 가격'),('268A036000','B'))

    def test_left_right_filter(self):
        with patch('live_prices.urlopen',return_value=response([row('헤드 램프-좌'),row('헤드 램프-우',number='1234567890')])):
            result=live_prices.lookup('헤드 램프 우','A')
        self.assertEqual([x['name'] for x in result['items']],['헤드 램프-우'])

    def test_cache_preserves_actual_checked_time(self):
        with patch('live_prices.urlopen',return_value=response([row()])) as fetch:
            first=live_prices.lookup('와셔 노즐','A');second=live_prices.lookup('와셔 노즐','A')
        self.assertEqual(fetch.call_count,1)
        self.assertEqual(first,second)
        self.assertEqual(first['checkedAt'],second['checkedAt'])

    def test_expired_cache_refreshes(self):
        live_prices.CACHE[('와셔 노즐','A')]=(-10000,{'items':[],'checkedAt':'old'})
        with patch('live_prices.urlopen',return_value=response([row()])) as fetch:
            result=live_prices.lookup('와셔 노즐','A')
        self.assertEqual(fetch.call_count,1);self.assertNotEqual(result['checkedAt'],'old')

    def test_pagination_is_bounded_and_deduplicated(self):
        with patch('live_prices.urlopen',side_effect=lambda *a,**kw:response([row()]*20,1000)) as fetch:
            result=live_prices.lookup('노즐','A')
        self.assertEqual(fetch.call_count,3)
        self.assertEqual(len(result['items']),1)

    def test_outage_uses_only_dated_reviewed_snapshot(self):
        with patch('live_prices.urlopen',side_effect=URLError('offline')):
            old=answer('와이퍼 모터 가격');unknown=answer('와셔 노즐 가격')
        self.assertIn('저장된 확인일',old['answer'])
        self.assertEqual(old['sources'][0]['checkedAt'],'2026-10-31')
        self.assertEqual(unknown['reason'],'price-unavailable')
        self.assertEqual(unknown['sources'],[])

    def test_malformed_responses_fail_without_invented_prices(self):
        for raw in [b'not json',b'{}',b'[]',b'x'*500001]:
            with self.subTest(raw=raw[:20]),patch('live_prices.urlopen',return_value=io.BytesIO(raw)):
                r=live_prices.answer('와셔 노즐 가격')
                self.assertEqual(r['sources'],[])
                self.assertEqual(r['reason'],'price-unavailable')

    def test_price_input_cannot_change_host(self):
        self.assertIsNone(live_prices.keyword('https://evil.example 가격'))
        self.assertIsNone(live_prices.keyword('../secret 가격'))

    def test_unknown_pdf_part_followup_keeps_subject(self):
        with patch('live_prices.urlopen',return_value=response([row()])):
            r=answer('그럼 가격은?',[{'role':'user','content':'와셔 노즐 점검 방법'}])
        self.assertIn('4,600원',r['answer'])

    def test_non_success_response_and_timeout(self):
        with patch('live_prices.urlopen',return_value=response([],code='9999')):
            self.assertEqual(answer('와셔 노즐 가격')['sources'],[])
        with patch('live_prices.urlopen',side_effect=TimeoutError()):
            self.assertEqual(answer('와셔 노즐 가격')['reason'],'price-unavailable')

    def test_explicit_part_cannot_mislabel_another_parts_price(self):
        with patch('live_prices.urlopen') as fetch:
            r=answer('와이퍼 모터 가격',part_id='battery')
        self.assertEqual(r['sources'],[])
        fetch.assert_not_called()


if __name__=='__main__':unittest.main()
