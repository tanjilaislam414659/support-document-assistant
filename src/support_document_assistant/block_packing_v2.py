"""Complete source blocks, compact model view and fixed rank-aware allocation."""
from copy import deepcopy
import json
from .assets import sha256
from .retrieval import query_tokens


def ordered_units(units):
    if not isinstance(units, list):
        raise ValueError("Evidence units must be a list")
    ranks = [u["retrieval_rank"] for u in units]
    if any(r is not None for r in ranks):
        if any(type(r) is not int or r < 1 for r in ranks) or len(set(ranks)) != len(ranks):
            raise ValueError("Ordinary parent ranks must be distinct positive integers")
        units = sorted(units, key=lambda u: u["retrieval_rank"])
    unit_ids, passage_ids = set(), set()
    for unit in units:
        if unit["unit_id"] in unit_ids or not unit["passages"]:
            raise ValueError("Duplicate/empty parent unit")
        unit_ids.add(unit["unit_id"])
        for passage in unit["passages"]:
            pid, text = passage["passage_id"], passage["text"]
            if pid in passage_ids or not isinstance(text, str) or not text:
                raise ValueError("Duplicate passage or empty block")
            passage_ids.add(pid)
            if sha256(text.encode()) != passage["text_sha256"]:
                raise ValueError("Block text identity mismatch")
            if type(passage["eligible_for_citation"]) is not bool:
                raise ValueError("Invalid citation eligibility")
            if passage["eligible_for_citation"]:
                a,b = passage["source_char_range"]
                if not passage["provenance"] or not 0 <= a < b or b-a != len(text):
                    raise ValueError("Invalid complete block source mapping")
        if "original_parent_text_sha256" in unit:
            text = "\n\n".join(p["text"] for p in unit["passages"])
            if sha256(text.encode()) != unit["original_parent_text_sha256"]:
                raise ValueError("Input blocks do not reconstruct the complete original parent")
    return units


def selected_groups(units, selected, config):
    groups = []
    for unit in units:
        passages = [deepcopy(p) for p in unit["passages"] if p["passage_id"] in selected]
        if passages:
            groups.append({**deepcopy(unit), "passages": passages,
                "parent_total_blocks": len(unit["passages"]),
                "packing_representation": config["packing"]["identity"]})
    return groups


