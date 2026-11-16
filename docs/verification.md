# Local publication verification

Completed 2026-11-16 using a fresh isolated checkout and environment, without model weights, existing tickets or private caches. [Selected machine-readable results](publication-verification.json) retain measurements; raw machine logs stay private.

| Check | Actual outcome |
|---|---|
| Documented Windows setup | Installed pinned runtime dependencies and editable app; default CLI ready with four bundled sources |
| Default independence | No Torch, Transformers or full research distribution installed |
| Native draft/edit/review | Synthetic issue, revision2 review; temporary data; owned server stopped |
| API/portable fixture tests |12 +6 passed|
| Real Chrome fixture workflow |14 checks passed; zero page errors|
| Docker/Compose |9 checks passed, actual build/run/persistence|
| CI configuration |YAML parsed; permissions/action pins checked; commands rehearsed with sparse checkout|
| Optional Windows startup |Explicit experimental mode reports missing artifacts; default workflow still ready; zero generation calls|

The actual application tests ran after root research/source/configuration directories were removed from the sparse checkout. Default application artifacts alone were sufficient. Dependencies installed without pip-cache reuse; Docker built without build-layer reuse, with the immutable base already available. The checkout finished clean.

Docker tests verified non-root UID10001, read-only code/corpus, readiness health check, loopback-only publication, absence of ML/research packages and Windows executables, synthetic source selection/draft/edit/review/stale rejection, exact SQLite history persistence after container recreation, and missing/corrupt artifact readiness503 while health stayed200. Publication image/project names are separate from the original; no original tickets volume was used or removed.

One observed publication image size was206,601,906 bytes; process-health startup1.23s, synthetic fixture startup1.10s; build step18.53s. These are descriptive integration observations, not repeated latency or model benchmarks. The record includes actual Linux dependency versions. Local Python was3.13.5, Chrome157.0.8103.78 and Docker Linux runtime used the pinned Python3.13.11 image. Those were the preparation-stage local checks; hosted verification is recorded separately below.

The20 curated saved contexts passed120 retained identity checks and192 eligible source-text mapping checks. Frozen inference bridge/code/prompt/template and original metric/annotation snapshots remain unchanged. These are integrity checks on existing results; no final query, generation or rescoring occurred.

Four new clean screenshots were captured and visually inspected. They show clearly labelled fictional Orbit data with generation disabled. Original verification screenshots in the development repository remain untouched. Mobile checks use a390px Chrome viewport, not a physical-device/Safari/accessibility certification.

The final publication history is initialized after privacy curation; the tested preparation commit is retained only as a provenance identifier, not imported history. Final application/CI/container payload hashes match the tested checkout. Public authorship uses only the proposed no-reply identity. No model weights, runtime binaries, environments, DBs, private user content, secrets or developer paths are proposed for tracking. Third-party source examples/notices retain their legitimate upstream attribution.

All owned test servers/containers/UUID volumes were stopped/removed. At preparation closure, no remote/push/release/upload existed. Publication was subsequently authorized. A fresh real-model public install, other browsers/architectures and production readiness remain unverified or unsupported. No cloud deployment was provisioned.

## Observed hosted GitHub Actions

[The first licensed-main run](https://github.com/tanjilaislam414659/support-document-assistant/actions/runs/43920212270) completed successfully on 2026-11-16 for commit118d104f4d68df2467502f76f412981909ec6e16. All job steps passed: 12 API tests, 6 portable-corpus tests, 14 real Chromium checks and 9 actual Docker/Compose checks. The hosted browser was Chromium159.0.8154.6. No CI portability fix was required for this run.

These are synthetic engineering checks, not retrieval-quality evidence or real-model inference. The original research methods/results and consumed holdout remain unchanged. The saved local preparation record retains its historical pending-CI status; it has not been rewritten to impersonate a hosted run. See [current workflow runs](https://github.com/tanjilaislam414659/support-document-assistant/actions/workflows/application.yml) for subsequent commits. A release is made only after the final main commit passes.
