#!/usr/bin/env bash
set -euo pipefail
linux_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -x "$linux_dir/.venv/bin/python" ]]; then
    python3 -m venv --system-site-packages "$linux_dir/.venv"
fi
if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$linux_dir/.venv/bin/python" --default-index https://pypi.org/simple -r "$linux_dir/requirements.txt"
else
    "$linux_dir/.venv/bin/python" -m pip install -r "$linux_dir/requirements.txt"
fi
if ! "$linux_dir/.venv/bin/python" -c 'import PyQt6.QtWidgets, PyQt6.QtNetwork' >/dev/null 2>&1; then
    if command -v uv >/dev/null 2>&1; then
        uv pip install --python "$linux_dir/.venv/bin/python" --default-index https://pypi.org/simple 'PyQt6==6.10.2'
    else
        "$linux_dir/.venv/bin/python" -m pip install 'PyQt6==6.10.2'
    fi
fi
"$linux_dir/.venv/bin/python" "$linux_dir/prepare_cores.py"
