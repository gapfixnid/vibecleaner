param(
    [string]$Python = "python",
    [string]$VenvPath = ".venv-runtime",
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$TauriRoot = Join-Path $RepoRoot "desktop\src-tauri"
$OutputDir = Join-Path $TauriRoot "binaries"
$SidecarName = "server-x86_64-pc-windows-msvc"
$VenvFullPath = Join-Path $RepoRoot $VenvPath
$RuntimePython = Join-Path $VenvFullPath "Scripts\python.exe"
$DistExe = Join-Path $RepoRoot "dist\$SidecarName.exe"
$OutputExe = Join-Path $OutputDir "$SidecarName.exe"
$FontSource = Join-Path $BackendRoot "infrastructure\assets\fonts"

if (-not (Test-Path $RuntimePython)) {
    & $Python -m venv $VenvFullPath
}

if (-not $SkipInstall) {
    & $RuntimePython -m pip install -U pip
    & $RuntimePython -m pip install -r (Join-Path $RepoRoot "requirements-runtime.txt")
    & $RuntimePython -m pip install -r (Join-Path $RepoRoot "requirements-build.txt")
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

Push-Location $RepoRoot
try {
    & $RuntimePython -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --name $SidecarName `
        --paths $BackendRoot `
        --add-data "$FontSource;backend\infrastructure\assets\fonts" `
        --exclude-module torch `
        --exclude-module torchvision `
        --exclude-module torchmetrics `
        --exclude-module pytorch_lightning `
        --exclude-module spacy `
        --exclude-module matplotlib `
        --exclude-module scipy `
        --exclude-module pandas `
        --exclude-module IPython `
        --exclude-module pytest `
        (Join-Path $BackendRoot "main.py")

    Copy-Item -Force $DistExe $OutputExe
}
finally {
    Pop-Location
}

$sizeMb = [math]::Round((Get-Item $OutputExe).Length / 1MB, 2)
Write-Host "Built runtime sidecar: $OutputExe ($sizeMb MB)"
Write-Host "Model files are not bundled. They download on demand to the app data models directory."
