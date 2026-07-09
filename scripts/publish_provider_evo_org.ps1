# Provider-Evo Org 批量发布（需 gh 对 Org 有写权限，或仓库已手动创建）
param(
    [string]$Org = "Provider-Evo",
    [string]$Proxy = "http://127.0.0.1:10808",
    [switch]$CreateOnly,
    [switch]$PushOnly
)

$ErrorActionPreference = "Continue"
$env:HTTP_PROXY = $Proxy
$env:HTTPS_PROXY = $Proxy

$EvoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$CoreRoot = Join-Path $EvoRoot "provider-self"
$PluginsRoot = Join-Path $CoreRoot "plugins"

$Repos = @(
    @{ Name = "provider-v2"; Path = $CoreRoot },
    @{ Name = "provider-sdk"; Path = Join-Path $EvoRoot "provider-sdk" },
    @{ Name = "plugin-repo"; Path = Join-Path $EvoRoot "plugin-repo" },
    @{ Name = "provider-docs"; Path = Join-Path $EvoRoot "provider-docs" }
)

if (Test-Path $PluginsRoot) {
    foreach ($pluginDir in Get-ChildItem $PluginsRoot -Directory -Filter "Provider-*") {
        $Repos += @{ Name = $pluginDir.Name; Path = $pluginDir.FullName }
    }
}

Write-Host "Target org: $Org ($($Repos.Count) repos)"
gh auth status 2>&1 | Out-Host

function Ensure-Repo {
    param([string]$Name)
    $remote = "git@github.com:${Org}/${Name}.git"
    if ($PushOnly) { return $remote }
    $check = gh repo view "${Org}/${Name}" --json name 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Creating ${Org}/${Name} ..."
        gh repo create "${Org}/${Name}" --public --description "Provider-Evo $Name" 2>&1 | Out-Host
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Create failed for $Name (fix PAT or create manually on GitHub)"
            return $null
        }
    }
    return $remote
}

foreach ($item in $Repos) {
    if (-not (Test-Path $item.Path)) {
        Write-Warning "Skip missing $($item.Path)"
        continue
    }
    Push-Location $item.Path
    try {
        $remote = Ensure-Repo -Name $item.Name
        if (-not $remote) { continue }
        if ($CreateOnly) { continue }

        if (-not (Test-Path ".git")) {
            git init -b main 2>&1 | Out-Host
        }
        if (-not (git rev-parse HEAD 2>$null)) {
            git add -A 2>&1 | Out-Host
            git commit -m "init ${Org}/$($item.Name)" 2>&1 | Out-Host
        }
        git remote remove origin 2>$null
        git remote add origin $remote
        Write-Host "Pushing $($item.Name) -> $remote"
        git push -u origin HEAD:main 2>&1 | Out-Host
        if ($item.Name -eq "provider-v2") {
            git push -u origin HEAD:dev 2>&1 | Out-Host
        }
    } catch {
        Write-Warning "Failed $($item.Name): $_"
    } finally {
        Pop-Location
    }
}

Write-Host "Done."
