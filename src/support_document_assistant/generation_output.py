"""Strict structural validation, exact passage resolution and explicit safe failures."""
import json
from copy import deepcopy
from .assets import json_bytes, sha256


def safe_failure(code, detail):
    return {"status": "insufficient_evidence",
            "answer": f"No validated answer is available ({code}). {detail}",
            "citations": [], "validation": {"valid": False, "failure_code": code,
                                            "detail": detail, "semantic_support": "pending_human_review"}}


def validate_output(raw, context, config, *, reached_cap_without_eos=False):
    def reject(code, detail):
        return safe_failure(code, detail)
    if reached_cap_without_eos:
        return reject("output_limit", "Generation reached the fixed token cap without EOS; output was not repaired.")
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    def constant(value):
        raise ValueError("Non-finite JSON value")
    try:
        parsed = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, TypeError, RecursionError):
        return reject("malformed_output", "Expected one strict JSON object; raw output is preserved.")
    if not isinstance(parsed, dict) or set(parsed) != {"status", "answer", "citations"}:
        return reject("output_schema", "Expected exactly status, answer and citations.")
    if parsed["status"] not in ("answered", "insufficient_evidence"):
        return reject("output_status", "Unknown answer status.")
    answer, citations = parsed["answer"], parsed["citations"]
    if (not isinstance(answer, str) or not answer.strip() or len(answer) > config["max_answer_characters"]
            or any((ord(c) < 32 and c not in "\n\r\t") or 0xD800 <= ord(c) <= 0xDFFF for c in answer)):
        return reject("output_answer", "The answer is empty, too long or contains invalid characters.")
    if (not isinstance(citations, list) or len(citations) > config["max_citations"]
            or any(not isinstance(c, str) for c in citations) or len(set(citations)) != len(citations)):
        return reject("output_citations", "Citations must be a bounded list of distinct passage IDs.")
    supplied = {p["passage_id"]: p for u in context["selected_units"] for p in u["passages"]}
    if any(c not in supplied or supplied[c]["eligible_for_citation"] is not True for c in citations):
        return reject("invalid_citation", "A cited passage was absent or ineligible; no citation was repaired.")
    if parsed["status"] == "answered" and not citations:
        return reject("missing_citation", "An answered response requires an eligible supplied citation.")
    return {"status": parsed["status"], "answer": answer,
            "citations": [deepcopy(supplied[c]) for c in citations],
            "validation": {"valid": True, "failure_code": None, "detail": None,
                           "semantic_support": "pending_human_review"}}


def identify_response(response, config, corpus_id, context):
    return {**response, "identifiers": {"candidate_id": config["candidate_id"],
        "corpus_build_id": corpus_id, "model_id": config["model_id"],
        "model_revision": config["model_revision"], "prompt_id": config["prompt_id"],
        "prompt_sha256": config["frozen_runtime_files"]["config/generation-prompt.txt"],
        "configuration_sha256": sha256(json_bytes(config)),
        "supplied_context_sha256": sha256(json_bytes(context["selected_units"])),
        "formatted_prompt_sha256": context["formatted_prompt_sha256"]},
        "scope": "Python 3.13.0 documentation only", "limitations": config["limitations"],
        "omitted_unit_count": len(context["omitted_units"])}
