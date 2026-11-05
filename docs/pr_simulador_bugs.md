# Simulador masivo de partidas y bugs que encontró

Rama: `claude/simulador-bugs` (desde `main`).

## Qué hace el simulador

`pruebas/simulador_masivo.py` juega partidas completas sin ventana
(`SDL_VIDEODRIVER=dummy`) con bots, para recorrer muchos estados del juego y
cazar bugs. Es el hermano grande de `pruebas/simulador.py` (que mide el
balance con 2 bots que no usan nada más):

- **2, 3 y 4 jugadores** (el juego es de 2 a 4) en las **cuatro dificultades**
  (facil, normal, dificil, inteligente), con roles al azar y **semillas
  deterministas**: la partida `i` con la semilla `S` siempre es la misma
  configuración (`configuracion(i, S)`).
- **Pasa por los menús de verdad**: Jugar, cantidad, dificultad, "¿Con qué
  juega cada uno?" (pantalla `controles`) y selección de rol, con las teclas
  de cada jugador.
- **Jugadores 3 y 4 con mando**: se conectan dos `MandoFalso` en
  `Mandos.por_puesto` (lo mismo que haría `pygame.joystick`). Lo que se
  mantiene (cruceta, A, LB) lo lee `juego/mandos.py` desde el mando falso, y
  lo que se presiona una vez se manda como `pygame.event.Event(JOYBUTTONDOWN /
  JOYHATMOTION)` por `Mandos.evento` y `Game._tecla_mando`, el mismo camino de
  un control de Xbox. No se cambió el juego para esto. A veces el jugador 2
  también escoge un mando, a veces se juega con los esquemas mezclados, y en
  ~10 % de las partidas de 3-4 no hay mandos (el 3 y el 4 no se mueven, como
  en el juego real sin mandos).
- **Bots**: caminan con BFS sobre una cuadrícula del mapa (con componentes
  conexas cacheadas para saber rápido si hay camino) hacia lo que dice la
  flecha de la misión (`Mision.punto_objetivo`), presionan o mantienen la
  tecla al llegar, marcan el código si lo leyó alguien del equipo (a veces se
  equivocan a propósito), rescatan, prenden la caja de fusibles, abren las
  puertas para dos (uno en cada panel), huyen y se esconden cuando los
  persiguen, juegan el minijuego del escondite, esperan en sigilo si todos los
  caminos pasan por un alien, se dejan atrapar a propósito de vez en cuando,
  abren el celular (NEXUS: investigar, desmentir con foto recortada o tal
  cual, compartir, rastrear, reportar, cambiar de pestaña), el árbol de
  habilidades (compran lo que alcanza), usan la habilidad (Emisión con el
  cursor del mapa incluida), sueltan cosas, entran a las Terminales NEXUS y
  abren la pausa. Todo con azar sembrado.
- **Partidas asistidas** (50 %): los aliens ven y oyen al 45 %, porque los bots
  son mucho peores que una persona en sigilo. **Partidas con atajo** (45 %): al
  terminar el tutorial se abren las puertas con código y se apagan las
  consolas (con `Mision.abrir_puerta` y el progreso de las consolas), para que
  también se juegue la fase de la cápsula.
- **Mide el tiempo** de actualizar (cada cuadro) y de dibujar (el dibujado
  real, `Game._dibujar`, sobre la pantalla dummy, cada N cuadros) con
  `time.perf_counter`.
- Corre en paralelo con `multiprocessing` (por defecto núcleos − 1).
- No escribe en `Guardado/logros.json` (se parchea `historial_logros.agregar`).

### Qué detecta

| Tipo | Qué es |
|---|---|
| `excepcion` | algo reventó (con traceback) |
| `inalcanzable` | consola, cápsula, celda, nota de código, puerta, consumible, pieza, caja de fusibles, panel de puerta para dos, Terminal NEXUS, planta o lugar de un rumor al que no se llega caminando desde el inicio ni con todas las puertas abiertas (cuadrícula libre del mapa fijo) |
| `mision_imposible` | piezas sueltas + en manos + entregadas < 3; sabotaje sin Tecnomante que se mueva y sin decodificador; cápsula sin Forjador que se mueva y sin kit |
| `jugador_en_pared` | hitbox de un jugador libre solapada con paredes o puertas más de 0,5 s |
| `alien_en_pared` | hitbox de un alien solapada con paredes más de 1 s |
| `alien_atascado` | alien patrullando o volviendo con `atascado_ms` > 4 s |
| `bot_trabado` | bot con meta que no se mueve en 8 s (muchas veces es del bot) |
| `panel_sin_cerrar` | un panel que sigue abierto 25 s aunque el bot presione todas las teclas de cerrar |
| `estado_imposible` | vidas < 0 o > máximo, piezas negativas, inventario con cantidades ≤ 0, eliminado que se mueve / está preso / escondido, preso sin celda o en una celda que dice otro preso, celda con un preso que no está en ella, escondite con ocupante ajeno, escondido y preso a la vez, minijuego sin estar escondido, panel abierto estando preso o eliminado, cursor fuera de rango, jugador o alien fuera del mapa, puntos del equipo negativos, fase desconocida, piezas entregadas fuera de 0-3, progreso fuera de [0, 1] |
| `sin_terminar` | llegó al límite de tiempo simulado sin ganar ni perder |
| `cuadro_lento` | actualizar o dibujar > 25 ms |

