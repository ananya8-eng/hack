# FastAPI backend — Render deployment
FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY backend ./backend

# Copy entrypoint
COPY docker-entrypoint.sh /docker-entrypoint.sh

# Fix Windows CRLF issues + make executable
RUN sed -i 's/\r$//' /docker-entrypoint.sh && \
    chmod +x /docker-entrypoint.sh

# Render dynamically injects PORT
ENV PORT=10000

# Important for Render detection
EXPOSE 10000

ENTRYPOINT ["/docker-entrypoint.sh"]