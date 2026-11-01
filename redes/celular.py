"""El celular de cada jugador: las pantallas de NEXUS y qué hace cada opción.

El celular es un panel más del jugador (jugador.panel con tipo "celular"):
mientras lo tiene abierto no camina, y si un alien llega, lo atrapa. Lo que
pasa en la red (rumores, desmentidos, el grafo) está en nexus.py; aquí solo
se arman las pantallas y se resuelve la opción elegida. El dibujo está en
screens/celular.py.

El inicio tiene tres pestañas (se cambian con izquierda/derecha):
    misiones   lo que hay que ir a verificar: rumores sin desmentir y pedidos
               de ayuda (la trampa del Cambiaformas). Nunca más de 3 a la vez
               (nexus.MAX_POR_VERIFICAR). Arriba, el que está haciendo.
    equipo     lo que publicaron los jugadores (desmentidos, compartidos) y los
               prisioneros rescatados.
    red        lo demás: la charla de los prisioneros.

Pantallas ("vista"):
    feed       el inicio, con la pestaña elegida
    post       una publicación, con lo que se puede hacer con ella
    origen     de dónde vino un rumor (camino más corto desde quien lo empezó)
    ubicacion  publicar la foto tal cual (se ve dónde estás) o recortada
    mensaje    el resultado de lo que hizo
"""

from redes.nexus import COLOR_BIEN, COLOR_MAL
from data.nexus import NOMBRE_LUGAR

PESTANAS = [("misiones", "Misiones"), ("equipo", "Equipo"), ("red", "Red")]
CLAVES_PESTANAS = [c for c, _ in PESTANAS]
MAX_HECHAS = 2        # misiones terminadas que se siguen viendo (abajo, en gris)


def abrir(juego, jugador):
    if juego.nexus is None:
        jugador.avisar("No hay señal de NEXUS en este mapa.", COLOR_MAL)
        return
    jugador.abrir_panel(_feed(juego, jugador))
    if juego.logros is not None:
        juego.logros.conseguir("conectado", jugador)


def volver(juego, jugador):
    """La tecla de celular con el celular abierto: atrás, o cerrar desde el inicio."""
    panel = jugador.panel or {}
    if panel.get("vista") in (None, "feed"):
        marcar_vistas(juego, jugador)
        jugador.cerrar_panel()
    else:
        jugador.abrir_panel(_feed(juego, jugador))


# -- Qué va en cada pestaña --------------------------------------------------------------------

def nombre_lugar(pub):
    """El nombre del lugar del que habla una publicación (o None)."""
    if pub.rumor is not None:
        return NOMBRE_LUGAR.get(pub.rumor.get("lugar"), "un lugar de la nave")
    return getattr(pub, "nombre_lugar", None)


def es_mision_activa(red, pub):
    """Algo que todavía hay que ir a verificar."""
    if pub.tipo == "rumor":
        return not pub.desmentida
    if pub.tipo == "trampa":
        return not pub.reportada and pub is red.trampa_activa()
    return False


def estado_mision(red, jugador, pub):
    """"foto" (ya la tiene), "en_curso", "pendiente", "hecha" o "reportada"."""
    if pub.tipo == "rumor" and pub.desmentida:
        return "hecha"
    if pub.tipo == "trampa" and pub.reportada:
        return "reportada"
    if pub in red.evidencias.get(jugador, []):
        return "foto"
    if red.investigando.get(jugador) is pub:
        return "en_curso"
    return "pendiente"


def misiones(red, jugador):
    nodo = red.nodo_de(jugador)
    yendo = red.investigando.get(jugador)
    activas = [p for p in reversed(red.publicaciones)
               if p.tipo in ("rumor", "trampa") and (nodo in p.alcanzados or p is yendo)
               and es_mision_activa(red, p)]
    orden = {"en_curso": 0, "foto": 1, "pendiente": 2}
    activas.sort(key=lambda p: orden.get(estado_mision(red, jugador, p), 3))
    hechas = [p for p in reversed(red.publicaciones)
              if p.tipo in ("rumor", "trampa") and nodo in p.alcanzados
              and not es_mision_activa(red, p)][:MAX_HECHAS]
    return activas + hechas


def _es_de_jugador(red, nodo):
    return str(nodo).startswith("jugador_")


def equipo(red, jugador):
    return [p for p in red.feed(jugador)
            if (p.tipo in ("desmentido", "compartido") and _es_de_jugador(red, p.autor))
            or p.tipo == "testimonio"]


def charla(red, jugador):
    del_equipo = set(id(p) for p in equipo(red, jugador))
    return [p for p in red.feed(jugador)
            if p.tipo not in ("rumor", "trampa") and id(p) not in del_equipo]


