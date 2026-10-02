# scripts_auxiliares

Cuadernos de análisis del TPF. Cada uno toma los **datos crudos** de una medición hecha en banco y reconstruye el análisis completo: qué problema apareció, cómo se lo midió, qué cuentas se hicieron, qué gráficos salen y qué se decidió.

Dos objetivos:

1. **Mostrar el avance y su justificación** — no sólo el resultado, sino el camino: qué se supuso, qué desmintió la medición y por qué.
2. **Generar las figuras del informe** — cada cuaderno guarda sus gráficos en `figuras/` a 200 dpi.

---

## Cuadernos

| # | Archivo | Qué responde | Estado |
|---|---|---|---|
| 01 | `01_calibracion_motores.ipynb` | Por qué las dos ruedas no giraban parejas y cómo se las emparejó. Rectas de calibración por rueda, zonas muertas, rangos de duty y de tensión. | ✅ |

## Cómo correrlos

Los datos medidos están **embebidos** en cada cuaderno: no hace falta el robot ni el ESP32 conectados.

```bash
pip install numpy pandas matplotlib jupyter
jupyter lab            # o: jupyter notebook
```

Después, *Cell → Run All*. Cada cuaderno reescribe sus PNG en `figuras/`.

## Convenciones

- **Numerados** por orden de aparición en el proyecto, no por importancia.
- **Autocontenidos**: los datos crudos se declaran arriba, en una celda visible, con la fecha y el método de medición. Nada de archivos externos.
- **Los números se calculan, no se transcriben**: los ajustes, las velocidades y los parámetros del firmware se recomputan en el cuaderno a partir de los datos crudos. Si un valor documentado no coincide con el calculado, el cuaderno lo dice.
- **Se distingue lo medido de lo predicho.** Donde una tabla es salida del modelo y no una medición independiente, está marcado.
- **Figuras**: dos series categóricas fijas (azul = rueda izquierda, naranja = rueda derecha), gris para la infraestructura del gráfico, rojo reservado para estados críticos (calado, fallas). El par azul/naranja está validado para daltonismo.
