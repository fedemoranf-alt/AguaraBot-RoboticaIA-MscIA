"""Grilla de frames de un .avi, con el número de frame y el motivo del CSV."""
import csv
import sys

import cv2
import numpy as np

video, csv_ruta, salida = sys.argv[1], sys.argv[2], sys.argv[3]
primero = int(sys.argv[4]) if len(sys.argv) > 4 else 0
cada = int(sys.argv[5]) if len(sys.argv) > 5 else 4
n = 24

filas = list(csv.DictReader(open(csv_ruta, encoding="utf-8")))
cap = cv2.VideoCapture(video)
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
cuadros = []
i = 0
while len(cuadros) < n:
    ok, f = cap.read()
    if not ok:
        break
    if i >= primero and (i - primero) % cada == 0:
        f = cv2.resize(f, (320, 240))
        r = filas[i] if i < len(filas) else {}
        txt = "#%d t=%s %s v_ang=%s" % (i, r.get("t_s", "?"), r.get("motivo", "")[:10], r.get("v_ang", "?"))
        cv2.rectangle(f, (0, 0), (320, 18), (0, 0, 0), -1)
        cv2.putText(f, txt, (3, 13), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        cuadros.append(f)
    i += 1
while len(cuadros) % 4:
    cuadros.append(np.zeros((240, 320, 3), np.uint8))
grilla = np.vstack([np.hstack(cuadros[k:k + 4]) for k in range(0, len(cuadros), 4)])
cv2.imwrite(salida, grilla, [cv2.IMWRITE_JPEG_QUALITY, 80])
print("frames en el video: %d · filas CSV: %d · grilla: %s" % (total, len(filas), salida))
