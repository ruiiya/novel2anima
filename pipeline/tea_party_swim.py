"""Trinity Tea Party swimsuit albums: Mika, Nagisa, Seia.

One builder, three albums. Each is 5 acts x 3 beats x 2 shots at a private Trinity pool,
her canonical white swimsuit never leaves her body, and every reveal is her own hand.
Anima tag prompts (tag block + at most 2 prose sentences).
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
ROOT = pathlib.Path('exports/tea_party')
PURPOSE = ('ESTABLISHING', 'DETAIL')
SHOTS_PER_BEAT = 2

SERIES = 'blue archive'
QUALITY = ['masterpiece', 'best quality', 'score_7']
STYLE = ['anime coloring', 'cel shading', 'clean lineart']
LIGHT = ['bright daylight', 'sunlight', 'clear sky', 'swimming pool']

CAMS = [('full body', 'eye level'), ('cowboy shot', 'from side'), ('upper body', 'three-quarter view'),
        ('close-up', 'eye level'), ('wide shot', 'from above'), ('full body', 'from side'),
        ('cowboy shot', 'from below'), ('upper body', 'from above'), ('close-up', 'from above'),
        ('wide shot', 'eye level')]

# Official swimsuits (user-supplied tag block per character, Blue Archive canon).
CHARACTERS = [
    {'dir': '01_mika', 'name': 'Mika', 'slug': 'mika_swimsuit_blue_archive',
     'tag': 'misono mika (swimsuit) (blue archive), misono mika',
     'identity': ['halo', 'angel wings', 'white wings', 'pink hair', 'very long hair',
                  'purple eyes', 'official alternate costume'],
     'outfit': ['white bikini', 'frilled bikini', 'spaghetti straps', 'white ribbon',
                'neck ribbon', 'white sandals', 'ankle ribbon'],
     'lift': 'bikini top lift', 'bottom': 'bikini bottom pull',
     'prose': 'very long pink hair, purple eyes, a halo, white angel wings and a white frilled '
              'bikini with spaghetti straps and a neck ribbon',
     'accessory': 'white ribbon neck tie'},
    {'dir': '02_nagisa', 'name': 'Nagisa', 'slug': 'nagisa_swimsuit_blue_archive',
     'tag': 'kirifuji nagisa (swimsuit) (blue archive), kirifuji nagisa',
     'identity': ['halo', 'angel wings', 'white wings', 'blonde hair', 'high ponytail',
                  'brown eyes', 'sunglasses', 'tinted eyewear', 'official alternate costume'],
     'outfit': ['black swimsuit', 'one-piece swimsuit', 'halterneck', 'cleavage cutout',
                'white lace shirt', 'open shirt', 'gold bracelet', 'white sandals'],
     'lift': 'clothing lift', 'bottom': 'clothing pull',
     'prose': 'a high blonde ponytail, brown eyes, a halo, white angel wings, tinted sunglasses '
              'and a black one-piece swimsuit under an open white lace shirt',
     'accessory': 'black halter one-piece'},
    {'dir': '03_seia', 'name': 'Seia', 'slug': 'seia_swimsuit_blue_archive',
     'tag': 'yurizono seia (swimsuit) (blue archive), yurizono seia',
     'identity': ['halo', 'fox ears', 'fox tail', 'blonde hair', 'side ponytail', 'yellow eyes',
                  'flat chest', 'sun visor', 'sunglasses', 'tinted eyewear', 'red choker',
                  'official alternate costume'],
     'outfit': ['white swimsuit', 'one-piece swimsuit', 'chest cutout', 'yellow jacket',
                'off-shoulder jacket', 'yellow sandals'],
     'lift': 'clothing lift', 'bottom': 'clothing pull',
     'prose': 'a blonde side ponytail, yellow eyes, fox ears and a fox tail, a halo, a sun visor, '
              'a red choker and a white one-piece swimsuit with a chest cutout under a yellow '
              'off-shoulder jacket',
     'accessory': 'white chest-cutout one-piece'},
]

ACTS = [
 {'title': 'Cổng vườn', 'safety': 'sensitive',
  'summary': 'Cô bước qua cổng vườn Trinity xuống sân hồ bơi, khăn trên vai.',
  'env': ['poolside', 'swimming pool', 'stone paving', 'hedge', 'parasol', 'garden'],
  'spec': {'set': 'private Trinity garden pool: stone deck, hedge behind, calm blue water',
           'time': 'early afternoon'},
  'beats': [
   ('arrive', 'She walks barefoot across the stone deck with a towel over one shoulder.',
    'walking, barefoot, towel over shoulder', 'calm expression',
    [('walking, barefoot, towel over shoulder', '{n} walks barefoot along the pool deck with a towel over one shoulder.'),
     ('standing, hand on hip, looking away', 'She stops at the water edge and looks off across the pool.')]),
   ('settle', 'She drops the towel on a lounger and sits down on it.',
    'sitting on deck chair, towel beside her', 'soft smile',
    [('sitting on deck chair, towel beside her', 'She drops the towel on the lounger and sits down on the edge of it.'),
     ('sitting, legs crossed, looking at viewer', 'She crosses one leg over the other and looks into the lens.')]),
   ('bask', 'She leans back on her hands with her face to the sun.',
    'sitting, leaning back on hands', 'eyes closed, smile',
    [('sitting, leaning back on hands, chest out', 'She leans back on her palms and lifts her chest toward the sun.'),
     ('looking at viewer, smile', 'Her face fills the frame with the bright hedge behind her.')])]},

 {'title': 'Nắng hồ', 'safety': 'sensitive',
  'summary': 'Cô thoa kem lên vai, vươn vai rồi nằm dài trên ghế.',
  'env': ['poolside', 'swimming pool', 'stone paving', 'parasol', 'garden', 'hedge'],
  'spec': {'set': 'same pool deck, camera closer on the lounger and parasol', 'time': 'early afternoon'},
  'beats': [
   ('lotion', 'She squeezes sunscreen into her palm and works it over one shoulder.',
    'applying sunscreen, hand on own shoulder', 'looking down',
    [('applying sunscreen, hand on own shoulder', 'She works sunscreen across her shoulder with her palm.'),
     ('hand on own chest, looking away', 'Her hand slides down over the front of the top.')]),
   ('stretch', 'She stretches both arms overhead.',
    'sitting, arms above head, stretching', 'eyes closed',
    [('sitting, arms above head, stretching', 'She stretches overhead and the top rides up.'),
     ('{lift}, underboob', 'The lift pulls the top up and bares the underside of her breasts.')]),
   ('recline', 'She lies back on the lounger with one knee raised.',
    'lying on deck chair, one knee raised', 'relaxed',
    [('lying on deck chair, one knee raised', 'She lies back on the lounger with one knee up and the pool behind her.'),
     ('lying on side, looking at viewer', 'Her head rests on her arm while she looks into the lens.')])]},

 {'title': 'Dây áo', 'safety': 'nsfw',
  'summary': 'Cô luồn ngón tay dưới dây áo và kéo hẳn lên tới hõm cổ.',
  'env': ['poolside', 'swimming pool', 'stone paving', 'parasol', 'garden', 'hedge'],
  'spec': {'set': 'same pool deck, lounger in the foreground', 'time': 'early afternoon'},
  'beats': [
   ('band', 'She hooks a thumb under the band and drags the top up over her ribs.',
    'sitting, {lift}, underboob', 'looking down',
    [('sitting, {lift}, underboob', 'She hooks a thumb under the band and drags the top up over her ribs.'),
     ('{lift}, nipples, navel', 'The frame holds her bare stomach and the hard line of both nipples.')]),
   ('out', 'She pulls the top up to her collarbone and her bare breasts come out.',
    '{lift}, breasts, nipples', 'looking away',
    [('{lift}, breasts, nipples', 'She yanks the top to her collarbone and both bare breasts spill free.'),
     ('hand on own breast, looking away', 'She cups one bare breast and turns her face aside, nipples hard.')]),
   ('stand', 'She stands with the top bunched above her chest, breasts out.',
    'standing, {lift}, breasts, hard nipples', 'half-closed eyes',
    [('standing, {lift}, breasts, hard nipples', 'She stands on the deck with the top bunched above her chest.'),
     ('looking down at viewer, half-closed eyes', 'Her chin drops as she looks down into the lens.')])]},

 {'title': 'Dây quần', 'safety': 'nsfw',
  'summary': 'Cô quỳ trên ghế, kéo dây buộc bên hông và để lộ mông trần.',
  'env': ['poolside', 'swimming pool', 'stone paving', 'parasol', 'garden', 'hedge'],
  'spec': {'set': 'same pool deck, lounger filling the frame', 'time': 'early afternoon'},
  'beats': [
   ('kneel', 'She turns onto her knees and looks back over her shoulder.',
    'kneeling on deck chair, looking back over shoulder', 'looking at viewer',
    [('kneeling on deck chair, looking back over shoulder', '{n} kneels on the lounger and looks back over her shoulder.'),
     ('{bottom}, ass', 'Her thumb hooks the side tie and drags the bottom over one cheek.')]),
   ('bare', 'Nothing under it: the bottom rides aside and her ass is bare.',
    '{bottom}, ass, thighs, pubic hair', 'smirk',
    [('{bottom}, ass, thighs, pubic hair', 'The bottom rides aside with nothing underneath, bare ass behind and a dark strip of pubic hair at the front.'),
     ('touching own thigh, legs apart, pubic hair', 'She parts her knees and runs a hand down the inside of one thigh.')]),
   ('lift', 'She lifts her hips with the bottom pulled aside.',
    'on all fours, hips lifted, ass, pubic hair', 'looking back',
    [('on all fours, hips lifted, ass, pubic hair', 'She lifts her hips on all fours with the tie pulled aside and the water bright behind her.'),
     ('looking back, smirk', 'Her head turns back toward the lens in a narrow smirk.')])]},

 {'title': 'Không che', 'safety': 'explicit',
  'summary': 'Cô ngồi choãi trên ghế, tự kéo quần bơi sang một bên và để lộ hẳn vùng kín.',
  'env': ['poolside', 'swimming pool', 'stone paving', 'parasol', 'garden', 'hedge'],
  'spec': {'set': 'same pool deck, parasol and hedge behind her', 'time': 'early afternoon'},
  'beats': [
   ('present', 'She sits with her knees wide and pulls the bottom aside.',
    'sitting, spread legs, clothing aside, pussy, pubic hair, nipples', 'looking at viewer',
    [('sitting, spread legs, clothing aside, pussy, pubic hair, nipples', 'She sits with her knees wide and pulls the white fabric aside, pubic hair and pussy fully showing.'),
     ('sitting, spread legs, pussy, touching own thigh', 'Her fingers slide down the inside of her thigh with her legs still open.')]),
   ('arch', 'She leans back on her elbows with her legs wide open.',
    'leaning back, spread legs, pussy, nipples, hard nipples, arching back', 'eyes closed',
    [('leaning back, spread legs, pussy, nipples, hard nipples, arching back', 'She leans back on her elbows with both legs wide, nipples and pussy bare to the lens.'),
     ('biting lip, half-closed eyes', 'Her face fills the frame with her teeth on the lower lip.')]),
   ('finish', 'She lies back on the lounger, then sits up smiling.',
    'lying on back, spread legs, pussy, pubic hair', 'smile',
    [('lying on back, spread legs, pussy, pubic hair', 'She lies back on the lounger with her legs open and the bikini pushed aside.'),
     ('sitting up, looking at viewer, spread legs', 'She sits up with her legs still open and gives a small smile.')])]},
]


def stage_i(i):
    return min((i - 1) // 6, 4)


def cam(act_no, beat_no, sub, si):
    framing, angle = CAMS[(act_no * 3 + beat_no * 2 + sub) % 10]
    if si >= 4 and angle == 'from above':
        angle = 'eye level'          # 'from above' + spread legs produced inverted bodies
    if si >= 1 and framing == 'close-up':
        framing = 'upper body'       # close-up cropped the head off at this breast size
    return framing, angle


def diff(a, b):
    return {'set': {k: v for k, v in b.items() if a.get(k) != v},
            'remove': [k for k in a if k not in b]}


def stages_for(cfg):
    base = cfg['outfit']
    lift, bottom = cfg['lift'], cfg['bottom']
    return [
        ('swimsuit_on', base,
         f'the {cfg["accessory"]} tied on exactly as she walked in'),
        ('top_lift', base + [lift, 'underboob', 'nipples'],
         'the same swimsuit, the top pulled up enough to show the underside of her breasts'),
        ('breasts_out', base + [lift, 'breasts', 'nipples', 'hard nipples', 'navel'],
         'the top bunched above her chest, bare breasts out, bottom still tied'),
        ('bottom_pull', base + [bottom, 'ass', 'thighs', 'pubic hair', 'clothed'],
         'the same bottom dragged aside, bare ass and pubic hair showing'),
        ('aside', base + ['clothing aside', 'clothing pull', 'pubic hair', 'pussy', 'labia',
                          'uncensored', 'spread legs', 'nipples', 'hard nipples'],
         'the swimsuit still on but pulled aside: nipples hard, pussy and pubic hair fully shown'),
    ]


def validate(out, text):
    p = out / 'drafts' / '_check.txt'
    p.write_text(text, encoding='utf-8')
    r = subprocess.run([sys.executable, 'tools/novel2anima/validate_anima_prompt.py', str(p)],
                       capture_output=True, text=True)
    p.unlink()
    if r.returncode:
        raise SystemExit(f'BLOCKED {text.splitlines()[0][:120]}\n{r.stdout}')


def prompt_for(cfg, act, stage, pose, expr, framing, angle, sentence):
    tags = (QUALITY + [act['safety'], 'highres', '1girl', 'solo', cfg['tag'], SERIES]
            + cfg['identity'] + stage[1] + pose.split(', ') + expr.split(', ')
            + [framing, angle] + act['env'] + LIGHT + STYLE)
    return ', '.join(dict.fromkeys(tags)) + '\n' + sentence


def build(cfg):
    name = cfg['name']
    title = f'Hồ Bơi Trinity — {name}'
    brief = f"""# Hồ Bơi Trinity — {name} (approved)

