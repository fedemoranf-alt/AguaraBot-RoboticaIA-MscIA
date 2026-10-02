# presentacion_10min

La presentación para **exponer ante profesores y compañeros, en 10 minutos
como máximo**. LaTeX Beamer, pensada para proyectar: poco texto, letra grande,
imágenes de la cámara del robot.

| Archivo | Qué es |
|---|---|
| `TPF_presentacion.pdf` | Lo que se proyecta: 14 diapositivas para exponer + 5 de respaldo |
| `TPF_presentacion.tex` | La fuente (un solo archivo) |
| `GUION.md` | **Qué decir en cada diapositiva y cuánto tarda** (suma 9:15), preguntas probables y qué recortar si falta tiempo |
| `demo_vista_del_robot.mp4` | Video de 20 s para pasar en la diapositiva 9: busca el oso y se acerca; ve la mochila y huye. Visto desde la cámara del robot, a velocidad real, **sin sonido**. Es del 01/10, de antes del ultrasónico |
| `figuras/` | Las imágenes de las diapositivas |

## Estructura

1. El problema · 2. El robot · 3. Arquitectura · 4. La IA · 5. El
comportamiento · 6. El control · 7. Del banco al piso · 8-9. Resultados (con
el video) · 10. Lo que se midió · 11. La lección · 12. Límites y futuro.

Después de "Gracias" hay cinco diapositivas de **respaldo** que no se
presentan: parámetros, seguridad y protocolo, la imagen rota, los motores, y
cómo se trabajó. Están para contestar preguntas.

## Compilar

Con MiKTeX, desde esta carpeta, dos pasadas:

```bash
pdflatex TPF_presentacion.tex
pdflatex TPF_presentacion.tex
```

El aviso `Overfull \vbox` de la portada es del tema y no se ve.

**Al editar:** el cuerpo de una diapositiva no puede empezar con una llave
`{`; beamer la toma como subtítulo y ese contenido desaparece sin dar error.

## De dónde salen las cosas

- Los números son los del **2026-10-01** (`PLAN.md` §13, Día 14), más lo del
  ultrasónico y el buzzer, del **2026-10-02** (Día 15): la foto del robot, la
  regla de los 30 cm, la fila "Distancia a una pared, huyendo" y los límites.
  Si se hacen las 10 corridas por escenario antes de exponer, actualizar la
  diapositiva 10 ("Lo que se midió"), que hoy dice que esa serie falta.
- Las tiras de imágenes son fotogramas de `logs/corrida_20261001_162944.avi`
  (oso) y `logs/corrida_20261001_165457.avi` (mochila). El video está armado
  con tramos de esas dos corridas.
- La foto del robot es `figuras/robot_terminado.jpg`: el robot terminado, el
  2026-10-02 (original en `../Fotos del bot/bot_terminado1.jpeg`; hay otras
  dos tomas ahí). `figuras/robot.jpg`, la del banco de pruebas de agosto, ya
  no se usa.
- Hay un segundo video, del 02/10 y ya con el ultrasónico, en
  `../media/2026-10-02_demo_con_ultrasonico_y_buzzer_vista_del_robot.mp4`: la
  acción está en los primeros 8 segundos (huye, esquiva una pared, encuentra
  el oso). No reemplaza al de 20 s, que muestra mejor la búsqueda.
- El detalle completo de todo lo que acá se menciona en una línea está en
  `../presentacion_resumen/TPF_resumen.pdf`.
