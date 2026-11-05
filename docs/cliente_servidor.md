# NEXUS cliente-servidor (punto 13 del laboratorio)

El modo en red de NEXUS: cómo se usa, cómo funciona y qué viaja por la red.
El modo local (`python main.py` > Jugar) no cambia en nada.

## Cómo se usa

### Desde el menú (lo normal en la feria)

Menú > **Jugar en red**. En esa pantalla (flechas para cambiar, Enter para
elegir, Esc para volver):

| Opción | Qué hace |
|---|---|
| Jugadores en la partida | 2, 3 o 4 en total |
| Juegan en esta laptop | cuántos de ellos están frente a ESTA pantalla |
| Controles | "teclado primero" (WASD, flechas, mando 1, mando 2) o "mandos primero" (mando 1, mando 2, WASD, flechas) |
| Dificultad | Fácil, Normal o Difícil |
| Crear partida en esta laptop | levanta el servidor (otro proceso, `--host 0.0.0.0`, puerto 5050) y conecta a los de aquí |
| IP para unirse / Unirse por IP | se escribe la IP de la laptop que creó la partida (abajo en su pantalla dice cuál es) |

Ejemplo de dos laptops con 4 jugadores: en la laptop A, "Jugadores en la
partida: 4", "Juegan en esta laptop: 2", Crear. En la laptop B, "Juegan en
esta laptop: 2", "mandos primero", escribir la IP de A y Unirse. La partida
empieza cuando están los cuatro. Esc sale al menú; al terminar se ve la
pantalla de resultados del modo local y Enter vuelve al menú.

### Por comandos

```bash
python -m cliente_servidor.servidor --jugadores 2                       # solo esta laptop
python -m cliente_servidor.servidor --jugadores 4 --host 0.0.0.0        # para la red local
python -m cliente_servidor.cliente --jugadores 2                        # J1 WASD, J2 flechas
python -m cliente_servidor.cliente --jugadores 2 --host 192.168.1.20 --mandos
```

Opciones del servidor: `--roles Biomante,Resonante`, `--dificultad facil`,
`--mapa Nave`, `--puerto 6000` (0 = uno libre), `--espera 30` (segundos sin
nadie conectado antes de apagarse), `--semilla`, `--segundos`,
`--sin-presentaciones`, `--aliens-quietos` y `--fase-final` (atajo para las
pruebas: empieza en la huida junto a la cápsula).

## Idea

Un **servidor** es el dueño del estado de la partida y los **clientes** solo
leen la entrada y dibujan.

```
 cliente (1 ventana por laptop)              servidor (sin ventana)
 ┌──────────────────────┐   socket J1   ┌──────────────────────────┐
 │ teclado + mandos     │ ────────────► │ hilo lector J1 ─┐        │
 │  -> intenciones      │   socket J2   │ hilo lector J2 ─┤ buzón  │
 │                      │ ────────────► │   ...           ┘ (lock) │
 │ espejo: Game que no  │ ◄──────────── │ hilo principal:          │
 │ se actualiza, solo   │  instantáneas │  Game() headless a 60 Hz │
 │ copia y dibuja       │  (delta)      │  instantánea cada 2 cuadros
 └──────────────────────┘               └──────────────────────────┘
```

- **Una conexión TCP por jugador**, aunque estén en la misma ventana: el
  servidor no sabe si los cuatro están en una laptop o en cuatro.
- **Una sola ventana por laptop**: el teclado solo le llega a la ventana que
  tiene el foco. Los mandos entran por `pygame.joystick` (`juego/mandos.py`).

## Archivos

