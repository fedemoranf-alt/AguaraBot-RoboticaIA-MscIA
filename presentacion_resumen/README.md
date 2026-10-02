# presentacion_resumen

Resumen completo del TPF en LaTeX Beamer, **para uso propio**: cómo funciona la
arquitectura, qué hace cada archivo, qué hace cada parámetro y de dónde salió
cada número. Refleja el estado al **2026-10-02** (demo completa andando en el
piso, con ultrasónico y buzzer). No es para proyectar: tiene más texto que una presentación normal.

| | |
|---|---|
| Fuente | `TPF_resumen.tex` (preámbulo) + `secciones/*.tex` (el contenido) |
| Salida | `TPF_resumen.pdf` — 137 páginas (121 diapositivas + portada y separadores), 16:9 |
| Tema | metropolis, letra base de 9 pt |
| Figuras | `figuras/` — copias reducidas y recortes de `Fotos del bot/`, `scripts_auxiliares/figuras/`, `media/` y `logs/` |

## Compilar

Con MiKTeX, desde esta carpeta (dos pasadas: la segunda arma el índice):

```bash
python arreglar_grupos.py          # sólo si se editó alguna sección
pdflatex TPF_resumen.tex
pdflatex TPF_resumen.tex
python desbordes.py                # ¿alguna diapositiva se pasa de la página?
```

Usa `pdflatex`, no XeLaTeX (el tema avisa que prefiere XeLaTeX por la
tipografía; con pdflatex compila igual). Paquetes: beamer, metropolis, tikz,
babel, booktabs, microtype, graphicx.

## Las secciones

| Archivo | Qué cubre |
|---|---|
| `01_panorama` | Objetivo, qué hace hoy, los números de un vistazo, alcance, decisiones de diseño |
| `02_hardware` | Inventario, fotos, alimentación, cableado, L298, motores y calibración, cámara, Pi |
| `03_arquitectura` | Los dos niveles, la vida de un frame, los relojes, las dos reglas, qué pasa si algo falla |
| `04_archivos` | El mapa del proyecto y una ficha por archivo de `src/` |
| `05_firmware` | El lazo del ESP32, de `M` al duty, constantes, watchdog, modos, cómo se graba |
| `06_estados` | Los cuatro estados, las reglas, `BUSCAR`, `APROXIMAR`, `HUIR`, el arbitraje |
| `07_control` | Las ecuaciones, qué pide la ley con números, por qué cada pieza, ganancia y retardo |
| `08_parametros` | **Cada parámetro de `config.py`**: valor, qué hace, de dónde sale; y "si pasa esto, tocar aquello" |
| `09_protocolo` | El protocolo serie y las redes de seguridad |
| `10_scripts` | `scripts_pi/`, `demo.sh`, `piso/`, cómo leer el análisis de una corrida |
| `11_historia` | Las 15 jornadas y las mediciones (visión, energía, movimiento, métricas) |
| `12_problemas` | Todo lo que falló y cómo se resolvió; los 21 casos del hilo conductor |
| `13_jornada` | El 1 de octubre en el piso, con imágenes de la cámara del robot |
| `13b_ultrasonico` | El 2 de octubre: fotos del robot terminado, cableado del ultrasónico y el buzzer, el sensor muerto, los tres ajustes de piso |
| `14_operacion` | Cómo se opera, estado por bloque, pendientes, segunda versión, glosario |

## Dos trampas al editar

1. **Una diapositiva no puede empezar con una llave.** En beamer,
   `\begin{frame}{Título}{...}` toma el segundo grupo como *subtítulo*, y el
   tema metropolis no lo muestra: una tabla envuelta en `{\footnotesize ...}`
   al principio del frame **desaparece sin dar error**. Por eso los frames
   empiezan con `\relax{...`. `arreglar_grupos.py` lo corrige solo.
2. **`\cod{...}`** (el atajo para nombres de archivo y parámetros) deja pasar
   los guiones bajos, pero **no puede llevar `%` ni `#`** adentro. Para esos
   casos, `\texttt{\#}` o `\verb` en un frame `[fragile]`.

`desbordes.py` lee el `.log` y lista las diapositivas que se pasan del alto o
del ancho de la página, con su título.

## Para mantenerla al día

Los números salen de `PLAN.md` (§13, la bitácora), `HARDWARE.md`, los
comentarios de `src/config.py` y los registros de `logs/`. Si cambian los
parámetros, las secciones a revisar son `07_control` (las tablas numéricas),
`08_parametros` y `13_jornada` (la tabla de "lo que cambió").
