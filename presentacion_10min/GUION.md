# Guion de la presentación de 10 minutos

`TPF_presentacion.pdf` — 14 diapositivas para exponer (unos **9 minutos**) y 5
de respaldo para las preguntas. El video es `demo_vista_del_robot.mp4` (20 s).

Los tiempos suman 9:15. Los 45 segundos que sobran son el margen: **ensayar
con cronómetro**, porque hablando en público se tarda más que leyendo.

*Actualizado el 2026-10-02: el robot ya tiene ultrasónico y buzzer. Cambiaron
las diapositivas 2, 3, 5, 7, 9, 10 y 12, y la foto de la 2 es la del robot
terminado.*

| # | Diapositiva | Tiempo | Acumulado |
|---|---|---|---|
| 0 | Portada | 0:10 | 0:10 |
| 1 | El problema | 0:35 | 0:45 |
| 2 | El robot | 0:40 | 1:25 |
| 3 | Arquitectura: dos niveles | 0:50 | 2:15 |
| 4 | La IA: detección de objetos a bordo | 0:50 | 3:05 |
| 5 | El comportamiento | 1:00 | 4:05 |
| 6 | El control | 0:35 | 4:40 |
| 7 | Del banco al piso | 1:15 | 5:55 |
| 8 | Resultado: busca el oso | 0:35 | 6:30 |
| 9 | Resultado: huye de la mochila + **video** | 1:00 | 7:30 |
| 10 | Lo que se midió | 0:30 | 8:00 |
| 11 | La lección del trabajo | 0:40 | 8:40 |
| 12 | Límites y trabajo futuro | 0:30 | 9:10 |
| 13 | Gracias | 0:05 | 9:15 |

---

## 0. Portada — 0:10

> Buenos días. Voy a presentar mi trabajo final: un robot que busca un objeto,
> se le acerca, y huye de otro, decidiendo todo a bordo con una red neuronal.

## 1. El problema — 0:35

**Idea:** qué hace el robot, en una frase.

> El robot recorre una sala, reconoce dos objetos con su cámara y reacciona
> distinto ante cada uno. Si ve este oso impreso, lo busca y se le acerca. Si
> ve una mochila, huye. Y si ve los dos a la vez, huir gana: la conducta de
> seguridad tiene prioridad. Todo se decide a bordo, sin una computadora
> externa ni control remoto. Estas dos imágenes son lo que ve el propio robot,
> con lo que la red detecta dibujado encima.

## 2. El robot — 0:40

**Idea:** las piezas, sin detalle.

> Este es el robot terminado. Tiene dos ruedas motrices y dos cerebros: una
> Raspberry Pi 5, que ve y decide, y un microcontrolador ESP32, que mueve los
> motores. Al frente, muy cerca del piso, lleva una webcam USB y un sensor
> ultrasónico, que mide la distancia a lo que tenga adelante. Tiene un buzzer,
> que suena cuando huye y cuando llega. Y usa dos baterías separadas, una para
> la Raspberry y otra para los motores, porque compartiendo una sola la
> Raspberry se quedaba sin tensión.

(La foto es `figuras/robot_terminado.jpg`, del 2 de octubre. Las otras dos
tomas están en la carpeta `Fotos del bot/`.)

## 3. Arquitectura — 0:50

**Idea:** dos niveles con una frontera clara; el freno automático.

> La arquitectura tiene dos niveles. Arriba, la Raspberry: toma una imagen, la
> pasa por la red neuronal, una máquina de estados decide qué hacer y una ley
> de control lo convierte en una orden simple: "avanzá tanto, girá tanto". Eso
> pasa once veces por segundo. Abajo, el ESP32 recibe esa orden y la traduce a
> potencia para cada motor, cien veces por segundo. La regla es que la
> Raspberry nunca toca un motor y el ESP32 nunca toma una decisión: mueve,
> mide la distancia y hace sonar el buzzer. Y hay una protección: si la Raspberry deja de hablar medio segundo, porque se colgó o
> se cortó el cable, el ESP32 frena solo.

## 4. La IA — 0:50

**Idea:** modelo preentrenado; el compromiso velocidad/tamaño se midió; el
aporte es integrar la inferencia en un lazo físico.

> La red es YOLOv8n, la más chica de la familia, preentrenada en el conjunto
> COCO. No entrené un modelo propio. Lo que sí hice fue medir cuánto rinde en
> la Raspberry según el tamaño de imagen: con la imagen grande da tres por
> segundo, que no alcanza; con 320 píxeles da once, más del doble del mínimo
> que me había fijado. De la foto a la decisión pasan unos 150 milisegundos. Y
> como una red a veces se equivoca en una imagen suelta, el robot sólo le cree
> a una detección si se repite tres imágenes seguidas. El aporte del trabajo
> no es entrenar una red: es meter la inferencia dentro de un lazo de control
> físico que corre en tiempo real.

## 5. El comportamiento — 1:00

**Idea:** cuatro estados, y la prioridad de huir.

