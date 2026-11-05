# Guía rápida

Lo mínimo para correr NEXUS, sus pruebas, el simulador y los editores. Todos
los comandos se corren desde la raíz del repositorio. El README tiene el
detalle de cómo se juega; esto es para arrancar rápido.

## Requisitos

- Python 3.
- Pygame: `pip install pygame` (es lo que dice el README). También funciona
  con `pygame-ce` (`pip install pygame-ce`); con pygame-ce la segunda pantalla
  (F9) usa `pygame.Window` y sale un poco más barata. No hay que instalar las
  dos: las dos se importan como `pygame`.
- Para jugar de 3 o 4 hace falta al menos un mando (tipo Xbox). Sin mandos,
  el jugador 1 va con WASD y el 2 con flechas, y el 3 y el 4 escogen rol pero
  no se mueven.

No hay `requirements.txt`: pygame es la única dependencia.

## Correr el juego

```bash
python main.py
```

Jugar → cuántos juegan (2, 3 o 4) → dificultad → (si hay mandos) con qué
juega cada uno → rol de cada uno → pantalla de carga → partida. El mapa que
se carga lo dice `Hitboxes/mapa_activo.json` (hoy `MapaFinal`); se cambia
desde el editor de mapa con la tecla M.

### Teclas globales

| Tecla | Qué hace |
|---|---|
| F11 | alterna entre ventana y pantalla completa |
| F3 | primera vez: FPS y ms de actualizar y dibujar arriba a la derecha; segunda: además perfila cada cuadro y anota los tirones (más de 40 ms) en la consola y en `Guardado/tirones.txt`; tercera: apagado |
| F9 | prende o apaga la segunda pantalla: con 3 o 4 jugadores, J3 y J4 se dibujan en otra ventana sin bordes en el otro monitor (en Windows tiene que estar en "Extender") |
| ESC (o START en el mando) | en partida abre el menú de pausa (continuar, opciones, logros, terminar partida); en el menú principal cierra el juego |

En Pausa > Opciones están las vistas para la sustentación: apagar el campo
de visión y la oscuridad, ver las hitboxes, ver el árbol de comportamiento de
cada alien en vivo y ver los grafos (NEXUS y la nave).

Las teclas de cada jugador están en la tabla del README.

## Pruebas

Las pruebas son scripts en `pruebas/` que corren sin abrir ventana. Para
correrlas todas de una (hoy son 33 archivos `prueba_*.py`):

```bash
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
for f in pruebas/prueba_*.py; do python "$f" || echo FALLA $f; done
```

Si solo se quiere ver cuál falla, sin toda la salida:

```bash
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
for f in pruebas/prueba_*.py; do python "$f" >/dev/null 2>&1 || echo FALLA $f; done
```

Si no imprime ningún `FALLA`, pasaron todas. En una máquina de 4 núcleos la
corrida completa tarda unos dos minutos y medio.

Las variables `SDL_VIDEODRIVER=dummy` y `SDL_AUDIODRIVER=dummy` hacen que
pygame no abra ventana ni busque parlantes. Con ellas, además, el juego no
escribe en `Guardado/logros.json` (`juego/historial_logros.py` lo revisa),
así que correr las pruebas no ensucia el historial de logros.

Algunas para correr solas:

```bash
python pruebas/prueba_estructuras.py   # los árboles por consola
python pruebas/prueba_aliens.py        # árbol de comportamiento: cada condición y acción existe
python pruebas/prueba_nexus.py         # grafo de NEXUS, rumores, celular, barras y planos
python pruebas/prueba_vista_grafo.py   # la vista de los grafos
python pruebas/prueba_logros.py        # árbol de logros y cuándo sale cada uno
python pruebas/prueba_partida.py       # una ronda completa sin ventana
```

`pruebas/probar_mando.py` no es una prueba automática: abre una ventana y
muestra qué número manda cada botón del mando, por si hay que ajustar
`juego/mandos.py`.

## Simulador

`pruebas/simulador.py` pone bots a jugar la misión de punta a punta sin
ventana. Sirve para encontrar bugs (algo que revienta, un bot o un alien
trabado) y para medir el balance (cuánto dura cada fase, cuántas capturas,
qué tipo de alien atrapa más).

```bash
python pruebas/simulador.py                         # 10 partidas, roles variados
python pruebas/simulador.py 30                      # 30 partidas
python pruebas/simulador.py 5 Biomante Resonante    # 5 partidas con esos dos roles
python pruebas/simulador.py 3 --desde 10            # partidas 10, 11 y 12
python pruebas/simulador.py 6 --dificultad facil    # facil, normal, dificil o inteligente
```

Los bots siempre son dos jugadores y juegan en el mapa `Nave` (el simulador
lo fija con `objetos_mapa.mapa_activo = lambda: "Nave"`), no en el
`MapaFinal` del juego. Sin `--dificultad` la partida queda sin objeto
`Dificultad` y cada parte usa sus números base, que son los de la columna
Pesadilla de `data/dificultad.py` (el comentario del simulador dice "como
Difícil"; ver las contradicciones en `docs/pr_documentacion.md`). Cada partida corre un `Game` completo, así que varias seguidas
cargan la máquina: si hay otras cosas corriendo, mejor pocas partidas.

## Editores

Están en `Editores/` y abren su propia ventana (no corren con
`SDL_VIDEODRIVER=dummy`).

| Comando | Para qué |
|---|---|
| `python Editores/editor_mapa.py [Mapa]` | pone con el mouse todo lo que va encima del mapa: inicio de los jugadores, rutas y tipo de cada alien, escondites, celdas, puertas con código y sus notas, consolas, cápsula, piezas, terminales NEXUS, compuertas, puertas para dos, cajas de fusibles, pruebas del infiltrado, salas, Guardia y planta. Sin argumento muestra la lista de fondos. Clic izquierdo pone o arrastra, clic derecho borra, Ctrl+S guarda en `Hitboxes/<mapa>_objetos.json`, M hace que el juego use ese mapa y F5 guarda y abre el juego. |
| `python Editores/hitbox_editor.py [imagen]` | dibuja las paredes de un mapa (`Hitboxes/<mapa>_hitboxes.json`). Sin argumento deja escoger un fondo de `Imagenes/Fondos/`. Rueda = zoom, 0 = ver todo, clic del medio = mover. |
| `python Editores/personaje_editor.py [sprite]` | calibra la escala y las dos hitboxes (roja de colisión, amarilla de interacción; I alterna) de cada rol y las guarda en `Hitboxes/<Rol>_config.json`, que es lo que lee `Movimiento/Personaje.py`. |
| `python Editores/visor_personajes.py [carpeta]` | muestra un personaje animado para revisar que estén las 8 direcciones y las animaciones. Flechas o WASD lo mueven, ESPACIO cambia la animación en reposo, TAB pasa al siguiente personaje, H muestra las hitboxes, ESC sale. |

Para un mapa nuevo: primero las paredes con `hitbox_editor.py` y después todo
lo demás con `editor_mapa.py`. Las pruebas `prueba_editor_mapa.py` y
`prueba_hitbox_editor.py` revisan que lo que guardan los editores sea lo que
el juego carga.

## Dónde seguir

- `docs/estructuras.md`: los árboles y el grafo, con sus operaciones y
  complejidades.
- `docs/arquitectura.md`: los módulos, el bucle de un cuadro y el modo en red.
