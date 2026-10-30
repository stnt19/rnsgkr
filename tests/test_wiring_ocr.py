import json
import uuid
import unittest
from pathlib import Path
from unittest.mock import patch
import maintenance
import wiring_ocr
from server import answer

ROOT=Path(__file__).resolve().parents[1]


class OcrCacheTests(unittest.TestCase):
    def setUp(self):
        self.path=ROOT/'tmp'/('ocr-test-'+uuid.uuid4().hex)
        self.path.mkdir(parents=True)
        self.addCleanup(self.cleanup)
        self.doc={'id':'wiring','sha256':'hash','name':'wiring.pdf','pages':1}
        self.data={'version':1,'sourceHash':'hash','complete':True,'engine':'Windows.Media.Ocr','language':'ko','createdAt':'time',
                   'pages':[{'page':1,'text':'와이퍼 모터 배선도','engine':'Windows.Media.Ocr'}]}

    def cleanup(self):
        for name in ['wiring-ocr.local.json','wiring-ocr-glyphs.local.json']:
            (self.path/name).unlink(missing_ok=True)
        self.path.rmdir()

    def save(self,data):
        (self.path/'wiring-ocr.local.json').write_text(json.dumps(data),encoding='utf-8')

    def test_missing_ocr_does_not_use_garbled_pdf_text(self):
        self.assertEqual(wiring_ocr.load_records(self.path,self.doc),[])

    def test_wrong_hash_partial_duplicate_pages_and_wrong_engine_fail_closed(self):
        for changes in [{'sourceHash':'other'},{'complete':False},{'version':99},{'pages':[]},
                        {'pages':self.data['pages']*2},{'engine':'unknown'},{'language':'ja'}]:
            with self.subTest(changes=changes):
                self.save({**self.data,**changes});self.assertEqual(wiring_ocr.load_records(self.path,self.doc),[])

    def test_valid_ocr_provenance(self):
        self.save(self.data);records=wiring_ocr.load_records(self.path,self.doc)
        self.assertEqual(records[0]['kind'],'wiring')
        self.assertEqual(records[0]['textMethod'],'ocr')
        self.assertIn('연결 관계',records[0]['ocrNotice'])

    def test_wrong_glyph_hash_cannot_correct_text(self):
        self.save(self.data)
        (self.path/'wiring-ocr-glyphs.local.json').write_text(json.dumps({'sourceHash':'wrong','method':'exact-glyph-outline','pages':[{'page':1,'unmappedCharacters':0,'text':'incorrect'}]}),encoding='utf-8')
        self.assertEqual(wiring_ocr.load_records(self.path,self.doc)[0]['textMethod'],'ocr')

    def test_unmapped_glyphs_cannot_correct_ocr(self):
        text,method,count=wiring_ocr.merge_page({'text':'SBII'}, {'unmappedCharacters':1,'text':'SB11'})
        self.assertEqual((text,method,count),('SBII','ocr',0))

    def test_standalone_identifier_is_not_guessed(self):
        text,method,count=wiring_ocr.merge_page({'text':'SBII'}, {'unmappedCharacters':0,'text':'SB11'})
        self.assertEqual(text,'SBII')

    def test_exact_aligned_heading_can_be_corrected(self):
        original='SB10~SB11, SB14, SB20, Ef1, 블로어(프런트) 릴레이'
        text,method,count=wiring_ocr.merge_page({'text':'SBIO~SBII, SB14, SB20, Ef1, 블로어(프런트) 릴레이\n'+'모터\n'*40}, {'unmappedCharacters':0,'text':original})
        self.assertIn(original,text);self.assertEqual(method,'ocr-partial-glyph-check')

    def test_explicit_part_cannot_force_another_parts_wiring(self):
        self.assertEqual(answer('와이퍼 모터 핀맵',part_id='battery')['sources'],[])

    def test_missing_or_changed_wiring_never_returns_reviewed_pin_claims(self):
        with patch.object(maintenance,'RECORDS',[]):
            self.assertEqual(answer('와이퍼 모터 핀맵')['sources'],[])
        with patch.object(maintenance,'MANUALS',[{**m,'sha256':'changed'} for m in maintenance.MANUALS]):
            self.assertEqual(answer('와이퍼 모터 핀맵')['sources'],[])


