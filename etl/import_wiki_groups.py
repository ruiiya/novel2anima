# -*- coding: utf-8 -*-
"""tag_group:* trong wiki Danbooru -> visual_concept kind=other + concept_tag.

Usage: python etl/import_wiki_groups.py [--file PATH] [--min-members 5]

Moi group thanh 1 concept: code TG_<slug>, search_terms = danh sach tag thanh vien,
metadata_json = cay phan cap (tag + depth + section). Member -> concept_tag usage=optional,
priority = 100 + depth. Group resolve < min-members bi bo qua (trang alias/rac).
"""
import argparse
import csv
import json
import os
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build

DEFAULT_FILE = "C:/Users/user/Downloads/wiki_pages.csv/wiki_pages.csv"
SOURCE_KEY = "danbooru_dump_wiki_pages"
LINK_RE = re.compile(r"\[\[([^\]|#]+)")
H4_RE = re.compile(r"^h4\.\s*(.+?)\s*$", re.M)
DEPTH_RE = re.compile(r"^(\*+)\s*")
ADULT_GROUPS = {"nudity", "penetration_tags", "sex_positions", "sexual_positions", "bdsm", "bondage"}
# group dac thu e621 (species/furry/quoc gia), khong dung cho prompt: bo qua
SKIP_GROUPS = {"species", "fictional_species", "original_species", "nazi_germany"}


def strip_markup(text):
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[/?[a-z0-9=,._\- ]+\]", "", text, flags=re.I)
    text = re.sub(r"^[*#]+\s*", "", text, flags=re.M)
    return " ".join(text.split())


def lead_paragraph(body):
    out = []
    for line in body.splitlines():
        s = line.strip()
        if not s:
            if out:
                break
            continue
        if s.startswith(("[", "h1.", "h2.", "h3.", "h4.", "h5.", "thumb")):
            continue
        out.append(s)
        if len(" ".join(out)) > 400:
            break
    return strip_markup(" ".join(out))[:600]


def members(body):
    """[(tag, depth, section)] theo thu tu xuat hien."""
    section = ""
    for line in body.splitlines():
        stripped = line.strip()
        m = H4_RE.match(stripped)
        if m:
            section = strip_markup(m.group(1))
            continue
        dm = DEPTH_RE.match(line)
        if not dm or "[[" not in stripped:
            continue
        for link in LINK_RE.finditer(stripped):
            tag = "_".join(link.group(1).strip().split())
            if tag and ":" not in tag:
                yield tag, min(len(dm.group(1)), 3), section


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("--min-members", type=int, default=5)
    args = ap.parse_args(argv)
    if not os.path.exists(args.file):
        raise SystemExit("missing: %s" % args.file)

    con = build.connect(build.DB_PATH)
    con.isolation_level = None
    con.execute("PRAGMA journal_mode=WAL")
    snap = con.execute("SELECT id FROM source_snapshot WHERE source_key=? ORDER BY id DESC LIMIT 1",
                       (SOURCE_KEY,)).fetchone()
    if snap is None:
        raise SystemExit("chua import wiki_pages")
    snap_id = snap[0]
    ep = time.time()

    con.execute("DROP TABLE IF EXISTS _tg")
    con.execute("CREATE TEMP TABLE _tg(tag TEXT, depth INT, section TEXT, grp TEXT)")
    groups = []
    with open(args.file, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            title = r["title"]
            if not title.startswith("tag_group:"):
                continue
            name = title.split(":", 1)[1].strip()
            body = r["body"] or ""
            groups.append((title, name, body, r["updated_at"]))
    con.execute("BEGIN")
    for title, name, body, _u in groups:
        for tag, depth, section in members(body):
            con.execute("INSERT INTO _tg VALUES(?,?,?,?)", (tag, depth, section, title))
    con.commit()
    con.execute("CREATE INDEX idx_tg ON _tg(tag)")

    added_c = added_t = skipped = 0
    links = 0
    for title, name, body, updated in groups:
        rows = con.execute(
            "SELECT l.tag, l.depth, l.section FROM _tg l JOIN tag t ON t.canonical_name=l.tag"
            " WHERE l.grp=? GROUP BY l.tag ORDER BY min(l.rowid)", (title,)).fetchall()
        if len(rows) < args.min_members or build.slug(name) in SKIP_GROUPS:
            skipped += 1
            continue
        code = "TG_" + build.slug(name)
        kind = "other"
        scope = "adult" if build.slug(name) in ADULT_GROUPS else "contextual"
        member_tags = [r[0] for r in rows]
        meta = {"source": "danbooru wiki tag_group", "page": title, "updated_at": updated,
                "members": [{"tag": r[0], "depth": r[1], "section": r[2]} for r in rows]}
        con.execute(
            "INSERT INTO visual_concept(code, kind, name, description, search_terms,"
            " content_scope, review_status, metadata_json) VALUES(?,?,?,?,?,?,?,?)"
            " ON CONFLICT(code) DO UPDATE SET description=excluded.description,"
            " search_terms=excluded.search_terms, metadata_json=excluded.metadata_json",
            (code, kind, name.replace("_", " ").title(), lead_paragraph(body),
             " ".join(member_tags), scope, "draft",
             json.dumps(meta, ensure_ascii=False, sort_keys=True)))
        cid = con.execute("SELECT id FROM visual_concept WHERE code=?", (code,)).fetchone()[0]
        added_c += 1
        con.execute("DELETE FROM concept_tag WHERE concept_id=?", (cid,))
        con.executemany(
            "INSERT OR IGNORE INTO concept_tag(concept_id, tag_id, usage, priority)"
            " SELECT ?, id, 'optional', ? FROM tag WHERE canonical_name=?",
            [(cid, 100 + d, t) for t, d, _s in rows])
        added_t += len(rows)
        links += 1
    con.execute("DROP TABLE _tg")
    print("tag_group=%d concept_moi=%d member=%d group_bo_qua=%d snap=%d %.1fs"
          % (links, added_c, added_t, skipped, snap_id, time.time() - ep))
    print("  visual_concept %d | concept_tag %d"
          % (con.execute("SELECT count(*) FROM visual_concept").fetchone()[0],
             con.execute("SELECT count(*) FROM concept_tag").fetchone()[0]))
    con.close()


if __name__ == "__main__":
    main()