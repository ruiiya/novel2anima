"""V5 structural narrative continuity and deterministic prompt assembly.

No LLM or renderer. The approved storyboard and ShotSpec provide semantic
decisions; these functions enforce the declared contract, not image fidelity.
"""
from __future__ import annotations

import importlib.util
from functools import lru_cache
from pathlib import Path
import re


NARRATIVE_ROLES = {'ESTABLISH','INITIATE','PROLONG','PEAK','REACTION','RESOLUTION','TRANSITION','DETAIL'}
SAFETY = {'safe','sensitive','nsfw','explicit'}


def ensure(ok, message):
    if not ok:
        raise ValueError(message)


def is_v5(plan):
    version = plan.get('schema_version', 4)
    ensure(type(version) is int and version in (4,5), 'Unknown storyboard schema_version')
    return version == 5


def tags(values, label):
    ensure(isinstance(values,list) and all(isinstance(t,str) and t and t.strip()==t
        and t.lower()==t and not re.search(r'[,\r\n]',t) for t in values), f'INVALID_TAG_BLOCK: {label}')
    ensure(len(values)==len(set(values)), f'DUPLICATE_TAG: {label}')
    return values


def validate_bible(plan):
    visual=plan['visual_bible']
    scenes=plan.get('scenes')
    ensure(isinstance(scenes,dict) and scenes, 'V5 requires scenes')
    for group in ('characters','locations','props','styles'):
        for name, entry in visual[group].items():
            tags(entry.get('prompt_tags'),f'{group}/{name}')
            if group in ('characters','styles'):
                ensure(bool(entry['prompt_tags']), f'MISSING_LOCKED_TAGS: {group}/{name}')
            if group=='characters':
                outfits=entry.get('outfits',{})
                ensure(isinstance(outfits,dict),f'Invalid outfits: {name}')
                for outfit, block in outfits.items():
                    ensure(isinstance(block,dict) and bool(tags(block.get('prompt_tags'),outfit)),f'Invalid outfit: {outfit}')
    for name, scene in scenes.items():
        ensure(isinstance(name,str) and bool(re.fullmatch(r'[A-Za-z0-9_-]+',name)), 'Invalid scene key')
        ensure(isinstance(scene,dict) and scene.get('location_key') in visual['locations']
               and scene.get('style_key') in visual['styles'] and isinstance(scene.get('time_key'),str)
               and bool(scene['time_key'].strip()),f'Invalid scene: {name}')
        roles=scene.get('role_keys')
        ensure(isinstance(roles,list) and len(roles)==len(set(roles)) and set(roles)<=set(visual['characters']),f'Invalid scene roles: {name}')
        tags(scene.get('lighting_tags'),f'lighting/{name}')


def validate_slot(plan, slot, prev):
    k=slot['shot_key']
    scene=plan['scenes'].get(slot.get('scene_key'))
    ensure(scene is not None and slot['location_key']==scene['location_key'] and slot['style_key']==scene['style_key'],f'SCENE_LOCK_MISMATCH: {k}')
    ensure(set(slot['role_keys'])<=set(scene['role_keys']),f'SCENE_ROLE_MISMATCH: {k}')
    visible=tags(slot.get('visible_location_tags'),k)
    ensure(set(visible)<=set(plan['visual_bible']['locations'][slot['location_key']]['prompt_tags']),f'LOCATION_TAG_DRIFT: {k}')
    transition=slot['transition']
    ensure(slot.get('narrative_role') in NARRATIVE_ROLES or (transition in ('START','INDEPENDENT') and slot.get('narrative_role') is None), f'NARRATIVE_ROLE_REQUIRED: {k}')
    ensure(type(slot.get('story_time')) is int and slot['story_time']>=0,f'STORY_TIME_REQUIRED: {k}')
    if prev is not None:
        if transition in ('CONTINUOUS','CAMERA_CUT','SAME_MOMENT','FLASHBACK'):
            ensure(prev['scene_key']==slot['scene_key'],f'SCENE_CHANGE_WITHOUT_CUT: {k}')
        if transition=='SAME_MOMENT':
            ensure(slot['story_time']==prev['story_time'],f'SAME_MOMENT_TIME_MISMATCH: {k}')
        else:
            ensure(slot['story_time']>=prev['story_time'],f'TIMELINE_MISMATCH: {k}')
        if transition=='FLASHBACK':
            ensure(slot['story_time']==prev['story_time'],f'FLASHBACK_REQUIRES_HISTORICAL_ANCHOR: {k}')
    return scene


