/*
 * TPF Robotica IA - Bring-up de motores
 * ------------------------------------------------------------------
 * Firmware de prueba. NO es el firmware final: su unico objetivo es
 * verificar que el cableado ESP32 <-> L298N <-> motores es correcto,
 * determinar el sentido de giro de cada rueda y encontrar el PWM
 * minimo al que los motores arrancan.
 *
 * Hardware: 2x GM25-370 (12 V, 350 rpm) sobre modulo L298N.
 *           Cableado en HARDWARE.md seccion 6.
 *
 * OJO: al 100% de PWM estos motores dan ~1.2 m/s, demasiado rapido
 * para el lazo de vision. El firmware final va a limitar la velocidad
 * al ~25% (HARDWARE.md seccion 0.3). Aca se recorre el rango completo
 * a proposito, para caracterizar el motor con las ruedas al aire.
 *
 * Al arrancar espera 3 s con los puentes deshabilitados, corre una
 * secuencia automatica de prueba, y despues queda escuchando comandos
 * por el monitor serie.
 *
 * Comandos (monitor serie a 115200):
 *   w / s   adelante / atras (ambos motores)
 *   a / d   girar izquierda / derecha en el lugar
 *   x       parar (coast)
 *   b       frenar (brake)
 *   1 / 2   probar solo motor izquierdo / derecho
 *   + / -   subir / bajar velocidad en pasos de 16
 *   r       repetir la secuencia automatica
 *   ?       ayuda
 */

#include <Arduino.h>

/* ------------------------------------------------------------------
 * Configuracion de pines - debe coincidir con HARDWARE.md seccion 6
 *
 * Estos son los rotulos del modulo L298N, no el lado del robot.
 * ------------------------------------------------------------------ */
#define PIN_ENA 25 /* PWM canal A       */
#define PIN_IN1 26 /* direccion canal A */
#define PIN_IN2 27 /* direccion canal A */

#define PIN_ENB 13 /* PWM canal B       */
#define PIN_IN3 33 /* direccion canal B */
#define PIN_IN4 32 /* direccion canal B */

/* ------------------------------------------------------------------
 * Mapeo canal del modulo <-> rueda
 *
 * Verificado en el bring-up: el canal A quedo cableado a la rueda
 * DERECHA y el canal B a la IZQUIERDA. Se corrige aca en vez de mover
 * los cables en la bornera.
 *
 * Cada motor ya gira en el sentido correcto con su cableado actual, asi
 * que las polaridades no se tocan: solo se intercambia que canal maneja
 * que rueda. Si alguna vez se recablea la bornera, este es el unico
 * bloque que hay que tocar.
 * ------------------------------------------------------------------ */
#define PIN_LEFT_PWM PIN_ENB
#define PIN_LEFT_A PIN_IN3
#define PIN_LEFT_B PIN_IN4

#define PIN_RIGHT_PWM PIN_ENA
#define PIN_RIGHT_A PIN_IN1
#define PIN_RIGHT_B PIN_IN2

/* ------------------------------------------------------------------
 * Parametros de PWM
 *
 * 1 kHz es terreno seguro para el L298 (bipolar, conmutacion lenta:
 * retardo de encendido ~2 us segun datasheet). Se escucha un chillido
 * agudo en los motores; es normal y no daña nada.
 * Para silenciarlo se puede subir a 8000 Hz una vez validado el
 * funcionamiento. El datasheet da f_C = 25 kHz tipico como techo.
 * ------------------------------------------------------------------ */
#define PWM_FREQ_HZ 1000
#define PWM_RES_BITS 8 /* 0..255 */
#define PWM_MAX 255

/* Canales LEDC (solo se usan en el core 2.x de Arduino-ESP32) */
#define PWM_CH_LEFT 0
#define PWM_CH_RIGHT 1

#define MOTOR_LEFT 0
#define MOTOR_RIGHT 1

/* Velocidad inicial de los comandos manuales. Arranca alto a proposito:
 * si el motor no se mueve a 180 el problema es de cableado, no de fuerza. */
static int g_speed = 180;

/* ------------------------------------------------------------------
 * Capa de PWM
 *
 * El core 3.x de Arduino-ESP32 cambio la API de LEDC: ledcSetup() y
 * ledcAttachPin() se reemplazaron por ledcAttach(), y ledcWrite() pasó
 * a recibir el pin en vez del canal. Este bloque compila con ambos.
 * ------------------------------------------------------------------ */
static void pwm_init(uint8_t pin, uint8_t channel)
{
#if defined(ESP_ARDUINO_VERSION_MAJOR) && (ESP_ARDUINO_VERSION_MAJOR >= 3)
    (void)channel;
    ledcAttach(pin, PWM_FREQ_HZ, PWM_RES_BITS);
#else
    ledcSetup(channel, PWM_FREQ_HZ, PWM_RES_BITS);
    ledcAttachPin(pin, channel);
#endif
}

