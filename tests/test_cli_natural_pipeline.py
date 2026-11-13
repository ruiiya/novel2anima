import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'database/src'))
from n2m_db import connect, apply_migrations, create_story, add_role
from n2m_workflow import add_act, add_beat, save_shot


class CliIntegrationTests(unittest.TestCase):
    def test_cli_txt_to_bundle_and_story_jsonl(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            db = temp/'sample.db'
            con = connect(db)
            apply_migrations(con)
            story = create_story(con, 'Illustration', 'BLIND', 'Aria sits in a garden.', [])
            add_role(con,story,'LEAD')
            act = add_act(con,story,1,'Garden')
            beat = add_beat(con,act,1,'Quiet scene')
            shot_id,_=save_shot(con,beat,'S01',{'participants':[{'role_key':'LEAD'}],
                                              'interactions':[], 'camera':'medium'})
            con.close()
            prompt = temp/'natural.txt'
            prompt.write_text('Anime illustration of a woman with silver hair sitting in a green garden, '
                              'wearing a white blouse, gentle daylight and an eye-level medium shot.',encoding='utf-8')
            save = subprocess.run([sys.executable,str(ROOT/'database/src/n2m_workflow.py'),
                                    '--db',str(db),'save-natural-prompt','--shot-id',shot_id,
                                    '--file',str(prompt)],capture_output=True,text=True)
            self.assertEqual(save.returncode,0,save.stderr)
            response=json.loads(save.stdout)
            self.assertEqual(response['status'],'PASS')
            prompt_id=response['result'][0]
            bundle=temp/'bundle'
            cmd=[sys.executable,str(ROOT/'database/src/n2m_db.py'),'--db',str(db),
                 'export-bundle','--prompt-id',prompt_id,'--out-dir',str(bundle)]
            export=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(export.returncode,0,export.stderr)
            self.assertTrue((bundle/'natural.prompt.txt').is_file())
            check=subprocess.run([sys.executable,str(ROOT/'tools/novel2moss/validate_natural_prompt.py'),
                                  str(bundle/'natural.prompt.txt'),'--manifest',str(bundle/'prompt.manifest.json')],
                                 capture_output=True,text=True)
            self.assertEqual(check.returncode,0,check.stderr)
            output=temp/'story_export'
            full=subprocess.run([sys.executable,str(ROOT/'database/src/n2m_db.py'),'--db',str(db),
                                 'export-story-prompts','--story-id',story,'--out-dir',str(output)],
                                capture_output=True,text=True)
            self.assertEqual(full.returncode,0,full.stderr)
            lines=[line for line in (output/'prompts.all.jsonl').read_text().splitlines() if line]
            self.assertEqual(len(lines),1)
            self.assertIsInstance(json.loads(lines[0])['prompt'],str)
            self.assertEqual(json.loads(lines[0])['prompt'],prompt.read_text(encoding='utf-8'))

if __name__ == '__main__':
    unittest.main()
