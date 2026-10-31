#!/usr/bin/env bash
set -euo pipefail

if [[ -f "$HOME/.config/aras-android/env.sh" ]]; then
    source "$HOME/.config/aras-android/env.sh"
fi

if ! command -v java >/dev/null 2>&1; then
    echo "Java is missing. Install a JDK and configure JAVA_HOME." >&2
    exit 1
fi

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

# arm64-v8a covers most current physical Android phones. Override for other devices.
./gradlew :app:assembleDebug "-PABI_FILTERS=${ABI_FILTERS:-arm64-v8a}" --console=plain "$@"