> El comportamiento es una máquina de cuatro estados. En BUSCAR, el robot mira
> quieto, gira un paso corto y vuelve a mirar. Cuando confirma el oso pasa a
> APROXIMAR: avanza manteniéndolo centrado. Cuando el oso ocupa suficiente
> imagen, frena: ENCONTRADO. Y las flechas naranjas son lo importante: la
> mochila interrumpe cualquiera de los tres estados y lo manda a HUIR, que es
> retroceder, girar media vuelta y alejarse. Y hay una regla más, que no está
> dibujada: si va a avanzar sin el oso a la vista y tiene algo a menos de 30
> centímetros adelante, no avanza, gira. Todo este comportamiento se pudo
> verificar sin el robot, con 79 pruebas automáticas, porque la lógica que
> decide está separada de la que toca el hardware.

## 6. El control — 0:35

**Idea:** dos números de la imagen, dos ecuaciones proporcionales.

> Para acercarse usa dos números de la caja que dibuja la red. Cuánto está
> corrida del centro me dice hacia dónde girar. Y cuánto ocupa de la imagen me
> dice cuánto falta: a medida que el robot se acerca, la caja crece, el avance
> baja, y el robot frena solo a unos 30 centímetros. Un detalle: la cámara no
> mide distancia, mide tamaño aparente.

*(Si falta tiempo, esta es la primera que se acorta: decir sólo la primera y
la última oración.)*

## 7. Del banco al piso — 1:15

**Idea:** lo más interesante del trabajo. Cuatro cosas que la realidad cambió.

> Hasta acá, el diseño. Lo interesante fue lo que pasó al apoyar el robot en
> el piso. Cuatro ejemplos.
>
> Uno: los dos motores, que son del mismo modelo, no son iguales: uno gira el
> doble de rápido. Hubo que calibrar cada rueda por separado, y volver a
> hacerlo en el piso, porque la calibración con las ruedas al aire no movía al
> robot apoyado.
>
> Dos: mientras el robot giraba buscando, la imagen salía movida y la red no
> veía nada, aunque el oso le pasara por delante. Por eso busca a pasos: mira
> quieto, gira dieciocho grados, vuelve a mirar.
>
> Tres: para la red, mi mochila no es una mochila, es una valija. El modelo
> aprendió mochilas en la espalda de una persona; apoyada en el piso y vista
> desde abajo, se parece a otra cosa.
>
> Y cuatro, que no quedó cerrado: a ratos la imagen llegaba rota, con franjas,
> aun con los motores apagados. Descarté varias causas. Al día siguiente, con
> el enchufe de la cámara bien puesto y las baterías recién cargadas, no
> volvió a pasar; como cambiaron las dos cosas juntas, no sé cuál era. Lo que
> hice fue que cada corrida registre la salud de cada imagen, para saber
> cuándo la cámara estuvo ciega.

## 8. Resultado: busca el oso — 0:35

**Idea:** funciona; la secuencia vista desde el robot.

> Y funciona. Esta es una corrida en el piso, vista desde la cámara del robot.
> Busca; ve el oso y se queda quieto hasta confirmarlo; avanza centrándolo; y
> frena a unos 30 centímetros. Con el oso a un metro y a noventa grados tarda
> unos quince segundos en encontrarlo, dos décimas en confirmarlo y dos
> segundos y medio en llegar.

## 9. Resultado: huye + video — 1:00

**Idea:** la huida y la prioridad. **Acá va el video.**

> Con la mochila: la ve, la confirma en dos décimas de segundo, retrocede
> girando, sigue girando hasta darle la espalda y se aleja. Lo muestro en
> video, visto desde el robot.

▶ **Reproducir `demo_vista_del_robot.mp4` (20 s).** Mientras corre:

> Primero busca el oso y se acerca… y ahora ve la mochila y huye.

> Y la prioridad se cumple: en la demo completa le puse la mochila al lado del
> oso mientras se estaba acercando, y huyó. Lo último que agregué fue el
> ultrasónico: cuando la huida lo lleva hacia una pared, deja de avanzar a 30
> centímetros y gira en el lugar hasta tener el camino libre.

(El video es del 1 de octubre, de antes del ultrasónico, y no tiene sonido:
el buzzer no se escucha. Hay otro del 2 de octubre en `media/`, con la huida
esquivando una pared en los primeros 8 segundos.)

*(Si el video no anda, las cuatro imágenes de la diapositiva cuentan lo mismo:
seguir de largo sin disculparse.)*

## 10. Lo que se midió — 0:30

**Idea:** números, y honestidad sobre lo que falta.

> En números: once imágenes por segundo contra un mínimo de cinco; ve el oso
> hasta un metro treinta; frena a unos 30 centímetros; reacciona a la mochila
> en dos décimas; huyendo hacia una pared deja de avanzar a 29 centímetros; y
> con las dos baterías no hubo ninguna caída de tensión. Lo
> que todavía no tengo es una evaluación estadística: estas son pruebas de
> puesta a punto, y falta la serie de diez corridas por escenario para dar
> porcentajes de éxito.

*(Si para la presentación ya están las 10 corridas, reemplazar el recuadro
rojo por los porcentajes. `analizar_corrida.py logs/corrida_*.csv` arma la
tabla.)*

