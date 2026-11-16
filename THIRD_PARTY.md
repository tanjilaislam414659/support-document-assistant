# Third-party materials and licensing

The approved MIT project-code license does not relicense third-party material.

| Material | Ownership / terms | Included material |
|---|---|---|
| Four CPython 3.13.0 documentation sources | Python Software Foundation and contributors; PSF license; documentation examples also available under 0BSD as described upstream | Unchanged raw files, chunks, mappings and required LICENSE/copyright.rst/license.rst in application/src/support_api/resources/corpus/data/ |
| Official Qwen3 chat template | Qwen / Alibaba; Apache-2.0 | Unchanged config/qwen3-official-template.jinja and notices/qwen3-Apache-2.0.txt |
| Qwen3-4B Q4_K_M weights | Official pinned Qwen repository; Apache-2.0 at the recorded revision | Not included |
| llama.cpp Windows CPU runtime | ggml-org contributors; MIT | No executable or library included; pinned identities only |
| FastAPI, Uvicorn, Pydantic and other runtime dependencies | Respective upstream owners/licenses | Installed from pinned requirements, not vendored; installed package notices remain in the container |
| Jinja2, Transformers and tokenizer tooling | Respective upstream licenses, including BSD and Apache-2.0 | Optional Windows dependencies; no weights included |
| Playwright / Chrome | Upstream test tooling and browser terms | Test dependencies only; no browser distribution included |
| Official Python / Debian container base | Python and Debian third-party terms | Pinned official base; its system notices/licenses remain intact |

CPython upstream commit: [60403a5409ff2c3f3b07dd2ca91a7a3e096839c7](https://github.com/python/cpython/tree/60403a5409ff2c3f3b07dd2ca91a7a3e096839c7). The included source registry preserves immutable file URLs and Git blob/SHA-256 identities. The stale distutils passage stays in raw source but is excluded from serving chunks; release notes are audit evidence only and are not part of the retrieval corpus.

Qwen template/weights provenance: [official immutable revision](https://huggingface.co/Qwen/Qwen3-4B-GGUF/tree/bc640142c66e1fdd12af0bd68f40445458f3869b). The Apache notice is copied from the previously verified official cached LICENSE, SHA-256 5de36594c10839788a8c589443a8ef9d8b8d17c65a1b5807206ae037fc36c6bd. No model was downloaded during publication preparation.

The historical MiniLM candidate's pinned weight license remains unresolved. Its saved comparison is retained as an unselected development result; its weights and embedding implementation are not distributed here. The license of a Python library is not permission to redistribute model weights.

No code or sample documents from Easy-Bot-QnA are reused. That separate educational project and Retail-Forecasting are unchanged.
