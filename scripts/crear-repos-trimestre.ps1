<#
    Crea los N repos de grupo de un trimestre (públicos, bajo la cuenta personal de GitHub,
    NO bajo una organización) y les empuja el contenido de /templates como setup inicial.

    Requiere: gh CLI autenticado (gh auth status) con permiso para crear repos públicos.
#>

param(
    # TODO: trimestre en curso, ej. "2026-2"
    [Parameter(Mandatory = $true)]
    [string]$Trimestre,

    # TODO: lista de grupos, ej. @("grupo-lecturas-1", "grupo-lecturas-2", "grupo-lecturas-3")
    [Parameter(Mandatory = $true)]
    [string[]]$Grupos,

    # Carpeta local donde se clonan los repos recién creados
    [string]$DestinoLocal = "$PSScriptRoot/../.repos-trimestre-$Trimestre",

    # Carpeta con el template a empujar a cada repo (esquemas, tests, guía)
    [string]$TemplatesPath = "$PSScriptRoot/../templates",

    # Si se pasa, solo imprime los comandos sin ejecutarlos
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $DestinoLocal)) {
    New-Item -ItemType Directory -Path $DestinoLocal | Out-Null
}

foreach ($grupo in $Grupos) {

    # TODO: ajustar convención de nombre de repo si no aplica "<grupo>-<trimestre>"
    $nombreRepo = "$grupo-$Trimestre"
    $rutaLocal = Join-Path $DestinoLocal $nombreRepo

    Write-Host "=== $nombreRepo ===" -ForegroundColor Cyan

    if ($DryRun) {
        Write-Host "[DRY-RUN] gh repo create $nombreRepo --public --clone -> $rutaLocal"
        continue
    }

    # Crea el repo bajo la cuenta autenticada (sin --org => no queda en ninguna organización)
    gh repo create $nombreRepo --public --clone --confirm
    if (-not $?) { throw "Fallo al crear el repo $nombreRepo" }

    Move-Item -Path (Join-Path (Get-Location) $nombreRepo) -Destination $rutaLocal -Force

    Copy-Item -Path "$TemplatesPath/*" -Destination $rutaLocal -Recurse -Force

    Push-Location $rutaLocal
    try {
        git add -A
        git commit -m "[INFRA] Se agrega el template inicial del trimestre $Trimestre"
        git push
    }
    finally {
        Pop-Location
    }
}
