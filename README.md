# Aguará — robot autónomo de aproximación y evasión con visión a bordo

Un robot de dos ruedas que **busca un objeto, se le acerca y frena a unos
30 cm**, y que **huye de otro objeto**, con la huida siempre por delante. Todo
se decide a bordo: una Raspberry Pi 5 corre la red de detección YOLOv8n y un
ESP32 mueve los motores. No hay computadora externa ni control remoto.

Trabajo práctico final de la materia *Inteligencia Artificial aplicada a la
Robótica* (Facultad de Ingeniería, Universidad Nacional de Asunción, 2026).
*Aguará* es "zorro" en guaraní.

![El robot terminado](Fotos%20del%20bot/bot_terminado1.jpeg)

## Qué hace

| Lo que ve | Lo que hace |
|---|---|
| nada | busca a pasos: mira quieto, gira ~18°, vuelve a mirar |
| el **oso** (impreso en una hoja A4) | lo confirma, se acerca centrándolo, frena a ~30 cm y da un pitido |
| la **mochila** | retrocede, gira media vuelta y se aleja, con la alarma sonando |
| oso **y** mochila | huye: la conducta de seguridad tiene prioridad |
| algo a menos de 30 cm adelante | no avanza: gira hasta tener el camino libre |

Hay dos videos tomados por la cámara del propio robot en [`media/`](media/),
con lo que detecta y lo que decide escrito sobre la imagen.

## Cómo está hecho

```
Raspberry Pi 5  (decide, ~10 veces por segundo)
  cámara USB -> YOLOv8n -> confirmación temporal -> máquina de estados -> ley de control
                                                                              |
                                              "avanzá tanto, girá tanto"      v
ESP32  (ejecuta, 100 veces por segundo)
  mezcla y calibración por rueda -> PWM -> L298N -> motores
  ultrasónico (distancia al frente)   zumbador   freno automático a los 0,5 s sin órdenes
```

- **La Raspberry Pi nunca toca un motor y el ESP32 nunca decide.** Entre los
  dos viaja una intención (avance y giro, de −100 a 100) por un enlace serie
  de texto.
- **La lógica que decide no toca hardware**, así que se verifica entera sin
  robot: 79 comprobaciones automáticas y un simulador.
- **Cada corrida deja un registro ciclo por ciclo** (CSV), del que salen todos
  los números del informe.

Piezas: Raspberry Pi 5 (8 GB), ESP32, driver L298N, dos motores GM25-370 de
12 V con reductora, cámara web USB, sensor ultrasónico Parallax PING))),
zumbador activo, y dos baterías separadas (una para la Raspberry Pi, otra para
los motores).

## Qué hay en este repositorio

| Carpeta o archivo | Qué es |
|---|---|
| [`src/`](src/) | El programa de la Raspberry Pi: visión, máquina de estados, ley de control, enlace con el ESP32, registro, verificaciones y simulador |
| [`firmware/`](firmware/) | El firmware del ESP32 (PlatformIO): protocolo, calibración por rueda, ultrasónico, zumbador y freno automático. Incluye los binarios ya compilados |
| [`scripts_pi/`](scripts_pi/) | Puesta en marcha de la Raspberry Pi y operación del robot, un comando por acción |
| [`logs/`](logs/) | Los registros de las 24 corridas en el piso (un CSV y un JSON por corrida) |
| [`media/`](media/) | Dos videos vistos desde el robot y la evidencia de un problema con la imagen USB |
| [`Fotos del bot/`](Fotos%20del%20bot/) | Fotos del robot, en el banco y terminado |
| [`scripts_auxiliares/`](scripts_auxiliares/) | Cuaderno con la calibración de los motores |
| [`informe/informe_tecnico/`](informe/informe_tecnico/) | **El informe técnico**, en LaTeX y PDF: es el mejor punto de entrada |
| [`presentacion_10min/`](presentacion_10min/) | La presentación para exponer, con su guion |
| [`presentacion_resumen/`](presentacion_resumen/) | Un resumen técnico extenso: una ficha por archivo y cada parámetro con el origen de su valor |
| [`presentacion/`](presentacion/) | La presentación del diseño, anterior a las pruebas en el piso. Se conserva como registro: sus números y pines no son los finales |
| [`HARDWARE.md`](HARDWARE.md) | Análisis eléctrico, cableado, calibración de los motores y mediciones |
| [`GUIA_PRESENTACION.md`](GUIA_PRESENTACION.md) | Guía para operar el robot paso a paso, con tabla de problemas |

