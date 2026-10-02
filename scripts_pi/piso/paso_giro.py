"""¿Cuánto gira el robot en cada paso del barrido? Lo mide la propia cámara.

MUEVE MOTORES (gira en el lugar). Da pulsos de giro como los de BUSCAR a pasos
y, en cada pausa, guarda un frame con el robot quieto. Después compara cada
frame con el anterior: el corrimiento horizontal de la escena, en píxeles, es
lo que giró. Lo que decide si el barrido tiene huecos es justamente eso —
cuánto de la imagen se renueva en cada paso— y no hace falta saber el campo
visual para leerlo. Los grados que imprime suponen config.FOV_H_GRAD.

    python paso_giro.py "V_ANG:PULSO_S:N" ["V_ANG:PULSO_S:N" ...]
    python paso_giro.py 35:0.4:5 35:0.25:5 10:0.4:5

El pulso se manda y se corta en el acto (sin esperar al latido de 10 Hz), así
que mide el pulso pedido y no el pedido más el retardo del enlace.
"""
import math
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, "/home/admin/TPF/src")
import config  # noqa: E402
from enlace_esp32 import Enlace  # noqa: E402
from vision import Camara, franjas  # noqa: E402

PAUSA_S = 0.9
tandas = [(int(a), float(b), int(c)) for a, b, c in
          (t.split(":") for t in (sys.argv[1:] or ["35:0.4:5"]))]

orb = cv2.ORB_create(1500)
bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
FOCAL_PX = (config.ANCHO_CAPTURA / 2) / math.tan(math.radians(config.FOV_H_GRAD / 2))


def corrimiento(a, b):
    """Píxeles que la escena se corrió hacia la IZQUIERDA entre a y b (giro a
    la derecha = positivo). None si no hay solapamiento suficiente."""
    # Sólo la mitad de arriba: lo lejano. El piso cercano tiene paralaje, porque
    # la cámara no está sobre el eje de giro.
    alto = a.shape[0] // 2
    ka, da = orb.detectAndCompute(cv2.cvtColor(a[:alto], cv2.COLOR_BGR2GRAY), None)
    kb, db = orb.detectAndCompute(cv2.cvtColor(b[:alto], cv2.COLOR_BGR2GRAY), None)
    if da is None or db is None:
        return None, 0
    dx = [ka[m.queryIdx].pt[0] - kb[m.trainIdx].pt[0] for m in bf.match(da, db)
          if abs(ka[m.queryIdx].pt[1] - kb[m.trainIdx].pt[1]) < 25]
    if len(dx) < 12:
        return None, len(dx)
    dx = np.array(dx)
    med = np.median(dx)
    cerca = np.abs(dx - med) < 15
    if cerca.sum() < 10:                      # sin consenso: emparejó ruido
        return None, int(cerca.sum())
    return float(np.median(dx[cerca])), int(cerca.sum())


def quieto(cam, segundos):
    """Lee frames durante `segundos` (vacía la cola) y devuelve el último."""
    ultimo, t0 = None, time.monotonic()
    while time.monotonic() - t0 < segundos:
        f = cam.leer()
        if f is not None:
            ultimo = f
    return ultimo


cuadros, etiquetas = [], []
with Camara() as cam, Enlace() as esp:
    print(esp.describir(), flush=True)
    previo = quieto(cam, 1.0)
    cuadros.append(previo)
    etiquetas.append("inicio")
    try:
        for v_ang, pulso, n in tandas:
            pasos = []
            for i in range(n):
                t0 = time.monotonic()
                esp.mover(0, v_ang)
                esp._escribir("M,0,%d\n" % v_ang)        # ya, sin esperar al latido
                while time.monotonic() - t0 < pulso:
                    esp.mover(0, v_ang)                   # mantiene vigente el comando
                    time.sleep(0.01)
                esp.parar()
                real = time.monotonic() - t0
                actual = quieto(cam, PAUSA_S)
                px, n_ok = corrimiento(previo, actual)
                pasos.append(px)
                grados = None if px is None else math.degrees(math.atan(px / FOCAL_PX))
                print("v_ang %2d pulso %.2f s (real %.3f) paso %d: %s  [%d puntos, franjas %.2f]"
                      % (v_ang, pulso, real, i + 1,
                         "sin solapamiento (giró demasiado o imagen rota)" if px is None
                         else "%4.0f px = %2.0f %% del ancho ≈ %4.1f°"
                         % (px, 100 * px / actual.shape[1], grados),
                         n_ok, franjas(actual)), flush=True)
                cuadros.append(actual)
                etiquetas.append("v%d p%.2f #%d" % (v_ang, pulso, i + 1))
                previo = actual
            ok = [p for p in pasos if p is not None]
            if ok:
                med = float(np.median(ok))
                print("  → v_ang %d, pulso %.2f s: mediana %.0f px = %.0f %% del ancho ≈ %.0f° por paso"
                      " (mín %.0f, máx %.0f px; %d de %d medidos)\n"
                      % (v_ang, pulso, med, 100 * med / config.ANCHO_CAPTURA,
                         math.degrees(math.atan(med / FOCAL_PX)), min(ok), max(ok), len(ok), n),
                      flush=True)
            time.sleep(1.0)
    finally:
        esp.parar()

chicos = []
for f, e in zip(cuadros, etiquetas):
    c = cv2.resize(f, (213, 160))
    cv2.rectangle(c, (0, 0), (213, 14), (0, 0, 0), -1)
    cv2.putText(c, e, (3, 11), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1)
    chicos.append(c)
while len(chicos) % 6:
    chicos.append(np.zeros((160, 213, 3), np.uint8))
grilla = np.vstack([np.hstack(chicos[k:k + 6]) for k in range(0, len(chicos), 6)])
ruta = "/home/admin/TPF/logs/paso_giro_%s.jpg" % time.strftime("%H%M%S")
cv2.imwrite(ruta, grilla, [cv2.IMWRITE_JPEG_QUALITY, 80])
print("grilla de las pausas: %s" % ruta)
