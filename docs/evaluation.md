# Frozen research evaluation

This is a curated account of the existing protocol, reviewed references and saved results, not a new evaluation. The [reference snapshot](../research/reference_cases.json) is locally visible and the holdout is consumed. Do not reuse final questions to tune or claim another unbiased assessment.

## Protocol and diagnostic

Development and final questions stayed in separate families, with related variants together. Facts are variant-specific. A required claim can have OR evidence alternatives; multiple spans within one alternative are joint requirements. Source-span checks inspect returned/packed text, not just filenames. Duplicate support does not inflate denominators. Excluded/audit-only/synthetic content cannot establish official support.

Original targets were Recall@5 ≥ 0.90, citation precision/completeness≥0.95, correct abstention on both negative cases and zero executed actions/invented citations/source-instruction obedience. Development safety prerequisites failed. The owner separately authorized a diagnostic despite that failure, exclusion of undefined T06 ordinary contexts, and one quality attempt per context instead of three timing repetitions. Targets were not lowered; failed prerequisites stayed failed.

The final inventory had 10 ordinary, 6 gold, 2 genuine-plus-distractor and 2 distractor-only contexts:20 requests total. Gold/control construction stayed separate from ordinary retrieval. Gold evidence was never counted as an ordinary retrieval success. Earlier development60-second stopped runs, the120-second follow-up and reused gold responses remain distinct histories, not a uniform latency experiment. The final diagnostic itself had20 accepted outputs and no timeout/skip.

## Scoring and preserved results

Correctness uses frozen0/0.5/1 anchors and approved required facts. Average variants within family, then give each family equal weight. Completeness, claim-to-citation support, status appropriateness and structural acceptance are separate. Undefined denominators/incomplete atomic assignments yield N/A, not a perfect score.

Successful abstention requires the approved checklist, no unsupported substantive answer and an appropriate response. A refusal enum containing an unsupported answer fails. Validation errors are errors, never abstentions.

| Ordinary measurement | Saved result |
|---|---|
| Correctness |3/6=0.5; three related answerable families|
| Recall@1/@3/@5 family macro |1/6,1/3,2/3|
| Pooled required claims at@1/@3/@5 |1/7,2/7,4/7|
| MRR family macro |457/1260|
| Complete variants at@1/@3/@5 |1/6,2/6,4/6|
| Strict packed full support |2/6 variants;2/7 claims|
| Successful abstention |0/4 variants;0/2 complete cases|
| Primary citation precision/completeness/unsupported-claim rate |N/A; incomplete atomic annotation|
| False-abstention/instruction-following aggregates |N/A; required finer judgments unassigned|

T01's supplied209–223 activation table contains the fact, but the frozen proxy requires broader200–223 support. This caveat does not change retrieval/packing scores, references or evidence alternatives.

Saved gold correctness is5.5/6; genuine-plus-distractor correctness1/2; distractor-only successful abstention1/2. These stay separate from ordinary results. Available emitted-claim support counts in controls remain in the original metrics and do not fill missing ordinary annotations. Across all contexts,20/20 emitted citation occurrences resolve structurally. That is not semantic support. No command was executed. Neither general injection resistance nor isolated note influence is established.

## Human review and evidence

Tanjila Islam confirmed AI-assisted assessments on 2026-11-15, first ten ordinary responses, then ten controls. This was not a blind independent review, authenticated signature or second reviewer. Only confirmed dimensions were assigned.

[Readable saved evidence](saved-evidence.md), [original human annotations](../research/results/human-review.original.json), [original dimensional metrics](../research/results/reviewed-metrics.original.json), [retrieval measurements](../research/results/retrieval-measurements.original.json) and [packing measurements](../research/results/retained-evidence.original.json) substantiate the findings. Curated context projections retain exact output/evidence but omit duplicated HTTP/token traces; see [curation](curation.md). They are not full byte-identical original records.

## Resources and limitations

Historical ordinary HTTP timings: n=10, median47.578s, range37.453–59.978s. Native peak 7,293,464,576 bytes (6.793GiB); Python lifetime peak 423,600,128 bytes was separately scoped. Model 2,497,280,256 bytes; runtime 64,501,533 bytes. These saved descriptive measurements are not an API benchmark, original repeated-timing target pass, causal speedup or model-equivalence claim.

One fixed MiniLM candidate scored lower than BM25 on development; the [saved comparison](../research/results/dense-development-comparison.original.json) is unselected. Its weight license remained unresolved. No dense weights or implementation is distributed here.

Small related families, a visible consumed holdout, AI-assisted confirmation and incomplete annotations limit generalization. Some original targets failed; others remain unavailable. Future quality changes need fresh independent evidence. Application integration tests do not establish answer quality.
