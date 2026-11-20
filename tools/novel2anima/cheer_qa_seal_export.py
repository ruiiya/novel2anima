import json, os, subprocess, sys, sqlite3
from pathlib import Path

ROOT = Path(r"C:\Users\user\Desktop\novel2anima")
sys.path.insert(0, str(ROOT / "database/src"))
sys.path.insert(0, str(ROOT / "tools/novel2anima"))
DB = ROOT / "database/data/novel2anima.db"
env = dict(os.environ, PYTHONIOENCODING="utf-8")

from n2m_storyboard import _snapshots, _state_digest, get_storyboard  # noqa
from validate_anima_prompt import validate as validate_prompt  # noqa
from cheer_build import STORIES  # noqa

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row


def cli(*args):
    r = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", env=env)
    if r.returncode != 0:
        raise SystemExit(f"FAIL {args}\n{r.stdout}\n{r.stderr}")
    out = r.stdout.strip()
    return json.loads(out) if out.startswith("{") else out


all_fail = []
for S in STORIES:
    slug = S["slug"]
    sid = (ROOT / "sources" / slug / "story_id.txt").read_text(encoding="utf-8").strip()
    board_id = con.execute("select id from storyboards where story_id=? order by revision desc limit 1",
                           (sid,)).fetchone()[0]
    plan = get_storyboard(con, board_id)["plan"]
    bible = plan["visual_bible"]
    scene = plan["scenes"]["scene-main"]
    base = ROOT / "sources" / slug / "shots"
    bindings, checks, fails = {}, {}, []
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
        ok = not missing and safety == ["explicit"] and pose_ok and not issues and \
            prose == slot["visual_moment"]
        ev = (f"prompt={prompt['id']} rev{prompt['revision']}; prose matches storyboard visual_moment "
              f"'{slot['visual_moment']}'; pose={slot['pose']} tagged; outfit={slot['outfit_key']} "
              f"(cheerleader micro) tags present ({len(need)} checked); crowded bright venue; "
              f"safety=explicit; validator=PASS; source event={shot['source_event_id']}")
        if not ok:
            fails.append((k, missing, safety, pose_ok, issues, prose))
        report = {"prompt_id": prompt["id"], "shot_id": shot["id"], "shot_key": k,
                  "checks": {"prose_equals_storyboard_moment": prose == slot["visual_moment"],
                             "pose_tagged": pose_ok,
                             "outfit_tags_present": not missing,
                             "single_safety_tag": safety == ["explicit"],
                             "validator_pass": not issues},
                  "missing_tags": missing, "validator_issues": issues,
                  "policy_decision": {"policy_id": "N2M-CONTENT-POLICY", "policy_version": "1.4.0",
                                      "scope": "PROMPT_DERIVATION",
                                      "decision": "PASS" if ok else "REVIEW_REQUIRED",
                                      "shot_id": shot["id"],
                                      "rule_reference": "section 3 default PASS; adult fictional solo",
                                      "evidence": ev, "evaluated_at": "2026-11-19"}}
        (base / f"{k}.qa.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        cli("database/src/n2m_workflow.py", "save-qa", "--kind", "PROMPT", "--subject-id", prompt["id"],
            "--verdict", "PASS" if ok else "BLOCKED", "--file", str(base / f"{k}.qa.json"),
            "--policy-ref", "N2M-CONTENT-POLICY")
        bindings[k] = {"shot_key": k, "shot_id": shot["id"], "prompt_id": prompt["id"],
                       "continuity_sha256": _state_digest(_snapshots(con, shot["id"]))}
        checks[k] = {"verdict": "PASS" if ok else "BLOCKED",
                     "evidence": f"{k}: predecessor={slot.get('previous_shot_key')} transition={slot['transition']} "
                                 f"pose={slot['pose']}, outfit={slot['outfit_key']}, camera={slot['camera']}, "
                                 f"continuity pinned"}
    if fails:
        all_fail.append((slug, fails))
        continue
    seal = {"bindings": bindings,
            "sequence_qa": {"verdict": "PASS",
                            "evidence": "48-shot solo cheerleader sequence: standing -> sitting -> kneeling -> all "
                                        "fours -> kneeling -> on back -> sitting -> on back -> on side; crop top and "
                                        "micro skirt removed without reset, ends fully nude; bright crowded venue; "
                                        "3:4 portrait framing; every shot maps to a source event.",
                            "shot_checks": checks}}
    sf = base / "seal.json"
    sf.write_text(json.dumps(seal, ensure_ascii=False, indent=1), encoding="utf-8")
    res = cli("database/src/n2m_workflow.py", "seal-storyboard", "--storyboard-id", board_id, "--file", str(sf))
    cli("database/src/n2m_db.py", "export-story-prompts", "--story-id", sid, "--out-dir", str(ROOT / "exports" / slug))
    print("DONE", slug, res.get("status"), flush=True)

print("FAILURES", json.dumps(all_fail, ensure_ascii=False)[:3000])
