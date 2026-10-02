# Imagen rota con el robot quieto — 2026-10-01

Evidencia de la segunda jornada en el piso ([PLAN.md](../../PLAN.md) §13). La
Aproximación 1 (oso a 1 m, a 90° a la izquierda, 25 s) terminó sin una sola
detección en 242 frames. Buscando por qué, apareció que **la webcam USB entrega
frames dañados aunque los motores estén parados**: franjas grises horizontales,
que son bloques MJPG perdidos en el camino.

Todas las imágenes son de la LifeCam Studio a 640×480 en MJPG, con el robot en
el piso mirando al oso impreso a ~1 m (salvo la 01, sobre el escritorio). Las
horas son aproximadas.

## Qué muestra cada archivo

"Rotos" = frames con más del 10 % de sus filas convertidas en franja gris.
Las grillas son 12 frames repartidos a lo largo de la medición, con el número
de frame y el porcentaje de filas dañadas en rojo.

| Archivo | Condición | Frames rotos | Frames con oso |
|---|---|---|---|
| `01_1518_escritorio_sana…` | sobre el escritorio, 12 V desenchufados | 0 (imagen sana) | todos, conf. 0,91 |
| `02_1523_piso_tras_corrida…` | piso, justo después de la corrida | dos franjas finas | — (miraba una pared) |
| `03_1527_piso_quieto…` | piso, motores parados | un frame muy roto | — |
| `04_1528_grilla_con12v…` | 12 V enchufados, motores parados | **69 de 71** | 4 de 71 |
| `05_1530_grilla_con12v…` | ídem | 5 de 48 | 45 de 48 |
| `06_1532_grilla_con12v…` | ídem | **41 de 50** | 14 de 50 |
| `07_1535_grilla_con12v…` | ídem | **39 de 47** | 16 de 47 |
| `08_1540_…sin12v…` | **12 V desenchufados** | **48 de 72** | 26 de 72 |
| `09_1541_…sin12v…` | ídem | 18 de 69 | 60 de 69 |
| `10_1542_…sin12v…` | ídem | 35 de 69 | 46 de 69 |
| `11_1543_…sin_yolo…` | sin 12 V, **sin inferencia** (sólo captura) | 9 de 82 | (no se corrió YOLO) |
| `12_1543_…con_yolo…` | sin 12 V, con inferencia | **71 de 71** | 14 de 71 |
| `13_1552_…con12v_60s…` | 12 V enchufados, 60 s seguidos — **el problema ya se había ido solo** | **0 de 606** | 606 de 606 |

Los `…_frame_peor…`, `…_frame_medio…` y `…_frame_limpio…` son frames sueltos a
resolución completa y sin anotar, elegidos de la medición del mismo número.

## Lo que la evidencia descarta

- **No es el PWM de los motores**: pasa con los motores parados.
- **No es la fuente de 12 V**: con la UPS desenchufada sigue igual (08-10).
- **No es la carga del procesador**: hay frames rotos capturando sin YOLO (11),
  y con YOLO una medición salió limpia (2 de 69) y la siguiente rota entera
  (12), diez segundos después.
- **No es la alimentación del Pi**: `get_throttled = 0x0` todo el tiempo,
  `EXT5V_V` entre 4,97 y 5,14 V.

El daño es **intermitente**, en escalas de segundos a minutos, con el robot sin
tocar. En el kernel quedaron además timeouts de control con la webcam
(`uvcvideo: Failed to set UVC probe control : -110`) que colgaron dos
mediciones.

Después de las 15:50 no volvió a aparecer en el resto de la tarde: 0 frames con
franjas en las ocho corridas siguientes (2104 frames) y 10 de 889 en la novena.
Nadie tocó los cables entre una cosa y la otra. El análisis completo está en
[HARDWARE.md](../../HARDWARE.md) §0.8.

## Lo que falta separar

Cable o conector de la webcam, la propia webcam, o el presupuesto de corriente
de los puertos USB (con el cargador portátil el Pi los limita a 600 mA, y la
webcam declara 500 mA y el ESP32 100 mA: justo el total).

## Cómo se midió

`scripts_pi/piso/franjas_quieto.py` (no toca el ESP32 ni los motores). Los
registros de la corrida fallida están en `logs/corrida_20261001_152132.csv`
y `.json`.
