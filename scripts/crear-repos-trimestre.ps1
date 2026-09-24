<#
    Creates the term's team repos (public, under the personal GitHub account, NOT under
    an organization), pushes /repo-template into each one, and adds each team's DELEGATE
    as a collaborator with "editor" permission (push).

    Leaves trimestre-actual/estado.json with the term's active repos (team, repo, owner,
    url, delegates, creation date). scripts/actualizar-repos-trimestre.ps1 reads that file
    to know which repos to push template updates to.

    Student GitHub usernames aren't known ahead of time, so the whole course isn't
    invited: only the team's delegate gets invited, and the delegate is the one who adds
    the rest of the team directly from GitHub (Settings > Collaborators), because they
    actually know their teammates.

    Idempotent:
      - If the repo already exists, it is NOT recreated and the template is NOT pushed
        again (so it doesn't clobber work the team already pushed). Only the delegate
        invitation is (re)processed.
      - Inviting a user who is already a collaborator (or already has a pending
        invitation) doesn't fail, the GitHub API just no-ops.

    Inputs (folder $InputsPath, "trimestre-actual" by default): a single "equipos.json"
    file with this contract:
      [
        { "team": "grupo-lecturas-1", "delegates": ["delegate-username-1"] },
        { "team": "grupo-lecturas-2", "delegates": ["delegate-username-2"] }
      ]
    A team with "delegates": [] is skipped (warning only, no repo created, no invite).

    Requires: gh CLI authenticated (gh auth status) with permission to create public
    repos and invite collaborators.
#>

param(
    # TODO: current term, e.g. "2026-2"
    [Parameter(Mandatory = $true)]
    [string]$Term,

    # Folder with equipos.json and (once this has run) estado.json
    [string]$InputsPath = "$PSScriptRoot/../trimestre-actual",

    # Owner of the repos. Empty = the user authenticated in gh (never an organization)
    [string]$Owner,

    # Guard against creating repos under the wrong gh-authenticated account (e.g. a
    # company account instead of the personal one this course's repos live under).
    # Pass -ExpectedOwner "" to bypass intentionally.
    [string]$ExpectedOwner = "IsaacBakugan",

    # Permission granted on invite: pull | triage | push | maintain | admin
    # "push" is the equivalent of "editor"
    [string]$Permission = "push",

    # Local folder where newly created repos get cloned
    [string]$LocalDestination = "$PSScriptRoot/../.repos-trimestre-$Term",

    # Folder with the template pushed into every new repo (schemas, tests, guide)
    [string]$TemplatesPath = "$PSScriptRoot/../repo-template",

    # If passed, only prints the actions without running them
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$teamsFile = Join-Path $InputsPath "equipos.json"
if (-not (Test-Path $teamsFile)) {
    throw "Missing $teamsFile"
}

if (-not $Owner) {
    $Owner = gh api user --jq ".login"
    if (-not $Owner) { throw "Could not resolve the user authenticated in gh. Run 'gh auth status'." }
}

if ($ExpectedOwner -and $Owner -ne $ExpectedOwner) {
    throw "Resolved owner '$Owner' is not the expected '$ExpectedOwner'. gh is probably authenticated as the wrong account (run 'gh auth switch' or 'gh auth status'). Pass -ExpectedOwner `"`" to bypass intentionally."
}

$teams = Get-Content $teamsFile -Raw | ConvertFrom-Json
if (-not $teams) {
    throw "$teamsFile has no teams"
}

if (-not (Test-Path $LocalDestination)) {
    New-Item -ItemType Directory -Path $LocalDestination | Out-Null
}

$statusPath = Join-Path $InputsPath "estado.json"
$previousStatus = @{}
if (Test-Path $statusPath) {
    $raw = Get-Content $statusPath -Raw | ConvertFrom-Json
    foreach ($item in $raw) { $previousStatus[$item.repo] = $item }
}

$report = @()
$newStatus = @()

foreach ($teamDef in $teams) {

    $teamName = $teamDef.team
    if (-not $teamName) {
        Write-Warning "  Entry with no 'team' field in $teamsFile, skipping"
        continue
    }

    # TODO: adjust the repo naming convention if "<team>-<term>" doesn't apply
    $repoName = "$teamName-$Term"
    $localPath = Join-Path $LocalDestination $repoName
    $invitationLink = "https://github.com/$Owner/$repoName/invitations"

    Write-Host "=== $repoName ===" -ForegroundColor Cyan

    $delegates = @($teamDef.delegates) |
        Where-Object { $_ } |
        ForEach-Object { $_.ToString().Trim() } |
        Where-Object { $_ -and -not $_.StartsWith("#") }

    if (-not $delegates) {
        Write-Warning "  $teamName has no delegates in equipos.json, skipping"
        continue
    }

    # --- Repo creation (idempotent) ---
    $exists = $false
    if (-not $DryRun) {
        # gh writes to stderr when the repo doesn't exist yet (the expected first-run case).
        # With $ErrorActionPreference = "Stop", redirecting a native command's stderr on
        # PS 5.1 turns that into a terminating NativeCommandError instead of a checkable
        # exit code, so ErrorAction is relaxed just for this call and $LASTEXITCODE is used.
        $previousEap = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        gh repo view "$Owner/$repoName" --json name *> $null
        $exists = ($LASTEXITCODE -eq 0)
        $ErrorActionPreference = $previousEap
    }

    if ($exists) {
        Write-Host "  Repo already exists, skipping creation and template push"
    }
    elseif ($DryRun) {
        Write-Host "  [DRY-RUN] gh repo create $Owner/$repoName --public --clone -> $localPath"
    }
    else {
        gh repo create "$Owner/$repoName" --public --clone --confirm
        if (-not $?) { throw "Failed to create repo $repoName" }

        Move-Item -Path (Join-Path (Get-Location) $repoName) -Destination $localPath -Force

        Copy-Item -Path "$TemplatesPath/*" -Destination $localPath -Recurse -Force

        Push-Location $localPath
        try {
            git add -A
            git commit -m "[INFRA] Se agrega el template inicial del trimestre $Term"
            git push
        }
        finally {
            Pop-Location
        }
    }

    # --- Delegate invitation(s) (idempotent) ---
    foreach ($delegate in $delegates) {
        if ($DryRun) {
            Write-Host "  [DRY-RUN] gh api -X PUT repos/$Owner/$repoName/collaborators/$delegate -f permission=$Permission"
        }
        else {
            try {
                gh api -X PUT "repos/$Owner/$repoName/collaborators/$delegate" -f permission=$Permission *> $null
                Write-Host "  Delegate invited: $delegate"
            }
            catch {
                Write-Warning "  Could not invite $delegate to $repoName : $_"
            }
        }

        $report += [PSCustomObject]@{
            Team           = $teamName
            Repo           = $repoName
            Delegate       = $delegate
            InvitationLink = $invitationLink
        }
    }

    if (-not $DryRun) {
        $createdAt = if ($previousStatus.ContainsKey($repoName)) { $previousStatus[$repoName].createdAt } else { (Get-Date).ToUniversalTime().ToString("o") }

        $newStatus += [PSCustomObject]@{
            team      = $teamName
            repo      = $repoName
            owner     = $Owner
            url       = "https://github.com/$Owner/$repoName"
            term      = $Term
            delegates = $delegates
            createdAt = $createdAt
            status    = "active"
        }
    }
}

if (-not $DryRun) {
    $newStatus | ConvertTo-Json -Depth 4 | Set-Content -Path $statusPath -Encoding UTF8
    Write-Host ""
    Write-Host "Term status saved to: $statusPath" -ForegroundColor Green
}

$csvPath = Join-Path $LocalDestination "invitations-$Term.csv"
$report | Export-Csv -Path $csvPath -NoTypeInformation -Encoding UTF8

Write-Host ""
Write-Host "Invitation report saved to: $csvPath" -ForegroundColor Green
$report | Format-Table -AutoSize
