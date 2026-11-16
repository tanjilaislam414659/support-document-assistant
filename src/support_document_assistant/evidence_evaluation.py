"""Source-character evidence coverage, independent of question text or retrieval."""
from collections import defaultdict
from fractions import Fraction
import math

from .assets import sha256

EVALUATOR_ID = "source-character-coverage-v1"
KS = (1, 3, 5)


def exact(value):
    value = Fraction(value)
    return {"numerator": value.numerator, "denominator": value.denominator, "value": float(value)}


def unpack(value):
    return Fraction(value["numerator"], value["denominator"])


class SourceCoverage:
    def __init__(self, sources, chunks):
        self.sources = dict(sources)
        self.catalog = {}
        self.positions = {}
        self.line_offsets = {}
        for source_id, text in self.sources.items():
            offsets = [0]
            for line in text.splitlines(keepends=True):
                offsets.append(offsets[-1] + len(line))
            self.line_offsets[source_id] = offsets
        for chunk in chunks:
            cid = chunk["chunk_id"]
            if cid in self.catalog:
                raise ValueError("Duplicate catalogue chunk ID")
            sid = chunk["source_id"]
            if sid not in self.sources or chunk.get("eligible_for_answer_support") is not True:
                raise ValueError("Ineligible evidence source")
            text = chunk["text"]
            if chunk["text_sha256"] != sha256(text.encode("utf-8")):
                raise ValueError("Returned text hash mismatch")
            source = self.sources[sid]
            positions, pieces = set(), []
            for segment in chunk["segments"]:
                a, b = segment["source_char_range"]
                x, y = segment["chunk_char_range"]
                first, last = segment["source_lines"]
                offsets = self.line_offsets[sid]
                if not 1 <= first <= last < len(offsets):
                    raise ValueError("Segment line mapping outside source")
                if not offsets[first - 1] <= a < b <= offsets[last]:
                    raise ValueError("Segment character/line mappings disagree")
                if not 0 <= x < y <= len(text) or source[a:b] != text[x:y]:
                    raise ValueError("Returned text does not match source mapping")
                pieces.append(source[a:b])
                positions.update(i for i in range(a, b) if not source[i].isspace())
            if not pieces or "\n\n".join(pieces) != text:
                raise ValueError("Unmapped returned chunk text")
            self.catalog[cid] = chunk
            self.positions[cid] = (sid, positions)

    def _validate_hits(self, hits):
        for rank, hit in enumerate(hits, 1):
            if hit.rank != rank or not math.isfinite(hit.score) or hit.score <= 0:
                raise ValueError("Invalid ranked hit")
            cid = hit.chunk["chunk_id"]
            if cid not in self.catalog or hit.chunk != self.catalog[cid]:
                raise ValueError("Hit differs from verified serving catalogue")

    def assess(self, required_ids, claims, hits):
        self._validate_hits(hits)
        covered = defaultdict(set)
        contributors = []
        for hit in hits:
            sid, positions = self.positions[hit.chunk["chunk_id"]]
            covered[sid].update(positions)
            contributors.append((hit.chunk["chunk_id"], sid, positions))
        result = {}
        for cid in required_ids:
            claim = claims[cid]
            alternatives = []
            for alternative in claim["alternatives"]:
                passages = []
                for passage in alternative["passages"]:
                    sid = passage["source_id"]
                    a, b = passage["lines"]
                    if sid not in self.sources or not 1 <= a <= b < len(self.line_offsets[sid]):
                        raise ValueError("Required evidence is outside approved source")
                    start, end = self.line_offsets[sid][a - 1], self.line_offsets[sid][b]
                    needed = {i for i in range(start, end) if not self.sources[sid][i].isspace()}
                    if not needed:
                        raise ValueError("Required evidence span is empty")
                    matched = needed & covered[sid]
                    passages.append({"source_id": sid, "lines": [a, b],
                                     "source_char_range": [start, end],
                                     "required_nonwhitespace_characters": len(needed),
                                     "covered_nonwhitespace_characters": len(matched),
                                     "complete": matched == needed,
                                     "contributing_chunk_ids": list(dict.fromkeys(
                                         chunk_id for chunk_id, source_id, positions in contributors
                                         if source_id == sid and positions & needed))})
                if not passages:
                    raise ValueError("An alternative must contain evidence passages")
                alternatives.append({"complete": all(p["complete"] for p in passages), "passages": passages})
            if not alternatives:
                raise ValueError("A claim must contain evidence alternatives")
            result[cid] = {"complete": any(a["complete"] for a in alternatives), "alternatives": alternatives}
        return result

    def evaluate(self, variant_id, family_id, required_ids, claims, hits):
        if not required_ids or len(set(required_ids)) != len(required_ids):
            raise ValueError("Scored variants require distinct required claims")
        self._validate_hits(hits)
        evidence = {str(k): self.assess(required_ids, claims, hits[:k]) for k in KS}
        first_rank = None
        for rank in range(1, len(hits) + 1):
            if any(c["complete"] for c in self.assess(required_ids, claims, hits[:rank]).values()):
                first_rank = rank
                break
        counts = {k: sum(c["complete"] for c in matches.values()) for k, matches in evidence.items()}
        return {"variant_id": variant_id, "family_id": family_id, "kind": "answerable",
                "required_claims": list(required_ids), "required_claim_count": len(required_ids),
                "covered_claim_counts": counts,
                "recall_at": {k: exact(Fraction(n, len(required_ids))) for k, n in counts.items()},
                "complete_at": {k: n == len(required_ids) for k, n in counts.items()},
                "first_support_rank": first_rank,
                "reciprocal_rank": exact(Fraction(1, first_rank) if first_rank else 0),
                "evidence_matches_at": evidence,
                "evidence_matches_all_returned": self.assess(required_ids, claims, hits)}


