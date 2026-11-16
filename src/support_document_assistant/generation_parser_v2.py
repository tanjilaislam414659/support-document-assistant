"""Diagnostic-only strict JSON / single outer-json-fence parser. No model imports."""
import json
import math
from .assets import sha256
from .generation_output import validate_output as validate_original

PARSER_ID = "strict-json-or-json-fence-v2"
JSON_WHITESPACE = " \t\r\n"


class DuplicateKey(ValueError):
    pass


class NonFinite(ValueError):
    pass


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise DuplicateKey(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value):
    raise NonFinite(f"Non-finite JSON value: {value}")


def _float(value):
    number = float(value)
    if not math.isfinite(number):
        raise NonFinite("JSON number overflows a finite float")
    return number


def _body(raw):
    if not isinstance(raw, str):
        return None, "unavailable", "Output must be text"
    framed = raw.strip(JSON_WHITESPACE)
    if framed.startswith("~~~") or framed.startswith("```") or framed.endswith("```"):
        opening = next((s for s in ("```json\r\n", "```json\n") if framed.startswith(s)), None)
        last_newline = framed.rfind("\n")
        if (opening is None or last_newline < len(opening) or
                framed[last_newline + 1:] != "```"):
            return None, "unsupported_envelope", "Expected one complete outer json fence with standalone delimiters"
        body = framed[len(opening):last_newline]
        if body.endswith("\r"):
            body = body[:-1]  # CR belongs to the closing delimiter's CRLF.
        return body, "outer_json_fence", None
    return raw, "direct", None


def revalidate(raw, context, config, *, reached_cap_without_eos=False):
    body, framing, envelope_error = _body(raw)
    invalid_text = False
    try:
        raw_digest = sha256(raw.encode()) if isinstance(raw, str) else None
    except UnicodeEncodeError:
        raw_digest, invalid_text = None, True
    result = {"parser_id": PARSER_ID, "raw_sha256": raw_digest,
        "framing": framing, "body_sha256": sha256(body.encode()) if body is not None and not invalid_text else None,
        "strict_json": {"accepted": False, "error": None}, "parsed_object": None,
        "model_declared_status": None, "outcome": "generation_validation_error",
        "validation": {"accepted": False, "error_code": None, "detail": None},
        "response": None, "semantic_support": "pending_human_review"}
    def reject(code, detail):
        result["validation"].update(error_code=code, detail=detail)
        return result
    if invalid_text:
        return reject("invalid_output_text", "Output contains an unpaired Unicode surrogate")
    if reached_cap_without_eos:
        return reject("output_limit", "Original fixed output cap reached without EOS; no repair")
    if envelope_error:
        return reject("unsupported_envelope", envelope_error)
    try:
        parsed = json.loads(body, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float)
    except json.JSONDecodeError as exc:
        result["strict_json"]["error"] = {"kind": "json_syntax", "message": exc.msg,
            "line": exc.lineno, "column": exc.colno, "character_position": exc.pos}
        return reject("invalid_json_syntax", exc.msg)
    except (DuplicateKey, NonFinite, ValueError, TypeError, RecursionError) as exc:
        kind = "duplicate_key" if isinstance(exc, DuplicateKey) else "non_finite" if isinstance(exc, NonFinite) else "json_value_error"
        result["strict_json"]["error"] = {"kind": kind, "message": str(exc)}
        return reject(kind, str(exc))
    result["strict_json"]["accepted"] = True
    result["strict_json"]["value_type"] = type(parsed).__name__
    if isinstance(parsed, dict):
        result["parsed_object"] = parsed
        result["model_declared_status"] = parsed.get("status")
    checked = validate_original(body, context, config, reached_cap_without_eos=False)
    if not checked["validation"]["valid"]:
        return reject(checked["validation"]["failure_code"], checked["validation"]["detail"])
    result["validation"].update(accepted=True)
    result["response"] = checked
    result["outcome"] = "validated_answer" if checked["status"] == "answered" else "validated_insufficient_evidence"
    return result


def citation_diagnostics(parsed, context):
    """Resolution facts only; never a claim-support judgment."""
    if not isinstance(parsed, dict) or not isinstance(parsed.get("citations"), list):
        return []
    supplied = {p["passage_id"]: p for u in context["selected_units"] for p in u["passages"]}
    diagnostics = []
    for identifier in parsed["citations"]:
        if not isinstance(identifier, str):
            diagnostics.append({"passage_id": identifier, "resolution": "invalid_id_type"})
        elif identifier not in supplied:
            diagnostics.append({"passage_id": identifier, "resolution": "not_supplied"})
        elif supplied[identifier]["eligible_for_citation"] is not True:
            diagnostics.append({"passage_id": identifier, "resolution": "ineligible",
                                "origin": supplied[identifier]["origin"]})
        else:
            diagnostics.append({"passage_id": identifier, "resolution": "eligible_supplied",
                                "source_lines": supplied[identifier]["source_lines"],
                                "provenance": supplied[identifier]["provenance"]})
    return diagnostics


def classify(original_valid, original_code, replay, raw):
    formatting, contract = [], []
    if replay["framing"] == "outer_json_fence":
        formatting.append("outer_markdown_json_fence")
    code = replay["validation"]["error_code"]
    if code in ("invalid_json_syntax", "duplicate_key", "non_finite", "json_value_error"):
        if (replay["framing"] == "direct" and isinstance(raw, str)
                and not raw.lstrip(JSON_WHITESPACE).startswith(("{", "[", '"'))):
            formatting.append("non_json_prose_or_literal")
        formatting.append(code)
    elif code == "unsupported_envelope":
        formatting.append(code)
    elif code is not None:
        contract.append({"output_schema": "schema_error", "output_answer": "answer_schema_error",
            "output_citations": "citation_schema_error", "output_status": "invalid_status_value",
            "missing_citation": "missing_required_citation", "invalid_citation": "invalid_citation",
            "output_limit": "unfinished_output_token_cap"}.get(code, code))
    return {"original_accepted": original_valid, "original_error_code": original_code,
        "formatting_issues": formatting, "contract_issues": contract,
        "outer_fence_only_original_failure": bool(not original_valid and
            replay["framing"] == "outer_json_fence" and replay["validation"]["accepted"]),
        "semantic_correctness": "not_automatically_classified"}
