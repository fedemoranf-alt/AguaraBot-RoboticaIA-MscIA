#!/usr/bin/env bash
# ==============================================================================
# TPF Robótica IA — comandos del día de la presentación
# ==============================================================================
# Corre EN EL PI. Cada acción es un solo comando, y el chequeo dice en castellano
# qué está mal y qué hacer. La guía completa está en GUIA_PRESENTACION.md.
#
#   bash ~/TPF/scripts_pi/demo.sh chequeo            ¿está todo listo?
#   bash ~/TPF/scripts_pi/demo.sh imagen             ¿la imagen llega sana? (6 s, sin motores)
#   bash ~/TPF/scripts_pi/demo.sh ver                ¿ve el oso? (Ctrl+C sale)
#   bash ~/TPF/scripts_pi/demo.sh fondo              ¿algo del fondo parece oso o mochila?
#   bash ~/TPF/scripts_pi/demo.sh sonar              ¿qué distancia mide el ultrasónico? (5 s, sin motores)
#   bash ~/TPF/scripts_pi/demo.sh correr [seg] [nota]   la demo (60 s por defecto)
#   bash ~/TPF/scripts_pi/demo.sh grabar [seg] [nota]   la demo, guardando el video
#   bash ~/TPF/scripts_pi/demo.sh ultima             análisis de la última corrida
#   bash ~/TPF/scripts_pi/demo.sh parar              corta una corrida colgada
#   bash ~/TPF/scripts_pi/demo.sh firmware           parámetros de motores del ESP32
#   bash ~/TPF/scripts_pi/demo.sh red                en qué WiFi está y qué redes conoce
#   bash ~/TPF/scripts_pi/demo.sh hotspot "NOMBRE" "CLAVE"   guarda el hotspot del celular
#   bash ~/TPF/scripts_pi/demo.sh apagar             apaga el Pi ordenadamente
#
# Si este script fallara, los comandos a mano están en la guía ("Comandos a
# mano"). Probados en el robot (2026-10-01 y 2026-10-02): chequeo, imagen, ver,
# sonar, correr, grabar, ultima, firmware, red, hotspot y apagar. A medias:
# parar (sólo sin corrida que parar). SIN PROBAR ALLÁ: fondo.
# ==============================================================================

set -u

TPF="$HOME/TPF"
SRC="$TPF/src"
VENV="$TPF/.venv"

problemas=0
avisos=0

