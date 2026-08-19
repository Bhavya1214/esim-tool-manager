<#
.SYNOPSIS
    Bootstrap installer for eSim Tool Manager on Windows.
.USAGE
    irm https://raw.githubusercontent.com/<USER>/esim-tool-manager/main/scripts/install_windows.ps1 | iex
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/<YOUR_GITHUB_USERNAME>/esim-tool-manager.git"
$InstallDir = "$env:LOCALAPPDATA\esim-tool-manager"
$BinDir = "$env:USERPROFILE\.local\bin"
$EntryPoint = "esim-tool.exe"

Write-Host "Installing eSim Tool Manager..." -ForegroundColor Cyan

# 1. Check Prereqs
if (-not (Get-Command "git" -ErrorAction SilentlyContinue)) {
    Write-Host "Git not found. Please install Git for Windows first." -ForegroundColor Red
    exit 1
}
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found. Please install Python 3.9+ from python.org or Microsoft Store." -ForegroundColor Red
    exit 1
}

# 2. Clone/Update
if (Test-Path $InstallDir) {
    Write-Host "Updating existing installation..." -ForegroundColor Yellow
    Set-Location $InstallDir
    git pull
} else {
    Write-Host "Cloning repository..." -ForegroundColor Yellow
    git clone $RepoUrl $InstallDir
    Set-Location $InstallDir
}

# 3. Venv & Install
Write-Host "Setting up Python environment..." -ForegroundColor Yellow
python -m venv venv
$VenvPython = "$InstallDir\venv\Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -e .

# 4. Create Shim / Symlink
if (-not (Test-Path $BinDir)) { New-Item -ItemType Directory -Force -Path $BinDir | Out-Null }

$ShimPath = "$BinDir\esim-tool.bat"
$ShimContent = @"
@echo off
"$VenvPython" -m esim_tool_manager.main %*
"@
Set-Content -Path $ShimPath -Value $ShimContent -Encoding Ascii

# 5. PATH Check
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$BinDir*") {
    Write-Host "Adding $BinDir to User PATH..." -ForegroundColor Yellow
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$BinDir", "User")
    Write-Host "PATH updated. Please RESTART YOUR TERMINAL for changes to take effect." -ForegroundColor Green
}

Write-Host "Installation complete!" -ForegroundColor Green
Write-Host "Run 'esim-tool --help' in a NEW terminal window." -ForegroundColor Cyan
