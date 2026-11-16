"""Source-exact evidence units and deterministic whole-parent packing; offline."""
from copy import deepcopy
import json
from .assets import sha256


def parent_unit(hit, sources):
    parent = hit.chunk
    raw = sources[parent["source_id"]]["text"]
    if (parent.get("eligible_for_answer_support") is not True or
            sha256(raw.encode()) != parent["source_sha256"]):
        raise ValueError("Parent source is ineligible or changed")
    pieces, passages = [], []
    for ordinal, segment in enumerate(parent["segments"], 1):
        a, b = segment["source_char_range"]
        x, y = segment["chunk_char_range"]
        text = raw[a:b]
        if not 0 <= a < b <= len(raw) or text != parent["text"][x:y]:
            raise ValueError("Parent passage mapping mismatch")
        pieces.append(text)
        passages.append({"passage_id": f"E{hit.rank}-S{ordinal}", "eligible_for_citation": True,
            "text": text, "text_sha256": sha256(text.encode()), "origin": "approved official corpus",
            "provenance": {k: deepcopy(parent[k]) for k in
                ("source_id", "source_path", "product_version", "commit", "immutable_url", "source_sha256")},
            "source_lines": segment["source_lines"], "source_char_range": [a, b],
            "parent_chunk_id": parent["chunk_id"], "parent_char_range": [x, y]})
    if "\n\n".join(pieces) != parent["text"] or sha256(parent["text"].encode()) != parent["text_sha256"]:
        raise ValueError("Full parent reconstruction mismatch")
    return {"unit_id": parent["chunk_id"], "retrieval_rank": hit.rank, "retrieval_score": hit.score,
            "section_titles": deepcopy(parent["section_titles"]), "passages": passages,
            "original_parent_text_sha256": parent["text_sha256"]}


def source_unit(source_id, first, last, sources, ordinal):
    source = sources[source_id]
    raw = source["text"]
    offsets = [0]
    for line in raw.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    if not 1 <= first <= last < len(offsets):
        raise ValueError("Control source lines outside corpus")
    a, b = offsets[first - 1], offsets[last]
    text = raw[a:b]
    return {"unit_id": f"gold-{ordinal}", "retrieval_rank": None, "retrieval_score": None,
            "section_titles": [], "passages": [{
                "passage_id": f"G{ordinal}-S1", "eligible_for_citation": True,
                "text": text, "text_sha256": sha256(text.encode()), "origin": "approved gold-evidence control",
                "provenance": {k: deepcopy(source[k]) for k in
                    ("source_id", "source_path", "product_version", "commit", "immutable_url", "source_sha256")},
                "source_lines": [first, last], "source_char_range": [a, b],
                "parent_chunk_id": None, "parent_char_range": None}]}


def synthetic_unit(fixture):
    text = fixture["text"]
    return {"unit_id": fixture["fixture_id"], "retrieval_rank": None, "retrieval_score": None,
            "section_titles": [], "passages": [{"passage_id": "X1-S1",
                "eligible_for_citation": False, "text": text, "text_sha256": sha256(text.encode()),
                "origin": fixture["origin"], "provenance": None, "source_lines": None,
                "source_char_range": None, "parent_chunk_id": None, "parent_char_range": None}]}


def messages_for(question, selected, system_prompt):
    evidence = []
    for unit in selected:
        passages = []
        for passage in unit["passages"]:
            provenance = passage["provenance"]
            passages.append({"passage_id": passage["passage_id"],
                "eligible_for_citation": passage["eligible_for_citation"],
                "origin": passage["origin"], "source_id": provenance["source_id"] if provenance else None,
                "version": provenance["product_version"] if provenance else None,
                "lines": passage["source_lines"], "text": passage["text"]})
        evidence.append({"unit_id": unit["unit_id"], "sections": unit["section_titles"], "passages": passages})
    envelope = {"question": question, "scope": "Python 3.13.0 documentation only", "evidence": evidence}
    encoded = json.dumps(envelope, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    encoded = encoded.replace("<", "\\u003c").replace(">", "\\u003e")
    return [{"role": "system", "content": system_prompt}, {"role": "user", "content": encoded}]


def pack_context(question, units, tokenizer, config, system_prompt):
    ids = [p["passage_id"] for u in units for p in u["passages"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate supplied passage ID")
    for unit in units:
        if not unit["passages"]:
            raise ValueError("Empty evidence unit")
        for passage in unit["passages"]:
            if (not isinstance(passage["text"], str) or
                    sha256(passage["text"].encode()) != passage["text_sha256"]):
                raise ValueError("Supplied passage text identity changed")
    cap, reserve = config["context_total_tokens"], config["output_token_cap"]
    def formatted(selected):
        messages = messages_for(question, selected, system_prompt)
        text, token_ids = tokenizer.format(messages)
        return messages, text, token_ids
    selected, omitted = [], []
    messages, text, token_ids = formatted([])
    base_overflow = len(token_ids) + reserve > cap
    if base_overflow:
        omitted = [{"unit": deepcopy(u), "reason": "base_prompt_overflow"} for u in units]
    else:
        for unit in units:
            candidate_messages, candidate_text, candidate_ids = formatted(selected + [unit])
            if len(candidate_ids) + reserve <= cap:
                selected.append(deepcopy(unit))
                messages, text, token_ids = candidate_messages, candidate_text, candidate_ids
            else:
                omitted.append({"unit": deepcopy(unit), "reason": "whole_unit_exceeds_context_budget",
                                "attempt_prompt_tokens": len(candidate_ids),
                                "attempt_total_with_reserve": len(candidate_ids) + reserve})
    return {"status": "overflow" if base_overflow else "packed", "selected_units": selected,
            "omitted_units": omitted, "messages": messages, "formatted_prompt": text,
            "input_token_ids": token_ids, "prompt_tokens": len(token_ids), "reserved_output_tokens": reserve,
            "total_token_budget": cap, "total_with_reserve": len(token_ids) + reserve,
            "input_ids_sha256": sha256(json.dumps(token_ids, separators=(",", ":")).encode()),
            "formatted_prompt_sha256": sha256(text.encode())}
