#!/usr/bin/env bash
# Corrida de piso con parámetros temporales y registro de voltaje en paralelo.
#   bash ~/TPF/scripts_pi/piso/corrida_piso.sh <etiqueta> <duracion> "<nota>" [PARAM=valor ...]
# Los PARAM se aplican a una copia de config.py y se restauran al terminar,
# pase lo que pase.
# Con GRABAR=1 delante, main.py guarda además el video anotado (baja el FPS):
#   GRABAR=1 bash corrida_piso.sh barrido 12 "qué ve en cada pausa"
set -u
etiqueta="$1"; duracion="$2"; nota="$3"; shift 3
cd ~/TPF/src || exit 1
cp config.py /tmp/config.py.bak
restaurar() {
    cp /tmp/config.py.bak config.py
    [ -n "${volt_pid:-}" ] && kill "$volt_pid" 2>/dev/null
}
trap restaurar EXIT

for par in "$@"; do
    nombre="${par%%=*}"; valor="${par#*=}"
    sed -i "s/^${nombre} = [^ ]*/${nombre} = ${valor}/" config.py
    grep -n "^${nombre} = " config.py
done

volt_log=../logs/volt_${etiqueta}.txt
( while :; do
    echo "$(date +%T.%N | cut -c1-12) $(vcgencmd get_throttled) $(vcgencmd pmic_read_adc EXT5V_V | awk '{print $2}') $(vcgencmd measure_temp)"
    sleep 0.5
  done > "$volt_log" ) &
volt_pid=$!

source ../.venv/bin/activate
grabar=""; [ "${GRABAR:-0}" = "1" ] && grabar="--grabar"
python main.py --espera 5 --duracion "$duracion" --silencioso --nota "$nota" $grabar

kill "$volt_pid" 2>/dev/null; volt_pid=""
echo
echo "== voltaje durante la corrida ($volt_log) =="
awk '{print $2}' "$volt_log" | sort | uniq -c
awk '{v=$3; sub(/V.*/,"",v); sub(/.*=/,"",v); if(min==""||v<min)min=v; if(v>max)max=v} END{print "EXT5V_V min " min "  max " max}' "$volt_log"
tail -1 "$volt_log"
