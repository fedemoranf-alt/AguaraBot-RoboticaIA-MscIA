"""¿Los motores rompen la imagen? YUYV quieto / YUYV girando / MJPG girando.

"rayado" = fracción de bordes entre filas consecutivas con un salto grande de
brillo medio. Una imagen sana tiene pocos (bordes reales); una con franjas de
paquetes USB perdidos, muchos.
"""
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, "/home/admin/TPF/src")
from enlace_esp32 import Enlace  # noqa: E402
from vision import Detector  # noqa: E402

FASES = [("YUYV", 0, 3.0), ("YUYV", 35, 6.0), ("MJPG", 35, 6.0)]


def rayado(f):
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32)
    salto = np.abs(np.diff(g, axis=0)).mean(axis=1)      # por borde entre filas
    return float((salto > 25).mean())


def abrir(fourcc):
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    real = int(cap.get(cv2.CAP_PROP_FOURCC)).to_bytes(4, "little").decode()
    return cap, real


det = Detector()
filas_grilla = []
with Enlace() as esp:
    for fourcc, v_ang, dur in FASES:
        cap, real = abrir(fourcc)
        for _ in range(5):
            cap.read()
        cuadros, rayas, con_oso, lecturas = [], [], 0, []
        t0 = time.monotonic()
        while time.monotonic() - t0 < dur:
            if v_ang:
                esp.mover(0, v_ang)
            t1 = time.monotonic()
            ok, f = cap.read()
            lecturas.append(time.monotonic() - t1)
            if not ok:
                continue
            d, _ = det.detectar(f)
            n = sum(1 for x in d if x.clase == "teddy bear")
            con_oso += n > 0
            rayas.append(rayado(f))
            cuadros.append(cv2.resize(f, (213, 160)))
        esp.parar()
        cap.release()
        print("%s (pedido %s) motores v_ang=%-2d  %3d frames  %.1f FPS  lectura máx %4.0f ms"
              "  rayado medio %.2f (máx %.2f)  frames con oso %d"
              % (real, fourcc, v_ang, len(rayas), len(rayas) / dur, 1000 * max(lecturas),
                 np.mean(rayas), np.max(rayas), con_oso), flush=True)
        idx = np.linspace(0, len(cuadros) - 1, 6).astype(int)
        filas_grilla.append(np.hstack([cuadros[i] for i in idx]))
        time.sleep(1.5)

cv2.imwrite("/tmp/grilla_diag.jpg", np.vstack(filas_grilla), [cv2.IMWRITE_JPEG_QUALITY, 80])
print("grilla: /tmp/grilla_diag.jpg (una fila por fase)")
