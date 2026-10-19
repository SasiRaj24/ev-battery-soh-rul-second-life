FROM node:24-bookworm-slim AS frontend-build

WORKDIR /build/frontend_v2
RUN corepack enable && corepack prepare pnpm@11.25.0 --activate
COPY frontend_v2/package.json frontend_v2/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend_v2/ ./
RUN pnpm run build

FROM python:3.14-slim-bookworm AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-deploy.txt ./requirements-deploy.txt
RUN pip install --upgrade pip \
    && pip install -r requirements-deploy.txt

COPY backend/ ./backend/
COPY models/ ./models/
COPY data/processed/ ./data/processed/
COPY --from=frontend-build /build/frontend_v2/dist ./frontend_v2/dist

EXPOSE 10000
CMD ["sh", "-c", "uvicorn backend.app_v2.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
