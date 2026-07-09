# 初始化、提交并推送所有 plugins/Provider-* 到 GitHub
# Usage: powershell -ExecutionPolicy Bypass -File scripts/publish_provider_evo_plugins.ps1

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PluginsDir = Join-Path $Root "plugins"
$GhUser = "nichengfuben"
$Proxy = "http://127.0.0.1:10808"

$env:HTTP_PROXY = $Proxy
$env:HTTPS_PROXY = $Proxy
$env:http_proxy = $Proxy
$env:https_proxy = $Proxy

$GitignoreLines = @(
    "accounts.py",
    "config.toml",
    "data/",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    ".venv/",
    "dist/",
    "build/",
    "*.egg-info/",
    ".pytest_cache/"
)

function Ensure-Gitignore {
    param([string]$Dir)
    $gi = Join-Path $Dir ".gitignore"
    $existing = @()
    if (Test-Path $gi) {
        $existing = Get-Content $gi -ErrorAction SilentlyContinue
    }
    $merged = ($existing + $GitignoreLines) | Where-Object { $_ -and $_.Trim() } | Select-Object -Unique
    Set-Content -Path $gi -Value $merged -Encoding utf8
}

function Ensure-TestsCi {
    param([string]$Dir, [string]$Name)
    $testsDir = Join-Path $Dir "tests"
    if (-not (Test-Path $testsDir)) { New-Item -ItemType Directory -Path $testsDir | Out-Null }
    $initPy = Join-Path $testsDir "__init__.py"
    if (-not (Test-Path $initPy)) { Set-Content -Path $initPy -Value "" -Encoding utf8 }
    $testPy = Join-Path $testsDir "test_plugin.py"
    if (-not (Test-Path $testPy)) {
        @"
"""$Name basic tests."""
from __future__ import annotations

from pathlib import Path


def test_manifest_exists() -> None:
    manifest = Path(__file__).parent.parent / "_manifest.json"
    disabled = Path(__file__).parent.parent / "_manifest.json.disabled"
    assert manifest.is_file() or disabled.is_file()


def test_plugin_entry() -> None:
    import sys
    plugin_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(plugin_dir))
    import plugin
    assert hasattr(plugin, "create_plugin")
"@ | Set-Content -Path $testPy -Encoding utf8
    }
    $wfDir = Join-Path $Dir ".github\workflows"
    if (-not (Test-Path $wfDir)) { New-Item -ItemType Directory -Path $wfDir -Force | Out-Null }
    $ci = Join-Path $wfDir "ci.yml"
    if (-not (Test-Path $ci)) {
        @"
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: `${{ matrix.python-version }}
      - name: Install
        run: |
          python -m pip install --upgrade pip pytest provider-sdk
          if [ -f pyproject.toml ]; then pip install -e .; fi
      - name: Test
        run: python -m pytest tests/ -v
"@ | Set-Content -Path $ci -Encoding utf8
    }
}

$results = @()
Get-ChildItem -Path $PluginsDir -Directory -Filter "Provider-*" | ForEach-Object {
    $name = $_.Name
    $dir = $_.FullName
    Write-Host "`n=== $name ===" -ForegroundColor Cyan
    try {
        Ensure-Gitignore -Dir $dir
        Ensure-TestsCi -Dir $dir -Name $name
        Push-Location $dir
        if (-not (Test-Path ".git")) {
            git init -b main | Out-Null
        }
        git add -A
        $status = git status --porcelain
        if ($status) {
            git commit -m "feat: Provider-Evo plugin scaffold for $name" | Out-Null
        }
        $remote = "https://github.com/$GhUser/$name.git"
        $hasOrigin = $false
        git remote 2>$null | ForEach-Object { if ($_ -eq "origin") { $hasOrigin = $true } }
        if ($hasOrigin) {
            git remote set-url origin $remote
        } else {
            git remote add origin $remote
        }
        gh repo view "$GhUser/$name" 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            gh repo create "$GhUser/$name" --public --description "$name for Provider-Evo" 2>&1 | Out-Null
        }
        git push -u origin main 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $results += [pscustomobject]@{ Plugin = $name; Status = "ok" }
        } else {
            $results += [pscustomobject]@{ Plugin = $name; Status = "push_failed" }
        }
    } catch {
        $results += [pscustomobject]@{ Plugin = $name; Status = "error: $_" }
        Write-Host "  ERROR: $_" -ForegroundColor Red
    } finally {
        Pop-Location
    }
}

Write-Host "`n=== Summary ===" -ForegroundColor Green
$results | Format-Table -AutoSize