def contenido(red, jugador, pestana):
    if pestana == "misiones":
        return misiones(red, jugador)
    if pestana == "equipo":
        return equipo(red, jugador)
    return charla(red, jugador)


def avisos(red, jugador):
    """Lo que dice la etiqueta de NEXUS en el HUD: (misiones por hacer, nuevos)."""
    por_hacer = [p for p in misiones(red, jugador) if es_mision_activa(red, p)]
    vistas = red.vistas[jugador]
    nuevos = sum(1 for p in por_hacer + equipo(red, jugador) if p.id not in vistas)
    return len(por_hacer), nuevos


def sin_ver(red, jugador, pestana):
    vistas = red.vistas[jugador]
    return sum(1 for p in contenido(red, jugador, pestana) if p.id not in vistas
               and (pestana != "misiones" or es_mision_activa(red, p)))


def pestana_de(red, jugador):
    return red.pestanas.get(jugador, "misiones")


def marcar_vistas(juego, jugador):
    """Lo de las pestañas Equipo y Red se da por visto al mirarlo."""
    red = juego.nexus
    panel = jugador.panel or {}
    if red is None or panel.get("vista") != "feed":
        return
    pestana = panel.get("pestana")
    if pestana in ("equipo", "red"):
        red.vistas[jugador].update(p.id for p in contenido(red, jugador, pestana))


def cambiar_pestana(juego, jugador, paso):
    red = juego.nexus
    panel = jugador.panel or {}
    if red is None or panel.get("tipo") != "celular" or panel.get("vista") != "feed":
        return False
    marcar_vistas(juego, jugador)
    i = CLAVES_PESTANAS.index(pestana_de(red, jugador))
    red.pestanas[jugador] = CLAVES_PESTANAS[(i + paso) % len(CLAVES_PESTANAS)]
    jugador.abrir_panel(_feed(juego, jugador))
    return True


def opciones_feed(juego, jugador):
    red = juego.nexus
    return [("post", pub) for pub in contenido(red, jugador, pestana_de(red, jugador))]


def _feed(juego, jugador):
    red = juego.nexus
    return {"tipo": "celular", "vista": "feed", "pestana": pestana_de(red, jugador),
            "opciones": opciones_feed(juego, jugador)}


# -- Una publicación ------------------------------------------------------------------------

def _post(juego, jugador, pub, camino=None):
    red = juego.nexus
    red.vistas[jugador].add(pub.id)
    acciones = []
    estado = estado_mision(red, jugador, pub) if pub.tipo in ("rumor", "trampa") else None
    # Primero lo principal: lo que hay que hacer con esta misión.
    if pub.tipo == "rumor" and not pub.desmentida:
        if estado == "foto":
            acciones.append(("Publicar mi foto y desmentirlo", "desmentir"))
        elif estado == "en_curso":
            acciones.append(("Dejar de verificarlo", "no_investigar"))
        else:
            acciones.append(("Ir a verificarlo", "investigar"))
    if pub.tipo == "trampa" and es_mision_activa(red, pub):
        if estado == "en_curso":
            acciones.append(("Dejar de ir", "no_investigar"))
        else:
            acciones.append(("Ir a ayudar", "investigar"))
    if pub.tipo in ("rumor", "trampa"):
        acciones.append(("¿De dónde salió esto?", "rastrear"))
        via = red.via(jugador, pub)
        if via in red.grafo and via != red.nodo_de(jugador):
            acciones.append((f"Reportar a {red.usuario(via)}", "reportar_via"))
    if pub.autor != red.nodo_de(jugador):
        acciones.append(("Compartir", "compartir"))
    acciones.append(("Volver", "volver"))
    return {"tipo": "celular", "vista": "post", "pub": pub, "opciones": acciones,
            "camino": camino, "estado": estado}


def _mensaje(texto, puntos, color=None, cerrar=False):
    opciones = [("Cerrar el celular", "cerrar")] if cerrar else []
    opciones.append(("Volver al inicio", "volver"))
    return {"tipo": "celular", "vista": "mensaje", "texto": texto, "puntos": puntos,
            "color": color or (COLOR_BIEN if puntos >= 0 else COLOR_MAL),
            "opciones": opciones}


