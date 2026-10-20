"""Clone the Hasumi track plan for three more Kivotos characters.

Colors: Yuuka purple, Mika white, Asuna pink. Adult AU, explicit solo.
Usage: python act_tools/generators/clone_track_roster.py
"""
import json
import pathlib
import pathlib as _p, sys as _s
_s.path.insert(0, str(_p.Path(__file__).resolve().parents[1]))
_s.path.insert(0, str(_p.Path(__file__).resolve().parents[2] / "etl"))
import sqlite3

SRC = pathlib.Path("data/plans/act30_hasumi_track_60.json")
DB = "db/novel_anima.db"

ROSTER = [
    {
        "code": "KARIN", "name": "Karin", "slug": "karin", "act": 31,
        "title": "Karin - Binh minh den", "buruma": "black_buruma",
        "buruma_vi": "buruma den",
        "identity": "karin_(blue_archive)",
        "attributes": ["dark-skinned_female", "black_hair", "long_hair",
                       "red_eyes", "halo", "large_breasts"],
        "note": "Kurosaki Karin (Blue Archive, Millennium) track AU; adult.",
    },
    {
        "code": "YUUKA", "name": "Yuuka", "slug": "yuuka", "act": 32,
        "title": "Yuuka - Binh minh tim", "buruma": "purple_buruma",
        "buruma_vi": "buruma tim",
        "identity": "yuuka_(track)_(blue_archive)",
        "attributes": ["purple_hair", "long_hair", "halo", "purple_eyes",
                       "large_breasts", "hairband"],
        "note": "Hayase Yuuka (Blue Archive, Millennium) track AU; adult.",
        "replace": [("high_ponytail", "ponytail"),
                    ("black_hairband", "hairband"),
                    ("high ponytail", "ponytail"),
                    ("long black hair", "long purple hair")],
    },
    {
        "code": "MIKA", "name": "Mika", "slug": "mika", "act": 33,
        "title": "Mika - Binh minh trang", "buruma": "white_buruma",
        "buruma_vi": "buruma trang",
        "identity": "mika_(track)_(blue_archive)",
        "attributes": ["blonde_hair", "long_hair", "wings", "white_wings",
                       "halo", "blue_eyes", "large_breasts"],
        "note": "Misono Mika (Blue Archive, Trinity) track AU; adult.",
    },
    {
        "code": "ASUNA", "name": "Asuna", "slug": "asuna", "act": 34,
        "title": "Asuna - Binh minh hong", "buruma": "pink_buruma",
        "buruma_vi": "buruma hong",
        "identity": "asuna_(blue_archive)",
        "attributes": ["blue_hair", "long_hair", "halo", "blue_eyes",
                       "large_breasts", "pale_skin"],
        "note": "Ichinose Asuna (Blue Archive, Millennium) track AU; adult.",
    },
]


def swap_text(value, item):
    out = (value.replace("Hasumi", item["name"])
                .replace("hasumi_(track)_(blue_archive)", item["identity"])
                .replace("blue_buruma", item["buruma"])
                .replace("blue buruma", item["buruma"].split("_")[0] + " buruma")
                .replace("buruma xanh", item["buruma_vi"])
                .replace("Binh minh uot", item["title"].split(" - ", 1)[1]))
    for old, new in item.get("replace", []):
        out = out.replace(old, new)
    return out


def build(item, write=True, out_dir="data/plans"):
    plan = json.loads(SRC.read_text(encoding="utf-8"))
    plan["project"]["title"] = item["title"]
    plan["project"]["idea"] = swap_text(plan["project"]["idea"], item)
    plan["prompt_file"] = "prompts/act%d_%s_track_60.txt" % (item["act"], item["slug"])
    plan["act"]["title"] = item["title"]
    ch = plan["characters"][0]
    ch["code"] = item["code"]
    ch["name"] = item["name"]
    ch["identity_line"] = "1girl, solo, " + ", ".join([item["identity"], "blue_archive"] + item["attributes"])
    ch["identity_json"] = {
        "identity_tags": [item["identity"], "blue_archive"],
        "attributes": item["attributes"] + ["1girl", "solo"],
        "adult": True,
        "note": item["note"],
    }
    ch["outfit_json"] = {
        "default": [swap_text(x, item) for x in ch["outfit_json"]["default"]],
        "variants": {k: [swap_text(x, item) for x in v]
                     for k, v in ch["outfit_json"]["variants"].items()},
    }
    for shot in plan["shots"]:
        for key in ("outfit", "cast", "action", "expression", "motion", "camera", "pose"):
            shot[key] = [swap_text(x, item) for x in shot.get(key, [])]
        shot["caption"] = swap_text(shot["caption"], item)
        shot["beat"] = swap_text(shot["beat"], item)
        shot["carry"] = swap_text(shot["carry"], item)
        shot["delta"] = swap_text(shot["delta"], item)
        shot["participants"] = [item["code"]]
        shot["sequence"]["actor"] = item["code"]
    out = pathlib.Path(out_dir) / ("act%d_%s_track_60.json" % (item["act"], item["slug"]))
    if write:
        out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    md_src = SRC.with_suffix(".md").read_text(encoding="utf-8")
    md = swap_text(md_src, item)
    md = md.replace("data/plans/act30_hasumi_track_60.json", str(out).replace("\\", "/"))
    md = md.replace("prompts/act30_hasumi_track_60.txt", plan["prompt_file"])
    if write:
        out.with_suffix(".md").write_text(md, encoding="utf-8")
    return out, plan


def check_tags(plan):
    names = set()
    for ch in plan["characters"]:
        names.update(ch["identity_json"].get("identity_tags", []))
        names.update(ch["identity_json"].get("attributes", []))
        for refs in ch["outfit_json"].values():
            if isinstance(refs, list):
                names.update(refs)
    for shot in plan["shots"]:
        for key in ("outfit", "action", "expression", "pose", "camera", "motion", "cast"):
            names.update(shot.get(key, []))
    names.update(plan["background_line"].split(", "))
    con = sqlite3.connect(DB)
    missing = [n for n in sorted(names) if not con.execute(
        "SELECT 1 FROM tag WHERE canonical_name=?", (n,)).fetchone()]
    con.close()
    return missing


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan-dir", default="data/plans")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    global SRC
    SRC = pathlib.Path(args.plan_dir) / SRC.name
    for item in ROSTER:
        out, plan = build(item, write=not args.dry_run, out_dir=args.plan_dir)
        missing = check_tags(plan)
        if missing:
            raise SystemExit("%s missing tags: %s" % (out, ", ".join(missing)))
        print(("would write " if args.dry_run else "wrote ") + "%s (%d shots)" % (out, len(plan["shots"])))


if __name__ == "__main__":
    main()
