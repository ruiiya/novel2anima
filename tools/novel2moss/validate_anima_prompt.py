#!/usr/bin/env python3
"""Validate one Anima positive prompt (tag block + up to 2 prose sentences).

Checks format and integrity only; content fidelity still needs QA against ShotSpec.
Contract: docs/novel2moss/ANIMA_TAG_PROMPT.md
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

FORMAT = 'anima-tag-v1'

SAFETY = ('safe', 'sensitive', 'nsfw', 'explicit')
FRAMING = ('close-up', 'upper body', 'cowboy shot', 'full body', 'wide shot')
ANGLE_HEIGHT = ('from above', 'from below')
ANGLE_YAW = ('from side', 'three-quarter view', 'from behind')
# Aesthetic v1.1 was trained with quality labels stripped; these tags only flatten style.
QUALITY_TAGS = ('masterpiece', 'best quality', 'worst quality', 'highres', 'absurdres',
                'ultra detailed', 'ultra-detailed', '8k', '4k')
SUBJECT_RE = re.compile(r'\b(\d+(?:girl|boy|other)s?|multiple (?:girls|boys))\b')
SCORE_RE = re.compile(r'\bscore_\d+\b')
UNDERSCORE_RE = re.compile(r'[a-z]_[a-z]', re.I)
BBOX_RE = re.compile(r'\[\s*-?\d+\s*,\s*-?\d+\s*,')
MAX_WORDS = 280  # ~480 T5 tokens; detail loss starts near 512


def has_tag(tag_line: str, name: str) -> bool:
    return re.search(rf'(?<![\w-]){re.escape(name)}(?![\w-])', tag_line) is not None


def validate(text: str) -> list[str]:
    errors = []
    if not text.strip():
        return ['EMPTY_PROMPT']
    if text.lstrip().startswith('```') or text.rstrip().endswith('```'):
        errors.append('CODE_FENCE')
    if '\x00' in text:
        errors.append('NUL_CHARACTER')

    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    tag_line = lines[0] if lines else ''
    prose = ' '.join(lines[1:])
    tags = [t.strip() for t in tag_line.split(',') if t.strip()]

    if len(tags) < 3:
        errors.append('TAG_BLOCK_MISSING')
    if re.search(r'[A-Z]', tag_line):
        errors.append('TAG_UPPERCASE')
    if UNDERSCORE_RE.search(tag_line) and not SCORE_RE.search(tag_line):
        errors.append('TAG_UNDERSCORE')
    if re.search(r',\S', tag_line) or re.search(r'\s,', tag_line):
        errors.append('TAG_COMMA_SPACING')
    if SCORE_RE.search(text):
        errors.append('SCORE_TAG_FORBIDDEN')
    low = tag_line.lower()
    if any(has_tag(low, q) for q in QUALITY_TAGS):
        errors.append('QUALITY_TAG_FORBIDDEN')
    if not any(has_tag(low, s) for s in SAFETY):
        errors.append('SAFETY_TAG_MISSING')
    if not SUBJECT_RE.search(low):
        errors.append('SUBJECT_COUNT_MISSING')
    framings = [f for f in FRAMING if has_tag(low, f)]
    if not framings:
        errors.append('FRAMING_TAG_MISSING')
    elif len(framings) > 1:
        errors.append('CAMERA_CONFLICT')
    if sum(has_tag(low, a) for a in ANGLE_HEIGHT) > 1:
        errors.append('CAMERA_CONFLICT')
    if sum(has_tag(low, a) for a in ANGLE_YAW) > 1:
        errors.append('CAMERA_CONFLICT')

    if BBOX_RE.search(text):
        errors.append('BBOX_IN_PROMPT')
    if text.lstrip().startswith('{'):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(data, dict):
                errors.append('JSON_OBJECT_NOT_PROMPT')
    if len(text.split()) > MAX_WORDS:
        errors.append('TOKEN_BUDGET_EXCEEDED')
    if len([s for s in re.split(r'[.!?]+', prose) if s.strip()]) > 2:
        errors.append('PROSE_TOO_LONG')
    return errors


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('file', type=Path)
    p.add_argument('--manifest', type=Path)
    args = p.parse_args()
    data = args.file.read_bytes()
    text = data.decode('utf-8')
    issues = validate(text)
    digest = hashlib.sha256(data).hexdigest()
    if args.manifest:
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        if digest != manifest.get('prompt_sha256'):
            issues.append('SHA256_MISMATCH')
        if manifest.get('format') != FORMAT:
            issues.append('FORMAT_MISMATCH')
    print(json.dumps({'status': 'PASS' if not issues else 'BLOCKED',
                      'prompt_sha256': digest, 'issues': sorted(set(issues))},
                     ensure_ascii=False))
    return 1 if issues else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (UnicodeError, OSError, json.JSONDecodeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(2)