def aggregate(variants):
    if not variants or len({v["variant_id"] for v in variants}) != len(variants):
        raise ValueError("Aggregation needs distinct scored variants")
    if any(v["kind"] != "answerable" for v in variants):
        raise ValueError("Only applicable answerable variants enter primary metrics")
    grouped = defaultdict(list)
    for variant in variants:
        grouped[variant["family_id"]].append(variant)

    def mean_metrics(items):
        count = len(items)
        return {"recall_at": {str(k): exact(sum((unpack(v["recall_at"][str(k)]) for v in items), Fraction()) / count) for k in KS},
                "complete_at": {str(k): exact(Fraction(sum(v["complete_at"][str(k)] for v in items), count)) for k in KS},
                "mrr": exact(sum((unpack(v["reciprocal_rank"]) for v in items), Fraction()) / count)}

    families = []
    for family_id, items in sorted(grouped.items()):
        families.append({"family_id": family_id, "variant_ids": [v["variant_id"] for v in items],
                         "variant_count": len(items),
                         "required_claim_opportunities": sum(v["required_claim_count"] for v in items),
                         **mean_metrics(items)})
    n = len(variants)
    required = sum(v["required_claim_count"] for v in variants)
    macro = {"recall_at": {}, "complete_at": {}}
    for k in map(str, KS):
        macro["recall_at"][k] = exact(sum((unpack(f["recall_at"][k]) for f in families), Fraction()) / len(families))
        macro["complete_at"][k] = exact(sum((unpack(f["complete_at"][k]) for f in families), Fraction()) / len(families))
    macro["mrr"] = exact(sum((unpack(f["mrr"]) for f in families), Fraction()) / len(families))
    return {"answerable_variants": n, "answerable_families": len(families),
            "required_claim_opportunities": required, "per_family": families, "family_macro": macro,
            "variant_macro": mean_metrics(variants),
            "micro_counts": {str(k): {"covered_claims": sum(v["covered_claim_counts"][str(k)] for v in variants),
                                     "required_claims": required,
                                     "complete_variants": sum(v["complete_at"][str(k)] for v in variants),
                                     "variants": n} for k in KS}}
