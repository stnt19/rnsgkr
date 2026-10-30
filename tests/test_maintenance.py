import io
import json
import unittest
from types import SimpleNamespace
import maintenance
from server import answer, Handler

class MaintenanceTests(unittest.TestCase):
    def test_camera_assets_and_recognition_endpoint_are_removed(self):
        for path in ['/camera.js','/live-core.js','/camera.css']:
            handler=Handler.__new__(Handler);handler.path=path;sent=[]
            handler.send=lambda code,data,mime='':sent.append(code)
            handler.do_GET();self.assertEqual(sent,[404])
        handler=Handler.__new__(Handler);handler.path='/api/identify';sent=[]
        handler.send=lambda code,data,mime='':sent.append(code)
        handler.do_POST();self.assertEqual(sent,[404])

    def test_parts_metadata_has_no_vision_configuration(self):
        handler=Handler.__new__(Handler);handler.path='/api/parts';sent=[]
        handler.send=lambda code,data,mime='':sent.append(data)
        handler.do_GET()
        self.assertIn('parts',sent[0]);self.assertNotIn('vision',sent[0]);self.assertNotIn('visionConfigured',sent[0])

    def test_all_static_assets_are_served(self):
        for path in ['/','/style.css','/guides.css','/app.js']:
            with self.subTest(path=path):
                handler=Handler.__new__(Handler);handler.path=path
                sent=[];handler.send=lambda code,data,mime='':sent.append((code,data,mime))
                handler.do_GET()
                self.assertEqual(sent[0][0],200)
                self.assertTrue(sent[0][1])

    def test_chat_rejects_unknown_part_id(self):
        handler=Handler.__new__(Handler);handler.path='/api/chat';handler.server=SimpleNamespace(server_port=8000)
        raw=json.dumps({'question':'점검','partId':'../secret'}).encode()
        handler.headers={'Content-Length':str(len(raw))};handler.rfile=io.BytesIO(raw)
        sent=[];handler.send=lambda code,data,mime='':sent.append((code,data))
        handler.do_POST()
        self.assertEqual(sent[0][0],400)

    def test_explicit_names_resolve(self):
        for question,expected in [('배터리 점검','battery'),('에어컨 필터 교환','cabin-filter'),('에어클리너 위치','air-cleaner'),('발전기 점검','alternator')]:
            with self.subTest(question=question):
                self.assertEqual(maintenance.infer_part(question)['id'],expected)

    def test_sgn_is_work_code(self):
        self.assertEqual(maintenance.infer_part('261001')['id'],'battery')

    def test_unknown_part_is_not_guessed(self):
        self.assertIsNone(maintenance.infer_part('존재하지않는장치XYZ 설명'))
        self.assertIsNone(maintenance.find_part('../../secret'))

    def test_public_registry_hides_local_paths(self):
        self.assertTrue(all('path' not in d and 'sha256' not in d for d in maintenance.public_manuals()))

@unittest.skipUnless(maintenance.RECORDS,'Requires local manual import')
class LocalManualTests(unittest.TestCase):
    def test_all_selected_parts_have_valid_original_page(self):
        for part in maintenance.PARTS:
            detail=maintenance.part_detail(part)
            with self.subTest(part=part['id']):
                self.assertTrue(detail['available'])
                self.assertTrue(any(p['page']==part['overview'] for p in detail['pages']))
                self.assertTrue(all(any(l['docId']==p['docId'] and l['start']<=p['page']<=l['end'] for l in part['locations']) or (part.get('diagnosis') and part['docId']==p['docId'] and part['diagnosis'][0]<=p['page']<=part['diagnosis'][1]) for p in detail['pages']))

    def test_selected_part_does_not_return_other_component_sources(self):
        result=answer('위치와 탈거 장착 정보를 보여 주세요',part_id='cabin-filter')
        self.assertEqual(result['mode'],'manual')
        self.assertTrue(all(s['docId']=='body-hvac' and 771<=s['page']<=773 for s in result['sources']))
        self.assertEqual(result['presentation'],'service-guide')
        self.assertIn('장착 방향',result['answer'])

    def test_table_keeps_image_reference(self):
        result=answer('배터리 점검')
        self.assertTrue(all('/manual-page?doc=engine&page=' in s['imageUrl'] for s in result['sources']))

    def test_manual_followup_retains_part(self):
        result=answer('그럼 더 자세히 알려줘',[{'role':'user','content':'에어클리너 위치'}])
        self.assertEqual(result.get('partId'),'air-cleaner')

    def test_renderer_rejects_unknown_document(self):
        with self.assertRaises(ValueError):
            maintenance.render_page('../secret',1)

if __name__=='__main__':
    unittest.main()
