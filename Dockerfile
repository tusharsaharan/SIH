# ---- frontend build ----
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --silent
COPY frontend/ ./
RUN npm run build

# ---- backend runtime ----
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# CPU-only torch first (much smaller/faster than CUDA default)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY aegis/ ./aegis/
COPY --from=web /web/dist ./frontend/dist/

# SQLite lives here at runtime (ephemeral unless a volume is attached)
RUN mkdir -p aegis/data
EXPOSE 8000
CMD ["python", "-m", "aegis.server"]
