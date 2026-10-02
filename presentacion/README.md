# presentacion

Presentación didáctica de la arquitectura del TPF, en LaTeX Beamer.

> **Es la versión vieja, del diseño.** Se escribió antes de que el robot
> anduviera en el piso: describe lo que se iba a hacer, y sus números son los
> de banco. El ultrasónico y el buzzer que muestra son los del plan (un
> HC-SR04 en los GPIO 18/19, el buzzer en el 4); los que terminaron entrando,
> el 2026-10-02, son otros y van en otros pines (`HARDWARE.md` §9). Las
> vigentes son [`presentacion_resumen/`](../presentacion_resumen/README.md)
> (el resumen completo, 137 páginas) y
> [`presentacion_10min/`](../presentacion_10min/README.md) (la de la
> exposición). Ésta se conserva como registro.

| | |
|---|---|
| Fuente | `TPF_arquitectura.tex` |
| Salida | `TPF_arquitectura.pdf` (58 diapositivas, 16:9) |
| Tema | metropolis |
| Figuras | se toman de `../scripts_auxiliares/figuras/`, que genera el cuaderno 01 |

## Compilar

```bash
pdflatex TPF_arquitectura.tex     # dos veces: la segunda arma el índice
```

O con `latexmk -pdf TPF_arquitectura.tex`, que hace las pasadas solo.

No necesita paquetes fuera de una instalación estándar (beamer, metropolis, tikz,
babel, booktabs, graphicx).

## Antes de mostrarla

- [ ] Revisar el nombre del autor: está en el macro `\autornombre`, arriba de todo.
- [ ] Si se regeneran las figuras del cuaderno 01, recompilar para que entren las nuevas.

## Estructura

1. **El problema** — qué hace el robot y por qué ese problema.
2. **La arquitectura** — el diagrama de bloques completo y cómo leerlo.
3. **Bloque por bloque** — 15 fichas: qué hace, cómo lo hace, con quién habla, estado.
4. **Los recorridos** — la vida de un frame, los tres lazos, qué pasa cuando algo falla.
5. **La máquina de estados** — los cuatro estados y el arbitraje.
6. **La ley de control** — de la caja en la imagen a las dos ecuaciones.
7. **Lo que ya está medido** — la calibración de tracción y la lección metodológica.
8. **Estado y plan** — tablero por bloque, dependencias, riesgos y métricas.
