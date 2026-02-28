#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Running smoke + contract checks..."
uv run python tools/scaffold/validate_service_descriptors.py
uv run pytest tests/integration/api/test_observability.py tests/integration/api/test_tasks.py -q
cd frontend
npm run test:run -- App.test.tsx
echo "Smoke + contract checks passed."
