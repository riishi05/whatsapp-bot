# ---------- Stage 1: build React frontend ----------
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build   # outputs to /frontend/dist

# ---------- Stage 2: backend + serve built frontend ----------
FROM python:3.11-slim
WORKDIR /app

# system deps
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
# static frontend build served by FastAPI at /
COPY --from=frontend-build /frontend/dist ./app/static

# Cloud Run injects $PORT; default to 8080 for local docker run
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
