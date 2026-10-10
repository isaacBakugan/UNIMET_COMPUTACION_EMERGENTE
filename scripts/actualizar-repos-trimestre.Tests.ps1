<#
    Guards the project's own invariant (see root CLAUDE.md): "preguntas.json nunca se
    sobreescribe una vez que el equipo lo llenó". The template has TWO preguntas.json files
    (repo-template/preguntas.json and repo-template/corte-preguntas-1/preguntas.json, the
    one that actually gets graded), and future corte-preguntas-N folders will add more.

    -DryRun never touches git/gh (clone/pull/push are all skipped before the per-file loop
    runs), so this exercises the real preservation logic with no network or git fixtures
    needed. Write-Host goes to the Information stream in PS5+, captured here via 6>&1.
#>

$scriptPath = Join-Path $PSScriptRoot "actualizar-repos-trimestre.ps1"

Describe "actualizar-repos-trimestre: preguntas.json preservation" {

    BeforeEach {
        $inputsPath = Join-Path $TestDrive "trimestre-actual"
        New-Item -ItemType Directory -Path $inputsPath -Force | Out-Null
        Set-Content -Path (Join-Path $inputsPath "estado.json") -Value @'
[{"team":"grupo-control","repo":"grupo-control-test","owner":"IsaacBakugan","url":"x","term":"test","delegates":["x"],"createdAt":"x","status":"active"}]
'@

        # Minimal template fixture with a nested preguntas.json, mirroring the real
        # repo-template/corte-preguntas-1/preguntas.json shape.
        $templatePath = Join-Path $TestDrive "repo-template"
        New-Item -ItemType Directory -Path (Join-Path $templatePath "corte-preguntas-1") -Force | Out-Null
        Set-Content -Path (Join-Path $templatePath "preguntas.json") -Value '{"placeholder":"root"}'
        Set-Content -Path (Join-Path $templatePath "corte-preguntas-1\preguntas.json") -Value '{"placeholder":"corte-1"}'

        $localDestination = Join-Path $TestDrive "local-repos"
        $teamRepoPath = Join-Path $localDestination "grupo-control-test"
        New-Item -ItemType Directory -Path (Join-Path $teamRepoPath "corte-preguntas-1") -Force | Out-Null

        # The team's real, already-graded answers, distinct from the template placeholder.
        Set-Content -Path (Join-Path $teamRepoPath "corte-preguntas-1\preguntas.json") -Value '{"team":"grupo-control","questions":["real answer"]}'
    }

    It "preserves the nested corte-preguntas-1/preguntas.json, not just the root one" {
        $output = & $scriptPath -InputsPath $inputsPath -RepoTemplatePath $templatePath `
            -LocalDestination $localDestination -DryRun 6>&1 | Out-String

        $nestedPath = Join-Path "corte-preguntas-1" "preguntas.json"
        $output | Should Match "Preserving $([regex]::Escape($nestedPath))"
        $output | Should Not Match "\[DRY-RUN\] copy $([regex]::Escape($nestedPath))"
    }

    It "does not touch preguntas.json or student code files on a real (non-dry-run) sync" {
        # Real git repo, no remote: "git pull"/"git push" fail loud on the console but are
        # non-terminating native-command failures (unredirected, so PS5.1 does not turn
        # them into exceptions), which is enough to exercise the actual Copy-Item pass.
        git init $teamRepoPath *> $null

        $preguntasPath = Join-Path $teamRepoPath "corte-preguntas-1\preguntas.json"
        $codePath = Join-Path $teamRepoPath "tarea-1-codigo\perceptron.py"
        New-Item -ItemType Directory -Path (Split-Path $codePath) -Force | Out-Null
        # perceptron.py never ships in the template (repo-template/tarea-1-codigo has no
        # such file — students write it from scratch), so it must never be a sync target.
        Set-Content -Path $codePath -Value "# student implementation, do not overwrite`nprint('perceptron')"

        $preguntasBefore = Get-Content $preguntasPath -Raw
        $codeBefore = Get-Content $codePath -Raw

        & $scriptPath -InputsPath $inputsPath -RepoTemplatePath $templatePath `
            -LocalDestination $localDestination 6>&1 | Out-Null

        (Get-Content $preguntasPath -Raw) | Should Be $preguntasBefore
        (Get-Content $codePath -Raw) | Should Be $codeBefore
    }
}

<#
    Guards the sync against a team rewriting its history. `git pull` on a diverged clone used to
    leave it half-merged with conflicts in the students' preguntas.json. Real git, no network:
    a bare "origin", the clone the script works on ("local") and the team's own clone ("student").
#>
Describe "actualizar-repos-trimestre: history divergence (force push)" {

    BeforeEach {
        $env:GIT_AUTHOR_NAME = "test"; $env:GIT_AUTHOR_EMAIL = "test@example.com"
        $env:GIT_COMMITTER_NAME = "test"; $env:GIT_COMMITTER_EMAIL = "test@example.com"

        $originPath = Join-Path $TestDrive "origin.git"
        $studentPath = Join-Path $TestDrive "student"
        $localDestination = Join-Path $TestDrive "local-repos"
        $localPath = Join-Path $localDestination "team-test"
        New-Item -ItemType Directory -Path $localDestination -Force | Out-Null

        git init --bare $originPath *> $null
        git clone $originPath $studentPath *> $null
        git -C $studentPath checkout -B main *> $null
        Set-Content -Path (Join-Path $studentPath "answers.txt") -Value "base"
        git -C $studentPath add -A *> $null
        git -C $studentPath commit -m "base" *> $null
        git -C $studentPath push -u origin main *> $null
        git -C $originPath symbolic-ref HEAD refs/heads/main *> $null
        git clone $originPath $localPath *> $null

        $inputsPath = Join-Path $TestDrive "trimestre-actual"
        New-Item -ItemType Directory -Path $inputsPath -Force | Out-Null
        Set-Content -Path (Join-Path $inputsPath "estado.json") -Value @'
[{"team":"team-test","repo":"team-test","owner":"x","url":"x","term":"test","delegates":["x"],"createdAt":"x","status":"active"}]
'@
        $templatePath = Join-Path $TestDrive "repo-template"
        New-Item -ItemType Directory -Path $templatePath -Force | Out-Null
        Set-Content -Path (Join-Path $templatePath "README.md") -Value "template"
    }

    # Local: base -> "student work" (only here). Origin: base -> "rewritten history".
    function New-Divergence {
        Set-Content -Path (Join-Path $localPath "mine.txt") -Value "mine"
        git -C $localPath add -A *> $null
        git -C $localPath commit -m "corte preguntas 1" *> $null
        Set-Content -Path (Join-Path $studentPath "theirs.txt") -Value "theirs"
        git -C $studentPath add -A *> $null
        git -C $studentPath commit -m "rewritten history" *> $null
        git -C $studentPath push origin main *> $null
    }

    It "skips a diverged repo untouched: no merge, no push, names the commits at risk" {
        New-Divergence
        $localHeadBefore = git -C $localPath rev-parse HEAD
        $originHeadBefore = git -C $originPath rev-parse main

        $output = & $scriptPath -InputsPath $inputsPath -RepoTemplatePath $templatePath `
            -LocalDestination $localDestination 3>&1 6>&1 | Out-String

        $output | Should Match "diverged from origin"
        $output | Should Match "corte preguntas 1"
        $output | Should Match "-ResolveDivergence"
        (git -C $localPath rev-parse HEAD) | Should Be $localHeadBefore
        (Test-Path (Join-Path $localPath ".git\MERGE_HEAD")) | Should Be $false
        (git -C $originPath rev-parse main) | Should Be $originHeadBefore
    }

    It "with -ResolveDivergence backs up the local commits, aligns to origin and pushes the sync" {
        New-Divergence

        & $scriptPath -InputsPath $inputsPath -RepoTemplatePath $templatePath `
            -LocalDestination $localDestination -ResolveDivergence 3>&1 6>&1 | Out-Null

        $backup = @(git -C $localPath branch --list "backup/diverged-*" --format "%(refname:short)")
        $backup.Count | Should Be 1
        (git -C $localPath log $backup[0] --format=%s) -contains "corte preguntas 1" | Should Be $true

        $originLog = git -C $originPath log main --format=%s
        $originLog -contains "rewritten history" | Should Be $true
        $originLog -contains "corte preguntas 1" | Should Be $false
        $originLog -contains "infra: Se actualiza el template del repo de grupo" | Should Be $true
    }

    It "fast-forwards when the team only pushed new commits, without a merge commit" {
        Set-Content -Path (Join-Path $studentPath "theirs.txt") -Value "theirs"
        git -C $studentPath add -A *> $null
        git -C $studentPath commit -m "student push" *> $null
        git -C $studentPath push origin main *> $null

        & $scriptPath -InputsPath $inputsPath -RepoTemplatePath $templatePath `
            -LocalDestination $localDestination 3>&1 6>&1 | Out-Null

        (Test-Path (Join-Path $localPath "theirs.txt")) | Should Be $true
        @(git -C $localPath rev-list --merges HEAD).Count | Should Be 0
    }
}
