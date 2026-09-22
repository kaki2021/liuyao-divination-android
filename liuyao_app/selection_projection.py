"""Derive deterministic kinship after the model has selected a function.

The model owns the contextual choice of relation or subject reference.  The
server owns the fixed relation-to-kinship mapping.  Only omitted derived fields
are populated: explicitly contradictory model values remain errors so an audit
never disguises a rejected functional choice as a successful one.
"""
from __future__ import annotations

from copy import deepcopy

from validate_ai_contract import ContractError


RELATION_TO_KINSHIP = {
    "generates_me": "parents",
    "same_as_me": "siblings",
    "generated_by_me": "offspring",
    "controlled_by_me": "wealth",
    "controls_me": "official_ghost",
}


def project_selection(output: dict) -> tuple[dict, list[str]]:
    """Return a detached output and audit notes for server-derived fields.

Malformed surrounding fields are left for the ordinary contract validator.
No function, subject, primary candidate, rule or evidence is chosen here.
"""
    projected = deepcopy(output)
    changes = []
    if not isinstance(projected, dict) or not isinstance(projected.get("candidates"), list):
        return projected, changes
    for index, candidate in enumerate(projected["candidates"]):
        if not isinstance(candidate, dict):
            continue
        path = f"$.candidates[{index}]"
        reference = candidate.get("subject_reference")
        relation = candidate.get("relation")
        if reference in ("shi", "shi_body"):
            # A missing relation must still fail the required-field check;
            # only a declared null relation permits the null kinship projection.
            if "relation" not in candidate:
                continue
            if relation is not None:
                raise ContractError(path + ".relation: subject reference is distinct from functional kinship")
            expected = None
        elif reference is None and isinstance(relation, str) and relation in RELATION_TO_KINSHIP:
            expected = RELATION_TO_KINSHIP[relation]
        else:
            continue
        if "six_relative" in candidate:
            if candidate["six_relative"] != expected:
                raise ContractError(path + ".six_relative: conflicts with server-derived functional kinship")
        else:
            candidate["six_relative"] = expected
            changes.append(path + ".six_relative: derived by server from declared relation or subject reference")
    return projected, changes