@unittest.skipUnless((ROOT/'data/wiring-ocr.local.json').exists(),'Requires local wiring OCR')
class LocalOcrTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=next(d for d in maintenance.MANUALS if d['id']=='wiring')
        cls.records=wiring_ocr.load_records(ROOT/'data',cls.doc)

    def test_all_796_pages_processed_and_searchable_results_are_unique(self):
        data=json.loads((ROOT/'data/wiring-ocr.local.json').read_text(encoding='utf-8'))
        self.assertEqual(len(data['pages']),796)
        self.assertEqual(len(self.records),766)
        self.assertEqual(len({r['page'] for r in self.records}),766)
        self.assertTrue(all(r['sourceHash']==self.doc['sha256'] and 1<=r['page']<=796 for r in self.records))

    def test_rendered_original_ground_truth_phrases_and_critical_entries(self):
        checks=json.loads((ROOT/'data/wiring-ocr-checks.json').read_text(encoding='utf-8'))
        self.assertEqual(checks['sourceHash'],self.doc['sha256'])
        by_page={r['page']:r for r in self.records};raw=0;corrected=0
        for case in checks['cases']:
            for expected in case['phrases']+case.get('critical',[]):
                with self.subTest(page=case['page'],expected=expected):
                    needle=wiring_ocr.compact(expected);r=by_page[case['page']]
                    raw+=needle in wiring_ocr.compact(r['ocrRawText'])
                    corrected+=needle in wiring_ocr.compact(r['text'])
                    self.assertIn(needle,wiring_ocr.compact(r['text']))
        self.assertEqual(corrected,76);self.assertGreater(corrected,raw)

    def test_corrupted_text_is_not_indexed(self):
        page=next(r for r in self.records if r['page']==5)
        self.assertIn('전기 회로도의 구성',page['text'])
        self.assertNotIn('㤸ὤG䟀⦐',page['text'])
        self.assertIn('"10A"',page['text'])

    @unittest.skipUnless(Path('C:/Windows/Fonts/gulim.ttc').exists(),'Requires Windows original font')
    def test_glyph_outline_mismatch_and_hidden_text_are_rejected(self):
        from scripts.check_wiring_glyphs import GlyphChecker
        checker=GlyphChecker(self.doc['path'],Path('C:/Windows/Fonts/gulim.ttc'))
        try:
            result=checker.page(5)
            self.assertGreater(result['hiddenCharacters'],0)
            self.assertNotIn('회로도 읽는법',result['text'])
            name=next(n for n in checker.fonts if '+Dotum-' in n)
            code=ord('͢')
            self.assertEqual(checker.decode(name,code),'1')
            embedded=checker.fonts[name][0];glyph=embedded['glyf'][embedded.getGlyphName(code)]
            x,y=glyph.coordinates[0];glyph.coordinates[0]=(x+1,y)
            checker.decode.cache_clear()
            self.assertIsNone(checker.decode(name,code))
        finally:checker.pdf.close()

    def test_reviewed_wiper_pin_mapping_and_image_source(self):
        r=answer('와이퍼 모터 핀맵')
        self.assertTrue(r['wiringReviewed']);self.assertIn('4번 접지',r['answer'])
        self.assertIn('3번 파킹 스위치 입력',r['answer'])
        self.assertEqual([s['page'] for s in r['sources']],[625])
        self.assertIn('doc=wiring',r['sources'][0]['imageUrl'])

    def test_headlamp_variants_do_not_mix_ground_pins(self):
        for variant,page,expected in [('2',789,'5번은 표에서 기능이'),('4',783,'5번 로우 빔 접지')]:
            with self.subTest(variant=variant):
                r=answer(f'헤드램프 {variant}-램프 핀맵')
                self.assertEqual([s['page'] for s in r['sources']],[page])
                self.assertIn(expected,r['answer'])
        r=answer('헤드램프 핀맵')
        self.assertEqual([s['page'] for s in r['sources']],[783,789])

    def test_rain_sensor_and_switch_reviewed_answers(self):
        r=answer('레인센서 단자 기능');self.assertIn('3번 LIN 통신',r['answer'])
        r=answer('와이퍼 스위치 핀맵');self.assertIn('14번은 와이퍼 볼륨 접지',r['answer'])

    def test_general_wiring_answers_are_references_not_inferred_connections(self):
        for q in ['와이퍼 배선도','블로어 배선도','F102F 커넥터','시동 회로도','배터리 배선도']:
            with self.subTest(q=q):
                r=answer(q)
                self.assertEqual(r['presentation'],'wiring-reference')
                self.assertTrue(r['sources']);self.assertFalse(r['wiringReviewed'])
                self.assertIn('확정하지 않습니다',r['answer'])
                self.assertTrue(all(s['docId']=='wiring' for s in r['sources']))
        self.assertTrue(any(s['page'] in (620,621) for s in answer('와이퍼 배선도')['sources']))

    def test_general_maintenance_and_prices_are_unchanged(self):
        self.assertEqual(answer('와이퍼 점검')['presentation'],'service-guide')
        with patch('live_prices.urlopen',side_effect=OSError()):
            self.assertEqual(answer('와이퍼 모터 가격')['mode'],'official')

    def test_unmatched_identifier_does_not_reuse_another_connector(self):
        r=answer('F999ZZ 커넥터 배선도')
        self.assertEqual(r['sources'],[])

    def test_outside_topic_cannot_use_wiring_route(self):
        self.assertEqual(answer('배선도로 케이크 레시피')['sources'],[])


if __name__=='__main__':unittest.main()
