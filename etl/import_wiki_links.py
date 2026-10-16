# -*- coding: utf-8 -*-
"""Sinh tag_relation tu section wiki (khong doi schema):

  h4/h5 "Not to be confused with" + [quote] "NOT to be confused with" -> conflicts
  "should not be tagged as [[x]]"                                     -> conflicts
  "See also" / "Related tags" / "Related"                             -> recommends

va co "tag under debate" ghi vao tag_source.source_metadata.under_debate.

Usage: python etl/import_wiki_links.py [--file PATH] [--reset]
Link [[x]] chi duoc resolve khi tag co that; link chet (pool:, help:, tag_group:) bo qua.
Idempotent nho PK (from,to,relation); --reset xoa relation cu cua wiki roi nap lai.
"""
import argparse
import csv
import os
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build

DEFAULT_FILE = "C:/Users/user/Downloads/wiki_pages.csv/wiki_pages.csv"
SOURCE_KEY = "danbooru_dump_wiki_pages"
SECTION_RE = re.compile(r"^h([45])\.\s*(.+?)\s*$", re.M)
LINK_RE = re.compile(r"\[\[([^\]|#]+)")
CONFUSED_RE = re.compile(r"not to be confused with", re.I)
QUOTE_RE = re.compile(r"\[quote[^\]]*\](.*?)\[/quote\]", re.S | re.I)
NOT_TAGGED_RE = re.compile(r"should not be tagged as (?:both )?\[?\[?([a-z0-9_ ]+?)\]?\]?(?:[ ,]|$)", re.I)
NOT_TAGGED_LINK_RE = re.compile(r"should not be tagged as (?:both )?\[\[([^\]|#]+)\]\]", re.I)
DEBATE_RE = re.compile(r"tag under debate", re.I)
RECOMMEND = ("see also", "related tags", "related:", "related", "see:", "other tags")
BATCH = 20000


def section_relation(title):
    t = title.lower().strip()
    if CONFUSED_RE.search(t):
        return "conflicts"
    if t.startswith(RECOMMEND):
        return "recommends"
    return None


def collect(text, src, rel, note, out):
    for m in LINK_RE.finditer(text):
        dst = build.canonical(m.group(1))
        if dst and ":" not in dst and dst != src:
            out.append((src, dst, rel, note))


def page_pairs(title, body):
    src = build.canonical(title)
    out = []
    if not src or ":" in src:
        return out
    marks = [(m.start(), int(m.group(1)), m.group(2).strip().lower())
             for m in SECTION_RE.finditer(body)]
    current = None  # h5 khong co quan he rieng thi thua huong h4 cha
    for i, (pos, level, name) in enumerate(marks):
        if level == 4 or section_relation(name):
            current = section_relation(name)
        rel = current
        if rel is None:
            continue
        end = marks[i + 1][0] if i + 1 < len(marks) else len(body)
        for line in body[pos:end].splitlines():
            # chi lay link o dau bullet, cat phan giai thich sau " - "
            collect(line.split(" - ", 1)[0], src, rel, name[:60], out)
    for q in QUOTE_RE.finditer(body):
        head = q.group(1).splitlines()[0] if q.group(1).strip() else ""
        if CONFUSED_RE.search(head):
            collect("\n".join(q.group(1).splitlines()[1:]), src, "conflicts", "quote: not to be confused", out)
    for m in NOT_TAGGED_LINK_RE.finditer(body):
        dst = build.canonical(m.group(1))
        if dst and ":" not in dst and dst != src:
            out.append((src, dst, "conflicts", "should not be tagged as"))
    return out


def iter_pages(path):
    with open(path, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            yield r["title"], r["body"] or ""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("--reset", action="store_true", help="xoa relation cu cua source nay roi nap lai")
    args = ap.parse_args(argv)
    if not os.path.exists(args.file):
        raise SystemExit("missing: %s" % args.file)

    con = build.connect(build.DB_PATH)
    con.isolation_level = None
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    snap = con.execute("SELECT id FROM source_snapshot WHERE source_key=? ORDER BY id DESC LIMIT 1",
                       (SOURCE_KEY,)).fetchone()
    if snap is None:
        raise SystemExit("chua import wiki_pages (chay etl/import_wiki_pages.py truoc)")
    snap_id = snap[0]
    ep = time.time()
    if args.reset:
        n = con.execute("DELETE FROM tag_relation WHERE source_id=? AND note IS NOT NULL", (snap_id,)).rowcount
        print("reset: xoa %d relation cu" % n)

    con.execute("DROP TABLE IF EXISTS _wiki_link")
    con.execute("CREATE TEMP TABLE _wiki_link(src TEXT, dst TEXT, rel TEXT, note TEXT,"
                " PRIMARY KEY(src, dst, rel))")
    con.execute("CREATE TEMP TABLE _wiki_debate(name TEXT PRIMARY KEY)")
    con.execute("BEGIN")
    buf, total = [], 0
    for title, body in iter_pages(args.file):
        for row in page_pairs(title, body):
            total += 1
            buf.append(row)
            if len(buf) >= BATCH:
                con.executemany("INSERT OR IGNORE INTO _wiki_link VALUES(?,?,?,?)", buf)
                buf = []
        if DEBATE_RE.search(body) and ":" not in title:
            con.execute("INSERT OR IGNORE INTO _wiki_debate VALUES(?)", (build.canonical(title),))
    if buf:
        con.executemany("INSERT OR IGNORE INTO _wiki_link VALUES(?,?,?,?)", buf)
    con.commit()
    pairs = con.execute("SELECT count(*) FROM _wiki_link").fetchone()[0]
    debate = con.execute("SELECT count(*) FROM _wiki_debate").fetchone()[0]

    con.execute("BEGIN")
    con.execute(
        "INSERT OR IGNORE INTO tag_relation(from_tag_id, to_tag_id, relation, weight, source_id, note)"
        " SELECT f.id, c.id, l.rel, 1.0, ?, l.note FROM _wiki_link l"
        " JOIN tag f ON f.canonical_name=l.src JOIN tag c ON c.canonical_name=l.dst"
        " WHERE f.id<>c.id", (snap_id,))
    added = con.execute("SELECT changes()").fetchone()[0]
    flagged = con.execute(
        "UPDATE tag_source SET source_metadata=json_set(source_metadata, '$.under_debate', 1)"
        " WHERE source_ref='wiki_pages.csv' AND tag_id IN"
        " (SELECT t.id FROM tag t JOIN _wiki_debate d ON d.name=t.canonical_name)").rowcount
    con.commit()
    con.execute("DROP TABLE _wiki_link")
    con.execute("DROP TABLE _wiki_debate")
    print("wiki_pairs=%d unique=%d relation_added=%d under_debate=%d (/ %d page) snap=%d %.1fs"
          % (total, pairs, added, flagged, debate, snap_id, time.time() - ep))
    for rel, n in con.execute("SELECT relation, count(*) FROM tag_relation GROUP BY 1 ORDER BY 2 DESC"):
        print("  %-11s %d" % (rel, n))
    con.close()


if __name__ == "__main__":
    main()