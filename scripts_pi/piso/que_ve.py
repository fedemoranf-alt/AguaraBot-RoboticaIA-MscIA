"""¿Qué cree YOLO que tiene adelante? Sin motores, sin filtro de clases.

`demo.sh ver` sólo muestra las dos clases de interés por encima del umbral de
trabajo. Cuando un objeto "no aparece", esto dice por qué: lista TODAS las
clases que el modelo propone, con umbral bajo. Así se supo, el 2026-10-01, que
la mochila de la demo es "suitcase" para el modelo.

Termina con un veredicto en castellano: en cuántos frames el robot vería "el
oso" y en cuántos "la mochila", con los alias y umbrales de config.py. Es lo
que usa `demo.sh fondo` para revisar una sala SIN los objetos a la vista: todo
lo que aparezca ahí es una falsa alarma.

    python que_ve.py [frames] [salida.jpg] [--tamanos]

Con --tamanos repite la cuenta a 480 y 640 px además del tamaño de trabajo.
"""
import os
import sys
from collections import defaultdict

import cv2

# src/ está dos carpetas más arriba de este archivo, en el Pi y en la PC.
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src")
sys.path.insert(0, SRC)
os.chdir(SRC)                      # los pesos del modelo se buscan desde acá
import config  # noqa: E402
from vision import Camara, Detector, franjas  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith("--")]
n = int(args[0]) if len(args) > 0 else 15
salida = args[1] if len(args) > 1 else os.path.join(SRC, "..", "logs", "que_ve.jpg")
os.makedirs(os.path.dirname(os.path.abspath(salida)), exist_ok=True)
tamanos = [config.TAM_INFERENCIA]
if "--tamanos" in sys.argv:
    tamanos += [t for t in (480, 640) if t != config.TAM_INFERENCIA]

det = Detector()
with Camara() as cam:
    for _ in range(8):
        cam.leer()
    frames = [cam.leer() for _ in range(n)]
frames = [f for f in frames if f is not None]
if not frames:
    print("La cámara no entregó ningún frame.")
    sys.exit(2)
rotas = max(franjas(f) for f in frames)
print("%d frames · franjas máx %.2f%s" % (
    len(frames), rotas, "  ← imagen dañada: medir con franjas_quieto.py" if rotas > 0.10 else ""))
cv2.imwrite(salida, frames[-1], [cv2.IMWRITE_JPEG_QUALITY, 92])


def rol(nombre):
    """Cómo trata el robot a una clase del modelo: (rol, umbral) o (None, general)."""
    canonica = det.alias.get(nombre, nombre)
    umbral = det.conf_clase.get(canonica, config.UMBRAL_CONFIANZA)
    if canonica == config.CLASE_OBJETIVO:
        return "OSO", umbral
    if canonica == config.CLASE_AMENAZA:
        return "MOCHILA", umbral
    return None, umbral


con_rol = {"OSO": 0, "MOCHILA": 0}
maximo = {"OSO": 0.0, "MOCHILA": 0.0}
for tam in tamanos:
    vistos = defaultdict(list)
    for f in frames:
        r = det.modelo.predict(f, imgsz=tam, conf=0.05, iou=config.UMBRAL_IOU, verbose=False)[0]
        mejores = {}
        for c, k in zip(r.boxes.conf.cpu().numpy(), r.boxes.cls.cpu().numpy().astype(int)):
            nombre = det.nombres[k]
            mejores[nombre] = max(mejores.get(nombre, 0.0), float(c))
        del_frame = set()
        for nombre, c in mejores.items():
            vistos[nombre].append(c)
            papel, umbral = rol(nombre)
            if papel and tam == config.TAM_INFERENCIA:
                maximo[papel] = max(maximo[papel], c)
                if c >= umbral:
                    del_frame.add(papel)
        for papel in del_frame:
            con_rol[papel] += 1
    print("\nimgsz=%d%s" % (tam, "  (el tamaño con que trabaja el robot)"
                            if tam == config.TAM_INFERENCIA else ""))
    if not vistos:
        print("  (el modelo no propone nada)")
    for nombre, cs in sorted(vistos.items(), key=lambda kv: -sum(kv[1]) / len(frames))[:6]:
        papel, umbral = rol(nombre)
        sobre = sum(1 for c in cs if c >= umbral)
        print("  %-14s en %2d de %d frames · conf media %.2f, máx %.2f · sobre su umbral (%.2f): %d%s"
              % (nombre, len(cs), len(frames), sum(cs) / len(cs), max(cs), umbral, sobre,
                 "  ← el robot lo toma por %s" % papel if papel else ""))

print()
print("VEREDICTO: el robot vería el OSO en %d de %d frames (confianza máx %.2f)"
      % (con_rol["OSO"], len(frames), maximo["OSO"]))
print("           y la MOCHILA en %d de %d frames (confianza máx %.2f)."
      % (con_rol["MOCHILA"], len(frames), maximo["MOCHILA"]))
print("  Hacen falta %d frames SEGUIDOS para que reaccione." % config.N_CONFIRMAR)
print("  Si el objeto no está a la vista y aparece igual, es el fondo: sacar o tapar lo que")
print("  se le parezca (bolsos, valijas, objetos oscuros grandes). Foto: %s" % salida)
