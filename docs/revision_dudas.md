# Revisión de código: lo dudoso que NO se tocó

Lo que salió en la revisión de `juego/app.py`, `misiones/`, `entidades/`,
`screens/partida.py`, `screens/paneles.py` y lo que usan, pero que no se
arregló en `claude/revision-codigo`: no es seguro que sea un error, arreglarlo
cambia diseño o balance, o es arriesgado justo antes de la feria. Los números
de línea son de `main` (commit `04d7b85`).

Riesgo = qué tan probable es que se note en la feria (bajo / medio / alto).

---

## 1. La pantalla sigue temblando (y el susto parpadeando) en pausa

- **Dónde:** `screens/partida.py:249` (`temblor(dueño, pygame.time.get_ticks())`),
  `juego/ambiente.py:135-144` y las semillas de los sustos (`juego/ambiente.py:287`,
  `308`, `398`, `435`, `482`, `520`, `537`).
- **Qué pasa:** con la pausa abierta, `susto_ms` no baja (bien: el susto se
  congela), pero el temblor de la cámara y el glitch/los parpadeos de los
  screamers usan el reloj de pygame, que sí corre. Detrás del velo de la pausa
  la vista del atrapado sigue sacudiéndose y el susto "vibra" quieto. Al
  despausar no salta nada (el tiempo del susto no avanzó).
- **Cómo reproducirlo:** que atrapen a alguien y apretar Esc en el medio
  segundo del susto.
- **Sugerencia:** guardar en `Game` un "reloj de partida" que solo avance en
  `_actualizar_partida` y pasar ese en vez de `get_ticks()` a `temblor` y a
  los sustos (o no aplicar el temblor si `juego.pausa` no es None).
- **Riesgo:** bajo (solo se ve, no cambia nada del juego).

## 2. "Terminar partida" desde la pausa no guarda los logros en el historial

- **Dónde:** `juego/app.py:1959-1963` (`_accion_pausa("terminar")`) frente a
  `juego/app.py:1287-1299` (`terminar_ronda`, que llama a
  `historial_logros.agregar`).
- **Qué pasa:** los logros que se consiguieron en una partida terminada desde
  la pausa no aparecen en Menú > Logros. La confirmación dice "Se pierde todo
  lo que llevan de esta partida", así que puede ser a propósito.
- **Cómo reproducirlo:** conseguir un logro, Esc > Terminar partida > Sí, y
  mirar Menú > Logros.
- **Sugerencia:** si se quiere guardar, llamar a `historial_logros.agregar`
  también en esa rama (sin pasar por resultados).
- **Riesgo:** bajo (decisión de diseño).

## 3. Las opciones de prueba de la pausa pasan a la partida siguiente

- **Dónde:** `juego/app.py:217` (`mostrar_hitboxes`) y `juego/app.py:255`
  (`oscuridad`): se fijan en `Game.__init__` y no se reinician en
  `_preparar_partida`.
- **Qué pasa:** si alguien apaga "Campo de visión y oscuridad" o prende "Ver
  hitboxes" en Pausa > Opciones, la siguiente partida (otros jugadores, en la
  feria) arranca igual: sin campo de visión o con las hitboxes dibujadas. El
  volumen también se conserva, y ahí sí tiene sentido. (El grafo sí se apaga
  ahora: ver `claude/revision-codigo`.)
- **Cómo reproducirlo:** Pausa > Opciones > Campo de visión: No; Terminar
  partida; Jugar otra vez.
- **Sugerencia:** decidir si son "opciones" (se quedan) o "vistas de prueba"
  (se apagan en `_crear_aliens`, como el árbol del alien y el grafo).
- **Riesgo:** medio en la feria (alguien prueba las opciones y el siguiente
  grupo juega sin el campo de visión sin saberlo).

## 4. Un tercer mando nunca reemplaza al que se desconecta

- **Dónde:** `juego/mandos.py:99-115` (`_conectar`, `_desconectar`) y
  `juego/mandos.py:169-174`.
- **Qué pasa:** solo se asigna un puesto al recibir JOYDEVICEADDED. Con tres
  mandos conectados, el tercero se ignora; si después se desconecta el Mando 1,
  el tercero no toma su lugar (habría que desconectarlo y volverlo a conectar).
  Además, si se desconectan los dos y se reconectan en el otro orden, quedan
  cambiados (el que era de J1 ahora es de J2): SDL no da cómo reconocer el
  mismo mando físico (dos del mismo modelo tienen el mismo GUID).
- **Cómo reproducirlo:** con `pruebas/probar_mando.py` o en partida con tres
  mandos.
- **Sugerencia:** en `_desconectar`, recorrer `pygame.joystick.get_count()` y
  conectar el primero que no esté asignado. Para el orden, avisar en pantalla
  "Mando 1 conectado" / "Mando 2 conectado" al reconectar.
- **Riesgo:** bajo-medio.

## 5. Desconectarse en pleno minijuego del escondite

- **Dónde:** `juego/app.py:988-1012` (`_actualizar_minijuegos`).
- **Qué pasa:** si al jugador escondido se le desconecta el mando mientras un
  alien revisa su escondite, el minijuego sigue corriendo y la barra del alien
  se llena: lo atrapan (pierde una vida) sin poder hacer nada. Los aliens ya
  no empiezan a cazarlo (`Jugador.cazable` pide `puede_moverse`), pero el que
  ya estaba revisando sigue.
