# FastAPI backend — build from repository root: docker build -f Dockerfile .
FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY docker-entrypoint.sh /docker-entrypoint.sh
# Strip CRLF when building on Windows so the shebang works in Linux.
RUN sed -i 's/\r$//' /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh

EXPOSE 8000

# Render sets PORT; local compose can set PORT=8000.
ENTRYPOINT ["/docker-entrypoint.sh"]
