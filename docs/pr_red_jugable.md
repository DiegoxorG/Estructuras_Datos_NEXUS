# PR: modo en red jugable (Jugar en red)

Rama `claude/red-jugable`, desde `claude/cliente-servidor` (PR #1).

## Qué hay

- **Menú > Jugar en red** (`cliente_servidor/lanzador.py`): crear partida en
  esta laptop (levanta el servidor en otro proceso con `--host 0.0.0.0`) o
  unirse por IP; cuántos juegan aquí, teclado o mandos primero, dificultad.
  Todo en la misma ventana del juego; al terminar vuelve al menú.
- **El cliente se ve como el modo local** (`cliente_servidor/espejo.py`): arma
  la misma partida con el `Game` del juego, le copia encima cada instantánea
  y llama las funciones de dibujo de siempre: vistas divididas, HUD,
  oscuridad y linterna, visión, sustos, paneles, celular, cartel de la IA,
  presentación de aliens, resultados. Sonidos: el servidor manda lo que sonó.
- **Instantáneas delta** por sección (`cliente_servidor/estado.py`), completas
  comprimidas (zlib + base64). Medido: delta sin comprimir 4,5 KB (2 jugadores)
  y 6,5 KB (4); comprimida ~1,5 y ~1,6 KB (+1/3 de base64); completa ~10 KB. Detalle en `docs/cliente_servidor.md`.
- **Interpolación** con 100 ms de búfer (`cliente_servidor/interpolacion.py`).
- **Robustez**: token de reconexión, `fin` al cerrar el servidor, 3 s de
  silencio = conexión caída, 10 s para reconectar, pedir `completa` si falta
  una delta, el servidor espera 30 s sin nadie antes de apagarse.
- **Pruebas** (sockets reales, sin ventana, < 15 s cada una):
  `prueba_red_jugable.py`, `prueba_red_proxy.py` (latencia y pérdida con un
  proxy), `prueba_red_capturas.py` (local vs espejo, < 1 % de píxeles
  distintos); `prueba_cliente_servidor.py` actualizada al protocolo 2.
- `docs/cliente_servidor.md` reescrito (uso, protocolo con ejemplos, tamaños,
  interpolación, reconexión, guion para la sustentación).

Cambios al juego: `screens/menu.py` (una opción más, "Jugar en red") y
`juego/app.py` (`_activar_opcion_menu` llama al lanzador, 5 líneas). Nada más
del modo local cambia.

## Cómo probarlo a mano en dos laptops

1. Las dos en la misma red (wifi de la feria o un router). En Windows, la
   primera vez el firewall pregunta si Python puede usar la red: **permitir**
   (red privada).
2. Laptop A: `python main.py` > Jugar en red. "Jugadores en la partida: 4",
   "Juegan en esta laptop: 2", Crear partida. Abajo dice "La IP de esta laptop es ...".
3. Laptop B: `python main.py` > Jugar en red. "Juegan en esta laptop: 2",
   "Controles: mandos primero" si tienen mandos, bajar a "IP para unirse",
   escribir la IP de A, Enter.
4. Jugar. Probar: desconectar el cable/wifi de B unos segundos (debe decir
   "reconectando..." y volver); Esc en B (A sigue, el jugador de B se queda
   quieto); Esc en A (cierra el servidor: B muestra el aviso y vuelve al menú; en
   Windows tarda ~13 s porque el proceso se termina sin mandar `fin`).
5. Una sola laptop: "Jugadores en la partida: 2", "Juegan en esta laptop: 2", Crear.

Por comandos: ver `docs/cliente_servidor.md`.

## Limitaciones

- **Pausa en red**: no hay (Esc sale al menú). Pausar a todos desde un cliente
  no se hizo.
- **Roles**: van en orden (Tecnomante, Forjador, Biomante, Resonante); la
  selección de rol del modo local no está en red (`--roles` por comandos).
- El tutorial se salta en red.
- El espejo no copia objetos que viven como referencias (por ejemplo los
  logros nuevos o algunas publicaciones del celular creadas en la partida):
  el aviso de logro y parte del celular pueden no verse igual. Si un panel no
  se puede dibujar, se cae al dibujo sencillo (y se imprime el error).
- La animación de los aliens del espejo no avanza (se ven en su pose; se mueven bien).
- Las pistas de teclas del HUD son las del puesto en el servidor (en la
  laptop B, J3 ve las pistas del mando aunque juegue con WASD).
- `F9` (dos pantallas) no aplica en red: cada laptop dibuja solo a sus jugadores.
- Puerto fijo 5050 para "Crear partida": si está ocupado avisa y no arranca.
- Se probó con pygame 2.6.1 sin ventana (driver dummy); NO con pygame-ce
  (no alcanzó el tiempo), ni con ventana real, mandos físicos o dos laptops.

## Decisiones tomadas sin consultar

- La opción va en el **menú principal** ("Jugar en red"), no en la selección
  de cantidad, para no tocar el flujo local.
- El cliente usa un **Game espejo** en vez de un objeto "estado de vista":
  cero cambios en `screens/` y se ve igual por construcción.
- Delta por sección/clave con JSON (no binario) para que se pueda leer en la
  sustentación; zlib solo para la completa y las delta grandes.
- El servidor del menú es un **subproceso** (no un hilo): `Game` no es
  seguro para hilos y así un error del servidor no tumba la ventana.
- `--fase-final` (atajo de pruebas) pone a todos junto a la cápsula en la huida.
