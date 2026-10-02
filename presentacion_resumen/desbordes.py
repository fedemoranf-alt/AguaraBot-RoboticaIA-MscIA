"""Lista las diapositivas cuyo contenido no entra en la página.

Lee TPF_resumen.log después de compilar y, por cada "Overfull \\vbox", dice en
qué archivo de secciones/ está, en qué línea termina el frame y cuál es su
título, ordenadas de la que más se pasa a la que menos.

    python desbordes.py [umbral_en_pt]      # por defecto 2 pt
"""
import re
import sys

umbral = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
log = open("TPF_resumen.log", encoding="latin-1").read()
# pdflatex corta las líneas del log a 79 columnas: se vuelven a unir.
log = re.sub(r"(?<=.{79})\n", "", log)

archivo, hallazgos = None, []
for m in re.finditer(r"\(secciones/([0-9a-z_]+\.tex)|Overfull \\vbox \(([0-9.]+)pt too high\) detected at line (\d+)", log):
    if m.group(1):
        archivo = m.group(1)
    elif archivo and float(m.group(2)) >= umbral:
        hallazgos.append((float(m.group(2)), archivo, int(m.group(3))))

for pt, arch, linea in sorted(hallazgos, reverse=True):
    lineas = open("secciones/" + arch, encoding="utf-8").read().split("\n")
    titulo = "?"
    for k in range(min(linea, len(lineas)) - 1, -1, -1):
        t = re.match(r"\s*\\begin\{frame\}(?:\[[^\]]*\])?\{(.*)\}\s*$", lineas[k])
        if t:
            titulo = t.group(1)
            break
    print("%6.1f pt  %-22s línea %4d  %s" % (pt, arch, linea, titulo))
print("%d diapositivas se pasan %g pt o más" % (len(hallazgos), umbral))

# Lo mismo a lo ancho: líneas o tablas que se salen del margen derecho.
archivo, anchos = None, []
for m in re.finditer(r"\(secciones/([0-9a-z_]+\.tex)|Overfull \\hbox \(([0-9.]+)pt too wide\)[^\n]*?lines? (\d+)", log):
    if m.group(1):
        archivo = m.group(1)
    elif archivo and float(m.group(2)) >= 2 * umbral:
        anchos.append((float(m.group(2)), archivo, int(m.group(3))))
for pt, arch, linea in sorted(anchos, reverse=True):
    print("%6.1f pt de ancho  %-22s línea %4d" % (pt, arch, linea))
print("%d líneas o tablas se pasan %g pt o más de ancho" % (len(anchos), 2 * umbral))