bien()  { printf '  [ OK ]  %s\n' "$1"; }
aviso() { printf '  [ ?? ]  %s\n' "$1"; [ $# -gt 1 ] && printf '          -> %s\n' "$2"; avisos=$((avisos + 1)); }
mal()   { printf '  [FALLA] %s\n' "$1"; [ $# -gt 1 ] && printf '          -> %s\n' "$2"; problemas=$((problemas + 1)); }

activar() {
    if [ ! -f "$VENV/bin/activate" ]; then
        echo "No encuentro el entorno de Python en $VENV."
        exit 1
    fi
    # shellcheck disable=SC1091
    source "$VENV/bin/activate"
    cd "$SRC" || exit 1
}

hay() { command -v "$1" >/dev/null 2>&1; }

# ------------------------------------------------------------------------------
chequeo() {
    echo "=============================================================="
    echo " Chequeo previo — $(date '+%H:%M:%S')"
    echo "=============================================================="

    echo "Alimentación del Pi"
    if hay vcgencmd; then
        local t hex v volt
        t=$(vcgencmd get_throttled | cut -d= -f2)
        hex=$((16#${t#0x}))
        if [ "$hex" -eq 0 ]; then
            bien "get_throttled = 0x0 (sin bajo voltaje ni recortes)"
        else
            if (( hex & 0x1 )); then
                mal "bajo voltaje AHORA ($t)" \
                    "cargador agotado o conectado por USB-C: pasarlo a USB-A, o usar la fuente de pared"
            fi
            if (( hex & 0x4 )); then
                mal "el Pi está recortando su velocidad AHORA ($t)" \
                    "el FPS va a caer: revisar alimentación y temperatura"
            fi
            if (( hex & 0x8 )); then
                mal "límite térmico AHORA ($t)" "dejarlo enfriar, destaparlo, no apoyarlo sobre algo caliente"
            fi
            if (( hex & 0x1 )) || (( hex & 0x4 )) || (( hex & 0x8 )); then
                :
            else
                aviso "hubo bajo voltaje en algún momento desde el arranque ($t), ahora no" \
                      "suele ser al enchufar algo; si el chequeo se repite limpio, seguir"
            fi
        fi
        volt=$(vcgencmd pmic_read_adc EXT5V_V 2>/dev/null | sed -n 's/.*=\([0-9.]*\)V.*/\1/p')
        [ -n "$volt" ] && volt=$(awk -v v="$volt" 'BEGIN{printf "%.2f", v}')
        if [ -n "$volt" ]; then
            if awk "BEGIN{exit !($volt >= 4.90)}"; then
                bien "EXT5V_V = ${volt} V (medido en casa: 4,91-5,13 con el lazo andando)"
            else
                aviso "EXT5V_V = ${volt} V, bajo" "el cargador se está agotando o el cable es malo"
            fi
        fi
        v=$(vcgencmd measure_temp | sed -n "s/temp=\([0-9.]*\).*/\1/p")
        if [ -n "$v" ]; then
            if awk "BEGIN{exit !($v < 75)}"; then
                bien "temperatura ${v} °C"
            elif awk "BEGIN{exit !($v < 80)}"; then
                aviso "temperatura ${v} °C, alta" "a 80 °C empieza a recortar; esperar un poco entre corridas"
            else
                mal "temperatura ${v} °C" "a más de 80 °C recorta la velocidad: dejarlo enfriar"
            fi
        fi
    else
        aviso "no encuentro vcgencmd: ¿esto es el Pi?"
    fi

    echo "Periféricos"
    if [ -e /dev/video0 ]; then
        local nombre=""
        # El bloque que contiene /dev/video0: el primero de la lista es el
        # procesador de imagen del Pi 5 (pispbe), no la webcam.
        hay v4l2-ctl && nombre=$(v4l2-ctl --list-devices 2>/dev/null \
            | awk '/^[^ \t]/ {h = $0} $1 == "/dev/video0" {print h; exit}' \
            | sed 's/ *(.*//; s/:$//')
        bien "cámara en /dev/video0 ${nombre:+($nombre)}"
    else
        mal "no hay cámara en /dev/video0" "desenchufar y volver a enchufar la webcam al Pi, esperar 5 s"
    fi
    local puertos
    puertos=$(ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null | tr '\n' ' ')
    if [ -n "$puertos" ]; then
        bien "ESP32 en ${puertos}"
    else
        mal "no aparece el ESP32 (ni ttyUSB ni ttyACM)" \
            "desenchufar y volver a enchufar su USB al Pi; probar otro cable"
    fi
    aviso "motores: el Pi no puede ver si la UPS da 12 V al L298" \
          "confirmarlo a ojo — y dejarla DESENCHUFADA hasta el momento de correr"

    echo "Software"
    if [ -f "$VENV/bin/activate" ]; then
        local salida n
        salida=$(cd "$SRC" && "$VENV/bin/python" prueba_estados.py 2>&1)
        n=$(printf '%s\n' "$salida" | grep -c '\[ok  \]')
        if printf '%s\n' "$salida" | grep -q 'FALLA'; then
            mal "prueba_estados.py tiene verificaciones que fallan" \
                "correrla a mano para ver cuáles: cd ~/TPF/src && python prueba_estados.py"
        else
            bien "prueba_estados.py: $n verificaciones en orden"
        fi
    else
        mal "no está el entorno de Python en $VENV"
    fi
    if pgrep -f "python main.py" >/dev/null; then
        aviso "ya hay una corrida de main.py andando" "si no es a propósito: bash ~/TPF/scripts_pi/demo.sh parar"
    fi
    local libre
    libre=$(df -BG --output=avail "$HOME" | tail -1 | tr -dc '0-9')
    if [ "${libre:-0}" -ge 2 ]; then
        bien "disco: ${libre} GB libres"
    else
        aviso "disco: ${libre} GB libres" "el video de --grabar ocupa; borrar logs viejos"
    fi

    echo "Red"
    bien "este Pi es $(hostname) en $(hostname -I | awk '{print $1}') — anotar la IP por si falla el nombre"

    echo "--------------------------------------------------------------"
    if [ "$problemas" -eq 0 ]; then
        echo " LISTO ($avisos para mirar). Siguiente: demo.sh imagen, y demo.sh ver con el oso a ~1 m."
    else
        echo " HAY $problemas PROBLEMA(S). Resolverlos antes de correr (guía: \"Problemas y qué hacer\")."
    fi
    return "$problemas"
}

# ------------------------------------------------------------------------------
ver() {
    activar
    echo "Mostrando lo que ve la cámara: ex (izq -/der +) y ar (tamaño aparente)."
    echo "El oso a ~1 m tiene que aparecer como 'teddy bear'. Ctrl+C para salir."
    echo "La foto anotada se va guardando en ~/TPF/logs/vivo.jpg"
    echo
    python bench_vision.py --en-vivo
}

correr() {
    local seg="${1:-60}" nota="${2:-demo}"
    activar
    if hay vcgencmd; then
        local t
        t=$(vcgencmd get_throttled | cut -d= -f2)
        if (( 16#${t#0x} & 0x5 )); then
            echo "!! Ojo: el Pi tiene bajo voltaje o recorte AHORA ($t). Va a andar más lento."
            echo
        fi
    fi
    echo "Corrida de $seg s — nota: \"$nota\""
    echo "Parar: Ctrl+C.  Emergencia: desenchufar los 12 V de la UPS (no el Pi)."
    echo
    # Los avisos de libjpeg ("Corrupt JPEG data") son frames con algún bloque
    # dañado por el ruido de los motores: esperables con MJPG y sin efecto en
    # la corrida (config.FORMATO_CAMARA). Se filtran para que no tapen la
    # pantalla; los demás errores pasan igual.
    python main.py --espera 5 --duracion "$seg" --silencioso --nota "$nota" \
        2> >(grep -v -E 'Corrupt JPEG|Invalid SOS|extraneous bytes|Premature end of JPEG' >&2)
    local estado=$?
    echo
    # Si main.py murió antes de registrar nada, `ultima` mostraría el resumen
    # de una corrida VIEJA como si fuera el de ésta (pasó el 2026-10-02, con la
    # webcam desenchufada).
    if [ "$estado" -ne 0 ]; then
        echo "!! La corrida NO se hizo: el programa terminó con error (lo de arriba dice por qué)."
        echo "   Si es la cámara: revisar que la webcam esté enchufada (demo.sh chequeo)."
        return "$estado"
    fi
    ultima
}

# Los avisos de libjpeg ("Corrupt JPEG data") tapan la pantalla y no dicen nada
# que el propio resultado no diga: se filtran. Los demás errores pasan igual.
RUIDO_JPEG='Corrupt JPEG|Invalid SOS|extraneous bytes|Premature end of JPEG'

imagen() {
    # ¿Llegan los frames enteros? Sin motores y sin YOLO. El 2026-10-01 la
    # imagen llegaba en franjas de a ratos con el robot quieto (HARDWARE §0.8).
    activar
    echo "Midiendo la imagen 6 s. Robot quieto; no hace falta el oso."
    SIN_YOLO=1 python "$TPF/scripts_pi/piso/franjas_quieto.py" 6 "$TPF/logs/imagen_chequeo.jpg" \
        2> >(grep -v -E "$RUIDO_JPEG" >&2)
}

fondo() {
    # ¿Algo de la sala se confunde con el oso o con la mochila? Se corre SIN
    # los dos objetos a la vista: todo lo que aparezca es una falsa alarma.
    activar
    echo "Mirando el fondo. Sacar de la vista el oso y la mochila."
    python "$TPF/scripts_pi/piso/que_ve.py" 15 "$TPF/logs/fondo.jpg" \
        2> >(grep -v -E "$RUIDO_JPEG" >&2)
}

grabar() {
    # Igual que `correr`, pero guarda el video de lo que ve el robot (con las
    # cajas y el estado dibujados). Baja ~1 FPS. Al final lo pasa a MP4.
    local seg="${1:-60}" nota="${2:-demo con video}"
    activar
    echo "Corrida de $seg s CON VIDEO — nota: \"$nota\""
    echo "Parar: Ctrl+C.  Emergencia: desenchufar los 12 V de la UPS (no el Pi)."
    echo
    python main.py --espera 5 --duracion "$seg" --silencioso --grabar --nota "$nota" \
        2> >(grep -v -E "$RUIDO_JPEG" >&2)
    local estado=$?
    echo
    # Igual que en `correr`: si no hubo corrida, no mostrar el resumen ni
    # convertir el video de una corrida VIEJA como si fueran los de ésta.
    if [ "$estado" -ne 0 ]; then
        echo "!! La corrida NO se hizo: el programa terminó con error (lo de arriba dice por qué)."
        echo "   Si es la cámara: revisar que la webcam esté enchufada (demo.sh chequeo)."
        return "$estado"
    fi
    ultima
    local avi
    avi=$(ls -t "$TPF"/logs/corrida_*.avi 2>/dev/null | head -1)
    if [ -z "$avi" ]; then
        echo "No quedó ningún video en ~/TPF/logs/."
        return 1
    fi
    if hay ffmpeg; then
        local mp4="${avi%.avi}.mp4"
        if ffmpeg -y -loglevel error -i "$avi" -c:v libx264 -pix_fmt yuv420p \
                  -crf 22 -preset veryfast -movflags +faststart "$mp4"; then
            echo "Video: $mp4"
        else
            echo "No pude convertirlo a MP4. Queda el original: $avi"
        fi
    else
        echo "Video: $avi  (VLC lo abre)"
    fi
    echo "Para traerlo a la notebook: .\\scripts_pi\\traer_corrida.cmd -Video   (desde la PC)"
}

red() {
    echo "Este Pi: $(hostname)   IP: $(hostname -I | awk '{print $1}')"
    if ! hay nmcli; then
        echo "No encuentro nmcli."
        return 1
    fi
    echo "WiFi en uso:"
    nmcli -t -f IN-USE,SSID,CHAN,SIGNAL dev wifi list 2>/dev/null \
        | awk -F: '$1 == "*" {printf "  %s  (canal %s, señal %s de 100)\n", $2, $3, $4; n++}
                   END {if (!n) print "  ninguna"}'
    echo "Redes guardadas (a las que se conecta solo):"
    nmcli -t -f NAME,TYPE connection show | awk -F: '$2 ~ /wireless/ {print "  " $1}'
}

hotspot() {
    # Guarda el hotspot del celular para que el Pi se conecte solo a él. En la
    # sala no va a estar el WiFi de siempre, y sin red no hay forma de entrar.
    local nombre="${1:-}" clave="${2:-}"
    if [ -z "$nombre" ] || [ -z "$clave" ]; then
        echo 'Uso: bash ~/TPF/scripts_pi/demo.sh hotspot "NOMBRE_DEL_HOTSPOT" "CLAVE"'
        return 1
    fi
    if nmcli -t -f NAME connection show | grep -qx "celular"; then
        sudo nmcli connection delete celular >/dev/null
    fi
    if sudo nmcli connection add type wifi con-name celular ifname wlan0 \
            ssid "$nombre" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$clave" \
            connection.autoconnect yes connection.autoconnect-priority 10 >/dev/null; then
        echo "Guardado como 'celular'. La próxima vez que el Pi arranque con ese hotspot"
        echo "encendido, se conecta solo (tiene prioridad sobre las otras redes)."
        echo "Probarlo ANTES del día: apagar el Pi, prender el hotspot, conectar la notebook"
        echo "al hotspot, prender el Pi y entrar con  .\\scripts_pi\\entrar.cmd"
    else
        echo "No se pudo guardar. A mano: sudo nmtui  (Activar una conexión)."
        return 1
    fi
}

ultima() {
    activar
    local csv
    csv=$(ls -t "$TPF"/logs/corrida_*.csv 2>/dev/null | head -1)
    if [ -z "$csv" ]; then
        echo "Todavía no hay corridas registradas en ~/TPF/logs/."
        return 1
    fi
    python analizar_corrida.py "$csv"
}

parar() {
    if pgrep -f "python main.py" >/dev/null; then
        # SIGINT es lo mismo que Ctrl+C: main.py sale por su camino normal,
        # que es el que frena los motores.
        pkill -INT -f "python main.py"
        sleep 2
        pgrep -f "python main.py" >/dev/null && pkill -KILL -f "python main.py"
        echo "Corrida cortada. El ESP32 frena solo si deja de recibir comandos (500 ms)."
    else
        echo "No hay ninguna corrida de main.py andando."
    fi
}

firmware() {
    # Pide al ESP32 sus parámetros (tecla 'e'). El puerto es uno solo: no
    # usarlo con una corrida andando. Tiene que decir
    # "v_min izq/der: 300 / 230": si dice 125 / 112 es el firmware de banco,
    # con el que la rueda izquierda no se mueve apoyada.
    if pgrep -f "python main.py" >/dev/null; then
        echo "Hay una corrida andando: primero demo.sh parar."
        return 1
    fi
    "$VENV/bin/python" - <<'PY'
import time
import serial
s = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.1)
time.sleep(2.2)
# Un salto de linea suelto primero: recien arrancado el Pi, al ESP32 le quedan
# bytes sueltos en la linea a medio armar, y la 'e' pegada a ellos sale como
# "comando desconocido" (paso el 2026-10-02, en el primer uso tras encender).
s.write(bytes([10]))
time.sleep(0.2)
s.reset_input_buffer()
s.write(b"e" + bytes([10]))
time.sleep(0.4)
for linea in s.read_all().decode("ascii", "replace").splitlines():
    if linea.startswith("#"):
        print(linea)
s.close()
PY
}

sonar() {
    # ¿Mide el ultrasónico? Robot quieto, sin motores. Poner algo adelante a
    # una distancia conocida: tiene que dar ese número, estable. Si dice SIN
    # LECTURA, se soltó alguno de los tres cables del sensor (pasó el
    # 2026-10-02) y el robot andaría a ciegas.
    if pgrep -f "python main.py" >/dev/null; then
        echo "Hay una corrida andando: primero demo.sh parar."
        return 1
    fi
    "$VENV/bin/python" "$TPF/scripts_pi/piso/sonar.py" 5
}

apagar() {
    echo "Apagando. Esperar a que el LED verde deje de parpadear (~10 s) antes de"
    echo "desenchufar el cargador. La sesión SSH se va a cortar: es normal."
    sudo shutdown -h now
}

case "${1:-}" in
    chequeo) chequeo ;;
    imagen)  imagen ;;
    ver)     ver ;;
    fondo)   fondo ;;
    sonar)   sonar ;;
    correr)  shift; correr "$@" ;;
    grabar)  shift; grabar "$@" ;;
    ultima)  ultima ;;
    parar)   parar ;;
    firmware) firmware ;;
    red)     red ;;
    hotspot) shift; hotspot "$@" ;;
    apagar)  apagar ;;
    *)
        sed -n '8,20p' "$0" | sed 's/^# \{0,1\}//'
        exit 1 ;;
esac
