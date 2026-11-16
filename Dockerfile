# Official multi-platform identity; tested Linux target is amd64.
FROM python:3.13.11-slim-bookworm@sha256:20080e807bfc404f8450b185cf0fc95d553462673598549613735f70a5b4d5d0 AS build
WORKDIR /build
COPY application/requirements-runtime.txt /build/requirements-runtime.txt
RUN python -m pip install --no-cache-dir setuptools==78.1.0 && python -m pip install --no-cache-dir -r requirements-runtime.txt
COPY application/pyproject.toml /build/application/pyproject.toml
COPY application/LICENSE /build/application/LICENSE
COPY application/src /build/application/src
RUN python -m pip wheel --no-deps --no-build-isolation --wheel-dir /wheels ./application

FROM python:3.13.11-slim-bookworm@sha256:20080e807bfc404f8450b185cf0fc95d553462673598549613735f70a5b4d5d0
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY application/requirements-runtime.txt /app/requirements-runtime.txt
RUN python -m pip install --no-cache-dir -r requirements-runtime.txt
COPY --from=build /wheels /wheels
RUN python -m pip install --no-cache-dir --no-deps /wheels/*.whl && rm -r /wheels && \
    python -c "from pathlib import Path; [p.unlink() for p in Path('/usr/local/lib/python3.13/site-packages/pip/_vendor/distlib').glob('*.exe')]" && \
    groupadd --gid 10001 support && useradd --uid 10001 --gid 10001 --no-create-home support && \
    mkdir -p /var/lib/support && chown 10001:10001 /var/lib/support && chmod -R a-w /app /usr/local/lib/python3.13/site-packages/support_api
USER 10001:10001
VOLUME ["/var/lib/support"]
EXPOSE 8010
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 CMD ["python","-c","import urllib.request; urllib.request.urlopen('http://127.0.0.1:8010/ready',timeout=2).read()"]
CMD ["python","-m","support_api.container"]
