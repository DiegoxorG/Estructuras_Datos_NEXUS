"""Lo que hace cada habilidad de los cuatro roles dentro de la partida.

El árbol de habilidades (Estructuras/arbol_habilidades.py) decide QUÉ tiene
desbloqueado cada jugador; este archivo decide qué PASA cuando lo usa. Se
pregunta siempre con `jugador.arbol.tiene(CLAVE)`, así que el árbol es lo que
abre o cierra cada acción: si el Tecnomante escogió ESCANEO, HACKEO quedó
descartado y las terminales ya no apagan aliens.

Tres formas de uso (campo `uso` de cada nodo en data/habilidades.py):
- pasiva: funciona sola (las dibuja screens/roles.py).
- estacion: tecla de interactuar frente a una terminal o un panel.
- activa: tecla de habilidad, en cualquier lado, con recarga.

Todo se apoya en lo que ya hacían los aliens: el escaneo y la interceptación
muestran su cono y su árbol; el señuelo y la señal falsa usan el mismo "oír un
ruido" que un latido; la regeneración baja el pulso, que es lo que delata.
"""

import math

import pygame


# -- Números de cada habilidad (para ajustar el balance, solo aquí) -----------------
DURACION_MAPA_TERMINAL_MS = 5000      # Conexión digital
RECARGA_TERMINAL_MS = 4000
RADIO_HACKEO = 520                    # Hackeo básico
DURACION_HACKEO_MS = 5000
RECARGA_HACKEO_MS = 15000
DURACION_ESCANEO_MS = 6000            # Escaneo de sistemas
DURACION_SENUELO_MS = 7000            # Fabricación improvisada
RADIO_SENUELO = 600
RADIO_AYUDA = 230                     # Regeneración e Impulso: hasta dónde llegan
CALMA_REGENERACION = 35
RECARGA_CURACION_MS = 40000           # Regeneración: cada cuánto puede devolver vidas
AMENAZA_REGENERACION = 30
DURACION_INTERCEPCION_MS = 8000       # Interceptación básica
DISTANCIA_EMISION = 320               # Emisión modulada: dónde empieza el cursor
RADIO_EMISION = 750                   # los aliens a esta distancia de la señal la oyen
VELOCIDAD_CURSOR_EMISION = 16         # px del mundo por frame, moviendo el cursor con teclas
DURACION_SENAL_MS = 2500

PUNTOS_HACKEO = 10
PUNTOS_REPARACION = 15
PUNTOS_AYUDA = 5

COLOR_BIEN = (96, 200, 120)
COLOR_MAL = (245, 130, 120)
COLOR_AVISO = (255, 214, 64)

# Hacia dónde mira el personaje, como vector, según el nombre de su dirección.
_VECTORES = {
    "north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0),
    "north-east": (0.707, -0.707), "north-west": (-0.707, -0.707),
    "south-east": (0.707, 0.707), "south-west": (-0.707, 0.707),
}


def _sonar(juego, nombre, volumen=1.0):
    if hasattr(juego, "sonar"):
        juego.sonar(nombre, volumen)


def sin_luz(juego):
    """En un apagón no funciona nada eléctrico (ver Game.sin_luz)."""
    return bool(getattr(juego, "sin_luz", False))


SIN_ENERGIA = "Sin energía: enciendan la caja de fusibles."


