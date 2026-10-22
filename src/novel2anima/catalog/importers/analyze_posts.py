# -*- coding: utf-8 -*-
"""Thong ke tu posts dump cua Danbooru -> cap nhat tag.post_count, tag_content_label,
tag_relation(relation=compatible) va liet ke tag la (co trong posts, chua co trong db).

Usage: python etl/analyze_posts.py [--file PATH] [--limit N] [--min-pair 50] [--min-label 100] [--dry-run]

1 pass duy nhat, doc tuan tu (khong parallel vi CSV co field chua newline).
Co-occurrence chi tinh trong vocab = tag cua TG_* concept + tag co tag_role.
"""
import argparse
import collections
import csv
import os
import pathlib
import sys
import time

from novel2anima.paths import DATA_DIR, SOURCES_DIR
from novel2anima.catalog import build_service as build

DEFAULT_FILE = os.path.join(os.environ.get("N2A_DATA_DIR", str(DATA_DIR / "imports")), "posts.csv")
UNKNOWN_OUT = str(SOURCES_DIR / "posts_unknown_tags.txt")
SOURCE_KEY = "danbooru_dump_posts"
LICENSE = "Danbooru official posts CSV dump; only derived statistics are stored."
csv.field_size_limit(1 << 24)
BUCKET = {"g": 0, "s": 1, "q": 2, "e": 3}


def snapshot(con, path):
    digest = build.sha256_file(path)
    rev = digest[:16]
    row = con.execute("SELECT id FROM source_snapshot WHERE source_key=? AND revision=?",
                      (SOURCE_KEY, rev)).fetchone()
    if row:
        return row[0], rev
    cur = con.execute(
        "INSERT INTO source_snapshot(source_key, source_url, revision, license_note, sha256)"
        " VALUES(?,?,?,?,?)",
        (SOURCE_KEY, "file:///" + pathlib.Path(path).as_posix(), rev, LICENSE, digest))
    return cur.lastrowid, rev


