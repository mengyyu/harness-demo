#!/bin/bash
# Railway Startup Script — Harness Framework
set -e

echo "=== Harness Framework v0.2.0 ==="
echo "Python: $(python --version)"

# Create data directory for SQLite
mkdir -p data logs

# Start FastAPI (init_harness runs via startup event)
echo "=== Starting FastAPI on port ${PORT:-8000} ==="
exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info