### Cómo correrlo

```bash
python pruebas/simulador_masivo.py                        # 24 partidas: 2/3/4 x 4 dificultades
python pruebas/simulador_masivo.py -n 120 -p 3            # 120 partidas en 3 procesos
python pruebas/simulador_masivo.py -n 8 -j 4 -d dificil   # solo 4 jugadores en Difícil
python pruebas/simulador_masivo.py -n 12 --semilla 500 --sin-dibujo --max-s 300
python pruebas/simulador_masivo.py -n 1 --desde 9 --semilla 2 -v   # repetir la partida 9
```

Opciones: `-n/--partidas`, `-j/--jugadores` (p. ej. `2,3,4`), `-d/--dificultad`
(separadas por coma), `--semilla`, `--desde`, `--max-s` (segundos simulados
por partida, 480 por defecto), `--sin-dibujo`, `--cada-dibujo N`,
`-p/--procesos`, `--mapa` (por defecto el activo, hoy MapaFinal) y `-v` (una
línea por partida con sus problemas). Al final imprime los resultados por
configuración, el tiempo medio por cuadro, cuántas partidas tuvieron cada tipo
de problema, el detalle de cada problema distinto (con las partidas donde
salió, para repetirlas) y los cuadros más lentos. Sale con código ≠ 0 si hubo
excepciones, estados imposibles, misiones imposibles, jugadores en paredes o
cosas inalcanzables.

Cada partida de 300 s simulados tarda ~50-110 s reales en esta máquina
(~0,6-1 ms por cuadro de actualizar y ~5-10 ms por dibujo con 4 vistas).

## Partidas jugadas

Todas en MapaFinal (el mapa activo), 300 s simulados como máximo (las
primeras 12, 360 s).

**101 partidas** en cuatro tandas (más unas cuantas sueltas para depurar):

| Tanda | Partidas | Código del juego |
|---|---|---|
| 1 (semilla 1, 360 s) | 12 | sin arreglos |
| 2 (semilla 1) | 19 | con el arreglo 1 (se cortó para meter el atajo) |
| 3 (semilla 2) | 34 | arreglos 1 y 2, el 3 entró a mitad de tanda |
| 4 (semilla 2, mismas configuraciones que la 3) | 36 | los tres arreglos |

Por configuración (jugadores × dificultad), sumando las cuatro:

| | facil | normal | dificil | inteligente |
|---|---|---|---|---|
| 2 jugadores | 9 | 9 | 9 | 9 |
| 3 jugadores | 8 | 9 | 9 | 9 |
| 4 jugadores | 8 | 8 | 7 | 7 |

En las tandas 3 y 4, 27 partidas fueron con atajo a la cápsula y ~la mitad
asistidas. Resultados de la tanda 4: 11 derrotas y 25 sin terminar en 300 s
(ninguna victoria: ver "Pendiente").

## Problemas encontrados

Partidas con al menos un problema de cada tipo:

| Tipo | Tanda 1 (antes, 12) | Tanda 2 (19) | Tanda 3 (34, mixta) | Tanda 4 (después, 36) |
|---|---|---|---|---|
| excepcion | 0 | 0 | 0 | 0 |
| inalcanzable | 0 | 0 | 0 | 0 |
| mision_imposible | 0 (*) | 0 (*) | 0 (*) | 0 |
| jugador_en_pared | 0 | 0 | 0 | 0 |
| alien_en_pared | 0 | 0 | 0 | 0 |
| alien_atascado | 0 | 0 | 0 | 0 |
| panel_sin_cerrar | 0 | 0 | 0 | 0 |
| estado_imposible | 0 | **2** (inventario con 0) | 0 | 0 |
| bot_trabado | 8 (**4** yendo a la nota encerrada) | 12 | 20 | 20 (ninguno a la nota encerrada) |
| sin_terminar | 3 | 11 | 19 | 25 |
| cuadro_lento | 9 | 14 | 27 | 32 |

(*) La misión imposible por los roles sin mando (arreglo 3) no la contaba el
simulador todavía: miraba a los vivos y no a los que se pueden mover. La vi
siguiendo a mano una partida de la tanda 3 (#9: 4 jugadores, Normal, sin
mandos, Forjador en el puesto 4, 300 s en la cápsula con 0 piezas) y después
corregí la revisión del simulador.

`sin_terminar` y `cuadro_lento` suben entre tandas porque las tandas 3 y 4
tienen más partidas de 4 jugadores (más vistas que dibujar) y con atajo (que
llegan al límite de tiempo en vez de perder pronto). En la tanda 4: tiempo
medio por cuadro 0,94 ms al actualizar y 8,9 ms al dibujar; el cuadro más
lento, 437 ms al dibujar (con la máquina cargada: ver "Pendiente").

## Qué se arregló

