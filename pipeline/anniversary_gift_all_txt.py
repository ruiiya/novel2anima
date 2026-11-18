import json, pathlib

ROOT = pathlib.Path("exports/anniversary_gift")
shots = json.loads((ROOT / "shots.json").read_text(encoding="utf-8"))
board = json.loads((ROOT / "storyboard.draft.json").read_text(encoding="utf-8"))
cam = {s["shot_key"]: s["camera"] for s in board["shots"]}
safety_tags = ("safe", "sensitive", "nsfw", "explicit")
lines = []
for i in range(1, 123):
    key = f"S{i:03d}"
    text = (ROOT / "prompts" / f"{key}.txt").read_text(encoding="utf-8").strip()
    tag_line = text.splitlines()[0]
    safety = next((t for t in safety_tags if t in [x.strip() for x in tag_line.split(",")]), "?")
    lines.append(f"### {key} | {shots[key]['beat_key']} | {safety} | {cam[key]}")
    lines.append(text)
    lines.append("")
(ROOT / "prompts.all.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("wrote", ROOT / "prompts.all.txt", "blocks", 122)
