# -*- coding: utf-8 -*-
"""Import vai character tag con thieu tu source pinned (danbooru_taxonomy/tags.csv).

Usage: python etl/import_tags.py shinra_tsubaki meguri_tomoe
Khong bia id: chi lay row co that trong data/sources/danbooru_taxonomy/tags.csv.
"""
import csv, sys, pathlib

from novel2anima.paths import SOURCES_DIR
from novel2anima.catalog import build_service as build

DB = "db/novel_anima.db"
CSV = SOURCES_DIR / "danbooru_taxonomy" / "tags.csv"
STATUS = {"approved": "approved", "needs_review": "needs_review"}


def main(names):
    want = {n.lower() for n in names}
    rows = [r for r in csv.DictReader(CSV.open(encoding="utf-8", newline=""))
            if r["tag"].lower() in want]
    con = build.connect(DB)
    snap = con.execute("SELECT id FROM source_snapshot WHERE source_key=? ORDER BY id DESC LIMIT 1",
                       ("danbooru_taxonomy",)).fetchone()
    if snap is None:
        raise SystemExit("no danbooru_taxonomy snapshot in db")
    w = build.TagWriter(con)
    for r in rows:
        tid = w.ensure(r["tag"], r["danbooru_category"], int(r["post_count"]),
                       STATUS.get(r["status"], "unreviewed"), snap[0], "tags.csv",
                       {"category": r["category"], "subcategory": r["subcategory"],
                        "slot": r["slot"], "confidence": float(r["confidence"]),
                        "status": r["status"], "imported_by": "import_tags.py"})
        n_alias = sum(w.alias(a.strip(), tid, snap[0])
                      for a in r["aliases"].split(",") if a.strip())
        print("%s -> id=%s category=%s post_count=%s aliases+%d"
              % (r["tag"], tid, r["danbooru_category"], r["post_count"], n_alias))
    missing = want - {r["tag"].lower() for r in rows}
    if missing:
        print("not in source (khong the them):", sorted(missing))
    con.commit()
    con.close()


if __name__ == "__main__":
    main(sys.argv[1:])
