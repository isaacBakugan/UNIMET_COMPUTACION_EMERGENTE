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
