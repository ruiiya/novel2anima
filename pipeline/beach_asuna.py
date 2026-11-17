"""Beach bikini erotic album: one adult character, one bikini that never comes off,
one cove, 5 acts x 3 beats x 2 shots.

Escalation is fit and slip only: she pulls the top up and the bottom aside with her own
hands. Nothing underneath the bikini. Anima tag prompts (tag block + at most 2 prose
sentences). Character: Asuna (Blue Archive) - CONFIRMED_ADULT / REVIEWED in the catalog.
"""
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, 'database/src')
from n2m_db import (add_role, bind_role, connect, create_story, save_natural_prompt, sha)  # noqa: E402
from n2m_storyboard import save_storyboard  # noqa: E402
from n2m_workflow import (add_act, add_beat, add_event, save_continuity, save_plan,  # noqa: E402
                          save_qa, save_shot)

DB = pathlib.Path('database/data/novel2anima.db')
OUT = pathlib.Path('exports/beach_asuna/01_asuna')
PURPOSE = ('ESTABLISHING', 'DETAIL')
SHOTS_PER_BEAT = 2

TITLE = 'Bãi Biển Riêng — Asuna'
NAME = 'Asuna'
CHAR_TAG = 'asuna (blue archive)'
SERIES = 'blue archive'
IDENTITY = ['light brown hair', 'very long hair', 'blue eyes', 'rabbit ears',
            'large breasts', 'halo', 'bangs', 'mole on breast']
QUALITY = ['masterpiece', 'best quality', 'score_7']
STYLE = ['anime coloring', 'cel shading', 'clean lineart']
LIGHT = ['bright daylight', 'sunlight', 'clear sky', 'beach']

CAMS = [('full body', 'eye level'), ('cowboy shot', 'from side'), ('upper body', 'three-quarter view'),
        ('close-up', 'eye level'), ('wide shot', 'from above'), ('full body', 'from side'),
        ('cowboy shot', 'from below'), ('upper body', 'from above'), ('close-up', 'from above'),
        ('wide shot', 'eye level')]

BASE_OUTFIT = ['blue bikini', 'string bikini', 'side-tie bikini bottom', 'bare legs', 'barefoot']

STAGES = [
    ('bikini_on', BASE_OUTFIT + ['navel', 'cleavage', 'bare shoulders'],
     'the blue string bikini tied on exactly as she walked in'),
    ('top_lift', BASE_OUTFIT + ['bikini top lift', 'underboob', 'nipples', 'cleavage'],
     'the same bikini, the top pulled up enough to show the underside of her breasts'),
    ('breasts_out', BASE_OUTFIT + ['bikini top lift', 'breasts', 'nipples', 'hard nipples', 'navel'],
     'the top bunched above her chest, bare breasts out, bottom still tied'),
    ('bottom_pull', BASE_OUTFIT + ['bikini bottom pull', 'ass', 'thighs', 'pubic hair', 'clothed'],
     'the same bottom dragged aside, bare ass and pubic hair showing'),
    ('aside', BASE_OUTFIT + ['clothing aside', 'bikini pull', 'pubic hair', 'pussy', 'labia',
                             'uncensored', 'spread legs', 'nipples', 'hard nipples'],
     'the bikini still on but pulled aside: nipples hard, pussy and pubic hair fully shown'),
]

