import json
import unittest
from unittest.mock import patch
import maintenance
import manual_search
from server import answer


class RegistryTests(unittest.TestCase):
    def test_unique_ids_and_valid_ranges(self):
        parts=maintenance.PARTS
        self.assertGreater(len(parts),350)
        self.assertEqual(len(parts),len({p['id'] for p in parts}))
        for p in parts:
            with self.subTest(part=p['name']):
                self.assertTrue(p['name'].strip())
                self.assertLessEqual(p['pages'][0],p['pages'][1])
                for loc in p['locations']:
                    self.assertGreater(loc['start'],0)
                    self.assertLessEqual(loc['start'],loc['end'])
                    self.assertEqual(len(loc['sourceHash']),64)

    def test_empty_system_sgn_never_matches_unrelated_text(self):
        self.assertIsNone(maintenance.infer_part('아무 관련 없는 이야기'))

    def test_variant_anchors_are_distinct(self):
        expected={'셀렉터 포지션 스위치':131,'수동변속기 오버홀(2WD)':183,
                  '주차 브레이크 슈(리프)':845,'리어 프로펠러 샤프트 (숏 데크)':440,
                  '리어 프로펠러 샤프트 (롱 데크)':444,'저압 EGR 밸브':1041}
        for name,page in expected.items():
            with self.subTest(name=name):
                p=next(p for p in maintenance.PARTS if p['name']==name)
                self.assertEqual(p['overview'],page)


@unittest.skipUnless(maintenance.RECORDS,'Requires imported local PDFs')
class ExpandedManualTests(unittest.TestCase):
    def test_all_topics_have_traceable_reference_answers(self):
        for p in maintenance.PARTS:
            with self.subTest(part=p['id']):
                result=answer('설명과 점검 방법',part_id=p['id'])
                self.assertTrue(result['sources'])
                self.assertIn(result.get('presentation'),('manual-reference','service-guide'))
                for source in result['sources']:
                    self.assertIn('#page=',source['url'])
                    self.assertIn(source['kind'],('manual','catalog'))

    def test_fulltext_coverage_and_wiring_exclusion(self):
        self.assertEqual(sum(m['pages'] for m in maintenance.MANUALS),5728)
        self.assertGreater(len(maintenance.RECORDS),4500)
        self.assertFalse(any(r['docId']=='wiring' for r in maintenance.RECORDS))
        self.assertTrue(any(r['docId']=='catalog' for r in maintenance.RECORDS))

    def test_common_vehicle_question_matrix(self):
        cases=[('오일 펌프 내용 있어?','engine'),('시동이 안 걸려요','engine'),
               ('브레이크가 고장 났어요','chassis'),('타이어 공기압은?','chassis'),
               ('에어컨 찬바람이 안 나와요','body-hvac'),('히터가 안 따뜻해요','body-hvac'),
               ('쇼바 소음이 나요','chassis'),('워터펌프 교체 방법','engine'),
               ('선루프가 안 열려요','body-hvac'),('사이드미러 교환 방법','body-hvac'),
               ('내비게이션 화면이 켜지지 않아요','service-lower'),
               ('프런트 브레이크 패드 교환','chassis'),('고압 펌프 설명','engine'),
               ('요소수 탱크 설명','engine'),('클러치 고장','chassis')]
        for q,doc in cases:
            with self.subTest(question=q):
                result=answer(q)
                self.assertTrue(result['sources'])
                self.assertTrue(any(s['docId']==doc for s in result['sources']))
                if result.get('presentation')=='manual-reference':self.assertIn('발췌',result['answer'])

    def test_oil_pump_exact_pages(self):
        r=answer('오일 펌프 내용 있어?')
        self.assertTrue(all(s['docId']=='engine' and 497<=s['page']<=499 for s in r['sources']))
        self.assertIn('오일',r['answer'])

    def test_unregistered_toc_topic_can_use_fulltext(self):
        r=answer('암 전류 점검')
        self.assertEqual(r['presentation'],'manual-reference')
        self.assertTrue(r['sources'])

    def test_no_false_airbag_correction(self):
        r=answer('에어컨 찬바람이 안 나와요')
        self.assertNotIn('에어백',r['answer'])
        self.assertNotIn('partMatch',r)

    def test_multiple_parts_keep_both_source_sets(self):
        r=answer('배터리와 브레이크 점검 방법')
        self.assertEqual({s['docId'] for s in r['sources']},{'engine','chassis'})
        self.assertNotIn('guide',r)

    def test_steering_and_instrument_variants_are_preserved(self):
        for word in ['핸들','계기판']:
            p=maintenance.infer_part(word)
            self.assertEqual(len(p['locations']),2)

    def test_every_record_page_is_in_manifest_bounds(self):
        docs={d['id']:d for d in maintenance.MANUALS}
        for r in maintenance.RECORDS:
            self.assertTrue(1<=r['page']<=docs[r['docId']]['pages'])
            self.assertEqual(r['sourceHash'],docs[r['docId']]['sha256'])

    def test_changed_hash_and_missing_index_do_not_produce_references(self):
        part=maintenance.infer_part('오일 펌프')
        changed=[{**m,'sha256':'changed'} for m in maintenance.MANUALS]
        self.assertIsNone(manual_search.search('오일 펌프',part,maintenance.RECORDS,changed))
        with patch.object(maintenance,'RECORDS',[]):
            self.assertEqual(answer('오일 펌프 설명')['sources'],[])

    def test_catalog_text_is_not_presented_as_a_repair_guide(self):
        records=[r for r in maintenance.RECORDS if r['docId']=='catalog']
        found=manual_search.search('오일 펌프',None,records,maintenance.MANUALS)
        self.assertIsNotNone(found)
        self.assertIn('완성된 작업 절차가 아니며',found[0])


if __name__=='__main__':unittest.main()
