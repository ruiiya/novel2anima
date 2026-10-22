# novel2anima P0P1 upgrade
# -*- coding: utf-8 -*-
"""LLM self-check cho prompt cua mot act: gui tung batch shot cho mot LLM qua stdin,
doc JSON tra ve va (tuy chon) ghi vao shot_finding source='qa:llm:v1'.

Usage:
  python etl/llm_review.py --act 13                  # chay + in ket qua (dry-run)
  python etl/llm_review.py --act 13 --apply          # ghi shot_finding + data/reviews/
  python etl/llm_review.py --act 13 --payload        # chi in payload (agent/nguoi tu review)
  python etl/llm_review.py --act 13 --from-json f.json --apply

Mac dinh LLM = codex CLI:  codex exec --sandbox read-only -o <tmp> -   (prompt qua stdin)
Doi bang --cmd "lenh doc stdin, tra JSON ra stdout".
"""
import argparse, collections, json, pathlib, re, subprocess, sys, tempfile

from novel2anima.paths import REVIEWS_DIR
from novel2anima.catalog import build_service as build
from novel2anima.storage import story_repository as story_db

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SOURCE = "qa:llm:v1"
REVIEW_DIR = REVIEWS_DIR
DEFAULT_CMD = "codex exec --sandbox read-only -c model_reasoning_effort=low -o {out} -"
AXES = ("y_nghia", "mau_thuan", "danh_tinh", "tiep_dien", "gia_tao", "thieu", "khac")
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["findings"],
          "properties": {"findings": {"type": "array", "items": {
              "type": "object", "additionalProperties": False,
              "required": ["shot", "axis", "severity", "why"],
              "properties": {"shot": {"type": "integer"}, "axis": {"type": "string"},
                             "severity": {"type": "number"}, "why": {"type": "string"}}}}}}

INSTRUCT = """Ban soat chat luong prompt anh (Anima/Danbooru tag + caption) cua mot act truyen
nguoi lon. Day la kiem tra ky thuat, khong phai danh gia dao duc: chi tim LOI trong prompt.

Luat:
- Chi bao loi THAT: prompt khong khop beat/caption, tag mau thuan nhau, tag gan sai nhan vat
  (shot nhieu nguoi), trang thai bi reset (dich/marks/quan ao), caption mau thuan voi tag,
  thieu chi tiet ma beat yeu cau, tag/cau toi nghia model de hieu sai.
- Khong bao loi: thieu tag trang tri, so thich nghe thuat, y kien lam dep.
- Dung dung ten tag co trong du lieu; khong bia tag.
- axis thuoc: %s
- severity 0.2 (nhe, ghi chu) .. 1.0 (sai nghiem trong, phai sua truoc khi render).
- Truoc khi bao, phai doc lai chuoi prompt that su: khong bao 'tag lap/trung' khi chu do chi
  xuat hien trong caption; neu bao lap thi trich dung ten tag.
- Khong co loi -> findings = [].
Tra ve DUY NHAT JSON, dung 4 khoa: {"findings":[{"shot":<so shot>,"axis":"<axis>","severity":<0.0-1.0>,"why":"<ly do, gom moi chi tiet>"}]}

Du lieu mot act (moi dong: shot | phase | participants | beat | caption | tags):
""" % "/".join(AXES)

def payload(con, act_no, batch, project=None, revision=None):
    aid = story_db.resolve_act(con, act_no, project, revision)
    rows = con.execute("SELECT shot_no, shot_spec_json FROM shot WHERE act_id=? ORDER BY shot_no",
                       (aid,)).fetchall()
    out = []
    for i in range(0, len(rows), batch):
        lines = []
        # Two-shot context overlap; findings must only target CURRENT batch.
        context = rows[max(0, i - 2):i]
        if context:
            lines.append("CONTEXT ONLY (do not report findings for these shots):")
            for ctx_no, ctx_json in context:
                ctx = json.loads(ctx_json)
                lines.append("CONTEXT %d | %s | %s" % (ctx_no, ctx.get("caption", ""), ctx.get("beat", "")))
            lines.append("CURRENT BATCH:")
        for shot_no, spec_json in rows[i:i + batch]:
            spec = json.loads(spec_json)
            tags = [x["name"] for g in ("identity", "outfit", "action", "expression", "pose",
                                        "motion", "camera", "cast") for x in spec.get(g) or []]
            lines.append("%d | %s | %s | %s | %s | %s" % (
                shot_no, spec.get("phase", ""),
                ",".join(p.get("code", "") for p in spec.get("participants") or []),
                spec.get("beat", ""), spec.get("caption", ""), ", ".join(tags)))
        out.append((rows[i][0], INSTRUCT + "\n".join(lines)))
    return aid, out

