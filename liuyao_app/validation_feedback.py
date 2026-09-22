"""Bounded, read-only feedback for repairing a model response in one pass.

This collector is diagnostic only. A response still has to pass validate_output
and the pipeline's semantic guards before it can become an accepted report.
"""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "software_prep"))
from validate_ai_contract import (  # noqa: E402
    ContractError, _conclusion, _core_rules, _quote_check, _refs,
    canonical, check_schema, validate_output,
)
from liuyao_app.claim_rule_scope import claim_rule_errors

MAX_ERRORS = 40


def collect_application_errors(stage: str, output: dict, server_input: dict) -> list[dict]:
    """Collect the application's stricter per-claim gates independently.

    Keep these separate from the shared research contract: the application has
    no engine-verified outcome inferences, and a model interpretation needs an
    actual interpretation rule, not just a naming or display definition.
    """
    if stage != "interpretation" or not isinstance(output, dict):
        return []
    claims = output.get("claims", [])
    if not isinstance(claims, list):
        return []
    errors = claim_rule_errors(output, server_input)
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            continue
        path = f"$.claims[{index}]"
        if claim.get("kind") == "engine_supported" and claim.get("inference_refs"):
            # Empty references already receive the richer shared-contract
            # ENGINE_INFERENCE_REQUIRED issue; avoid duplicating that error.
            errors.append({
                "code": "APPLICATION_ENGINE_CLAIM_UNAVAILABLE", "path": path + ".kind",
                "message": "this application has no verified outcome inferences. "
                "Keep computed chart facts as fact citations and remove redundant factual claims. "
                "A genuinely supported conditional interpretation must be rewritten with applicable "
                "rules, evidence, assumptions and limitations; merely renaming its kind is not a repair.",
            })
        if len(errors) >= MAX_ERRORS:
            break
    return errors


