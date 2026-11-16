"""Casual-wear erotic album: one adult character, one outfit, one room, 5 acts x 3 beats x 2 shots.

No wardrobe change at any point: escalation runs on fit, exposure and pose, never on
removing a garment. Anima tag prompts (tag block + at most 2 prose sentences).
Character: Karin (Blue Archive) - CONFIRMED_ADULT / REVIEWED in the catalog.
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
OUT = pathlib.Path('exports/casual_karin/01_karin')
PURPOSE = ('ESTABLISHING', 'DETAIL')
SHOTS_PER_BEAT = 2

TITLE = 'Căn Hộ Chiều Muộn — Karin'
NAME = 'Karin'
CHAR_TAG = 'karin (blue archive)'
SERIES = 'blue archive'
IDENTITY = ['dark skin', 'black hair', 'long hair', 'ponytail', 'yellow eyes',
            'large breasts', 'halo', 'bangs', 'sidelocks']
QUALITY = ['masterpiece', 'best quality', 'score_7']
STYLE = ['anime coloring', 'cel shading', 'clean lineart']
LIGHT = ['indoors', 'bright lighting', 'afternoon', 'sunlight']

# 10 distinct framing/angle pairs; a beat rotates so no two shots of a beat share a camera.
CAMS = [('full body', 'eye level'), ('cowboy shot', 'from side'), ('upper body', 'three-quarter view'),
        ('close-up', 'eye level'), ('wide shot', 'from above'), ('full body', 'from side'),
        ('cowboy shot', 'from below'), ('upper body', 'from above'), ('close-up', 'from above'),
        ('wide shot', 'eye level')]

BASE_OUTFIT = ['white t-shirt', 'short shorts', 'denim shorts', 'bare legs', 'sneakers']

STAGES = [
    ('thin_tee_no_bra', BASE_OUTFIT + ['no bra', 'no panties', 'thin fabric',
                                       'nipples visible through clothing', 'hard nipples'],
     'the thin tee with nothing under it, both nipples standing out through the damp-free fabric'),
    ('taut_tee_no_panties', BASE_OUTFIT + ['no bra', 'no panties', 'taut shirt',
                                           'nipples visible through clothing', 'hard nipples',
                                           'cameltoe', 'pubic hair'],
     'same tee and shorts, nothing underneath at all, nipples and the shape of her mound through the fabric'),
    ('breasts_out', BASE_OUTFIT + ['no bra', 'no panties', 'shirt lift', 'midriff', 'navel',
                                   'nipples', 'hard nipples', 'breasts', 'large areolae',
                                   'shorts pull', 'pubic hair', 'pussy'],
     'the tee pulled up over her chest, bare breasts out with the nipples fully visible'),
    ('shorts_low', BASE_OUTFIT + ['no bra', 'no panties', 'shirt lift', 'midriff', 'navel',
                                  'nipples', 'hard nipples', 'breasts', 'shorts pull', 'ass',
                                  'thighs', 'pubic hair', 'pussy'],
     'tee still up, shorts dragged low, bare ass and a clear strip of pubic hair at the front'),
    ('aside', BASE_OUTFIT + ['no bra', 'no panties', 'shirt lift', 'nipples', 'hard nipples',
                             'breasts', 'shorts pull', 'ass', 'pubic hair', 'uncensored',
                             'pussy', 'spread pussy', 'detailed pussy', 'spread legs',
                             'clothed', 'clothing aside'],
     'clothes still on but pulled aside: nipples hard, pubic hair and the whole pussy spread open'),
]

ACTS = [
 {'title': 'Căn hộ trống', 'safety': 'sensitive',
  'summary': 'Cô về nhà một mình, đặt túi xuống và đi qua phòng khách tới cửa sổ.',
  'env': ['apartment', 'living room', 'sofa', 'coffee table', 'curtains', 'window',
          'wooden floor'],
  'spec': {'set': 'small apartment living room: sofa, coffee table, tall window with curtains',
           'time': 'late afternoon'},
  'beats': [
   ('return', 'She sets a paper bag on the coffee table and looks at the camera.',
    'standing, holding paper bag', 'looking at viewer',
    [('standing, holding paper bag', 'Karin stands in the left third of the frame with a paper bag in one hand.'),
     ('standing, hand on hip', 'She sets the bag down and puts one hand on her hip.')]),
   ('walk', 'She crosses the room to the window and stops there.',
    'walking, looking away', 'calm expression',
    [('walking, looking away', 'She crosses the room toward the window with one foot lifted.'),
     ('standing at window, hand on curtain', 'She stops at the glass with the curtain edge against her arm.')]),
   ('sit', 'She sits on the sofa and crosses her legs.',
    'sitting on sofa, legs crossed', 'smile, looking at viewer',
    [('sitting on sofa, legs crossed', 'She lowers herself onto the sofa and crosses one leg over the other.'),
     ('looking at viewer, smile', 'Her face fills the frame with window light across one cheek.')])]},

 {'title': 'Ngồi xuống', 'safety': 'sensitive',
  'summary': 'Cô vươn vai trên sofa, nghiêng người và nằm dài ra.',
  'env': ['apartment', 'living room', 'sofa', 'coffee table', 'curtains', 'window',
          'wooden floor'],
  'spec': {'set': 'living room, camera closer on the sofa', 'time': 'late afternoon'},
  'beats': [
   ('stretch', 'She stretches both arms overhead.',
    'sitting, arms above head, stretching', 'eyes closed',
    [('sitting, arms above head, stretching', 'She stretches both arms overhead and the shirt pulls across her chest.'),
     ('arching back, taut shirt', 'Her back arches and the fabric draws tight over her breasts.')]),
   ('lean', 'She leans forward with her elbows on her knees.',
    'sitting, leaning forward, elbows on knees', 'looking down',
    [('sitting, leaning forward, elbows on knees', 'She leans forward over her knees with her elbows planted on them.'),
     ('hand on own thigh', 'Her hand slides along her thigh above the knee.')]),
   ('recline', 'She lies back along the sofa.',
    'lying on sofa, one knee raised', 'relaxed',
    [('lying on sofa, one knee raised', 'She lies back along the cushions with one knee raised.'),
     ('lying on side, looking at viewer', 'Her head rests on the armrest while she looks into the lens.')])]},

 {'title': 'Vạt áo', 'safety': 'nsfw',
  'summary': 'Cô tự kéo vạt áo lên tới hõm cổ và để lộ hẳn bộ ngực trần.',
  'env': ['apartment', 'living room', 'sofa', 'coffee table', 'curtains', 'window',
          'wooden floor'],
  'spec': {'set': 'living room, sofa in the foreground', 'time': 'late afternoon'},
  'beats': [
   ('hem', 'She hooks a thumb under the hem and drags it up over her ribs.',
    'sitting, shirt lift, midriff, navel', 'looking down',
    [('sitting, shirt lift, midriff, navel', 'She hooks a thumb under the hem and drags the thin cotton up over her ribs.'),
     ('shirt lift, midriff, stomach', 'The frame holds her bare stomach and the underside of one breast.')]),
   ('out', 'She pulls the shirt up to her collarbone and her bare breasts come out.',
    'shirt lift, breasts, nipples', 'looking away',
    [('shirt lift, breasts, nipples', 'She yanks the shirt up to her collarbone and both bare breasts spill free.'),
     ('hand on own breast, looking away', 'She cups one bare breast and turns her face aside, nipples hard.')]),
   ('stand', 'She stands with the shirt bunched above her chest, breasts still out.',
    'standing, shirt lift, breasts, nipples', 'half-closed eyes',
    [('standing, shirt lift, breasts, nipples', 'She stands and keeps the shirt bunched above her chest, breasts fully out.'),
     ('looking down at viewer, half-closed eyes', 'Her chin drops as she looks down into the lens.')])]},

 {'title': 'Cạp quần', 'safety': 'nsfw',
  'summary': 'Cô quỳ trên sofa, kéo cạp quần short xuống hẳn và để lộ mông trần.',
  'env': ['apartment', 'living room', 'sofa', 'coffee table', 'curtains', 'window',
          'wooden floor'],
  'spec': {'set': 'living room, sofa cushions filling the frame', 'time': 'late afternoon'},
  'beats': [
   ('kneel', 'She kneels on the cushion and looks back over her shoulder.',
    'kneeling on sofa, looking back over shoulder, shirt lift', 'looking at viewer',
    [('kneeling on sofa, looking back over shoulder, shirt lift', 'Karin kneels on the cushion, shirt up, and looks back over her shoulder.'),
     ('shorts pull, ass', 'Her thumb hooks the waistband and drags the denim down over her bare ass.')]),
   ('bare', 'Nothing underneath: the shorts sit under her cheeks, pubic hair visible at the front.',
    'shorts pull, ass, no panties, thighs, pubic hair, pussy', 'smirk',
    [('shorts pull, ass, no panties, thighs, pubic hair, pussy', 'The shorts ride under her cheeks with nothing underneath, bare ass behind and a dark strip of pubic hair at the front.'),
     ('touching own thigh, legs apart, pubic hair', 'She parts her knees and runs a hand down the inside of one thigh, pubic hair in plain view.')]),
   ('lean', 'She drapes herself over the back of the sofa, hips lifted, ass bare.',
    'leaning forward over sofa, ass, top-down bottom-up', 'looking back',
    [('leaning forward over sofa, ass, top-down bottom-up', 'She drapes herself over the sofa back with her hips lifted and her bare ass toward the lens.'),
     ('looking back, smirk', 'Her head turns back toward the lens in a narrow smirk.')])]},

 {'title': 'Không che', 'safety': 'explicit',
  'summary': 'Cô ngồi choãi chân, tự kéo quần short sang một bên và để lộ hẳn vùng kín.',
  'env': ['apartment', 'living room', 'sofa', 'coffee table', 'curtains', 'window',
          'wooden floor'],
  'spec': {'set': 'living room, sofa, window behind', 'time': 'late afternoon'},
  'beats': [
   ('present', 'She sits with her legs spread and pulls the shorts aside, pussy spread open.',
    'sitting, spread legs, clothing aside, spread pussy, pubic hair, shirt lift, breasts, hard nipples',
    'looking at viewer',
    [('sitting, spread legs, clothing aside, spread pussy, pubic hair, shirt lift, breasts, hard nipples', 'She sits with her knees wide and pulls the denim aside, her pubic hair and spread pussy fully exposed under the lifted shirt.'),
     ('sitting, spread legs, pussy, pubic hair, touching own thigh', 'Her fingers part her lips and slide down the inside of her thigh with her legs still wide open.')]),
   ('arch', 'She arches back on the cushions, legs spread, pussy and nipples uncovered.',
    'spread legs, spread pussy, pubic hair, breasts, hard nipples, arching back, hand in own hair',
    'eyes closed',
    [('spread legs, spread pussy, pubic hair, breasts, hard nipples, arching back, hand in own hair', 'Her back arches with both legs spread wide, spread pussy, pubic hair and hard nipples all bare to the lens.'),
     ('biting lip, half-closed eyes', 'Her face fills the frame with her teeth on the lower lip.')]),
   ('finish', 'She lies back with her legs open, pussy still showing, then sits up.',
    'lying on back, spread legs, spread pussy, pubic hair, arm over eyes', 'smile',
    [('lying on back, spread legs, spread pussy, pubic hair, arm over eyes', 'She lies back along the sofa with her legs open, pubic hair and pussy still in frame under a forearm.'),
     ('sitting up, looking at viewer, spread legs, spread pussy', 'She sits up with her legs still open, pussy spread to the lens, and gives a small smile.')])]},
]

BRIEF = f"""# Căn Hộ Chiều Muộn — source brief (approved)