1. **La flecha apuntaba a una nota encerrada detrás de otra puerta**
   (`misiones/mision.py`, `Mision.punto_objetivo` / `_guiar_a_puerta`). En
   MapaFinal hay tres puertas con código, y el código de una puede quedar en
   una nota detrás de otra puerta cerrada (lo permite `sortear_candidatas`).
   La flecha escogía la puerta cerrada más cercana y su nota sin leer más
   cercana sin mirar si había camino: cuando la que faltaba era la encerrada,
   apuntaba a un lugar inalcanzable. El simulador lo vio como bots "trabados,
   sin ruta" yendo a la misma nota (2807, 5586) en 4 de las primeras 12
   partidas. Ahora prueba las puertas de la más cercana a la más lejana y usa
   la primera cuya nota sin leer tiene camino (si ninguna, sigue con lo demás
   de la misión). Prueba: `pruebas/prueba_flecha_puertas.py` (falla sin el
   arreglo en la semilla 0).
2. **El inventario dejaba tipos en 0** (`entidades/jugador.py`,
   `Inventario.discard`). `Counter.__delitem__` solo borra si `tipo in self`,
   y `Inventario.__contains__` es "cuenta > 0": con la cuenta en 0 no borraba
   y quedaba `{"fruta": 0}` (inventario vacío pero verdadero, `len` 1). Salió
   como `estado_imposible` en 2 de 19 partidas (fruta después de dársela al
   Guardia y un decodificador). Ahora se borra con
   `dict.pop`. Prueba: `pruebas/prueba_inventario.py`.
3. **Con 3-4 jugadores sin mandos la misión podía quedar imposible**
   (`misiones/mision.py`, `Mision.__init__`). Sin mandos el 3 y el 4 no se
   mueven (está en el README) y la misión ya no los contaba para ganar ni
   perder, pero sí para decidir qué roles faltaban: con el Tecnomante o el
   Forjador en esos puestos no salían ni el decodificador ni el kit, y nadie
   que caminara podía hackear o recoger piezas. Salió en una partida de 4 sin
   mandos atascada en la cápsula con 0 piezas. Ahora solo cuentan los roles de
   los que se pueden mover. Prueba: `pruebas/prueba_roles_sin_mando.py`.
   `pruebas/prueba_guardia.py` asumía que en sus partidas de 4 contaban los
   cuatro roles: ahora conecta dos mandos quietos (`MandoQuieto`) para eso.

Los cambios al juego son de pocas líneas y están en `misiones/mision.py` (dos
lugares) y `entidades/jugador.py` (una línea), para no chocar con la revisión
de esos archivos en la otra rama. No se tocaron textos, controles, balance ni
assets. Las 33 pruebas de antes y las 3 nuevas pasan.

## Pendiente o dudoso

- **Los bots no llegan a la huida.** Aun con partidas asistidas y con atajo,
  ninguna partida llegó a la fase de huida en 300 s: los bots juntan pocas
  piezas, casi no consiguen los planos (NEXUS) y los atrapan seguido. Así que
  la huida, la reparación completa y la pantalla de resultados de victoria
  están poco cubiertas. Mejorar los bots (o un atajo más largo) es lo
  siguiente.
- **`bot_trabado` y `sin_terminar`** son casi siempre límites de los bots
  (rodear esquinas, huir, mucha gente atrapada). No se "arreglaron" en el
  juego. Después del arreglo 1 no volvió a salir ningún bot yendo a la nota
  encerrada, pero en la tanda 4 sigue habiendo bots "sin ruta" hacia una
  celda (rescate) y hacia consolas en el sabotaje. Lo más probable es que sea
  del bot (el radio con el que da por buena la llegada a una celda es más
  chico que el `RADIO_RESCATE` del juego) o compuertas/puertas cerradas en
  ese momento, pero no alcancé a confirmarlo: vale la pena repetir esas
  partidas con `-v` y mirar.
- **Cuadros lentos.** Salen en casi todas las partidas, casi todos al
  dibujar con 4 vistas (25-85 ms) y algunos raros de más de 100 ms. Ojo: la
  máquina tenía otros agentes trabajando y 3 procesos del simulador a la vez,
  así que los números exactos tienen ruido. Uno claro: la primera vez que el
  Resonante abre la Emisión, `screens/partida.py: render_mapa_emision` hace un
  `smoothscale` del mapa entero (6144×6144) y el cuadro tarda ~60-80 ms; queda
  en caché pero se podría precargar al cargar la partida (como
  `precargar_iconos`). No lo cambié porque `juego/app.py` y
  `screens/partida.py` los está revisando otra rama.
- Las partidas "antes" y "después" no son exactamente los mismos procesos:
  los arreglos 2 y 3 se hicieron mientras corría una tanda (los procesos del
  simulador se reinician cada 4 partidas y toman el código nuevo), así que el
  conteo de esas tandas mezcla las dos versiones. La tanda "después" se jugó
  entera con todos los arreglos.
- `inalcanzable`, `jugador_en_pared`, `alien_en_pared`, `alien_atascado`,
  `panel_sin_cerrar` y `excepcion` no salieron en ninguna partida en
  MapaFinal. No probé Nave ni MapaE2 de forma masiva (`--mapa Nave`).
