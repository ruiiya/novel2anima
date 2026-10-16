# -*- coding: utf-8 -*-
"""Goi y tag NGOAI bo tag goc cua shot, dua vao quan he trong catalog (khong bia tag).

Usage:
  python etl/suggest_tags.py --tag thighhighs [--limit 15]
  python etl/suggest_tags.py --shot 1234 [--limit 15]      # shot_id trong bang shot
  python etl/suggest_tags.py --act 13 [--limit 15]

Nguon:
  * tag_relation: implies (tag nay keo theo gi), compatible (hay di cung, do tu lift
    co-occurrence trong posts.csv), recommends (wiki "related tags"),
  * concept_tag usage='optional'/'alternative' cua concept gan voi tag trong shot
    (vd concept WC_thighhighs -> cac bien the mau),
  * tag_role de loc theo vai tro (outfit/pose/expression...).
Ket qua in ra "ten:id  pc=...  nguon" de dan thang vao plan.
"""
import argparse, collections, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REL = ("compatible", "recommends", "implies")

def shot_tags(con, shot_id):
    spec = con.execute("SELECT shot_spec_json FROM shot WHERE id=?", (shot_id,)).fetchone()
    if not spec:
        raise SystemExit("khong co shot id=%s" % shot_id)
    spec = json.loads(spec[0])
    out = {}
    for group in ("identity", "outfit", "action", "expression", "pose", "motion", "camera", "cast"):
        for x in spec.get(group) or []:
            out[x["tagId"]] = x["name"]
    return out

def act_tags(con, act_no):
    rows = con.execute("SELECT id FROM shot WHERE act_id=(SELECT id FROM act WHERE act_no=? ORDER BY id DESC LIMIT 1)",
                       (act_no,)).fetchall()
    out = {}
    for (sid,) in rows:
        out.update(shot_tags(con, sid))
    return out

def suggest(con, tags, limit, roles=None):
    """tags: {tag_id: name} da co trong shot -> [(name, id, pc, diem, nguon)]"""
    have = set(tags)
    score = collections.Counter()
    why = {}
    for tid in have:
        for rel, t2, name, pc, w in con.execute(
                "SELECT r.relation, r.to_tag_id, t.canonical_name, t.post_count, r.weight"
                " FROM tag_relation r JOIN tag t ON t.id=r.to_tag_id WHERE r.from_tag_id=?", (tid,)):
            if t2 in have or t2 in score and score[t2, rel] > w:
                continue
            score[(t2, rel)] += 1 + min(w or 1.0, 50) / 50.0
            why[t2] = "%s <- %s" % (rel, tags[tid])
        for t2, name, pc in con.execute(
                "SELECT ct.tag_id, t.canonical_name, t.post_count FROM concept_tag ct"
                " JOIN tag t ON t.id=ct.tag_id"
                " WHERE ct.usage IN ('optional','alternative') AND ct.concept_id IN"
                " (SELECT concept_id FROM concept_tag WHERE tag_id=?) AND ct.tag_id NOT IN"
                " (SELECT tag_id FROM concept_tag WHERE concept_id IN"
                "  (SELECT concept_id FROM concept_tag WHERE tag_id=?) AND usage='primary')", (tid, tid)):
            score[(t2, "concept")] += 0.5
            why.setdefault(t2, "concept cua %s" % tags[tid])
    best = {}
    for (tid, rel), s in score.items():
        if tid not in best or s > best[tid][0]:
            best[tid] = (s, why.get(tid, rel))
    rows = con.execute("SELECT id, canonical_name, post_count, (SELECT group_concat(role) FROM tag_role"
                       " WHERE tag_id=tag.id) FROM tag WHERE id IN (%s)"
                       % ",".join(str(t) for t in best) or "0").fetchall() if best else []
    out = []
    for tid, name, pc, role in rows:
        if roles and not (set((role or "").split(",")) & roles):
            continue
        out.append((best[tid][0], name, tid, pc, best[tid][1], role or "-"))
    out.sort(key=lambda x: (-x[0], -x[3]))
    return out[:limit]

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag")
    ap.add_argument("--shot", type=int)
    ap.add_argument("--act", type=int)
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--role", help="loc theo vai tro, vd outfit,pose")
    args = ap.parse_args(argv)
    con = build.connect(build.DB_PATH)

    if args.tag:
        row = con.execute("SELECT id FROM tag WHERE canonical_name=?", (args.tag,)).fetchone()
        if not row:
            raise SystemExit("tag khong co trong catalog: %s" % args.tag)
        tags = {row[0]: args.tag}
        print("tu tag: %s" % args.tag)
    elif args.shot:
        tags = shot_tags(con, args.shot)
        print("shot %d: %d tag" % (args.shot, len(tags)))
    elif args.act:
        tags = act_tags(con, args.act)
        print("act %d: %d tag" % (args.act, len(tags)))
    else:
        raise SystemExit("can --tag, --shot hoac --act")

    roles = set(args.role.split(",")) if args.role else None
    for s, name, tid, pc, why, role in suggest(con, tags, args.limit, roles):
        print("  %-28s %-8s pc=%-9d %-14s %s" % (name, ":%d" % tid, pc, role, why))
    con.close()

if __name__ == "__main__":
    main()
