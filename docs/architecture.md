# Architecture and purpose

The useful default task is preparing a reviewable support draft from documentation and user information. The research asks whether a small local generator can stay grounded in explicit evidence. Observed generation failures are why these are separate paths.

~~~mermaid
flowchart LR
  U[Same-origin browser UI] --> A[FastAPI · one local worker]
  A --> R[Fixed BM25 · 40 source-linked parents]
  R --> C[Four pinned CPython sources]
  A --> D[SQLite drafts · revisions · review events]
  A -. explicit Windows opt-in .-> G[Unverified Qwen3 CPU adapter]
~~~

Corpus load verifies bundle/file hashes, chunk identities and exact source mappings. Search uses byte-identical frozen BM25 helper copies. Scores are ranking values, not probabilities. Stale distutils lines remain raw but are excluded from serving chunks. Includes/links are not fetched.

Ticket text is deterministic. User statements, explicitly supplied environment, missing-information fields, human notes and source quotations remain distinct. Selected IDs must resolve to corpus blocks. SQLite stores revision snapshots and review events; compare-and-swap revisions reject stale actions. There is no sending endpoint or command execution.

The UI uses labelled controls, local assets and literal rendering. Review labels are not authenticated identities. Local storage is unencrypted; no multi-user security or production-readiness claim is made.

Experimental generation allows one explicit native request, no queue. The frozen prompt, source-block packing, model, template, greedy settings, schema and independent validation remain unchanged. Overflow is rejected without silent truncation; raw status stays separate from structural acceptance. The owned CPU process is cleaned up.

Runtime code never imports references, gold selectors or saved final responses. Selected evaluator source is included for inspection only. No final-assessment runner or holdout-reset command is distributed.

Publication adaptation: application version remains 0.2.0; only the native launcher is edited to load the unchanged packaged corpus by default and use a checkout-relative data directory. Research modules, prompt, packing, model settings and validator remain byte-identical. New demonstration helpers use synthetic data. [Curation notes](curation.md) distinguish exact copies from edited/generated files.