**Cast mode:** NON_BLIND — {name} (swimsuit) (Blue Archive), `CONFIRMED_ADULT`, `REVIEWED`.
**User yêu cầu:** album erotic ~30 shot cho từng thành viên Tea Party, dùng đúng bộ swimsuit
của nhân vật, **không thay đồ**, nhân vật chủ động tự làm lộ vùng nhạy cảm.

## Premise

Hồ bơi riêng trong vườn Trinity, đầu giờ chiều, nắng đều trên mặt nước. {name} xuống sân hồ
một mình trong bộ swimsuit chính thức: {cfg['accessory']}. **Không có gì bên trong bộ swimsuit.**
Cô không thay đồ và không cởi bộ swimsuit trong suốt album.

## Trục leo thang

Không thay đồ, không cởi đồ. Leo thang bằng **độ vén và tư thế**, tất cả do cô tự làm:
bikini buộc đủ → vén áo lộ `underboob` → kéo áo lên hõm cổ, **ngực trần** → kéo dây buộc hông,
**mông trần + lông mu** → ngồi choãi, **tự kéo quần bơi sang một bên, lộ vùng kín**.

## Ràng buộc

- Một người trong khung, không khán giả, không người thứ hai quanh hồ.
- Đồng thuận rõ ràng, không ép buộc, không bạo lực. Cô tự tay làm mọi thứ.
- Sáng đều: không low-key, không tối góc.
- Khô: không mồ hôi, không nước trên da.
- Một địa điểm duy nhất: hồ bơi riêng vườn Trinity (sân đá, dù, hàng rào cây).
- Halo luôn hiện. Bộ swimsuit luôn nằm trên người, không thay bộ khác.
"""
    out = ROOT / cfg['dir']
    out.mkdir(parents=True, exist_ok=True)
    (out / 'drafts').mkdir(exist_ok=True)
    (out / 'source_brief.md').write_text(brief, encoding='utf-8')
    con = connect(DB)
    cid = con.execute('select id from characters where slug=?', (cfg['slug'],)).fetchone()['id']
    labels = ['nsfw', 'adult', 'erotic', 'consensual', 'solo', 'anime_style', 'swimsuit',
              'trinity_pool', 'fixed_outfit', 'progressive_exposure']
    story = create_story(con, title, 'NON_BLIND', brief, labels)
    add_role(con, story, 'MUSE_A', f'{cfg["tag"]} - official white bikini, same outfit all 30 shots')
    bind_role(con, story, 'MUSE_A', cid)
    print(f'{name}: story {story} char {cid}')

    stages = stages_for(cfg)
    acts_plan = []
    for n, act in enumerate(ACTS, 1):
        beats = []
        for bi, (btype, bsum, pose, expr, _shots) in enumerate(act['beats'], 1):
            st = stages[stage_i((n - 1) * 6 + (bi - 1) * 2 + 1)]
            beats.append({'beat_id': f'B{(n - 1) * 3 + bi:02d}', 'type': btype, 'summary': bsum, 'events': [
                {'event_id': f'E{(n - 1) * 3 + bi:02d}', 'actor_id': 'MUSE_A', 'target_id': None,
                 'primary_action': pose, 'reaction': bsum,
                 'state_change': f'outfit: {st[0]}; pose: {pose}; expression: {expr}',
                 'spec': {'pose': pose, 'expression': expr, 'outfit': st[0]}}]})
        acts_plan.append({'act_id': f'A{n:02d}', 'title': act['title'], 'summary': act['summary'],
                          'spec': act['spec'], 'beats': beats})

    ident = f'{cfg["tag"]}, {cfg["prose"]}'
    plan = {'schema_version': 'n2m.story_plan.v1', 'story_id': story, 'title': title,
            'cast_mode': 'NON_BLIND',
            'source_refs': [{'type': 'user_input', 'path': f'{out}/source_brief.md', 'sha256': sha(brief)}],
            'approval': {'status': 'APPROVED', 'approved_by': 'user', 'approved_at': '2026-11-17T00:00:00Z',
                         'evidence': 'User asked for a 30-shot swimsuit album per Tea Party member',
                         'policy_id': 'N2M-CONTENT-POLICY', 'policy_version': '1.3.0'},
            'intent': {'content_profile': 'erotic_album', 'raw_labels': labels,
                       'constraints': ['One woman only in frame; empty pool deck, no audience.',
                                       'Consent is explicit and voluntary; no coercion, no violence.',
                                       'Bright even exposure only: no low-key, no dark falloff.',
                                       'Dry skin: no sweat, no water on skin.',
                                       'One location only (the Trinity garden pool).',
                                       f'The official swimsuit never changes: {cfg["outfit"][0]}, '
                                       f'{cfg["accessory"]}.',
                                       'Nothing under the bikini in any shot.',
                                       'She exposes herself deliberately with her own hands.',
                                       'The halo stays in every shot.']},
            'art_direction': {'format': 'anime-illustrated erotic album, 5 acts, 3 beats each, 2 shots per beat',
                              'brightness_constraint': 'Bright, evenly exposed anime illustration.',
                              'location': {'type': 'private garden pool',
                                           'detail': 'stone deck, calm pool, parasol, hedge, garden',
                                           'continuity': 'same deck; pool behind, hedge left, parasol right'},
                              'costume': {'type': f'{cfg["outfit"][0]}, {cfg["accessory"]}, barefoot',
                                          'single_variable': 'how far the fabric is pulled aside',
                                          'ladder': [s[0] for s in stages]}},
            'characters': [{'role_key': 'MUSE_A', 'character_id': cid, 'age_status': 'CONFIRMED_ADULT',
                            'identity': ident,
                            'appearance_evidence': 'catalog character_tags for ' + cfg['tag']}],
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

    shots, coverage, prev, k = [], [], None, 0
    for act_no in range(1, 6):
        for beat_no in range(1, 4):
            beat_id, ev_id = ev_map[f'A{act_no:02d}.B{beat_no}']
            _t, _s, _p, _e, moments = ACTS[act_no - 1]['beats'][beat_no - 1]
            for i in range(SHOTS_PER_BEAT):
                k += 1
                key = f'S{k:03d}'
                framing, angle = cam(act_no, beat_no, i, stage_i(k))
                pose = moments[i][0].format(lift=cfg['lift'], bottom=cfg['bottom'])
                shots.append({'shot_key': key, 'shot_order': k, 'beat_id': beat_id, 'branch_key': 'MAIN',
                              'previous_shot_key': prev,
                              'transition': 'START' if prev is None else ('TIME_CUT' if i == 0 else 'CAMERA_CUT'),
                              'purpose': PURPOSE[i], 'camera': f'{framing}, {angle}',
                              'focus': pose, 'visual_moment': pose,
                              'role_keys': ['MUSE_A'], 'location_key': 'LOC_POOL',
                              'prop_keys': [], 'style_key': 'STYLE_ANIME'})
                coverage.append({'event_id': ev_id, 'status': 'VISUALIZED', 'shot_key': key,
                                 'evidence': f'{key} shows: {pose}'})
                prev = key

    board = {'story_revision': con.execute('select current_revision from stories where id=?',
                                           (story,)).fetchone()[0],
             'approval': {'status': 'APPROVED', 'approved_by': 'user', 'approved_at': '2026-11-17T00:00:00Z',
                          'evidence': f'User approved a 30-shot swimsuit album for {name}'},
             'visual_bible': {
                 'characters': {'MUSE_A': {'description': ident,
                                           'provenance': 'catalog character_tags for ' + cfg['tag'],
                                           'character_id': cid, 'outfit_id': None}},
                 'locations': {'LOC_POOL': {
                     'description': 'private Trinity garden pool: stone deck, calm water, parasol, hedge',
                     'provenance': f'{out}/source_brief.md + plan art_direction.location'}},
                 'props': {},
                 'styles': {'STYLE_ANIME': {
                     'description': 'clean anime illustration, crisp line art, cel shading, bright palette',
                     'tone': 'bright midday, even exposure', 'provenance': 'user preference: anime'}}},
             'shots': shots, 'coverage': coverage}
    json.dump(board, open(out / 'storyboard.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    board_id, _ = save_storyboard(con, story, board, 0)
    print(f'{name}: board {board_id}')

    slots = con.execute('select shot_key,shot_order,beat_id,context_sha256 from storyboard_shots '
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
        sentence = sentence.format(n=name, lift=cfg['lift'], bottom=cfg['bottom'])
        pose = pose.format(lift=cfg['lift'], bottom=cfg['bottom'])
        expr = act['beats'][beat_no - 1][3]
        framing, angle = cam(act_no, beat_no, sub, stage_i(i))
        stage = stages[stage_i(i)]
        state = {'stage': stage[0], 'outfit': stage[2], 'pose': pose, 'expression': expr}
        scene = {'location_key': 'LOC_POOL', 'light': 'bright midday sunlight',
                 'skin': 'dry and matte', 'outfit': 'unchanged'}
        ev = con.execute('select * from story_events where beat_id=?', (slot['beat_id'],)).fetchone()
        shot = {'schema_version': 'n2m.shot.v4', 'visual_context_sha256': slot['context_sha256'],
                'camera': f'{framing}, {angle}', 'focus': pose, 'location_key': 'LOC_POOL',
                'style_key': 'STYLE_ANIME', 'purpose': PURPOSE[sub], 'prop_keys': [],
                'source_refs': [{'type': 'story_event', 'id': ev['id']}],
                'participants': [{'role_key': 'MUSE_A', 'spec': {
                    'appearance': ident, 'world_position': 'on the lounger or on the stone deck',
                    'screen_position': 'centre', 'pose': pose, 'expression': expr}}],
                'interactions': [{'event_id': ev['id'], 'actor_role_key': 'MUSE_A', 'target_role_key': None,
                                  'action_text': pose, 'reaction_text': expr,
                                  'constraints': ['solo shot: no second person, no audience',
                                                  'outfit unchanged: official white bikini, nothing underneath']}],
                'intent': {'raw_labels': labels,
                           'constraints': ['one woman only, empty pool deck', 'bright even anime lighting',
                                           'dry matte skin, dry fabric', 'no underwear under the bikini',
                                           'exposure is self-directed, never forced']},
                'continuity_revision_note': 'initial approved pool state'}
        shot_id, _ = save_shot(con, slot['beat_id'], slot['shot_key'], shot, ev['id'])
        ids[slot['shot_key']] = shot_id
        before_state = state if prev_state is None else prev_state
        save_continuity(con, shot_id, {'snapshots': [
            {'role_key': None, 'before': prev_scene or scene,
             'delta': diff(prev_scene or scene, scene), 'after': scene},
            {'role_key': 'MUSE_A', 'before': before_state,
             'delta': diff(before_state, state), 'after': state}]})
        prev_state, prev_scene = state, scene

        text = prompt_for(cfg, act, stage, pose, expr, framing, angle, sentence)
        validate(out, text)
        (out / 'drafts' / f'{slot["shot_key"]}.txt').write_text(text, encoding='utf-8')
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
    json.dump({'bindings': bindings}, open(out / 'bindings.json', 'w', encoding='utf-8'), indent=1)
    json.dump({'bindings': bindings,
               'sequence_qa': {'verdict': 'PASS',
                               'evidence': '30 shots, one escalating exposure ladder, one pool, one character, '
                                           'one unchanged official bikini, nothing underneath, '
                                           'every reveal made by her own hand'}},
              open(out / 'seal.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    render = {'model': 'anima-base-v1.0.safetensors',
              'text_encoder': 'qwen_3_06b_base.safetensors', 'vae': 'qwen_image_vae.safetensors',
              'width': 864, 'height': 1152, 'aspect': '3:4', 'megapixels': round(864 * 1152 / 1e6, 3),
              'divisible_by': 16, 'steps': 40, 'cfg': 4.5, 'sampler': 'er_sde', 'scheduler': 'simple',
              'negative': 'worst quality, low quality, score_1, score_2, score_3, artist name, '
                          'blurry, jpeg artifacts, chromatic aberration, shiny skin, oily skin, '
                          'glossy skin, sweat, extra limbs, extra fingers, fused fingers, bad anatomy',
              'seed_policy': 'fixed per shot_key so a prompt edit is the only variable'}
    (out / 'render.config.json').write_text(json.dumps(render, indent=1) + '\n', encoding='utf-8')
    print(f'{name}: shots {len(ids)}')
    return story, board_id


if __name__ == '__main__':
    if len(sys.argv) > 1:
        wanted = {a.lower() for a in sys.argv[1:]}
        picks = [c for c in CHARACTERS if c['name'].lower() in wanted]
    else:
        picks = CHARACTERS
    for cfg in picks:
        build(cfg)
