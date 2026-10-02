<#
.SYNOPSIS
    Encuentra el Pi en la red y abre una sesion SSH en el.
.DESCRIPTION
    Se corre desde la PC (PowerShell). El 2026-10-01 el nombre 'pi-MB.local' no
    resolvio aunque el Pi estaba prendido y en la red: desde entonces no se
    confia solo en el nombre. Este script prueba, en orden:

      1. el nombre pi-MB.local;
      2. la ultima IP con la que se pudo entrar (queda anotada en
         scripts_pi\ultima_ip.txt);
      3. la tabla ARP de Windows, buscando la placa de red del Pi;
      4. si la red es chica (un hotspot de celular lo es), un barrido de todas
         las direcciones para que el Pi aparezca en esa tabla.

    Cuando lo encuentra, entra con la clave id_ed25519_pi.
.EXAMPLE
    .\scripts_pi\entrar.cmd                 # buscar y entrar
    .\scripts_pi\entrar.cmd -SoloBuscar     # solo decir la IP
    .\scripts_pi\entrar.cmd -Comando "bash ~/TPF/scripts_pi/demo.sh chequeo"
    .\scripts_pi\entrar.cmd -Ip 192.168.43.57     # si ya se sabe la IP
.NOTES
    Si no lo encuentra: mirar en el celular la lista de dispositivos conectados
    al hotspot y pasar esa IP con -Ip.
#>
param(
    [string]$Ip = "",
    [string]$Comando = "",
    [switch]$SoloBuscar
)

$usuario = "admin"
$nombre  = "pi-MB.local"
$clave   = Join-Path $env:USERPROFILE ".ssh\id_ed25519_pi"
$anotada = Join-Path $PSScriptRoot "ultima_ip.txt"

# Placa WiFi del Pi, para reconocerlo en la tabla ARP. La direccion completa
# del robot propio va en scripts_pi\mac_pi.txt (una linea, como la muestra
# 'arp -a'; ese archivo no se versiona). Sin el, se busca por el prefijo del
# fabricante, que es comun a las Raspberry Pi 5 y no identifica a ninguna.
$archivoMac = Join-Path $PSScriptRoot "mac_pi.txt"
$mac = "2c-cf-67"
if (Test-Path $archivoMac) {
    $leida = (Get-Content $archivoMac -TotalCount 1)
    if ($leida) { $mac = $leida.Trim().ToLower() }
}

# El alias hace que se compare siempre contra la huella ya conocida del Pi,
# se entre por nombre o por IP: si contesta otro equipo, ssh lo dice.
$sshOpts = @("-o", "ConnectTimeout=6", "-o", "HostKeyAlias=pi-mb.local",
             "-o", "StrictHostKeyChecking=accept-new")
if (Test-Path $clave) { $sshOpts = @("-i", $clave) + $sshOpts }

function Decir($texto) { if (-not $SoloBuscar) { Write-Host $texto -ForegroundColor DarkGray } }

function Contesta($destino) {
    # BatchMode: si la clave no sirve, falla en vez de quedarse pidiendo contrasena.
    $null = & ssh @sshOpts -o BatchMode=yes "$usuario@$destino" "echo ok" 2>$null
    return ($LASTEXITCODE -eq 0)
}

function IpPorArp {
    $linea = arp -a | Select-String -SimpleMatch $mac | Select-Object -First 1
    if ($linea) { return (($linea.ToString().Trim() -split "\s+")[0]) }
    return ""
}

function Barrer {
    # Solo en redes de hasta 254 direcciones: un hotspot lo es, la red de la
    # facultad (65 000) no.
    $redes = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.PrefixLength -ge 24 -and $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" }
    foreach ($red in $redes) {
        $base = ($red.IPAddress -split "\.")[0..2] -join "."
        Decir "   barriendo $base.1 a $base.254 ..."
        $tareas = 1..254 | ForEach-Object {
            (New-Object System.Net.NetworkInformation.Ping).SendPingAsync("$base.$_", 400)
        }
        try { [System.Threading.Tasks.Task]::WaitAll($tareas) } catch {}
    }
}

$encontrada = ""
$candidatas = @()
if ($Ip) { $candidatas += $Ip }
$candidatas += $nombre
if (Test-Path $anotada) { $candidatas += (Get-Content $anotada -TotalCount 1).Trim() }

foreach ($c in $candidatas) {
    if (-not $c) { continue }
    Decir "Probando $c ..."
    if (Contesta $c) { $encontrada = $c; break }
}

if (-not $encontrada) {
    $porArp = IpPorArp
    if (-not $porArp) { Barrer; $porArp = IpPorArp }
    if ($porArp) {
        Decir "Probando $porArp (la placa del Pi aparece en la red) ..."
        if (Contesta $porArp) { $encontrada = $porArp }
    }
}

if (-not $encontrada) {
    Write-Host @"

No encontre el Pi. En orden:
  1. Esta prendido? Tarda 1-2 minutos en arrancar. LED verde parpadeando = arrancando.
  2. La notebook y el Pi estan en la MISMA red (el hotspot del celular)?
  3. En el celular, mirar los dispositivos conectados al hotspot: si aparece
     'pi-MB', probar con su IP:   .\scripts_pi\entrar.cmd -Ip <esa IP>
  4. Si el Pi no aparece en el celular, nunca se le cargo ese hotspot: hay que
     volver a una red que conozca y correr   demo.sh hotspot "NOMBRE" "CLAVE"
"@ -ForegroundColor Yellow
    exit 1
}

if ($encontrada -ne $nombre) { Set-Content -Path $anotada -Value $encontrada -Encoding ascii }

if ($SoloBuscar) {
    Write-Output $encontrada
    exit 0
}

Write-Host "Pi encontrado en $encontrada" -ForegroundColor Green
if ($Comando) {
    & ssh @sshOpts "$usuario@$encontrada" $Comando
} else {
    # -t: terminal completa, para que Ctrl+C llegue al programa que corre en el Pi.
    & ssh -t @sshOpts "$usuario@$encontrada"
}
exit $LASTEXITCODE
