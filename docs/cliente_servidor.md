# NEXUS cliente-servidor (punto 13 del laboratorio)

Diseño corto del modo en red y del prototipo que hay en `cliente_servidor/`.
El modo local (`python main.py`) no cambia: el modo en red es aparte y se
arranca con sus propios comandos.

## Idea

Un **servidor** es el dueño del estado de la partida y uno o varios
**clientes** solo leen la entrada y dibujan.

```
 cliente (1 ventana)                         servidor (sin ventana)
 ┌──────────────────────┐   socket J1   ┌──────────────────────────┐
 │ teclado + mandos     │ ────────────► │ hilo lector J1 ─┐        │
 │  -> intenciones      │   socket J2   │ hilo lector J2 ─┤ buzón  │
 │                      │ ────────────► │   ...           ┘ (lock) │
 │ dibuja la última     │ ◄──────────── │ hilo principal:          │
 │ instantánea          │  instantáneas │  Game() headless a 60 Hz │
 └──────────────────────┘               │  instantánea cada 2 cuadros
                                        └──────────────────────────┘
```

- **Una conexión TCP por jugador**, aunque los jugadores estén en la misma
  ventana. Así el servidor no sabe ni le importa si los cuatro están en una
  laptop o en cuatro: cada socket es un jugador.
- **Una sola ventana en el cliente**: el teclado solo le llega a la ventana
  que tiene el foco, así que con dos ventanas un jugador dejaría sin teclado
  al otro. Los mandos entran por `pygame.joystick` (reutiliza `juego/mandos.py`).

## Procesos e hilos

| Proceso | Hilo | Hace |
|---|---|---|
| servidor | principal | escucha, arma la partida, acepta N conexiones y corre el bucle de juego a 60 Hz; manda las instantáneas |
| servidor | 1 lector por conexión | lee líneas JSON del socket y deja la última intención en el buzón de ese jugador |
| cliente | principal | eventos de pygame, teclado, mandos, manda intenciones y dibuja (pygame tiene que ir en el hilo principal) |
| cliente | 1 lector por conexión | lee instantáneas y guarda la última |

Solo el hilo principal del servidor toca el objeto `Game` (no es seguro para
hilos). Los lectores solo tocan el buzón, protegido con un `threading.Lock`.

## Protocolo

TCP en `127.0.0.1:<puerto>` (por defecto 5050). Cada mensaje es **un objeto
JSON en una línea** terminada en `\n` (UTF-8). `json.dumps` escapa los saltos
de línea dentro de los textos, así que la línea nunca se parte.

| Dirección | `tipo` | Campos |
|---|---|---|
| C→S | `hola` | `version`, `nombre` |
| S→C | `bienvenida` | `jugador` (0..N-1), `jugadores`, `roles`, `mapa`, `ancho`, `alto`, `escala`, `hz` |
| S→C | `espera` | `conectados`, `faltan` (mientras no han llegado todos) |
| C→S | `intencion` | `n` (número de secuencia), `mantener` (acciones mantenidas), `pulsar` (acciones de una vez) |
| S→C | `estado` | la instantánea (abajo), `ack` = último `n` recibido de cada jugador |
| C→S | `adios` | (el cliente se va; cerrar el socket vale lo mismo) |
| S→C | `error` | `texto` (servidor lleno, versión distinta) |

Las acciones son nombres, no teclas: `arriba abajo izquierda derecha sigilo
interactuar` se mantienen; `interactuar habilidad habilidades celular soltar
volver` y las cuatro direcciones (para mover el cursor de los paneles) se
pulsan. El cliente traduce sus teclas (WASD, flechas, mando) a acciones y el
servidor traduce las acciones a las teclas del puesto de ese jugador. Así el
cliente puede tener cualquier distribución de teclado.

El cliente manda la intención cuando cambia y, si no cambia, cada 100 ms.
Lo mantenido es "estado" (si se pierde un mensaje, el siguiente lo corrige);
lo pulsado es "evento" y el servidor lo acumula hasta el siguiente cuadro.

La **instantánea** (`estado`, 20-30 Hz; el prototipo usa 30) lleva: cuadro,
reloj de juego, fase de la misión y objetivo, resultado, apagón, piezas
entregadas, la cápsula, las piezas sueltas; por jugador posición, dirección,
rol, vidas, preso/eliminado/escondido, sigilo, pulso, puntos, mensaje, pista,
progreso de lo que mantiene y el panel abierto (título, cuerpo, opciones,
cursor); por alien tipo, posición, ángulo, acción y cono de visión; y la
ventana que presenta un alien nuevo (pausa a todos hasta que alguien la
cierra). Todas las conexiones reciben la misma instantánea (se arma y se
codifica una vez por envío); cada cliente mira el jugador que le tocó.

