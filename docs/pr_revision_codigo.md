# Revisión de código: errores lógicos y casos borde

Revisé sobre todo `juego/app.py`, `misiones/`, `entidades/`, `screens/partida.py`
y `screens/paneles.py`, y lo que usan (`juego/mandos.py`, `juego/segunda_pantalla.py`,
`juego/pausa.py`, `juego/transition_manager.py`, `juego/tutorial.py`,
`juego/dificultad.py`, `juego/presentacion_aliens.py`, `juego/ambiente.py`).
Busqué divisiones por cero e índices fuera de rango, estado que pasa de una
partida a la otra, cambios de resolución (F11, F9) a mitad de partida, mandos
que se desconectan, y la pausa durante sustos, transiciones, apagones,
minijuegos, paneles y la presentación de aliens.

Cada bug se reprodujo antes de arreglarlo y tiene su prueba en `pruebas/`
(script autónomo, como las demás; cada una falla sin el arreglo). Las 33 pruebas
de antes y las 5 nuevas pasan después de cada commit.

Lo dudoso que no toqué va aparte, en la rama `claude/revision-dudas`
(`docs/revision_dudas.md`).

## Bugs arreglados

### 1. La vista del grafo pasaba a la partida siguiente
- **Síntoma:** si en Pausa > Opciones se prendía "Grafo: NEXUS" (o "Nave") y
  se terminaba la partida, la siguiente arrancaba tapada por el grafo.
- **Causa:** `Game.vista_grafo` solo se fijaba en `__init__`; el árbol del
  alien sí se apagaba en `_crear_aliens`, el grafo no.
- **Arreglo:** `_crear_aliens` también pone `vista_grafo = None`.
- **Prueba:** `pruebas/prueba_nueva_partida.py` (una de 4 en Fácil terminada
  desde la pausa y otra de 2 en Difícil desde el menú; además revisa pausa,
  cronómetro, vidas de la dificultad nueva, tutorial y Sombra).

### 2. Un tirón hacía saltar la partida varios segundos
- **Síntoma:** después de un cuadro trabado (F9 abriendo la otra ventana,
  arrastrar la ventana en Windows con F11, la laptop que se suspende), todo lo
  que avanza con `dt` saltaba de golpe: el minijuego del escondite se podía
  llenar en un cuadro (atrapado sin poder hacer nada), los sustos y avisos se
  saltaban, y los relojes de celdas, eventos y director corrían segundos.
- **Causa:** `Game.run` pasaba el `clock.tick()` entero.
- **Arreglo:** `dt = min(clock.tick(...), DT_MAXIMO_MS)` con
  `DT_MAXIMO_MS = 100` (unos 10 FPS).
- **Prueba:** `pruebas/prueba_cuadro_lento.py` (corre el `Game.run` de verdad
  con un reloj que devuelve 5000 ms en un cuadro y un jugador en el minijuego).

### 3. Mandos conectados o desconectados durante la carga
- **Síntoma:** si un mando se desconectaba en la pantalla de carga, al
  reconectarlo no volvía a funcionar (el jugador quedaba sin control toda la
  partida); uno que se conectaba durante la carga no se anotaba nunca.
- **Causa:** `_manejar_eventos` tiraba todos los eventos mientras
  `self.carga` existía, también `JOYDEVICEADDED`/`JOYDEVICEREMOVED`. El mando
  quitado seguía en `Mandos.por_puesto` ocupando su puesto, y el reconectado
  (con otro `instance_id`) ya no tenía lugar.
- **Arreglo:** esos dos eventos se procesan siempre (antes del filtro de la
  carga). Y como los jugadores se crean en el otro hilo, al terminar de cargar
  se llama otra vez a `_sincronizar_mandos`.
- **Prueba:** `pruebas/prueba_mando_desconectado.py` (sección "cargando").

### 4. El mando tomado en "¿Con qué juega cada uno?" que se desconecta
- **Síntoma:** si alguien ya había tomado un mando y ese mando se
  desconectaba, el jugador seguía con él: desde el teclado no había cómo
  soltarlo y entraba a la partida sin poder moverse.
- **Causa:** `esquemas_libres()` ya no ofrecía ese mando, pero `self.esquemas`
  lo seguía teniendo.
- **Arreglo:** `_sincronizar_mandos`, en esa pantalla, deja libre (None) el
  esquema de un mando que ya no está.
- **Prueba:** `pruebas/prueba_mando_desconectado.py` (sección "controles").

### 5. Perder la partida porque se suelta el cable del mando
- **Síntoma:** con los demás eliminados (o de 2 con mandos y uno eliminado),
  desconectar el mando del que quedaba en pie terminaba la partida en derrota
  al instante.
- **Causa:** `Mision.actualizar` solo cuenta a los que `puede_moverse`; sin
  ninguno y con algún eliminado, es derrota. Un jugador sin mando tampoco
  puede moverse.
