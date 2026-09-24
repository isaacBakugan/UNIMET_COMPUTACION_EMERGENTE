<#
    Pushea cambios de /repo-template (tests nuevos, guías, esquemas) a todos los repos
    activos del trimestre actual, sin pisar las respuestas ya subidas por los estudiantes.

    Fuente de verdad de "qué repos están activos": trimestre-actual/estado.json, que deja
    escrito scripts/crear-repos-trimestre.ps1. Si no existe, corre ese script primero.

    Se ejecuta local (gh + git), no vía GitHub Action: reusa la sesión de gh ya autenticada
    en esta máquina en vez de guardar un token de alcance amplio como secret en el repo
    central solo para pushear a N repos ajenos.

    $PreservarArchivos declara qué archivos del template NUNCA se sobreescriben si ya
    existen en el repo del equipo (por defecto, preguntas.json: son las respuestas reales
    del equipo, no el placeholder del template).

    Idempotente: si el diff contra el template está vacío, no commitea ni pushea.
#>

param(
    # Carpeta con un subdirectorio por equipo, la misma que usa crear-repos-trimestre.ps1
    [string]$InsumosPath = "$PSScriptRoot/../trimestre-actual",

    # Carpeta con el template a sincronizar
    [string]$RepoTemplatePath = "$PSScriptRoot/../repo-template",

    # Carpeta local donde se clonan/actualizan los repos de los equipos
    [string]$DestinoLocal = "$PSScriptRoot/../.repos-trimestre-actual",

    [string]$Mensaje = "[INFRA] Se actualiza el template del repo de grupo",

    # Archivos del template que jamás se sobreescriben si ya existen en el repo destino
    [string[]]$PreservarArchivos = @("preguntas.json"),

    # Si se pasa, solo imprime las acciones sin ejecutarlas
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$estadoPath = Join-Path $InsumosPath "estado.json"
if (-not (Test-Path $estadoPath)) {
    throw "No existe $estadoPath. Corre primero ./scripts/crear-repos-trimestre.ps1"
}

$repos = Get-Content $estadoPath -Raw | ConvertFrom-Json
if (-not $repos) {
    throw "$estadoPath no tiene repos activos"
}

if (-not (Test-Path $RepoTemplatePath)) {
    throw "No existe la carpeta de template: $RepoTemplatePath"
}

if (-not (Test-Path $DestinoLocal)) {
    New-Item -ItemType Directory -Path $DestinoLocal | Out-Null
}

$raizTemplate = (Resolve-Path $RepoTemplatePath).Path
$archivosTemplate = Get-ChildItem -Path $raizTemplate -Recurse -File

foreach ($r in $repos) {

    if ($r.estado -ne "activo") {
        Write-Host "=== $($r.repo) === (omitido, estado: $($r.estado))" -ForegroundColor DarkGray
        continue
    }

    Write-Host "=== $($r.repo) ===" -ForegroundColor Cyan
    $rutaLocal = Join-Path $DestinoLocal $r.repo

    try {
        if ($DryRun) {
            Write-Host "  [DRY-RUN] clonar/actualizar $($r.owner)/$($r.repo) -> $rutaLocal"
        }
        elseif (-not (Test-Path (Join-Path $rutaLocal ".git"))) {
            gh repo clone "$($r.owner)/$($r.repo)" $rutaLocal
            if (-not $?) { throw "no se pudo clonar" }
        }
        else {
            Push-Location $rutaLocal
            try { git pull } finally { Pop-Location }
        }

        foreach ($archivo in $archivosTemplate) {
            $relativo = $archivo.FullName.Substring($raizTemplate.Length + 1)
            $destinoArchivo = Join-Path $rutaLocal $relativo

            if ($PreservarArchivos -contains $relativo -and (Test-Path $destinoArchivo)) {
                Write-Host "  Se preserva $relativo (no se sobreescribe)"
                continue
            }

            if ($DryRun) {
                Write-Host "  [DRY-RUN] copiar $relativo"
                continue
            }

            $destinoCarpeta = Split-Path $destinoArchivo -Parent
            if (-not (Test-Path $destinoCarpeta)) {
                New-Item -ItemType Directory -Path $destinoCarpeta -Force | Out-Null
            }
            Copy-Item -Path $archivo.FullName -Destination $destinoArchivo -Force
        }

        if ($DryRun) { continue }

        Push-Location $rutaLocal
        try {
            git add -A
            $cambios = git status --porcelain
            if ($cambios) {
                git commit -m $Mensaje
                git push
                Write-Host "  Actualizado y pusheado"
            }
            else {
                Write-Host "  Sin cambios contra el template, no se pushea"
            }
        }
        finally {
            Pop-Location
        }
    }
    catch {
        Write-Warning "  Fallo actualizando $($r.repo): $_"
    }
}
