<#
    Crea los repos de grupo de un trimestre (públicos, bajo la cuenta personal de GitHub,
    NO bajo una organización), les empuja el contenido de /repo-template y agrega como
    colaborador con permiso "editor" (push) al DELEGADO de cada equipo.

    Deja trimestre-actual/estado.json con los repos activos del trimestre (equipo, repo,
    owner, url, delegados, fecha de creación). Ese archivo es el que usa
    scripts/actualizar-repos-trimestre.ps1 para saber a qué repos pushear cambios de template.

    No se conocen de antemano los usernames de todos los estudiantes, así que no se invita
    al curso completo: se invita solo al delegado de cada equipo, y es el delegado quien
    agrega al resto de su equipo directamente desde GitHub (Settings > Collaborators),
    porque él sí conoce a sus compañeros.

    Idempotente:
      - Si el repo ya existe, NO se recrea ni se pushea el template (para no pisar el
        trabajo que ya haya subido el equipo). Solo se procesa la invitación del delegado.
      - Invitar a un usuario que ya es colaborador (o ya tiene invitación pendiente) no falla,
        la API de GitHub simplemente no hace nada nuevo.

    Insumos (carpeta $InsumosPath, por defecto "trimestre-actual"): un solo archivo
    "equipos.json" con el contrato:
      [
        { "equipo": "grupo-lecturas-1", "delegados": ["username-delegado-1"] },
        { "equipo": "grupo-lecturas-2", "delegados": ["username-delegado-2"] }
      ]
    Un equipo con "delegados": [] se salta (se avisa por warning, no crea repo ni invita).

    Requiere: gh CLI autenticado (gh auth status) con permiso para crear repos públicos
    e invitar colaboradores.
#>

param(
    # TODO: trimestre en curso, ej. "2026-2"
    [Parameter(Mandatory = $true)]
    [string]$Trimestre,

    # Carpeta con equipos.json y (una vez corrido) estado.json
    [string]$InsumosPath = "$PSScriptRoot/../trimestre-actual",

    # Dueño de los repos. Vacío = usuario autenticado en gh (nunca una organización)
    [string]$Owner,

    # Permiso a otorgar en la invitación: pull | triage | push | maintain | admin
    # "push" es el equivalente de "editor"
    [string]$Permission = "push",

    # Carpeta local donde se clonan los repos recién creados
    [string]$DestinoLocal = "$PSScriptRoot/../.repos-trimestre-$Trimestre",

    # Carpeta con el template a empujar a cada repo nuevo (esquemas, tests, guía)
    [string]$TemplatesPath = "$PSScriptRoot/../repo-template",

    # Si se pasa, solo imprime las acciones sin ejecutarlas
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$equiposPath = Join-Path $InsumosPath "equipos.json"
if (-not (Test-Path $equiposPath)) {
    throw "No existe $equiposPath"
}

if (-not $Owner) {
    $Owner = gh api user --jq ".login"
    if (-not $Owner) { throw "No se pudo resolver el usuario autenticado en gh. Corre 'gh auth status'." }
}

$equipos = Get-Content $equiposPath -Raw | ConvertFrom-Json
if (-not $equipos) {
    throw "$equiposPath no tiene equipos"
}

if (-not (Test-Path $DestinoLocal)) {
    New-Item -ItemType Directory -Path $DestinoLocal | Out-Null
}

$estadoPath = Join-Path $InsumosPath "estado.json"
$estadoPrevio = @{}
if (Test-Path $estadoPath) {
    $crudo = Get-Content $estadoPath -Raw | ConvertFrom-Json
    foreach ($item in $crudo) { $estadoPrevio[$item.repo] = $item }
}

$reporte = @()
$estadoNuevo = @()

foreach ($equipoDef in $equipos) {

    $grupo = $equipoDef.equipo
    if (-not $grupo) {
        Write-Warning "  Entrada sin campo 'equipo' en $equiposPath, se omite"
        continue
    }

    # TODO: ajustar convención de nombre de repo si no aplica "<equipo>-<trimestre>"
    $nombreRepo = "$grupo-$Trimestre"
    $rutaLocal = Join-Path $DestinoLocal $nombreRepo
    $linkInvitacion = "https://github.com/$Owner/$nombreRepo/invitations"

    Write-Host "=== $nombreRepo ===" -ForegroundColor Cyan

    $delegados = @($equipoDef.delegados) |
        Where-Object { $_ } |
        ForEach-Object { $_.ToString().Trim() } |
        Where-Object { $_ -and -not $_.StartsWith("#") }

    if (-not $delegados) {
        Write-Warning "  $grupo no tiene delegados en equipos.json, se omite"
        continue
    }

    # --- Creación del repo (idempotente) ---
    $existe = $false
    if (-not $DryRun) {
        gh repo view "$Owner/$nombreRepo" --json name *> $null
        $existe = $?
    }

    if ($existe) {
        Write-Host "  Repo ya existe, se omite creación y push del template"
    }
    elseif ($DryRun) {
        Write-Host "  [DRY-RUN] gh repo create $Owner/$nombreRepo --public --clone -> $rutaLocal"
    }
    else {
        gh repo create "$Owner/$nombreRepo" --public --clone --confirm
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

    # --- Invitación del/los delegado(s) (idempotente) ---
    foreach ($delegado in $delegados) {
        if ($DryRun) {
            Write-Host "  [DRY-RUN] gh api -X PUT repos/$Owner/$nombreRepo/collaborators/$delegado -f permission=$Permission"
        }
        else {
            try {
                gh api -X PUT "repos/$Owner/$nombreRepo/collaborators/$delegado" -f permission=$Permission *> $null
                Write-Host "  Delegado invitado: $delegado"
            }
            catch {
                Write-Warning "  No se pudo invitar a $delegado en $nombreRepo : $_"
            }
        }

        $reporte += [PSCustomObject]@{
            Equipo     = $grupo
            Repo       = $nombreRepo
            Delegado   = $delegado
            Invitacion = $linkInvitacion
        }
    }

    if (-not $DryRun) {
        $creadoEn = if ($estadoPrevio.ContainsKey($nombreRepo)) { $estadoPrevio[$nombreRepo].creadoEn } else { (Get-Date).ToUniversalTime().ToString("o") }

        $estadoNuevo += [PSCustomObject]@{
            equipo     = $grupo
            repo       = $nombreRepo
            owner      = $Owner
            url        = "https://github.com/$Owner/$nombreRepo"
            trimestre  = $Trimestre
            delegados  = $delegados
            creadoEn   = $creadoEn
            estado     = "activo"
        }
    }
}

if (-not $DryRun) {
    $estadoNuevo | ConvertTo-Json -Depth 4 | Set-Content -Path $estadoPath -Encoding UTF8
    Write-Host ""
    Write-Host "Estado del trimestre guardado en: $estadoPath" -ForegroundColor Green
}

$csvPath = Join-Path $DestinoLocal "invitaciones-$Trimestre.csv"
$reporte | Export-Csv -Path $csvPath -NoTypeInformation -Encoding UTF8

Write-Host ""
Write-Host "Reporte de invitaciones guardado en: $csvPath" -ForegroundColor Green
$reporte | Format-Table -AutoSize
