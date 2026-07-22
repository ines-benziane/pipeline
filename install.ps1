# Active l'environnement conda cible avant de lancer ce script.
$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot

Write-Host "Installing myo-pipeline workspace..."

Push-Location $ScriptDir
try {
    pip install -e ".[dev]"
    if ($LASTEXITCODE -ne 0) { throw "pip install -e .[dev] a échoué (exit code $LASTEXITCODE)" }
} finally {
    Pop-Location
}

pip install -e "$ScriptDir\medical_report"
if ($LASTEXITCODE -ne 0) { throw "pip install -e medical_report a échoué (exit code $LASTEXITCODE)" }

pip install -e "$ScriptDir\medical_report\src\medical_report\tools\py-bspline"
if ($LASTEXITCODE -ne 0) { throw "pip install -e bsplines a échoué (exit code $LASTEXITCODE)" }

Write-Host "myo-pipeline workspace installed successfully."
