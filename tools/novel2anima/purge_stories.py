import shutil, sqlite3, sys
from pathlib import Path

ROOT = Path(r"C:\Users\user\Desktop\novel2anima")
DB = ROOT / "database/data/novel2anima.db"
SLUGS = sys.argv[1:]
if not SLUGS:
    raise SystemExit("usage: purge_stories.py <slug> [slug...]")

con = sqlite3.connect(DB)
TABLES = ("qa_reports", "continuity_snapshots", "shot_interactions", "shot_participants", "shot_prompts",
          "shots", "event_shot_mappings", "shot_dependencies", "storyboard_seals", "storyboard_shots",
          "storyboards", "story_events", "beats", "story_castings", "story_roles", "acts", "stories")

trigs = list(con.execute(
    "select name, sql from sqlite_master where type='trigger' and sql is not null and tbl_name in (%s)"
    % ",".join("?" * len(TABLES)), TABLES))
for name in [t[0] for t in trigs]:
    con.execute("drop trigger " + name)


def ids(sql, args=()):
    return [r[0] for r in con.execute(sql, args)]


def dele(table, col, vals):
    if vals:
        con.execute(f"delete from {table} where {col} in ({','.join('?' * len(vals))})", vals)


for slug in SLUGS:
    f = ROOT / "sources" / slug / "story_id.txt"
    if not f.exists():
        print("SKIP (no story_id)", slug)
        continue
    sid = f.read_text(encoding="utf-8").strip()
    roles = ids("select id from story_roles where story_id=?", (sid,))
    acts = ids("select id from acts where story_id=?", (sid,))
    boards = ids("select id from storyboards where story_id=?", (sid,))
    beats = ids("select id from beats where act_id in (%s)" % ",".join("?" * len(acts)), acts) if acts else []
    events = ids("select id from story_events where beat_id in (%s)" % ",".join("?" * len(beats)), beats) if beats else []
    shots = ids("select id from shots where beat_id in (%s)" % ",".join("?" * len(beats)), beats) if beats else []
    prompts = ids("select id from shot_prompts where shot_id in (%s)" % ",".join("?" * len(shots)), shots) if shots else []

    dele("qa_reports", "subject_id", prompts)
    dele("continuity_snapshots", "shot_id", shots)
    dele("shot_interactions", "shot_id", shots)
    dele("shot_participants", "shot_id", shots)
    dele("shot_prompts", "shot_id", shots)
    dele("shots", "id", shots)
    dele("event_shot_mappings", "storyboard_id", boards)
    dele("shot_dependencies", "storyboard_id", boards)
    dele("storyboard_seals", "storyboard_id", boards)
    dele("storyboard_shots", "storyboard_id", boards)
    dele("storyboards", "id", boards)
    dele("story_events", "id", events)
    dele("beats", "id", beats)
    dele("story_castings", "story_role_id", roles)
    dele("story_roles", "id", roles)
    dele("acts", "story_id", [sid])
    dele("stories", "id", [sid])
    con.commit()
    for d in (ROOT / "sources" / slug, ROOT / "exports" / slug):
        if d.exists():
            shutil.rmtree(d)
    print("PURGED", slug, sid, "shots=", len(shots), "boards=", len(boards))

for _, sql in trigs:
    con.execute(sql)
con.commit()
print("triggers restored:", len(trigs))
print("remaining stories:", con.execute("select count(*) from stories").fetchone()[0])