def validate_moment(state, apply_delta):
    moment=state.get('moment')
    ensure(isinstance(moment,dict) and set(moment)=={'at_shot','at_delta','after_delta'},'MOMENT_REQUIRED')
    ensure(apply_delta(state['before'],moment['at_delta'])==moment['at_shot'], 'AT_SHOT_DELTA_MISMATCH')
    ensure(apply_delta(moment['at_shot'],moment['after_delta'])==state['after'], 'AFTER_SHOT_DELTA_MISMATCH')
    return moment['at_shot']


def validate_states(plan, slot, states, apply_delta):
    scene=plan['scenes'][slot['scene_key']]
    ensure(set(states)==set(scene['role_keys'])|{None},f'SCENE_SNAPSHOTS_MISSING: {slot["shot_key"]}')
    moment={role:validate_moment(state,apply_delta) for role,state in states.items()}
    for state in (moment[None], states[None]['after']):
        ensure(state.get('location_key')==scene['location_key'] and state.get('time_key')==scene['time_key'],'SCENE_STATE_MISMATCH')
    for role in scene['role_keys']:
        outfits=plan['visual_bible']['characters'][role].get('outfits',{})
        if outfits:
            ensure(moment[role].get('outfit_key') in outfits and states[role]['after'].get('outfit_key') in outfits,f'OUTFIT_STATE_MISMATCH: {role}')
    return moment


@lru_cache(maxsize=1)
def _validator():
    path=Path(__file__).resolve().parents[2]/'tools/novel2anima/validate_anima_prompt.py'
    spec=importlib.util.spec_from_file_location('n2a_prompt_validator',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate


def compile_prompt(plan, slot, shot_spec, moment):
    """Assemble approved locked blocks plus agent-authored shot-specific blocks."""
    visual=plan['visual_bible']
    scene=plan['scenes'][slot['scene_key']]
    blocks=shot_spec.get('prompt_blocks')
    ensure(isinstance(blocks,dict) and set(blocks)=={'prefix','subjects','action','camera','prose'},'PROMPT_BLOCKS_REQUIRED')
    prefix=tags(blocks['prefix'],'prefix')
    ensure(sum(t in SAFETY for t in prefix)==1, 'Exactly one content rating tag required')
    dynamic=prefix+tags(blocks['subjects'],'subjects')+tags(blocks['action'],'action')+tags(blocks['camera'],'camera')
    output=prefix+blocks['subjects']
    locked=[]
    for role in slot['role_keys']:
        char=visual['characters'][role]
        locked+=char['prompt_tags']
        outfits=char.get('outfits',{})
        if outfits:
            locked+=outfits[moment[role]['outfit_key']]['prompt_tags']
    output+=locked
    output+=tags(blocks['action'],'action')+tags(blocks['camera'],'camera')
    output+=slot['visible_location_tags']+scene['lighting_tags']
    for prop in slot.get('prop_keys',[]):
        output+=visual['props'][prop]['prompt_tags']
    output+=visual['styles'][slot['style_key']]['prompt_tags']
    selected=set(locked+slot['visible_location_tags']+scene['lighting_tags']+
        visual['styles'][slot['style_key']]['prompt_tags'])
    for prop in slot.get('prop_keys',[]):
        selected.update(visual['props'][prop]['prompt_tags'])
    catalog={tag for group in ('characters','locations','styles','props')
             for entry in visual[group].values() for tag in entry['prompt_tags']}
    catalog.update(tag for entry in visual['characters'].values()
                   for outfit in entry.get('outfits',{}).values() for tag in outfit['prompt_tags'])
    catalog.update(tag for sc in plan['scenes'].values() for tag in sc['lighting_tags'])
    ensure(not (set(dynamic)&(catalog-selected)), 'LOCKED_TAG_CONFLICT: dynamic block contains an inactive canonical tag')
    ensure(sum(t in SAFETY for t in set(output))==1, 'Conflicting content rating tags')
    prose=blocks['prose']
    ensure(isinstance(prose,str) and '\n' not in prose and '\r' not in prose,'Invalid prose')
    text=', '.join(dict.fromkeys(output)) + ('\n'+prose.strip() if prose.strip() else '')
    issues=_validator()(text)
    ensure(not issues,'PROMPT_FORMAT: '+', '.join(issues))
    return text
