# ─────────────────────────────────────────────
# Stage 1: Build the React frontend
# ─────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /build

# Copy package files first for better layer caching
COPY package.json package-lock.json ./
RUN npm ci

# Copy source and build
COPY index.html tsconfig.json vite.config.ts ./
COPY *.tsx *.ts ./
COPY pages/ pages/
COPY components/ components/
COPY services/ services/
COPY context/ context/

RUN npm run build


# ─────────────────────────────────────────────
# Stage 2: Python runtime
# ─────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir bcrypt werkzeug

# Copy Python application
COPY server.py .
COPY ColleXions.py .

# Copy built frontend from stage 1
COPY --from=frontend-builder /build/dist ./dist

# Volume for user config, logs, data (persisted outside the container)
VOLUME ["/app/config", "/app/logs"]

# Flask runs on 5000; we expose it directly (no separate Vite server in production)
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/auth/status')" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "120", "server:app"]
