# Mandos de Xbox y PlayStation (PS4/PS5) a la vez

## Causa

`juego/mandos.py` leía todos los mandos con `pygame.joystick` y los números de
botón del control de Xbox (`A=0, B=1, X=2, Y=3, LB=4, RB=5, BACK=6, START=7`,
cruceta como *hat*, LT en el eje 4). Por joystick, SDL numera distinto un
DualShock/DualSense: 4 = Share, 5 = PS, 6 = Options, 7 = L3, 9 = L1, 10 = R1,
la cruceta va en los botones 11-14 y los gatillos en los ejes 4 y 5. Con un
mando de PS, el celular (RB) caía en el botón PS, la pausa (START) en L3, el
sigilo (LB) en Share y la cruceta no hacía nada. Además las pistas en pantalla
siempre decían A/X/Y/RB.

## Qué cambió

- **`juego/mandos.py`**: todo mando que SDL reconoce
  (`pygame._sdl2.controller.is_controller(i)`) se abre como `Controller(i)` y
  se lee **por posición** (`CONTROLLER_BUTTON_A` es el de abajo también en
  PlayStation). El mapeo de acciones es el mismo de antes: abajo interactuar,
  izquierda habilidad, arriba árbol, derecha volver/soltar/cerrar, RB/R1
  celular, LB o LT / L1 o L2 sigilo, Start/Options pausa, cruceta y stick
  izquierdo moverse. Se cubren los dos caminos: eventos
  (`CONTROLLERBUTTONDOWN`, `CONTROLLERAXISMOTION`, `CONTROLLERDEVICEADDED/REMOVED`)
  y estado continuo (`presionada()`: cruceta, stick, sigilo mantenido, mantener A).
- **Sin doble pulsación**: SDL manda JOY* y CONTROLLER* a la vez para un mando
  reconocido; los JOY* de un mando abierto como controller se ignoran (por
  `instance_id`). Los dos avisos de conexión (JOYDEVICEADDED y
  CONTROLLERDEVICEADDED) conectan una sola vez.
- **Respaldo**: un mando que SDL no reconoce, o si `pygame._sdl2.controller`
  no se puede importar, sigue como antes (números de Xbox).
- **Tipo de mando**: `"xbox"`, `"playstation"` u `"otro"` por el nombre ("Xbox",
  "X-Box", "XInput", "PS4", "PS5", "DualSense", "DualShock", "Sony",
  "Wireless Controller"...) y, si el nombre no alcanza, por el fabricante del
  GUID (054c Sony, 045e Microsoft, "xinput").
- **Pistas por jugador**: `Jugador.nombre_tecla()` escribe el botón del mando
  de ese jugador (A/X/Y/B/RB/LB/Start en Xbox, Cruz/Cuadrado/Triángulo/
  Círculo/R1/L1/Options en PS; "otro" como Xbox). Así se actualizan solos
  tutorial, HUD, paneles, panel de habilidades, celular, presentación de
  aliens, etc. Pausa y resultados (que son de todos) dicen "A/Cruz" según los
  mandos conectados. La selección de rol muestra el botón de aceptar de cada uno.
- **Símbolos de PS**: la fuente (Determination Mono) no trae ✕ ○ □ △;
  `render_texto_mando()` en `screens/paneles.py` cambia "[Cruz]", "[Círculo]"...
  por el dibujo con `pygame.draw` (con sus colores) en la pista de zona, el
  minijuego del escondite, el pie de los paneles y la pantalla de controles.
  Donde no se dibuja, sale la palabra.
- **"¿Con qué juega cada uno?"**: "Mando 1 (Xbox)", "Mando 2 (PlayStation)",
  "[A] tomar" / "[✕] tomar" y "[ESC] o B/Círculo: volver".
- **`pruebas/probar_mando.py`**: al conectar dice si tomó el mando como
  controller o como joystick de respaldo y de qué tipo; cada botón/eje sale
  con la acción del juego que dispara y su nombre en ese mando.
- **`pruebas/prueba_mandos_xbox_ps.py`** (nueva): Controller/Joystick falsos y
  eventos fabricados; mapeo por posición en los dos tipos, sin doble
  pulsación, respaldo, tipo por nombre/GUID, pistas por jugador con un mando
  de cada tipo, pantalla de controles, símbolos y conectar/desconectar.
  Pasa con pygame 2.6.1 y con pygame-ce 2.5.8.