## 11. La lección — 0:40

**Idea:** el hilo conductor. Es la diapositiva que tiene que quedar.

> Si tengo que resumir lo que aprendí en una frase: un número vale en el
> contexto donde se midió. La calibración era exacta con las ruedas al aire, y
> en el piso una rueda no arrancaba. La velocidad de giro era correcta medida
> en varias vueltas, y en un giro de un segundo daba mucho menos. Y la
> etiqueta "mochila" es correcta para las fotos con las que se entrenó la red,
> no para una mochila vista desde el piso. Me pasó veintiún veces, y la
> respuesta fue de método: anotar al lado de cada número en qué condiciones se
> midió, y probar una capa por vez.

## 12. Límites y trabajo futuro — 0:30

> Los límites: el ultrasónico sólo mira adelante, así que el robot retrocede y
> gira a ciegas; ve el oso hasta poco más de un metro; y la falla intermitente
> de la imagen no quedó explicada del todo. Para una segunda versión, sensores
> atrás y a los costados, y encoders para controlar la velocidad de cada
> rueda. Lo que queda demostrado
> es la cadena completa: percepción con inteligencia artificial, decisión y
> actuación, cerradas en un robot físico, en tiempo real y a bordo.

## 13. Gracias — 0:05

> Muchas gracias. Quedo a disposición para las preguntas.

---

## Preguntas probables y dónde está la respuesta

| Pregunta | Respuesta corta | Respaldo |
|---|---|---|
| ¿Por qué no entrenaste tu propio modelo? | El tiempo se fue en la integración física, que era el aporte. Un modelo propio probablemente evitaría lo de la mochila-valija; queda como mejora | — |
| ¿De dónde salen los valores de los parámetros? | Cada uno medido o ajustado en el piso; están todos en un archivo con su origen | "Los parámetros principales" |
| ¿Qué pasa si el programa se cuelga? | Dos redes: a los 0,4 s la Raspberry manda parar; a los 0,5 s el ESP32 frena solo | "Seguridad y protocolo" |
| ¿Y si hay un obstáculo? | Adelante lo ve con el ultrasónico: con algo a menos de 30 cm no avanza, gira. Marcha atrás y girando va a ciegas, y una pared muy de costado no la detecta | "Seguridad y protocolo" |
| ¿Por qué dos distancias, 30 y 20 cm? | Al oso hay que poder acercarse (20); a una pared no (30). Con una sola de 20, huyendo la lectura llegó a 11 cm | "Los parámetros principales" |
| ¿Cuánto llevó agregar el ultrasónico? | La estimación era media hora y fueron más de dos: el primer sensor estaba muerto, y los umbrales sólo aparecieron en el piso | "Cómo se trabajó" |
| ¿Qué es eso de la imagen rota? | Paquetes USB perdidos, de a ratos. Qué descarté, y por qué al día siguiente no volvió (enchufe y baterías, las dos cosas a la vez) | "La imagen rota" |
| ¿Por qué los motores son distintos? | Reducciones distintas: 2,1 veces. Una recta de calibración por rueda | "Los motores y su calibración" |
| ¿Por qué 320 píxeles? | Es el mayor tamaño que supera con margen el mínimo de velocidad. El costo es alcance: ve hasta 1,3 m | diapositiva 4 |
| ¿Cuántas veces funcionó? | Llegó al oso en 5 de 6 corridas (la que falló tenía la imagen rota) y huyó 6 veces en las 3 últimas corridas con mochila. No es una serie estadística | diapositiva 10 |
| ¿Por qué no usás distancia real? | La cámara sola no la da; el tamaño aparente alcanza para frenar, y depende del objeto con que se calibró | diapositiva 6 |
| ¿Cómo lo probaste sin el robot? | La lógica que decide no toca hardware: 79 pruebas automáticas y un simulador | "Cómo se trabajó" |

## Si hay que recortar sobre la marcha

1. Diapositiva 6 (control): una sola oración.
2. Diapositiva 10 (lo que se midió): leer sólo tres números y el recuadro.
3. Diapositiva 2 (el robot): nombrar las piezas sin explicar las baterías.

Lo que **no** se recorta: la 7 (del banco al piso), el video y la 11 (la
lección).

## Antes de exponer

- [ ] Probar el video en la computadora de la sala (VLC lo abre seguro).
- [ ] Tener el PDF y el video en un pendrive además de la notebook.
- [ ] Si se va a mostrar el robot en vivo: `GUIA_PRESENTACION.pdf`, impresa. Es
      el manual para operarlo sin ayuda — los siete pasos están en la primera
      página, y el plan B (mostrar el video) en la sección 13. Antes de ese
      día hay que haber hecho lo de su sección 2: un ensayo completo por el
      hotspot del celular (`FedeAP`, ya cargado en el Pi). Llevar las baterías **desenchufadas de
      sus cargadores** y revisar que la webcam y los tres cables del
      ultrasónico estén firmes.
- [ ] Ensayar una vez con cronómetro, en voz alta.
