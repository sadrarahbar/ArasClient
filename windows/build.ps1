$ErrorActionPreference = 'Stop'
& "$PSScriptRoot/.venv/Scripts/python.exe" "$PSScriptRoot/build.py"
if ($LASTEXITCODE) { throw 'Windows build failed.' }
