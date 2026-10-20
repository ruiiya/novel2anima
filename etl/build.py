# novel2anima P0P1 upgrade
#!/usr/bin/env python3
"""Novel2Anima SQLite build: P0 schema + P1 pinned-source import. No PostgreSQL.

    python etl/build.py all      # schema -> fetch -> load -> verify
    python etl/build.py schema   # rebuild db/novel_anima.db from sql/schema_v1.sql
    python etl/build.py fetch    # download pinned sources into data/sources/
    python etl/build.py load     # idempotent import of every enabled source
    python etl/build.py verify   # integrity_check / foreign_key_check / FTS5 / counts

Raw downloads are cached under data/sources/ and hashed into data/sources/manifest.json,
so load/verify work offline. Every imported row carries a source_snapshot id.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "db", "novel_anima.db")
SCHEMA_PATH = os.path.join(ROOT, "sql", "schema_v1.sql")
SOURCES_PATH = os.path.join(ROOT, "etl", "sources.json")
SRC_DIR = os.path.join(ROOT, "data", "sources")
MANIFEST_PATH = os.path.join(SRC_DIR, "manifest.json")
REPORT_PATH = os.path.join(ROOT, "db", "import_report.json")
UA = "novel2anima-etl/0.1"

DANBOORU_CATEGORY = {0: "general", 1: "artist", 3: "copyright", 4: "character", 5: "meta"}
STATUS_RANK = {"unreviewed": 0, "needs_review": 1, "approved": 2}

# Danbooru taxonomy slot -> tag_role. Unmapped slots (characters, copyrights,
# meta, style, layout...) stay tag-only: they are dictionary entries, not
# prompt-building roles. Seeded from Mexes/danbooru-tag-taxonomy `slot`.
ROLE_BY_SLOT = {
    "appearance:anatomy": ("identity",),
    "appearance:demographics": ("identity",),
    "appearance:eyes": ("identity",),
    "appearance:hair": ("identity",),
    "clothing:accents": ("outfit",),
    "clothing:bottom": ("outfit",),
    "clothing:eyewear": ("outfit",),
    "clothing:footwear": ("outfit",),
    "clothing:headwear": ("outfit",),
    "clothing:legwear": ("outfit",),
    "clothing:outfit": ("outfit",),
    "clothing:top": ("outfit",),
    "clothing:underwear": ("outfit",),
    "pose:camera": ("camera",),
    "pose:combat": ("action",),
    "pose:expression": ("expression",),
    "pose:gesture": ("pose", "action"),
    "pose:interaction": ("interaction", "action"),
    "pose:kinetic": ("motion",),
    "pose:physiological": ("pose",),
    "pose:posture": ("pose",),
    "scenery:atmosphere": ("background",),
    "scenery:props": ("other",),
    "scenery:setting": ("background",),
    "equipment:handheld": ("other",),
    "equipment:weapon": ("other",),
    "creature:animal": ("other",),
}

# Anatomy / nudity tags must never become outfit or pose roles. Import sources
# (attire slots, pose groups, wardrobe presets) occasionally list them there.
BODY_TAGS = {
    "nude", "completely_nude", "topless", "bottomless", "nipples",
    "pussy", "pubic_hair", "pussy_juice", "pussy_juice_drip",
    "pussy_juice_trail", "pussy_juice_stain", "pussy_juice_puddle",
    "afterglow",
}

def role_for(name, role):
    if role in ("outfit", "pose", "interaction") and name in BODY_TAGS:
        return "body_state"
    return role

TABLES = ("source_snapshot", "tag", "tag_source", "tag_alias", "tag_role",
          "tag_relation", "tag_content_label", "visual_concept", "concept_tag",
          "concept_relation")


# --------------------------------------------------------------------------- helpers

def connect(path, wal=False):
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=5000")
    if wal:
        con.execute("PRAGMA journal_mode=WAL")
    return con


def load_sources():
    with open(SOURCES_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "unnamed"


def canonical(name):
    """Danbooru canonical (underscored) form from a space-form tag name."""
    return "_".join(name.strip().split())


def counts(con):
    return {t: con.execute("SELECT count(*) FROM %s" % t).fetchone()[0] for t in TABLES}


# --------------------------------------------------------------------------- schema

def cmd_schema(args):
    if os.path.exists(DB_PATH) and not args.force:
        print("db exists, use --force to rebuild: %s" % DB_PATH)
        return
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(DB_PATH + suffix):
            os.remove(DB_PATH + suffix)
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        ddl = fh.read()
    con = connect(DB_PATH, wal=True)
    con.executescript(ddl)
    # The continuity/QA tables must exist on a fresh build too.
    with open(os.path.join(os.path.dirname(SCHEMA_PATH), "migrations", "002_shot_state.sql"),
              encoding="utf-8") as fh:
        con.executescript(fh.read())
    con.commit()
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    fts = [t for t in tables if t.startswith("visual_concept_fts")]
    print("schema applied: %d tables (incl. %d fts5 shadow) -> %s" % (len(tables), len(fts), DB_PATH))
    con.close()


# --------------------------------------------------------------------------- fetch

def download(url, dest, timeout=600, attempts=3):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    last = None
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp, open(part, "wb") as out:
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
            os.replace(part, dest)
            return
        except Exception as exc:  # noqa: BLE001 - retry any transport failure
            last = exc
            if os.path.exists(part):
                os.remove(part)
            time.sleep(2 * attempt)
    raise SystemExit("download failed after %d attempts: %s (%s)" % (attempts, url, last))


def cmd_fetch(args):
    sources = load_sources()
    manifest = {}
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, encoding="utf-8") as fh:
            manifest = json.load(fh)
    for key, src in sources.items():
        if not src["enabled"]:
            print("skip (disabled): %s" % key)
            continue
        entry = manifest.setdefault(key, {"revision": src["revision"], "files": {}})
        entry["revision"] = src["revision"]
        for rel in src["files"]:
            dest = os.path.join(SRC_DIR, key, rel.replace("/", os.sep))
            have = entry["files"].get(rel)
            if os.path.exists(dest) and not args.force:
                digest, size = sha256_file(dest), os.path.getsize(dest)
                if not have or have["sha256"] == digest:
                    entry["files"][rel] = {
                        "sha256": digest, "bytes": size,
                        "url": src["url_template"].format(revision=src["revision"], path=rel)}
                    print("cached  %s/%s (%d bytes)" % (key, rel, size))
                    continue
            url = src["url_template"].format(revision=src["revision"], path=rel)
            download(url, dest)
            entry["files"][rel] = {"sha256": sha256_file(dest), "bytes": os.path.getsize(dest),
                                   "url": url}
            print("fetched %s/%s (%d bytes)" % (key, rel, entry["files"][rel]["bytes"]))
    with open(MANIFEST_PATH, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")


def local_path(key, rel):
    return os.path.join(SRC_DIR, key, rel.replace("/", os.sep))


# --------------------------------------------------------------------------- tag writer

class TagWriter:
    """INSERT-or-update tag rows with an in-memory id cache."""

    def __init__(self, con):
        self.con = con
        self.cache = {row[0]: row[1] for row in con.execute("SELECT canonical_name, id FROM tag")}
        self.created = 0
        self.updated = 0

    def ensure(self, name, category=None, post_count=None, status=None,
               source_id=None, source_ref="", metadata=None):
        name = canonical(name)
        if not name:
            return None
        tid = self.cache.get(name)
        if tid is None:
            cur = self.con.execute(
                "INSERT INTO tag(canonical_name, search_name, danbooru_category, post_count, taxonomy_status)"
                " VALUES(?,?,?,?,?)",
                (name, name.replace("_", " "), category, post_count or 0, status or "unreviewed"))
            tid = cur.lastrowid
            self.cache[name] = tid
            self.created += 1
        else:
            sets, params = [], []
            if category:
                sets.append("danbooru_category=COALESCE(danbooru_category, ?)")
                params.append(category)
            if post_count:
                sets.append("post_count=MAX(post_count, ?)")
                params.append(post_count)
            if status and STATUS_RANK[status] > STATUS_RANK[
                    self.con.execute("SELECT taxonomy_status FROM tag WHERE id=?", (tid,)).fetchone()[0]]:
                sets.append("taxonomy_status=?")
                params.append(status)
            if sets:
                params.append(tid)
                self.con.execute("UPDATE tag SET %s WHERE id=?" % ", ".join(sets), params)
                self.updated += 1
        if source_id:
            self.con.execute(
                "INSERT OR IGNORE INTO tag_source(tag_id, source_id, source_ref, source_metadata)"
                " VALUES(?,?,?,?)",
                (tid, source_id, source_ref,
                 json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)))
        return tid

    def role(self, tid, role, confidence, source_id):
        self.con.execute(
            "INSERT INTO tag_role(tag_id, role, confidence, source_id) VALUES(?,?,?,?)"
            " ON CONFLICT(tag_id, role) DO UPDATE SET confidence=MAX(confidence, excluded.confidence)",
            (tid, role, confidence, source_id))

    def alias(self, alias_name, tid, source_id):
        cur = self.con.execute(
            "INSERT OR IGNORE INTO tag_alias(alias_name, tag_id, source_id) VALUES(?,?,?)",
            (alias_name.strip(), tid, source_id))
        return cur.rowcount


# --------------------------------------------------------------------------- loaders

def load_implications(con, snap_id, writer):
    path = local_path("danbooru_implications", "danbooru_implications.db")
    src = sqlite3.connect("file:%s?mode=ro" % path.replace(os.sep, "/"), uri=True)
    stats = {}
    for name, count, category, deprecated in src.execute(
            "SELECT name, post_count, category, is_deprecated FROM tags_all"):
        writer.ensure(name, DANBOORU_CATEGORY.get(category), count, None, snap_id, "tags_all",
                      {"deprecated": 1} if deprecated else None)
    stats["tags_all"] = writer.created
    aliases = alias_conflicts = 0
    for a, b in src.execute("SELECT a, b FROM aliases WHERE status='active'"):
        tid = writer.cache.get(canonical(b))
        if tid is None:
            stats["alias_dangling"] = stats.get("alias_dangling", 0) + 1
            continue
        inserted = writer.alias(canonical(a), tid, snap_id)
        aliases += inserted
        alias_conflicts += 1 - inserted
    relations = 0
    for a, b in src.execute("SELECT a, b FROM implications WHERE status='active'"):
        from_id = writer.cache.get(canonical(a))
        to_id = writer.cache.get(canonical(b))
        if from_id is None or to_id is None:
            stats["implies_dangling"] = stats.get("implies_dangling", 0) + 1
            continue
        con.execute(
            "INSERT OR IGNORE INTO tag_relation(from_tag_id, to_tag_id, relation, weight, source_id)"
            " VALUES(?,?,'implies',1.0,?)", (from_id, to_id, snap_id))
        relations += 1
    src.close()
    stats.update(aliases=aliases, alias_conflicts=alias_conflicts, implies=relations)
    return stats


def load_taxonomy(con, snap_id, writer):
    stats = {"roles": 0, "aliases": 0, "alias_conflicts": 0}
    with open(local_path("danbooru_taxonomy", "tags.csv"), encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            slot = row["slot"]
            confidence = float(row["confidence"])
            status = {"approved": "approved", "needs_review": "needs_review"}.get(
                row["status"], "unreviewed")
            tid = writer.ensure(row["tag"], row["danbooru_category"], int(row["post_count"]), status,
                                snap_id, "tags.csv",
                                {"category": row["category"], "subcategory": row["subcategory"],
                                 "slot": slot, "confidence": confidence, "status": row["status"]})
            for role in ROLE_BY_SLOT.get(slot, ()):
                writer.role(tid, role_for(row["tag"], role), confidence, snap_id)
                stats["roles"] += 1
            for alias in (a.strip() for a in row["aliases"].split(",")):
                if alias:
                    inserted = writer.alias(canonical(alias), tid, snap_id)
                    stats["aliases"] += inserted
                    stats["alias_conflicts"] += 1 - inserted
    return stats


def load_anima_index(con, snap_id, writer):
    stats = {"aliases": 0, "alias_conflicts": 0, "blocked": 0}
    path = local_path("anima_tag_index", "danbooru-tags/anima-1.0.csv")
    with open(path, encoding="utf-8", newline="") as fh:
        for tag, category, post_count, aliases in csv.reader(fh):
            tid = writer.ensure(tag, DANBOORU_CATEGORY.get(int(category)), int(post_count),
                                None, snap_id, "anima-1.0.csv", {"anima_category": int(category)})
            for alias in (a.strip() for a in aliases.split(",")):
                if alias:
                    inserted = writer.alias(canonical(alias), tid, snap_id)
                    stats["aliases"] += inserted
                    stats["alias_conflicts"] += 1 - inserted
    path = local_path("anima_tag_index", "danbooru-tags/banned_tags.csv")
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            tid = writer.ensure(row["tag"], "artist", int(row["count"] or 0), None, snap_id,
                                "banned_tags.csv")
            con.execute(
                "INSERT INTO tag_content_label(tag_id, scope, confidence, rationale)"
                " VALUES(?,'blocked',1.0,?)"
                " ON CONFLICT(tag_id) DO UPDATE SET scope='blocked', rationale=excluded.rationale",
                (tid, "danbooru banned/do-not-post artist tag; see %s" % row["url"]))
            stats["blocked"] += 1
    return stats


def add_concept(con, writer, snap_id, code, kind, name, description, tags, search_terms,
                metadata, content_scope="contextual"):
    code = code[:120]
    row = con.execute("SELECT id FROM visual_concept WHERE code=?", (code,)).fetchone()
    if row:
        return row[0], False
    cur = con.execute(
        "INSERT INTO visual_concept(code, kind, name, description, search_terms, content_scope,"
        " review_status, metadata_json) VALUES(?,?,?,?,?,?,'draft',?)",
        (code, kind, name, description, search_terms, content_scope,
         json.dumps(metadata, ensure_ascii=False, sort_keys=True)))
    cid = cur.lastrowid
    for index, tag in enumerate(tags):
        tid = writer.ensure(tag, source_id=snap_id, source_ref=metadata.get("source_ref", ""))
        con.execute(
            "INSERT OR IGNORE INTO concept_tag(concept_id, tag_id, usage, priority) VALUES(?,?,?,?)",
            (cid, tid, "primary" if index == 0 else "optional", 100 if index == 0 else 110 + index))
    return cid, True


def load_wardrobe(con, snap_id, writer):
    stats = {"roles": 0}
    with open(local_path("anima_wardrobe", "presets/attire_slots.json"), encoding="utf-8") as fh:
        slots = json.load(fh)["slots"]
    for slot, names in slots.items():
        for name in names:
            tid = writer.ensure(name, "general", None, None, snap_id, "attire_slots.json",
                                {"attire_slot": slot})
            writer.role(tid, role_for(name, "outfit"), 0.9, snap_id)
            stats["roles"] += 1

    # Presets are vocabulary + slot rules for the wardrobe layer: they seed tag_role
    # and provenance only. visual_concept rows come from Anima-Tools pose groups.
    with open(local_path("anima_wardrobe", "presets/anima_presets.json"), encoding="utf-8") as fh:
        sections = json.load(fh)["sections"]
    role_by_section = {"clothing": "outfit", "scene": "background",
                       "pose": "pose", "expression": "expression"}
    for section, payload in sections.items():
        role = role_by_section.get(section)
        for group in payload.get("groups", []):
            for item in group.get("items", []):
                for tag in item.get("tags", []):
                    tid = writer.ensure(tag, None, None, None, snap_id,
                                        "presets/anima_presets.json",
                                        {"section": section, "group": group["group"],
                                         "label": item["label"]})
                    if role:
                        writer.role(tid, role_for(tag, role), 0.8, snap_id)
                        stats["roles"] += 1
    return stats


def load_pose_tools(con, snap_id, writer):
    raw = open(local_path("anima_tools", "js/pose_data.js"), encoding="utf-8").read()
    items = json.loads(raw[raw.index("["):raw.rindex("]") + 1])  # pinned data, no eval
    stats = {"concepts": 0, "roles": 0}
    for item in items:
        tags = [t.strip() for t in item["tags"].split(",") if t.strip()]
        if not tags:
            continue
        kind = "interaction" if any("Interaction" in c for c in item["categories"]) else "pose"
        for tag in tags:
            tid = writer.ensure(tag, None, None, None, snap_id, "js/pose_data.js",
                                {"pose_id": item["id"], "categories": item["categories"]})
            writer.role(tid, role_for(tag, kind), 0.8, snap_id)
            stats["roles"] += 1
        code = "POSE_%s" % slug(item["name"])
        _, created = add_concept(
            con, writer, snap_id, code, kind, item["name"],
            "from Comfyui-Anima-Tools pose group %s" % ", ".join(item["categories"]),
            tags, " ".join([item["name"]] + item.get("traits", []) + tags),
            {"pose_id": item["id"], "categories": item["categories"],
             "source_ref": "js/pose_data.js"})
        stats["concepts"] += created
    return stats


LOADERS = {
    "danbooru_implications": load_implications,
    "danbooru_taxonomy": load_taxonomy,
    "anima_tag_index": load_anima_index,
    "anima_wardrobe": load_wardrobe,
    "anima_tools": load_pose_tools,
}


# --------------------------------------------------------------------------- load

def cmd_load(args):
    sources = load_sources()
    manifest = {}
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, encoding="utf-8") as fh:
            manifest = json.load(fh)
    con = connect(DB_PATH, wal=True)
    before = counts(con)
    writer = TagWriter(con)
    for key in LOADERS:
        src = sources[key]
        if not src["enabled"]:
            print("skip (disabled): %s" % key)
            continue
        files = manifest.get(key, {}).get("files", {})
        digest = hashlib.sha256("".join(sorted(
            "%s:%s" % (rel, meta["sha256"]) for rel, meta in files.items())).encode()).hexdigest() \
            if files else None
        row = con.execute("SELECT id FROM source_snapshot WHERE source_key=? AND revision=?",
                          (key, src["revision"])).fetchone()
        if row and not args.force:
            print("skip (already imported): %s@%s" % (key, src["revision"][:12]))
            continue
        if row:
            snap_id = row[0]
        else:
            snap_id = con.execute(
                "INSERT INTO source_snapshot(source_key, source_url, revision, license_note, sha256)"
                " VALUES(?,?,?,?,?)",
                (key, src["origin"], src["revision"], src["license"], digest)).lastrowid
        started = time.time()
        with con:
            stats = LOADERS[key](con, snap_id, writer)
            con.execute("INSERT INTO visual_concept_fts(visual_concept_fts) VALUES('rebuild')")
        print("loaded %-24s snapshot#%d %5.1fs %s" % (key, snap_id, time.time() - started, stats))
    after = counts(con)
    print("\ntable                        before      after      delta")
    for table in TABLES:
        if before[table] or after[table]:
            print("%-24s %9d %10d %10d" % (table, before[table], after[table],
                                           after[table] - before[table]))
    con.execute("PRAGMA optimize")
    con.close()


# --------------------------------------------------------------------------- verify

MINIMUMS = {
    "tag": 160000,
    "tag_alias": 40000,
    "tag_relation": 40000,
    "tag_role": 5000,
    "tag_source": 300000,
    "visual_concept": 200,
}
CHECKS = []


def check(name, ok, detail):
    CHECKS.append({"check": name, "ok": bool(ok), "detail": detail})
    print("%-4s %-28s %s" % ("OK" if ok else "FAIL", name, detail))
    return ok


def cmd_verify(args):
    del CHECKS[:]
    con = connect(DB_PATH)
    check("integrity_check",
          con.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
          "PRAGMA integrity_check")
    fk = con.execute("PRAGMA foreign_key_check").fetchall()
    check("foreign_key_check", not fk, "%d violations" % len(fk))
    concepts = con.execute("SELECT count(*) FROM visual_concept").fetchone()[0]
    fts = con.execute("SELECT count(*) FROM visual_concept_fts").fetchone()[0]
    check("fts5_index", fts == concepts, "fts rows %d == concept rows %d" % (fts, concepts))
    hits = con.execute("SELECT count(*) FROM visual_concept_fts WHERE visual_concept_fts MATCH ?",
                       ("pose",)).fetchone()[0]
    check("fts5_query", hits > 0, "MATCH 'pose' -> %d rows" % hits)
    rows = counts(con)
    for table, minimum in MINIMUMS.items():
        check("rows:%s" % table, rows[table] >= minimum,
              "%d (min %d)" % (rows[table], minimum))
    sources = load_sources()
    imported = {r[0] for r in con.execute("SELECT source_key FROM source_snapshot")}
    missing = sorted(k for k, s in sources.items() if s["enabled"] and k not in imported)
    check("sources_imported", not missing, "%d imported, missing %s" % (len(imported), missing or "none"))
    orphan_roles = con.execute(
        "SELECT count(*) FROM tag_role r LEFT JOIN tag t ON t.id=r.tag_id WHERE t.id IS NULL"
    ).fetchone()[0]
    check("roles_link_to_tags", orphan_roles == 0, "%d orphan tag_role rows" % orphan_roles)
    unscoped = con.execute(
        "SELECT count(*) FROM visual_concept WHERE content_scope='contextual' AND review_status='draft'"
    ).fetchone()[0]
    check("content_review_pending", True,
          "%d/%d draft concepts still 'contextual' (P2 review gate, not an import failure)"
          % (unscoped, concepts))
    con.close()

    report = {"db": os.path.relpath(DB_PATH, ROOT), "tables": rows, "checks": CHECKS,
              "sources": {r[0]: {"revision": r[1], "sha256": r[2]}
                          for r in _snapshot_rows(DB_PATH)}}
    with open(REPORT_PATH, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")
    failed = [c for c in CHECKS if not c["ok"]]
    print("\n%d checks, %d failed -> %s" % (len(CHECKS), len(failed), REPORT_PATH))
    return 1 if failed else 0


def _snapshot_rows(path):
    con = connect(path)
    try:
        return con.execute(
            "SELECT source_key, revision, sha256 FROM source_snapshot ORDER BY source_key").fetchall()
    finally:
        con.close()


# --------------------------------------------------------------------------- cli

def cmd_all(args):
    cmd_schema(argparse.Namespace(force=args.force))
    cmd_fetch(argparse.Namespace(force=False))
    cmd_load(argparse.Namespace(force=False))
    return cmd_verify(args)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("schema", help="rebuild db from sql/schema_v1.sql")
    p.add_argument("--force", action="store_true", help="drop the existing db")
    p.set_defaults(func=cmd_schema)
    p = sub.add_parser("fetch", help="download pinned sources")
    p.add_argument("--force", action="store_true", help="re-download even if cached")
    p.set_defaults(func=cmd_fetch)
    p = sub.add_parser("load", help="import every enabled source")
    p.add_argument("--force", action="store_true", help="re-import an already-imported revision")
    p.set_defaults(func=cmd_load)
    p = sub.add_parser("verify", help="integrity / fk / fts5 / row gates")
    p.set_defaults(func=cmd_verify)
    p = sub.add_parser("all", help="schema -> fetch -> load -> verify")
    p.add_argument("--force", action="store_true", help="drop and rebuild the db")
    p.set_defaults(func=cmd_all)
    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
