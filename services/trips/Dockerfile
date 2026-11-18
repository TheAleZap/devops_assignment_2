# Base image: Python 3.14 on Debian slim (same Python version as local development).
FROM python:3.14-slim-trixie

# No .pyc files in the image; logs go straight to stdout without buffering.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, so this layer is cached until requirements.lock changes.
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

# Only the files the service needs at runtime: no tests, no .env, no COPY . .
COPY app.py config.py db.py migrate.py ./
COPY migrations/ migrations/
COPY trips/ trips/

# Run as an unprivileged user, not root.
RUN useradd --create-home --uid 10001 appuser
USER appuser

# The commit SHA is passed at build time and reported by /health.
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION} \
    PORT=8002

EXPOSE 8002
CMD ["python", "app.py"]