def scan(con, path, limit, pair_every=1):
    known = {r[0] for r in con.execute("SELECT canonical_name FROM tag")}
    tag_names = [r[0] for r in con.execute(
        "SELECT DISTINCT t.canonical_name FROM tag t"
        " JOIN concept_tag ct ON ct.tag_id=t.id"
        " JOIN visual_concept c ON c.id=ct.concept_id WHERE c.code LIKE 'TG_%'")]
    role_names = [r[0] for r in con.execute(
        "SELECT DISTINCT t.canonical_name FROM tag t JOIN tag_role r ON r.tag_id=t.id")]
    vidx = {name: i for i, name in enumerate(sorted(set(tag_names) | set(role_names)))}  # rating
    pidx = {name: i for i, name in enumerate(sorted(tag_names))}                        # pair
    V = len(pidx)
    counts = collections.Counter()
    rating = {}
    pairs = {}
    unknown = collections.Counter()
    posts = deleted = 0
    ep = time.time()
    with open(path, encoding="utf-8", newline="", errors="replace") as fh:
        rd = csv.reader(fh)
        head = next(rd)
        it = head.index("tag_string")
        ir = head.index("rating")
        ild = head.index("is_deleted")
        for row in rd:
            posts += 1
            do_pair = (posts % max(pair_every, 1) == 0)
            if limit and posts > limit:
                break
            if row[ild] == "t":
                deleted += 1
            rb = BUCKET.get(row[ir], 3)
            local = []
            for t in row[it].split():
                if t not in known:
                    unknown[t] += 1
                    continue
                counts[t] += 1
                j = vidx.get(t)
                if j is None:
                    continue
                jp = pidx.get(t)
                if jp is not None:
                    local.append(jp)
                b = rating.get(j)
                if b is None:
                    b = rating[j] = [0, 0, 0, 0]
                b[rb] += 1
            if not do_pair:
                continue
            if len(local) > 40:
                local = local[:40]
            local.sort()
            for a in range(len(local)):
                ia = local[a]
                for b in range(a + 1, len(local)):
                    k = ia * V + local[b]
                    pairs[k] = pairs.get(k, 0) + 1
    return dict(V=V,
                rating_names=[n for n, _i in sorted(vidx.items(), key=lambda kv: kv[1])],
                pair_names=[n for n, _i in sorted(pidx.items(), key=lambda kv: kv[1])],
                counts=counts, rating=rating, pairs=pairs, unknown=unknown,
                posts=posts, deleted=deleted, elapsed=time.time() - ep, pair_every=pair_every)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--min-pair", type=int, default=50)
    ap.add_argument("--min-label", type=int, default=100)
    ap.add_argument("--pair-every", type=int, default=4, help="chi dem pair moi N post")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if not os.path.exists(args.file):
        raise SystemExit("missing: %s" % args.file)

    con = build.connect(build.DB_PATH)
    con.isolation_level = None
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    res = scan(con, args.file, args.limit, args.pair_every)
    print("posts=%d (deleted=%d) trong %.1fs | tag khop=%d | token la=%d | cap=%d"
          % (res["posts"], res["deleted"], res["elapsed"], len(res["counts"]),
             len(res["unknown"]), len(res["pairs"])))
    if args.dry_run:
        print("top tag:", res["counts"].most_common(5))
        print("top token la:", res["unknown"].most_common(5))
        return

    snap_id, rev = snapshot(con, args.file)
    con.execute("DROP TABLE IF EXISTS _pt")
    con.execute("CREATE TEMP TABLE _pt(name TEXT PRIMARY KEY, n INT)")
    con.execute("BEGIN")
    items = list(res["counts"].items())
    for i in range(0, len(items), 20000):
        con.executemany("INSERT OR IGNORE INTO _pt VALUES(?,?)", items[i:i + 20000])
    con.execute("COMMIT")
    n_pc = con.execute("UPDATE tag SET post_count=MAX(post_count, p.n) FROM _pt p"
                       " WHERE tag.canonical_name=p.name AND p.n>tag.post_count").rowcount

    # content label tu histogram rating: e = explicit, s = sensitive, q = questionable
    rows = []
    for j, (g, s, q, e) in res["rating"].items():
        name = res["rating_names"][j]
        n = g + s + q + e
        if n < args.min_label:
            continue
        if e >= 0.5 * n:
            scope, conf = "adult", round(e / n, 3)
        elif (e + s + q) >= 0.3 * n:
            scope, conf = "contextual", round((e + s + q) / n, 3)
        else:
            scope, conf = "neutral", round(g / n, 3)
        rows.append((name, scope, conf, n))
    con.execute("BEGIN")
    con.executemany(
        "INSERT INTO tag_content_label(tag_id, scope, confidence, rationale, reviewed_at)"
        " SELECT t.id, ?, ?, 'derived from Danbooru posts ratings (n=' || ? || ')', NULL"
        " FROM tag t WHERE t.canonical_name=?"
        " ON CONFLICT(tag_id) DO UPDATE SET scope=excluded.scope, confidence=excluded.confidence,"
        " rationale=excluded.rationale WHERE tag_content_label.scope<>'blocked'",
        [(scope, conf, n, name) for name, scope, conf, n in rows])
    con.execute("COMMIT")

    voc = res["pair_names"]
    V = res["V"]
    scale = max(res.get("pair_every", 1), 1)
    pair_rows = []
    for k, c in res["pairs"].items():
        if c * scale < args.min_pair:
            continue
        pair_rows.append((voc[k // V], voc[k % V], float(c * scale)))
    con.execute("BEGIN")
    con.executemany(
        "INSERT OR IGNORE INTO tag_relation(from_tag_id, to_tag_id, relation, weight, source_id, note)"
        " SELECT f.id, c.id, 'compatible', ?, ?, 'posts co-occurrence' FROM tag f, tag c"
        " WHERE f.canonical_name=? AND c.canonical_name=? AND f.id<>c.id",
        [(w, snap_id, a, b) for a, b, w in pair_rows])
    con.execute("COMMIT")

    os.makedirs(os.path.dirname(UNKNOWN_OUT), exist_ok=True)
    with open(UNKNOWN_OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# tag co trong posts dump nhung chua co trong db (count)\n")
        for name, c in res["unknown"].most_common(20000):
            fh.write("%s\t%d\n" % (name, c))
    print("post_count cap nhat: %d | content_label: %d | compatible pair: %d | snapshot=%d rev=%s"
          % (n_pc, len(rows), len(pair_rows), snap_id, rev))
    print("token la -> %s (top %d)" % (UNKNOWN_OUT, min(20000, len(res["unknown"]))))
    con.close()


if __name__ == "__main__":
    main()
