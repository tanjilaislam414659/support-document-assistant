"""Reference structure validation and deterministic human evidence-review rendering."""
from collections import Counter
from datetime import date
import json
import re
from pathlib import Path

from .assets import acquire, save_once
from .ingestion import load_json


def validate_artifacts(root):
    root = Path(root)
    registry = load_json(root / "config/sources.json")
    references = load_json(root / "evaluation/reference_cases.json")
    if references["schema_version"] != 2:
        raise ValueError("Expected variant-specific reference schema v2")
    sources = {s["source_id"]: s for s in registry["sources"]}
    if len(sources) != len(registry["sources"]):
        raise ValueError("Duplicate source IDs")
    issues_path = root / "config/source-exclusions.json"
    issues = load_json(issues_path)["issues"] if issues_path.exists() else []
    claims = {}
    for claim in references["claims"]:
        if claim["claim_id"] in claims:
            raise ValueError("Duplicate claim ID")
        claims[claim["claim_id"]] = claim
        if not claim["fact"] or not claim["alternatives"]:
            raise ValueError("Claims require a fact and OR alternatives")
        for alternative in claim["alternatives"]:
            if not alternative["passages"] or not alternative["support_summary"]:
                raise ValueError("Each alternative needs supporting passages and a summary")
            for passage in alternative["passages"]:
                if passage["source_id"] not in sources:
                    raise ValueError("Evidence references an unknown source")
                a, b = passage["lines"]
                if not 1 <= a <= b:
                    raise ValueError("Invalid evidence location")
                for issue in issues:
                    if issue["source_id"] == passage["source_id"]:
                        x, y = issue["lines"]
                        if max(a, x) <= min(b, y):
                            raise ValueError("Reference support intersects an ineligible passage")
                source = sources[passage["source_id"]]
                raw_path = root / source["local_path"]
                if raw_path.exists() and b > len(raw_path.read_text(encoding="utf-8").splitlines()):
                    raise ValueError("Evidence outside downloaded source")
    case_ids, variant_ids, families = set(), set(), {}
    splits = {"development": set(), "final_test": set()}
    for case in references["cases"]:
        if case["case_id"] in case_ids:
            raise ValueError("Duplicate case ID")
        case_ids.add(case["case_id"])
        split = case["split"]
        if split not in splits:
            raise ValueError("Unknown split")
        if families.setdefault(case["family_id"], split) != split:
            raise ValueError("Question family leaks across splits")
        if case["kind"] not in {"answerable", "unanswerable", "misleading_document"}:
            raise ValueError("Unknown case kind")
        splits[split].add(case["kind"])
        if not case["variants"]:
            raise ValueError("Missing question variants")
        for variant in case["variants"]:
            if variant["variant_id"] in variant_ids or not variant["question"]:
                raise ValueError("Duplicate/empty question variant")
            variant_ids.add(variant["variant_id"])
            review = variant["human_review"]
            if review["status"] not in {"pending", "approved", "needs_changes"}:
                raise ValueError("Unknown human review status")
            if review["status"] == "pending" and (review["reviewer"] is not None or review["reviewed_on"] is not None):
                raise ValueError("Pending review must not fabricate human identity/date")
            if review["status"] != "pending":
                if not isinstance(review["reviewer"], str) or not review["reviewer"].strip():
                    raise ValueError("Reviewed records require a real reviewer")
                reviewed_on = review["reviewed_on"]
                if not isinstance(reviewed_on, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", reviewed_on):
                    raise ValueError("Reviewed records require an ISO review date")
                date.fromisoformat(reviewed_on)
            contexts = variant["contexts"]
            expected = {"genuine_evidence_plus_distractor", "distractor_only"} if case["kind"] == "misleading_document" else {"standard"}
            if set(contexts) != expected:
                raise ValueError("Expected context-specific behaviors")
            for name, context in contexts.items():
                if not context["required_response"] or context["status"] not in {"answered", "abstained"}:
                    raise ValueError("Missing expected response/status")
                if len(set(context["required_claims"])) != len(context["required_claims"]):
                    raise ValueError("Duplicate required claim")
                if any(cid not in claims for cid in context["required_claims"]):
                    raise ValueError("Unknown required claim")
                if context["status"] == "abstained" and context["required_claims"]:
                    raise ValueError("Abstention must not require document-backed answer facts")
                if context["status"] == "answered" and not context["required_claims"]:
                    raise ValueError("Answered context requires evidence claims")
                if name == "distractor_only" and context["status"] != "abstained":
                    raise ValueError("Distractor-only context must abstain")
        if case["kind"] == "misleading_document" and not case.get("distractor"):
            raise ValueError("Missing synthetic distractor")
    if any(kinds != {"answerable", "unanswerable", "misleading_document"} for kinds in splits.values()):
        raise ValueError("Both splits must cover all case kinds")
    return {"sources": len(sources), "families": len(families), "questions": len(variant_ids)}


def render_review(root, *, replace=False):
    root = Path(root)
    counts = validate_artifacts(root)
    registry = load_json(root / "config/sources.json")
    # Rendering passages is permitted only after offline asset integrity verification.
    acquire(root, registry, load_json(root / "config/chunking.json"), fetch=False)
    references = load_json(root / "evaluation/reference_cases.json")
    sources = {s["source_id"]: s for s in registry["sources"]}
    claims = {c["claim_id"]: c for c in references["claims"]}
    reviews = [v["human_review"] for c in references["cases"] for v in c["variants"]]
    review_counts = dict(Counter(r["status"] for r in reviews))
    human_status = next(iter(review_counts)) if len(review_counts) == 1 else "mixed"

    def cell(value):
        return str(value).replace("&", "&amp;").replace("|", "&#124;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", " ")

    lines = ["# Evidence review — AI-assisted reference v2", "",
             "Generated from the corrected reference set and verified raw source bytes.",
             f"Human review metadata: {review_counts}. Approval concerns reference records only, not system performance.",
             "Required claim IDs are AND requirements. Alternatives within one claim are OR choices;",
             "passages within a single alternative are joint support. Read the passage catalogue below.",
             "Abstention contexts require the stated response behavior, not document-backed answer facts.", "",
             "| Variant / split / family | Question | Context / status | Required facts and response | Evidence | Human review |",
             "| --- | --- | --- | --- | --- | --- |"]
    rows = 0
    for case in references["cases"]:
        for variant in case["variants"]:
            for context_name, context in variant["contexts"].items():
                required = context["required_claims"]
                facts = [claims[cid]["fact"] for cid in required] + context["required_response"]
                links = [f"[{cid}](#{cid})" for cid in required]
                lines.append("| " + " | ".join([
                    cell(f"{variant['variant_id']} / {case['split']} / {case['family_id']}"),
                    cell(variant["question"]), cell(f"{context_name} / {context['status']}"),
                    "<br>".join(cell(f) for f in facts), ", ".join(links) or "No supported-answer facts",
                    cell("; ".join(str(variant["human_review"][key]) for key in ("status", "reviewer", "reviewed_on")))]) + " |")
                rows += 1
    lines += ["", "## Supporting passage catalogue", "",
              "URLs and line numbers refer to the immutable CPython source revision.",
              "RST below is quoted as inert source data; embedded commands are never executed.", ""]
    for claim in references["claims"]:
        cid = claim["claim_id"]
        lines += [f'<a id="{cid}"></a>', f"### {cid}", "", claim["fact"], ""]
        for index, alternative in enumerate(claim["alternatives"], 1):
            lines += [f"Alternative {index} (OR): {alternative['support_summary']}", ""]
            for passage in alternative["passages"]:
                source = sources[passage["source_id"]]
                a, b = passage["lines"]
                url = f"{source['immutable_url']}#L{a}-L{b}"
                lines += [f"[{source['source_id']} lines {a}–{b}]({url})", "", "```rst"]
                raw_lines = (root / source["local_path"]).read_text(encoding="utf-8").splitlines()
                lines.extend(raw_lines[a - 1:b])
                lines += ["```", ""]
    lines += ["## Review workflow", "", "Edit human-review fields only after an actual human review.",
              "This table reflects recorded reference review, not system-performance approval. Corrections belong in the reference JSON;",
              "preserve an annotated copy before regenerating a changed table.", ""]
    content = "\n".join(lines).encode("utf-8")
    output = root / "docs/evidence-review.md"
    if replace:
        output.write_bytes(content)
    else:
        save_once(output, content)
    return {**counts, "review_rows": rows, "required_claims": len(claims),
            "human_status": human_status, "human_review_counts": review_counts, "output": "docs/evidence-review.md"}
