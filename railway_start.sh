#!/bin/bash
# Railway Startup Script — Harness Framework
# Railway 使用此脚本启动服务

set -e

echo "=== Harness Framework — Railway Deployment ==="
echo "Python: $(python --version)"
echo "Working dir: $(pwd)"

# Init the framework (database, MCP, skills, etc.)
python -c "
from run_demo import init_harness
init_harness()
print('Framework initialized successfully.')
"

echo "=== Starting FastAPI on port \${PORT:-8000} ==="
exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info
