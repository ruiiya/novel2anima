"""anima_ab — build the A/B prompt file for Anima-Aesthetic-v1.1.

Same shot, same seed, two prompt styles:
  A = current natural-language sentence (written for MOSS)
  B = Anima tag block (Danbooru vocabulary, no quality tags)

Two shots picked to cover both crop extremes: S001 full body, S009 close-up.

  python exports/cnc_bunny/anima_ab.py
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / 'exports/cnc_bunny/03_karin/v1/prompts.all.jsonl'
OUT = ROOT / 'exports/cnc_bunny/test_render_anima'

# ponytail: hand-written tag blocks for 2 shots. Replace with a tag compiler
# built from catalog_tags once the A/B shows tags win.
TAGS = {
    'S001': ('1girl, solo, nsfw, karin (bunny) (blue archive), dark skin, black hair, very long hair, ponytail, '
             'yellow eyes, large breasts, rabbit tail, halo, black bunny suit, blue bow, '
             'wrist cuffs, fake animal ears, fishnet pantyhose, high heels, '
             'standing, arms crossed under breasts, from side, full body, looking away, '
             'backstage, green room, closed door, no humans, bright lighting, daytime, '
             'cel shading, clean lineart, bright colors'),
    'S009': ('1girl, solo, nsfw, karin (bunny) (blue archive), dark skin, black hair, very long hair, ponytail, '
             'yellow eyes, large breasts, halo, black bunny suit, blue bow, wrist cuffs, '
             'fake animal ears, close-up, portrait, from side, '
             'looking at reflection, backstage, green room, vanity mirror, '
             'bright lighting, cel shading, clean lineart, bright colors'),
}
NEG = 'worst quality, low quality, artist name, blurry, jpeg artifacts, chromatic aberration'


def main():
    rows = {}
    for line in SRC.read_text(encoding='utf-8').splitlines():
        if line.strip():
            r = json.loads(line)
            if r['shot_key'] in TAGS:
                rows[r['shot_key']] = r
    assert len(rows) == len(TAGS), sorted(set(TAGS) - set(rows))

    blocks = []
    for key in sorted(TAGS):
        seed = int(key[1:])  # fixed seed, identical for A and B
        a, b = rows[key]['prompt'], TAGS[key]
        for variant, text in (('A-nl', a), ('B-tag', b)):
            blocks.append(
                f'# {key} {variant} seed={seed} 896x1152 30steps cfg3.5 er_sde\n'
                f'POS: {text}\nNEG: {NEG}\n')
        assert 'quality' not in b and 'score_' not in b, key  # Aesthetic v1.1 needs no quality tags

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'prompts.ab.txt').write_text('\n'.join(blocks), encoding='utf-8')
    wf = json.loads((ROOT / 'pipeline/workflows/anima_aesthetic_v11.json').read_text(encoding='utf-8'))
    assert wf['7']['inputs']['cfg'] == 3.5 and wf['7']['inputs']['steps'] == 30
    assert wf['6']['inputs']['width'] % 16 == 0 and wf['6']['inputs']['height'] % 16 == 0
    print(f'ab: {len(blocks)} prompts -> {OUT / "prompts.ab.txt"}')
    print('workflow:', ROOT / 'pipeline/workflows/anima_aesthetic_v11.json')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
