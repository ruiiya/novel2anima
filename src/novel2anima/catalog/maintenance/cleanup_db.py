# -*- coding: utf-8 -*-
"""Don dep 2 loai du lieu mo ho con lai (khong doi schema).

Usage: python etl/cleanup_db.py [--apply] [--vacuum]

1. Alias trung ten tag that (alias_name cung la canonical_name cua mot tag):
   quy tac TAG THANG ALIAS -> xoa cac dong alias nay (du lieu cu/tu site khac).
2. Tag ten khong phai prompt token (ky tu dac biet, emoji, CJK): KHONG xoa, vi do la du lieu
   that (^_^ 158k post, ? 108k post, ten artist tieng Nhat...). Xuat deny-list cho buoc
   build prompt: data/sources/tags_not_prompt_token.txt
"""
import argparse
import os
import pathlib
import sys
import time

from novel2anima.paths import SOURCES_DIR
from novel2anima.catalog import build_service as build

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DENY_LIST = str(SOURCES_DIR / "tags_not_prompt_token.txt")
SYMBOL_ONLY = "canonical_name NOT GLOB '*[a-z0-9]*'"


def deny_rows(con):
    return con.execute("SELECT canonical_name, post_count FROM tag WHERE %s" % SYMBOL_ONLY).fetchall()


def write_deny_list(rows):
    os.makedirs(os.path.dirname(DENY_LIST), exist_ok=True)
    with open(DENY_LIST, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# khong dung lam prompt token (ky tu dac biet/emoji/CJK); van giu trong db\n")
        for name, pc in rows:
            fh.write("%s\t%d\n" % (name, pc))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--vacuum", action="store_true")
    args = ap.parse_args(argv)

    con = build.connect(build.DB_PATH)
    con.isolation_level = None
    con.execute("PRAGMA journal_mode=WAL")

    n_alias = con.execute(
        "SELECT count(*) FROM tag_alias a JOIN tag t ON t.canonical_name=a.alias_name").fetchone()[0]
    vd_alias = con.execute(
        "SELECT a.alias_name, a.tag_id, t.id FROM tag_alias a JOIN tag t ON t.canonical_name=a.alias_name LIMIT 5").fetchall()
    rows = deny_rows(con)
    print("alias trung ten tag (se xoa, tag thang): %d | vd %s" % (n_alias, vd_alias))
    print("tag khong phai prompt token (ghi deny-list, KHONG xoa): %d | vd %s"
          % (len(rows), [r[0] for r in rows[:8]]))
    if not args.apply:
        print("dry-run: them --apply de chay that")
        con.close()
        return

    ep = time.time()
    d_alias = con.execute(
        "DELETE FROM tag_alias WHERE rowid IN (SELECT a.rowid FROM tag_alias a"
        " JOIN tag t ON t.canonical_name=a.alias_name)").rowcount
    write_deny_list(rows)
    print("da xoa alias=%d | deny-list %s (%d dong) | %.1fs"
          % (d_alias, DENY_LIST, len(rows), time.time() - ep))
    for t in ("tag", "tag_alias", "tag_relation", "tag_source", "tag_content_label", "concept_tag"):
        print("  %-18s %d" % (t, con.execute("SELECT count(*) FROM %s" % t).fetchone()[0]))
    print("fk_check %s" % (con.execute("PRAGMA foreign_key_check").fetchall(),))
    if args.vacuum:
        ep = time.time()
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.execute("VACUUM")
        print("vacuum %.1fs" % (time.time() - ep))
    con.close()


if __name__ == "__main__":
    main()