def confirmar(juego, jugador):
    """El jugador eligió la opción del cursor."""
    red = juego.nexus
    panel = jugador.panel
    if red is None or panel is None:
        jugador.cerrar_panel()
        return
    opciones = panel.get("opciones", [])
    if not opciones:
        if panel.get("vista") != "feed":
            jugador.abrir_panel(_feed(juego, jugador))
        return
    eleccion = opciones[jugador.cursor % len(opciones)]
    vista = panel["vista"]

    if vista == "feed":
        _tipo, pub = eleccion
        marcar_vistas(juego, jugador)
        jugador.abrir_panel(_post(juego, jugador, pub))
        return

    accion = eleccion[1]
    if accion == "volver":
        jugador.abrir_panel(_feed(juego, jugador))
        return
    if accion == "cerrar":
        jugador.cerrar_panel()
        return

    if vista == "ubicacion":
        texto, puntos = red.desmentir(jugador, panel["rumor"], accion == "tal_cual")
        jugador.tareas_hechas += 1
        jugador.abrir_panel(_mensaje(texto, puntos))
        return

    if vista == "origen":
        if accion == "reportar_origen":
            texto, puntos = red.reportar(jugador, panel["origen"])
            jugador.abrir_panel(_mensaje(texto, puntos))
        elif accion == "reportar_suplantacion":
            texto, puntos = red.reportar_suplantacion(jugador, panel["pub"])
            jugador.abrir_panel(_mensaje(texto, puntos))
        return

    pub = panel["pub"]
    if accion == "investigar":
        red.investigar(jugador, pub)
        lugar = nombre_lugar(pub) or "el lugar"
        jugador.abrir_panel(_mensaje(
            f"¡Vamos a {lugar}! Sigue la flecha azul. Al llegar, la foto se saca sola "
            "y después la publicas desde Misiones.", 0, (120, 190, 255), cerrar=True))
    elif accion == "no_investigar":
        red.investigando.pop(jugador, None)
        jugador.abrir_panel(_post(juego, jugador, pub))
    elif accion == "desmentir":
        jugador.abrir_panel({"tipo": "celular", "vista": "ubicacion", "rumor": pub,
                             "opciones": [("Publicar la foto tal cual", "tal_cual"),
                                          ("Recortar el fondo y publicar", "recortada"),
                                          ("Volver", "volver")]})
    elif accion == "compartir":
        texto, puntos = red.compartir(jugador, pub)
        jugador.abrir_panel(_mensaje(texto, puntos))
    elif accion == "reportar_via":
        texto, puntos = red.reportar(jugador, red.via(jugador, pub))
        jugador.abrir_panel(_mensaje(texto, puntos))
    elif accion == "rastrear":
        camino = red.rastrear(jugador, pub)
        origen = camino[0] if camino else pub.autor
        opciones = []
        if pub.suplantada and not pub.reportada:
            opciones.append((f"Reportar suplantación de {red.usuario(origen)}",
                             "reportar_suplantacion"))
        elif origen in red.grafo and origen != red.nodo_de(jugador):
            opciones.append((f"Reportar a {red.usuario(origen)}", "reportar_origen"))
        opciones.append(("Volver", "volver"))
        jugador.abrir_panel({"tipo": "celular", "vista": "origen", "pub": pub,
                             "camino": camino, "origen": origen, "opciones": opciones})


# -- Central de ayuda: lo que muestran las Terminales NEXUS del mapa ----------------------

def _pie(jugador):
    return (f"[{jugador.pista_mover()}] elegir   "
            f"[{jugador.nombre_tecla('interactuar')}] confirmar")


def lineas_estado(juego):
    """Cómo va el equipo en NEXUS, para la central de ayuda."""
    from data.nexus import NOMBRE_LUGAR, UMBRAL_PLANOS
    red = juego.nexus
    if red is None:
        return ["NEXUS no tiene señal en este mapa."]
    verde, rojo = red.barras()
    lineas = [f"Confianza de la tripulación: {int(verde * 100)}% en ustedes, "
              f"{int(rojo * 100)}% en los aliens."]
    if red.planos:
        lineas.append("Ya tienen los planos de la cápsula.")
    else:
        falta = max(0, int(round((getattr(red, "umbral_planos", UMBRAL_PLANOS) - verde) * 100)))
        lineas.append(f"Planos de la cápsula: les falta {falta}% de confianza.")
    activos = red.rumores_activos()
    if activos:
        lugares = ", ".join(NOMBRE_LUGAR.get(p.rumor["lugar"], "?") for p in activos)
        lineas.append(f"Rumores sin desmentir: {len(activos)} ({lugares}).")
    else:
        lineas.append("No hay rumores sin desmentir. Por ahora.")
    if rojo > verde:
        lineas.append("Los aliens van ganando en NEXUS: están más rápidos y ven más lejos.")
    return lineas


# El dibujito de cada tema en el mosaico de la terminal (screens/paneles.py).
ICONO_TEMA = [("celular", "celular"), ("rumor", "lupa"), ("ubicaci", "ubicacion"),
              ("cuentas", "bot"), ("perfiles", "perfil")]


def _icono_de(titulo):
    t = titulo.lower()
    return next((icono for clave, icono in ICONO_TEMA if clave in t), "info")


