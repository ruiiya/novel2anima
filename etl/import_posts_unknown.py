# -*- coding: utf-8 -*-
"""Nap cac tag co trong posts dump nhung thieu trong db (file do analyze_posts.py sinh ra).

Usage: python etl/import_posts_unknown.py [--file PATH] [--min-count 5]

Chi them TEN + post_count quan sat duoc; danbooru_category = NULL (khong biet),
taxonomy_status = unreviewed, gan tag_source vao snapshot posts.
"""
import argparse
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build

DEFAULT_FILE = "data/sources/posts_unknown_tags.txt"
SOURCE_KEY = "danbooru_dump_posts"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("--min-count", type=int, default=5)
    args = ap.parse_args(argv)
    if not os.path.exists(args.file):
        raise SystemExit("missing: %s" % args.file)
    rows = []
    with open(args.file, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            name, count = line.rstrip("\n").split("\t")
            if int(count) >= args.min_count:
                rows.append((name, int(count)))
    con = build.connect(build.DB_PATH)
    con.isolation_level = None
    con.execute("PRAGMA journal_mode=WAL")
    snap = con.execute("SELECT id FROM source_snapshot WHERE source_key=? ORDER BY id DESC LIMIT 1",
                       (SOURCE_KEY,)).fetchone()
    if snap is None:
        raise SystemExit("chua co snapshot posts (chay etl/analyze_posts.py truoc)")
    con.execute("DROP TABLE IF EXISTS _pu")
    con.execute("CREATE TEMP TABLE _pu(name TEXT PRIMARY KEY, c INT)")
    con.execute("BEGIN")
    con.executemany("INSERT OR IGNORE INTO _pu VALUES(?,?)", rows)
    con.execute(
        "INSERT INTO tag(canonical_name, search_name, danbooru_category, post_count, taxonomy_status)"
        " SELECT p.name, replace(p.name, '_', ' '), NULL, p.c, 'unreviewed' FROM _pu p"
        " WHERE NOT EXISTS(SELECT 1 FROM tag t WHERE t.canonical_name=p.name)")
    con.execute(
        "UPDATE tag SET post_count=MAX(post_count, p.c) FROM _pu p WHERE tag.canonical_name=p.name")
    n_src = con.execute(
        "INSERT OR IGNORE INTO tag_source(tag_id, source_id, source_ref, source_metadata)"
        " SELECT t.id, ?, 'posts.csv', json_object('observed_posts', p.c)"
        " FROM tag t JOIN _pu p ON p.name=t.canonical_name", (snap[0],)).rowcount
    con.execute("COMMIT")
    print("tag them/cap nhat: %d (min_count=%d) | vd tag_source +%d" % (len(rows), args.min_count, n_src))
    print("tag tong: %d" % con.execute("SELECT count(*) FROM tag").fetchone()[0])
    con.close()


if __name__ == "__main__":
    main()