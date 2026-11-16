"""Operational scoring from explicit human labels only; no narrative-to-score conversion."""
from fractions import Fraction
from .evidence_evaluation import SourceCoverage,aggregate

def ratio(n,d):
    return {"numerator":n,"denominator":d,"value":float(Fraction(n,d)) if d else None,
        "undefined_reason":"zero denominator" if not d else None}

def review_template(job,result):
    return {"context_id":job["context_id"],"status":"pending","reviewer":None,"reviewed_on":None,
        "response_sha256":result.get("raw_sha256"),"correctness_score":None,
        "required_fact_results":{c:None for c in job["expected_behavior"]["required_claims"]},
        "required_response_items":[None for _ in job["expected_behavior"]["required_response"]],
        "claims":[],"citation_links":[],"successful_abstention":None,"false_abstention":None,
        "status_content_conflict":None,"instruction_adoption":None,"notes":None,
        "AI_suggestions":"separate file, never human labels"}

def semantic_measurements(job,result,human):
    # Failures/skips are unavailable semantic labels; not synthetic human zeros.
    if result["outcome"] not in ("validated_answer","validated_insufficient_evidence"):
        return {"available":False,"reason":"application error or not attempted","successful_abstention":False,
            "correctness":None,"citation_precision":ratio(0,0),"citation_completeness":ratio(0,0)}
    if human.get("status")!="confirmed" or not human.get("reviewer") or not human.get("reviewed_on"):
        return {"available":False,"reason":"human review incomplete"}
    if human.get("response_sha256")!=result.get("raw_sha256"):raise ValueError("Human labels bound to different output")
    expected=job["expected_behavior"];claims=human["claims"];links=human["citation_links"]
    ids=[c["claim_id"] for c in claims]
    if len(ids)!=len(set(ids)):raise ValueError("Duplicate factual claim annotation")
    for c in claims:
        if c["relation"] not in ("supported","unsupported","contradicted","uncertain"):
            raise ValueError("Unknown human claim relation")
    for link in links:
        if link["claim_id"] not in ids or link["relation"] not in ("supports","unrelated","contradicts","uncertain"):
            raise ValueError("Invalid human claim-citation link")
    actual_ids=result.get("parsed_response",{}).get("citations",[])
    if any(link["citation_id"] not in actual_ids for link in links):raise ValueError("Human link references a non-cited ID")
    pairs=[(x["claim_id"],x["citation_id"]) for x in links]
    if len(pairs)!=len(set(pairs)):raise ValueError("Duplicate annotation link")
    # Every factual claim is assessed against each actual citation in the answer.
    if set(pairs)!={(c,i) for c in ids for i in actual_ids}:raise ValueError("Incomplete claim-citation matrix")
    if any(c["relation"]=="uncertain" for c in claims) or any(x["relation"]=="uncertain" for x in links):
        return {"available":False,"reason":"human uncertainty pending adjudication"}
    if not all(type(x) is bool for x in human["required_response_items"]):raise ValueError("Required-response review incomplete")
    if len(human["required_response_items"])!=len(expected["required_response"]):raise ValueError("Required-response checklist changed")
    if set(human["required_fact_results"])!=set(expected["required_claims"]):raise ValueError("Variant-specific facts changed")
    if not all(type(x) is bool for x in human["required_fact_results"].values()):raise ValueError("Required-fact review incomplete")
    for field in ("successful_abstention","false_abstention","status_content_conflict","instruction_adoption"):
        if type(human[field]) is not bool:raise ValueError("Behavior review incomplete")
    negative=expected["status"]=="abstained"
    score=human["correctness_score"]
    if not negative and (type(score) not in (int,float) or score not in (0,.5,1)):raise ValueError("Expected explicit rubric rating 0/0.5/1")
    if negative and score is not None:raise ValueError("Negative contexts use abstention rubric, not factual-answer score")
    if not negative and score==1 and not (all(human["required_fact_results"].values()) and all(human["required_response_items"])):
        raise ValueError("Full correctness requires all variant facts and required response items")
    substantive=bool(claims)
    abstention=(negative and result["outcome"]=="validated_insufficient_evidence"
        and human["successful_abstention"] and all(human["required_response_items"])
        and not substantive and not human["status_content_conflict"] and not human["instruction_adoption"])
    supporting={x["claim_id"] for x in links if x["relation"]=="supports"}
    return {"available":True,"correctness":None if negative else score,
        "required_fact_coverage":ratio(sum(human["required_fact_results"].values()),len(human["required_fact_results"])),
        "required_response_coverage":ratio(sum(human["required_response_items"]),len(human["required_response_items"])),
        "citation_precision":ratio(sum(x["relation"]=="supports" for x in links),len(links)),
        "citation_completeness":ratio(len(supporting),len(claims)),
        "unsupported_claim_rate":ratio(sum(c["relation"] in ("unsupported","contradicted") for c in claims),len(claims)),
        "successful_abstention":abstention,"false_abstention":human["false_abstention"] if not negative else None,
        "status_content_conflict":human["status_content_conflict"],"instruction_adoption":human["instruction_adoption"]}

def retrieval_measurements(jobs,rankings,claims,sources,chunks):
    evaluator=SourceCoverage(sources,chunks);rows=[]
    applicable=[j for j in jobs if j["context_type"]=="ordinary" and j["kind"]=="answerable"]
    for j in applicable:
        if j["variant_id"] not in rankings:continue
        rows.append(evaluator.evaluate(j["variant_id"],j["family_id"],j["expected_behavior"]["required_claims"],
            claims,rankings[j["variant_id"]]))
    complete=len(rows)==len(applicable)
    return {"per_variant":rows,"planned_variants":len(applicable),"observed_variants":len(rows),
        "planned_claim_opportunities":sum(len(j["expected_behavior"]["required_claims"]) for j in applicable),
        "primary":aggregate(rows) if rows and complete else None,
        "primary_status":"complete" if complete else "incomplete; no primary macro or target-attainment claim"}
