FROM python:3.12-slim AS build

ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --requirement requirements.txt

FROM python:3.12-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --home-dir /app app

WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --chown=app:app app ./app

USER 10001:10001

FROM runtime AS api
ENV PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)"]

CMD ["gunicorn", "--config=python:app.gunicorn_config", "--bind=0.0.0.0:8000", "--workers=2", "--access-logfile=-", "app.app:app"]

FROM runtime AS worker
EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8001/metrics', timeout=2)"]

CMD ["python", "-m", "app.worker"]