| Archivo | Qué hace |
|---|---|
| `cliente_servidor/protocolo.py` | JSON por línea, `LectorLineas`, `Reconstructor` (arma las delta), `comprimir` (zlib + base64), `legible` |
| `cliente_servidor/servidor.py` | el `Game` sin ventana, puestos con token, hilos, instantáneas |
| `cliente_servidor/estado.py` | copia los DATOS de un objeto del juego a JSON y de vuelta encima de otro objeto (`extraer`, `atributos`, `aplicar`, `diferencias`) |
| `cliente_servidor/espejo.py` | el Game espejo del cliente y el dibujo con las funciones del modo local |
| `cliente_servidor/interpolacion.py` | el búfer de 100 ms y la mezcla entre dos instantáneas |
| `cliente_servidor/cliente.py` | `Conexion` (lector, reconexión), `Entrada` (teclado y mandos), `Sesion` (el bucle en la ventana del juego) |
| `cliente_servidor/lanzador.py` | la pantalla "Jugar en red" del menú y el servidor como subproceso |
| `cliente_servidor/dibujo_simple.py` | el dibujo del prototipo, de respaldo si el espejo falla |

## Procesos e hilos

| Proceso | Hilo | Hace |
|---|---|---|
| servidor | principal | arma la partida, espera a todos y corre el juego a 60 Hz; es el único que toca `Game` y el único que escribe en los sockets ya sentados |
| servidor | aceptar | acepta conexiones durante toda la partida (las primeras y las que vuelven) |
| servidor | 1 por saludo | lee el `hola`, busca puesto (por token o uno libre) y manda la bienvenida |
| servidor | 1 lector por conexión | deja la última intención en el buzón de ese jugador (`threading.Lock`) |
| cliente | principal | eventos de pygame, entrada, manda intenciones y dibuja (pygame va en el hilo principal) |
| cliente | 1 lector por conexión | arma las instantáneas, alimenta la interpolación y reconecta si se cae |
| cliente | 1 mientras carga | arma el espejo (como la pantalla de carga del modo local) |

## Protocolo

TCP, puerto 5050 por defecto. Cada mensaje es **un objeto JSON en una línea**
terminada en `\n` (UTF-8). `VERSION = 2`.

| Dirección | `tipo` | Ejemplo |
|---|---|---|
| C→S | `hola` | `{"tipo":"hola","version":2,"nombre":"local 1"}` (al volver trae `"token":"9f1c2a7b4e3d0a11"`) |
| S→C | `bienvenida` | `{"tipo":"bienvenida","jugador":0,"jugadores":2,"token":"9f1c2a7b4e3d0a11","roles":["Tecnomante","Forjador"],"dificultad":"normal","semilla":518234,"presentaciones":true,"mapa":"MapaFinal","ancho":8160,"alto":6144,"escala":3,"hz":30}` |
| S→C | `espera` | `{"tipo":"espera","conectados":1,"faltan":1}` (cada 250 ms mientras faltan) |
| C→S | `intencion` | `{"tipo":"intencion","n":57,"mantener":["derecha","sigilo"],"pulsar":["interactuar"]}` |
| S→C | `estado` (delta) | `{"tipo":"estado","c":1204,"ack":[57,40],"snd":[["paso",0.3]],"base":1202,"s":{"j0":{"x":4012.0,"hx":4086,"a.fase_latido":0.86},"al":{"3":[2210,760,-3.12]}}}` |
| S→C | `estado` (completa) | `{"tipo":"estado","c":1200,"ack":[57,40],"snd":[],"base":null,"z":"eJztvdty..."}` (zlib + base64) |
| C→S | `completa` | `{"tipo":"completa"}` (me faltó una delta: la próxima, entera) |
| C→S | `adios` | `{"tipo":"adios"}` (cerrar el socket vale lo mismo) |
| S→C | `fin` | `{"tipo":"fin","texto":"El servidor se cerró."}` |
| S→C | `error` | `{"tipo":"error","texto":"la partida ya tiene sus 2 jugadores"}` |

Las acciones son nombres, no teclas: `arriba abajo izquierda derecha sigilo
interactuar` se mantienen; `interactuar habilidad habilidades celular soltar
volver` y las cuatro direcciones se pulsan. Cada cliente traduce sus teclas o
mandos a acciones y el servidor las traduce a las teclas del puesto de ese
jugador. Lo mantenido es "estado" (la última intención manda; se repite cada
100 ms); lo pulsado es "evento" y se acumula hasta el siguiente cuadro.

