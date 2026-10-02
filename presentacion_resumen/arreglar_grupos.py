"""Evita que beamer se coma el primer grupo de una diapositiva como subtítulo.

En beamer, `\\begin{frame}{Título}{...}` toma el SEGUNDO grupo entre llaves
como subtítulo del frame. Si el cuerpo de la diapositiva empieza con un grupo
(`{\\footnotesize ... }` alrededor de una tabla, por ejemplo), ese grupo entero
desaparece: se vuelve un subtítulo que el tema metropolis no muestra.

Este script recorre secciones/*.tex y, donde el cuerpo de un frame empieza con
una llave, le antepone `\\relax`, que corta la búsqueda del subtítulo sin
cambiar nada más. Es idempotente: se puede correr todas las veces que haga
falta, y conviene correrlo antes de compilar si se editó alguna sección.

    python arreglar_grupos.py
"""
import glob
import re

total = 0
for ruta in sorted(glob.glob("secciones/*.tex")):
    lineas = open(ruta, encoding="utf-8").read().split("\n")
    cambios = 0
    for i, linea in enumerate(lineas):
        if not re.match(r"\s*\\begin\{frame\}", linea):
            continue
        j = i + 1
        while j < len(lineas) and not lineas[j].strip():
            j += 1
        if j < len(lineas) and lineas[j].lstrip().startswith("{"):
            sangria = lineas[j][: len(lineas[j]) - len(lineas[j].lstrip())]
            lineas[j] = sangria + "\\relax" + lineas[j].lstrip()
            cambios += 1
    if cambios:
        open(ruta, "w", encoding="utf-8", newline="\n").write("\n".join(lineas))
        print("%s: %d diapositivas corregidas" % (ruta, cambios))
    total += cambios
print("total: %d" % total)