def ask(cmd, text, timeout):
    with tempfile.TemporaryDirectory() as td:
        out_file = pathlib.Path(td) / "last.json"
        argv = cmd.replace("{out}", str(out_file))
        p = subprocess.run(argv, input=text, capture_output=True, text=True, encoding="utf-8",
                           shell=True, timeout=timeout)
        body = out_file.read_text(encoding="utf-8") if out_file.exists() else p.stdout
    if not body or not body.strip():
        raise SystemExit("LLM khong tra ve gi (exit %s): %s" % (p.returncode, (p.stderr or "")[-300:]))
    m = re.findall(r"\{.*\}", body, re.S)
    if not m:
        raise SystemExit("khong thay JSON trong tra loi: %s" % body[:200])
    return json.loads(m[-1])

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--act", type=int)
    ap.add_argument("--project")
    ap.add_argument("--revision", type=int)
    ap.add_argument("--db", default=build.DB_PATH)
    ap.add_argument("--replay", action="store_true",
                    help="nap lai findings tu data/reviews/*.json (khong goi LLM)")
    ap.add_argument("--batch", type=int, default=20, help="so shot moi lan goi LLM")
    ap.add_argument("--cmd", default=DEFAULT_CMD)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--payload", action="store_true", help="chi in payload")
    ap.add_argument("--from-json", help="doc findings tu file thay vi goi LLM")
    ap.add_argument("--apply", action="store_true", help="ghi vao shot_finding")
    args = ap.parse_args(argv)

    con = build.connect(args.db)
    if args.replay:                      # seed lai act -> cascade xoa shot_state: nap lai tu report
        if args.act:
            files = sorted(REVIEW_DIR.glob("act%02d_id*_llm.json" % args.act))
            if not files:
                files = [REVIEW_DIR / ("act%02d_llm.json" % args.act)]
        else:
            files = sorted(REVIEW_DIR.glob("act*_id*_llm.json"))
            seen_no = {f.name.split("_id")[0] for f in files}
            files += [f for f in sorted(REVIEW_DIR.glob("act*_llm.json"))
                      if f.name.removesuffix("_llm.json") not in seen_no]
        con.isolation_level = None
        con.execute("BEGIN")
        # Clear per act only, after resolving the exact act for every replay file.
        total = 0
        for f in files:
            d = json.loads(f.read_text(encoding="utf-8"))
            act_no = d["act"]
            try:
                replay_id = int(d.get("act_id")) if d.get("act_id") is not None else story_db.resolve_act(
                    con, act_no, args.project, args.revision)
                row = con.execute("SELECT id FROM act WHERE id=? AND act_no=?", (replay_id, act_no)).fetchone()
            except ValueError as exc:
                raise SystemExit(str(exc))
            if not row:
                print("bo qua %s: act %s khong co trong db" % (f.name, act_no))
                continue
            story_db.clear_findings_for_act(con, SOURCE, row[0])
            shots = {r[0]: r[1] for r in con.execute("SELECT shot_no, id FROM shot WHERE act_id=?",
                                                     (row[0],))}
            for x in d["findings"]:
                if x["shot"] not in shots:
                    continue
                story_db.record_finding(con, shots[x["shot"]], "llm:" + x["axis"], SOURCE,
                                        x["severity"], axis="llm:" + x["axis"],
                                        evidence={"shot": x["shot"], "why": x.get("why", "")})
                total += 1
            print("act %02d: %d dong" % (act_no, len(d["findings"])))
        con.commit()
        print("shot_finding: %d dong (source=%s)" % (total, SOURCE))
        return 0
    if not args.act:
        ap.error("can --act hoac --replay")
    aid, chunks = payload(con, args.act, args.batch, args.project, args.revision)
    if args.payload:
        for _first, text in chunks:
            print(text + "\n" + "=" * 70)
        return 0
    if args.from_json:
        found = json.loads(pathlib.Path(args.from_json).read_text(encoding="utf-8"))
        findings = found.get("findings", found)
    else:
        findings = []
        for first, text in chunks:
            print("hoi LLM batch tu shot %s (%d ky tu)..." % (first, len(text)))
            findings += ask(args.cmd, text, args.timeout).get("findings", [])

    shots = {r[0]: r[1] for r in con.execute("SELECT shot_no, id FROM shot WHERE act_id=?", (aid,))}
    findings = [f for f in findings if f.get("shot") in shots]
    for f in findings:                      # LLM co the doi ten khoa -> chuan hoa
        f["axis"] = str(f.get("axis") or "khac")
        f["axis"] = f["axis"] if f["axis"] in AXES else "khac"
        f["severity"] = max(0.0, min(1.0, float(f.get("severity") or 0.5)))
        extra = [str(v) for k, v in f.items() if k not in ("shot", "axis", "severity") and v]
        f["why"] = " | ".join(extra)[:400]      # LLM hay doi ten khoa giai thich
    findings.sort(key=lambda f: -f["severity"])
    print("act %02d: %d phat hien" % (args.act, len(findings)))
    for f in findings:
        print("  shot %-4s sev %.1f  %-10s %s" % (f["shot"], f["severity"], f["axis"], f["why"][:110]))
    REPORT_DIR = REVIEW_DIR
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    raw = REPORT_DIR / ("act%02d_id%d_llm.json" % (args.act, aid))
    raw.write_text(json.dumps({"act": args.act, "act_id": aid, "findings": findings}, ensure_ascii=False, indent=1),
                   encoding="utf-8", newline="\n")
    print("luu: %s" % raw)
    if not args.apply:
        print("dry-run: them --apply de ghi shot_finding")
        return 0
    con.isolation_level = None
    con.execute("BEGIN")
    story_db.clear_findings_for_act(con, SOURCE, aid)
    for f in findings:
        story_db.record_finding(con, shots[f["shot"]], "llm:" + f["axis"], SOURCE,
                                f["severity"], axis="llm:" + f["axis"],
                                evidence={"shot": f["shot"], "why": f.get("why", "")})
    con.commit()
    print("shot_finding: %d dong (source=%s)" % (len(findings), SOURCE))
    con.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
