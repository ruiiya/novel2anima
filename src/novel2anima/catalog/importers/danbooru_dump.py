# -*- coding: utf-8 -*-
"""Import dump CSV chinh thuc cua Danbooru (tags / aliases / implications / artists .csv.gz).

Usage: python -m novel2anima.catalog.importers.danbooru_dump [--dir DIR] [--only tags,aliases,implications,artists]

--dir defaults to $N2A_DATA_DIR (fallback: data/imports).

Idempotent: chi INSERT OR IGNORE / MAX(post_count); khong doi id tag da co, khong sua schema.
"""
import argparse
import csv
import gzip
import os
import pathlib
import sys
import time

from novel2anima.paths import DATA_DIR
from novel2anima.catalog import build_service as build

CATEGORY = build.DANBOORU_CATEGORY
BATCH = 20000
LICENSE = "Danbooru official CSV dump; tag names are Danbooru public data."
FILES = {
    "tags": "tags.csv.gz",
    "aliases": "tag_aliases.csv.gz",
    "implications": "tag_implications.csv.gz",
    "artists": "artists.csv.gz",
}
TAG_DDL = "(name TEXT PRIMARY KEY, category TEXT, post_count INTEGER, src TEXT)"  # src = file goc
PAIR_DDL = "(alias_name TEXT PRIMARY KEY, tag_name TEXT)"
IMP_DDL = "(alias_name TEXT, tag_name TEXT)"  # nhieu consequent cho 1 antecedent


def reader(path):
    return gzip.open(path, "rt", encoding="utf-8", newline="")


def snapshot(con, key, path):
    digest = build.sha256_file(path)
    rev = digest[:16]
    row = con.execute("SELECT id FROM source_snapshot WHERE source_key=? AND revision=?",
                      (key, rev)).fetchone()
    if row:
        return row[0], rev
    cur = con.execute(
        "INSERT INTO source_snapshot(source_key, source_url, revision, license_note, sha256)"
        " VALUES(?,?,?,?,?)",
        (key, "file:///" + pathlib.Path(path).as_posix(), rev, LICENSE, digest))
    return cur.lastrowid, rev


def fill(con, table, ddl, rows):
    """Stream rows into a TEMP table; returns row count."""
    con.execute("DROP TABLE IF EXISTS %s" % table)
    con.execute("CREATE TEMP TABLE %s %s" % (table, ddl))
    con.execute("BEGIN")
    buf, total, sql = [], 0, None
    for row in rows:
        buf.append(row)
        if len(buf) >= BATCH:
            sql = sql or "INSERT OR IGNORE INTO %s VALUES (%s)" % (table, ",".join("?" * len(row)))
            con.executemany(sql, buf)
            total += len(buf)
            buf = []
    if buf:
        con.executemany("INSERT OR IGNORE INTO %s VALUES (%s)" % (table, ",".join("?" * len(buf[0]))), buf)
        total += len(buf)
    con.commit()
    return total


def run(con, key, filename, argv_dir, table, ddl, index_col, rows, statements):
    """snapshot -> temp table -> index -> statements. Param "?" -> snapshot id."""
    ep = time.time()
    path = os.path.join(argv_dir, filename)
    if not os.path.exists(path):
        raise SystemExit("missing: %s" % path)
    snap_id, rev = snapshot(con, key, path)
    n = fill(con, table, ddl, rows(path))
    if index_col:
        con.execute("CREATE INDEX IF NOT EXISTS idx_%s ON %s(%s)" % (table.lstrip("_"), table, index_col))
    con.execute("BEGIN")
    for sql, params in statements:
        con.execute(sql, [snap_id if p == "?" else p for p in params])
    con.commit()
    con.execute("DROP TABLE %s" % table)
    print("%-22s rows=%-8d snap=%d rev=%s %.1fs" % (key, n, snap_id, rev, time.time() - ep))


# --------------------------------------------------------------------- row generators

def it_tags(*paths):
    for path in paths:
        ref = os.path.basename(path)
        with reader(path) as fh:
            for r in csv.DictReader(fh):
                name = build.canonical(r["name"])
                if not name:
                    continue
                if ref.startswith("artists"):
                    yield name, "artist", 0, ref
                else:
                    cat = CATEGORY.get(int(r["category"]))
                    if cat:
                        yield name, cat, int(r["post_count"] or 0), ref


def it_pairs(path):
    """(alias|antecedent, target) voi status=active."""
    with reader(path) as fh:
        for r in csv.DictReader(fh):
            if r["status"] != "active":
                continue
            a = build.canonical(r["antecedent_name"])
            b = build.canonical(r["consequent_name"])
            if a and b and a != b:
                yield a, b


def it_artist_names(path):
    with reader(path) as fh:
        for r in csv.DictReader(fh):
            target = build.canonical(r["name"])
            others = r["other_names"].strip("{}") if r["other_names"] else ""
            for other in others.split(","):
                alias = build.canonical(other)
                if alias and target and alias != target:
                    yield alias, target


