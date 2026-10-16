# -*- coding: utf-8 -*-
"""Import wiki_pages dump vao tag_source (khong doi schema, khong them bang).

Usage: python etl/import_wiki_pages.py [--file PATH]

Moi wiki page co title trung canonical_name cua tag -> 1 row tag_source tren snapshot
wiki, source_metadata = {"wiki_id":..,"updated_at":..,"body":..}. Title khong phai tag
(e621:*, help:*, script...) bi bo qua. Idempotent nho PK (tag_id, source_id, source_ref).
"""
import argparse
import csv
import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build

DEFAULT_FILE = "C:/Users/user/Downloads/wiki_pages.csv/wiki_pages.csv"
SOURCE_KEY = "danbooru_dump_wiki_pages"
LICENSE = "Danbooru official CSV dump; wiki text is Danbooru public data."
BATCH = 5000


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


def it_wiki(path):
    with open(path, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            title = build.canonical(r["title"])
            if title and ":" not in title:
                yield title, r["id"], r["updated_at"], r["body"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=DEFAULT_FILE)
    args = ap.parse_args(argv)
    if not os.path.exists(args.file):
        raise SystemExit("missing: %s" % args.file)

    con = build.connect(build.DB_PATH)
    con.isolation_level = None
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    ep = time.time()
    snap_id, rev = snapshot(con, args.file)

    con.execute("DROP TABLE IF EXISTS _dump_wiki")
    con.execute("CREATE TEMP TABLE _dump_wiki(title TEXT PRIMARY KEY, wiki_id INT, updated_at TEXT, body TEXT)")
    con.execute("BEGIN")
    buf, seen, total = [], 0, 0
    for row in it_wiki(args.file):
        total += 1
        buf.append(row)
        if len(buf) >= BATCH:
            con.executemany("INSERT OR IGNORE INTO _dump_wiki VALUES(?,?,?,?)", buf)
            seen += len(buf)
            buf = []
    if buf:
        con.executemany("INSERT OR IGNORE INTO _dump_wiki VALUES(?,?,?,?)", buf)
        seen += len(buf)
    con.commit()
    con.execute("CREATE INDEX IF NOT EXISTS idx_dump_wiki ON _dump_wiki(title)")
    n_in = con.execute("SELECT count(*) FROM _dump_wiki").fetchone()[0]
    matched = con.execute(
        "SELECT count(*) FROM _dump_wiki w JOIN tag t ON t.canonical_name=w.title").fetchone()[0]
    con.execute("BEGIN")
    con.execute(
        "INSERT OR IGNORE INTO tag_source(tag_id, source_id, source_ref, source_metadata)"
        " SELECT t.id, ?, 'wiki_pages.csv',"
        " json_object('wiki_id', w.wiki_id, 'updated_at', w.updated_at, 'body', w.body)"
        " FROM _dump_wiki w JOIN tag t ON t.canonical_name=w.title", (snap_id,))
    con.commit()
    con.execute("DROP TABLE _dump_wiki")
    print("wiki rows=%d unique=%d matched_tag=%d snap=%d rev=%s %.1fs"
          % (total, n_in, matched, snap_id, rev, time.time() - ep))
    print("  tag_source  %d" % con.execute("SELECT count(*) FROM tag_source").fetchone()[0])
    con.close()


if __name__ == "__main__":
    main()
