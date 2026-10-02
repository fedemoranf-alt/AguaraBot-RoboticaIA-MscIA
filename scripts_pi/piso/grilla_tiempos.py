"""Grilla con los frames de un video de `main.py --grabar` más cercanos a una
lista de instantes. Para mirar QUÉ veía la cámara en un evento del CSV.

    python grilla_tiempos.py <video.avi> <corrida.csv> <salida.jpg> t1 t2 t3 ...
"""
import csv
import sys

import cv2
import numpy as np

video, csv_ruta, salida = sys.argv[1], sys.argv[2], sys.argv[3]
tiempos = [float(x) for x in sys.argv[4:]]

filas = list(csv.DictReader(open(csv_ruta, encoding="utf-8")))
ts = np.array([float(r["t_s"]) for r in filas])
quiero = sorted({int(np.abs(ts - t).argmin()) for t in tiempos})

cap = cv2.VideoCapture(video)
cuadros, i = [], 0
while quiero and i <= quiero[-1]:
    ok, f = cap.read()
    if not ok:
        break
    if i in quiero:
        f = cv2.resize(f, (320, 240))
        r = filas[i]
        txt = "#%d t=%s %s %s" % (i, r["t_s"], r["estado"][:5], r["motivo"][:16])
        cv2.rectangle(f, (0, 0), (320, 18), (0, 0, 0), -1)
        cv2.putText(f, txt, (3, 13), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        cuadros.append(f)
    i += 1
while len(cuadros) % 4:
    cuadros.append(np.zeros((240, 320, 3), np.uint8))
grilla = np.vstack([np.hstack(cuadros[k:k + 4]) for k in range(0, len(cuadros), 4)])
cv2.imwrite(salida, grilla, [cv2.IMWRITE_JPEG_QUALITY, 80])
print("%d frames -> %s" % (len(quiero), salida))