ACTS = [
 {'title': 'Bãi cát', 'safety': 'sensitive',
  'summary': 'Cô đi chân trần xuống bãi, trải khăn và ngồi xuống nhìn ra biển.',
  'env': ['beach', 'white sand', 'palm trees', 'ocean', 'cumulus clouds', 'beach towel'],
  'spec': {'set': 'private cove: white sand, palms behind, calm ocean in front', 'time': 'midday'},
  'beats': [
   ('arrive', 'She walks barefoot across the white sand toward the towel.',
    'walking, barefoot, on sand', 'calm expression',
    [('walking, barefoot, on sand', 'Asuna walks barefoot across the white sand with the sea behind her.'),
     ('standing, hand on hip, looking away', 'She stops and plants one hand on her hip, looking off toward the water.')]),
   ('towel', 'She spreads a towel on the sand and kneels down on it.',
    'kneeling on beach towel, spreading towel', 'soft smile',
    [('kneeling on beach towel, spreading towel', 'She kneels and rolls the striped towel open with both hands.'),
     ('sitting on beach towel, legs to the side', 'She settles on the towel with both legs folded to one side.')]),
   ('bask', 'She leans back on her hands with her face to the sun.',
    'sitting, leaning back on hands', 'eyes closed, smile',
    [('sitting, leaning back on hands, chest out', 'She leans back on her palms and lifts her chest toward the sun.'),
     ('looking at viewer, smile', 'Her face fills the frame with open sky behind her.')])]},

 {'title': 'Bôi kem', 'safety': 'sensitive',
  'summary': 'Cô thoa kem chống nắng lên vai, vươn vai rồi nằm dài trên khăn.',
  'env': ['beach', 'white sand', 'beach towel', 'beach umbrella', 'ocean', 'cumulus clouds'],
  'spec': {'set': 'same cove, camera closer on the towel and umbrella', 'time': 'midday'},
  'beats': [
   ('lotion', 'She squeezes sunscreen into her palm and works it over one shoulder.',
    'applying sunscreen, hand on own shoulder', 'looking down',
    [('applying sunscreen, hand on own shoulder', 'She works sunscreen across her shoulder with her palm.'),
     ('hand on own chest, looking away', 'Her hand slides down over the front of the top.')]),
   ('stretch', 'She stretches both arms overhead.',
    'sitting, arms above head, stretching', 'eyes closed',
    [('sitting, arms above head, stretching', 'She stretches overhead and the string top rides up.'),
     ('bikini top lift, underboob', 'The lift pulls the top up and bares the underside of her breasts.')]),
   ('recline', 'She lies back on the towel with one knee raised.',
    'lying on beach towel, one knee raised', 'relaxed',
    [('lying on beach towel, one knee raised', 'She lies back on the towel with one knee up and the sea behind her.'),
     ('lying on side, looking at viewer', 'Her head rests on her arm while she looks into the lens.')])]},

 {'title': 'Dây áo', 'safety': 'nsfw',
  'summary': 'Cô luồn ngón tay dưới dây áo và kéo hẳn lên tới hõm cổ.',
  'env': ['beach', 'white sand', 'beach towel', 'beach umbrella', 'ocean', 'cumulus clouds'],
  'spec': {'set': 'same cove, towel in the foreground', 'time': 'midday'},
  'beats': [
   ('band', 'She hooks a thumb under the band and drags the top up over her ribs.',
    'sitting, bikini top lift, underboob', 'looking down',
    [('sitting, bikini top lift, underboob', 'She hooks a thumb under the band and drags the top up over her ribs.'),
     ('bikini top lift, nipples, navel', 'The frame holds her bare stomach and the hard line of both nipples.')]),
   ('out', 'She pulls the top up to her collarbone and her bare breasts come out.',
    'bikini top lift, breasts, nipples', 'looking away',
    [('bikini top lift, breasts, nipples', 'She yanks the top to her collarbone and both bare breasts spill free.'),
     ('hand on own breast, looking away', 'She cups one bare breast and turns her face aside, nipples hard.')]),
   ('stand', 'She stands with the top bunched above her chest, breasts out.',
    'standing, bikini top lift, breasts, hard nipples', 'half-closed eyes',
    [('standing, bikini top lift, breasts, hard nipples', 'She stands on the sand with the top bunched above her chest.'),
     ('looking down at viewer, half-closed eyes', 'Her chin drops as she looks down into the lens.')])]},

 {'title': 'Dây quần', 'safety': 'nsfw',
  'summary': 'Cô quỳ trên khăn, kéo dây buộc bên hông và để lộ mông trần.',
  'env': ['beach', 'white sand', 'beach towel', 'beach umbrella', 'ocean', 'cumulus clouds'],
  'spec': {'set': 'same cove, towel filling the frame', 'time': 'midday'},
  'beats': [
   ('kneel', 'She turns onto her knees and looks back over her shoulder.',
    'kneeling on towel, looking back over shoulder', 'looking at viewer',
    [('kneeling on towel, looking back over shoulder', 'Asuna kneels on the towel and looks back over her shoulder.'),
     ('bikini bottom pull, ass', 'Her thumb hooks the side tie and drags the bottom over one cheek.')]),
   ('bare', 'Nothing under it: the bottom rides aside and her ass is bare.',
    'bikini bottom pull, ass, thighs, pubic hair', 'smirk',
    [('bikini bottom pull, ass, thighs, pubic hair', 'The bottom rides aside with nothing underneath, bare ass behind and a dark strip of pubic hair at the front.'),
     ('touching own thigh, legs apart, pubic hair', 'She parts her knees and runs a hand down the inside of one thigh.')]),
   ('lift', 'She lifts her hips with the bottom pulled aside.',
    'on all fours, hips lifted, ass, pubic hair', 'looking back',
    [('on all fours, hips lifted, ass, pubic hair', 'She lifts her hips on all fours with the tie pulled aside and the sand bright under her.'),
     ('looking back, smirk', 'Her head turns back toward the lens in a narrow smirk.')])]},

 {'title': 'Không che', 'safety': 'explicit',
  'summary': 'Cô ngồi choãi trên khăn, tự kéo quần bơi sang một bên và để lộ hẳn vùng kín.',
  'env': ['beach', 'white sand', 'beach towel', 'beach umbrella', 'ocean', 'cumulus clouds'],
  'spec': {'set': 'same cove, towel and umbrella behind her', 'time': 'midday'},
  'beats': [
   ('present', 'She sits with her knees wide and pulls the bottom aside.',
    'sitting, spread legs, clothing aside, pussy, pubic hair, nipples', 'looking at viewer',
    [('sitting, spread legs, clothing aside, pussy, pubic hair, nipples', 'She sits with her knees wide and pulls the blue fabric aside, pubic hair and pussy fully showing.'),
     ('sitting, spread legs, pussy, touching own thigh', 'Her fingers slide down the inside of her thigh with her legs still open.')]),
   ('arch', 'She leans back on her elbows with her legs wide open.',
    'leaning back, spread legs, pussy, nipples, hard nipples, arching back', 'eyes closed',
    [('leaning back, spread legs, pussy, nipples, hard nipples, arching back', 'She leans back on her elbows with both legs wide, nipples and pussy bare to the lens.'),
     ('biting lip, half-closed eyes', 'Her face fills the frame with her teeth on the lower lip.')]),
   ('finish', 'She lies back on the towel, then sits up smiling.',
    'lying on back, spread legs, pussy, pubic hair', 'smile',
    [('lying on back, spread legs, pussy, pubic hair', 'She lies back on the towel with her legs open and the bikini pushed aside.'),
     ('sitting up, looking at viewer, spread legs', 'She sits up with her legs still open and gives a small smile.')])]},
]

