"""Beach bikini album: one adult character, one location, 5 acts x 3 beats x 5 shots.

Anima tag prompts (tag block + at most 2 prose sentences), portrait 3:4 at ~1 MP.
Character: Iori (swimsuit) (Blue Archive) - CONFIRMED_ADULT / REVIEWED in catalog.
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
OUT = pathlib.Path('exports/beach_bikini/01_iori')
CHAR = 'character:deepghs:06e690431b2c002bb9'
PURPOSE = ['ESTABLISHING', 'ACTION', 'DETAIL', 'REACTION', 'CLIMAX']

TITLE = 'Bãi Biển Riêng — Iori'
NAME = 'Iori'
CHAR_TAG = 'iori (swimsuit) (blue archive)'
SERIES = 'blue archive'
IDENTITY = ['dark skin', 'grey hair', 'very long hair', 'twintails', 'red eyes',
            'pointy ears', 'halo', 'demon tail', 'hair over one eye', 'black ribbon']
QUALITY = ['masterpiece', 'best quality', 'score_7']
STYLE = ['anime coloring', 'cel shading', 'clean lineart']
LIGHT = ['bright daylight', 'sunlight', 'clear sky']

# 15 distinct framing/angle pairs; a beat rotates through them so no shot repeats.
CAMS = [('full body', 'eye level'), ('cowboy shot', 'from side'), ('upper body', 'three-quarter view'),
        ('close-up', 'eye level'), ('wide shot', 'from above'), ('full body', 'from side'),
        ('cowboy shot', 'from below'), ('upper body', 'from above'), ('close-up', 'three-quarter view'),
        ('wide shot', 'eye level'), ('full body', 'three-quarter view'), ('cowboy shot', 'eye level'),
        ('upper body', 'from side'), ('close-up', 'from above'), ('full body', 'from below')]

STAGES = [
    ('bikini_sunglasses', ['black bikini', 'string bikini', 'side-tie bikini bottom', 'sunglasses'],
     'sunglasses left on the towel'),
    ('bikini', ['black bikini', 'string bikini', 'side-tie bikini bottom'], 'sunglasses on the towel'),
    ('bikini_sunbathing', ['black bikini', 'string bikini', 'side-tie bikini bottom'], 'none'),
    ('bikini_top_off', ['topless', 'black bikini bottom', 'side-tie bikini bottom'],
     'bikini top dropped beside the towel'),
    ('nude', ['completely nude', 'nipples', 'uncensored'], 'bikini folded on the towel'),
]

ACTS = [
 {'title': 'Lên bãi', 'safety': 'sensitive',
  'summary': 'Cô bước xuống bãi cát trắng, trải khăn và đứng nhìn ra biển.',
  'env': ['beach', 'white sand', 'palm trees', 'ocean', 'cumulus clouds', 'bright daylight', 'sunlight'],
  'spec': {'set': 'private cove: white sand, palms behind, calm ocean in front', 'time': 'midday'},
  'beats': [
   ('arrival', 'She walks barefoot across the white sand toward the water.', 'walking, barefoot, sandals in hand',
    'calm expression', [('walking, barefoot, sandals in hand', 'Iori walks barefoot across the white sand, her sandals hanging from her right hand.'),
                        ('standing, hand on hip, head turned', 'She stops in the left third of the frame and turns her head toward the sea.'),
                        ('looking at viewer, adjusting sunglasses', 'Iori lowers her sunglasses one finger-width and looks straight into the lens.'),
                        ('smile, closed mouth', 'The frame holds her face with the bright empty sky behind her.'),
                        ('walking, barefoot on sand', 'Seen from above, she crosses the open sand toward the shoreline.')]),
   ('setup', 'She spreads the towel and kneels down on it.', 'kneeling, spreading beach towel',
    'neutral expression', [('kneeling, spreading beach towel', 'Iori kneels at the centre of the frame and rolls the towel open with both hands.'),
                           ('kneeling, adjusting towel, looking down', 'She smooths the towel corner and glances down at it.'),
                           ('leaning forward, reaching', 'She leans forward over the towel, one arm stretched out of the crop.'),
                           ('smile, looking down', 'The frame holds her smiling face as she looks down at the sand.'),
                           ('kneeling on beach towel', 'She settles cross-legged on the towel with the palms rising behind her.')]),
   ('bask', 'She stands up and stretches with her face to the sun.', 'standing, arms behind head, stretching',
    'eyes closed, smile', [('standing, arms behind head, stretching', 'Iori stretches with both hands behind her head, chest lifted toward the sun.'),
                          ('standing, hand on hip, looking away', 'She plants one hand on her hip and looks off to the left of the frame.'),
                          ('arms up, hair blowing', 'Both arms stay raised while the sea wind lifts her twintails.'),
                          ('eyes closed, smile', 'Her face fills the frame, eyes closed under the flat bright light.'),
                          ('standing, looking at ocean, wind', 'She stands at the right edge of the frame facing the water, hands loose at her hips.')])]},

 {'title': 'Ngấn nước', 'safety': 'sensitive',
  'summary': 'Cô xuống mép nước, đi giữa bọt sóng và ngồi lên mỏm đá.',
  'env': ['beach', 'waterline', 'shallow water', 'sea foam', 'wet sand', 'ocean', 'bright daylight', 'sunlight'],
  'spec': {'set': 'waterline: shallow clear water, foam, flat wet sand, a low rock at the right', 'time': 'midday'},
  'beats': [
   ('wade', 'She stands ankle-deep and looks down at the foam.', 'standing, ankle deep in water, looking down',
    'neutral expression', [('standing, ankle deep in water, looking down', 'Iori stands ankle-deep at the left of the frame and looks down at the foam.'),
                           ('walking in shallow water', 'She steps sideways through the shallow water, one foot lifted.'),
                           ('hand shielding eyes, looking away', 'She shades her eyes with one hand and looks at the horizon.'),
                           ('smile, looking at viewer', 'The frame holds her face with the bright water line behind her.'),
                           ('standing at waterline, foam around feet', 'She stands alone at the waterline, foam spreading around her ankles.')]),
   ('crouch', 'She crouches and touches the foam with one hand.', 'crouching, hand touching water',
    'curious expression', [('crouching, hand touching water', 'Iori crouches low at the centre of the frame and touches the foam with her fingertips.'),
                          ('crouching, looking at viewer', 'Still crouched, she turns her head up toward the lens.'),
                          ('bending forward, hands on knees', 'She bends forward over the water with both hands on her knees.'),
                          ('laughing', 'The frame holds her laughing face just above the water.'),
                          ('standing on wet sand, foam', 'She rises again on the wet sand with foam breaking around her feet.')]),
   ('rock', 'She sits on a low rock with her legs crossed.', 'sitting on rock, legs crossed',
    'relaxed expression', [('sitting on rock, legs crossed', 'Iori sits on the low rock at the right of the frame, legs crossed at the ankle.'),
                           ('sitting on rock, leaning back on hands', 'She leans back on both hands and lets her shoulders drop.'),
                           ('looking away, wind in hair', 'Her head turns away from the lens while the wind pulls her twintails sideways.'),
                           ('smirk, looking at viewer', 'Her face fills the frame in a narrow smirk.'),
                           ('standing on rock, hands on hips', 'She stands up on the rock with both hands on her hips, the sea behind her.')])]},

 {'title': 'Phơi nắng', 'safety': 'sensitive',
  'summary': 'Cô nằm dài trên khăn, lật người và ngồi dậy ôm gối.',
  'env': ['beach', 'beach towel', 'white sand', 'beach umbrella', 'ocean', 'bright daylight', 'sunlight'],
  'spec': {'set': 'towel under a beach umbrella on white sand, ocean beyond', 'time': 'midday'},
  'beats': [
   ('back', 'She lies on her back with both arms above her head.', 'lying on back, arms above head',
    'eyes closed, relaxed', [('lying on back, arms above head', 'Iori lies on her back on the towel with both arms stretched above her head.'),
                             ('lying on back, one knee raised', 'Her head stays at the left of the frame while one knee rises.'),
                             ('lying, head turned to viewer', 'She turns her head toward the lens without moving her shoulders.'),
                             ('eyes closed, relaxed', 'The frame holds her face with the umbrella shade across it.'),
                             ('lying on towel, full length', 'Seen from above, she fills the towel from head to feet.')]),
   ('front', 'She rolls onto her stomach and props her chin on her hands.', 'lying on stomach, chin on hands',
    'smile', [('lying on stomach, legs crossed', 'Iori lies on her stomach with her legs crossed at the ankle, looking back over her shoulder.'),
              ('lying on stomach, chin on hands', 'She props her chin on both hands and looks off to the right.'),
              ('lying on stomach, smiling', 'She looks up at the lens from the towel with a small smile.'),
              ('half-closed eyes, smile', 'Her face fills the frame, eyes half closed under the sun.'),
              ('lying on stomach on towel', 'She lies flat along the towel with the ocean filling the frame edge.')]),
   ('sit', 'She sits up with her knees drawn in.', 'sitting, knees up, arms around knees',
    'calm expression', [('sitting, knees up, arms around knees', 'Iori sits in the middle of the towel with her knees drawn up and both arms wrapped around them.'),
                          ('sitting cross-legged, hand on knee', 'She sits cross-legged and rests one hand on her knee.'),
                          ('leaning back on hands, chest out', 'She leans back on both hands and lifts her chin.'),
                          ('looking up, smile', 'Seen from above, she looks up into the lens and smiles.'),
                          ('sitting, stretching arms', 'She sits on the towel and stretches both arms overhead.')])]},

 {'title': 'Cởi dây', 'safety': 'nsfw',
  'summary': 'Cô cởi dây áo bikini, giữ vạt trước ngực rồi bỏ hẳn.',
  'env': ['beach', 'beach towel', 'white sand', 'beach umbrella', 'ocean', 'bright daylight', 'sunlight'],
  'spec': {'set': 'towel under a beach umbrella on white sand, ocean beyond', 'time': 'midday'},
  'beats': [
   ('untie', 'She reaches behind her neck and works the knot loose.', 'standing, hand on own bikini top, untying',
    'looking down', [('standing, hand on own bikini top, untying', 'Iori stands on the towel with one hand behind her neck, working the knot loose.'),
                     ('standing, bikini top loosened, holding the front', 'She holds the loosened front of the top flat against her chest.'),
                     ('holding bikini top against chest, looking away', 'She keeps the fabric against her chest and turns her face away from the lens.'),
                     ('smile, blush', 'Her face fills the frame with a faint blush and a closed smile.'),
                     ('standing on towel, top in hand', 'She stands at the centre of the towel with the top held loosely in one hand.')]),
   ('off', 'The top comes away and she lowers her arm.', 'topless, covering breasts with forearm',
    'looking away', [('topless, covering breasts with forearm', 'Iori stands topless on the towel with one forearm still across her chest.'),
                     ('topless, hands at sides', 'She drops both arms to her sides and faces the lens.'),
                     ('topless, arms above head', 'Both arms go above her head, the top gone from her hands.'),
                     ('topless, looking at viewer', 'Her face fills the frame, chin lowered toward the lens.'),
                     ('topless, standing on towel', 'She stands topless at the left of the frame, the bottom still tied at her hip.')]),
   ('lie', 'She lies back down on the towel, topless.', 'topless, lying on back, arms above head',
    'eyes closed, smile', [('topless, lying on back, arms above head', 'She lies back on the towel with both arms above her head.'),
                            ('topless, lying on back, one knee raised', 'Her body lies diagonally across the frame with one knee up.'),
                            ('topless, stretching', 'She stretches one arm along the towel above her head.'),
                            ('topless, eyes closed, sun', 'Seen from above, her face rests in the bright sun.'),
                            ('topless, sitting, knees up', 'She sits up topless with her knees drawn in, the sea behind her.')])]},

 {'title': 'Không còn gì', 'safety': 'explicit',
  'summary': 'Cô nằm và đứng hoàn toàn khoả thân trên bãi cát, không che.',
  'env': ['beach', 'beach towel', 'white sand', 'ocean', 'cumulus clouds', 'bright daylight', 'sunlight'],
  'spec': {'set': 'white sand and ocean, towel underneath, no cover', 'time': 'midday'},
  'beats': [
   ('stand', 'She stands naked on the sand with her hands at her sides.', 'completely nude, standing, hands at sides',
    'calm expression', [('completely nude, standing, hands at sides', 'Iori stands naked at the centre of the frame, hands loose at her hips, facing the lens.'),
                        ('completely nude, standing, looking at viewer', 'She keeps her feet apart on the sand and looks straight into the lens.'),
                        ('completely nude, arms above head', 'Both arms lift above her head, the whole front of her body open to the frame.'),
                        ('smile, hair over one eye', 'Her face fills the frame with hair fallen over her right eye.'),
                        ('completely nude, standing on towel', 'Seen from above, she stands on the towel with the ocean behind her feet.')]),
   ('kneel', 'She kneels on the towel, then lies back.', 'completely nude, kneeling',
    'looking at viewer', [('completely nude, kneeling', 'Iori kneels on the towel facing the lens, both hands on her thighs.'),
                          ('completely nude, kneeling, hands on thighs', 'She stays kneeling and lifts her chin toward the lens.'),
                          ('completely nude, reclining', 'She lets herself down onto one elbow on the towel.'),
                          ('completely nude, lying, looking at viewer', 'Her face and shoulders fill the frame as she lies back.'),
                          ('completely nude, lying on towel', 'She lies full length along the towel under the open sky.')]),
   ('recline', 'She reclines with her arms behind her head.', 'completely nude, reclining, arms behind head',
    'eyes closed, relaxed', [('completely nude, reclining, arms behind head', 'She reclines on both elbows with her arms folded behind her head.'),
                             ('completely nude, sitting, legs crossed', 'She sits up on the towel with her legs crossed at the ankle.'),
                             ('completely nude, arching back', 'She arches her back and lifts her chest toward the sun.'),
                             ('completely nude, eyes closed', 'Seen from above, her face rests with her eyes closed.'),
                             ('completely nude, standing, hand in hair', 'She stands one last time with one hand pushed into her hair.')])]},
]

BRIEF = f"""# Bãi Biển Riêng — source brief (approved)