static void pwm_write(uint8_t pin, uint8_t channel, uint32_t duty)
{
#if defined(ESP_ARDUINO_VERSION_MAJOR) && (ESP_ARDUINO_VERSION_MAJOR >= 3)
    (void)channel;
    ledcWrite(pin, duty);
#else
    (void)pin;
    ledcWrite(channel, duty);
#endif
}

/* ------------------------------------------------------------------
 * Control de motores
 *
 * Tabla de verdad del L298 (por puente):
 *   EN=H, IN_A=H, IN_B=L  -> giro en un sentido
 *   EN=H, IN_A=L, IN_B=H  -> giro en el otro sentido
 *   EN=H, IN_A=IN_B       -> freno activo (fast motor stop)
 *   EN=L                  -> rueda libre (free running stop / coast)
 * ------------------------------------------------------------------ */

/* speed en [-255, 255]. Signo = sentido, 0 = rueda libre. */
static void motor_set(int motor, int speed)
{
    uint8_t pin_a, pin_b, pin_en, channel;

    if (motor == MOTOR_LEFT) {
        pin_a = PIN_LEFT_A;
        pin_b = PIN_LEFT_B;
        pin_en = PIN_LEFT_PWM;
        channel = PWM_CH_LEFT;
    } else {
        pin_a = PIN_RIGHT_A;
        pin_b = PIN_RIGHT_B;
        pin_en = PIN_RIGHT_PWM;
        channel = PWM_CH_RIGHT;
    }

    if (speed > PWM_MAX) {
        speed = PWM_MAX;
    }
    if (speed < -PWM_MAX) {
        speed = -PWM_MAX;
    }

    if (speed > 0) {
        digitalWrite(pin_a, HIGH);
        digitalWrite(pin_b, LOW);
        pwm_write(pin_en, channel, (uint32_t)speed);
    } else if (speed < 0) {
        digitalWrite(pin_a, LOW);
        digitalWrite(pin_b, HIGH);
        pwm_write(pin_en, channel, (uint32_t)(-speed));
    } else {
        /* coast: deshabilitar el puente y dejar la rueda libre */
        digitalWrite(pin_a, LOW);
        digitalWrite(pin_b, LOW);
        pwm_write(pin_en, channel, 0);
    }
}

/* Freno activo: cortocircuita el motor a traves del puente. */
static void motor_brake(int motor)
{
    uint8_t pin_a, pin_b, pin_en, channel;

    if (motor == MOTOR_LEFT) {
        pin_a = PIN_LEFT_A;
        pin_b = PIN_LEFT_B;
        pin_en = PIN_LEFT_PWM;
        channel = PWM_CH_LEFT;
    } else {
        pin_a = PIN_RIGHT_A;
        pin_b = PIN_RIGHT_B;
        pin_en = PIN_RIGHT_PWM;
        channel = PWM_CH_RIGHT;
    }

    digitalWrite(pin_a, HIGH);
    digitalWrite(pin_b, HIGH);
    pwm_write(pin_en, channel, PWM_MAX);
}

static void motors_stop(void)
{
    motor_set(MOTOR_LEFT, 0);
    motor_set(MOTOR_RIGHT, 0);
}

static void motors_set(int left, int right)
{
    motor_set(MOTOR_LEFT, left);
    motor_set(MOTOR_RIGHT, right);
}

/* ------------------------------------------------------------------
 * Secuencia automatica de verificacion
 * ------------------------------------------------------------------ */

/* Rampa de 0 al maximo y vuelta, para ver a que PWM arranca el motor. */
static void ramp_motor(int motor, int direction, const char *label)
{
    int duty;

    Serial.printf("  %s\n", label);
    Serial.println("    subiendo PWM: ");

    for (duty = 0; duty <= PWM_MAX; duty += 15) {
        motor_set(motor, direction * duty);
        Serial.printf("      %3d\n", duty);
        delay(250);
    }

    delay(500);

    for (duty = PWM_MAX; duty >= 0; duty -= 15) {
        motor_set(motor, direction * duty);
        delay(120);
    }

    motor_set(motor, 0);
    delay(600);
}

static void run_test_sequence(void)
{
    Serial.println();
    Serial.println("=== SECUENCIA DE PRUEBA ===");
    Serial.println("Anotar para cada paso: que rueda gira y hacia donde.");
    Serial.println();

    Serial.println("[1/4] MOTOR IZQUIERDO - sentido positivo");
    ramp_motor(MOTOR_LEFT, +1, "deberia girar hacia ADELANTE");

    Serial.println("[2/4] MOTOR IZQUIERDO - sentido negativo");
    ramp_motor(MOTOR_LEFT, -1, "deberia girar hacia ATRAS");

    Serial.println("[3/4] MOTOR DERECHO - sentido positivo");
    ramp_motor(MOTOR_RIGHT, +1, "deberia girar hacia ADELANTE");

    Serial.println("[4/4] MOTOR DERECHO - sentido negativo");
    ramp_motor(MOTOR_RIGHT, -1, "deberia girar hacia ATRAS");

    Serial.println("Ambos motores adelante al 60%...");
    motors_set(150, 150);
    delay(1500);
    motors_stop();

    Serial.println();
    Serial.println("=== FIN DE LA SECUENCIA ===");
    Serial.println("Si alguna rueda giro al reves: ver diagnostico en RUNBOOK.md");
    Serial.println();
}

