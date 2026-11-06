# Independent Streamable HTTP service image for wled-mcp (issue #11).
#
# Build context: a staged release directory created by deploy/stage_release.py that
# holds exactly the versioned wheel, requirements-runtime.txt and SHA256SUMS (the
# allowlist .dockerignore keeps everything else, including inventories and secrets,
# out of the context). Build locally on the target and never push:
#
#   docker build --pull -t wled-mcp:0.1.0 /app/binaries/wled-mcp/0.1.0
#
# Base image: official Python 3.13 slim image on Debian trixie, exact patch tag plus the
# multi-architecture index digest (docker.io/library/python, 2026-11-05). Update both
# together and rebuild deliberately; see docs/DEPLOYMENT.md.
FROM python:3.13.18-slim-trixie@sha256:09a17cad02668ae61ece136b4fd36ac3849e14f670ebedb637ea3e15580525bc

# Fixed non-root identity; adjust at build time if the host data directory needs a
# different owner (docker build --build-arg APP_UID=... --build-arg APP_GID=...).
ARG APP_UID=10001
ARG APP_GID=10001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_INPUT=1

COPY wled_mcp-0.1.0-py3-none-any.whl requirements-runtime.txt SHA256SUMS /tmp/wled-mcp-release/

# Verify the staged artifacts: SHA256SUMS must list both the wheel and the constraints
# exactly once each and both must match (a missing or duplicated line fails the build).
# Then install only the pinned wheel with the exported runtime constraints and remove
# the build inputs. No index package named wled-mcp is used.
RUN cd /tmp/wled-mcp-release \
    && grep -E '^[0-9a-f]{64}  (wled_mcp-0\.1\.0-py3-none-any\.whl|requirements-runtime\.txt)$' SHA256SUMS > required.sha256 \
    && test "$(cut -c67- required.sha256 | sort)" = "$(printf '%s\n' requirements-runtime.txt wled_mcp-0.1.0-py3-none-any.whl)" \
    && sha256sum --strict -c required.sha256 \
    && python -m pip install --no-cache-dir --root-user-action=ignore \
        --constraint requirements-runtime.txt \
        ./wled_mcp-0.1.0-py3-none-any.whl \
    && cd / && rm -rf /tmp/wled-mcp-release \
    && groupadd --gid "${APP_GID}" wledmcp \
    && useradd --no-log-init --uid "${APP_UID}" --gid "${APP_GID}" --no-create-home \
        --home-dir /nonexistent --shell /usr/sbin/nologin wledmcp \
    && install -d -o "${APP_UID}" -g "${APP_GID}" -m 0700 /app/data/wled-mcp \
    && wled-mcp --version

USER ${APP_UID}:${APP_GID}
WORKDIR /app/data/wled-mcp

# The console owns SIGTERM handling (drain up to 122 s, then exit 0); exec form keeps it
# PID 1 so the signal is delivered directly. Transport, bind, allowlist, credential file
# and paths are supplied explicitly by the Compose command.
STOPSIGNAL SIGTERM
ENTRYPOINT ["wled-mcp"]
CMD ["--help"]