## Qué se manda y cuánto pesa

La instantánea completa es un diccionario de **secciones**:

| Sección | Qué lleva |
|---|---|
| `g` | lo legible: tiempo, fase, objetivo, resultado, piezas, cápsula, puntos, presentación de alien, y `G.*` (tiempo jugado, oscuridad...) |
| `j0`..`j3` | cada jugador: lo legible (x, y, dirección, vidas, panel...) y `a.*` = todos los atributos de datos del `Jugador` (pulso, susto, mensajes, panel, cursor, inventario...), `h.*` = su árbol de habilidades, `lin` = ángulo de la linterna, `escondite` = índice |
| `al` | por alien `"3": [x, y, ángulo]` (cambia siempre) y `"3d": [nombre, alcance, medio ángulo, {acción, alerta...}]` (casi nunca) |
| `m`, `ev`, `eq`, `nx`, `inf`, `gp`, `tut`, `nar`, `lg`, `pr`, `npc`, `cf` | misión, eventos (apagón), equipo, NEXUS (celular), infiltrado, guardia y planta, tutorial, narrador, logros, presentación, NPC, cambiaformas: sus atributos de datos |
| `pz`, `te`, `pa`, `sn`, `sl`, `pd`, `cp`, `es` | listas: piezas, terminales, paneles, señuelos, señales, puertas dobles, compuertas, escondites (`{"n": 3, "0": ..., "1": ...}`) |

`estado.extraer` convierte los datos a JSON: números (floats a 2
decimales), textos, listas, dicts, `Rect` como `{"R":[x,y,w,h]}` y sets como
`{"S":[...]}`. Las referencias a otros objetos (el juego, el mundo, el alien
que te persigue) **no** viajan: cada lado tiene las suyas.

**Delta**: casi todas las instantáneas llevan solo las claves que cambiaron
desde la anterior (`base` = el cuadro de la anterior). La completa va al que
llega, al que vuelve, al que la pide y cada 5 s, comprimida. Una delta de más
de 1200 B también va comprimida (`z`).

Medido (MapaFinal, jugadores caminando, aliens patrullando, 300
instantáneas seguidas; el servidor también imprime su media y máximo al cerrarse).
"con zlib" es el tamaño comprimido; con base64 dentro del JSON suma un tercio:

| | delta media | delta máx. | completa (zlib) |
|---|---|---|---|
| prototipo (todo cada vez, sin espejo) | 2 937 B | 3 531 B | — |
| 2 jugadores, delta sin comprimir | 4 467 B | 5 503 B | ~10 100 B |
| 4 jugadores, delta sin comprimir | 6 481 B | 7 706 B | ~10 400 B |
| 2 jugadores, delta con zlib | ~1 470 B | ~2 000 B | ~10 100 B |
| 4 jugadores, delta con zlib | ~1 620 B | ~2 200 B | ~10 400 B |

O sea ~60 KB/s por conexión a 30 instantáneas por segundo: nada para una
LAN. Lo que más pesa en la delta son los NPC caminando y los aliens; las
claves cortas por alien bajaron los aliens de 2,7 KB a 0,7 KB por instantánea.

## Interpolación

Llegan 30 instantáneas por segundo (y por la red, a tirones). El cliente
dibuja **100 ms en el pasado**: guarda un segundo de posiciones (jugadores:
x, y y ángulo de la linterna; aliens: x, y, ángulo) y mezcla las dos que
rodean ese momento. El tiempo del servidor sale del número de cuadro (`c`, 60
por segundo); el desfase con el reloj local se toma de la llegada más rápida
vista, así un mensaje que llega tarde no mueve la referencia. Los ángulos van
por el lado corto. Si algo salta más de 300 px (un teletransporte) no se
interpola. Lo demás (vidas, paneles, misión) va con la última instantánea.

