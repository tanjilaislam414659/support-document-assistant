"""Separate cohorts; never turn missing human judgments into successful scores."""
from collections import Counter,defaultdict
from .final_assessment_scoring import semantic_measurements,ratio

def aggregate_semantics(jobs,results,human_reviews):
    by_id={r["context_id"]:r for r in results}
    if len(by_id)!=len(results):raise ValueError("Duplicate result")
    planned={j["context_id"] for j in jobs}
    if set(by_id)-planned or set(human_reviews)-planned:raise ValueError("Unknown context")
    cohorts={}
    for kind in dict.fromkeys(j["context_type"] for j in jobs):
        selected=[j for j in jobs if j["context_type"]==kind]
        rows=[];outcomes=Counter()
        for j in selected:
            r=by_id.get(j["context_id"],{"outcome":"not_attempted","raw_sha256":None})
            outcomes[r["outcome"]]+=1
            m=semantic_measurements(j,r,human_reviews.get(j["context_id"],{}))
            rows.append({"context_id":j["context_id"],"family_id":j["family_id"],
                "expected_negative":j["expected_behavior"]["status"]=="abstained",**m})
        reviewed=[r for r in rows if r["available"]]
        families=defaultdict(list)
        for r in rows:families[r["family_id"]].append(r)
        family_values=[]
        for family,items in families.items():
            available=[r for r in items if r["available"]]
            values={"family_id":family,"variants":len(items),"human_scored_variants":len(available),
                "complete_human_assessment":len(available)==len(items)}
            for metric in ("correctness","successful_abstention","false_abstention"):
                eligible=[r for r in items if (r["expected_negative"] if metric=="successful_abstention" else not r["expected_negative"])]
                observed=[r for r in eligible if r["available"]]
                values[metric]={"value":sum(float(r[metric]) for r in observed)/len(observed)
                    if eligible and len(observed)==len(eligible) else None,
                    "planned":len(eligible),"observed":len(observed)}
            for metric in ("citation_precision","citation_completeness","unsupported_claim_rate"):
                defined=[r[metric]["value"] for r in available if r[metric]["value"] is not None]
                values[metric]={"value":sum(defined)/len(defined)
                    if defined and len(available)==len(items) else None,
                    "defined_variants":len(defined),"planned_variants":len(items),
                    "undefined_variants":len(items)-len(defined)}
            family_values.append(values)
        citation={}
        for metric in ("citation_precision","citation_completeness","unsupported_claim_rate"):
            citation[metric]=ratio(sum(r[metric]["numerator"] for r in reviewed),
                sum(r[metric]["denominator"] for r in reviewed))
            citation[metric]["scope"]="human-scored outputs only; never application errors"
        negatives=[r for r in rows if r["expected_negative"]]
        macro={}
        for metric in ("correctness","successful_abstention","false_abstention","citation_precision","citation_completeness","unsupported_claim_rate"):
            values=[f[metric]["value"] for f in family_values if f[metric]["value"] is not None]
            macro[metric]={"value":sum(values)/len(values) if values else None,
                "defined_families":len(values),"all_families":len(family_values)}
        cohorts[kind]={"family_macro_defined_only":macro,"planned":len(selected),"outcomes":dict(outcomes),"human_scored":len(reviewed),
            "pending_or_unavailable":len(rows)-len(reviewed),"per_context":rows,"per_family":family_values,
            "citation_micro":citation,
            "confirmed_abstentions_over_all_planned_negatives":ratio(sum(
                bool(r.get("successful_abstention")) for r in negatives),len(negatives)),
            "abstention_numerator_is_provisional":any(not r["available"] and r.get("reason")!="application error or not attempted" for r in negatives),
            "target_attainment":"unavailable until every planned context is completed, accepted and independently reviewed"
                if len(reviewed)!=len(rows) else "compare original targets separately; no composite pass threshold"}
    return cohorts
