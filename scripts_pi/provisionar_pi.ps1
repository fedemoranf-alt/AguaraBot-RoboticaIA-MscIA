<#
.SYNOPSIS
    Copia el codigo del TPF al Pi y corre el inventario del Paso 11.5.
.DESCRIPTION
    Se corre desde la PC (PowerShell), una vez que el Pi arranca y responde
    por SSH. Idempotente: se puede repetir cuando se cambia algo en src/.
.EXAMPLE
    .\scripts_pi\provisionar_pi.cmd
    .\scripts_pi\provisionar_pi.cmd -Equipo admin@192.168.0.42
.NOTES
    El Pi se grabo el 2026-09-04 con hostname 'pi-MB' y usuario 'admin'.

    Sin -Equipo, busca el Pi con entrar.ps1 (nombre, ultima IP conocida, tabla
    ARP). Desde el 2026-10-01 usa la clave id_ed25519_pi tambien cuando se
    entra por IP: antes solo la tomaba por nombre, y por IP pedia contrasena.
#>
param(
    [string]$Equipo = "",
    [switch]$SoloInventario
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot

function Paso($t) { Write-Host "`n== $t" -ForegroundColor Cyan }

if (-not $Equipo) {
    Paso "Buscando el Pi en la red"
    $ErrorActionPreference = "Continue"
    $ip = & (Join-Path $PSScriptRoot "entrar.ps1") -SoloBuscar
    $ErrorActionPreference = "Stop"
    if (-not $ip) { exit 1 }
    $Equipo = "admin@" + ($ip | Select-Object -Last 1).ToString().Trim()
    Write-Host "   $Equipo"
}
# Una IP pelada (-Equipo 192.168.43.57) entraria con el usuario de Windows y
# quedaria esperando una contrasena que no existe. Paso el 2026-10-02.
if ($Equipo -notmatch "@") { $Equipo = "admin@$Equipo" }

# accept-new: acepta la huella del Pi la primera vez sin el prompt yes/no,
# pero sigue avisando si la huella CAMBIA despues (que es el caso que importa).
# HostKeyAlias: la huella se compara contra la ya conocida del Pi, se entre por
# nombre o por IP.
$sshOpts = @("-o","ConnectTimeout=10","-o","StrictHostKeyChecking=accept-new",
             "-o","HostKeyAlias=pi-mb.local")
$clave = Join-Path $env:USERPROFILE ".ssh\id_ed25519_pi"
if (Test-Path $clave) { $sshOpts = @("-i", $clave) + $sshOpts }

Paso "Probando SSH contra $Equipo"
if (-not (Test-Path $clave)) {
    Write-Host "   (te va a pedir la contrasena de '$($Equipo.Split('@')[0])')" -ForegroundColor DarkGray
}
ssh @sshOpts $Equipo "echo conectado a `$(hostname) como `$(whoami)"
if ($LASTEXITCODE -ne 0) {
    Write-Host @"

No se pudo entrar. En orden:
  1. El primer arranque tarda 3-5 min y reinicia solo una vez. Esperar.
  2. Si 'pi-MB.local' no resuelve, buscar la IP en la tabla de clientes DHCP
     del router, o con: arp -a    (y despues: -Equipo admin@<IP>)
  3. Si el Pi tampoco aparece por IP, volver a leer la SD desde la PC:
     Update-HostStorageCache ; .\scripts_pi\verificar_sd.ps1
"@ -ForegroundColor Yellow
    exit 1
}

if (-not $SoloInventario) {
    Paso "Creando ~/TPF en el Pi"
    ssh @sshOpts $Equipo "mkdir -p ~/TPF/scripts_pi ~/TPF/logs"

    Paso "Copiando src/ y scripts_pi/"
    # Los __pycache__ son .pyc compilados en la PC: no sirven en el Pi, ensucian
    # la copia y confunden al leer que se subio. Se limpian de los dos lados.
    Get-ChildItem -Path "$raiz\src" -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    scp @sshOpts -r "$raiz\src" "${Equipo}:~/TPF/"
    ssh @sshOpts $Equipo "rm -rf ~/TPF/src/__pycache__"
    scp @sshOpts    "$raiz\scripts_pi\inventario_pi.sh" "$raiz\scripts_pi\demo.sh" "${Equipo}:~/TPF/scripts_pi/"
    # Pruebas de piso (2026-09-30): motores por escalones, umbrales, camara.
    scp @sshOpts -r "$raiz\scripts_pi\piso" "${Equipo}:~/TPF/scripts_pi/"
    # Los .sh viajan desde Windows con CRLF; bash no los ejecuta asi.
    ssh @sshOpts $Equipo "sed -i 's/\r`$//' ~/TPF/scripts_pi/inventario_pi.sh ~/TPF/scripts_pi/demo.sh ~/TPF/scripts_pi/piso/*.sh"

    # Que lo copiado funcione ALLA: las verificaciones del comportamiento, con
    # el Python del Pi. Es lo que confirma que la PC y el Pi tienen lo mismo.
    Paso "Verificaciones del comportamiento, en el Pi"
    $ErrorActionPreference = "Continue"
    $fallas = ssh @sshOpts $Equipo "cd ~/TPF/src && ../.venv/bin/python prueba_estados.py 2>&1 | grep -c FALLA"
    $ErrorActionPreference = "Stop"
    if ("$fallas".Trim() -eq "0") {
        Write-Host "   todas en orden" -ForegroundColor Green
    } else {
        Write-Host "   OJO: no pasaron limpias (salida: $fallas). Entrar al Pi y correr:" -ForegroundColor Yellow
        Write-Host "   cd ~/TPF/src && ../.venv/bin/python prueba_estados.py" -ForegroundColor Yellow
        Write-Host "   (si el Pi es nuevo y todavia no tiene el entorno de Python, es el Paso 12 del RUNBOOK)" -ForegroundColor DarkGray
    }
}

Paso "Inventario del Pi"
ssh @sshOpts $Equipo "bash ~/TPF/scripts_pi/inventario_pi.sh"

Write-Host "`nListo. Para operar el robot: GUIA_PRESENTACION.md (entrar con .\scripts_pi\entrar.cmd)." -ForegroundColor Green
