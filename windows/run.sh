#!/usr/bin/env bash
set -euo pipefail
linux_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$linux_dir/.venv/bin/python" "$linux_dir/main.py" "$@"
