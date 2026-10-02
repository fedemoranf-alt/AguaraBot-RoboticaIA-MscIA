<#
.SYNOPSIS
    Revisa la SD recien grabada ANTES del primer arranque del Pi.
.DESCRIPTION
    Sin cable micro-HDMI, la red es el unico camino de entrada: si el Imager no
    dejo el SSH activado o el WiFi quedo mal, el Pi arranca y no hay forma de
    saber que paso. Este script lee la particion 'bootfs' (FAT32, la unica que
    Windows monta) y confirma que la personalizacion quedo escrita.

    Correr con la SD todavia en la PC, despues de grabar. Si el Imager la
    expulso, sacarla y volver a ponerla.

    No escribe nada: solo lee. Nunca imprime contrasenas.
.EXAMPLE
    .\scripts_pi\verificar_sd.ps1
    .\scripts_pi\verificar_sd.ps1 -Unidad E -Hostname otro
#>
param(
    [string]$Unidad,
    [string]$Hostname = "pi-MB",     # lo grabado el 2026-09-04
    [string]$Usuario  = "admin"
)

$ErrorActionPreference = "Stop"
$ok = 0; $mal = 0
function Bien($m) { Write-Host "  OK   $m" -ForegroundColor Green;  $script:ok++ }
function Mal ($m) { Write-Host "  MAL  $m" -ForegroundColor Red;    $script:mal++ }
function Nota($m) { Write-Host "  --   $m" -ForegroundColor DarkGray }
function Titulo($t) { Write-Host "`n$t" -ForegroundColor Cyan }

# --- Encontrar bootfs -------------------------------------------------------
if (-not $Unidad) {
    $cand = Get-Volume | Where-Object {
        $_.DriveLetter -and $_.FileSystem -eq 'FAT32' -and
        (Test-Path "$($_.DriveLetter):\config.txt")
    }
    if (-not $cand) {
        Write-Host "No encontre la particion bootfs (FAT32 con config.txt)." -ForegroundColor Yellow
        Write-Host "Si el Imager expulso la tarjeta, sacala y volve a ponerla."
        Get-Volume | Where-Object DriveLetter | Select-Object DriveLetter, FileSystemLabel, FileSystem, @{n='GB';e={[math]::Round($_.Size/1GB,1)}} | Format-Table -AutoSize
        exit 1
    }
    $Unidad = ($cand | Select-Object -First 1).DriveLetter
}
$b = "${Unidad}:"
Titulo "Particion de arranque en $b"
Nota "etiqueta: $((Get-Volume -DriveLetter $Unidad).FileSystemLabel)"

# --- Version de la imagen ---------------------------------------------------
# issue.txt de Raspberry Pi OS trae la fecha, no el nombre de la version:
#   "Raspberry Pi reference 2026-06-18"
Titulo "Imagen grabada"
if (Test-Path "$b\issue.txt") {
    $issue = (Get-Content "$b\issue.txt" -TotalCount 1)
    Nota $issue
    if ($issue -match 'Raspberry Pi reference (\d{4}-\d{2}-\d{2})') { Bien "imagen oficial del $($Matches[1])" }
    elseif ($issue -match 'trixie|bookworm')                       { Bien "version $($Matches[0])" }
    else { Mal "issue.txt no tiene la forma esperada - la grabacion puede estar incompleta" }
} else { Mal "falta issue.txt - la grabacion puede estar incompleta" }

# --- Personalizacion --------------------------------------------------------
# Dos mecanismos posibles segun la version del Imager y de la imagen:
#   - Imager 1.x  -> firstrun.sh + systemd.run en cmdline.txt
#   - Imager 2.x / Raspberry Pi OS Trixie -> cloud-init (user-data, meta-data,
#     network-config), datasource NoCloud con dsmode: local
Titulo "Personalizacion de primer arranque"
$firstrun = "$b\user-data"
$cmdline  = Get-Content "$b\cmdline.txt" -ErrorAction SilentlyContinue
$hn = ""; $usr = ""

