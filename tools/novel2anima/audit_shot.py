#!/usr/bin/env python3
"""Audit basic structured source→ShotSpec fidelity. NOT a full semantic/visual review.

Exit 0 if deterministic checks pass; 2 if missing roles/labels/event direction.
"""
import argparse
import json
import sys
from pathlib import Path


def _events(story):
    for act in story.get("acts", []):
        for beat in act.get("beats", []):
            for event in beat.get("events", []):
                yield event


def audit(story, shot):
    findings = []

    def fail(rule, message, source=None, target=None):
        findings.append({"rule": rule, "status": "BLOCKED", "evidence": message,
                         "source_pointer": source, "target_pointer": target, "autofix": False})

    if story.get("story_id") != shot.get("story_id"):
        fail("STORY_ID_MISMATCH", "Shot does not belong to story", "/story_id", "/story_id")

    source_labels = story.get("intent", {}).get("raw_labels", [])
    shot_labels = shot.get("intent", {}).get("raw_labels", [])
    if not isinstance(source_labels, list) or not isinstance(shot_labels, list):
        fail("SOURCE_LABEL_INVALID", "raw_labels must be arrays")
    else:
        # Track exact source labels; do not normalize/censor/downgrade any classification.
        for label in source_labels:
            if label not in shot_labels:
                fail("SOURCE_LABEL_LOSS", f"Source label dropped/rewritten: {label!r}",
                     "/intent/raw_labels", "/intent/raw_labels")

    source_profile = story.get("intent", {}).get("content_profile")
    if source_profile is not None and source_profile != shot.get("intent", {}).get("content_profile"):
        fail("CONTENT_PROFILE_CHANGED", "Content profile changed", "/intent/content_profile", "/intent/content_profile")

    event_id = shot.get("event_id")
    events = [evt for evt in _events(story) if evt.get("event_id") == event_id]
    if len(events) != 1:
        fail("EVENT_UNRESOLVED", f"Expected one matching event for {event_id!r}; got {len(events)}")
    else:
        event, interaction = events[0], shot.get("interaction", {})
        for key in ("actor_id", "target_id", "primary_action"):
            if event.get(key) != interaction.get(key):
                fail("ACTOR_TARGET_MISMATCH" if key != "primary_action" else "ACTION_CHANGED",
                     f"Event {key}: {event.get(key)!r} != shot {interaction.get(key)!r}",
                     f"/events/{event_id}/{key}", f"/interaction/{key}")

    known = {p.get("character_id") for p in story.get("characters", [])}
    participants = shot.get("participants", [])
    if not isinstance(participants, list):
        fail("PARTICIPANTS_INVALID", "participants must be an array")
        participants = []
    ids = [p.get("character_id") for p in participants if isinstance(p, dict)]
    if len(ids) != len(set(ids)):
        fail("DUPLICATE_PARTICIPANT", "Participant IDs repeated")
    for pid in ids:
        if pid not in known:
            fail("UNKNOWN_PARTICIPANT", f"Participant {pid!r} is not in story cast")
    interaction = shot.get("interaction", {})
    if isinstance(interaction, dict):
        for key in ("actor_id", "target_id"):
            value = interaction.get(key)
            if value is not None and value not in ids:
                fail("PARTICIPANT_LOSS", f"{key} {value!r} absent from shot participants")
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", type=Path, required=True)
    parser.add_argument("--shot", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        story = json.loads(args.story.read_text(encoding="utf-8"))
        shot = json.loads(args.shot.read_text(encoding="utf-8"))
        findings = audit(story, shot)
        result = {"shot_id": shot.get("shot_id"), "status": "BLOCKED" if findings else "PASS",
                  "scope": "deterministic_source_shot_fields_only", "findings": findings}
        raw = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(raw, encoding="utf-8")
        print(raw)
        return 2 if findings else 0
    except (OSError, ValueError, TypeError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