- README: los nombres de PlayStation en la explicación de los controles.

## pygame vs pygame-ce (lo que se encontró)

| | pygame 2.6.1 (SDL 2.28) | pygame-ce 2.5.8 (SDL 2.32) |
|---|---|---|
| `pygame._sdl2.controller` | sí | sí |
| `is_controller`, `Controller(i)`, `from_joystick`, `as_joystick`, `get_count`, `init` | sí | sí |
| `name_forindex`, `get_eventstate`/`set_eventstate`, `update` | sí | **no** |
| `Controller.set_led` | no | sí |
| Constantes `CONTROLLER_BUTTON_*`, `CONTROLLER_AXIS_*`, eventos `CONTROLLER*` | iguales (mismos valores) | iguales |
| Tipo de mando de SDL (`SDL_GameControllerGetType`) | no se expone | no se expone |

Por eso: `set_eventstate` se llama solo si existe; el tipo se adivina por el
nombre/GUID; el `instance_id` se toma del `Joystick` del mismo índice (igual en
los dos); `Controller.name` se lee siendo atributo o método; los ejes de
controller (enteros de -32768 a 32767, gatillos de 0 a 32767) se normalizan a
-1..1 y también se aceptan si ya vienen normalizados.

## Decisiones tomadas sin consultar

- `NOMBRE_BOTON` se dejó (con los nombres de Xbox) por compatibilidad; lo
  nuevo es `nombre_boton(accion, tipo)`.
- El tipo de cada jugador se pregunta a `Mandos.activo` (los mandos del juego
  abierto) desde `Jugador.tipo_mando`, para no tocar más `app.py` (otros
  trabajan ahí): conectar o cambiar de mando actualiza las pistas solo.
- En la selección de rol el nombre del control sigue siendo "Mando 1"/"Mando 2"
  (como antes); el tipo se ve en "¿Con qué juega cada uno?".
- "otro" (genéricos, Switch Pro...) se escribe como Xbox (no se probó con
  mandos de Nintendo).
- La palabra "Stick" se mantuvo para moverse en los dos tipos.
- LB/L1 en un evento no hace nada (el sigilo se mantiene), igual que antes.

## Compatibilidad con `claude/revision-codigo`

Esa rama procesa JOYDEVICEADDED/REMOVED antes del filtro de `self.carga`. Aquí
`_manejar_eventos` usa `EVENTOS_MANDO` / `EVENTOS_CONEXION` de `mandos.py`
(JOY* + CONTROLLER*). Al mezclar, en su rama nueva basta con cambiar
`evento.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED)` por
`evento.type in EVENTOS_CONEXION` y la otra tupla por `EVENTOS_ENTRADA`;
`_sincronizar_mandos` no se tocó, así que su cambio entra limpio.

## Para probar a mano en Windows (con los mandos de verdad)

1. `python pruebas/probar_mando.py` y conectar los dos mandos: cada uno debe
   decir **controller (por posición)** y su tipo (Xbox / PlayStation). Si uno
   sale como "joystick de respaldo", anotar su nombre.
2. En el PS presionar Cruz, Cuadrado, Triángulo, Círculo, R1, L1, L2, Options y
   la cruceta: deben salir interactuar, habilidad, habilidades, volver,
   celular, sigilo (L1 y L2), pausa, arriba/abajo/izq./der., **una sola vez**
   cada uno. Lo mismo con A, X, Y, B, RB, LB, LT, Start en el Xbox.
3. En el juego, con 2 jugadores: "¿Con qué juega cada uno?" muestra "Mando 1
   (Xbox)" y "Mando 2 (PlayStation)"; cada uno toma el suyo y escoge rol.
4. En partida: moverse con stick y cruceta, sigilo con L1/L2 y LB/LT, abrir el
   celular (R1/RB), pausa con Options/Start y navegarla. Las pistas de cada
   pantalla dicen los botones de su mando (✕ en la del PS, A en la del Xbox).
5. Desconectar y volver a conectar el mando de PS con la partida andando.