# --------------------------------------------------------------------- stages

def stage_tags(con, args, wanted, both_tags):
    files = [FILES["tags"], FILES["artists"]] if both_tags else [FILES["tags"]]
    ep = time.time()
    # moi file 1 snapshot rieng: hash cua ban ghi phai dung file goc
    snaps = {}
    for f in files:
        key = "danbooru_dump_artists" if f.startswith("artists") else "danbooru_dump_tags"
        snaps[f] = snapshot(con, key, os.path.join(args.dir, f))
    snap_id, rev = snaps[files[0]]
    n = fill(con, "_dump_tag", TAG_DDL, it_tags(*[os.path.join(args.dir, f) for f in files]))
    con.execute("CREATE INDEX IF NOT EXISTS idx_dump_tag ON _dump_tag(name)")
    con.execute("BEGIN")
    con.execute(
        "INSERT INTO tag(canonical_name, search_name, danbooru_category, post_count, taxonomy_status)"
        " SELECT d.name, replace(d.name, '_', ' '), d.category, d.post_count, 'unreviewed'"
        " FROM _dump_tag d WHERE NOT EXISTS(SELECT 1 FROM tag t WHERE t.canonical_name=d.name)")
    created = con.execute("SELECT changes()").fetchone()[0]
    con.execute(
        "UPDATE tag SET post_count=MAX(tag.post_count, d.post_count),"
        " danbooru_category=COALESCE(danbooru_category, d.category)"
        " FROM _dump_tag d WHERE tag.canonical_name=d.name")
    for f in files:
        con.execute(
            "INSERT OR IGNORE INTO tag_source(tag_id, source_id, source_ref, source_metadata)"
            " SELECT t.id, ?, d.src, '{}' FROM tag t JOIN _dump_tag d ON d.name=t.canonical_name"
            " WHERE d.src=?", (snaps[f][0], f))
    con.commit()
    con.execute("DROP TABLE _dump_tag")
    print("%-22s rows=%-8d new=%-8d snaps=%s %.1fs"
          % ("+".join(files), n, created, {f: snaps[f][1] for f in files}, time.time() - ep))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.environ.get("N2A_DATA_DIR", str(DATA_DIR / "imports")),
                    help="directory holding the downloaded Danbooru CSV dumps")
    ap.add_argument("--only", default=",".join(FILES))
    args = ap.parse_args(argv)
    wanted = [w.strip() for w in args.only.split(",") if w.strip()]
    for k in wanted:
        if k not in FILES:
            raise SystemExit("unknown stage: %s" % k)

    con = build.connect(build.DB_PATH)
    con.isolation_level = None  # tu quan ly BEGIN/COMMIT cho bulk import
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    before = con.execute("SELECT count(*) FROM tag").fetchone()[0]
    t0 = time.time()

    if "tags" in wanted:
        stage_tags(con, args, wanted, "artists" in wanted)

    if "aliases" in wanted:
        run(con, "danbooru_dump_tag_aliases", FILES["aliases"], args.dir,
            "_dump_alias", PAIR_DDL, "alias_name", it_pairs,
            [("INSERT OR IGNORE INTO tag_alias(alias_name, tag_id, source_id)"
              " SELECT a.alias_name, t.id, ? FROM _dump_alias a"
              " JOIN tag t ON t.canonical_name=a.tag_name", ["?"])])
        run(con, "danbooru_dump_artist_names", FILES["artists"], args.dir,
            "_dump_artist_alias", PAIR_DDL, "alias_name", it_artist_names,
            [("INSERT OR IGNORE INTO tag_alias(alias_name, tag_id, source_id)"
              " SELECT a.alias_name, t.id, ? FROM _dump_artist_alias a"
              " JOIN tag t ON t.canonical_name=a.tag_name", ["?"])])

    if "implications" in wanted:
        run(con, "danbooru_dump_tag_implications", FILES["implications"], args.dir,
            "_dump_imp", IMP_DDL, "alias_name", it_pairs,
            [("INSERT OR IGNORE INTO tag_relation(from_tag_id, to_tag_id, relation, weight, source_id, note)"
              " SELECT f.id, c.id, 'implies', 1.0, ?, NULL FROM _dump_imp i"
              " JOIN tag f ON f.canonical_name=i.alias_name"
              " JOIN tag c ON c.canonical_name=i.tag_name WHERE f.id<>c.id", ["?"])])

    after = con.execute("SELECT count(*) FROM tag").fetchone()[0]
    for t in ("tag", "tag_alias", "tag_relation", "tag_source", "tag_role"):
        print("  %-12s %d" % (t, con.execute("SELECT count(*) FROM %s" % t).fetchone()[0]))
    print("tag: %d -> %d (+%d) in %.1fs" % (before, after, after - before, time.time() - t0))
    con.close()


if __name__ == "__main__":
    main()
