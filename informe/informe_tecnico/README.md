# informe_tecnico

Informe técnico del Proyecto Final, escrito sobre la plantilla de la cátedra
(`../Plantilla-InformeTecnico-ProyectoIARM/`, formato Springer Nature, clase
`sn-jnl.cls`). La plantilla original no se tocó.

| Archivo | Qué es |
|---|---|
| `informe_tecnico.pdf` | **El informe** (22 páginas) |
| `informe_tecnico.tex` | La fuente, un solo archivo |
| `sn-jnl.cls` | La clase de la plantilla, copiada tal cual |
| `figuras/` | Fotos del robot, imágenes de su cámara y gráficos |
| `generar_figuras.py` | Regenera los tres gráficos (`fig_*.pdf`) desde los registros de `../../logs/` |

## Compilar

Con MiKTeX, desde esta carpeta, dos pasadas:

```bash
pdflatex informe_tecnico.tex
pdflatex informe_tecnico.tex
```

La clase necesita el paquete `sttools` (archivo `cuted.sty`), que no viene
instalado por defecto: `miktex packages install sttools`. Si el PDF está
abierto en un visor, `pdflatex` no puede escribirlo: cerrarlo antes.

Para regenerar los gráficos (hace falta `matplotlib`):

```bash
python generar_figuras.py
```

## Qué revisar antes de entregar

- **Autores y correos.** Figuran Federico Morán y Juan Barboza, cada uno con
  su correo (`\email{...}` debajo de su `\author`).
- **Afiliación.** Quedó la de la plantilla: "Maestría en Ciencias de la
  Ingeniería, Facultad de Ingeniería, UNA". Si la carrera es otra, cambiar
  `\orgdiv`.
- **Contribución de los integrantes.** El texto dice que los dos participaron
  en todo. La plantilla pide declarar qué hizo cada uno: ajustarlo.
- **Uso de herramientas de IA generativa.** Declara el uso de Claude (Claude
  Code) para programación, pruebas remotas, documentación y redacción del
  informe. Es una declaración de los autores: leerla y corregirla si no
  refleja lo que se quiere declarar.
- **Disponibilidad del código.** Da el enlace del repositorio
  (<https://github.com/fedemoranf-alt/AguaraBot-RoboticaIA-MscIA>) y dice que
  es público: confirmar que lo sea antes de entregar el informe.
- **Referencias.** Las doce son reales, pero conviene abrir los enlaces DOI y
  confirmar páginas y año antes de entregar.
- **Nombre del robot.** "Aguará" ("zorro" en guaraní). Está en el título, el
  resumen y la introducción.

## De dónde sale cada número

Todo sale de la bitácora de trabajo (que no está en el repositorio), de
`../../HARDWARE.md` y de los registros de `../../logs/`:

- Las 16 corridas "de puesta a punto" son los CSV del 1 de octubre y de la
  mañana del 2 de octubre de 2026 que están en `logs/`.
- Las 8 corridas "de operación independiente" son las de la tarde del 2 de
  octubre (13:46 a 14:21), que hizo uno de los autores por su cuenta. Tres son
  anteriores al cambio en el sentido de la búsqueda tras la evasión (el código
  nuevo llegó al robot a las 13:58) y cinco, posteriores. Sus CSV también
  están en `logs/`.
- La figura de la aproximación usa `corrida_20261002_104127`; la de las
  evasiones, `corrida_20261002_103658` y `corrida_20261002_105908`.

Lo que el informe dice sin rodeos y conviene tener presente en la defensa:

- No se hizo la serie de 10 corridas por escenario: ninguna tasa es
  estadística.
- En operación independiente el robot no llegó al objetivo en ninguna de las
  tres corridas anteriores al cambio en la búsqueda, y llegó en tres de las
  cinco posteriores. Las condiciones no se controlaron: la comparación es
  indicativa.
- En espacios reducidos el ultrasónico llegó a marcar 3 cm mientras el robot
  giraba para esquivar: quedó prácticamente en contacto con el obstáculo.
- Las imágenes dañadas reaparecieron la última tarde (33 de 3793).