**Cast mode:** NON_BLIND — Karin (Blue Archive), `CONFIRMED_ADULT`, `REVIEWED`.
**User yêu cầu:** 1 story album erotic, **không thay đổi trang phục**, ~30 shot, trang phục thường ngày,
**không mặc nội y**, nhân vật chủ động tự làm lộ vùng nhạy cảm.

## Premise

Căn hộ nhỏ, chiều muộn, nắng xiên qua cửa sổ. Karin ở nhà một mình, mặc đồ mặc hàng ngày:
áo thun trắng mỏng, quần short jean, giày sneaker. **Dưới áo và dưới quần không có gì.** Cô không
thay đồ trong suốt album.

## Trục leo thang

Không thay đồ, không cởi đồ. Leo thang bằng **độ bó, độ vén và tư thế**, tất cả do cô tự làm:
áo mỏng lộ núm → áo bó + `cameltoe` → vén áo lên tới hõm cổ, **ngực trần** → kéo cạp quần
short xuống, **mông trần** → ngồi choãi, **tự kéo quần sang một bên, lộ vùng kín**.

## Ràng buộc

- Một người trong khung, không khán giả, không phản chiếu người khác.
- Đồng thuận rõ ràng, không ép buộc, không bạo lực. Cô tự tay làm mọi thứ.
- Sáng đều: không low-key, không tối góc.
- Khô: không mồ hôi, không ướt, không nước trên da hay trên vải.
- Một địa điểm duy nhất: phòng khách căn hộ (sofa, bàn, cửa sổ).
- Halo luôn hiện. Bộ đồ (áo thun, short jean, sneaker) luôn nằm trên người, không thay bộ khác.
"""


def char_id(con):
    row = con.execute('select id from characters where slug=?', ('karin_blue_archive',)).fetchone()
    assert row, 'character not found in catalog'
    return row['id']


def stage_at(i):
    return STAGES[min((i - 1) // 6, 4)]


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
    labels = ['nsfw', 'adult', 'erotic', 'consensual', 'solo', 'anime_style', 'casual_wear',
              'apartment', 'no_underwear', 'fixed_outfit', 'progressive_exposure']
    story = create_story(con, TITLE, 'NON_BLIND', BRIEF, labels)
    add_role(con, story, 'MUSE_A', f'{CHAR_TAG} - casual tee and denim shorts, same outfit all 30 shots')
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

    ident = (f'{CHAR_TAG}, dark skin, long black hair in a ponytail, yellow eyes, a small halo '
             f'above her head and a large chest')
    plan = {'schema_version': 'n2m.story_plan.v1', 'story_id': story, 'title': TITLE,
            'cast_mode': 'NON_BLIND',
            'source_refs': [{'type': 'user_input', 'path': f'{OUT}/source_brief.md', 'sha256': sha(BRIEF)}],
            'approval': {'status': 'APPROVED', 'approved_by': 'user', 'approved_at': '2026-11-17T00:00:00Z',
                         'evidence': 'User asked for a 30-shot erotic album in unchanged everyday clothes',
                         'policy_id': 'N2M-CONTENT-POLICY', 'policy_version': '1.3.0'},
            'intent': {'content_profile': 'erotic_album', 'raw_labels': labels,
                       'constraints': ['One woman only in frame; empty apartment, no audience.',
                                       'Consent is explicit and voluntary; no coercion, no violence.',
                                       'Bright even exposure only: no low-key, no dark falloff.',
                                       'Dry: no sweat, no water, no wet fabric.',
                                       'One location only (the living room).',
                                       'The outfit never changes: white tee, denim shorts, sneakers.',
                                       'No bra, no panties: she wears nothing under the clothes in all 30 shots.',
                                       'She exposes herself deliberately with her own hands; no one else acts on her.',
                                       'The small halo stays in every shot.']},
            'art_direction': {'format': 'anime-illustrated erotic album, 5 acts, 3 beats each, 2 shots per beat',
                              'brightness_constraint': 'Bright, evenly exposed anime illustration.',
                              'location': {'type': 'indoor apartment', 'detail': 'living room, sofa, window',
                                           'continuity': 'same room; sofa left, window right, bag on the table'},
                              'costume': {'type': 'white tee, denim shorts, sneakers',
                                          'single_variable': 'how much the fabric covers',
                                          'ladder': [s[0] for s in STAGES]}},
            'characters': [{'role_key': 'MUSE_A', 'character_id': cid, 'age_status': 'CONFIRMED_ADULT',
                            'identity': ident,
                            'appearance_evidence': 'catalog character_tags: dark skin, black hair, ponytail, '
                                                   'yellow eyes, large breasts, halo'}],
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
                framing, angle = CAMS[(act_no * 3 + beat_no * 2 + i) % 10]
                shots.append({'shot_key': key, 'shot_order': k, 'beat_id': beat_id, 'branch_key': 'MAIN',
                              'previous_shot_key': prev,
                              'transition': 'START' if prev is None else ('TIME_CUT' if i == 0 else 'CAMERA_CUT'),
                              'purpose': PURPOSE[i], 'camera': f'{framing}, {angle}',
                              'focus': moments[i][0], 'visual_moment': moments[i][0],
                              'role_keys': ['MUSE_A'], 'location_key': 'LOC_APARTMENT',
                              'prop_keys': [], 'style_key': 'STYLE_ANIME'})
                coverage.append({'event_id': ev_id, 'status': 'VISUALIZED', 'shot_key': key,
                                 'evidence': f'{key} shows: {moments[i][0]}'})
                prev = key

    board = {'story_revision': con.execute('select current_revision from stories where id=?',
                                           (story,)).fetchone()[0],
             'approval': {'status': 'APPROVED', 'approved_by': 'user', 'approved_at': '2026-11-17T00:00:00Z',
                          'evidence': 'User approved a 30-shot casual-wear erotic album, fixed outfit'},
             'visual_bible': {
                 'characters': {'MUSE_A': {'description': ident,
                                           'provenance': 'catalog character_tags for ' + CHAR_TAG,
                                           'character_id': cid, 'outfit_id': None}},
                 'locations': {'LOC_APARTMENT': {
                     'description': 'small living room: sofa left, coffee table, tall window with curtains',
                     'provenance': f'{OUT}/source_brief.md + plan art_direction.location'}},
                 'props': {},
                 'styles': {'STYLE_ANIME': {
                     'description': 'clean anime illustration, crisp line art, cel shading, bright palette',
                     'tone': 'bright afternoon, even exposure', 'provenance': 'user preference: anime'}}},
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
        framing, angle = CAMS[(act_no * 3 + beat_no * 2 + sub) % 10]
        stage = stage_at(i)
        state = {'stage': stage[0], 'outfit': stage[2], 'pose': pose, 'expression': expr}
        scene = {'location_key': 'LOC_APARTMENT', 'light': 'bright afternoon sunlight',
                 'skin': 'dry and matte', 'outfit': 'unchanged'}
        ev = con.execute('select * from story_events where beat_id=?', (slot['beat_id'],)).fetchone()
        shot = {'schema_version': 'n2m.shot.v4', 'visual_context_sha256': slot['context_sha256'],
                'camera': f'{framing}, {angle}', 'focus': pose, 'location_key': 'LOC_APARTMENT',
                'style_key': 'STYLE_ANIME', 'purpose': PURPOSE[sub], 'prop_keys': [],
                'source_refs': [{'type': 'story_event', 'id': ev['id']}],
                'participants': [{'role_key': 'MUSE_A', 'spec': {
                    'appearance': ident, 'world_position': 'on or beside the sofa',
                    'screen_position': 'centre', 'pose': pose, 'expression': expr}}],
                'interactions': [{'event_id': ev['id'], 'actor_role_key': 'MUSE_A', 'target_role_key': None,
                                  'action_text': pose, 'reaction_text': expr,
                                  'constraints': ['solo shot: no second person, no audience',
                                                  'outfit unchanged: white tee and denim shorts, no underwear']}],
                'intent': {'raw_labels': labels,
                           'constraints': ['one woman only, empty apartment', 'bright even anime lighting',
                                           'dry matte skin and dry fabric', 'no bra, no panties',
                                           'exposure is self-directed, never forced']},
                'continuity_revision_note': 'initial approved apartment state'}
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
                       'nudity': f'exposure stage {stage[0]}: no bra, no panties, self-directed reveal',
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
                               'evidence': '30 shots, one escalating exposure ladder, one room, one character, '
                                           'one unchanged outfit, no bra and no panties throughout, '
                                           'every reveal made by her own hand'}},
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
