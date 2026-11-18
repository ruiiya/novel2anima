import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'database/src'))
from n2m_db import (connect,apply_migrations,create_story,add_role,bind_role,
                    save_natural_prompt,export_story_prompts,export_bundle)
from n2m_workflow import save_plan,add_act,add_beat,add_event,save_shot,save_continuity,save_qa
from n2m_storyboard import save_storyboard,get_storyboard,seal_storyboard,apply_delta,compare_storyboards


class VisualStoryboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.con = connect(self.root/'db.sqlite')
        apply_migrations(self.con)

    def tearDown(self):
        self.con.close()
        self.temp.cleanup()

    def fixture(self, mode='BLIND'):
        c = self.con
        story = create_story(c,'Notebook',mode,'A hands a notebook to B. B smiles.',['mature'])
        for role in ('LEAD','PARTNER_A'):
            add_role(c,story,role)
        chars = {}
        for role in ('LEAD','PARTNER_A'):
            char = None
            if mode == 'NON_BLIND':
                char = 'char_'+role
                c.execute('INSERT INTO characters(id,slug,display_name) VALUES(?,?,?)',(char,char,role))
                c.commit()
                bind_role(c,story,role,char)
            chars[role] = {'description':role+' with dark hair','provenance':'user',
                           'character_id':char,'outfit_id':None}
        rev = save_plan(c,story,{'approval':{'status':'APPROVED','evidence':'user confirmed'}})
        act = add_act(c,story,1,'Reading room')
        beat = add_beat(c,act,1,'Notebook handover')
        evt = add_event(c,beat,1,{'action':'passes notebook','actor_role_key':'LEAD','target_role_key':'PARTNER_A'})
        react = add_event(c,beat,2,{'action':'smiles','actor_role_key':'PARTNER_A'})
        base = {'beat_id':beat,'branch_key':'main','role_keys':['LEAD','PARTNER_A'],
                'location_key':'room','style_key':'anime','prop_keys':['notebook']}
        board = {'story_revision':rev,'approval':{'status':'APPROVED','evidence':'user confirmed'},
                 'visual_bible':{'characters':chars,
                    'locations':{'room':{'description':'reading room, oak table','provenance':'user'}},
                    'styles':{'anime':{'description':'clean anime linework','provenance':'user','tone':'warm'}},
                    'props':{'notebook':{'description':'blue notebook','provenance':'user'}}},
                 'shots':[
                     {**base,'shot_key':'S2','shot_order':1,'purpose':'ACTION','focus':'notebook',
                      'camera':'medium','visual_moment':'A passes notebook to B','transition':'START','previous_shot_key':None},
                     {**base,'shot_key':'S10','shot_order':2,'purpose':'REACTION','focus':'smile',
                      'camera':'close-up','visual_moment':'B smiles','transition':'CAMERA_CUT','previous_shot_key':'S2'}],
                 'coverage':[
                     {'event_id':evt,'status':'VISUALIZED','shot_key':'S2','evidence':'handover'},
                     {'event_id':react,'status':'VISUALIZED','shot_key':'S10','evidence':'reaction'}]}
        return story,board

    def materialize(self, bid, break_state=False, no_qa=False):
        c = self.con
        board = get_storyboard(c,bid)
        bindings = {}
        scene_history = {}
        for i,slot in enumerate(board['slots']):
            s = json.loads(slot['spec_json'])
            mapped = [r['event_id'] for r in board['plan']['coverage'] if r.get('shot_key') == s['shot_key']]
            interactions=[]
            for event_id in mapped:
                e=c.execute('''SELECT e.action,a.role_key AS actor,t.role_key AS target FROM story_events e
                    LEFT JOIN story_roles a ON a.id=e.actor_role_id LEFT JOIN story_roles t ON t.id=e.target_role_id
                    WHERE e.id=?''',(event_id,)).fetchone()
                if e['actor'] in s['role_keys'] and (not e['target'] or e['target'] in s['role_keys']):
                    interactions.append({'event_id':event_id,'actor_role_key':e['actor'],
                                         'target_role_key':e['target'],'action_text':e['action']})
            spec = {'participants':[{'role_key':r} for r in s['role_keys']], 'interactions':interactions,
                    'camera':s['camera'],'focus':s['focus'],'location_key':s['location_key'],
                    'visual_context_sha256':slot['context_sha256']}
            shot,_ = save_shot(c,s['beat_id'],s['shot_key'],spec,mapped[0])
            after_scene = {'location_key':s['location_key']}
            before_scene = scene_history.get(s.get('previous_shot_key'),after_scene)
            scene_history[s['shot_key']] = after_scene
            snap = [{'role_key':None,'before':before_scene,'after':after_scene,
                     'delta':{'set':after_scene if before_scene!=after_scene else {},'remove':[]}}]
            for r in s['role_keys']:
                before = {'holding':'notebook' if (i==0 and r=='LEAD') or (i>0 and r=='PARTNER_A') else None}
                if break_state and i==1 and r=='LEAD':
                    before = {'holding':'notebook'}
                after = {'holding':'notebook' if r=='PARTNER_A' else None}
                snap.append({'role_key':r,'before':before,'after':after,
                             'delta':{'set':after,'remove':[]}})
            save_continuity(c,shot,{'snapshots':snap})
            prompt,_ = save_natural_prompt(c,shot,'sensitive, 1girl, solo, reading room, upper body, eye level\n'
                                                   'Anime illustration of two people in a reading room, '+s['visual_moment']+'.')
            if not no_qa:
                save_qa(c,'PROMPT',prompt,'PASS',{'policy_decision':{'scope':'PROMPT_DERIVATION',
                    'decision':'PASS','shot_id':shot,'policy_version':'1.3.0','evidence':'fixture assessed'}},
                    'N2M-CONTENT-POLICY:1.3.0')
            bindings[s['shot_key']] = {'shot_id':shot,'prompt_id':prompt}
        return {'bindings':bindings,'sequence_qa':{'verdict':'PASS','evidence':'fixture sequence assessed'}}

    def test_blind_sealed_order_and_exact_prompt(self):
        story,obj = self.fixture()
        bid,rev = save_storyboard(self.con,story,obj,0)
        self.assertEqual(save_storyboard(self.con,story,obj,1),(bid,rev))
        inputs = self.materialize(bid)
        seal = seal_storyboard(self.con,bid,inputs)
        self.assertEqual(seal_storyboard(self.con,bid,inputs),seal)
        first = inputs['bindings']['S2']
        save_natural_prompt(self.con,first['shot_id'],'sensitive, 1girl, solo, reading room, upper body\n'
                                                     'A different unapproved prompt.')
        out = self.root/'out'
        export_story_prompts(self.con,story,out)
        rows=[json.loads(line) for line in (out/'prompts.all.jsonl').read_text().splitlines() if line]
        self.assertEqual([r['shot_key'] for r in rows],['S2','S10'])
        self.assertEqual([r['shot_order'] for r in rows],[1,2])
        self.assertNotEqual(rows[0]['prompt'],'A different unapproved prompt.')
        self.assertEqual(rows[0]['storyboard_id'],bid)
        self.assertTrue((out/rows[0]['bundle_dir']/'natural.prompt.txt').exists())
        self.assertEqual(self.con.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        self.assertEqual(list(self.con.execute('PRAGMA foreign_key_check')),[])

    def test_nonblind_and_stale_casting_default_export(self):
        story,obj = self.fixture('NON_BLIND')
        bid,_=save_storyboard(self.con,story,obj)
        seal_storyboard(self.con,bid,self.materialize(bid))
        bind_role(self.con,story,'LEAD','char_PARTNER_A')
        with self.assertRaisesRegex(ValueError,'STALE_STORYBOARD'):
            export_story_prompts(self.con,story,self.root/'fail')
        self.assertFalse((self.root/'fail').exists())
        export_story_prompts(self.con,story,self.root/'archive',bid)

    def test_coverage_missing_and_foreign_event(self):
        story,obj=self.fixture()
        obj['coverage'].pop()
        with self.assertRaisesRegex(ValueError,'SOURCE_COVERAGE_MISSING'):
            save_storyboard(self.con,story,obj)
        self.assertEqual(self.con.execute('SELECT count(*) FROM storyboards').fetchone()[0],0)
        _,other=self.fixture()
        obj['coverage'].append(other['coverage'][1])
        with self.assertRaisesRegex(ValueError,'Invalid coverage'):
            save_storyboard(self.con,story,obj)

    def test_unsupported_record_kept_and_full_export_blocked(self):
        story,obj=self.fixture()
        obj['shots'].pop()
        obj['coverage'][1].update(status='UNSUPPORTED_CONTENT',shot_key=None,evidence='recorded policy decision')
        bid,_=save_storyboard(self.con,story,obj)
        self.assertEqual(get_storyboard(self.con,bid)['plan']['coverage'][1]['status'],'UNSUPPORTED_CONTENT')
        with self.assertRaisesRegex(ValueError,'SOURCE_COVERAGE_BLOCKED'):
            seal_storyboard(self.con,bid,self.materialize(bid))
        with self.assertRaisesRegex(ValueError,'Storyboard seal'):
            export_story_prompts(self.con,story,self.root/'blocked')

    def test_continuity_mismatch_and_no_qa(self):
        story,obj=self.fixture()
        bid,_=save_storyboard(self.con,story,obj)
        bad=self.materialize(bid,break_state=True)
        with self.assertRaisesRegex(ValueError,'CONTINUITY_BREAK'):
            seal_storyboard(self.con,bid,bad)
        story,obj=self.fixture()
        bid,_=save_storyboard(self.con,story,obj)
        with self.assertRaisesRegex(ValueError,'Prompt QA'):
            seal_storyboard(self.con,bid,self.materialize(bid,no_qa=True))

    def test_branch_ancestry_and_immutable_records(self):
        story,obj=self.fixture()
        third={**obj['shots'][1],'shot_key':'S3','shot_order':3,'branch_key':'alt',
               'transition':'BRANCH','previous_shot_key':'S2'}
        obj['shots'].append(third)
        obj['coverage'].append({**obj['coverage'][1],'shot_key':'S3'})
        bid,_=save_storyboard(self.con,story,obj)
        seal_storyboard(self.con,bid,self.materialize(bid))
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute('UPDATE storyboard_shots SET purpose=? WHERE storyboard_id=?',('CLIMAX',bid))
        self.con.rollback()
        obj['shots'][2]['transition']='CONTINUOUS'
        with self.assertRaisesRegex(ValueError,'fork explicitly'):
            save_storyboard(self.con,story,obj)

    def test_repair_revisions_do_not_change_old_seals(self):
        story,obj=self.fixture()
        bid,_=save_storyboard(self.con,story,obj)
        old=self.materialize(bid)
        seal_storyboard(self.con,bid,old)
        revised=copy.deepcopy(obj)
        revised['shots'][1]['camera']='medium close-up'
        new,_=save_storyboard(self.con,story,revised,1)
        first_old=get_storyboard(self.con,bid)['slots'][0]['context_sha256']
        first_new=get_storyboard(self.con,new)['slots'][0]['context_sha256']
        self.assertEqual(first_old,first_new)
        self.assertNotEqual(get_storyboard(self.con,bid)['slots'][1]['context_sha256'],
                            get_storyboard(self.con,new)['slots'][1]['context_sha256'])
        diff=compare_storyboards(self.con,bid,new)
        self.assertEqual(diff['changed'],['S10'])
        self.assertEqual(diff['candidate_reuse'],['S2'])
        with self.assertRaisesRegex(ValueError,'STALE_VISUAL_CONTEXT'):
            seal_storyboard(self.con,new,old)
        with self.assertRaisesRegex(ValueError,'Storyboard seal'):
            export_story_prompts(self.con,story,self.root/'fail')
        # Only changed shot needs a new spec; unchanged slot has identical context.
        repaired=self.materialize(new)
        self.assertEqual(repaired['bindings']['S2'],old['bindings']['S2'])
        seal_storyboard(self.con,new,repaired)
        export_story_prompts(self.con,story,self.root/'repaired')

    def test_qa_block_after_seal(self):
        story,obj=self.fixture()
        bid,_=save_storyboard(self.con,story,obj)
        inp=self.materialize(bid)
        seal_storyboard(self.con,bid,inp)
        prompt=inp['bindings']['S2']['prompt_id']
        save_qa(self.con,'PROMPT',prompt,'BLOCKED',{'finding':'regression'})
        with self.assertRaisesRegex(ValueError,'no longer PASS'):
            export_story_prompts(self.con,story,self.root/'blocked')

    def test_delta_and_projection(self):
        self.assertEqual(apply_delta({'a':1,'b':2},{'set':{'a':3},'remove':['b']}),{'a':3})
        with self.assertRaises(ValueError):
            apply_delta({}, {'set':{},'remove':['b']})

    def test_actor_target_reversal_fails_seal(self):
        story,obj=self.fixture()
        bid,_=save_storyboard(self.con,story,obj)
        inp=self.materialize(bid)
        old=inp['bindings']['S2']['shot_id']
        spec=json.loads(self.con.execute('SELECT shot_spec_json FROM shots WHERE id=?',(old,)).fetchone()[0])
        spec['interactions'][0].update(actor_role_key='PARTNER_A',target_role_key='LEAD')
        shot,_=save_shot(self.con,obj['shots'][0]['beat_id'],'S2',spec,obj['coverage'][0]['event_id'])
        inp['bindings']['S2']['shot_id']=shot
        with self.assertRaisesRegex(ValueError,'ACTOR_TARGET_MISMATCH'):
            seal_storyboard(self.con,bid,inp)

    def test_camera_cut_offscreen_and_return(self):
        story,obj=self.fixture()
        obj['shots'][1]['role_keys']=['PARTNER_A']
        third={**obj['shots'][0],'shot_key':'S3','shot_order':3,'purpose':'AFTERMATH',
               'transition':'CAMERA_CUT','previous_shot_key':'S10','camera':'reverse-angle medium',
               'visual_moment':'B smiles after receiving notebook','focus':'reaction'}
        obj['shots'].append(third)
        obj['coverage'].append({**obj['coverage'][1],'shot_key':'S3'})
        bid,_=save_storyboard(self.con,story,obj)
        seal_storyboard(self.con,bid,self.materialize(bid))
        revised=copy.deepcopy(obj)
        revised['shots'][1]['camera']='extreme close-up'
        b2,_=save_storyboard(self.con,story,revised)
        diff=compare_storyboards(self.con,bid,b2)
        self.assertEqual(diff['recheck_descendants'],['S3'])

    def test_empty_visual_board_retains_source_without_seal(self):
        story,obj=self.fixture()
        obj['shots']=[]
        for r in obj['coverage']:
            r.update(status='UNRESOLVED',shot_key=None,evidence='needs clarification')
        bid,_=save_storyboard(self.con,story,obj)
        self.assertEqual(get_storyboard(self.con,bid)['slots'],[])
        with self.assertRaisesRegex(ValueError,'SOURCE_COVERAGE_BLOCKED'):
            seal_storyboard(self.con,bid,{'bindings':{},'sequence_qa':{'verdict':'SKIP'}})

    def test_multi_act_location_cut(self):
        story,obj=self.fixture()
        act=add_act(self.con,story,2,'Garden')
        beat=add_beat(self.con,act,1,'In garden')
        event=add_event(self.con,beat,1,{'actor_role_key':'LEAD','action':'stands in garden'})
        obj['visual_bible']['locations']['garden']={'description':'garden beside fountain','provenance':'user'}
        third={**obj['shots'][0],'shot_key':'S3','shot_order':3,'beat_id':beat,'purpose':'TRANSITION',
               'transition':'LOCATION_CUT','previous_shot_key':'S10','location_key':'garden',
               'visual_moment':'The two people stand in a garden','focus':'garden'}
        obj['shots'].append(third)
        obj['coverage'].append({'event_id':event,'status':'VISUALIZED','shot_key':'S3','evidence':'garden scene'})
        bid,_=save_storyboard(self.con,story,obj)
        seal_storyboard(self.con,bid,self.materialize(bid))
        result=export_story_prompts(self.con,story,self.root/'out')
        self.assertEqual(result['acts'],2)
        self.assertTrue((self.root/'out/prompts/A02.jsonl').exists())
        obj['shots'][2]['transition']='CAMERA_CUT'
        with self.assertRaisesRegex(ValueError,'LOCATION_CHANGE_WITHOUT_CUT'):
            save_storyboard(self.con,story,obj)

    def test_v4_individual_prompt_without_qa_cannot_export(self):
        story,obj=self.fixture()
        bid,_=save_storyboard(self.con,story,obj)
        inp=self.materialize(bid,no_qa=True)
        with self.assertRaisesRegex(ValueError,'Prompt QA'):
            export_bundle(self.con,inp['bindings']['S2']['prompt_id'],self.root/'fail')

    def test_storyboard_cli(self):
        import subprocess
        story,obj=self.fixture()
        path=self.root/'board.json'
        path.write_text(json.dumps(obj),encoding='utf-8')
        cli=[sys.executable,str(ROOT/'database/src/n2m_workflow.py'),'--db',str(self.root/'db.sqlite')]
        result=subprocess.run(cli+['save-storyboard','--story-id',story,'--file',str(path)],
                              capture_output=True,text=True,check=True)
        bid=json.loads(result.stdout)['result'][0]
        inp=self.materialize(bid)
        path.write_text(json.dumps(inp),encoding='utf-8')
        result=subprocess.run(cli+['seal-storyboard','--storyboard-id',bid,'--file',str(path)],
                              capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(result.stdout)['status'],'PASS')
        result=subprocess.run(cli+['get-storyboard','--storyboard-id',bid],capture_output=True,text=True,check=True)
        self.assertIsNotNone(json.loads(result.stdout)['result']['seal'])

    def test_migration_from_v3_preserves_prompt(self):
        # Construct actual schema 007, insert real V3 data, then apply migration 008.
        old=connect(self.root/'old.sqlite')
        for migration in sorted((ROOT/'database/migrations').glob('00[1-7]*.sql')):
            old.executescript(migration.read_text())
        story=create_story(old,'Legacy','BLIND','One person reads.',[])
        add_role(old,story,'LEAD')
        act=add_act(old,story,1)
        beat=add_beat(old,act,1)
        shot,_=save_shot(old,beat,'S1',{'participants':[{'role_key':'LEAD'}]})
        pid,_=save_natural_prompt(old,shot,'sensitive, 1girl, solo, reading room, upper body\nA person reads a book.')
        apply_migrations(old)
        self.assertEqual(old.execute('SELECT prompt_text FROM shot_prompts WHERE id=?',(pid,)).fetchone()[0],
                         'sensitive, 1girl, solo, reading room, upper body\nA person reads a book.')
        export_story_prompts(old,story,self.root/'legacy')
        old.close()


if __name__=='__main__':
    unittest.main()
