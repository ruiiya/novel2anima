import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("auditor", ROOT / "tools/novel2anima/audit_shot.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.story=json.loads((ROOT/'examples/story_plan.example.json').read_text(encoding='utf-8'))
        self.shot=json.loads((ROOT/'examples/shot_spec.example.json').read_text(encoding='utf-8'))

    def test_valid_example(self):
        self.assertEqual(module.audit(self.story,self.shot),[])

    def test_nsfw_metadata_retained(self):
        self.assertIn('nsfw',self.shot['intent']['raw_labels'])
        self.shot['intent']['raw_labels']=['mature']
        self.assertIn('SOURCE_LABEL_LOSS',{x['rule'] for x in module.audit(self.story,self.shot)})

    def test_action_direction_changed(self):
        self.shot['interaction']['actor_id']='NOAH'
        self.assertIn('ACTOR_TARGET_MISMATCH',{x['rule'] for x in module.audit(self.story,self.shot)})

    def test_unknown_actor(self):
        self.shot['participants']=self.shot['participants'][1:]
        self.assertIn('PARTICIPANT_LOSS',{x['rule'] for x in module.audit(self.story,self.shot)})

    def test_content_profile_not_silently_changed(self):
        self.shot['intent']['content_profile']='sfw'
        self.assertIn('CONTENT_PROFILE_CHANGED',{x['rule'] for x in module.audit(self.story,self.shot)})

    def test_immutable_source(self):
        original=copy.deepcopy(self.story)
        self.shot['interaction']['target_id']='ARIA'
        module.audit(self.story,self.shot)
        self.assertEqual(self.story,original)


if __name__=='__main__':
    unittest.main()