def model_messages(question, groups, prompt, source_metadata, config):
    evidence = []
    for unit in groups:
        source_id = next((p["provenance"]["source_id"] for p in unit["passages"] if p["provenance"]), None)
        if source_id is None:
            sections, platform = ["Untrusted synthetic note"], "untrusted synthetic content"
        else:
            source = source_metadata[source_id]
            sections = unit["section_titles"][-config["packing"]["model_section_titles"]:] or [source["title"]]
            platform = source["platform_scope"]
        evidence.append({"section": sections, "platform": platform,
            "passages": [[p["passage_id"], p["eligible_for_citation"], p["text"]] for p in unit["passages"]]})
    envelope = json.dumps({"question": question, "evidence": evidence},
                         ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    envelope = envelope.replace("<", "\\u003c").replace(">", "\\u003e")
    return [{"role":"system","content":prompt},{"role":"user","content":envelope}]


def pack_blocks(question, units, tokenizer, config, prompt, source_metadata):
    query_tokens(question)
    units = ordered_units(units)
    reserve, cap = config["output_token_cap"], config["context_total_tokens"]
    if type(reserve) is not int or type(cap) is not int or not 0 < reserve < cap:
        raise ValueError("Invalid fixed token budgets")
    selected, omitted, trace = set(), [], []
    def formatted(chosen):
        groups = selected_groups(units, chosen, config)
        messages = model_messages(question, groups, prompt, source_metadata, config)
        text, ids = tokenizer.format(messages)
        return groups, messages, text, ids
    groups, messages, text, ids = formatted(set())
    base_overflow = len(ids) + reserve > cap
    for round_index in range(max((len(u["passages"]) for u in units), default=0)):
        for parent_index, unit in enumerate(units, 1):
            if round_index >= len(unit["passages"]):
                continue
            passage = unit["passages"][round_index]
            pid = passage["passage_id"]
            info = {"round":round_index+1,"parent_order":parent_index,
                    "parent_retrieval_rank":unit["retrieval_rank"],"block_ordinal":round_index+1,
                    "unit_id":unit["unit_id"],"passage_id":pid}
            if base_overflow:
                reason, candidate_total, standalone_total = "base_prompt_overflow", None, None
            else:
                candidate = formatted(selected | {pid})
                candidate_total = len(candidate[3]) + reserve
                if candidate_total <= cap:
                    selected.add(pid)
                    trace.append({**info,"selected":True,"candidate_total_tokens":candidate_total})
                    continue
                standalone_total = len(formatted({pid})[3]) + reserve
                reason = "block_exceeds_standalone_budget" if standalone_total > cap else "remaining_budget_exhausted"
            omitted.append({**info,"reason":reason,"passage":deepcopy(passage),
                "unit_metadata":{k:deepcopy(v) for k,v in unit.items() if k!="passages"},
                "candidate_total_tokens":candidate_total,"standalone_total_tokens":standalone_total})
            trace.append({**info,"selected":False,"reason":reason,
                          "candidate_total_tokens":candidate_total,"standalone_total_tokens":standalone_total})
    groups, messages, text, ids = formatted(selected)
    result = {"packing_id":config["packing"]["identity"],"status":"overflow" if base_overflow else "packed",
        "input_units":deepcopy(units),"selected_units":groups,"omitted_blocks":omitted,"allocation_trace":trace,
        "messages":messages,"formatted_prompt":text,"formatted_prompt_sha256":sha256(text.encode()),
        "input_token_ids":ids,"input_ids_sha256":sha256(json.dumps(ids,separators=(",",":")).encode()),
        "prompt_tokens":len(ids),"reserved_output_tokens":reserve,"total_with_reserve":len(ids)+reserve,
        "total_token_budget":cap,
        "parent_opportunities":[{"unit_id":u["unit_id"],"attempted_blocks":len(u["passages"]),
            "selected_blocks":sum(p["passage_id"] in selected for p in u["passages"])} for u in units]}
    validate_view(result, config)
    return result


def validate_view(context, config, sources=None):
    inputs = ordered_units(context["input_units"])
    catalogue = {p["passage_id"]:p for u in inputs for p in u["passages"]}
    selected = [p for u in context["selected_units"] for p in u["passages"]]
    omitted = [o["passage"] for o in context["omitted_blocks"]]
    ids = [p["passage_id"] for p in selected+omitted]
    if len(ids)!=len(set(ids)) or set(ids)!=set(catalogue):
        raise ValueError("Every complete block must be selected or omitted exactly once")
    for passage in selected+omitted:
        if passage != catalogue[passage["passage_id"]]:
            raise ValueError("A source block was changed or cut")
        if sources is not None and passage["eligible_for_citation"]:
            a,b=passage["source_char_range"]
            raw=sources[passage["provenance"]["source_id"]]
            if raw[a:b]!=passage["text"] or sha256(raw.encode())!=passage["provenance"]["source_sha256"]:
                raise ValueError("Actual block/source mapping mismatch")
    if (context["prompt_tokens"]!=len(context["input_token_ids"]) or
            context["total_with_reserve"]!=context["prompt_tokens"]+config["output_token_cap"] or
            context["formatted_prompt_sha256"]!=sha256(context["formatted_prompt"].encode())):
        raise ValueError("Formatted prompt counts/identity changed")
    if context["status"]!="overflow" and context["total_with_reserve"]>config["context_total_tokens"]:
        raise ValueError("Complete formatted prompt exceeds the fixed budget")
    return True
