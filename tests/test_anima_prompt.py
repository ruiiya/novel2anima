import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / 'tools/novel2anima/validate_anima_prompt.py'
GOOD = ('nsfw, 1girl, solo, karin (blue archive), black hair, yellow eyes, halo, '
        'bunny suit, standing, from side, full body, green room, bright lighting\n'
        'Karin stands in the left third of the frame. Flat daylight keeps the room even.')


def run(text):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'prompt.txt'
        path.write_text(text, encoding='utf-8')
        proc = subprocess.run([sys.executable, str(VALIDATOR), str(path)],
                              capture_output=True, text=True)
        return proc.returncode, json.loads(proc.stdout)


class AnimaPromptFileTests(unittest.TestCase):
    def test_sample_prompt_validation_and_manifest(self):
        sample = (ROOT / 'examples/anima_prompt.example.txt').read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'prompt.txt'
            path.write_bytes(sample)
            manifest = Path(tmp) / 'manifest.json'
            manifest.write_text(json.dumps({'format': 'anima-tag-v1',
                                            'prompt_sha256': hashlib.sha256(sample).hexdigest()}))
            run_ = subprocess.run([sys.executable, str(VALIDATOR), str(path),
                                   '--manifest', str(manifest)], capture_output=True, text=True)
            self.assertEqual(run_.returncode, 0, run_.stdout)
            self.assertEqual(json.loads(run_.stdout)['status'], 'PASS')
            manifest.write_text(json.dumps({'format': 'anima-tag-v1', 'prompt_sha256': 'bad'}))
            run_ = subprocess.run([sys.executable, str(VALIDATOR), str(path),
                                   '--manifest', str(manifest)], capture_output=True, text=True)
            self.assertEqual(run_.returncode, 1)
            self.assertIn('SHA256_MISMATCH', run_.stdout)
            manifest.write_text(json.dumps({'format': 'moss-natural-v1',
                                            'prompt_sha256': hashlib.sha256(sample).hexdigest()}))
            run_ = subprocess.run([sys.executable, str(VALIDATOR), str(path),
                                   '--manifest', str(manifest)], capture_output=True, text=True)
            self.assertIn('FORMAT_MISMATCH', run_.stdout)

    def test_accepts_valid_tag_block(self):
        code, out = run(GOOD)
        self.assertEqual(code, 0, out)
        self.assertEqual(out['status'], 'PASS')

    def test_reject_json_layout_as_positive_prompt(self):
        code, out = run('{"summary":{},"items":[],"bbox_format":"yxyx"}')
        self.assertEqual(code, 1)
        self.assertIn('JSON_OBJECT_NOT_PROMPT', out['issues'])

    def test_tag_grammar_rules(self):
        cases = {
            'Blue hair, 1girl, solo, nsfw, full body': 'TAG_UPPERCASE',
            'nsfw, 1girl, solo, blue_hair, full body': 'TAG_UNDERSCORE',
            '1girl, solo, blue hair, full body': 'SAFETY_TAG_MISSING',
            'nsfw, 1girl, solo, blue hair, green room': 'FRAMING_TAG_MISSING',
            'nsfw, 1girl, solo, blue hair, full body, masterpiece, best quality':
                'QUALITY_TAG_FORBIDDEN',
            'nsfw, 1girl, solo, blue hair, full body, score_7': 'SCORE_TAG_FORBIDDEN',
            'nsfw,1girl,solo,blue hair,full body': 'TAG_COMMA_SPACING',
            'nsfw, solo, blue hair, full body': 'SUBJECT_COUNT_MISSING',
        }
        for text, issue in cases.items():
            with self.subTest(issue=issue):
                code, out = run(text)
                self.assertEqual(code, 1)
                self.assertIn(issue, out['issues'])

    def test_camera_conflicts(self):
        for text in ('nsfw, 1girl, solo, close-up, full body, from side',
                     'nsfw, 1girl, solo, full body, from above, from below',
                     'nsfw, 1girl, solo, full body, from side, three-quarter view'):
            with self.subTest(text=text):
                code, out = run(text)
                self.assertEqual(code, 1)
                self.assertIn('CAMERA_CONFLICT', out['issues'])

    def test_bbox_and_budget(self):
        code, out = run(GOOD.replace('green room', 'green room, bbox [-480,-420,480,420]'))
        self.assertIn('BBOX_IN_PROMPT', out['issues'])
        long_block = 'nsfw, 1girl, solo, ' + ', '.join(f'tag{i}' for i in range(400))
        code, out = run(long_block)
        self.assertIn('TOKEN_BUDGET_EXCEEDED', out['issues'])
        prose = GOOD + '\nOne. Two. Three.'
        code, out = run(prose)
        self.assertIn('PROSE_TOO_LONG', out['issues'])


if __name__ == '__main__':
    unittest.main()
