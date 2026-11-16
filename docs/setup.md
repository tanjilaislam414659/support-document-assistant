# Setup, Docker and verification

Use Python 3.13 and the root README commands, from the checkout root. / is the UI; /docs is a local reference; /openapi.json is typed OpenAPI. --port selects another loopback port; --data-directory chooses a writable directory. Stop with Ctrl+C.

The publication launcher uses the packaged corpus. It needs no original data/ tree. The separate --portable flag also explicitly disables generation.

## Docker

Dockerfile pins official python:3.13.11-slim-bookworm to index sha256:20080e807bfc404f8450b185cf0fc95d553462673598549613735f70a5b4d5d0. Tested architecture is Linux amd64. Compose publishes only 127.0.0.1:8010:8010, runs UID/GID 10001 with one worker, drops capabilities and uses a read-only root filesystem. The dedicated tickets volume is mounted at /var/lib/support; /tmp is a small tmpfs.

~~~powershell
docker compose up --build -d
docker compose ps
docker compose logs support
docker compose down
~~~

down preserves user tickets. Do not remove that volume if you need its drafts. Back up SQLite/database/WAL consistently while stopped. There is no automatic private-database migration.

The health check uses /ready. Missing/corrupt corpus artifacts return readiness503 while /health remains live. A healthy process is not a correctness guarantee. Linux generation is unsupported.

## Synthetic integration checks

~~~powershell
.\.venv\Scripts\python.exe -m pip install -r application/requirements-test.txt
.\.venv\Scripts\python.exe -m unittest discover -s application/tests -p test_api.py
.\.venv\Scripts\python.exe -m unittest discover -s application/tests -p test_portable.py
.\.venv\Scripts\python.exe application/tests/browser_smoke.py --channel chrome --output application/.app-data/browser
docker build -t support-document-assistant:0.2.0 .
.\.venv\Scripts\python.exe application/tests/container_smoke.py --output application/.app-data/container.json
~~~

Chrome must already be installed for --channel chrome. Hosted CI instead installs the pinned Playwright release's Chromium on its ephemeral runner. Tests use invented evidence/fake generation, never weights. HTML-looking security strings belong to verification fixtures; portfolio screenshots use a separate clean fixture.

Docker tests own UUID containers/volumes and a separate Compose project, and remove only those resources. They never delete the default user tickets volume. Browser helpers stop their fixture server. Do not run the container smoke while another app occupies8010.

## CI and demonstrations

.github/workflows/application.yml has contents:read, pinned actions and no persisted credentials. Its sparse checkout needs no root research package, references, final results, private DB or ignored model/cache. Local verification is described in [verification](verification.md); hosted Actions has passed; see [workflow runs](https://github.com/tanjilaislam414659/support-document-assistant/actions/workflows/application.yml).

Clean screenshots use only synthetic Orbit data, with generation disabled:

~~~powershell
.\.venv\Scripts\python.exe application/tools/capture_demo.py --output application/.app-data/new-demo --channel chrome
~~~

The helper refuses to overwrite existing output. Committed screenshots are actual captures, not mockups or Qwen3 outputs.
