<#
.SYNOPSIS
    Trae del Pi a la PC los registros de las ultimas corridas (y el video).
.DESCRIPTION
    Se corre desde la PC (PowerShell), con el Pi prendido. Copia a la carpeta
    logs\ del proyecto el CSV y el JSON de las ultimas corridas, y con -Video
    tambien el video (el .mp4 si `demo.sh grabar` llego a convertirlo, o el
    .avi original).
.EXAMPLE
    .\scripts_pi\traer_corrida.cmd                 # la ultima corrida
    .\scripts_pi\traer_corrida.cmd -Video          # la ultima, con su video
    .\scripts_pi\traer_corrida.cmd -Cuantas 10     # las ultimas diez
    .\scripts_pi\traer_corrida.cmd -Ip 192.168.43.57 -Video
.NOTES
    Para analizar lo traido, en la PC:
        cd src ; python analizar_corrida.py ..\logs\corrida_*.csv
#>
param(
    [int]$Cuantas = 1,
    [switch]$Video,
    [string]$Ip = ""
)

$raiz    = Split-Path -Parent $PSScriptRoot
$destino = Join-Path $raiz "logs"
$clave   = Join-Path $env:USERPROFILE ".ssh\id_ed25519_pi"
$usuario = "admin"

$sshOpts = @("-o", "ConnectTimeout=10", "-o", "HostKeyAlias=pi-mb.local",
             "-o", "StrictHostKeyChecking=accept-new")
if (Test-Path $clave) { $sshOpts = @("-i", $clave) + $sshOpts }

if ($Ip) { $equipo = & (Join-Path $PSScriptRoot "entrar.ps1") -SoloBuscar -Ip $Ip }
else     { $equipo = & (Join-Path $PSScriptRoot "entrar.ps1") -SoloBuscar }
if (-not $equipo) { exit 1 }
$equipo = ($equipo | Select-Object -Last 1).ToString().Trim()
Write-Host "Pi en $equipo" -ForegroundColor Green

if (-not (Test-Path $destino)) { $null = New-Item -ItemType Directory -Path $destino }

$lista = & ssh @sshOpts "$usuario@$equipo" "ls -t TPF/logs/corrida_*.csv 2>/dev/null | head -$Cuantas"
if (-not $lista) {
    Write-Host "No hay corridas registradas en el Pi (~/TPF/logs/)." -ForegroundColor Yellow
    exit 1
}

$copiados = 0
$fallidos = 0
foreach ($csv in @($lista)) {
    $base = $csv.Trim() -replace "\.csv$", ""
    $archivos = @("$base.csv", "$base.json")
    if ($Video) {
        # El .mp4 primero: `ls a.mp4 a.avi | head -1` ordena alfabeticamente y
        # devolvia siempre el .avi, ocho veces mas pesado (2026-10-02).
        $hay = & ssh @sshOpts "$usuario@$equipo" "ls $base.mp4 2>/dev/null || ls $base.avi 2>/dev/null"
        if ($hay) { $archivos += ($hay | Select-Object -First 1).ToString().Trim() }
        else { Write-Host "   $(Split-Path $base -Leaf): esa corrida no tiene video" -ForegroundColor DarkGray }
    }
    foreach ($a in $archivos) {
        # $destino SIN barra final: con "$destino\" la barra escapa la comilla
        # de cierre y, como la ruta tiene espacios, scp recibia un nombre roto
        # y no copiaba nada (2026-10-02).
        & scp @sshOpts "${usuario}@${equipo}:$a" $destino | Out-Null
        if ($LASTEXITCODE -eq 0) { $copiados++; Write-Host "   copiado: $(Split-Path $a -Leaf)" }
        else { $fallidos++; Write-Host "   NO se pudo copiar: $(Split-Path $a -Leaf)" -ForegroundColor Yellow }
    }
}

if ($copiados -eq 0) {
    Write-Host "`nNo se copio nada." -ForegroundColor Yellow
    exit 1
}
Write-Host "`nQuedaron en $destino ($copiados archivos)" -ForegroundColor Green
if ($fallidos -gt 0) { Write-Host "Ojo: $fallidos no se pudieron copiar." -ForegroundColor Yellow }
Write-Host "Para analizarlas:  cd src ; python analizar_corrida.py ..\logs\corrida_*.csv"
