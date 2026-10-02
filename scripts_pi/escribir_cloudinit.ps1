<#
.SYNOPSIS
    Escribe la personalizacion de primer arranque en la SD ya grabada.
.DESCRIPTION
    Raspberry Pi Imager 2.x guarda los ajustes de personalizacion en el
    registro, pero NO los escribe en la tarjeta cuando la imagen se cargo con
    "Usar personalizada" (el caso del 2026-09-04, con el Imager en modo
    Offline). El resultado es una SD valida pero virgen: sin usuario, sin SSH y
    sin WiFi. Arrancarla asi, sin micro-HDMI, deja el Pi inalcanzable.

    Este script cierra ese hueco: lee los ajustes del registro y escribe a mano
    los archivos de cloud-init que Raspberry Pi OS Trixie lee en el primer
    arranque (user-data y network-config, datasource NoCloud, dsmode local).

    Las credenciales viajan del registro al archivo SIN pasar por pantalla ni
    por variables intermedias legibles: el Imager ya las guarda en el formato
    que cloud-init necesita (hash crypt $5$ para la contrasena, PSK de 64 hex
    para el WiFi), asi que se copian tal cual.

    Los archivos originales se respaldan como .orig antes de sobrescribir.
.EXAMPLE
    .\scripts_pi\escribir_cloudinit.ps1
    .\scripts_pi\escribir_cloudinit.ps1 -Unidad E -Pais AR -Zona America/Argentina/Buenos_Aires
#>
param(
    [string]$Unidad,
    [string]$Pais = "PY",
    [string]$Zona = "America/Asuncion",
    [string]$Teclado = "us"
)

$ErrorActionPreference = "Stop"

# --- Ubicar bootfs ----------------------------------------------------------
if (-not $Unidad) {
    $cand = Get-Volume | Where-Object {
        $_.DriveLetter -and $_.FileSystem -eq 'FAT32' -and
        (Test-Path "$($_.DriveLetter):\config.txt") -and (Test-Path "$($_.DriveLetter):\meta-data")
    }
    if (-not $cand) {
        Write-Host "No encontre la particion bootfs de una imagen con cloud-init." -ForegroundColor Red
        Write-Host "Si la SD esta puesta pero sin letra, correr antes: Update-HostStorageCache"
        exit 1
    }
    $Unidad = ($cand | Select-Object -First 1).DriveLetter
}
$b = "${Unidad}:"
Write-Host "bootfs en $b" -ForegroundColor Cyan

# --- Leer los ajustes que el Imager guardo ----------------------------------
$k = "HKCU:\Software\Raspberry Pi\Raspberry Pi Imager\imagecustomization"
if (-not (Test-Path $k)) {
    Write-Host "El Imager no tiene ajustes guardados en el registro." -ForegroundColor Red
    Write-Host "Abrir el Imager, completar 'Editar ajustes' y volver a correr esto."
    exit 1
}
$c = Get-ItemProperty $k

$usuario  = $c.sshUserName
$hostname = $c.hostname
$ssid     = $c.wifiSSID
$oculta   = ($c.wifiHidden -eq 'true')

foreach ($par in @(@('sshUserName',$usuario), @('hostname',$hostname), @('wifiSSID',$ssid),
                   @('sshUserPassword',$c.sshUserPassword), @('wifiPasswordCrypt',$c.wifiPasswordCrypt))) {
    if (-not $par[1]) { Write-Host "Falta '$($par[0])' en los ajustes del Imager." -ForegroundColor Red; exit 1 }
}

# Validar el formato de las credenciales sin mostrarlas
if ($c.sshUserPassword -notmatch '^\$[0-9a-z]+\$') {
    Write-Host "La contrasena guardada no es un hash crypt; abortando por seguridad." -ForegroundColor Red; exit 1
}
$psk = [string]$c.wifiPasswordCrypt
$claveWifi = if ($psk -match '^[0-9a-fA-F]{64}$') { $psk } else { $psk }

Write-Host "  usuario  : $usuario"
Write-Host "  hostname : $hostname"
Write-Host "  SSID     : $ssid"
Write-Host "  pais     : $Pais    zona: $Zona"
Write-Host "  claves   : hash crypt + PSK, se copian sin mostrarse" -ForegroundColor DarkGray

# --- Respaldar los originales ----------------------------------------------
foreach ($f in @("user-data","network-config")) {
    if ((Test-Path "$b\$f") -and -not (Test-Path "$b\$f.orig")) {
        Copy-Item "$b\$f" "$b\$f.orig"
        Write-Host "  respaldo: $f.orig" -ForegroundColor DarkGray
    }
}

# --- user-data --------------------------------------------------------------
# Grupos: la lista canonica que usaba el propio firstrun.sh del Imager 1.x.
# 'dialout' es imprescindible para hablarle al ESP32 por USB en el Dia 4,
# y 'video' para la camara.
$userData = @"
#cloud-config
# Generado por scripts_pi/escribir_cloudinit.ps1 el $(Get-Date -Format 'yyyy-MM-dd HH:mm').
# Reemplaza la personalizacion que el Imager 2.0.8 no escribio.

hostname: $hostname
manage_etc_hosts: true

users:
- name: $usuario
  gecos: $usuario
  shell: /bin/bash
  groups: adm,dialout,cdrom,sudo,audio,video,plugdev,games,users,input,netdev,spi,i2c,gpio
  sudo: ALL=(ALL) NOPASSWD:ALL
  lock_passwd: false
  passwd: $($c.sshUserPassword)

ssh_pwauth: true

chpasswd:
  expire: false

timezone: $Zona

keyboard:
  model: pc105
  layout: $Teclado

# En Raspberry Pi OS la radio WiFi queda bloqueada por rfkill hasta que se
# fija el pais. Sin esto el WiFi puede no levantar aunque netplan este bien.
runcmd:
- [ raspi-config, nonint, do_wifi_country, $Pais ]
- [ rfkill, unblock, wifi ]
- [ systemctl, enable, --now, ssh ]
"@

# --- network-config (netplan v2) -------------------------------------------
$oculto = if ($oculta) { "`n          hidden: true" } else { "" }
$networkConfig = @"
# Generado por scripts_pi/escribir_cloudinit.ps1 el $(Get-Date -Format 'yyyy-MM-dd HH:mm').
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: true
      optional: true
  wifis:
    wlan0:
      dhcp4: true
      optional: true
      access-points:
        "$ssid":
          password: "$claveWifi"$oculto
      regulatory-domain: "$Pais"
"@

# --- Escribir: UTF-8 SIN BOM y con saltos LF --------------------------------
# Un BOM o un CRLF rompen el YAML que lee cloud-init.
$sinBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText("$b\user-data",      ($userData      -replace "`r`n", "`n"), $sinBom)
[System.IO.File]::WriteAllText("$b\network-config", ($networkConfig -replace "`r`n", "`n"), $sinBom)

Write-Host "`nEscritos user-data y network-config." -ForegroundColor Green
Write-Host "Verificar con: .\scripts_pi\verificar_sd.ps1"