La bitácora de trabajo y el cuaderno de procedimientos internos (`PLAN.md` y
`RUNBOOK.md`) no forman parte del repositorio. Varios documentos y comentarios
del código los citan por sección: esas referencias quedan sin destino aquí.

## Probarlo sin el robot

La máquina de estados y la ley de control se pueden ejecutar en cualquier
computadora con Python 3 y `numpy`:

```bash
cd src
python prueba_estados.py      # las 79 verificaciones del comportamiento
python simular_piso.py        # la máquina real contra un robot simulado
python analizar_corrida.py ../logs/corrida_20261002_104127.csv   # leer una corrida real
```

Ninguno de los tres necesita la cámara, el ESP32 ni la red neuronal. Para el
robot completo hacen falta las dependencias de
[`src/requirements.txt`](src/requirements.txt); los pesos del modelo
(`yolov8n.pt`) no están en el repositorio: Ultralytics los descarga la
primera vez.

## Armarlo y operarlo

1. **Armado y cableado**: [`HARDWARE.md`](HARDWARE.md), pines en §6 y §9.
2. **Firmware**: `firmware/esp32_control/`, con PlatformIO. La calibración de
   los motores es propia de cada robot y hay que rehacerla
   ([`HARDWARE.md`](HARDWARE.md) §0.5 y §0.6).
3. **Raspberry Pi**: Raspberry Pi OS de 64 bits, un entorno virtual con
   `src/requirements.txt`, y los scripts de [`scripts_pi/`](scripts_pi/README.md)
   para copiar el código y comprobar la instalación.
4. **Operación**: [`GUIA_PRESENTACION.md`](GUIA_PRESENTACION.md).

Los nombres de red, las direcciones y el nombre del equipo que aparecen en los
documentos son los de nuestro robot: hay que reemplazarlos por los propios.

## Qué se midió, y qué no

| | |
|---|---|
| Velocidad del lazo completo | unas 10 imágenes por segundo (mínimo fijado: 5) |
| De la imagen a la decisión | ~150 ms |
| Alcance de detección del oso impreso | ~1,3 m |
| Reacción ante la mochila | ~0,2 s |
| Aproximación desde 1 m | 2 a 3 s, frenando a ~30 cm |
| Avance hacia una pared | se interrumpe a 29–30 cm |

Son **pruebas de puesta a punto**, no una evaluación estadística: no se hizo la
serie de 10 corridas por escenario. Las limitaciones conocidas están en el
informe: el ultrasónico sólo mira adelante (el robot retrocede y gira a
ciegas), con la mochila siempre a la vista puede quedar huyendo una y otra
vez, la imagen USB se daña de a ratos por una causa que no quedó aislada, y sin
codificadores el robot se desvía al acelerar y al frenar.

## Autores

Federico Morán y Juan Barboza.

En el desarrollo se usó un asistente de programación basado en un modelo de
lenguaje (Claude, de Anthropic) para escribir código, ejecutar pruebas en el
robot, analizar registros y redactar documentación.

## Licencia y material de terceros

El contenido de este repositorio se distribuye bajo la licencia
**GNU Affero General Public License v3.0**: ver [`LICENSE`](LICENSE).

- La detección usa [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics),
  también bajo AGPL-3.0, con pesos entrenados en COCO.
- El informe usa la clase LaTeX `sn-jnl.cls` de Springer Nature, que conserva
  su propia licencia.
- Las hojas de datos de los componentes no se incluyen: se consultan en los
  sitios de sus fabricantes.
