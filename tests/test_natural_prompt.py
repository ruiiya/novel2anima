import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / 'tools/novel2moss/validate_natural_prompt.py'


class NaturalPromptFileTests(unittest.TestCase):
    def test_sample_prompt_validation_and_manifest(self):
        sample = (ROOT / 'examples/natural_prompt.example.txt').read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'prompt.txt'
            path.write_bytes(sample)
            manifest = Path(tmp) / 'manifest.json'
            manifest.write_text(json.dumps({'format': 'moss-natural-v1',
                                            'prompt_sha256': hashlib.sha256(sample).hexdigest()}))
            run = subprocess.run([sys.executable, str(VALIDATOR), str(path),
                                  '--manifest', str(manifest)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)['status'], 'PASS')
            manifest.write_text(json.dumps({'format': 'moss-natural-v1',
                                            'prompt_sha256': 'bad'}))
            run = subprocess.run([sys.executable, str(VALIDATOR), str(path),
                                  '--manifest', str(manifest)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 1)
            self.assertIn('SHA256_MISMATCH', run.stdout)

    def test_reject_json_layout_as_positive_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'prompt.txt'
            path.write_text('{"summary":{},"items":[],"bbox_format":"yxyx"}')
            run = subprocess.run([sys.executable, str(VALIDATOR), str(path)],
                                  capture_output=True, text=True)
            self.assertEqual(run.returncode, 1)
            self.assertIn('JSON_OBJECT_NOT_NATURAL_PROMPT', run.stdout)

    def test_reject_conflicting_camera_angles_and_bbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'prompt.txt'
            path.write_text('A sunlit deck. Shot at 35mm directly overhead looking straight '
                            'down at her, then a low angle looking up. bbox [-480,-420,480,420].')
            run = subprocess.run([sys.executable, str(VALIDATOR), str(path)],
                                  capture_output=True, text=True)
            self.assertEqual(run.returncode, 1)
            issues = json.loads(run.stdout)['issues']
            self.assertIn('CAMERA_CONFLICT', issues)
            self.assertIn('BBOX_IN_PROMPT', issues)
            path.write_text('A sunlit deck. Shot at 35mm from a low angle, full body head to feet.')
            run = subprocess.run([sys.executable, str(VALIDATOR), str(path)],
                                  capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout)
            self.assertEqual(json.loads(run.stdout)['status'], 'PASS')


if __name__ == '__main__':
    unittest.main()