def collect_output_errors(stage: str, output: dict, server_input: dict, pack: dict) -> list[dict]:
    """Return distinct {code, message, path} issues without changing any input.

    Paths refer to the original output. Structure and each independent claim or
    advice item are checked even if a different item has already failed. Strict
    validation is also run at the end to retain coverage of contract rules that
    are not independently expanded here. This is not a natural-language proof.
    """
    errors: list[dict] = []
    seen: set[tuple] = set()

    def add(code, message, path="$"):
        key = (code, path, str(message))
        if key not in seen and len(errors) < MAX_ERRORS:
            seen.add(key)
            errors.append({"code": code, "message": str(message)[:2000], "path": path})

    def checked(fn, code, path):
        try:
            fn()
        except ContractError as exc:
            add(code, str(exc), path)
        except (KeyError, TypeError, IndexError, AttributeError):
            # A malformed item already has a structural error; do not abort
            # independent checks of the other items.
            pass

    if stage not in pack.get("stages", {}):
        add("UNKNOWN_STAGE", "unknown stage")
        return errors
    schema = pack["stages"][stage]["output_schema"]

    def schema_errors(value, node, path, depth=0):
        if len(errors) >= MAX_ERRORS:
            return
        if depth > 100:
            add("SCHEMA_DEPTH", "output nesting exceeds diagnostic limit", path)
            return
        if "$ref" in node:
            ref = node["$ref"]
            if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
                add("SCHEMA_REFERENCE", "external schema ref forbidden", path)
                return
            target = schema.get("$defs", {}).get(ref.split("/")[-1])
            if target is None:
                add("SCHEMA_REFERENCE", "schema definition not found", path)
                return
            return schema_errors(value, target, path, depth + 1)
        # Reuse the contract's type/scalar/array constraint implementation,
        # while traversing fields separately instead of failing at item one.
        if "type" in node:
            before = len(errors)
            checked(lambda: check_schema(value, {"type": node["type"]}, path=path),
                    "SCHEMA_TYPE", path)
            if len(errors) != before:
                return
        local = {key: val for key, val in node.items()
                 if key not in ("properties", "required", "additionalProperties", "items", "$defs")}
        checked(lambda: check_schema(value, local, path=path), "SCHEMA_CONSTRAINT", path)
        if isinstance(value, dict):
            props = node.get("properties", {})
            for key in node.get("required", []):
                if key not in value:
                    add("SCHEMA_REQUIRED", "required field is missing", path + "." + key)
            if node.get("additionalProperties") is False:
                for key in value:
                    if key not in props:
                        add("SCHEMA_EXTRA_FIELD", "field is not allowed by this output schema", path + "." + key)
            for key, child in value.items():
                if key in props:
                    schema_errors(child, props[key], path + "." + key, depth + 1)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                schema_errors(child, node.get("items", {}), f"{path}[{index}]", depth + 1)
                if len(errors) >= MAX_ERRORS:
                    break

    schema_errors(output, schema, "$")
    if not isinstance(output, dict):
        return errors

    def objects(value):
        return value if isinstance(value, list) else []

    def table(items, key, path=None):
        result = {}
        for index, item in enumerate(objects(items)):
            if not isinstance(item, dict) or not isinstance(item.get(key), str):
                continue
            identifier = item[key]
            if identifier in result:
                if path is not None:
                    add("DUPLICATE_IDENTIFIER", "duplicate identifier: " + identifier,
                        f"{path}[{index}].{key}")
            else:
                result[identifier] = item
        return result

    def references(refs, available, label, path):
        if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
            return []
        checked(lambda: _refs(refs, available, label), "UNKNOWN_REFERENCE", path)
        return [ref for ref in refs if ref in available]

    def core_rules(refs, rules, path):
        valid = references(refs, rules, "rule", path)
        for rid in valid:
            checked(lambda rid=rid: _core_rules([rid], rules), "RULE_NOT_APPROVED_CORE", path)
        return valid

    def quote_checks(quotes, evidence, path):
        for index, quote in enumerate(objects(quotes)):
            if isinstance(quote, dict):
                checked(lambda quote=quote: _quote_check([quote], evidence),
                        "USER_QUOTE_MISMATCH", f"{path}[{index}]")

    expected_binding = {key: server_input.get("meta", {}).get(key)
                        for key in ("analysis_run_id", "input_snapshot_id")}
    if isinstance(output.get("binding"), dict) and output["binding"] != expected_binding:
        add("BINDING_MISMATCH", "cross-run or cross-snapshot binding", "$.binding")

    rules = table(server_input.get("rules"), "rule_id")
    facts = table(server_input.get("facts"), "fact_id")
    inferences = table(server_input.get("inferences"), "inference_id")
    gaps = table(server_input.get("unresolved_gaps"), "gap_id")

    if stage in ("intent", "selection"):
        evidence = table(server_input.get("user_evidence"), "evidence_id")
        candidates = table(output.get("candidates"), "candidate_id", "$.candidates")
        for index, candidate in enumerate(objects(output.get("candidates"))):
            if not isinstance(candidate, dict):
                continue
            path = f"$.candidates[{index}]"
            quote_checks(candidate.get("evidence_quotes"), evidence, path + ".evidence_quotes")
            if stage == "selection":
                valid_rules = core_rules(candidate.get("rule_refs"), rules, path + ".rule_refs")
                if any(rules[r].get("usage") != "selection" for r in valid_rules):
                    add("RULE_USAGE_MISMATCH", "functional candidates require selection rules", path + ".rule_refs")
        selected_key = "selected_candidate_id" if stage == "intent" else "selected_primary_id"
        if output.get("status") == "ready":
            selected = output.get(selected_key)
            if not isinstance(selected, str) or selected not in candidates:
                add("PRIMARY_CANDIDATE_MISSING", "ready output must select an existing candidate", "$." + selected_key)
            elif stage == "selection" and candidates[selected].get("purpose") != "primary":
                add("PRIMARY_CANDIDATE_ROLE", "selected candidate must have primary purpose", "$." + selected_key)

    if stage in ("interpretation", "report"):
        uncertainties = table(output.get("uncertainties"), "gap_id", "$.uncertainties")
        for gap_id in gaps:
            if gap_id not in uncertainties:
                add("UNRESOLVED_GAP_OMITTED", "unresolved server gap was omitted: " + gap_id, "$.uncertainties")
        for index, uncertainty in enumerate(objects(output.get("uncertainties"))):
            if not isinstance(uncertainty, dict):
                continue
            gap_id = uncertainty.get("gap_id")
            if isinstance(gap_id, str) and gap_id not in gaps and not gap_id.startswith("AI_GAP_"):
                add("NEW_GAP_PREFIX", "new gap needs AI_GAP_ prefix", f"$.uncertainties[{index}].gap_id")

    if stage == "interpretation":
        claims = table(output.get("claims"), "claim_id", "$.claims")
        table(output.get("advice"), "advice_id", "$.advice")
        for index, claim in enumerate(objects(output.get("claims"))):
            if not isinstance(claim, dict):
                continue
            path = f"$.claims[{index}]"
            valid_facts = references(claim.get("fact_refs"), facts, "claim facts", path + ".fact_refs")
            valid_inferences = references(claim.get("inference_refs"), inferences,
                                          "claim inferences", path + ".inference_refs")
            kind = claim.get("kind")
            if kind in ("engine_supported", "ai_hypothesis"):
                core_rules(claim.get("rule_refs"), rules, path + ".rule_refs")
            if kind == "engine_supported":
                if not claim.get("inference_refs"):
                    add("ENGINE_INFERENCE_REQUIRED",
                        "engine_supported requires a supplied verified inference ID; none was cited. "
                        "Keep computed chart facts as fact citations and remove redundant factual claims. "
                        "If applicable interpretation rules genuinely support a conditional interpretation, "
                        "rewrite it with evidence, assumptions, limitations and review. "
                        "Do not merely rename its kind or invent inference IDs.", path + ".inference_refs")
                if claim.get("requires_review") or claim.get("assumptions"):
                    add("ENGINE_NEW_ASSUMPTIONS", "engine claim cannot add assumptions or require review", path)
                for iid in valid_inferences:
                    inf = inferences[iid]
                    if inf.get("status") != "verified":
                        add("ENGINE_INFERENCE_UNVERIFIED", "inference is not verified: " + iid, path + ".inference_refs")
                    if inf.get("conclusion") != claim.get("proposition") or inf.get("direction") != claim.get("direction"):
                        add("ENGINE_CONCLUSION_MISMATCH", "inference does not support exact proposition and direction: " + iid, path + ".proposition")
                    if (not set(objects(inf.get("premise_fact_ids"))).issubset(valid_facts)
                            or inf.get("rule_id") not in objects(claim.get("rule_refs"))):
                        add("ENGINE_PREMISE_OMITTED", "claim omitted inference premises or rule: " + iid, path)
                if any(gap.get("blocking") and claim.get("dimension") in objects(gap.get("affects"))
                       for gap in gaps.values()):
                    add("BLOCKING_GAP", "blocking server gap prevents an engine-supported claim in this dimension", path + ".dimension")
            elif kind == "ai_hypothesis":
                if not claim.get("rule_refs"):
                    add("HYPOTHESIS_RULE_REQUIRED", "AI hypothesis requires an applicable approved core rule", path + ".rule_refs")
                if claim.get("requires_review") is not True:
                    add("HYPOTHESIS_REVIEW_REQUIRED", "AI hypothesis must keep requires_review=true", path + ".requires_review")
                if not claim.get("limitations"):
                    add("HYPOTHESIS_LIMIT_REQUIRED", "AI hypothesis must state its substantive limitations", path + ".limitations")
                if claim.get("inference_refs"):
                    add("HYPOTHESIS_ENGINE_REFS", "AI hypothesis uses facts/rules, not engine inference refs", path + ".inference_refs")
            elif kind == "real_world_context":
                if claim.get("rule_refs") or claim.get("inference_refs") or claim.get("direction") != "neutral":
                    add("CONTEXT_PREDICTION", "real-world context requires neutral direction and no rule/inference refs", path)
                if any(facts[f].get("kind") != "context" for f in valid_facts):
                    add("CONTEXT_FACT_KIND", "real-world context must cite observed context facts", path + ".fact_refs")
                proposition = claim.get("proposition")
                if isinstance(proposition, dict) and not any(
                        all(key in proposition and facts[f].get(key) == proposition[key]
                            for key in ("subject", "predicate", "value")) for f in valid_facts):
                    add("CONTEXT_ATOM_MISMATCH", "context proposition must exactly match an observed context fact; "
                        "missing algorithms or chart interpretations are not user facts", path + ".proposition")

        for index, advice in enumerate(objects(output.get("advice"))):
            if not isinstance(advice, dict):
                continue
            path = f"$.advice[{index}]"
            valid_claims = references(advice.get("claim_refs"), claims, "advice claims", path + ".claim_refs")
            valid_facts = references(advice.get("fact_refs"), facts, "advice facts", path + ".fact_refs")
            if not advice.get("claim_refs") and not advice.get("fact_refs"):
                add("ADVICE_BASIS_REQUIRED", "advice needs a factual or interpretive basis", path)
            if advice.get("basis") == "system_interpretation" and not advice.get("claim_refs"):
                add("ADVICE_CLAIM_REQUIRED", "system advice needs claim refs", path + ".claim_refs")
            if advice.get("basis") == "real_world_information":
                if not advice.get("fact_refs") or any(facts[f].get("kind") != "context" for f in valid_facts):
                    add("ADVICE_CONTEXT_REQUIRED", "real-world advice needs observed context facts", path + ".fact_refs")
                if any(claims[c].get("kind") != "real_world_context" for c in valid_claims):
                    add("ADVICE_CONTEXT_CLAIM_KIND", "real-world advice cannot disguise chart speculation", path + ".claim_refs")
        if any(claim.get("requires_review") for claim in claims.values()) and output.get("status") != "needs_review":
            add("REVIEW_STATUS", "review-required claim must be reflected in needs_review status", "$.status")
        if output.get("status") == "supported" and (gaps or output.get("uncertainties") or not claims):
            add("SUPPORTED_STATUS_GAP", "supported status conflicts with unresolved gaps or empty claims", "$.status")
        checked(lambda: _conclusion(output, claims, rules), "CONCLUSION_CONTRACT", "$.conclusion")

    if stage == "report":
        plan = server_input.get("accepted_interpretation", {})
        claims = table(plan.get("claims"), "claim_id")
        advice = table(plan.get("advice"), "advice_id")
        for key in ("uncertainties", "clarifying_questions", "conclusion"):
            if key in output and output[key] != plan.get(key):
                add("ACCEPTED_FIELD_CHANGED", "report must preserve the accepted " + key, "$." + key)
        if output.get("question_restated") != server_input.get("question"):
            add("QUESTION_CHANGED", "report changed the current question", "$.question_restated")
        for index, part in enumerate(objects(output.get("parts"))):
            if not isinstance(part, dict):
                continue
            path = f"$.parts[{index}]"
            cited = references(part.get("claim_refs"), claims, "report claims", path + ".claim_refs")
            references(part.get("advice_refs"), advice, "report advice", path + ".advice_refs")
            if any(claims[c].get("dimension") != part.get("dimension") for c in cited):
                add("REPORT_DIMENSION", "report claim belongs to a different dimension", path + ".claim_refs")
            if part.get("advice_refs") and part.get("dimension") != "adjustment":
                add("REPORT_ADVICE_DIMENSION", "advice only belongs in adjustment dimension", path + ".advice_refs")
            if part.get("qualification") != "undetermined" and not part.get("claim_refs") and not part.get("advice_refs"):
                add("REPORT_UNSUPPORTED", "section without claim/advice refs cannot be presented as resolved", path)
            if part.get("qualification") == "supported" and any(claims[c].get("kind") == "ai_hypothesis" for c in cited):
                add("REPORT_HYPOTHESIS_PROMOTED", "conditional hypothesis cannot become a supported report", path + ".qualification")
        checked(lambda: _conclusion(output, claims), "CONCLUSION_CONTRACT", "$.conclusion")

    # Preserve all strict gates. This result is only additional repair feedback,
    # never an alternative admission check or an automatic transformation.
    try:
        validate_output(stage, canonical(output), server_input, pack)
    except ContractError as exc:
        message = str(exc)
        if not any(error["message"] == message for error in errors):
            add("STRICT_CONTRACT", message)
    except (KeyError, TypeError, IndexError, AttributeError, ValueError, RecursionError):
        if not errors:
            add("CONTRACT_STRUCTURE", "malformed contract data prevented full validation")
    return errors
