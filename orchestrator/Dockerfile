# Dockerfile
# Image for the orchestrator: the only component that holds the researcher's
# API key, talks to Postgres, and is reachable from the host.
#
# Kept separate from the server images rather than sharing a base, because the
# dependency sets diverge from 7.2 onward and the divergence is the point: an
# analysis sandbox must not carry a model client or a database driver.

FROM python:3.12-slim-bookworm

# Unbuffered so logs reach `docker compose logs` as they happen. No bytecode
# because the runtime filesystem is read-only.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Fixed uid, so ownership of anything mounted in is predictable across hosts.
RUN useradd --system --uid 10001 --user-group biogent

WORKDIR /app

# common/ first: it changes less often than component code, so the layer
# cache survives most edits.
COPY common/ ./common/
COPY orchestrator/main.py ./orchestrator/main.py

USER biogent

EXPOSE 8000

# In the image rather than in compose, so the check travels with it. No curl
# in a slim image, and adding one for this would be a package in every layer.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]

CMD ["python", "orchestrator/main.py"]