- **Arreglo:** `_sincronizar_mandos` marca `jugador.mando_desconectado` al que
  tenía mando y lo perdió (se borra al reconectar). Si no queda nadie que se
  pueda mover, la misión cuenta a esos (se espera a que reconecten). Un
  puesto que nunca tuvo mando sigue como antes (3 sin mandos y los otros dos
  eliminados = derrota).
- **Prueba:** `pruebas/prueba_mando_desconectado.py` (sección "partida",
  incluye reconectar con otro `instance_id` y volver a moverse).

### 6. La pausa se caía con el mouse (IndexError)
- **Síntoma:** clic en "Terminar partida" (o en Opciones > "Volver") y un
  movimiento del mouse en el mismo cuadro; después Enter (o izquierda/derecha)
  tumbaba el juego: `IndexError` en `MenuPausa.activar`.
- **Causa:** los rects de las opciones los llena el dibujo; al cambiar de
  vista seguían los de la anterior hasta el siguiente cuadro, y
  `mover_mouse` dejaba la selección en, p. ej., la 4.ª opción de una vista de 2.
- **Arreglo:** `MenuPausa._ir_a` vacía `rects` y `rects_logros`.
- **Prueba:** `pruebas/prueba_pausa_mouse.py`.

### 7. Clic en el mapa de la Emisión con dos pantallas
- **Síntoma:** con el modo dos pantallas, si J3 (en la otra pantalla) tenía
  abierto el mapa de la Emisión, un clic en la ventana principal que cayera en
  las mismas coordenadas le ponía la señal a J3. También se podía poner con la
  ventana de presentación de un alien abierta (el juego está detenido).
- **Causa:** `_jugador_con_mapa_en` revisaba a todos los jugadores, pero el
  `rect_mapa` de los de la otra pantalla está en coordenadas de esa pantalla.
- **Arreglo:** solo se revisan los de la pantalla principal
  (`_reparto_pantallas()[0]`; el mouse de la otra ya se ignoraba), y nada con
  la presentación abierta.
- **Prueba:** `pruebas/prueba_emision_dos_pantallas.py` (con una segunda
  pantalla falsa, sin ventana).

## Lo que revisé y está bien

- **Pausa:** congela todo lo que va con `dt` (aliens, reloj, eventos, apagón,
  tutorial, minijuego, presentación, sustos); no se acumula `dt` ni salta nada
  al despausar. No se puede pausar durante una transición, y con la
  presentación de un alien abierta Esc/START la cierran. Lo único que sigue
  moviéndose es cosmético (temblor y parpadeo del susto): ver dudas.
- **F11 / F9 a mitad de partida, en pausa y con paneles abiertos** (celular,
  árbol, Terminal NEXUS, Emisión, susto): las cachés de superficies van por
  tamaño (oscuridad, viñetas, velos, transición) y los rects se recalculan al
  dibujar. Lo probé alternando F11 varias veces con 4 jugadores y todo abierto.
- **Estado entre partidas:** misión, eventos, NEXUS, logros, tutorial,
  presentación, Sombra, Cambiaformas, ambiente y narrador se crean de nuevo en
  `_preparar_partida`; la dificultad y el director arrancan de cero.
- **Índices y divisiones:** los cursores de paneles, celular, habilidades,
  resultados y menús ya se protegían con `%`, `min` o `max(1, ...)`.

## Decisiones

- **`DT_MAXIMO_MS = 100`:** por debajo de 10 FPS el juego va en cámara lenta en
  vez de saltar; a 30-60 FPS no cambia nada. No toca el balance.
- **Mando desconectado:** no lo hice contar siempre para ganar (los demás
  pueden escapar sin él, como con un puesto sin mando); solo cuando no queda
  nadie más en pie, para no perder por un cable. Queda anotado en las dudas
  por si se prefiere esperarlo siempre.
- **Opciones de la pausa** (campo de visión, hitboxes, volumen): no las
  reinicié entre partidas; solo el grafo, que es una vista de prueba como el
  árbol del alien (que ya se apagaba). Queda en las dudas.
- No cambié textos, controles, balance ni assets.

## Archivos y funciones tocados

- `juego/app.py`: constante `DT_MAXIMO_MS`; `Game._actualizar_carga`,
  `Game._crear_aliens`, `Game.run`, `Game._manejar_eventos`,
  `Game._sincronizar_mandos`, `Game._jugador_con_mapa_en`.
- `juego/pausa.py`: `MenuPausa._ir_a`.
- `misiones/mision.py`: `Mision.actualizar` (el principio, la lista de jugadores).
- Pruebas nuevas: `pruebas/prueba_nueva_partida.py`,
  `pruebas/prueba_cuadro_lento.py`, `pruebas/prueba_mando_desconectado.py`,
  `pruebas/prueba_pausa_mouse.py`, `pruebas/prueba_emision_dos_pantallas.py`.
