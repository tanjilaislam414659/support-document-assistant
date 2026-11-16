# API and draft workflow

The default service binds 127.0.0.1:8010. [Committed OpenAPI 0.2.0](../application/openapi-0.2.0.json) documents exact types/bounds; the running service exposes /openapi.json and the local /docs reference.

| Endpoint | Purpose |
|---|---|
| GET /health | Process liveness |
| GET /ready | Corpus/index/storage readiness;503 on required-artifact failure |
| GET /metadata | Source/version identities, capabilities, historical limitations |
| POST /search | Bounded ranked source-linked passages |
| POST /tickets/draft | Deterministic local draft |
| GET /tickets/{id} | Content, revision, history and review events |
| PATCH /tickets/{id} | Permitted edits with expected_revision |
| POST /tickets/{id}/review | Explicit action for the saved current revision |
| POST /experimental/answer | Disabled by default; unverified Windows generation only |

Search example, using a new user question:

~~~json
{"question":"<new user question>","top_k":3}
~~~

Draft example; select source_id/passage_id pairs returned by search:

~~~json
{"issue":"<observed issue>","environment":{"OS":"<explicit user value>"},"selected_sources":[{"source_id":"<returned source ID>","passage_id":"<returned passage ID>"}],"human_notes":"<human note>"}
~~~

PATCH permits title, issue, environment, selected_sources, missing_information and human_notes:

~~~json
{"expected_revision":1,"human_notes":"<edited note>"}
~~~

Review requires the current revision and explicit boolean confirmation:

~~~json
{"expected_revision":2,"confirm_review":true,"reviewer_label":"local user","note":"Read this saved revision"}
~~~

Unknown/mismatched/duplicate sources are rejected. Provenance/review/model-output fields cannot be set directly. Edits invalidate previous review; stale revision409, invalid input422, unknown ticket404, oversized request413 and unavailable artifacts503 are explicit. Disabled generation403 and native timeout504 are errors, never successful abstentions.

No sending or command-execution endpoint exists. Citation eligibility establishes structural provenance, not support for an answer.
