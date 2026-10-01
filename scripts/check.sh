#!/bin/sh
# Lokalnie to samo co CI (.github/workflows/ci.yml): node --check frontendu, ruff i pytest backendu.
# Backend w kontenerze python:3.12-slim (lokalny Python zwykle nie ma zaleznosci). Uruchom z katalogu glownego repo.
set -e
cd "$(dirname "$0")/.."

echo "== frontend: node --check"
for f in frontend/js/*.js frontend/js/views/*.js frontend/sw.js; do node --check "$f"; done

echo "== backend: ruff + pytest"
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONPATH=/app -v "$PWD/backend:/app" -w /app python:3.12-slim \
  sh -c "pip install -q --user -r requirements.txt -r requirements-dev.txt 2>/dev/null \
    && ~/.local/bin/ruff check --no-cache . && python -m pytest -q -p no:cacheprovider"
