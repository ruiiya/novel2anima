# -*- coding: utf-8 -*-
"""Assert the catalog is safe to reshape: re-seed every plan and check nothing drifts.

Usage: python etl/check_reseed.py

Guards the whole ingestion/curation work: after any DB edit (prune, alias cleanup,
post_count refresh) the prompts must regenerate byte-identical from data/plans/*.json,
no plan ref may go unknown, no alias may shadow a real tag, and the FKs must stay clean.
"""
import glob, hashlib, json, os, sqlite3, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "etl"))
import build

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
md5 = lambda p: hashlib.md5(open(p, "rb").read()).hexdigest()

files = sorted(glob.glob("prompts/*.txt"))
before = {f: md5(f) for f in files}
db0 = sqlite3.connect(build.DB_PATH)
seeded = {r[0] for r in db0.execute("SELECT DISTINCT act_no FROM act")}
db0.close()
failed, pending = [], []
for plan in sorted(glob.glob("data/plans/*.json")):
    d = json.load(open(plan, encoding="utf-8-sig")) or {}
    if d.get("act", {}).get("act_no") not in seeded:   # plan chua vao db -> khong phai viec cua check nay
        pending.append(os.path.basename(plan))
        continue
    pf = d.get("prompt_file")
    if not pf or not os.path.exists(pf):
        pending.append(os.path.basename(plan))
        continue
    r = subprocess.run([sys.executable, "etl/seed_plan.py", plan], capture_output=True, text=True)
    if r.returncode or "UNKNOWN" in r.stdout:
        failed.append((plan, r.returncode, (r.stdout or r.stderr)[-160:]))
changed = [f for f in files if before[f] != md5(f)]
subprocess.run([sys.executable, "etl/qa_shots.py", "--apply"], capture_output=True)  # seed lai shot -> shot_state bi cascade
subprocess.run([sys.executable, "etl/llm_review.py", "--replay"], capture_output=True)  # nap lai findings LLM
r = subprocess.run([sys.executable, "etl/check_prompts.py", "--examples", "0"], capture_output=True,
               text=True, encoding="utf-8")   # tu soat prompt vua sinh lai
prompt_detail = ((r.stdout or r.stderr).strip().splitlines() or ["khong co output"])[-1]

con = sqlite3.connect(build.DB_PATH)
shadowed = con.execute("SELECT count(*) FROM tag_alias a JOIN tag t ON t.canonical_name=a.alias_name").fetchone()[0]
fk = con.execute("PRAGMA foreign_key_check").fetchall()
con.close()

checks = [
    ("seed_plan runs", not failed, failed),
    ("prompts byte-identical", not changed, changed),
    ("alias khong shadow tag", shadowed == 0, shadowed),
    ("foreign_key_check", not fk, fk),
    ("ke hoach chua seed (bo qua)", True, "%d: %s" % (len(pending), ", ".join(pending))),
    ("prompt self-check", r.returncode == 0, prompt_detail),
]
for name, ok, detail in checks:
    print(("OK   " if ok else "FAIL ") + "%-24s %s" % (name, detail if detail else ""))
bad = [n for n, ok, _ in checks if not ok]
print("%d checks, %d failed" % (len(checks), len(bad)))
sys.exit(1 if bad else 0)