def _detalle_caso(juego, jugador):
    """La línea de abajo del mosaico del Cambiaformas: cómo va el caso."""
    caso = juego.infiltrado
    from data.infiltrado import PRUEBAS
    if not caso.pruebas:
        return "La red está tranquila... por ahora"
    if not caso.activo:
        return "Caso cerrado: lo expusieron" if caso.estado == "expuesto" else "Caso cerrado: falló la acusación"
    mias = len(caso.pruebas_de(jugador))
    texto = f"Pruebas subidas: {len(caso.subidas)}/{len(PRUEBAS)}"
    if mias:
        texto += f"  ·  ¡llevas {mias} para subir!"
    return texto


def panel_ayuda(juego, jugador, zona=None):
    """Menú de la central de ayuda de una Terminal NEXUS: un mosaico con
    iconos. El caso del Cambiaformas (si hay) va arriba, resaltado y a todo lo
    ancho; debajo, los temas de a tres; abajo, Salir."""
    from data.nexus import AYUDA_TEMAS, UMBRAL_PLANOS
    opciones, acciones = [], []

    def agregar(opcion, accion):
        opciones.append(opcion)
        acciones.append(accion)
        return len(opciones) - 1

    filas = []
    if getattr(juego, "infiltrado", None) is not None:
        filas.append([agregar({"texto": "El caso del Cambiaformas", "icono": "cambiaformas",
                               "destacada": True, "detalle": _detalle_caso(juego, jugador)},
                              ("infiltrado", None))])
    mosaicos = [agregar({"texto": titulo, "icono": _icono_de(titulo)}, ("tema", i))
                for i, (titulo, _) in enumerate(AYUDA_TEMAS)]
    mosaicos.append(agregar({"texto": "Repasar el tutorial", "icono": "tutorial"}, ("tutorial", None)))
    filas += [mosaicos[k:k + 3] for k in range(0, len(mosaicos), 3)]
    filas.append([agregar({"texto": "Salir", "icono": "salir"}, ("salir", None))])

    cuerpo = lineas_estado(juego)[1:] if juego.nexus is not None else lineas_estado(juego)
    if juego.mision is not None and juego.mision.activa and juego.mision.objetivo():
        cuerpo += ["Ahora: " + juego.mision.objetivo()]
    red = juego.nexus
    confianza = None
    if red is not None:
        verde, rojo = red.barras()
        confianza = (verde, rojo, getattr(red, "umbral_planos", UMBRAL_PLANOS))
    mover = jugador.pista_mover()
    if "/" in mover:      # WASD: también izquierda y derecha
        mover = "".join(jugador.nombre_tecla(t) for t in ("arriba", "izquierda", "abajo", "derecha"))
    pie = (f"[{mover}] elegir   [{jugador.nombre_tecla('interactuar')}] abrir   "
           f"[{jugador.nombre_tecla('celular')}] salir")
    return {"tipo": "opciones", "accion": "ayuda_menu", "zona": zona, "nexus_terminal": True,
            "mosaico": True, "filas": filas, "confianza": confianza,
            "titulo": "NEXUS · Central de ayuda", "cuerpo": cuerpo,
            "opciones": opciones, "acciones": acciones, "pie": pie}


def _panel_tema(jugador, titulo, parrafos, zona):
    cuerpo = []
    for p in parrafos:
        cuerpo += [p, ""]
    return {"tipo": "opciones", "accion": "ayuda_tema", "zona": zona, "nexus_terminal": True,
            "titulo": titulo, "cuerpo": cuerpo[:-1],
            "opciones": [{"texto": "Volver"}], "pie": _pie(jugador)}


def confirmar_ayuda(juego, jugador):
    from data.nexus import AYUDA_TEMAS
    from juego.tutorial import pasos_con_teclas, con_teclas
    panel = jugador.panel
    zona = panel.get("zona")
    if panel["accion"] == "ayuda_tema":
        jugador.abrir_panel(panel_ayuda(juego, jugador, zona))
        return
    tipo, dato = panel["acciones"][jugador.cursor % len(panel["acciones"])]
    if tipo == "tema":
        titulo, parrafos = AYUDA_TEMAS[dato]
        jugador.abrir_panel(_panel_tema(jugador, titulo,
                                        [con_teclas(p, jugador) for p in parrafos], zona))
    elif tipo == "tutorial":
        pasos = [f"{i}. {t}" for i, t in enumerate(pasos_con_teclas(jugador), start=1)]
        jugador.abrir_panel(_panel_tema(jugador, "Tutorial", pasos, zona))
    elif tipo == "infiltrado":
        jugador.abrir_panel(juego.infiltrado.panel_terminal(jugador, zona))
    else:
        jugador.cerrar_panel()
