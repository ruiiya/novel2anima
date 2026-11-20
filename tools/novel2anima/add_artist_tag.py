import json, os, subprocess, sys, sqlite3
from pathlib import Path

ROOT = Path(r"C:\Users\user\Desktop\novel2anima")
DB = ROOT / "database/data/novel2anima.db"
env = dict(os.environ, PYTHONIOENCODING="utf-8")
ARTIST = "@anjing"

STORIES = [("story_3fbb888ae9c145a98d", "indigo_boudoir_raiden"),
           ("story_bf1edb8c91ef4d709a", "hotel_noir_kafka"),
           ("story_a790370aa95d437690", "casino_backroom_yelan"),
           ("story_6a9f78c5f3164aa8b0", "rain_glass_acheron"),
           ("story_6dece8543bd349dc8b", "unit_maintenance_2b")]

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

for sid, slug in STORIES:
    row = con.execute("select id, plan_json from storyboards where story_id=? order by revision desc limit 1",
                      (sid,)).fetchone()
    plan = json.loads(row["plan_json"])
    styles = plan["visual_bible"]["styles"]
    for spec in styles.values():
        tags = spec.setdefault("prompt_tags", [])
        if ARTIST not in tags:
            tags.append(ARTIST)
    sf = ROOT / "sources" / slug / "storyboard_v5.json"
    sf.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    r = subprocess.run([sys.executable, "database/src/n2m_workflow.py", "save-storyboard",
                        "--story-id", sid, "--file", str(sf)],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=env)
    print(slug, r.returncode, r.stdout.strip()[-160:], r.stderr.strip()[-160:])
