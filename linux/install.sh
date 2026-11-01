#!/usr/bin/env bash
set -euo pipefail
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
target_dir="$HOME/.local/opt/tesla-vpn"
mkdir -p "$target_dir" "$HOME/.local/bin" "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/scalable/apps"
if [[ "$source_dir" != "$target_dir" ]]; then
    cp -a "$source_dir/." "$target_dir/"
fi
ln -sf "$target_dir/TeslaVpn" "$HOME/.local/bin/tesla-vpn"
cp "$target_dir/icon.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/tesla-vpn.svg"
python3 - "$HOME/.local/share/applications/tesla-vpn.desktop" "$target_dir/TeslaVpn" <<'PY'
import sys
from pathlib import Path
executable=sys.argv[2].replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$')
Path(sys.argv[1]).write_text('[Desktop Entry]\nType=Application\nName=Tesla Vpn\nComment=Single-profile VPN client\nExec="'+executable+'"\nIcon=tesla-vpn\nTerminal=false\nCategories=Network;Security;\nStartupWMClass=tesla-vpn\n')
PY
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$HOME/.local/share/applications" || true
echo "Installed Tesla Vpn. Run: $HOME/.local/bin/tesla-vpn"
