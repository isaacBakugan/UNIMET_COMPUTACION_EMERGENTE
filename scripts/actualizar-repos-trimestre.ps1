<#
    Pushes /repo-template changes (new tests, guides, schemas) to every active repo of the
    current term, without clobbering answers students have already pushed.

    Source of truth for "which repos are active": trimestre-actual/estado.json, written by
    scripts/crear-repos-trimestre.ps1. If it doesn't exist, run that script first.

    Runs locally (gh + git), not as a GitHub Action: reuses the gh session already
    authenticated on this machine instead of storing a broad-scope token as a secret in
    the central repo just to push to N other repos.

    $PreservedFiles declares which template files are NEVER overwritten if they already
    exist in a team's repo (by default, preguntas.json: that's the team's real answers,
    not the template placeholder).

    Idempotent: if the diff against the template is empty, nothing is committed or pushed.
#>

param(
    # Folder with a subdirectory per team, same one used by crear-repos-trimestre.ps1
    [string]$InputsPath = "$PSScriptRoot/../trimestre-actual",

    # Folder with the template to sync
    [string]$RepoTemplatePath = "$PSScriptRoot/../repo-template",

    # Local folder where team repos get cloned/updated
    [string]$LocalDestination = "$PSScriptRoot/../.repos-trimestre-actual",

    [string]$CommitMessage = "[INFRA] Se actualiza el template del repo de grupo",

    # File NAMES (not paths) that are never overwritten if they already exist in the target
    # repo, matched at any depth. Matching by name (not full relative path) is deliberate:
    # every corte-preguntas-N/preguntas.json must be preserved too, not just the top-level
    # placeholder one, without having to list each corte folder here as it gets added.
    [string[]]$PreservedFiles = @("preguntas.json"),

    # If passed, only prints the actions without running them
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$statusPath = Join-Path $InputsPath "estado.json"
if (-not (Test-Path $statusPath)) {
    throw "Missing $statusPath. Run ./scripts/crear-repos-trimestre.ps1 first"
}

$repos = Get-Content $statusPath -Raw | ConvertFrom-Json
if (-not $repos) {
    throw "$statusPath has no active repos"
}

if (-not (Test-Path $RepoTemplatePath)) {
    throw "Missing template folder: $RepoTemplatePath"
}

if (-not (Test-Path $LocalDestination)) {
    New-Item -ItemType Directory -Path $LocalDestination | Out-Null
}

$templateRoot = (Resolve-Path $RepoTemplatePath).Path
$templateFiles = Get-ChildItem -Path $templateRoot -Recurse -File

foreach ($repo in $repos) {

    if ($repo.status -ne "active") {
        Write-Host "=== $($repo.repo) === (skipped, status: $($repo.status))" -ForegroundColor DarkGray
        continue
    }

    Write-Host "=== $($repo.repo) ===" -ForegroundColor Cyan
    $localPath = Join-Path $LocalDestination $repo.repo

    try {
        if ($DryRun) {
            Write-Host "  [DRY-RUN] clone/update $($repo.owner)/$($repo.repo) -> $localPath"
        }
        elseif (-not (Test-Path (Join-Path $localPath ".git"))) {
            gh repo clone "$($repo.owner)/$($repo.repo)" $localPath
            if (-not $?) { throw "could not clone" }
        }
        else {
            Push-Location $localPath
            try { git pull } finally { Pop-Location }
        }

        foreach ($file in $templateFiles) {
            $relativePath = $file.FullName.Substring($templateRoot.Length + 1)
            $destinationFile = Join-Path $localPath $relativePath

            $fileName = Split-Path $relativePath -Leaf
            if ($PreservedFiles -contains $fileName -and (Test-Path $destinationFile)) {
                Write-Host "  Preserving $relativePath (not overwritten)"
                continue
            }

            if ($DryRun) {
                Write-Host "  [DRY-RUN] copy $relativePath"
                continue
            }

            $destinationFolder = Split-Path $destinationFile -Parent
            if (-not (Test-Path $destinationFolder)) {
                New-Item -ItemType Directory -Path $destinationFolder -Force | Out-Null
            }
            Copy-Item -Path $file.FullName -Destination $destinationFile -Force
        }

        if ($DryRun) { continue }

        Push-Location $localPath
        try {
            git add -A
            $changes = git status --porcelain
            if ($changes) {
                git commit -m $CommitMessage
                git push
                Write-Host "  Updated and pushed"
            }
            else {
                Write-Host "  No changes against the template, not pushing"
            }
        }
        finally {
            Pop-Location
        }
    }
    catch {
        Write-Warning "  Failed updating $($repo.repo): $_"
    }
}
