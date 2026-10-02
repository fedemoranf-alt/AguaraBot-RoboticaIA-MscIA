#!/usr/bin/env bash
# Inventario del Pi 5 — checklist de salida del Paso 11.5 del RUNBOOK.
# Corre en el Pi. No modifica nada: sólo mira y dictamina.
#
#   bash ~/TPF/scripts_pi/inventario_pi.sh

ok=0; mal=0
si() { printf '  \033[32mOK\033[0m   %s\n' "$1"; ok=$((ok+1)); }
no() { printf '  \033[31mMAL\033[0m  %s\n' "$1"; mal=$((mal+1)); }
nota() { printf '  --   %s\n' "$1"; }
titulo() { printf '\n\033[1m%s\033[0m\n' "$1"; }

titulo "Identidad"
nota "usuario : $(whoami)"
nota "equipo  : $(hostname)"
nota "IP      : $(hostname -I 2>/dev/null | tr -s ' ')"

titulo "Sistema — trixie o bookworm, y aarch64 sí o sí"
version_so=$(. /etc/os-release 2>/dev/null && echo "$VERSION_CODENAME")
arquitectura=$(uname -m)
python_ver=$(python3 -V 2>&1 | cut -d' ' -f2)
nota "modelo  : $(tr -d '\0' < /proc/device-tree/model 2>/dev/null)"
case "$version_so" in
  trixie)   si "sistema trixie (Debian 13), Python $python_ver" ;;
  bookworm) si "sistema bookworm (Debian 12), Python $python_ver" ;;
  *)        no "sistema '$version_so' — se esperaba trixie o bookworm; reflashear" ;;
esac
[ "$arquitectura" = "aarch64" ] && si "arquitectura $arquitectura (64 bits)" \
    || no "arquitectura '$arquitectura' — torch/ultralytics necesitan aarch64; reflashear"

titulo "Espacio y memoria — hacen falta 6 GB libres"
libre_gb=$(df -BG --output=avail / | tail -1 | tr -dc '0-9')
nota "libre en / : ${libre_gb} GB    RAM: $(free -h | awk '/^Mem:/{print $2}')"
[ "${libre_gb:-0}" -ge 6 ] && si "hay lugar para torch + ultralytics (~3 GB)" \
    || no "sólo ${libre_gb} GB libres — pip se va a quedar sin espacio"

titulo "Alimentación — el rayo amarillo, sin monitor"
estado=$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)
if [ -z "$estado" ]; then
    nota "vcgencmd no disponible"
elif [ "$estado" = "0x0" ]; then
    si "sin recortes de tensión ni térmicos ($estado)"
else
    # Los bits 0-3 son "ahora mismo"; los 16-19, "paso alguna vez desde el arranque".
    # La distincion importa: los altos solos suelen ser el transitorio de encendido.
    v=$((estado))
    nota "get_throttled = $estado"
    ahora=0
    for par in "0:bajo voltaje" "1:frecuencia de la CPU limitada" "2:throttling" "3:limite termico blando"; do
        b=${par%%:*}; d=${par#*:}
        if [ $(( (v >> b) & 1 )) -eq 1 ]; then no "AHORA MISMO: $d (bit $b)"; ahora=1; fi
    done
    hubo=0
    for par in "16:bajo voltaje" "17:frecuencia limitada" "18:throttling" "19:limite termico blando"; do
        b=${par%%:*}; d=${par#*:}
        if [ $(( (v >> b) & 1 )) -eq 1 ]; then nota "ocurrio desde el arranque: $d (bit $b)"; hubo=1; fi
    done
    if [ "$ahora" -eq 0 ] && [ "$hubo" -eq 1 ]; then
        no "hubo bajo voltaje/throttling pero AHORA NO. Suele ser el transitorio de encendido, pero una fuente al limite vuelve a caer bajo la carga de YOLO. Verificar la fuente ANTES de dar por buena una medicion de FPS"
    fi
fi
nota "temperatura: $(vcgencmd measure_temp 2>/dev/null | cut -d= -f2)"
# En el Pi 5 el PMIC expone los rieles reales: EXT5V_V debajo de ~4,8 V es fuente floja.
riel=$(vcgencmd pmic_read_adc 2>/dev/null | grep -i 'EXT5V_V\|VDD_CORE_V' | tr -s ' ' | paste -sd' ' -)
[ -n "$riel" ] && nota "rieles: $riel"

titulo "Cámara Arducam — CSI o USB (pendiente abierto del PLAN §1)"
# El Pi 5 expone siempre /dev/video19..35: son la ISP (pispbe) y el decodificador
# HEVC, no cámaras. Filtrarlos o el chequeo da falso positivo.
csi=$(rpicam-hello --list-cameras 2>/dev/null | grep -c ':' )
usb=$(v4l2-ctl --list-devices 2>/dev/null | grep -iv 'pispbe\|hevc\|codec\|pisp' | grep -i 'cam\|usb\|uvc')
if [ "${csi:-0}" -gt 0 ]; then
    si "es CSI — poner FUENTE_CAMARA = \"csi\" en src/config.py"
    rpicam-hello --list-cameras 2>/dev/null | sed 's/^/       /'
elif [ -n "$usb" ]; then
    si "es USB — poner FUENTE_CAMARA = \"usb\" y el /dev/videoN en INDICE_CAMARA"
    echo "$usb" | sed 's/^/       /'
    lsusb 2>/dev/null | grep -i 'cam\|video\|arducam' | sed 's/^/       /'
else
    nota "rpicam-hello no lista sensores CSI, y los /dev/videoN que hay son"
    nota "la ISP y el decodificador del propio Pi 5, no cámaras."
    no "no hay ninguna cámara conectada. Si ya la conectaste y aun así no aparece: apagar el Pi (la CSI NO se conecta en caliente), revisar que el cable plano entre a fondo y con los contactos del lado correcto, y volver a arrancar"
fi

titulo "Internet — pip baja ~2 GB y el bench descarga yolov8n.pt"
ping -c1 -W3 deb.debian.org >/dev/null 2>&1 && si "hay salida a internet" \
    || no "sin internet — revisar WiFi (nmcli device wifi list)"

titulo "Código del proyecto"
[ -f "$HOME/TPF/src/bench_vision.py" ] && si "~/TPF/src está en el Pi" \
    || no "falta ~/TPF/src — correr provisionar_pi.ps1 desde la PC"

printf '\n\033[1m%d bien, %d mal.\033[0m ' "$ok" "$mal"
[ "$mal" -eq 0 ] && printf 'Listo para el Paso 12.\n\n' \
    || printf 'Resolver lo marcado MAL antes de seguir.\n\n'
