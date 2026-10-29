import io
import unittest
from unittest.mock import patch
from PIL import Image
import maintenance
import service_guides
from server import answer, Handler

@unittest.skipUnless(maintenance.RECORDS,'Requires local manuals')
class ServiceGuideTests(unittest.TestCase):
    def test_each_part_has_traceable_paraphrases_and_images(self):
        for part in maintenance.PARTS:
            with self.subTest(part=part['id']):
                result=answer('점검 및 정비 방법',part_id=part['id'])
                self.assertEqual(result.get('presentation'),'service-guide')
                guide=result['guide'];ids={s['id'] for s in result['sources']}
                claims=[guide['description']]+guide['warnings']+[c for s in guide['sections'] for c in s['items']]
                self.assertTrue(all(set(c['refs'])<=ids for c in claims))
                self.assertTrue(all(f['ref'] in ids for f in guide['figures']))
                self.assertTrue(guide['figures'])
                # Narrative is newly organized; no whole source page is dumped into the answer.
                for source in result['sources']:
                    self.assertNotIn(source['text'],result['answer'])

    def test_moisture_symptom_selects_cover_guide_not_bumper_removal(self):
        result=answer('헤드램프에 습기와 결로가 계속 생겨요')
        self.assertIn('결로',result['guide']['subtitle'])
        self.assertIn('흡습제',result['answer'])
        steps=next(s for s in result['guide']['sections'] if s['id']=='steps')
        self.assertFalse(any('범퍼' in c['text'] for c in steps['items']))
        self.assertTrue(any('figure=moisture' in f['src'] for f in result['guide']['figures']))

    def test_filter_direction_and_fuel_priming_warning_are_preserved(self):
        self.assertIn('화살표가 아래',answer('에어컨 필터 교환')['answer'])
        result=answer('연료 필터 교환')
        self.assertTrue(any('엔진 크랭킹' in c['text'] for c in result['guide']['warnings']))

    def test_radiator_summary_keeps_refrigerant_recovery_prerequisite(self):
        result=answer('라디에이터 교환')
        self.assertIn('냉매 회수기로 에어컨 냉매 회수',result['answer'])

    def test_changed_manual_version_disables_reviewed_guide(self):
        changed=[{**m,'sha256':'changed'} for m in maintenance.MANUALS]
        with patch.object(maintenance,'MANUALS',changed):
            result=answer('배터리 점검')
        self.assertNotIn('guide',result)
        self.assertIn('버전',result['answer'])
        self.assertNotIn('REXTON SPORTS 2023.05',result['answer'])

    def test_missing_source_page_does_not_emit_unsupported_claims(self):
        part=maintenance.find_part('cabin-filter')
        fewer=[r for r in maintenance.RECORDS if not(r['docId']=='body-hvac' and r['page']==773)]
        self.assertIsNone(service_guides.build_guide(part,'교환',fewer,maintenance.MANUALS))

    def test_numeric_request_is_not_answered_with_unverified_value(self):
        result=answer('배터리 전압 규정값은?')
        self.assertIn('측정 조건',result['guide']['warnings'][0]['text'])
        self.assertNotIn('11.0 V',result['answer'])

    def test_figure_handler_accepts_only_registered_crop(self):
        stream=io.BytesIO();Image.new('RGB',(1000,1400),'white').save(stream,format='PNG')
        maintenance.render_figure.cache_clear()
        with patch('maintenance.render_page',return_value=stream.getvalue()):
            image=Image.open(io.BytesIO(maintenance.render_figure('battery','location')))
            self.assertEqual(image.size,(870,672));image.close()
        with self.assertRaises(ValueError):maintenance.render_figure('../secret','location')
        with self.assertRaises(ValueError):maintenance.render_figure('battery','../secret')
        maintenance.render_figure.cache_clear()

    def test_figure_api_rejects_invalid_ids(self):
        handler=Handler.__new__(Handler);handler.path='/manual-figure?part=unknown&figure=location'
        sent=[];handler.send=lambda code,data,mime='':sent.append(code)
        handler.do_GET();self.assertEqual(sent,[404])

if __name__=='__main__':unittest.main()