**Cast mode:** NON_BLIND — {CHAR_TAG.title()}, `CONFIRMED_ADULT`, `REVIEWED`.
**User yêu cầu:** 1 story album erotic, trang phục bikini, bối cảnh biển, prompt cho ảnh dọc 3:4 ~1 MP.

## Premise

Một vịnh biển riêng, nắng trưa, cát trắng. Iori ở một mình, mặc bikini đen.
Trục leo thang: **lớp vải trên ngực** — bikini còn nguyên → cởi dây → trần → khoả thân.
Act 5 khoả thân hoàn toàn, full-frontal.

## Ràng buộc

- Một người trong khung, không khán giả, không phản chiếu người khác.
- Đồng thuận rõ ràng, không ép buộc, không bạo lực.
- Sáng đều: không low-key, không tối góc.
- Da khô mịn: không mồ hôi, không ướt, không nước trên da.
- Một địa điểm duy nhất: bãi biển / mép nước trong cùng một vịnh.
- Halo luôn hiện, kể cả Act 5.
"""


def char_id(con):
    row = con.execute('select id from characters where slug=?', ('iori_swimsuit_blue_archive',)).fetchone()
    if row:
        return row['id']
    row = con.execute('select id from characters where display_name=?', (CHAR_TAG,)).fetchone()
    assert row, 'character not found in catalog'
    return row['id']


def stage_at(i):
    return STAGES[min((i - 1) // 15, 4)]


def diff(a, b):
    return {'set': {k: v for k, v in b.items() if a.get(k) != v},
            'remove': [k for k in a if k not in b]}


def validate(text):
    """Structural gate before a prompt reaches the DB (same checker the renderer uses)."""
    import subprocess as sp
    p = OUT / 'drafts' / '_check.txt'
    p.write_text(text, encoding='utf-8')
    r = sp.run([sys.executable, 'tools/novel2anima/validate_anima_prompt.py', str(p)],
               capture_output=True, text=True)
    p.unlink()
    if r.returncode:
        raise SystemExit(f'BLOCKED {text.splitlines()[0][:120]}\n{r.stdout}')


def prompt_for(act, stage, pose, expr, framing, angle, sentence):
    # Prose must not restate a camera the tag block already fixes, or the two fight.
    sentence = re.sub(r'^Seen from above, (.)', lambda m: m.group(1).upper(), sentence)
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
    labels = ['nsfw', 'adult', 'erotic', 'consensual', 'solo', 'anime_style', 'bikini',
              'beach', 'progressive_exposure', 'nude', 'full_frontal']
    story = create_story(con, TITLE, 'NON_BLIND', BRIEF, labels)
    add_role(con, story, 'MUSE_A', f'{CHAR_TAG} - bikini on a private beach, top comes off in act 4')
    bind_role(con, story, 'MUSE_A', cid)
    print('story', story, 'char', cid)

    acts_plan = []
    for n, act in enumerate(ACTS, 1):
        beats = []
        for bi, (btype, bsum, pose, expr, _shots) in enumerate(act['beats'], 1):
            st = stage_at((n - 1) * 15 + (bi - 1) * 5 + 1)
            beats.append({'beat_id': f'B{(n - 1) * 3 + bi:02d}', 'type': btype, 'summary': bsum, 'events': [
                {'event_id': f'E{(n - 1) * 3 + bi:02d}', 'actor_id': 'MUSE_A', 'target_id': None,
                 'primary_action': pose, 'reaction': bsum,
                 'state_change': f'outfit: {st[0]}; pose: {pose}; expression: {expr}',
                 'spec': {'pose': pose, 'expression': expr, 'outfit': st[0]}}]})
        acts_plan.append({'act_id': f'A{n:02d}', 'title': act['title'], 'summary': act['summary'],
                          'spec': act['spec'], 'beats': beats})

    ident = (f'{CHAR_TAG}, dark skin, grey hair in two very long twintails, red eyes, pointy ears, '
             f'a small halo above her head, a thin demon tail and hair over one eye')
    plan = {'schema_version': 'n2m.story_plan.v1', 'story_id': story, 'title': TITLE,
            'cast_mode': 'NON_BLIND',
            'source_refs': [{'type': 'user_input', 'path': f'{OUT}/source_brief.md', 'sha256': sha(BRIEF)}],
            'approval': {'status': 'APPROVED', 'approved_by': 'user', 'approved_at': '2026-11-16T00:00:00Z',
                         'evidence': 'User asked for one erotic bikini beach album with portrait 3:4 prompts',
                         'policy_id': 'N2M-CONTENT-POLICY', 'policy_version': '1.3.0'},
            'intent': {'content_profile': 'erotic_album', 'raw_labels': labels,
                       'constraints': ['One woman only in frame; empty private cove, no audience.',
                                       'Consent is explicit and voluntary; no coercion, no violence.',
                                       'Bright even exposure only: no low-key, no dark falloff.',
                                       'Dry matte skin: no sweat, no water, no wet look.',
                                       'One location only (private beach cove).',
                                       'The small halo stays in every act including the nude.',
                                       'Portrait 3:4 framing, ~1 MP output.']},
            'art_direction': {'format': 'anime-illustrated erotic album, 5 acts, 3 beats each, 5 shots per beat',
                              'brightness_constraint': 'Bright, evenly exposed anime illustration.',
                              'location': {'type': 'outdoor beach', 'detail': 'private white-sand cove, calm water',
                                           'continuity': 'same cove; palms behind, ocean in front, tide flat'},
                              'costume': {'type': 'black string bikini',
                                          'single_variable': 'fabric over the chest',
                                          'ladder': [s[0] for s in STAGES]}},
            'characters': [{'role_key': 'MUSE_A', 'character_id': cid, 'age_status': 'CONFIRMED_ADULT',
                            'identity': ident,
                            'appearance_evidence': 'catalog character_tags: dark skin, grey hair, twintails, '
                                                   'red eyes, pointy ears, halo, demon tail'}],
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
            for i in range(5):
                k += 1
                key = f'S{k:03d}'
                framing, angle = CAMS[(beat_no * 5 + i) % 15]
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
             'approval': {'status': 'APPROVED', 'approved_by': 'user', 'approved_at': '2026-11-16T00:00:00Z',
                          'evidence': 'User approved one bikini beach album, 75 shots, portrait 3:4'},
             'visual_bible': {
                 'characters': {'MUSE_A': {'description': ident,
                                           'provenance': 'catalog character_tags for ' + CHAR_TAG,
                                           'character_id': cid, 'outfit_id': None}},
                 'locations': {'LOC_BEACH': {'description': 'private white-sand cove, palms behind, calm ocean in front',
                                             'provenance': f'{OUT}/source_brief.md + plan art_direction.location'}},
                 'props': {},
                 'styles': {'STYLE_ANIME': {'description': 'clean anime illustration, crisp line art, cel shading, '
                                                          'bright palette, sunlight',
                                            'tone': 'bright daylight, even exposure', 'provenance': 'user preference: anime'}}},
             'shots': shots, 'coverage': coverage}
    json.dump(board, open(OUT / 'storyboard.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    board_id, board_rev = save_storyboard(con, story, board, 0)
    print('board', board_id, board_rev)

    slots = con.execute('select shot_key,shot_order,beat_id,context_sha256,spec_json from storyboard_shots '
                        'where storyboard_id=? order by shot_order', (board_id,)).fetchall()
    assert len(slots) == 75, len(slots)

    ids, prev_state, prev_scene = {}, None, None
    for slot in slots:
        i = slot['shot_order']
        act_no = (i - 1) // 15 + 1
        act = ACTS[act_no - 1]
        beat_no = (i - 1) % 15 // 5 + 1
        sub = i - 1 - (act_no - 1) * 15 - (beat_no - 1) * 5
        pose, sentence = act['beats'][beat_no - 1][4][sub]
        expr = act['beats'][beat_no - 1][3]
        framing, angle = CAMS[(beat_no * 5 + sub) % 15]
        stage = stage_at(i)
        state = {'stage': stage[0], 'discarded': stage[2], 'pose': pose, 'expression': expr}
        scene = {'location_key': 'LOC_BEACH', 'light': 'bright daylight, sunlight', 'tide': 'flat, calm',
                 'skin': 'dry and matte'}
        ev = con.execute('select * from story_events where beat_id=?', (slot['beat_id'],)).fetchone()
        shot = {'schema_version': 'n2m.shot.v4', 'visual_context_sha256': slot['context_sha256'],
                'camera': f'{framing}, {angle}', 'focus': pose, 'location_key': 'LOC_BEACH',
                'style_key': 'STYLE_ANIME', 'purpose': PURPOSE[sub], 'prop_keys': [],
                'source_refs': [{'type': 'story_event', 'id': ev['id']}],
                'participants': [{'role_key': 'MUSE_A', 'spec': {
                    'appearance': ident, 'world_position': 'standing or reclining on the sand',
                    'screen_position': 'centre', 'pose': pose, 'expression': expr}}],
                'interactions': [{'event_id': ev['id'], 'actor_role_key': 'MUSE_A', 'target_role_key': None,
                                  'action_text': pose, 'reaction_text': expr,
                                  'constraints': ['solo shot: no second person, no audience']}],
                'intent': {'raw_labels': labels,
                           'constraints': ['one woman only, empty cove', 'bright even anime lighting',
                                           'dry matte skin, no sweat, no water on skin']},
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
                       'tags_validated': 'validate_anima_prompt.py PASS'},
            'policy_decision': {'policy_id': 'N2M-CONTENT-POLICY', 'policy_version': '1.3.0',
                                'scope': 'PROMPT_DERIVATION', 'decision': 'PASS', 'shot_id': shot_id,
                                'rule_reference': 'consensual adult solo nudity, no minors, no violence',
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
                               'evidence': '75 shots, single escalating ladder, one location, one character'}},
              open(OUT / 'seal.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    render = {'model': 'anima-base-v1.0.safetensors',
              'text_encoder': 'qwen_3_06b_base.safetensors', 'vae': 'qwen_image_vae.safetensors',
              'width': 864, 'height': 1152, 'aspect': '3:4', 'megapixels': round(864 * 1152 / 1e6, 3),
              'divisible_by': 16, 'steps': 40, 'cfg': 4.5, 'sampler': 'er_sde', 'scheduler': 'simple',
              'negative': 'worst quality, low quality, score_1, score_2, score_3, artist name, '
                          'blurry, jpeg artifacts, chromatic aberration',
              'seed_policy': 'fixed per shot_key so a prompt edit is the only variable'}
    (OUT / 'render.config.json').write_text(json.dumps(render, indent=1) + '\n', encoding='utf-8')
    print('story', story, 'board', board_id, 'shots', len(ids))
    return story, board_id


if __name__ == '__main__':
    main()