## Quién es dueño de qué

- **Servidor**: todo el estado de juego (posiciones, colisiones, misión,
  aliens, eventos, reloj, vidas, presos, paneles). Es la única verdad.
- **Cliente**: qué teclas/mandos tiene cada jugador local, la cámara de cada
  jugador y la animación de los sprites (el cuadro de la animación es local:
  no vale la pena mandarlo).

## Cómo el servidor reutiliza `Game`

No se reescribe la lógica: el servidor crea un `Game()` con
`SDL_VIDEODRIVER=dummy` (como `pruebas/simulador.py`), arma la partida
saltándose los menús (`abrir_seleccion_roles`, roles listos,
`_preparar_partida`) y en cada cuadro:

1. Lo mantenido: `Game._actualizar_partida` pregunta las teclas con
   `self.mandos.envolver(pygame.key.get_pressed())`. El servidor cambia
   `envolver` **en su instancia** por una función que devuelve un diccionario
   con las teclas del puesto de cada jugador que el cliente mantiene. No hay
   que parchear `pygame.key.get_pressed` para todo el proceso ni tocar `app.py`.
2. Lo pulsado: `Game._tecla_en_partida(tecla)` con la primera tecla de esa
   acción en `jugador.teclas` (para los puestos 3 y 4 es la tecla virtual del
   mando). `volver` hace lo mismo que el botón B del mando.
3. Llama `_actualizar_partida(16)` (60 Hz fijos, el paso que espera el juego:
   la velocidad de los personajes va por cuadro).

A los puestos 3 y 4 se les pone `puede_moverse = True`: en local solo se
mueven con mando, pero en red su entrada viene del socket. El servidor deja de
actualizar cuando la misión tiene resultado y se apaga cuando se desconectan
todos. Al que llega con la partida llena se le contesta `error`.
`--sin-presentaciones` y `--aliens-quietos` sirven para las pruebas y para
mostrar la red sin que un alien interrumpa.

## Qué dibuja el cliente

Una ventana dividida en una vista por jugador local (completa, mitades o
cuartos; con 3 el cuarto que sobra muestra el equipo), cada una con su cámara
centrada en su jugador. Dibuja el fondo del mapa (el mismo
PNG de `Imagenes/Fondos/`, escalado solo el pedazo visible), los sprites de
los personajes (`Movimiento/Personaje.py`), los aliens como círculos con su
cono de visión, las piezas y la cápsula, y un HUD de texto (fase, objetivo,
vidas, pista, panel abierto, latencia). No dibuja oscuridad, linternas,
sonido ni los paneles bonitos de `screens/`.

## Latencia en localhost

En 127.0.0.1 el viaje ida y vuelta es < 1 ms; lo que se nota es el ritmo:
la intención espera hasta el siguiente cuadro del servidor (≤ 16 ms) y la
instantánea sale cada 33 ms, así que la reacción es de 20-50 ms. Se activa
`TCP_NODELAY` en los dos lados para que Nagle no junte los mensajes chicos.
El HUD muestra la "respuesta": desde que se manda la intención `n` hasta que
llega la primera instantánea con `ack` = `n` (RTT + espera del cuadro + espera
de la instantánea). En la laptop de prueba da 15-20 ms. En una LAN real (2-10 ms) se
sigue jugando bien; por Internet haría falta predicción en el cliente.

## Fuera del prototipo

Menús, selección de rol y dificultad en red (van por argumentos del
servidor), tutorial (se salta), pausa, pantalla de resultados, sonido,
oscuridad/linternas, paneles con el dibujo real de `screens/`, celular
completo, reconexión, varias laptops (funciona cambiando `--host`, pero no
se probó), interpolación y predicción.

## Pasos para llevarlo a algo completo

1. Mandar también los eventos de sonido y los avisos del narrador en la
   instantánea (lista de "lo que pasó" desde la anterior).
2. Separar el dibujo de `screens/partida.py` del objeto `Game`: que dibuje
   desde un "estado de vista" que pueda armarse con la instantánea. Ahí el
   cliente se vería igual que el local (oscuridad, HUD, paneles).
3. Lobby en red: cantidad, dificultad, controles y rol por el socket.
4. Instantáneas delta (solo lo que cambió) o binario (`struct`) si el ancho
   de banda importa; interpolación entre dos instantáneas en el cliente.
5. Reconexión con un token por jugador y servidor que siga si alguien se cae.
6. `--host 0.0.0.0` para jugar desde varias laptops en la misma red.