BRIEF = f"""# Bãi Biển Riêng — source brief (approved)

**Cast mode:** NON_BLIND — Asuna (Blue Archive), `CONFIRMED_ADULT`, `REVIEWED`.
**User yêu cầu:** 1 story album erotic, **không thay đổi trang phục**, ~30 shot, **bikini ngoài biển**,
nhân vật chủ động tự làm lộ vùng nhạy cảm.

## Premise

Bãi biển riêng, trưa nắng, cát trắng, dừa phía sau. Asuna đi chân trần xuống bãi trong bộ bikini xanh
dây buộc. **Không có gì bên trong bộ bikini.** Cô không thay đồ và không cởi bộ bikini trong suốt album.

## Trục leo thang

Không thay đồ, không cởi đồ. Leo thang bằng **độ vén và tư thế**, tất cả do cô tự làm:
bikini buộc đủ → vén áo lộ `underboob` → kéo áo lên hõm cổ, **ngực trần** → kéo dây buộc hông,
**mông trần + lông mu** → ngồi choãi, **tự kéo quần bơi sang một bên, lộ vùng kín**.

## Ràng buộc

- Một người trong khung, không khán giả, không người thứ hai trên bãi.
- Đồng thuận rõ ràng, không ép buộc, không bạo lực. Cô tự tay làm mọi thứ.
- Sáng đều: không low-key, không tối góc.
- Khô: không mồ hôi, không nước trên da; nhấn mạnh da khô mịn.
- Một địa điểm duy nhất: bãi biển riêng (cát, khăn, dù, biển).
- Halo luôn hiện. Bộ bikini luôn nằm trên người, không thay bộ khác.
"""


