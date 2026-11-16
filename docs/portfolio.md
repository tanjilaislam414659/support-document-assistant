# Portfolio material — draft for Tanjila Islam

## Short description

A local documentation-search and support-draft workspace built with FastAPI, plain JavaScript and SQLite. It returns pinned passages, creates editable drafts and records review of specific revisions. Separate CPU Qwen3 research preserves grounding and abstention failures; generation stays optional. The default workflow is model-free, Docker-packaged and checked with synthetic API/browser/container tests.

Proposed repository description: “Local source-linked documentation search and revision-reviewed support drafts, with a separately evaluated experimental CPU RAG generator.”

## Two CV bullets

- Built a local FastAPI/JavaScript support workspace over 40 versioned CPython documentation chunks, with source-linked BM25 search, editable SQLite drafts, optimistic revision checks and explicit review events; packaged its model-free workflow with Docker and CI.
- Designed and ran a 20-context CPU Qwen3 diagnostic with family-separated references and preserved source evidence; reported human-confirmed ordinary correctness 3/6 and successful abstention 0/4, separating structural acceptance from factual support.

These are AI-assisted project claims grounded in implementation/saved evidence, not production use, employment impact, a blind external evaluation or improved model quality.

## Three-minute interview walkthrough

**0:00–0:35 — What can someone run?**

“This starts with a practical workflow: search documentation, select passages, write a draft and review a saved revision. The default app needs no model. A small FastAPI service serves plain JavaScript, and SQLite stores revisions and review events. Nothing executes documentation commands or submits tickets.”

**0:35–1:10 — Why these choices?**

“I used four licensed CPython 3.13.0 documents pinned to one immutable revision. Forty parent chunks preserve source lines, sections and code layout. BM25 gives an inspectable fixed baseline. An embedding experiment did worse on the small development set and had unresolved weight licensing, so I retained it as an unselected result. The source text stays visible before drafting. Revisions prevent an old review from silently covering edited content.”

**1:10–1:55 — What did evaluation reveal?**

“Generator research is separate from API checks. References specify facts per variant and alternative supporting passages. Related variants stay in the same family. The one final diagnostic had ten ordinary contexts and ten controls. Ordinary correctness was 3/6, successful abstention 0/4 and family-macro Recall@5 was 2/3. Some responses reversed a pip default or confused exact and minimum versions despite plausible citations. A refusal label could still contain an unsupported answer. Primary citation aggregates remain N/A where atomic annotations were incomplete.”

**1:55–2:30 — What are the limits?**

“The holdout was locally visible and is now consumed; I cannot keep reusing it as a new benchmark. Failed development safety cases stayed failed; the owner authorized a diagnostic, not readiness approval. T01 also exposes a measurement caveat: its table contains the answer but misses a broader frozen span requirement. I documented that without changing the score. Human review was AI-assisted and explicitly confirmed, not blind or independent.”

**2:30–3:00 — Why optional generation?**

“Qwen3 runs on CPU, but saved ordinary requests had a roughly 48-second median and still made semantic mistakes. It stays behind a Windows experimental flag. Docker runs search/drafting without models. Synthetic checks cover provenance, literal rendering, stale revisions, persistence and cleanup. Those checks show integration, not trustworthy answers. Any future quality change needs fresh independent evidence.”
