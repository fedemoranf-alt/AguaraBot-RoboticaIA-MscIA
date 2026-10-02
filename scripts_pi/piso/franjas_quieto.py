"""¿La imagen llega dañada con el robot QUIETO? No toca el ESP32 ni los motores.

Con MJPG, un bloque perdido se decodifica como una franja gris uniforme (el
"Corrupt JPEG data" de libjpeg). Acá se cuenta, frame por frame, qué fracción
de las filas es una franja de ésas, y cuántos frames ven el oso.

    python franjas_quieto.py [segundos] [salida.jpg] [ancho alto]

Sirve para separar dos causas: si hay franjas con los motores parados, el ruido
no viene del PWM (probar con y sin los 12 V enchufados, y moviendo el cable).
"""
import os
import sys
import time

import cv2
import numpy as np

# src/ está dos carpetas más arriba de este archivo, en el Pi y en la PC.
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src")
sys.path.insert(0, SRC)
os.chdir(SRC)                      # los pesos del modelo se buscan desde acá
from vision import Camara, Detector  # noqa: E402

dur = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
salida = sys.argv[2] if len(sys.argv) > 2 else os.path.join(SRC, "..", "logs", "franjas_quieto.jpg")
os.makedirs(os.path.dirname(os.path.abspath(salida)), exist_ok=True)


def franjas(f):
    """Fracción de filas que son gris uniforme (bloque MJPG perdido)."""
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32)
    sat = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)[:, :, 1].astype(np.float32)
    uniforme = (g.std(axis=1) < 4) & (np.abs(g.mean(axis=1) - 128) < 12) & (sat.mean(axis=1) < 12)
    return float(uniforme.mean())


ancho = int(sys.argv[3]) if len(sys.argv) > 4 else None
alto = int(sys.argv[4]) if len(sys.argv) > 4 else None

# SIN_YOLO=1 captura al mismo ritmo pero sin inferencia: separa "la imagen se
# rompe sola" de "se rompe cuando el Pi está cargado".
sin_yolo = os.environ.get("SIN_YOLO") == "1"
det = None if sin_yolo else Detector()
print("inferencia: %s" % ("NO (sólo captura)" if sin_yolo else "sí"))
with Camara(ancho=ancho, alto=alto) as cam:
    print("captura: %s" % (cam.resolucion_real(),))
    for _ in range(5):
        cam.leer()
    cuadros, enteros, fr, cuando, con_oso, lecturas, nulos = [], [], [], [], 0, [], 0
    t0 = time.monotonic()
    while time.monotonic() - t0 < dur:
        t1 = time.monotonic()
        f = cam.leer()
        lecturas.append(time.monotonic() - t1)
        if f is None:
            nulos += 1
            continue
        if det is None:
            time.sleep(0.09)          # el tiempo que tardaría la inferencia
        else:
            d, _ = det.detectar(f)
            con_oso += any(x.clase == "teddy bear" for x in d)
        fr.append(franjas(f))
        cuando.append(t1 - t0)
        enteros.append(f.copy() if len(enteros) < 150 else None)
        cuadros.append(cv2.resize(f, (213, 160)))

fr = np.array(fr)
print("%d frames en %.1f s (%.1f FPS) · lectura p50 %.0f ms, máx %.0f ms · sin frame: %d"
      % (len(fr), dur, len(fr) / dur, 1000 * np.median(lecturas), 1000 * max(lecturas), nulos))
print("franjas: frames limpios %d · con algo (>1 %% de filas) %d · muy dañados (>10 %%) %d"
      % ((fr <= 0.01).sum(), (fr > 0.01).sum(), (fr > 0.10).sum()))
print("franjas: media %.3f · máx %.3f" % (fr.mean(), fr.max()))
if det is not None:
    print("frames con oso: %d de %d" % (con_oso, len(fr)))
# Línea de tiempo: frames con franjas en cada segundo. El daño va y viene, y
# esto muestra cuándo (para cruzarlo con lo que se estaba tocando).
seg = np.array(cuando).astype(int)
print("rotos por segundo: " + " ".join(
    "%d" % (fr[seg == s] > 0.01).sum() for s in range(int(dur))))

idx = np.linspace(0, len(cuadros) - 1, 12).astype(int)
for i in idx:
    cv2.putText(cuadros[i], "#%d %.0f%%" % (i, 100 * fr[i]), (3, 13),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
grilla = np.vstack([np.hstack([cuadros[i] for i in idx[k:k + 4]]) for k in (0, 4, 8)])
cv2.imwrite(salida, grilla, [cv2.IMWRITE_JPEG_QUALITY, 80])
print("grilla: %s" % salida)

# Tres frames a resolución completa, sin anotar: el más dañado, el del medio y
# el más limpio. Son los que sirven para la bitácora y la presentación.
orden = np.argsort(fr[:150])      # sólo los primeros 150 se guardan enteros
base = salida.rsplit(".", 1)[0]
for nombre, i in (("peor", orden[-1]), ("medio", orden[len(orden) // 2]), ("mejor", orden[0])):
    cv2.imwrite("%s_%s.jpg" % (base, nombre), enteros[i], [cv2.IMWRITE_JPEG_QUALITY, 92])
    print("  %s: frame #%d, %.0f %% de filas en franja" % (nombre, i, 100 * fr[i]))

# Veredicto en una línea, para leerlo sin interpretar los números de arriba
# (es lo que usa `demo.sh imagen`). El código de salida es 0 sólo si está sana.
rotos = float((fr > 0.10).mean())
print()
if rotos == 0 and (fr > 0.01).mean() < 0.05:
    print("VEREDICTO: imagen SANA (%d frames, ninguno muy dañado)." % len(fr))
    sys.exit(0)
if rotos < 0.20:
    print("VEREDICTO: imagen DAÑADA A RATOS (%.0f %% de los frames muy dañados). "
          "Se puede correr, pero el robot va a ver peor." % (100 * rotos))
else:
    print("VEREDICTO: imagen ROTA (%.0f %% de los frames muy dañados). "
          "Así el robot está casi ciego." % (100 * rotos))
print("  Qué hacer: desenchufar y enchufar la webcam (USB azul de abajo), revisar que el")
print("  cable no esté tirante, esperar 5 s y medir de nuevo. Mirar: %s" % salida)
sys.exit(1)
