# -*- coding: utf-8 -*-
"""Xoa tag rac: post_count = 0, khong tai lieu, khong duoc tham chieu o dau.

Usage: python etl/prune_tags.py [--apply] [--vacuum]

Giu lai tag khi co BAT KY dau hieu su dung:
  post_count > 0 | danbooru_category = artist | taxonomy_status != unreviewed
  co wiki page | co tag_role | co tag_relation | trong concept_tag | la alias target
  duoc nhac theo ten hoac theo id (name:123) trong data/plans, data/characters, prompts.
Mac dinh chi in thong ke; --apply moi xoa that.
"""
import argparse
import glob
import os
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build

REF_GLOBS = ("data/plans/*.json", "data/characters/*.json")
TOKEN_RE = re.compile(r"[a-z0-9_]{3,}")
ID_RE = re.compile(r":(\d{2,7})\b")


def ref_files():
    for pattern in REF_GLOBS:
        for path in glob.glob(pattern):
            yield path
    for path in glob.glob("prompts/*.txt"):
        yield path


def referenced():
    """(names, ids) xuat hien trong plan/profile/prompt."""
    names, ids = set(), set()
    for path in ref_files():
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        names.update(TOKEN_RE.findall(text.lower()))
        ids.update(int(x) for x in ID_RE.findall(text))
    return names, ids


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--vacuum", action="store_true")
    args = ap.parse_args(argv)

    con = build.connect(build.DB_PATH)
    con.isolation_level = None
    con.execute("PRAGMA journal_mode=WAL")
    before = con.execute("SELECT count(*) FROM tag").fetchone()[0]

    con.execute("DROP TABLE IF EXISTS _keep")
    con.execute("CREATE TEMP TABLE _keep(id INTEGER PRIMARY KEY)")
    reasons = [
        ("post_count>0", "SELECT id FROM tag WHERE post_count>0"),
        ("artist", "SELECT id FROM tag WHERE danbooru_category='artist'"),
        ("curated", "SELECT id FROM tag WHERE taxonomy_status<>'unreviewed'"),
        ("wiki", "SELECT tag_id FROM tag_source WHERE source_ref='wiki_pages.csv'"),
        ("role", "SELECT tag_id FROM tag_role"),
        ("relation", "SELECT from_tag_id FROM tag_relation UNION SELECT to_tag_id FROM tag_relation"),
        ("concept", "SELECT tag_id FROM concept_tag"),
        ("alias_target", "SELECT tag_id FROM tag_alias"),
    ]
    for label, sql in reasons:
        n = con.execute("INSERT OR IGNORE INTO _keep %s" % sql).rowcount
        print("  keep %-12s +%d" % (label, n))

    names, ids = referenced()
    extra = [r[0] for r in con.execute(
        "SELECT id, canonical_name FROM tag WHERE id NOT IN (SELECT id FROM _keep)").fetchall()
        if r[1] in names]
    con.executemany("INSERT OR IGNORE INTO _keep VALUES(?)", [(i,) for i in extra])
    print("  keep %-12s +%d (ten trong plan/profile/prompt)" % ("ref_name", len(extra)))
    kept_ids = con.execute("SELECT count(*) FROM tag WHERE id IN (%s) AND id NOT IN (SELECT id FROM _keep)"
                           % ",".join(map(str, ids or [0]))).fetchone()[0]
    con.executemany("INSERT OR IGNORE INTO _keep VALUES(?)", [(i,) for i in ids])
    print("  keep %-12s +%d (id trong plan/profile/prompt)" % ("ref_id", kept_ids))

    dead = con.execute("SELECT count(*) FROM tag WHERE id NOT IN (SELECT id FROM _keep)").fetchone()[0]
    sample = con.execute(
        "SELECT canonical_name FROM tag WHERE id NOT IN (SELECT id FROM _keep)"
        " ORDER BY post_count, length(canonical_name) LIMIT 10").fetchall()
    print("tag %d -> giu %d | xoa %d" % (before, before - dead, dead))
    print("  sample xoa: %s" % ([s[0] for s in sample],))
    if not args.apply:
        print("dry-run: them --apply de xoa that")
        con.close()
        return

    ep = time.time()
    con.execute("BEGIN")
    con.execute("DELETE FROM tag WHERE id NOT IN (SELECT id FROM _keep)")
    con.execute("COMMIT")
    after = con.execute("SELECT count(*) FROM tag").fetchone()[0]
    print("da xoa %d tag -> con %d (%.1fs)" % (before - after, after, time.time() - ep))
    for t in ("tag", "tag_alias", "tag_relation", "tag_source", "tag_role", "concept_tag"):
        print("  %-12s %d" % (t, con.execute("SELECT count(*) FROM %s" % t).fetchone()[0]))
    print("fk_check %s" % (con.execute("PRAGMA foreign_key_check").fetchall(),))
    con.execute("DROP TABLE _keep")
    if args.vacuum:
        ep = time.time()
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.execute("VACUUM")
        print("vacuum %.1fs -> %.0f MB" % (time.time() - ep, os.path.getsize(build.DB_PATH) / 1e6))
    con.close()


if __name__ == "__main__":
    main()