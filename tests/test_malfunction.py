import unittest
from unittest.mock import patch

import maintenance
import question_scope as scope
from server import answer


class MalfunctionScopeTests(unittest.TestCase):
    def test_short_failure_forms_for_every_registered_part(self):
        for part in maintenance.PARTS:
            for phrase in ['작동하지 않는다', '작동이 안 돼요', '작동이 안 됩니다',
                           '작동이 이상해요', '동작 불량', '고장 났어요', '작동에 이상이 생겼어요',
                           '문제가 있어요', '작동이 안 되는데 수리 방법 알려줘',
                           '안 돼요', '먹통이에요', '안 움직여요', '안 켜져요']:
                with self.subTest(part=part['id'], phrase=phrase):
                    q=part['name']+'가 '+phrase
                    self.assertTrue(scope.supported(part,q))
                    self.assertTrue(scope.malfunction(q))

    def test_malfunction_does_not_allow_extra_unreviewed_requests(self):
        for q in ['와이퍼가 작동하지 않는다. 모터 전압 규정값은?',
                  '와이퍼가 작동하지 않는다. 배터리 교환 방법',
                  '와이퍼가 작동하지 않는다. 릴레이를 우회하는 방법',
                  '헤드램프가 고장 났어요. 밝기는 몇 루멘?',
                  '와이퍼가 작동하지 않는다. 주식 추천해줘',
                  '리어 와이퍼가 작동하지 않는다',
                  '라디에이터에서 이상한 소리가 나요']:
            with self.subTest(q=q):
                result=answer(q)
                self.assertNotIn('guide',result)
                if result['sources']:self.assertEqual(result['presentation'],'manual-reference')

    def test_unknown_parts_still_need_evidence(self):
        result=answer('브레이크가 작동하지 않는다')
        self.assertNotIn('guide',result)
        self.assertTrue(result['sources'])
        self.assertEqual(result['presentation'],'manual-reference')

    def test_missing_manual_does_not_fabricate_procedure(self):
        with patch.object(maintenance,'RECORDS',[]):
            result=answer('와이퍼가 작동하지 않는다')
        self.assertNotIn('guide',result)
        self.assertEqual(result['sources'],[])


@unittest.skipUnless(maintenance.RECORDS,'Requires local manuals')
class MalfunctionGuideTests(unittest.TestCase):
    def test_all_parts_get_conditional_maintenance_not_confirmed_diagnosis(self):
        for part in maintenance.PARTS:
            if part.get('coverage')!='reviewed-guide':continue
            with self.subTest(part=part['id']):
                result=answer(part['name']+'가 작동하지 않는다')
                self.assertEqual(result.get('presentation'),'service-guide')
                self.assertIn('원인을 확정한 진단이 아니며',result['answer'])
                self.assertIn('점검 후 필요 시',result['guide']['sections'][1]['title'])
                self.assertTrue(result['sources'])

    def test_wiper_has_traceable_checks_and_precautions(self):
        result=answer('와이퍼가 작동하지 않는다')
        self.assertEqual(result['partId'],'wiper')
        self.assertIn('얼어붙',result['answer'])
        self.assertIn('AUTO',result['answer'])
        self.assertIn('파킹',result['answer'])
        self.assertIn('음극',result['answer'])
        self.assertIn('service-upper:282',[s['id'] for s in result['sources']])
        self.assertIn('service-upper:321',[s['id'] for s in result['sources']])

    def test_typo_and_followup_keep_failure_context(self):
        for q in ['헤드렘프가 작동하지 않는다', '와이퍼가 작동하지 않는다']:
            first=answer(q)
            next_answer=answer('더 자세히 알려줘',[{'role':'user','content':q}])
            self.assertEqual(first['partId'],next_answer['partId'])
            self.assertIn('작동 이상',next_answer['guide']['subtitle'])

    def test_wiper_missing_page_or_changed_hash_disables_guide(self):
        with patch.object(maintenance,'RECORDS',[r for r in maintenance.RECORDS if not (r['docId']=='service-upper' and r['page']==321)]):
            self.assertNotIn('guide',answer('와이퍼가 작동하지 않는다'))
        with patch.object(maintenance,'MANUALS',[{**m,'sha256':'changed'} for m in maintenance.MANUALS]):
            self.assertNotIn('guide',answer('와이퍼가 작동하지 않는다'))


if __name__=='__main__':
    unittest.main()