if (Test-Path "$b\firstrun.sh") {
    Nota "mecanismo: firstrun.sh (Imager 1.x)"
    $f = Get-Content "$b\firstrun.sh" -Raw
    if ($cmdline -match 'systemd\.run=.*firstrun') { Bien "cmdline.txt invoca firstrun.sh" }
    else { Mal "firstrun.sh existe pero cmdline.txt no lo llama - no se va a aplicar" }
    $hn  = [regex]::Match($f, 'raspi-config nonint do_hostname\s+(\S+)').Groups[1].Value
    $usr = [regex]::Match($f, 'do_user(?:conf)?\s+(\S+)').Groups[1].Value
    if ($f -match 'do_ssh|systemctl enable ssh') { Bien "SSH activado" } else { Mal "SSH NO activado" }
}
elseif (-not (Test-Path $firstrun)) {
    Mal "no hay ni firstrun.sh ni user-data: la SD quedo sin personalizar."
}
else {
    Nota "mecanismo: cloud-init (Imager 2.x / Trixie)"
    $f = Get-Content $firstrun -Raw
    $n = if (Test-Path "$b\network-config") { Get-Content "$b\network-config" -Raw } else { "" }

    # Una plantilla de fabrica tiene TODO comentado: detectarlo explicitamente,
    # porque los archivos existen igual y a simple vista parecen configurados.
    $activas = ($f -split "`n" | Where-Object { $_.Trim() -and $_.Trim() -notmatch '^#' }).Count
    if ($activas -lt 3) {
        Mal "user-data es la plantilla de fabrica: todo comentado, no configura nada."
        Nota "Correr: .\scripts_pi\escribir_cloudinit.ps1"
    } else {
        Bien "user-data tiene $activas lineas activas"
        if ($f -notmatch '^#cloud-config') { Mal "user-data no empieza con '#cloud-config' - cloud-init lo ignora" }
        if ($f -match "`t")                { Mal "user-data tiene TABS - el YAML de cloud-init solo acepta espacios" }

        $hn  = [regex]::Match($f, '(?m)^hostname:\s*(\S+)').Groups[1].Value
        $usr = [regex]::Match($f, '(?m)^\s*-\s*name:\s*(\S+)').Groups[1].Value

        if ($f -match '(?m)^\s*passwd:\s*\$[0-9a-z]+\$') { Bien "contrasena presente, como hash crypt" }
        else { Mal "no hay hash de contrasena en user-data - no vas a poder entrar" }

        if ($f -match '(?m)^ssh_pwauth:\s*true') { Bien "SSH por contrasena habilitado (ssh_pwauth)" }
        else { Mal "falta 'ssh_pwauth: true' - SSH va a rechazar la contrasena" }

        if ($n -match '(?m)^\s*wifis:') {
            $ssid = [regex]::Match($n, '(?m)^\s*"?([^"\s:]+)"?:\s*$\s*\n\s*password:').Groups[1].Value
            Bien "WiFi preconfigurado$(if ($ssid) { " (SSID: $ssid)" })"
            if ($n -match '(?m)^\s*password:\s*"?([0-9a-fA-F]{64})"?') { Bien "clave WiFi como PSK de 64 hex" }
            elseif ($n -match '(?m)^\s*password:') { Nota "clave WiFi en texto plano (funciona igual)" }
            else { Mal "el bloque wifis no tiene password" }

            $pais = [regex]::Match($n, 'regulatory-domain:\s*"?([A-Z]{2})"?').Groups[1].Value
            if (-not $pais) { $pais = [regex]::Match($f, 'do_wifi_country,\s*(\w{2})').Groups[1].Value }
            if ($pais) { Bien "pais del WiFi = $pais" }
            else { Mal "sin pais de WiFi - en Raspberry Pi OS la radio queda bloqueada por rfkill hasta fijarlo" }
        } else {
            Mal "sin WiFi preconfigurado - solo vas a entrar por Ethernet"
        }
    }
}

# --- Identidad, comun a los dos mecanismos ----------------------------------
if ($hn) {
    Bien "hostname = $hn"
    if ($hn -ne $Hostname) { Nota "esperaba '$Hostname'; usar -Equipo <usuario>@$hn.local" }
    if ($hn -cmatch '[A-Z]') {
        Nota "tiene mayusculas: mDNS no distingue may/min, '$($hn.ToLower()).local' resuelve igual."
    }
} else { Mal "no encontre el hostname" }

if ($usr) {
    Bien "usuario = $usr"
    if ($usr -ne $Usuario) { Nota "esperaba '$Usuario'; ajustar -Equipo en provisionar_pi.ps1" }
} else { Mal "no encontre el usuario - sin usuario no hay como entrar" }

Write-Host "`n$ok bien, $mal mal. " -NoNewline -ForegroundColor White
if ($mal -eq 0) {
    Write-Host "Expulsar la SD, ponerla en el Pi y alimentar." -ForegroundColor Green
    Write-Host "El primer arranque tarda 3-5 min y reinicia solo una vez. Despues:" -ForegroundColor Green
    $eq = if ($usr -and $hn) { "$usr@$hn.local" } else { "$Usuario@$Hostname.local" }
    Write-Host "  .\scripts_pi\provisionar_pi.ps1 -Equipo $eq"
} else {
    Write-Host "Regrabar antes de arrancar: corregirlo despues cuesta mucho mas." -ForegroundColor Yellow
}