def _distancia(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _rect_en(rx, ry, tamano, mundo):
    rect = pygame.Rect(0, 0, *tamano)
    rect.center = (int(rx * mundo.ancho), int(ry * mundo.alto))
    return rect


# -- Preparar el mapa -----------------------------------------------------------------

def preparar_estaciones(mundo, objetos=None):
    """Terminales, paneles y piezas en píxeles.

    Salen de los objetos del mapa (objetos_mapa.py, lo que se pone con el
    editor).
    """
    from data.estaciones import TAMANO_ESTACION, TAMANO_PIEZA
    if objetos is None:
        return [], [], []
    lista_t, lista_p, lista_piezas = objetos["terminales"], objetos["paneles"], objetos["piezas"]

    terminales = []
    for datos in lista_t:
        t = dict(datos, tipo="terminal", recarga_ms=0)
        t["rect"] = _rect_en(datos["rx"], datos["ry"], TAMANO_ESTACION, mundo)
        terminales.append(t)
    paneles = []
    for datos in lista_p:
        p = dict(datos, tipo="panel", reparado=False)
        p["rect"] = _rect_en(datos["rx"], datos["ry"], TAMANO_ESTACION, mundo)
        # El sello que levanta este panel al repararlo (si el mapa le puso uno).
        sello = datos.get("sello")
        p["sello_rect"] = None
        if sello:
            p["sello_rect"] = pygame.Rect(0, 0, max(8, int(sello["ancho"] * mundo.ancho)),
                                          max(8, int(sello["alto"] * mundo.alto)))
            p["sello_rect"].center = (int(sello["rx"] * mundo.ancho), int(sello["ry"] * mundo.alto))
        paneles.append(p)
    piezas = [{"rect": _rect_en(rx, ry, TAMANO_PIEZA, mundo), "recogida": False}
              for rx, ry in lista_piezas]
    return terminales, paneles, piezas


# -- Consultas --------------------------------------------------------------------------

def habilidad_activa(jugador):
    """El nodo de la habilidad que se usa con la tecla de habilidad, o None."""
    for nodo in reversed(jugador.arbol.desbloqueadas()):
        if nodo.uso == "activa":
            return nodo
    return None


def estacion_bajo(juego, jugador):
    """(tipo, estación) que este jugador puede usar donde está parado, o None.

    Solo el Tecnomante usa terminales y solo el Forjador repara paneles: los
    demás pasan por encima sin que les salga la pista.
    """
    if jugador.arbol.tiene("CONEXION"):
        for t in juego.terminales:
            if t["rect"].colliderect(jugador.hitbox):
                return t
    if jugador.arbol.tiene("INGENIO"):
        for p in juego.paneles:
            if not p["reparado"] and p["rect"].colliderect(jugador.hitbox):
                return p
    return None


def companeros_cerca(juego, jugador, radio=RADIO_AYUDA, incluirse=False):
    centro = jugador.hitbox.center
    return [j for j in juego.jugadores
            if (incluirse or j is not jugador) and _distancia(centro, j.hitbox.center) <= radio]


# -- Estaciones (tecla de interactuar) ---------------------------------------------------

def usar_estacion(juego, jugador, estacion):
    if estacion["tipo"] == "terminal":
        _usar_terminal(juego, jugador, estacion)
    elif estacion["tipo"] == "panel":
        _reparar_panel(juego, jugador, estacion)


def _usar_terminal(juego, jugador, terminal):
    if sin_luz(juego):
        jugador.avisar("La terminal está apagada. " + SIN_ENERGIA, COLOR_MAL)
        return
    if terminal["recarga_ms"] > 0:
        jugador.avisar(f"La terminal se reinicia: {math.ceil(terminal['recarga_ms'] / 1000)} s",
                       COLOR_MAL)
        return
    # Conexión digital (la base): el mapa de la nave con los aliens.
    jugador.efectos["mapa"] = DURACION_MAPA_TERMINAL_MS
    terminal["recarga_ms"] = RECARGA_TERMINAL_MS

    if not jugador.arbol.tiene("HACKEO"):
        jugador.avisar("Conectado: estado de la nave en pantalla.", COLOR_AVISO)
        return
    apagados = [a for a in juego.aliens
                if _distancia(a.centro, terminal["rect"].center) <= RADIO_HACKEO]
    for alien in apagados:
        alien.aturdir(DURACION_HACKEO_MS)
    terminal["recarga_ms"] = RECARGA_HACKEO_MS
    if apagados:
        from misiones.logros import logro
        logro(juego, "apagado", jugador)
        _sonar(juego, "hackeo", 0.8)
        jugador.sumar_puntos(PUNTOS_HACKEO)
        jugador.avisar(f"Hackeo: {len(apagados)} alien(s) apagados. +{PUNTOS_HACKEO}", COLOR_BIEN)
    else:
        jugador.avisar("Hackeo: no había aliens cerca de esta terminal.", COLOR_AVISO)


def _reparar_panel(juego, jugador, panel):
    if not jugador.arbol.tiene("REPARACION"):
        jugador.avisar(f"Necesitas Reparación básica ([{jugador.nombre_tecla('habilidades')}])",
                       COLOR_MAL)
        return
    if jugador.recarga_ms > 0:
        jugador.avisar(f"Reparación: {math.ceil(jugador.recarga_ms / 1000)} s", COLOR_MAL)
        return
    if jugador.piezas <= 0:
        jugador.avisar("Te falta una pieza para repararlo.", COLOR_MAL)
        return
    sello = panel.get("sello_rect")
    if sello is not None and any(a.hitbox.colliderect(sello) for a in juego.aliens):
        jugador.avisar("Hay un alien en el paso del sello: espera a que se mueva.", COLOR_MAL)
        return
    jugador.piezas -= 1
    panel["reparado"] = True
    jugador.sumar_puntos(PUNTOS_REPARACION)
    # La Reparación usa la misma recarga que las habilidades con tecla (el
    # Forjador que la escoge no tiene otra), así el Impulso también la llena.
    nodo = next((n for n in jugador.arbol.desbloqueadas() if n.clave == "REPARACION"), None)
    jugador.recarga_ms = int(getattr(nodo, "recarga_s", 0) * 1000)
    if sello is not None:
        # Sellos: la barrera de energía que levanta el panel. Frena a los
        # aliens (no pasan ni ven a través) y a los jugadores no. Es de
        # energía: en un apagón se cae y vuelve con la luz (_actualizar_sellos).
        if sin_luz(juego):
            jugador.avisar(f"Panel reparado: el sello se levanta cuando vuelva la luz. "
                           f"+{PUNTOS_REPARACION}", COLOR_AVISO)
            _sonar(juego, "encajar", 0.6)
            return
        panel["sello_on"] = True
        _actualizar_sellos(juego)
        jugador.avisar(f"¡Sello activado! Los aliens no pasan por ahí. +{PUNTOS_REPARACION}",
                       COLOR_BIEN)
        _sonar(juego, "sello", 0.8)
        if hasattr(juego, "decir"):
            juego.decir("sello", jugador.rol)
        return
    _sonar(juego, "encajar", 0.6)
    hechos = sum(p["reparado"] for p in juego.paneles)
    jugador.avisar(f"Panel reparado ({hechos}/{len(juego.paneles)}). +{PUNTOS_REPARACION}",
                   COLOR_BIEN)


# -- Habilidades activas (tecla de habilidad) ----------------------------------------------

def usar_habilidad(juego, jugador):
    """El jugador presionó su tecla de habilidad."""
    nodo = habilidad_activa(jugador)
    if nodo is None:
        if len(jugador.arbol.desbloqueadas()) <= 1:
            jugador.avisar(f"Escoge una habilidad con [{jugador.nombre_tecla('habilidades')}]",
                           COLOR_AVISO)
        else:
            jugador.avisar("Tu habilidad se usa en el mapa, no con esta tecla.", COLOR_AVISO)
        return False
    if jugador.recarga_ms > 0:
        jugador.avisar(f"{nodo.nombre}: {math.ceil(jugador.recarga_ms / 1000)} s", COLOR_MAL)
        return False

    if nodo.clave == "EMISION":
        # No se gasta todavía: abre el mapa para escoger dónde cae la señal.
        # La recarga empieza al ponerla (poner_emision).
        abrir_emision(juego, jugador)
        return True

    usar = {
        "ESCANEO": _escaneo,
        "FABRICACION": _fabricar_senuelo,
        "REGENERACION": _regeneracion,
        "IMPULSO": _impulso,
        "INTERCEPCION": _intercepcion,
    }.get(nodo.clave)
    if usar is None or not usar(juego, jugador):
        return False
    jugador.recarga_ms = int(nodo.recarga_s * 1000)
    return True


def _escaneo(juego, jugador):
    if sin_luz(juego):
        jugador.avisar("Escaneo: no hay sistemas que escanear sin luz.", COLOR_MAL)
        return False   # no gasta la recarga
    jugador.efectos["mapa"] = DURACION_ESCANEO_MS
    jugador.efectos["escaneo"] = DURACION_ESCANEO_MS
    jugador.avisar("Escaneo: aliens y sus conos en el mapa.", COLOR_AVISO)
    return True


def _fabricar_senuelo(juego, jugador):
    if jugador.piezas <= 0:
        jugador.avisar("Necesitas una pieza para el señuelo.", COLOR_MAL)
        return False
    jugador.piezas -= 1
    juego.senuelos.append({"pos": jugador.hitbox.center, "ms": DURACION_SENUELO_MS,
                           "duracion": DURACION_SENUELO_MS})
    jugador.avisar("Señuelo armado: los aliens vendrán por el ruido.", COLOR_BIEN)
    _sonar(juego, "senal", 0.7)
    return True


def _regeneracion(juego, jugador):
    """Calma el pulso de los que están cerca y, si la curación está lista, le
    devuelve una vida a cada compañero cercano al que le falte alguna."""
    curados = []
    if jugador.curacion_ms <= 0:
        for otro in companeros_cerca(juego, jugador):
            if otro.preso is None and otro.curar(1):
                curados.append(otro)
                otro.avisar("La Biomante te devolvió una vida.", COLOR_BIEN)
        if curados:
            from misiones.logros import logro
            logro(juego, "medico", jugador)
            _sonar(juego, "curar", 0.7)
            jugador.curacion_ms = RECARGA_CURACION_MS
            jugador.sumar_puntos(PUNTOS_AYUDA * 2 * len(curados))
            if hasattr(juego, "decir"):
                juego.decir("curacion", jugador.rol)
    ayudados = 0
    for otro in companeros_cerca(juego, jugador, incluirse=True):
        otro.pulso = max(0.0, otro.pulso - CALMA_REGENERACION)
        if otro is not jugador:
            ayudados += 1
            otro.avisar("La Biomante te calmó.", COLOR_BIEN)
    # Si alguien está escondido cerca y un alien lo revisa, le baja la amenaza.
    for otro in juego.jugadores:
        juego_escondite = otro.minijuego
        if (juego_escondite is not None and otro is not jugador and
                _distancia(jugador.hitbox.center, otro.hitbox.center) <= RADIO_AYUDA):
            juego_escondite.amenaza = max(0.0, juego_escondite.amenaza - AMENAZA_REGENERACION)
            ayudados += 1
    if ayudados:
        jugador.sumar_puntos(PUNTOS_AYUDA * ayudados)
    if curados:
        jugador.avisar(f"Regeneración: +1 vida a {len(curados)} compañero(s).", COLOR_BIEN)
    elif jugador.curacion_ms > 0:
        jugador.avisar(f"Pulso calmado. Curar vidas: {math.ceil(jugador.curacion_ms / 1000)} s",
                       COLOR_AVISO)
    else:
        jugador.avisar(f"Regeneración: {ayudados} compañero(s) más tranquilos.", COLOR_BIEN)
    return True


def _impulso(juego, jugador):
    """Impulso energético: recarga lo que tengan en espera los compañeros
    cercanos (su habilidad o la Reparación del Forjador) y reinicia todas las
    terminales, para que el Tecnomante pueda volver a hackear enseguida."""
    recargados = [o for o in companeros_cerca(juego, jugador)
                  if o.recarga_ms > 0 and not getattr(o, "eliminado", False)]
    terminales = [t for t in getattr(juego, "terminales", []) if t["recarga_ms"] > 0]
    if not recargados and not terminales:
        jugador.avisar("Nada necesita energía ahora.", COLOR_AVISO)
        return False   # no gasta la recarga
    for otro in recargados:
        otro.recarga_ms = 0
        otro.avisar("Impulso: tu habilidad está lista otra vez.", COLOR_BIEN)
    for terminal in terminales:
        terminal["recarga_ms"] = 0
    _sonar(juego, "impulso", 0.7)
    ayudas = len(recargados) + (1 if terminales else 0)
    jugador.sumar_puntos(PUNTOS_AYUDA * ayudas)
    partes = []
    if recargados:
        partes.append(f"{len(recargados)} compañero(s)")
    if terminales:
        partes.append(f"{len(terminales)} terminal(es)")
    jugador.avisar(f"Impulso: {' y '.join(partes)} listos. +{PUNTOS_AYUDA * ayudas}", COLOR_BIEN)
    return True


def _intercepcion(juego, jugador):
    jugador.efectos["intercepcion"] = DURACION_INTERCEPCION_MS
    jugador.avisar("Interceptando: rutas y decisiones de los aliens.", COLOR_AVISO)
    return True


def abrir_emision(juego, jugador):
    """Emisión modulada: abre el mapa de la nave en la vista del Resonante.

    Ahí solo se ve él (no sus compañeros ni los aliens) y un cursor que se
    mueve con el mouse o con sus teclas de movimiento; con clic o con su tecla
    de interactuar la señal cae donde está el cursor.
    """
    dx, dy = _VECTORES.get(jugador.personaje.direccion, (0, 1))
    x, y = jugador.hitbox.center
    jugador.abrir_panel({"tipo": "emision",
                         "cursor_mapa": [x + dx * DISTANCIA_EMISION, y + dy * DISTANCIA_EMISION]})


def mover_cursor_emision(juego, jugador, dx, dy, dt=16):
    panel = jugador.panel
    if panel is None or panel.get("tipo") != "emision":
        return
    paso = VELOCIDAD_CURSOR_EMISION * dt / 16
    mundo = juego.mundo
    panel["cursor_mapa"][0] = min(mundo.ancho - 1, max(0, panel["cursor_mapa"][0] + dx * paso))
    panel["cursor_mapa"][1] = min(mundo.alto - 1, max(0, panel["cursor_mapa"][1] + dy * paso))


def poner_emision(juego, jugador, punto=None):
    """Pone la señal (en `punto`, o donde está el cursor) y empieza la recarga."""
    panel = jugador.panel or {}
    if punto is None:
        punto = panel.get("cursor_mapa", jugador.hitbox.center)
    # Que caiga en el piso, no dentro de una pared.
    x, y = juego.mundo.punto_libre((int(punto[0]) - 17, int(punto[1]) - 10), 34, 20)
    punto = (int(x + 17), int(y + 10))
    jugador.cerrar_panel()
    atraidos = [a for a in juego.aliens
                if _distancia(a.centro, punto) <= RADIO_EMISION and a.oir(punto)]
    # El Guardia (guardia.py) no va a ver la señal, pero si cae en su sala se
    # queda escuchándola un rato.
    from entidades.guardia import DISTRACCION_EMISION_MS
    for a in juego.aliens:
        if hasattr(a, "distraer") and a.en_area(punto) and a.distraer(DISTRACCION_EMISION_MS, jugador):
            atraidos.append(a)
            jugador.avisar("¡El Guardia se quedó escuchando la señal!", COLOR_AVISO)
    juego.senales.append({"pos": punto, "ms": DURACION_SENAL_MS, "duracion": DURACION_SENAL_MS})
    _sonar(juego, "senal", 0.7)
    if atraidos:
        from misiones.logros import logro
        logro(juego, "titiritero", jugador)
        jugador.sumar_puntos(PUNTOS_AYUDA)
    jugador.avisar(f"Señal falsa: {len(atraidos)} alien(s) van a revisarla.", COLOR_AVISO)
    nodo = habilidad_activa(jugador)
    jugador.recarga_ms = int(getattr(nodo, "recarga_s", 0) * 1000)
    return punto


# -- Cada frame -----------------------------------------------------------------------------

def _actualizar_sellos(juego):
    """Qué sellos frenan a los aliens ahora: los de paneles reparados, si hay
    luz. Al volver la luz, un sello no se levanta encima de un alien (lo
    dejaría encerrado): espera a que se mueva."""
    mundo = getattr(juego, "mundo", None)
    if mundo is None:
        return
    apagado = sin_luz(juego)
    activos = []
    for panel in getattr(juego, "paneles", ()):
        sello = panel.get("sello_rect")
        if sello is None or not panel["reparado"]:
            continue
        if apagado:
            panel["sello_on"] = False
        elif not panel.get("sello_on") and not any(a.hitbox.colliderect(sello)
                                                   for a in getattr(juego, "aliens", ())):
            panel["sello_on"] = True
        if panel.get("sello_on"):
            activos.append(sello)
    mundo.bloqueos_alien[:] = activos


def actualizar(juego, dt):
    """Recargas, efectos, piezas, señuelos y la línea de estado del HUD."""
    _actualizar_sellos(juego)
    for terminal in juego.terminales:
        terminal["recarga_ms"] = max(0, terminal["recarga_ms"] - dt)

    for jugador in juego.jugadores:
        jugador.recarga_ms = max(0, jugador.recarga_ms - dt)
        jugador.curacion_ms = max(0, getattr(jugador, "curacion_ms", 0) - dt)
        if sin_luz(juego):
            # Se fue la luz: se apagan las pantallas (mapa de la terminal y escaneo).
            jugador.efectos.pop("mapa", None)
            jugador.efectos.pop("escaneo", None)
        for nombre in list(jugador.efectos):
            jugador.efectos[nombre] -= dt
            if jugador.efectos[nombre] <= 0:
                del jugador.efectos[nombre]

        # Ingenio mecánico: el Forjador recoge las piezas al pasar por encima
        # (sin Forjador, quien lleve el kit de herramientas: Mision.ve_piezas).
        mision = getattr(juego, "mision", None)
        ve = mision.ve_piezas(jugador) if mision is not None else jugador.arbol.tiene("INGENIO")
        if ve and not jugador.escondido and not jugador.preso:
            for pieza in juego.piezas:
                if pieza.get("solto") is jugador:
                    # La acaba de soltar: no la recoge hasta que se mueva de encima.
                    if not pieza["rect"].colliderect(jugador.hitbox):
                        pieza["solto"] = None
                    continue
                if not pieza["recogida"] and pieza["rect"].colliderect(jugador.hitbox):
                    pieza["recogida"] = True
                    _sonar(juego, "recoger", 0.6)
                    jugador.piezas += 1
                    jugador.avisar(f"Pieza recogida ({jugador.piezas})", COLOR_BIEN)

        jugador.estacion_cerca = (None if jugador.escondido or jugador.zona_cerca
                                  else estacion_bajo(juego, jugador))

    # El señuelo hace ruido todo el rato que dura.
    for senuelo in juego.senuelos:
        senuelo["ms"] -= dt
        for alien in juego.aliens:
            if _distancia(alien.centro, senuelo["pos"]) <= RADIO_SENUELO:
                alien.oir(senuelo["pos"])
    juego.senuelos = [s for s in juego.senuelos if s["ms"] > 0]
    for senal in juego.senales:
        senal["ms"] -= dt
    juego.senales = [s for s in juego.senales if s["ms"] > 0]


def linea_de_estado(jugador):
    """Lo que dice la tercera línea del HUD: la habilidad y si está lista."""
    partes = []   # las piezas ya se ven en el inventario (paneles.render_inventario)
    nodo = habilidad_activa(jugador)
    tecla = jugador.nombre_tecla("habilidad")
    if nodo is not None:
        if jugador.recarga_ms > 0:
            partes.append(f"{nodo.nombre}: {math.ceil(jugador.recarga_ms / 1000)} s")
        else:
            partes.append(f"[{tecla}] {nodo.nombre} lista")
    elif jugador.recarga_ms > 0:
        partes.append(f"{jugador.arbol.actual.nombre}: {math.ceil(jugador.recarga_ms / 1000)} s")
    elif len(jugador.arbol.desbloqueadas()) <= 1:
        partes.append(f"[{jugador.nombre_tecla('habilidades')}] escoge tu habilidad")
    else:
        partes.append(f"{jugador.arbol.actual.nombre}: úsala en el mapa")
    return "  ·  ".join(partes)
