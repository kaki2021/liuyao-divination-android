"""Narrow compatibility for model JSON, without inventing interpretive evidence.

Normalisation is NOT validation. Callers must retain the original response for
an audit and pass the returned copy to ``validate_output``. No rule, fact, claim,
or forecast direction is inferred or repaired here.
"""
from __future__ import annotations

import copy
import json
import math
import re


MAX_JSON_CHARACTERS = 500000
_BINDING_FIELDS = ("analysis_run_id", "input_snapshot_id")
_OPTIONAL_ARRAYS = {
    "intent": ("independent_questions", "clarifying_questions"),
    "selection": ("route_requests", "unresolved", "clarifying_questions"),
    "interpretation": ("advice", "clarifying_questions"),
    "report": (),
}


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("non-finite JSON number: " + value)


def _check_finite(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite JSON number")
    if isinstance(value, dict):
        for item in value.values():
            _check_finite(item)
    elif isinstance(value, list):
        for item in value:
            _check_finite(item)


def _json_text(raw: str) -> str:
    if not isinstance(raw, str) or len(raw) > MAX_JSON_CHARACTERS:
        raise ValueError("raw output must be text of at most 500000 characters")
    text = raw.strip()
    # A single transport BOM is harmless; an embedded or repeated BOM is not.
    if text.startswith("\ufeff"):
        text = text[1:].strip()
    # Only a fence enclosing the entire response is accepted. Do not extract a
    # JSON-looking substring from prose or multiple fenced responses.
    match = re.fullmatch(r"```(?:json)?[ \t]*\r?\n([\s\S]*)\r?\n```", text)
    return match.group(1).strip() if match else text


def parse_model_json(raw: str) -> dict:
    """Parse one strict JSON object, with an optional enclosing Markdown fence.

    Duplicate keys, NaN/infinity/overflow, extra prose, adjacent objects, nested
    fences and non-object roots remain errors.
    """
    try:
        parsed = json.loads(_json_text(raw), object_pairs_hook=_unique_pairs,
                            parse_constant=_reject_constant)
        _check_finite(parsed)
        if not isinstance(parsed, dict):
            raise ValueError("model output must be a JSON object")
        return parsed
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid model JSON") from exc


def _add_array(output, field, changes, prefix=""):
    if field not in output:
        output[field] = []
        changes.append(f"{prefix}{field}: added empty optional array")


def _copy_fixed(output, field, value, changes):
    if field not in output or output[field] != value:
        output[field] = copy.deepcopy(value)
        changes.append(f"{field}: copied server-owned value")


def _carry_conclusion_conditions(output, changes):
    """Preserve each referenced claim's original qualifications verbatim."""
    conclusion, claims = output.get("conclusion"), output.get("claims")
    if not isinstance(conclusion, dict) or not isinstance(claims, list):
        return
    refs = conclusion.get("claim_refs")
    if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
        return
    by_id = {}
    for claim in claims:
        if not isinstance(claim, dict) or not isinstance(claim.get("claim_id"), str):
            return
        if claim["claim_id"] in by_id:
            return  # Ambiguous identifiers must be rejected, not guessed.
        by_id[claim["claim_id"]] = claim
    if any(ref not in by_id for ref in refs):
        return
    for target, source in (("key_conditions", "assumptions"), ("limits", "limitations")):
        existing = conclusion.get(target)
        if not isinstance(existing, list) or not all(isinstance(x, str) for x in existing):
            continue
        for ref in refs:
            additions = by_id[ref].get(source)
            if not isinstance(additions, list) or not all(isinstance(x, str) for x in additions):
                continue
            for text in additions:
                if text not in existing:
                    existing.append(text)
                    changes.append(f"conclusion.{target}: retained {ref}.{source} verbatim")


def _deduplicate_refs(value, changes, path="$"):
    """Repeated identical IDs carry no extra evidence; retain their first use."""
    if isinstance(value, dict):
        for key, child in value.items():
            here = path + "." + key
            if (key in ("fact_refs", "rule_refs", "inference_refs", "claim_refs", "advice_refs")
                    and isinstance(child, list) and all(isinstance(x, str) for x in child)):
                unique = list(dict.fromkeys(child))
                if len(unique) != len(child):
                    value[key] = unique
                    changes.append(here + ": removed repeated identical reference IDs")
            else:
                _deduplicate_refs(child, changes, here)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _deduplicate_refs(child, changes, f"{path}[{index}]")


def normalize_stage_output(stage: str, raw: str | dict, server_input: dict) -> tuple[dict, list[str]]:
    """Return a new object with only safe mechanical compatibility corrections.

    Missing binding identifiers may be filled from the server; explicit wrong
    bindings, missing substantive judgments and invalid evidence are untouched
    so the contract validator can reject them. ``raw`` and ``server_input`` are
    never modified.
    """
    if stage not in _OPTIONAL_ARRAYS:
        raise ValueError("unknown stage")
    if isinstance(raw, str):
        output = parse_model_json(raw)
        changes = []
        if _json_text(raw) != raw.strip():
            changes.append("response: removed enclosing Markdown fence or BOM")
    elif isinstance(raw, dict):
        output = copy.deepcopy(raw)
        changes = []
    else:
        raise ValueError("model output must be text or object")

    meta = server_input.get("meta", {})
    if not isinstance(meta, dict):
        meta = {}
    if "binding" not in output:
        output["binding"] = {}
        changes.append("binding: created server-owned identifiers object")
    if isinstance(output["binding"], dict):
        for field in _BINDING_FIELDS:
            if field not in output["binding"] and field in meta:
                output["binding"][field] = copy.deepcopy(meta[field])
                changes.append(f"binding.{field}: copied server-owned identifier")

    for field in _OPTIONAL_ARRAYS[stage]:
        _add_array(output, field, changes)
    if stage == "selection" and isinstance(output.get("candidates"), list):
        for index, candidate in enumerate(output["candidates"]):
            if isinstance(candidate, dict):
                _add_array(candidate, "assumptions", changes, f"candidates[{index}].")
        # The model has already identified a sole primary candidate. Completing
        # its omitted/null reference is mechanical; never choose among several
        # primaries, promote a supporting candidate, or replace a wrong ID.
        primary = [c for c in output["candidates"]
                   if isinstance(c, dict) and c.get("purpose") == "primary"]
        if (output.get("status") == "ready" and output.get("selected_primary_id") is None
                and len(primary) == 1 and isinstance(primary[0].get("candidate_id"), str)):
            output["selected_primary_id"] = primary[0]["candidate_id"]
            changes.append("selected_primary_id: referenced the model's sole declared primary candidate")

    if stage == "interpretation":
        advice = output.get("advice")
        if isinstance(advice, list):
            for index, item in enumerate(advice):
                if isinstance(item, dict) and type(item.get("requires_review")) is bool:
                    del item["requires_review"]
                    changes.append(f"advice[{index}].requires_review: removed redundant metadata; all advice remains for review")
        claims = output.get("claims")
        if isinstance(claims, list):
            for index, claim in enumerate(claims):
                if isinstance(claim, dict) and claim.get("kind") == "ai_hypothesis" and claim.get("requires_review") is not True:
                    claim["requires_review"] = True
                    changes.append(f"claims[{index}].requires_review: AI hypothesis requires review")
            if any(isinstance(c, dict) and c.get("requires_review") is True for c in claims) and output.get("status") != "needs_review":
                output["status"] = "needs_review"
                changes.append("status: reflected claim review requirement")
        _carry_conclusion_conditions(output, changes)
    elif stage == "report":
        if "question" in server_input:
            _copy_fixed(output, "question_restated", server_input["question"], changes)
        plan = server_input.get("accepted_interpretation")
        if isinstance(plan, dict):
            for field in ("conclusion", "uncertainties", "clarifying_questions"):
                if field in plan:
                    _copy_fixed(output, field, plan[field], changes)
    _deduplicate_refs(output, changes)
    return output, changes
