import copy
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_visual_storyboard as legacy
from n2m_db import connect, apply_migrations, save_natural_prompt, export_story_prompts
from n2m_storyboard import save_storyboard, get_storyboard, seal_storyboard, compile_bound_prompt, compare_storyboards
from n2m_workflow import save_shot, save_continuity, save_qa


def delta(before, after):
    return {'set':{k:v for k,v in after.items() if k not in before or before[k]!=v},
            'remove':sorted(set(before)-set(after))}


def snapshot(role,before,at,after):
    return {'role_key':role,'before':before,'after':after,'delta':delta(before,after),
            'moment':{'at_shot':at,'at_delta':delta(before,at),'after_delta':delta(at,after)}}


class NarrativeContinuityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.con=connect(self.root/'db.sqlite')
        self.addCleanup(self.con.close)
        apply_migrations(self.con)

    def fixture(self, mode='BLIND'):
        story,board=legacy.VisualStoryboardTests.fixture(self,mode)
        board['schema_version']=5
        visual=board['visual_bible']
        for role,char in visual['characters'].items():
            char['prompt_tags']=['black hair'] if role=='LEAD' else ['brown hair']
            char['outfits']={'daily':{'prompt_tags':['white shirt'] if role=='LEAD' else ['blue jacket']}}
        visual['locations']['room']['prompt_tags']=['indoors','wooden table']
        visual['styles']['anime']['prompt_tags']=['anime style']
        visual['props']['notebook']['prompt_tags']=['blue notebook']
        board['scenes']={'room_day':{'location_key':'room','style_key':'anime','time_key':'afternoon',
                         'role_keys':['LEAD','PARTNER_A'],'lighting_tags':['sunlight']}}
        for i,slot in enumerate(board['shots']):
            slot.update(scene_key='room_day',story_time=i,narrative_role='PEAK' if not i else 'REACTION',
                        visible_location_tags=['indoors','wooden table'] if not i else ['indoors'])
        return story,board

    def materialize(self,bid,reset=False,corrupt=False):
        board=get_storyboard(self.con,bid)
        bindings={}
        records={}
        scene={'location_key':'room','time_key':'afternoon'}
        for i,row in enumerate(board['slots']):
            slot=json.loads(row['spec_json']); key=slot['shot_key']
            mapped=[c['event_id'] for c in board['plan']['coverage'] if c.get('shot_key')==key]
            spec={'participants':[{'role_key':r} for r in slot['role_keys']], 'interactions':[],
                  'camera':slot['camera'],'focus':slot['focus'],'location_key':slot['location_key'],
                  'visual_context_sha256':row['context_sha256'],
                  'prompt_blocks':{'prefix':['safe'],'subjects':['2girls'] if len(slot['role_keys'])==2 else ['1girl','solo'],
                                   'action':['smile'],'camera':['upper body','eye level'],'prose':''}}
            for event_id in mapped:
                event=self.con.execute('''SELECT e.action,a.role_key AS actor,t.role_key AS target FROM story_events e
                    LEFT JOIN story_roles a ON a.id=e.actor_role_id LEFT JOIN story_roles t ON t.id=e.target_role_id
                    WHERE e.id=?''',(event_id,)).fetchone()
                if event['actor'] in slot['role_keys'] and (not event['target'] or event['target'] in slot['role_keys']):
                    spec['interactions'].append({'event_id':event_id,'actor_role_key':event['actor'],
                        'target_role_key':event['target'],'action_text':event['action']})
            shot,_=save_shot(self.con,slot['beat_id'],key,spec,mapped[0])
            rows=[snapshot(None,scene,scene,scene)]
            if slot['transition'] in ('SAME_MOMENT','FLASHBACK'):
                rows=copy.deepcopy(records[slot['previous_shot_key']])
            else:
                for role in ('LEAD','PARTNER_A'):
                    first=i==0 or reset
                    before={'outfit_key':'daily','holding':first==(role=='LEAD')}
                    at={**before,'holding':True if i==0 else before['holding']}
                    after={**before,'holding':role=='PARTNER_A'}
                    rows.append(snapshot(role,before,at,after))
            if corrupt and i==1:
                rows[1]['moment']['at_shot']['holding']=True
            save_continuity(self.con,shot,{'snapshots':rows})
            records[key]=rows
            prompt=compile_bound_prompt(self.con,shot)
            pid,_=save_natural_prompt(self.con,shot,prompt)
            save_qa(self.con,'PROMPT',pid,'PASS',{'policy_decision':{'scope':'PROMPT_DERIVATION','decision':'PASS',
                    'shot_id':shot,'policy_version':'fixture','evidence':'safe fixture assessed'}},'fixture')
            bindings[key]={'shot_id':shot,'prompt_id':pid}
        return {'bindings':bindings,'sequence_qa':{'verdict':'PASS','evidence':'fixture sequence verified',
                'shot_checks':{k:{'verdict':'PASS','evidence':'fixture reviewed'} for k in bindings}}}

    def test_continuous_compile_and_export_both_cast_modes(self):
        for mode in ('BLIND','NON_BLIND'):
            story,board=self.fixture(mode)
            bid,_=save_storyboard(self.con,story,board)
            seal=self.materialize(bid)
            first=compile_bound_prompt(self.con,seal['bindings']['S2']['shot_id'])
            second=compile_bound_prompt(self.con,seal['bindings']['S10']['shot_id'])
            for tag in ('black hair','brown hair','white shirt','blue jacket','sunlight','anime style'):
                self.assertIn(tag,first);self.assertIn(tag,second)
            self.assertIn('wooden table',first);self.assertNotIn('wooden table',second)
            self.assertNotIn('previous',second)
            cli=subprocess.run([sys.executable,str(legacy.ROOT/'database/src/n2m_workflow.py'),
                '--db',str(self.root/'db.sqlite'),'compile-prompt','--shot-id',seal['bindings']['S2']['shot_id'],'--save'],
                capture_output=True,text=True,check=True)
            self.assertEqual(json.loads(cli.stdout)['result']['prompt'],first)
            with self.assertRaisesRegex(ValueError,'PROMPT_COMPILER_MISMATCH'):
                save_natural_prompt(self.con,seal['bindings']['S10']['shot_id'],second.replace('blue jacket','red jacket'))
            seal_storyboard(self.con,bid,seal)
            export_story_prompts(self.con,story,self.root/mode)
            rows=[json.loads(l) for l in (self.root/mode/'prompts.all.jsonl').read_text(encoding='utf-8').splitlines() if l]
            self.assertEqual([r['transition'] for r in rows],['START','CAMERA_CUT'])

    def test_independent_allows_new_pose_state(self):
        story,board=self.fixture(); board['shots'][1].update(transition='INDEPENDENT',previous_shot_key=None,narrative_role=None)
        bid,_=save_storyboard(self.con,story,board)
        seal_storyboard(self.con,bid,self.materialize(bid,reset=True))
        revised=copy.deepcopy(board);revised['shots'][0]['focus']='hands'
        new,_=save_storyboard(self.con,story,revised)
        self.assertIn('S10',compare_storyboards(self.con,bid,new)['candidate_reuse'])

    def test_continuous_rejects_reset_and_missing_review(self):
        story,board=self.fixture();bid,_=save_storyboard(self.con,story,board)
        with self.assertRaisesRegex(ValueError,'CONTINUITY_BREAK'):
            seal_storyboard(self.con,bid,self.materialize(bid,reset=True))
        story,board=self.fixture();bid,_=save_storyboard(self.con,story,board)
        review=self.materialize(bid);review['sequence_qa']['shot_checks'].pop('S10')
        with self.assertRaisesRegex(ValueError,'CROSS_SHOT_QA_REQUIRED'):
            seal_storyboard(self.con,bid,review)

    def test_same_moment_offscreen_and_flashback(self):
        story,board=self.fixture()
        board['shots'][1].update(transition='SAME_MOMENT',story_time=0,role_keys=['PARTNER_A'],narrative_role='DETAIL')
        third={**board['shots'][0],'shot_key':'S3','shot_order':3,'branch_key':'past',
               'transition':'FLASHBACK','previous_shot_key':'S2','story_time':0}
        board['shots'].append(third)
        board['coverage'].append({**board['coverage'][0],'shot_key':'S3'})
        bid,_=save_storyboard(self.con,story,board)
        seal=self.materialize(bid)
        text=compile_bound_prompt(self.con,seal['bindings']['S10']['shot_id'])
        self.assertNotIn('black hair',text); self.assertIn('brown hair',text)
        seal_storyboard(self.con,bid,seal)
        self.assertEqual(self.con.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        self.assertFalse(self.con.execute('PRAGMA foreign_key_check').fetchall())

    def test_moment_integrity_and_scene_lock(self):
        story,board=self.fixture();board['shots'][1]['visible_location_tags']=['random room']
        with self.assertRaisesRegex(ValueError,'LOCATION_TAG_DRIFT'):
            save_storyboard(self.con,story,board)
        board['shots'][1]['visible_location_tags']=['indoors']
        bid,_=save_storyboard(self.con,story,board)
        with self.assertRaisesRegex(ValueError,'AT_SHOT_DELTA_MISMATCH'):
            self.materialize(bid,corrupt=True)
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute('UPDATE continuity_snapshots SET moment_json=NULL')
        self.con.rollback()

    def test_upgrade_preserves_v4_dependencies(self):
        original=self.con
        old=connect(self.root/'upgrade.sqlite')
        try:
            for migration in sorted((legacy.ROOT/'database/migrations').glob('00[1-8]*.sql')):
                old.executescript(migration.read_text(encoding='utf-8'))
            self.con=old
            story,board=legacy.VisualStoryboardTests.fixture(self)
            bid,_=save_storyboard(old,story,board)
            deps=[tuple(row) for row in old.execute('SELECT * FROM shot_dependencies')]
            apply_migrations(old)
            self.assertEqual(deps,[tuple(row) for row in old.execute('SELECT * FROM shot_dependencies')])
            self.assertEqual(get_storyboard(old,bid)['plan'],board)
            seal=legacy.VisualStoryboardTests.materialize(self,bid)
            seal_storyboard(old,bid,seal)
            export_story_prompts(old,story,self.root/'v4-upgraded')
            self.assertFalse(old.execute('PRAGMA foreign_key_check').fetchall())
        finally:
            self.con=original
            old.close()

    def test_known_inactive_tag_rejected(self):
        from n2m_continuity import compile_prompt
        _,board=self.fixture()
        slot=board['shots'][1]
        slot['role_keys']=['PARTNER_A']
        spec={'prompt_blocks':{'prefix':['safe'],'subjects':['1girl','solo'],
              'action':['black hair'],'camera':['close-up'],'prose':''}}
        with self.assertRaisesRegex(ValueError,'LOCKED_TAG_CONFLICT'):
            compile_prompt(board,slot,spec,{'PARTNER_A':{'outfit_key':'daily'}})


if __name__=='__main__':
    unittest.main()
