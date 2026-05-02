#!/usr/bin/env bash
# Bootstrap script: install mise tools, python env, and install the Engram plugin.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "==> Installing mise tools..."
if ! command -v mise &>/dev/null; then
  curl https://mise.run | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
mise install

echo "==> Creating virtual environment with uv..."
uv venv .venv
uv sync

echo "==> Installing Engram plugin..."
uv run python -m scripts.install engram

echo ""
echo "Done. Activate the provider with:"
echo "  hermes memory set engram"
echo ""
echo "Or add to ~/.hermes/config.yaml:"
echo "  memory:"
echo "    provider: engram"