- **Cómo reproducirlo:** esconderse con un mando, esperar que un alien revise
  y desenchufar el mando.
- **Sugerencia:** saltar el minijuego (o congelarlo) mientras
  `jugador.mando_desconectado` sea True; o que el alien se rinda.
- **Riesgo:** bajo (tiene que coincidir).

## 6. Algún dispositivo que no es mando puede quedarse con el "Mando 1"

- **Dónde:** `juego/mandos.py:85-97` (`Mandos.__init__` conecta todo lo que
  reporte `pygame.joystick`).
- **Qué pasa:** en Windows, algunos teclados con luces, volantes, tabletas o
  el acelerómetro de ciertas laptops aparecen como joystick. Se quedarían con
  el puesto del Mando 1 y el mando de verdad pasaría a ser el Mando 2 (o nada).
  Saldría además la pantalla "¿Con qué juega cada uno?" aunque no haya mandos.
- **Cómo reproducirlo:** en la laptop de la feria, `python pruebas/probar_mando.py`
  sin mandos conectados: si sale alguno, pasa esto.
- **Sugerencia:** filtrar por `joy.get_numbuttons() >= 4` y `get_numaxes() >= 2`
  (o por nombre), o usar `pygame._sdl2.controller` (solo gamepads).
- **Riesgo:** medio, depende de la laptop. Conviene probarlo antes.

## 7. Cachés de miniaturas que van por `id()`

- **Dónde:** `screens/roles.py:332` (`_cache_minimapa`), `screens/partida.py:408`
  (`_mapas_emision`), con `juego/salas_selladas.py:444` (`clave_cache` =
  `id(sellado)`); `screens/grafo_vista.py:275` (`id(mundo)`, `id(nav)`);
  `screens/roles.py:233` (`_pasos` por `id(alien)`).
- **Qué pasa:** un `id()` se puede reusar cuando el objeto viejo se libera. Si
  el `Sellado` de una partida nueva cae en la dirección del de hace dos
  partidas, el minimapa y el mapa de la Emisión mostrarían las salas selladas
  de aquella. `_pasos` además guarda una referencia a los aliens de partidas
  viejas (no crece mucho, pero no se limpia). No se pudo reproducir: en
  `MapaFinal` (el mapa activo) no se sella ninguna sala con 2 o 3 jugadores.
- **Sugerencia:** dar a `Sellado` un número de versión (contador global) y
  usar ese en `clave_cache`; vaciar `_pasos` al empezar la partida.
- **Riesgo:** bajo.

## 8. La tecla con que se cierra la pausa sigue "mantenida" al volver

- **Dónde:** `juego/app.py:1134` (`mantiene = any(teclas[k] ...)`).
- **Qué pasa:** Enter (J2) o A (mando) cierran la pausa con "Continuar"; si se
  sigue apretando, en el primer cuadro de juego cuenta como mantener
  interactuar: empieza a apagar una consola o a cambiar fusibles si está al
  lado. Es medio segundo, no es grave.
- **Sugerencia:** ignorar "mantener" hasta que se suelte la tecla después de
  cerrar la pausa (o la presentación de un alien).
- **Riesgo:** bajo.

## 9. Se desconecta la segunda pantalla con el juego abierto

- **Dónde:** `juego/app.py:300-326` y `juego/segunda_pantalla.py`.
- **Qué pasa:** si se desenchufa el monitor (o Windows pasa a "Duplicar") con
  el modo dos pantallas prendido, nadie lo nota: la ventana de la pantalla 2
  queda donde SDL la deje (a veces encima de la principal) y J3/J4 siguen
  dibujándose en ella. F9 lo apaga a mano.
- **Sugerencia:** escuchar `pygame.WINDOWDISPLAYCHANGED` / revisar
  `segunda_pantalla.pantallas()` cada tanto y cerrar la segunda si ya no hay
  dos pantallas.
- **Riesgo:** bajo-medio (cables flojos en la feria).

## 10. En "Roles", un mando que se desconecta deja al jugador sin poder elegir

- **Dónde:** `juego/app.py:470-495` (`abrir_seleccion_roles`, las etiquetas
  `controles`, `tecla_mover`, `tecla_ok`) y `juego/app.py:1801`.
- **Qué pasa:** si el mando de alguien se desconecta en la pantalla de roles,
  las etiquetas siguen diciendo "Mando 1" / "A" y ese jugador solo puede
  escoger con las letras de respaldo (I/K/O, T/G/Y). Esc vuelve a "¿Con qué
  juega cada uno?" y ahí ya se arregla (ver `claude/revision-codigo`).
- **Sugerencia:** en `_sincronizar_mandos`, con `current_screen == "roles"`,
  volver a `abrir_controles()`.
- **Riesgo:** bajo.

## 11. Con un mando desconectado los demás pueden ganar sin él

- **Dónde:** `misiones/mision.py:1002-1031` (`Mision.actualizar`).
- **Qué pasa:** el que se quedó sin mando no cuenta para la victoria (no se
  puede mover), así que el resto puede escapar sin él. Es lo mismo que con un
  puesto sin mando desde el principio. Con el arreglo de
  `claude/revision-codigo` solo se le cuenta si es el único que queda en pie
  (para no perder por un cable). Si se prefiere que haya que esperarlo
  siempre, contar `mando_desconectado` en la lista de `jugadores` siempre.
- **Riesgo:** bajo (decisión de diseño).
