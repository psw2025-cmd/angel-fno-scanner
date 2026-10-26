FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git gcc libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

ARG SOURCE_COMMIT=unknown
ENV GIT_SHA=$SOURCE_COMMIT
RUN printf '%s\n' "$SOURCE_COMMIT" > /app/SOURCE_COMMIT \
    && mkdir -p /app/logs /tmp/logs \
    && useradd --create-home --shell /bin/bash scanner \
    && chown -R scanner:scanner /app /tmp/logs \
    && chmod -R 777 /app/logs /tmp/logs
USER scanner

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TMPDIR=/tmp

ENTRYPOINT ["python", "scanner.py"]
