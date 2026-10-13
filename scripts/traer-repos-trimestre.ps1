<#
    Brings the team repos of the current term to local, so the code students pushed can be read
    and graded. Read-only with respect to GitHub: only clone / fetch, nothing is ever pushed.

    Source of truth for "which repos": trimestre-actual/estado.json (written by
    crear-repos-trimestre.ps1). The repos are public, so no gh session is needed.

    Result: <repo-root>/.repos-trimestre-<term>/<Team>-<term>/ with ALL the assignments the team
    has pushed so far (a clone brings every folder and the whole history). This is the folder
    that correcciones/calificador.py reads.

    Idempotent: missing -> clone; existing -> fetch + fast-forward. Never `reset --hard`: if a
    team force-pushed (diverged history) or the clone has local edits, that repo is reported as
    FAILED and left untouched instead of silently rewritten.

    Usage:
        ./scripts/traer-repos-trimestre.ps1
        ./scripts/traer-repos-trimestre.ps1 -Team LUMON,areperos
#>

param(
    [string]$StatusPath = "$PSScriptRoot/../trimestre-actual/estado.json",

    # Default: .repos-trimestre-<term> at the repo root (git-ignored)
    [string]$Destination,

    # Only these teams (by name). Empty = all active teams
    [string[]]$Team = @(),

    # Teams that are not students (the teacher's control repo)
    [string[]]$ExcludeTeams = @("grupo-control")
)

$ErrorActionPreference = "Stop"

# Runs git and returns its exit code + output. Needed because in Windows PowerShell 5.1 with
# $ErrorActionPreference = "Stop", any stderr line from git (clone progress) is raised as an error.
function Invoke-Git {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & git @args 2>&1 | ForEach-Object { "$_" }
        return [pscustomobject]@{ ExitCode = $LASTEXITCODE; Output = ($output -join "`n") }
    }
    finally { $ErrorActionPreference = $previous }
}

if (-not (Test-Path $StatusPath)) {
    throw "Missing $StatusPath. Run ./scripts/crear-repos-trimestre.ps1 first"
}

# Assign first, then pipe: in PS 5.1 `ConvertFrom-Json | ...` hands the whole array over as ONE
# object, so Where-Object would filter the array instead of each team.
$allTeams = Get-Content $StatusPath -Raw | ConvertFrom-Json
$repos = @($allTeams | Where-Object { $_.status -eq "active" -and $ExcludeTeams -notcontains $_.team })
if ($Team.Count -gt 0) {
    $repos = @($repos | Where-Object { $Team -contains $_.team })
}
if (-not $repos) { throw "No active teams to fetch (check -Team / $StatusPath)" }

$terms = @($repos | ForEach-Object { $_.term } | Select-Object -Unique)
if ($terms.Count -ne 1) { throw "Expected a single term in $StatusPath, found: $($terms -join ', ')" }

if (-not $Destination) { $Destination = Join-Path "$PSScriptRoot/.." ".repos-trimestre-$($terms[0])" }
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
$Destination = (Resolve-Path $Destination).Path

$failed = 0
foreach ($repo in $repos) {
    $localPath = Join-Path $Destination $repo.repo
    try {
        if (-not (Test-Path (Join-Path $localPath ".git"))) {
            $result = Invoke-Git clone $repo.url $localPath
            $action = "cloned"
            $null = Invoke-Git -C $localPath remote set-head origin --auto
        }
        else {
            $null = Invoke-Git -C $localPath remote set-url origin $repo.url
            $result = Invoke-Git -C $localPath fetch --prune origin
            if ($result.ExitCode -eq 0) {
                # origin/HEAD instead of @{u}: clones made by crear-repos-trimestre.ps1 have no upstream
                $null = Invoke-Git -C $localPath remote set-head origin --auto
                $result = Invoke-Git -C $localPath merge --ff-only origin/HEAD
            }
            $action = "updated"
        }
        if ($result.ExitCode -ne 0) { throw $result.Output }

        $count = (Invoke-Git -C $localPath rev-list --count HEAD).Output
        $last = (Invoke-Git -C $localPath log -1 --format="%cd %an" --date=format:"%Y-%m-%d %H:%M").Output
        Write-Host ("{0,-12} {1,-8} {2,3} commits  last: {3}" -f $repo.team, $action, $count, $last)
    }
    catch {
        $failed++
        Write-Warning "$($repo.team): FAILED, clone left untouched. $_"
    }
}

Write-Host "`nClones in: $Destination ($($repos.Count - $failed)/$($repos.Count) ok)"
if ($failed -gt 0) { exit 1 }
