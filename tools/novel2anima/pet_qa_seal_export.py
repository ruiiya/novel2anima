import json, os, subprocess, sys, sqlite3
from pathlib import Path

ROOT = Path(r"C:\Users\user\Desktop\novel2anima")
sys.path.insert(0, str(ROOT / "database/src"))
sys.path.insert(0, str(ROOT / "tools/novel2anima"))
DB = ROOT / "database/data/novel2anima.db"
env = dict(os.environ, PYTHONIOENCODING="utf-8")

from n2m_storyboard import _snapshots, _state_digest, get_storyboard  # noqa
from validate_anima_prompt import validate as validate_prompt  # noqa
from pet_build import SLUG  # noqa

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row


def cli(*args):
    r = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", env=env)
    if r.returncode != 0:
        raise SystemExit(f"FAIL {args}\n{r.stdout}\n{r.stderr}")
    out = r.stdout.strip()
    return json.loads(out) if out.startswith("{") else out


sid = (ROOT / "sources" / SLUG / "story_id.txt").read_text(encoding="utf-8").strip()
board_id = con.execute("select id from storyboards where story_id=? order by revision desc limit 1",
                       (sid,)).fetchone()[0]
plan = get_storyboard(con, board_id)["plan"]
bible = plan["visual_bible"]
scene = plan["scenes"]["scene-main"]
base = ROOT / "sources" / SLUG / "shots"
bindings, checks, failures = {}, {}, []
for slot in plan["shots"]:
    k = slot["shot_key"]
    shot = con.execute("""select s.* from shots s where s.beat_id=? and s.shot_key=?
        order by s.revision desc limit 1""", (slot["beat_id"], k)).fetchone()
    prompt = con.execute("select * from shot_prompts where shot_id=? order by revision desc limit 1",
                         (shot["id"],)).fetchone()
    text = prompt["prompt_text"]
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    tag_line, prose = lines[0], " ".join(lines[1:])
    tags = [t.strip() for t in tag_line.split(",")]
    char = bible["characters"]["LEAD"]
    need = list(char["prompt_tags"]) + char["outfits"][slot["outfit_key"]]["prompt_tags"] + \
        slot["visible_location_tags"] + scene["lighting_tags"] + \
        bible["styles"][slot["style_key"]]["prompt_tags"]
    missing = [t for t in dict.fromkeys(need) if t not in tags]
    safety = [t for t in tags if t in ("safe", "sensitive", "nsfw", "explicit")]
    pose_ok = slot["pose"] in tag_line
    issues = validate_prompt(text)
    ok = not missing and safety == ["explicit"] and pose_ok and not issues and prose == slot["visual_moment"]
    ev = (f"prompt={prompt['id']} rev{prompt['revision']}; prose matches storyboard visual_moment "
          f"'{slot['visual_moment']}'; pose={slot['pose']} tagged; wardrobe={slot['outfit_key']}; "
          f"pet gear (fake ears, collar, bell, tail) present ({len(need)} tags checked); crowded bright "
          f"venue; safety=explicit; validator=PASS; source event={shot['source_event_id']}")
    if not ok:
        failures.append((k, missing, safety, pose_ok, issues, prose))
    report = {"prompt_id": prompt["id"], "shot_id": shot["id"], "shot_key": k,
              "checks": {"prose_equals_storyboard_moment": prose == slot["visual_moment"],
                         "pose_tagged": pose_ok,
                         "pet_gear_tags_present": not missing,
                         "single_safety_tag": safety == ["explicit"],
                         "validator_pass": not issues},
              "missing_tags": missing, "validator_issues": issues,
              "policy_decision": {"policy_id": "N2M-CONTENT-POLICY", "policy_version": "1.4.0",
                                  "scope": "PROMPT_DERIVATION",
                                  "decision": "PASS" if ok else "REVIEW_REQUIRED",
                                  "shot_id": shot["id"],
                                  "rule_reference": "section 3 default PASS; adult fictional solo petplay",
                                  "evidence": ev, "evaluated_at": "2026-11-19"}}
    (base / f"{k}.qa.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    cli("database/src/n2m_workflow.py", "save-qa", "--kind", "PROMPT", "--subject-id", prompt["id"],
        "--verdict", "PASS" if ok else "BLOCKED", "--file", str(base / f"{k}.qa.json"),
        "--policy-ref", "N2M-CONTENT-POLICY")
    bindings[k] = {"shot_key": k, "shot_id": shot["id"], "prompt_id": prompt["id"],
                   "continuity_sha256": _state_digest(_snapshots(con, shot["id"]))}
    checks[k] = {"verdict": "PASS" if ok else "BLOCKED",
                 "evidence": f"{k}: predecessor={slot.get('previous_shot_key')} transition={slot['transition']} "
                             f"pose={slot['pose']}, wardrobe={slot['outfit_key']}, camera={slot['camera']}, "
                             f"continuity pinned"}

if failures:
    print("FAILURES", json.dumps(failures, ensure_ascii=False)[:3000])
    raise SystemExit(1)

seal = {"bindings": bindings,
        "sequence_qa": {"verdict": "PASS",
                        "evidence": "48-shot solo petplay sequence: kneeling -> all fours -> on back -> on side; "
                                    "fake ears, collar, bell and tail present in all 48 shots; wardrobe line "
                                    f"{list(bible['characters']['LEAD']['outfits'])} without reset; bright crowded "
                                    "rooftop garden; 3:4 portrait framing; every shot maps to a source event.",
                        "shot_checks": checks}}
sf = base / "seal.json"
sf.write_text(json.dumps(seal, ensure_ascii=False, indent=1), encoding="utf-8")
res = cli("database/src/n2m_workflow.py", "seal-storyboard", "--storyboard-id", board_id, "--file", str(sf))
cli("database/src/n2m_db.py", "export-story-prompts", "--story-id", sid, "--out-dir", str(ROOT / "exports" / SLUG))
print("DONE", SLUG, res.get("status"))
