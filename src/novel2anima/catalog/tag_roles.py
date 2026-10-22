"""Single source for tag-role overrides shared by build, QA and seed (v1).

Import sources (attire slots, pose groups, wardrobe presets) occasionally list
anatomy/nudity tags as outfit or pose. Every consumer must use this module so the
sets cannot drift; `tests/test_tag_roles.py` asserts the contract.
"""
ROLE_OVERRIDES_VERSION = "v1"

BODY_STATE_TAGS = frozenset({
    "nude", "completely_nude", "topless", "bottomless", "nipples",
    "pussy", "pubic_hair", "pussy_juice", "pussy_juice_drip",
    "pussy_juice_trail", "pussy_juice_stain", "pussy_juice_puddle",
    "wet", "afterglow",
})

def role_for(name, role):
    """Move body-state tags out of outfit/pose/interaction roles."""
    if role in ("outfit", "pose", "interaction") and name in BODY_STATE_TAGS:
        return "body_state"
    return role
