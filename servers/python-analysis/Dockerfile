# Dockerfile
# Image for the Python analysis sandbox. Holds the scanpy-side tools from 7.4
# on; for now it holds only the shared health endpoint.
#
# This image must never gain a model client, a database driver, or a cloud SDK.
# The isolation is enforced at runtime by compose (internal network, read-only
# root, no environment) -- keeping the image itself thin is what makes that
# enforcement easy to believe.

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

RUN useradd --system --uid 10001 --user-group biogent

WORKDIR /app

COPY common/ ./common/
COPY servers/python-analysis/main.py ./servers/python-analysis/main.py

USER biogent

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]

CMD ["python", "servers/python-analysis/main.py"]
