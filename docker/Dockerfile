# AegisAI Dockerfile
FROM python:3.11-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    cmake \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml MANIFEST.in ./
COPY src/ ./src/

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install the package with all dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install .

# ============================================
# Stage 2: Production
# ============================================
FROM python:3.11-slim AS production

# Labels
LABEL maintainer="AegisAI Team" \
    version="0.1.0" \
    description="Agentic fraud & trust intelligence system for Account Takeover detection"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    # Application settings
    AEGIS_ENVIRONMENT=production \
    AEGIS_LOG_LEVEL=INFO \
    AEGIS_API_HOST=0.0.0.0 \
    AEGIS_API_PORT=8000

# Create non-root user for security
RUN groupadd --gid 1000 aegis && \
    useradd --uid 1000 --gid aegis --shell /bin/bash --create-home aegis

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=aegis:aegis src/ ./src/
COPY --chown=aegis:aegis config/ ./config/
COPY --chown=aegis:aegis docker/entrypoint.sh /app/entrypoint.sh
COPY --chown=aegis:aegis main.py ./

# Ensure entrypoint is executable
RUN chmod +x /app/entrypoint.sh

# Create directories for logs and data
RUN mkdir -p /app/logs/audit /app/data && \
    chown -R aegis:aegis /app/logs /app/data

# Switch to non-root user
USER aegis

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ready || exit 1

# Default command: Run the FastAPI server
ENTRYPOINT ["/app/entrypoint.sh"]