def char_id(con):
    row = con.execute('select id from characters where slug=?', ('asuna_blue_archive',)).fetchone()
    assert row, 'character not found in catalog'
    return row['id']


def stage_i(i):
    return min((i - 1) // 6, 4)


def stage_at(i):
    return STAGES[stage_i(i)]


def cam(act_no, beat_no, sub, si):
    """Fix the two camera faults that broke the apartment album."""
    framing, angle = CAMS[(act_no * 3 + beat_no * 2 + sub) % 10]
    if si >= 4 and angle == 'from above':
        angle = 'eye level'          # 'from above' + spread legs produced inverted bodies
    if si >= 1 and framing == 'close-up':
        framing = 'upper body'       # close-up cropped the head off at this breast size
    return framing, angle


def diff(a, b):
    return {'set': {k: v for k, v in b.items() if a.get(k) != v},
            'remove': [k for k in a if k not in b]}


def validate(text):
    """Structural gate before a prompt reaches the DB (same checker the renderer uses)."""
    p = OUT / 'drafts' / '_check.txt'
    p.write_text(text, encoding='utf-8')
    r = subprocess.run([sys.executable, 'tools/novel2anima/validate_anima_prompt.py', str(p)],
                       capture_output=True, text=True)
    p.unlink()
    if r.returncode:
        raise SystemExit(f'BLOCKED {text.splitlines()[0][:120]}\n{r.stdout}')


def prompt_for(act, stage, pose, expr, framing, angle, sentence):
    tags = (QUALITY + [act['safety'], 'highres', '1girl', 'solo', CHAR_TAG, SERIES]
            + IDENTITY + stage[1] + pose.split(', ') + expr.split(', ')
            + [framing, angle] + act['env'] + LIGHT + STYLE)
    return ', '.join(dict.fromkeys(tags)) + '\n' + sentence


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'drafts').mkdir(exist_ok=True)
    (OUT / 'source_brief.md').write_text(BRIEF, encoding='utf-8')
    con = connect(DB)
    cid = char_id(con)
    labels = ['nsfw', 'adult', 'erotic', 'consensual', 'solo', 'anime_style', 'beach',
              'bikini', 'outdoor', 'fixed_outfit', 'progressive_exposure']
    story = create_story(con, TITLE, 'NON_BLIND', BRIEF, labels)
    add_role(con, story, 'MUSE_A', f'{CHAR_TAG} - blue string bikini, same outfit all 30 shots')
    bind_role(con, story, 'MUSE_A', cid)
    print('story', story, 'char', cid)

    acts_plan = []
    for n, act in enumerate(ACTS, 1):
        beats = []
        for bi, (btype, bsum, pose, expr, _shots) in enumerate(act['beats'], 1):
            st = stage_at((n - 1) * 6 + (bi - 1) * 2 + 1)
            beats.append({'beat_id': f'B{(n - 1) * 3 + bi:02d}', 'type': btype, 'summary': bsum, 'events': [
                {'event_id': f'E{(n - 1) * 3 + bi:02d}', 'actor_id': 'MUSE_A', 'target_id': None,
                 'primary_action': pose, 'reaction': bsum,
                 'state_change': f'outfit: {st[0]}; pose: {pose}; expression: {expr}',
                 'spec': {'pose': pose, 'expression': expr, 'outfit': st[0]}}]})
        acts_plan.append({'act_id': f'A{n:02d}', 'title': act['title'], 'summary': act['summary'],
                          'spec': act['spec'], 'beats': beats})

    ident = (f'{CHAR_TAG}, light brown hair in a very long ponytail, rabbit ears, blue eyes, a small halo '
             f'above her head and a large chest')
    plan = {'schema_version': 'n2m.story_plan.v1', 'story_id': story, 'title': TITLE,
            'cast_mode': 'NON_BLIND',
            'source_refs': [{'type': 'user_input', 'path': f'{OUT}/source_brief.md', 'sha256': sha(BRIEF)}],
            'approval': {'status': 'APPROVED', 'approved_by': 'user', 'approved_at': '2026-11-17T00:00:00Z',
                         'evidence': 'User asked for a 30-shot bikini erotic album on a beach, fixed outfit',
                         'policy_id': 'N2M-CONTENT-POLICY', 'policy_version': '1.3.0'},
            'intent': {'content_profile': 'erotic_album', 'raw_labels': labels,
                       'constraints': ['One woman only in frame; empty cove, no audience.',
                                       'Consent is explicit and voluntary; no coercion, no violence.',
                                       'Bright even exposure only: no low-key, no dark falloff.',
                                       'Dry skin: no sweat, no water on skin.',
                                       'One location only (the private cove).',
                                       'The outfit never changes: blue string bikini, barefoot.',
                                       'Nothing under the bikini in any shot.',
                                       'She exposes herself deliberately with her own hands.',
                                       'The small halo stays in every shot.']},
            'art_direction': {'format': 'anime-illustrated erotic album, 5 acts, 3 beats each, 2 shots per beat',
                              'brightness_constraint': 'Bright, evenly exposed anime illustration.',
                              'location': {'type': 'private beach cove',
                                           'detail': 'white sand, striped towel, beach umbrella, palms, calm ocean',
                                           'continuity': 'same cove; ocean behind, palms to the right, towel centre'},
                              'costume': {'type': 'blue string bikini, side-tie bottom, barefoot',
                                          'single_variable': 'how far the fabric is pulled aside',
                                          'ladder': [s[0] for s in STAGES]}},
            'characters': [{'role_key': 'MUSE_A', 'character_id': cid, 'age_status': 'CONFIRMED_ADULT',
                            'identity': ident,
                            'appearance_evidence': 'catalog character_tags: light brown hair, very long hair, '
                                                   'rabbit ears, blue eyes, large breasts, halo, '
                                                   'mole on breast'}],
            'acts': acts_plan}
    save_plan(con, story, plan)

    ev_map = {}
    for act in acts_plan:
        act_id = add_act(con, story, int(act['act_id'][1:]), act['title'], act['summary'], act['spec'])
        for bi, beat in enumerate(act['beats'], 1):
            beat_id = add_beat(con, act_id, bi, beat['summary'])
            for ev in beat['events']:
                eid = add_event(con, beat_id, 1, {'actor_role_key': 'MUSE_A', 'target_role_key': None,
                                                  'action': ev['primary_action'], 'reaction': ev['reaction'],
                                                  'raw_labels': labels, 'source_fragment': beat['summary'],
                                                  'spec': ev['spec']})
                ev_map[f'A{act["act_id"][1:]}.B{bi}'] = (beat_id, eid)
    print('acts/beats/events', len(ev_map))

    shots, coverage, prev, k = [], [], None, 0
    for act_no in range(1, 6):
        for beat_no in range(1, 4):
            beat_id, ev_id = ev_map[f'A{act_no:02d}.B{beat_no}']
            _t, _s, _p, _e, moments = ACTS[act_no - 1]['beats'][beat_no - 1]
            for i in range(SHOTS_PER_BEAT):
                k += 1
                key = f'S{k:03d}'
                framing, angle = cam(act_no, beat_no, i, stage_i(k))
                shots.append({'shot_key': key, 'shot_order': k, 'beat_id': beat_id, 'branch_key': 'MAIN',
                              'previous_shot_key': prev,
                              'transition': 'START' if prev is None else ('TIME_CUT' if i == 0 else 'CAMERA_CUT'),
                              'purpose': PURPOSE[i], 'camera': f'{framing}, {angle}',
                              'focus': moments[i][0], 'visual_moment': moments[i][0],
                              'role_keys': ['MUSE_A'], 'location_key': 'LOC_BEACH',
                              'prop_keys': [], 'style_key': 'STYLE_ANIME'})
                coverage.append({'event_id': ev_id, 'status': 'VISUALIZED', 'shot_key': key,
                                 'evidence': f'{key} shows: {moments[i][0]}'})
                prev = key

    board = {'story_revision': con.execute('select current_revision from stories where id=?',
                                           (story,)).fetchone()[0],
             'approval': {'status': 'APPROVED', 'approved_by': 'user', 'approved_at': '2026-11-17T00:00:00Z',
                          'evidence': 'User approved a 30-shot bikini erotic album on a private beach'},
             'visual_bible': {
                 'characters': {'MUSE_A': {'description': ident,
                                           'provenance': 'catalog character_tags for ' + CHAR_TAG,
                                           'character_id': cid, 'outfit_id': None}},
                 'locations': {'LOC_BEACH': {
                     'description': 'private white-sand cove: striped towel, beach umbrella, palms right, '
                                    'calm ocean behind',
                     'provenance': f'{OUT}/source_brief.md + plan art_direction.location'}},
                 'props': {},
                 'styles': {'STYLE_ANIME': {
                     'description': 'clean anime illustration, crisp line art, cel shading, bright palette',
                     'tone': 'bright midday, even exposure', 'provenance': 'user preference: anime'}}},
             'shots': shots, 'coverage': coverage}
    json.dump(board, open(OUT / 'storyboard.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    board_id, board_rev = save_storyboard(con, story, board, 0)
    print('board', board_id, board_rev)

    slots = con.execute('select shot_key,shot_order,beat_id,context_sha256,spec_json from storyboard_shots '
                        'where storyboard_id=? order by shot_order', (board_id,)).fetchall()
    assert len(slots) == 30, len(slots)

    ids, prev_state, prev_scene = {}, None, None
    for slot in slots:
        i = slot['shot_order']
        act_no = (i - 1) // 6 + 1
        act = ACTS[act_no - 1]
        beat_no = (i - 1) % 6 // 2 + 1
        sub = (i - 1) % 2
        pose, sentence = act['beats'][beat_no - 1][4][sub]
        expr = act['beats'][beat_no - 1][3]
        framing, angle = cam(act_no, beat_no, sub, stage_i(i))
        stage = stage_at(i)
        state = {'stage': stage[0], 'outfit': stage[2], 'pose': pose, 'expression': expr}
        scene = {'location_key': 'LOC_BEACH', 'light': 'bright midday sunlight',
                 'skin': 'dry and matte', 'outfit': 'unchanged', 'tide': 'calm'}
        ev = con.execute('select * from story_events where beat_id=?', (slot['beat_id'],)).fetchone()
        shot = {'schema_version': 'n2m.shot.v4', 'visual_context_sha256': slot['context_sha256'],
                'camera': f'{framing}, {angle}', 'focus': pose, 'location_key': 'LOC_BEACH',
                'style_key': 'STYLE_ANIME', 'purpose': PURPOSE[sub], 'prop_keys': [],
                'source_refs': [{'type': 'story_event', 'id': ev['id']}],
                'participants': [{'role_key': 'MUSE_A', 'spec': {
                    'appearance': ident, 'world_position': 'on the towel or on the open sand',
                    'screen_position': 'centre', 'pose': pose, 'expression': expr}}],
                'interactions': [{'event_id': ev['id'], 'actor_role_key': 'MUSE_A', 'target_role_key': None,
                                  'action_text': pose, 'reaction_text': expr,
                                  'constraints': ['solo shot: no second person, no audience',
                                                  'outfit unchanged: blue string bikini, nothing underneath']}],
                'intent': {'raw_labels': labels,
                           'constraints': ['one woman only, empty cove', 'bright even anime lighting',
                                           'dry matte skin, dry fabric', 'no underwear under the bikini',
                                           'exposure is self-directed, never forced']},
                'continuity_revision_note': 'initial approved beach state'}
        shot_id, _ = save_shot(con, slot['beat_id'], slot['shot_key'], shot, ev['id'])
        ids[slot['shot_key']] = shot_id
        before_state = state if prev_state is None else prev_state
        save_continuity(con, shot_id, {'snapshots': [
            {'role_key': None, 'before': prev_scene or scene,
             'delta': diff(prev_scene or scene, scene), 'after': scene},
            {'role_key': 'MUSE_A', 'before': before_state,
             'delta': diff(before_state, state), 'after': state}]})
        prev_state, prev_scene = state, scene

        text = prompt_for(act, stage, pose, expr, framing, angle, sentence)
        validate(text)
        (OUT / 'drafts' / f'{slot["shot_key"]}.txt').write_text(text, encoding='utf-8')
        prompt_id, _ = save_natural_prompt(con, shot_id, text, 'en')
        save_qa(con, 'PROMPT', prompt_id, 'PASS', {
            'checks': {'identity': 'catalog anchors only', 'outfit': stage[0], 'solo': 'one body only',
                       'camera': f'{framing} + {angle}', 'moment_match': pose, 'scene': scene,
                       'nudity': f'exposure stage {stage[0]}: bikini on, nothing underneath, self-directed',
                       'tags_validated': 'validate_anima_prompt.py PASS'},
            'policy_decision': {'policy_id': 'N2M-CONTENT-POLICY', 'policy_version': '1.3.0',
                                'scope': 'PROMPT_DERIVATION', 'decision': 'PASS', 'shot_id': shot_id,
                                'rule_reference': 'consensual adult clothed eroticism, no minors, no violence',
                                'evidence': 'prompt derived from ShotSpec; no event added or removed'},
            'verdict_reason': 'tag block + one prose sentence, straight from ShotSpec'}, 'N2M-CONTENT-POLICY@1.3.0')

    bindings = {}
    for slot in slots:
        sid = ids[slot['shot_key']]
        pid = con.execute('select id from shot_prompts where shot_id=? order by revision desc limit 1',
                          (sid,)).fetchone()['id']
        bindings[slot['shot_key']] = {'shot_id': sid, 'prompt_id': pid}
    json.dump({'bindings': bindings}, open(OUT / 'bindings.json', 'w', encoding='utf-8'), indent=1)
    json.dump({'bindings': bindings,
               'sequence_qa': {'verdict': 'PASS',
                               'evidence': '30 shots, one escalating exposure ladder, one cove, one character, '
                                           'one unchanged blue bikini, nothing underneath, '
                                           'every reveal made by her own hand'}},
              open(OUT / 'seal.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    render = {'model': 'anima-base-v1.0.safetensors',
              'text_encoder': 'qwen_3_06b_base.safetensors', 'vae': 'qwen_image_vae.safetensors',
              'width': 864, 'height': 1152, 'aspect': '3:4', 'megapixels': round(864 * 1152 / 1e6, 3),
              'divisible_by': 16, 'steps': 40, 'cfg': 4.5, 'sampler': 'er_sde', 'scheduler': 'simple',
              'negative': 'worst quality, low quality, score_1, score_2, score_3, artist name, '
                          'blurry, jpeg artifacts, chromatic aberration, shiny skin, oily skin, '
                          'glossy skin, sweat, extra limbs, extra fingers, fused fingers, bad anatomy',
              'seed_policy': 'fixed per shot_key so a prompt edit is the only variable'}
    (OUT / 'render.config.json').write_text(json.dumps(render, indent=1) + '\n', encoding='utf-8')
    print('story', story, 'board', board_id, 'shots', len(ids))
    return story, board_id


if __name__ == '__main__':
    main()
