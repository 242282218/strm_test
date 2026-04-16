# =============================================================================
# Multi-stage Dockerfile for quark_strm
# =============================================================================
# Stage 1: Frontend Builder (Node.js)
# Stage 2: Python Dependencies Builder
# Stage 3: Runtime Image (Python slim)
# =============================================================================

# Build arguments for metadata
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION=0.1.0

# =============================================================================
# Stage 1: Frontend Build
# =============================================================================
FROM node:22-alpine AS frontend-builder

WORKDIR /build

# Copy package files first for better caching
COPY web/package*.json ./

# Install dependencies
RUN npm ci --prefer-offline --no-audit

# Copy source files
COPY web/ ./

# Build production bundle
RUN npm run build

# =============================================================================
# Stage 2: Python Dependencies Builder
# =============================================================================
FROM python:3.11-slim AS python-builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install dependencies
COPY requirements.txt ./

# Upgrade pip and install dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Stage 3: Runtime Image
# =============================================================================
FROM python:3.11-slim AS runtime

# Labels for container metadata
LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.title="quark-strm" \
      org.opencontainers.image.description="Quark STRM Media Management System" \
      org.opencontainers.image.source="https://github.com/242282218/smart_media"

# Create non-root user for security
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=python-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY app ./app
COPY config ./config
COPY core ./core
COPY models ./models
COPY schemas ./schemas
COPY services ./services
COPY utils ./utils

# Copy frontend build from frontend-builder
COPY --from=frontend-builder /build/dist ./web/dist

# Copy configuration files
COPY config.example.yaml ./config.example.yaml
COPY pyproject.toml ./pyproject.toml

# Create necessary directories and set permissions
RUN mkdir -p logs strm && \
    chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WEB_CONCURRENCY=2 \
    PORT=8000

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ready || exit 1

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
