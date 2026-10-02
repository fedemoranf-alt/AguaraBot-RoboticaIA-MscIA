"""¿Los frames MJPG ya vienen rotos de la cámara, o se rompen en el USB?

Captura MJPG crudo con v4l2-ctl (sin OpenCV, sin YOLO, sin tocar el ESP32) con
la traza del driver uvcvideo encendida, y cruza dos cosas:

  - lo que dice el kernel: paquetes USB perdidos ("isochronous frame lost") o
    frames que la cámara marcó con error ("error bit set");
  - lo que dice la imagen: qué fracción de las filas de cada frame decodificado
    es una franja gris.

Si hay franjas y el kernel no perdió nada, el daño viene de adentro de la
cámara. Necesita sudo (traza y dmesg).

    python franjas_crudo.py [frames] [ancho alto] [fps]
"""
import subprocess
import sys

import cv2
import numpy as np

n = int(sys.argv[1]) if len(sys.argv) > 1 else 150
ancho = int(sys.argv[2]) if len(sys.argv) > 3 else 640
alto = int(sys.argv[3]) if len(sys.argv) > 3 else 480
fps = int(sys.argv[4]) if len(sys.argv) > 4 else 30
CRUDO = "/tmp/crudo.mjpg"
TRAZA = "/sys/module/uvcvideo/parameters/trace"


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout


def franjas(f):
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32)
    sat = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)[:, :, 1].astype(np.float32)
    uniforme = (g.std(axis=1) < 4) & (np.abs(g.mean(axis=1) - 128) < 12) & (sat.mean(axis=1) < 12)
    return float(uniforme.mean())


sh("sudo dmesg -C; echo 128 | sudo tee %s" % TRAZA)
sh("v4l2-ctl -d /dev/video0 --set-fmt-video=width=%d,height=%d,pixelformat=MJPG "
   "--set-parm=%d --stream-mmap --stream-count=%d --stream-to=%s" % (ancho, alto, fps, n, CRUDO))
sh("echo 0 | sudo tee %s" % TRAZA)
kernel = sh("sudo dmesg")

datos = open(CRUDO, "rb").read()
cortes = []
i = datos.find(b"\xff\xd8\xff")
while i != -1:
    cortes.append(i)
    i = datos.find(b"\xff\xd8\xff", i + 3)
cortes.append(len(datos))

tam, fr, ilegibles, rst = [], [], 0, []
for a, b in zip(cortes[:-1], cortes[1:]):
    jpg = datos[a:b]
    tam.append(len(jpg))
    rst.append(sum(jpg.count(bytes([0xFF, 0xD0 + k])) for k in range(8)))
    f = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
    if f is None:
        ilegibles += 1
        continue
    fr.append(franjas(f))

tam, fr, rst = np.array(tam), np.array(fr), np.array(rst)
print("%dx%d a %d FPS pedidos: %d frames crudos" % (ancho, alto, fps, len(tam)))
print("tamaño del JPEG: mín %d · p50 %d · máx %d bytes  (%.1f Mbit/s a %d FPS)"
      % (tam.min(), np.median(tam), tam.max(), np.median(tam) * 8 * fps / 1e6, fps))
print("marcadores de reinicio por frame: mín %d · p50 %d · máx %d" % (rst.min(), np.median(rst), rst.max()))
print("imagen: limpios %d · con franjas (>1 %% de filas) %d · muy dañados (>10 %%) %d · ilegibles %d"
      % ((fr <= 0.01).sum(), (fr > 0.01).sum(), (fr > 0.10).sum(), ilegibles))
print("kernel: frames completos %d · paquetes USB perdidos %d · frames con bit de error %d"
      % (kernel.count("Frame complete"), kernel.count("frame lost"), kernel.count("error bit")))
