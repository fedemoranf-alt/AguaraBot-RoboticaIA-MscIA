# `scripts_pi/piso/` — pruebas con el robot en el piso

Scripts de las tres jornadas en el piso (2026-09-30, 2026-10-01 y 2026-10-02,
[PLAN.md](../../PLAN.md) §13, Días 13 a 15). Corren **en el Pi**;
`provisionar_pi.ps1` los copia a `~/TPF/scripts_pi/piso/`. **Mueven motores**
`corrida_piso.sh`, `escalones.py`, `umbral_piso.py`, `cinetico_piso.py`,
`diag_camara.py`, `paso_giro.py` y `freno_sonar.py`: robot en un espacio
despejado y alguien con la mano en el conector de 12 V. Los demás sólo miran.

Para el uso de todos los días hay atajos en `../demo.sh`: `demo.sh imagen`
llama a `franjas_quieto.py`, `demo.sh fondo` a `que_ve.py` y `demo.sh sonar` a
`sonar.py`.

| Script | Qué hace | Watchdog |
|---|---|---|
| `corrida_piso.sh <etiqueta> <seg> "<nota>" [PARAM=valor ...]` | `main.py` con parámetros de `config.py` cambiados **sólo para esa corrida** (se restauran al terminar, pase lo que pase), y `get_throttled`/`EXT5V_V` cada 0,5 s en `logs/volt_<etiqueta>.txt` | sí |
| `escalones.py` | secuencia de comandos `M` por el protocolo normal (lista `PASOS` al principio). Sirvió para ver qué rueda se calaba y para cronometrar vueltas | sí |
| `umbral_piso.py` | duty **crudo** (modo `C`) por rueda, subiendo: ¿desde qué duty arranca apoyado? | 🔴 **no** |
| `cinetico_piso.py` | duty crudo bajando cada 1 s sin pausas: ¿hasta qué duty sigue girando? | 🔴 **no** |
| `diag_camara.py` | YUYV quieto / YUYV girando / MJPG girando: mide el "rayado" de la imagen y cuenta detecciones; deja una grilla en `/tmp/grilla_diag.jpg` | sí |
| `grilla.py <video.avi> <corrida.csv> <salida.jpg> [primero] [cada]` | grilla de frames de un video de `main.py --grabar`, con el motivo del CSV en cada uno | — |
| `grilla_tiempos.py <video.avi> <corrida.csv> <salida.jpg> t1 t2 ...` | lo mismo, pero con los frames más cercanos a una lista de instantes: qué veía la cámara en cada evento del CSV | — |
| `paso_giro.py "V_ANG:PULSO_S:N" ...` | **mueve motores.** Da pulsos de giro como los de `BUSCAR` y mide con la cámara cuánto se corrió la escena entre pausa y pausa (píxeles, % del ancho, grados). De acá salió `BUSCAR_PASO_GIRO_S` = 0,25 | sí |
| `franjas_quieto.py [seg] [salida.jpg] [ancho alto]` | **sin motores.** ¿La imagen llega rota con el robot quieto? Cuenta frames con franjas grises y con oso, deja una grilla y tres frames enteros (peor, medio, mejor), y termina con un **veredicto** (SANA / DAÑADA A RATOS / ROTA; el código de salida es 0 sólo si está sana). `SIN_YOLO=1` captura sin inferencia | — |
| `franjas_crudo.py [frames] [ancho alto] [fps]` | **sin motores.** Captura MJPG crudo con `v4l2-ctl` y la traza del driver: cruza franjas en la imagen con paquetes USB perdidos según el kernel. Usa `sudo` | — |
| `que_ve.py [frames] [salida.jpg] [--tamanos]` | **sin motores.** Todas las clases que YOLO propone para lo que tiene enfrente, con umbral bajo, y al final un **veredicto**: en cuántos frames el robot vería el oso y en cuántos la mochila, con los alias y umbrales de `config.py`. Con `--tamanos` repite a 480 y 640 px. Así se supo que la mochila es "suitcase" | — |

| `sonar.py [seg]` | **sin motores.** Lee la distancia del ultrasónico de la telemetría durante unos segundos (5 por defecto), segundo a segundo, y resume: lecturas válidas, mínima, mediana y máxima. Termina con SIN LECTURA si el sensor no contesta. Ojo: ~370 cm es "nada adelante", no una distancia | — |
| `freno_sonar.py [v_lin] [umbral_cm] [seg_max]` | **mueve motores.** Avanza derecho hacia lo que tenga adelante y frena cuando el ultrasónico lee el umbral o menos; informa a cuántos cm mandó frenar y a cuántos quedó parado. No arranca si no hay lectura. De acá salió que a velocidad 40 la inercia son 3 cm | sí |

Las corridas del 2026-10-01 ([PLAN.md](../../PLAN.md) §13 Día 14) se lanzaron con
`GRABAR=1 bash corrida_piso.sh ...`, que además guarda el video anotado.

Los que usan modo `C` dejan el ESP32 **sin watchdog** mientras corren; el
`finally` lo devuelve a protocolo (`x`, `p`). Si algo queda girando: 12 V afuera.

Uso típico:

```bash
cd ~/TPF/scripts_pi/piso
bash corrida_piso.sh aprox1 25 "oso a 1 m a 90° izquierda"
bash corrida_piso.sh buscar15 15 "vueltas" BUSCAR_GIRO_S=15.0 BUSCAR_PASO_MIRAR_S=0
~/TPF/.venv/bin/python escalones.py
```
