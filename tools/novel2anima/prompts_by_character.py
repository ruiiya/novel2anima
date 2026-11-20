import json
from pathlib import Path

ROOT = Path(r"C:\Users\user\Desktop\novel2anima\exports")
OUT = ROOT / "by_character"
OUT.mkdir(exist_ok=True)

PARTNER_OF = {"neru": "serika", "hifumi": "koharu", "serika": "kayoko",
              "kayoko": "koharu", "koharu": "neru"}

CHAR = {}
for d in ROOT.iterdir():
    if not d.is_dir() or not (d / "prompts.all.jsonl").exists():
        continue
    slug = d.name
    key = slug.split("_")[0]
    name = {"indigo": "raiden", "hotel": "kafka", "casino": "yelan", "rain": "acheron",
            "unit": "2b"}.get(key, key)
    CHAR.setdefault(name, []).append(slug)
    # couple stories also appear in the partner's file: same prompt features both women
    if key in PARTNER_OF:
        CHAR.setdefault(PARTNER_OF[key], []).append(slug)

ORDER = ["raiden", "kafka", "yelan", "acheron", "2b", "karin", "hina", "toki", "seia", "mari", "asuna",
         "neru", "hifumi", "serika", "kayoko", "koharu", "iori", "ako", "chinatsu"]
for name in ORDER + sorted(set(CHAR) - set(ORDER)):
    slugs = sorted(CHAR.get(name, []))
    if not slugs:
        continue
    prompts = []
    for slug in slugs:
        rows = [json.loads(l) for l in (ROOT / slug / "prompts.all.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        rows.sort(key=lambda r: r["shot_order"])
        prompts += [r["prompt"] for r in rows]
    text = "\n\n".join(prompts) + "\n"
    (OUT / f"{name}.prompt.all.txt").write_text(text, encoding="utf-8", newline="\n")
    print(name, len(slugs), "stories", len(prompts), "prompts")
