"""Create an origin character and optionally rebind Story roles to it.

Dry-run by default. Nothing is written unless --apply and --user-approved are
both given; the reviewer decides whether to run it.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'database/src'))

from n2m_db import connect, apply_migrations, bind_role, uid  # noqa: E402


def norm(tag: str) -> str:
    return ' '.join(tag.lower().replace('_', ' ').split())


def validate_tags(con, tags):
    """Every anchor must exist in the catalog vocabulary; no invented tags."""
    known = {norm(r[0]) for r in con.execute('SELECT name FROM catalog_tags')}
    known |= {norm(r[0]) for r in con.execute('SELECT label_en FROM vocabulary')}
    missing = [t for t in tags if norm(t) not in known]
    if missing:
        raise ValueError(f'UNKNOWN_ANCHOR_TAGS: {missing}')
    return [norm(t) for t in tags]


COLORS = {'black', 'brown', 'blonde', 'white', 'silver', 'grey', 'gray', 'red',
          'pink', 'blue', 'green', 'purple', 'orange', 'gold', 'auburn'}


def check_conflicts(tags):
    """One colour per hair/eyes group; the user must pick, not the machine."""
    groups = {}
    for t in tags:
        parts = t.split()
        if len(parts) >= 2 and parts[0] in COLORS and parts[-1] in ('hair', 'eyes'):
            groups.setdefault(parts[-1], set()).add(parts[0])
    bad = {k: sorted(v) for k, v in groups.items() if len(v) > 1}
    if bad:
        raise ValueError(f'CONFLICTING_ANCHORS: {bad}')


def create_origin(con, source_id, slug, name, anchors, outfit_tags,
                  outfit_name='default', review_id=None,
                  minor_check='NO_EVIDENCE', from_source_candidates=False,
                  db_tag_ids=None):
    if minor_check == 'EXPLICIT_MINOR':
        raise ValueError('POLICY_BLOCKED: explicit minor evidence has no replacement branch')
    if minor_check not in ('NO_EVIDENCE', 'AMBIGUOUS', 'CONFIRMED_ADULT'):
        raise ValueError(f'Invalid minor_check: {minor_check}')
    src = con.execute('SELECT * FROM characters WHERE id=?', (source_id,)).fetchone()
    if src is None:
        raise ValueError(f'Source character not found: {source_id}')
    if from_source_candidates and not anchors:
        anchors = [r[0] for r in con.execute(
            "SELECT t.name FROM character_tags c JOIN catalog_tags t ON t.id=c.tag_id "
            "WHERE c.character_id=? AND c.tag_role='APPEARANCE_CANDIDATE'", (source_id,))]
    if not anchors:
        raise ValueError('MISSING_IDENTITY_ANCHORS: pass --anchor or --from-source-candidates')
    if not outfit_tags:
        raise ValueError('MISSING_OUTFIT_TAGS: pass --outfit at least once')
    anchors = validate_tags(con, anchors)
    outfit_tags = validate_tags(con, outfit_tags)
    check_conflicts(anchors)

    origin_id = f'character:original_adult_au:{slug}'
    universe_id = 'universe:original_adult_au'
    identity = {
        'provenance': 'derived_from_source=UNKNOWN',
        'replacement_mode': 'user_approved_original',
        'age_status_source': src['age_status'],
        'review_id': review_id,
        'minor_check': minor_check,
        'derived_from': source_id,
        'prompt_tags': anchors,
        'outfits': {outfit_name: {'prompt_tags': outfit_tags}},
        'forbidden_reuse': [src['display_name'], src['slug']],
    }
    con.execute('INSERT OR IGNORE INTO universes(id,slug,display_name) VALUES(?,?,?)',
                (universe_id, 'original_adult_au', 'Original Adult AU'))
    con.execute('''INSERT INTO characters(id,universe_id,slug,display_name,age_status,
                   identity_description,identity_json,identity_review)
                   VALUES(?,?,?,?,?,?,?,?)''',
                (origin_id, universe_id, slug, name, 'CONFIRMED_ADULT',
                 'Original adult character; user-approved anchors',
                 json.dumps(identity, ensure_ascii=False), 'REVIEWED'))
    outfit_id = f'outfit:original_adult_au:{slug}:{outfit_name}'
    con.execute('''INSERT INTO outfits(id,character_id,slug,name,outfit_kind,description,verification)
                   VALUES(?,?,?,?,?,?,?)''',
                (outfit_id, origin_id, outfit_name, outfit_name, 'ORIGINAL',
                 ', '.join(outfit_tags), 'REVIEWED'))
    return {'origin_id': origin_id, 'outfit_id': outfit_id, 'identity': identity}


def revert_origin(con, origin_id, story_id, role_key):
    """Role-level swap back, like blind cast: casting changes, history kept."""
    origin = con.execute('SELECT * FROM characters WHERE id=?', (origin_id,)).fetchone()
    if origin is None:
        raise ValueError(f'Origin character not found: {origin_id}')
    identity = json.loads(origin['identity_json'] or '{}')
    source_id = identity.get('derived_from')
    if identity.get('replacement_mode') != 'user_approved_original' or not source_id:
        raise ValueError('NOT_AN_ORIGIN_REPLACEMENT: missing derived_from/user_approved_original')
    if not con.execute('SELECT 1 FROM characters WHERE id=?', (source_id,)).fetchone():
        raise ValueError(f'Source character missing: {source_id}')
    role = con.execute('''SELECT r.id, c.character_id FROM story_roles r
                          LEFT JOIN story_castings c ON c.story_role_id=r.id AND c.until_revision IS NULL
                          WHERE r.story_id=? AND r.role_key=?''', (story_id, role_key)).fetchone()
    if role is None:
        raise ValueError(f'Role {role_key} not found in story')
    if role['character_id'] != origin_id:
        raise ValueError(f'ROLE_NOT_BOUND_TO_ORIGIN: {role["character_id"]}')
    return {'source_id': source_id, 'role_key': role_key, 'story_id': story_id}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', type=Path, default=ROOT / 'database/data/novel2anima.db')
    p.add_argument('--source', help='character to derive the origin from')
    p.add_argument('--revert', help='origin character id to swap back to its source')
    p.add_argument('--slug', help='origin slug (with --source)')
    p.add_argument('--name', help='origin display name (with --source)')
    p.add_argument('--anchor', action='append', default=[])
    p.add_argument('--outfit', action='append', default=[])
    p.add_argument('--outfit-name', default='default')
    p.add_argument('--from-source-candidates', action='store_true')
    p.add_argument('--minor-check', default='NO_EVIDENCE',
                   choices=('NO_EVIDENCE', 'AMBIGUOUS', 'CONFIRMED_ADULT', 'EXPLICIT_MINOR'))
    p.add_argument('--story-id')
    p.add_argument('--role')
    p.add_argument('--review-id')
    p.add_argument('--user-approved', action='store_true')
    p.add_argument('--apply', action='store_true')
    args = p.parse_args(argv)

    con = connect(args.db)
    apply_migrations(con)
    try:
        if args.revert:
            if not (args.story_id and args.role):
                raise ValueError('--story-id and --role required with --revert')
            plan = {'action': 'revert_origin',
                    **revert_origin(con, args.revert, args.story_id, args.role)}
            plan['applied'] = bool(args.apply and args.user_approved)
            if plan['applied']:
                if not args.review_id:
                    raise ValueError('--review-id required when applying')
                plan['new_revision'] = bind_role(
                    con, args.story_id, args.role, plan['source_id'])
                con.commit()
            else:
                con.rollback()
            print(json.dumps(plan, ensure_ascii=False, indent=2))
            return
        if not (args.source and args.slug and args.name):
            raise ValueError('--source, --slug and --name are required unless --revert')
        result = create_origin(con, args.source, args.slug, args.name, args.anchor,
                               args.outfit, args.outfit_name, args.review_id,
                               args.minor_check, args.from_source_candidates)
        plan = {'action': 'create_origin', **result}
        if args.story_id or args.role:
            if not (args.story_id and args.role):
                raise ValueError('--story-id and --role must be given together')
            plan['rebind'] = {'story_id': args.story_id, 'role_key': args.role,
                              'character_id': result['origin_id'],
                              'outfit_id': result['outfit_id']}
        plan['applied'] = bool(args.apply and args.user_approved)
        if plan['applied']:
            if not args.review_id:
                raise ValueError('--review-id required when applying')
            if args.story_id:
                plan['rebind']['new_revision'] = bind_role(
                    con, args.story_id, args.role, result['origin_id'], result['outfit_id'])
            con.commit()
        else:
            con.rollback()
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    except Exception:
        con.rollback()
        raise


if __name__ == '__main__':
    main()
