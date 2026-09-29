# Dockerfile
# Image for the data access server: from 7.3 the only component that resolves a
# dataset ID to a storage location.
#
# It is on the internal network with the sandboxes and holds no credentials.
# When this resolves S3 prefixes instead of local folders after the import, the
# credential question has to be answered deliberately rather than by adding an
# environment variable here.

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

RUN useradd --system --uid 10001 --user-group biogent

WORKDIR /app

COPY common/ ./common/
COPY servers/data-access/main.py ./servers/data-access/main.py

USER biogent

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]

CMD ["python", "servers/data-access/main.py"]
