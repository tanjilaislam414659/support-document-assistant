# Optional Windows generator

Default search/drafting needs none of these optional dependencies/artifacts. Linux generation is unsupported; Docker omits its adapter. The endpoint is disabled without --experimental. Publication checks make no real inference call.

The snapshot includes the existing unchanged adapter and required frozen helpers, not a historical CLI/final runner. Only the publication launcher changes corpus loading, using the same immutable packaged corpus.

## Exact candidate

- Official [Qwen/Qwen3-4B-GGUF](https://huggingface.co/Qwen/Qwen3-4B-GGUF/tree/bc640142c66e1fdd12af0bd68f40445458f3869b), revision bc640142c66e1fdd12af0bd68f40445458f3869b.
- Qwen3-4B-Q4_K_M.gguf only:2,497,280,256 bytes; SHA-2567485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5. Apache-2.0 at the recorded revision; no weights redistributed.
- Official [llama.cpp b12283](https://github.com/ggml-org/llama.cpp/releases/tag/b12283), commit f3b407ca1bfeeecebf9e9ef19fcd6eed565bd70a, Windows CPU. Expected files/sizes/hashes are in application/frozen-inference.json. No runtime binary included.
- Official non-thinking template; greedy seed0, threads2/2; one loopback worker; context4096; output192; absolute completion deadline120s; native8GiB guard.
- Original 2048-token packing budget including192 reserved output tokens. Runtime4096 does not expand evidence.
- Known prompt 800-character/8-ID versus schema 400/3 mismatch is retained.

Packing uses pinned Qwen2.5 tokenizer metadata, not Qwen2.5 generation. Its1.5B weights are not required. config/generator-model.json records metadata identities/locations. Models/runtime belong only in ignored models/ paths matching the bridge.

Manually acquire required artifacts from official immutable sources after reviewing terms; verify every expected size/hash and retain notices. No downloader runs at startup. [Model provenance](../research/config/model-provenance.json) records pinned identities and license evidence.

## Optional installation

On adequately resourced 64-bit Windows Python 3.13:

~~~powershell
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
.\.venv\Scripts\python.exe -m pip install -r requirements-experimental-windows.txt
# Separately supply/verify licensed artifacts at the recorded ignored paths.
.\.venv\Scripts\python.exe -m support_api --experimental
~~~

Default setup does not install this research source snapshot or tokenizer tooling. Optional requirements pin already-used dependency identities, not a new model. This preparation does not download artifacts or verify a fresh real-model installation. Missing artifacts leave generation unavailable.

One active request, no queue; additional calls409. Startup/metadata deadlines are separate from completion. Timeout/validation failures are errors, not successful abstentions. Raw status, application acceptance and semantic correctness differ. Output stays unverified, separate from tickets.

Saved ordinary correctness 3/6, successful abstention 0/4, HTTP median47.578s (n=10), native peak 6.793GiB and roughly2.50GB model are why generation is optional. They do not establish production readiness or general injection resistance.