static void print_help(void)
{
    Serial.println();
    Serial.println("--- Comandos ---");
    Serial.println("  w / s   adelante / atras");
    Serial.println("  a / d   girar izq / der en el lugar");
    Serial.println("  x       parar (rueda libre)");
    Serial.println("  b       frenar (freno activo)");
    Serial.println("  1 / 2   solo motor izquierdo / derecho");
    Serial.println("  + / -   velocidad +/- 16");
    Serial.println("  r       repetir secuencia automatica");
    Serial.println("  ?       esta ayuda");
    Serial.printf("  velocidad actual: %d / %d\n", g_speed, PWM_MAX);
    Serial.println();
}

static void handle_command(char c)
{
    switch (c) {
    case 'w':
        Serial.printf("adelante (%d)\n", g_speed);
        motors_set(g_speed, g_speed);
        break;
    case 's':
        Serial.printf("atras (%d)\n", g_speed);
        motors_set(-g_speed, -g_speed);
        break;
    case 'a':
        Serial.printf("giro izquierda (%d)\n", g_speed);
        motors_set(-g_speed, g_speed);
        break;
    case 'd':
        Serial.printf("giro derecha (%d)\n", g_speed);
        motors_set(g_speed, -g_speed);
        break;
    case 'x':
        Serial.println("parar (rueda libre)");
        motors_stop();
        break;
    case 'b':
        Serial.println("freno activo");
        motor_brake(MOTOR_LEFT);
        motor_brake(MOTOR_RIGHT);
        break;
    case '1':
        Serial.printf("solo motor IZQUIERDO (%d)\n", g_speed);
        motors_set(g_speed, 0);
        break;
    case '2':
        Serial.printf("solo motor DERECHO (%d)\n", g_speed);
        motors_set(0, g_speed);
        break;
    case '+':
        g_speed += 16;
        if (g_speed > PWM_MAX) {
            g_speed = PWM_MAX;
        }
        Serial.printf("velocidad = %d\n", g_speed);
        break;
    case '-':
        g_speed -= 16;
        if (g_speed < 0) {
            g_speed = 0;
        }
        Serial.printf("velocidad = %d\n", g_speed);
        break;
    case 'r':
        run_test_sequence();
        break;
    case '?':
        print_help();
        break;
    default:
        break; /* ignorar CR, LF y ruido */
    }
}

/* ------------------------------------------------------------------ */

void setup(void)
{
    Serial.begin(115200);

    /* Primero los pines en un estado seguro, antes que cualquier otra
     * cosa: al salir del reset los GPIO quedan flotando y el L298 no
     * tiene niveles definidos en sus entradas. */
    pinMode(PIN_IN1, OUTPUT);
    pinMode(PIN_IN2, OUTPUT);
    pinMode(PIN_IN3, OUTPUT);
    pinMode(PIN_IN4, OUTPUT);
    digitalWrite(PIN_IN1, LOW);
    digitalWrite(PIN_IN2, LOW);
    digitalWrite(PIN_IN3, LOW);
    digitalWrite(PIN_IN4, LOW);

    /* Cada enable va atado a su propio canal LEDC. En el core 2.x
     * ledcWrite() recibe el canal y no el pin, asi que el pin y el canal
     * de una misma rueda tienen que moverse juntos. */
    pwm_init(PIN_LEFT_PWM, PWM_CH_LEFT);
    pwm_init(PIN_RIGHT_PWM, PWM_CH_RIGHT);
    motors_stop();

    delay(300); /* que el monitor serie alcance a conectarse */

    Serial.println();
    Serial.println("========================================");
    Serial.println(" TPF Robotica IA - Bring-up de motores");
    Serial.println("========================================");
    Serial.printf("PWM: %d Hz, %d bits (0..%d)\n",
                  PWM_FREQ_HZ, PWM_RES_BITS, PWM_MAX);
    Serial.printf("Izq (canal B del modulo): EN=%d A=%d B=%d\n",
                  PIN_LEFT_PWM, PIN_LEFT_A, PIN_LEFT_B);
    Serial.printf("Der (canal A del modulo): EN=%d A=%d B=%d\n",
                  PIN_RIGHT_PWM, PIN_RIGHT_A, PIN_RIGHT_B);
    Serial.println();
    Serial.println("!! RUEDAS AL AIRE, chasis apoyado sobre un soporte !!");
    Serial.println("Arrancando en 3 segundos...");

    delay(3000);

    run_test_sequence();
    print_help();
}

void loop(void)
{
    if (Serial.available() > 0) {
        handle_command((char)Serial.read());
    }
}