## Reconexión y cortes

- La bienvenida trae un `token`. Si el socket se cae (o no llega nada en
  3 s), el lector del cliente vuelve a conectar durante 10 s mandando el
  token y recupera su mismo jugador; mientras, sale "Se cortó la conexión:
  reconectando..." y el jugador se queda quieto en el servidor.
- Si el servidor se cierra (Ctrl+C, o la laptop que creó la partida sale al
  menú: en Linux/Mac se le manda Ctrl+C; en Windows se termina el proceso y
  los demás se enteran por el silencio) manda `fin` a todos: los clientes muestran el aviso y vuelven al menú.
  Si se muere sin avisar, el cliente no recibe nada en 3 s, intenta 10 s y
  vuelve al menú con "Se perdió la conexión con el servidor".
- El servidor espera `--espera` segundos (30) sin nadie conectado antes de apagarse.
- Si falta una delta (la `base` no coincide), el cliente pide `completa`.

## Qué dibuja el cliente: el espejo

El cliente arma **la misma partida** que el servidor con el `Game` del juego
(mismo mapa, roles, dificultad y semilla de `random`), pero **nunca la
actualiza**: cada cuadro le copia encima la instantánea (`estado.aplicar`) y
llama las mismas funciones de dibujo del modo local
(`Game._dibujar_partida_en` → `screens/partida.py`, `paneles.py`,
`celular.py`, `juego/oscuridad.py`, `vision.py`...). Así se ve igual que el
local: vistas divididas (solo las de los jugadores de esa laptop), HUD,
oscuridad y linterna en los apagones, campo de visión, sustos, paneles,
celular, cartel de la IA, presentación de aliens y la pantalla de resultados.
`pruebas/prueba_red_capturas.py` dibuja el mismo estado con el modo local y
con el espejo y da menos de 1 % de píxeles distintos.

Si el espejo no sabe dibujar algo (un panel con objetos que no viajan), la
sesión no se cae: imprime el error y sigue con el dibujo sencillo.

## Pruebas

| Prueba | Qué revisa |
|---|---|
| `prueba_cliente_servidor.py` | el protocolo con clientes falsos: saludo, mover, ack, celular, partida llena |
| `prueba_red_jugable.py` | sockets reales y el cliente real: 2 jugadores en una ventana, reconexión, cierre del servidor, 4 jugadores en dos "laptops" (teclado y mandos) hasta la victoria y los resultados |
| `prueba_red_proxy.py` | proxy con 80 ms de retraso y 15 % de instantáneas descartadas, y un corte: siguen jugando y vuelven |
| `prueba_red_capturas.py` | modo local vs espejo, píxel por píxel (dos vistas, una, apagón, panel) |

## Para la sustentación (en corto)

1. **Arquitectura cliente-servidor autoritativa**: el servidor corre el juego
   de verdad (el mismo código del modo local, sin ventana) y es la única
   verdad. Los clientes mandan *intenciones* ("voy a la derecha"), no
   posiciones: así nadie puede hacer trampa moviendo su jugador.
2. **TCP con un JSON por línea**: TCP es un chorro de bytes, por eso un
   lector arma las líneas completas (una cola de bytes, un búfer).
3. **Hilos**: un hilo por conexión lee y deja la intención en un buzón con
   candado (productor-consumidor); solo el hilo principal toca el juego.
4. **Instantáneas delta**: un diccionario por sección y se manda la
   *diferencia* con la anterior (como un diff); la completa va comprimida.
   De ~30 KB a ~1,5 KB por instantánea.
5. **Interpolación**: un búfer (cola) con un segundo de instantáneas; se
   dibuja 100 ms atrás mezclando dos, así 30 por segundo se ven como 60.
6. **Reconexión con token**: un diccionario token → puesto en el servidor.
7. **Espejo**: el cliente reutiliza el dibujo del juego en vez de
   reescribirlo; la prueba de capturas demuestra que se ve igual.
