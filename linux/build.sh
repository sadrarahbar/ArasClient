#!/usr/bin/env bash
set -euo pipefail
linux_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(dirname -- "$linux_dir")"
cd "$project_dir"
"$linux_dir/.venv/bin/python" "$linux_dir/prepare_cores.py"
if ! command -v objdump >/dev/null 2>&1; then
    task_binutils="$HOME/.local/share/tesla-build-tools/usr"
    if [[ -x "$task_binutils/bin/objdump" ]]; then
        export PATH="$task_binutils/bin:$PATH"
        export LD_LIBRARY_PATH="$task_binutils/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    else
        echo 'Install binutils to build the Linux bundle.' >&2
        exit 1
    fi
fi
"$linux_dir/.venv/bin/python" -m PyInstaller --noconfirm --onedir --name TeslaVpn \
    --distpath "$project_dir/artifacts/linux" --workpath "$linux_dir/build/pyinstaller" \
    --specpath "$linux_dir/build" --paths "$linux_dir" \
    --add-data "$linux_dir/assets:assets" --add-data "$linux_dir/cores:cores" \
    --add-data "$linux_dir/licenses:licenses" \
    --exclude-module PySide6 --exclude-module PyQt5 "$linux_dir/main.py"
cp "$linux_dir/install.sh" "$project_dir/artifacts/linux/TeslaVpn/install.sh"
cp "$linux_dir/README.fa.md" "$project_dir/artifacts/linux/TeslaVpn/README.fa.md"
cp "$linux_dir/assets/app-logo.svg" "$project_dir/artifacts/linux/TeslaVpn/icon.svg"
tar -czf "$project_dir/artifacts/linux/TeslaVpn-1.0.1-linux-x86_64.tar.gz" -C "$project_dir/artifacts/linux" TeslaVpn
