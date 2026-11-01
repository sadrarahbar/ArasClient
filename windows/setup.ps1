$ErrorActionPreference = 'Stop'
if (!(Test-Path "$PSScriptRoot/.venv/Scripts/python.exe")) {
    python -m venv "$PSScriptRoot/.venv"
    if ($LASTEXITCODE) { throw 'Python 3.12 x64 is required.' }
}
& "$PSScriptRoot/.venv/Scripts/python.exe" -m pip install -r "$PSScriptRoot/requirements.txt"
if ($LASTEXITCODE) { throw 'Dependency installation failed.' }
& "$PSScriptRoot/.venv/Scripts/python.exe" "$PSScriptRoot/prepare_cores.py"
if ($LASTEXITCODE) { throw 'Native core verification failed.' }
