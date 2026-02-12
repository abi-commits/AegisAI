#!/usr/bin/env sh

set -e

# Default values
AEGIS_API_HOST="${AEGIS_API_HOST:-0.0.0.0}"
AEGIS_API_PORT="${AEGIS_API_PORT:-8000}"
AEGIS_WORKERS="${AEGIS_WORKERS:-1}"

echo "==================================="
echo "AegisAI Starting..."
echo "Environment: ${AEGIS_ENVIRONMENT:-production}"
echo "Host: ${AEGIS_API_HOST}:${AEGIS_API_PORT}"
echo "Workers: ${AEGIS_WORKERS}"
echo "==================================="

# Wait for dependencies if needed
if [ -n "$WAIT_FOR_HOST" ]; then
    echo "Waiting for $WAIT_FOR_HOST..."
    while ! nc -z ${WAIT_FOR_HOST} ${WAIT_FOR_PORT:-80}; do
        sleep 1
    done
    echo "$WAIT_FOR_HOST is available"
fi

# Run database migrations or initialization if needed
# python -m aegis_ai.scripts.init_db

# Start the application
# Normalize log level to lowercase for uvicorn which expects lowercase values
AEGIS_LOG_LEVEL_LOWER=$(echo "${AEGIS_LOG_LEVEL:-info}" | tr '[:upper:]' '[:lower:]')

exec uvicorn aegis_ai.api.gateway:app \
    --host "$AEGIS_API_HOST" \
    --port "$AEGIS_API_PORT" \
    --workers "$AEGIS_WORKERS" \
    --access-log \
    --log-level "${AEGIS_LOG_LEVEL_LOWER}"
