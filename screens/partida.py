"""Pantalla de partida: el mundo con la vista dividida por jugador.

Cada jugador tiene su propio viewport con una cámara que lo sigue. Todos los
personajes se dibujan en todos los viewports, así que cada jugador ve al otro
moverse por el mapa.

Los layouts siguen el CLAUDE.md: con dos jugadores la pantalla se parte en
vertical (izquierda y derecha); con tres, dos arriba y uno abajo a lo ancho;
con cuatro, en cuartos.
"""

import math
import os

import pygame

from juego.fuentes import fuente, fuente_de_tamano
from juego import oscuridad
from juego import vision
from screens.infiltrado_dibujo import dibujar_pruebas
from misiones import puertas
from misiones.eventos import dibujar_cajas, dibujar_brillo_caja, dibujar_flecha_caja
from screens import flechas
from juego import salas_selladas
from screens.paneles import (render_panel, render_mosaico, render_hud, render_mensaje, render_pista_zona,
                             render_pulso, render_tension, render_minijuego,
                             render_escondido, render_vidas, render_eliminado,
                             render_inventario)
from juego.ambiente import temblor, dibujar_susto
from screens.panel_habilidades import render_panel_habilidades
from screens import roles as dibujo_roles
from screens import mision_dibujo
from screens import celular as dibujo_celular


COLOR_SEPARADOR = (18, 16, 30)
COLOR_ETIQUETA = (255, 255, 255)
COLOR_SOMBRA = (12, 11, 23)
GROSOR_SEPARADOR = 4

# Colores de la vista de hitboxes (Pausa > Opciones). Son los mismos que usan los editores
# de Editores/, para que lo que se dibuja ahí se reconozca aquí.
COLOR_PARED = (90, 180, 255)
COLOR_ZONA = (255, 140, 70)
COLOR_COLISION = (230, 60, 60)
COLOR_INTERACCION = (255, 210, 40)


def calcular_viewports(ancho, alto, cantidad):
    """Divide la pantalla según cuántos jugadores haya (ver CLAUDE.md)."""
    if cantidad <= 1:
        return [pygame.Rect(0, 0, ancho, alto)]

    mitad_x = ancho // 2
    if cantidad == 2:
        # Jugador 1 a la izquierda, jugador 2 a la derecha.
        return [
            pygame.Rect(0, 0, mitad_x, alto),
            pygame.Rect(mitad_x, 0, ancho - mitad_x, alto),
        ]

    mitad_y = alto // 2
    if cantidad == 3:
        # Jugadores 1 y 2 arriba, lado a lado; el 3 abajo ocupando todo el
        # ancho. Queda como una Y invertida: dos ramas arriba y el tronco
        # abajo.
        return [
            pygame.Rect(0, 0, mitad_x, mitad_y),
            pygame.Rect(mitad_x, 0, ancho - mitad_x, mitad_y),
            pygame.Rect(0, mitad_y, ancho, alto - mitad_y),
        ]

    # Cuatro: 1 arriba-izq, 2 arriba-der, 3 abajo-izq, 4 abajo-der.
    return [
        pygame.Rect(0, 0, mitad_x, mitad_y),
        pygame.Rect(mitad_x, 0, ancho - mitad_x, mitad_y),
        pygame.Rect(0, mitad_y, mitad_x, alto - mitad_y),
        pygame.Rect(mitad_x, mitad_y, ancho - mitad_x, alto - mitad_y),
    ]


def render_partida(screen, mundo, jugadores, zonas=(), segundos_restantes=None,
                   mostrar_hitboxes=False, aliens=(), escondites=(), extras=None):
    """Dibuja un viewport por jugador, cada uno con su cámara, HUD y paneles."""
    ancho, alto = screen.get_size()
    viewports = calcular_viewports(ancho, alto, len(jugadores))
    extras = dict(extras or {})
    extras.setdefault("aliens", aliens)
    extras.setdefault("escondites", escondites)
    extras.setdefault("jugadores", jugadores)
    extras.setdefault("mundo", mundo)
    screen.fill(COLOR_SEPARADOR)

    # La barra de confianza va encima de todas las vistas: lo de cada jugador
    # que caería debajo de ella se corre (screens/paneles.fila_vidas).
    barra = (dibujo_celular.rect_confianza(screen, len(jugadores))
             if extras.get("nexus") is not None else None)
    for indice, jugador in enumerate(jugadores):
        if indice >= len(viewports):
            break
        vista = viewports[indice]
        tapado = barra if barra is not None and barra.colliderect(vista) else None
        _dibujar_vista(screen, vista, mundo, jugadores, jugador, zonas, mostrar_hitboxes,
                       aliens, escondites, extras)

        # Lo de la interfaz va después del mundo pero sigue recortado al
        # viewport: si un jugador abre un panel, los demás no lo ven ni se les
        # congela su parte.
        clip_previo = screen.get_clip()
        screen.set_clip(vista)
        render_escondido(screen, vista, jugador)
        render_tension(screen, vista, jugador)
        render_hud(screen, vista, jugador, segundos_restantes)
        dibujo_celular.render_aviso_celular(screen, vista, jugador, extras.get("nexus"))
        render_vidas(screen, vista, jugador, tapado)
        render_escolta(screen, vista, jugador, extras.get("escolta"), tapado, extras.get("nexus"))
        render_pista_zona(screen, vista, jugador)
        if jugador.panel is not None and jugador.panel.get("tipo") == "habilidades":
            render_panel_habilidades(screen, vista, jugador)
        elif jugador.panel is not None and jugador.panel.get("tipo") == "emision":
            render_mapa_emision(screen, vista, jugador, mundo)
        elif jugador.panel is not None and jugador.panel.get("tipo") == "celular":
            pass    # el celular va al final, encima del inventario y del pulso
        elif jugador.panel is not None and jugador.panel.get("mosaico"):
            pass    # la Terminal NEXUS va encima de todo (render_terminales_encima)
        else:
            render_panel(screen, vista, jugador)
        render_mensaje(screen, vista, jugador, tapado)
        render_pulso(screen, vista, jugador)
        render_inventario(screen, vista, jugador)
        dibujo_roles.render_minimapa(screen, vista, jugador, extras)
        mision_dibujo.render_progreso(screen, vista, jugador)
        if jugador.panel is not None and jugador.panel.get("tipo") == "celular":
            dibujo_celular.render_celular(screen, vista, jugador, extras.get("nexus"), tapado)
        render_minijuego(screen, vista, jugador)
        render_tutorial(screen, vista, jugador, extras.get("tutorial"))
        dibujar_susto(screen, vista, jugador)
        render_eliminado(screen, vista, jugador)
        screen.set_clip(clip_previo)

    _dibujar_separadores(screen, viewports)
    dibujo_celular.render_confianza(screen, extras.get("nexus"), len(jugadores))
    render_evento(screen, extras.get("eventos"),
                  dibujo_celular.desplazamiento_avisos(screen, len(jugadores), extras.get("nexus")))
    if mostrar_hitboxes:
        _dibujar_leyenda(screen, mundo, jugadores)


def render_terminales_encima(screen, jugadores):
    """La Terminal NEXUS (un mosaico que ocupa casi toda la vista) se dibuja
    al final, encima de la barra de confianza y del cartel de la IA, que si no
    le tapaban la parte de arriba."""
    viewports = calcular_viewports(*screen.get_size(), len(jugadores))
    for vista, jugador in zip(viewports, jugadores):
        if jugador.panel is not None and jugador.panel.get("mosaico"):
            clip_previo = screen.get_clip()
            screen.set_clip(vista)
            render_mosaico(screen, vista, jugador)
            screen.set_clip(clip_previo)


def _dibujar_leyenda(screen, mundo, jugadores):
    """Franja inferior que explica de qué es cada color (Pausa > Opciones > Ver hitboxes)."""
    entradas = [
        (COLOR_PARED, f"paredes ({len(mundo.paredes)})"),
        (COLOR_ZONA, f"zonas ({len(mundo.interactuables)})"),
        (COLOR_COLISION, "colision personaje"),
        (COLOR_INTERACCION, "interaccion personaje"),
    ]
    font = fuente("small")
    alto_franja = 26
    y = screen.get_height() - alto_franja

    franja = pygame.Surface((screen.get_width(), alto_franja), pygame.SRCALPHA)
    franja.fill((0, 0, 0, 190))
    screen.blit(franja, (0, y))

    x = 12
    for color, texto in entradas:
        pygame.draw.rect(screen, color, (x, y + 8, 14, 10), 2)
        etiqueta = font.render(texto, True, COLOR_ETIQUETA)
        screen.blit(etiqueta, (x + 20, y + 4))
        x += 20 + etiqueta.get_width() + 22



def _dibujar_vista(screen, vista, mundo, jugadores, dueño, zonas, mostrar_hitboxes,
                   aliens=(), escondites=(), extras=None):
    camara = mundo.camara(dueño.hitbox.center, vista.width, vista.height)
    # Si lo acaban de atrapar, su mitad de la pantalla tiembla un instante.
    camara = camara.move(*temblor(dueño, pygame.time.get_ticks()))

    # Recorta el dibujo al viewport para que nada se salga a la mitad vecina.
    clip_previo = screen.get_clip()
    screen.set_clip(vista)

    # En pantallas muy grandes un viewport puede ser más ancho o alto que el
    # mapa; en ese caso se centra lo que hay en vez de dejarlo pegado a un borde.
    destino = list(vista.topleft)
    if camara.width > mundo.ancho:
        destino[0] += (camara.width - mundo.ancho) // 2
    if camara.height > mundo.alto:
        destino[1] += (camara.height - mundo.alto) // 2
    screen.blit(mundo.imagen, destino, area=camara)
    # Las salas selladas (menos jugadores, mapa más chico): oscuras y con
    # franjas de peligro en la entrada.
    salas_selladas.dibujar(screen, (camara.x - destino[0], camara.y - destino[1]), camara, mundo)

    if mostrar_hitboxes:
        # Hitboxes del fondo: paredes y zonas interactuables del mapa.
        for pared in mundo.paredes:
            if pared.colliderect(camara):
                pygame.draw.rect(screen, COLOR_PARED, _a_pantalla(pared, vista, camara), 2)
        for zona in mundo.interactuables:
            if zona.colliderect(camara):
                pygame.draw.rect(screen, COLOR_ZONA, _a_pantalla(zona, vista, camara), 2)

    # Zonas de tarea: se dibujan antes que los personajes para que queden en
    # el piso. Solo se marcan las que ese jugador puede usar, así cada mitad de
    # la pantalla le muestra a su dueño a dónde le toca ir.
    for zona in zonas:
        if zona["roles"] and getattr(dueño, "rol", None) not in zona["roles"]:
            continue
        rect = zona["rect"]
        if not rect.inflate(0, 160).colliderect(camara):   # el sprite sobresale hacia arriba
            continue
        en_pantalla = _a_pantalla(rect, vista, camara)
        _dibujar_zona(screen, en_pantalla, zona, dueño)

    offset = (camara.x - vista.x, camara.y - vista.y)

    for escondite in escondites:
        if escondite["rect"].inflate(0, 120).colliderect(camara):
            _dibujar_escondite(screen, escondite, offset, dueño)
    tiempo_ms = pygame.time.get_ticks()
    if extras:
        mision_dibujo.dibujar_piso(screen, offset, camara, dueño, extras.get("mision"), tiempo_ms)
        if extras.get("guardia_planta") is not None:
            extras["guardia_planta"].dibujar_planta(screen, offset, camara, tiempo_ms)
        dibujo_roles.dibujar_piso(screen, offset, camara, dueño, extras, tiempo_ms)

    if extras:
        puertas.dibujar(screen, offset, camara, extras.get("puertas_dobles", ()),
                        extras.get("compuertas", ()), tiempo_ms)
        dibujar_cajas(screen, offset, camara, extras.get("eventos"), tiempo_ms)
        dibujar_pruebas(screen, offset, camara, extras.get("infiltrado"), tiempo_ms)

    # Durante un apagón de los aliens solo se ve su cuerpo (y su señal),
    # oscurecidos como todo lo demás: ni conos, ni el anillo del Ciego, ni
    # ojos. Así no queda otra que ir a prender la caja de fusibles.
    a_oscuras = bool((extras or {}).get("oscuridad")) and not mostrar_hitboxes

    # Campo de visión (vision.py): lo que el dueño tiene detrás de una pared no
    # se ve. Los aliens fuera de su vista no se dibujan (ni cuerpo, ni cono, ni
    # señal); los compañeros sí, oscurecidos como el resto del mapa.
    campo = None
    todos_los_aliens = list(aliens)      # (los que no ve, la Sintonía los oye: pasos rosados)
    npcs = list((extras or {}).get("npcs", ()))
    if (extras or {}).get("vision") and not mostrar_hitboxes:
        campo = vision.campo_de(dueño.hitbox.center, vision.obstaculos(
            mundo, extras.get("puertas_dobles", ()), extras.get("compuertas", ())))
        aliens = [a for a in aliens if campo.ve_a(a.hitbox)]
        npcs = [n for n in npcs if campo.ve_a(n.hitbox)]

    # Los conos de visión van en el piso, debajo de todos los personajes.
    if not a_oscuras:
        for alien in aliens:
            alien.dibujar_vision(screen, offset)

    # Jugadores y aliens juntos, ordenados por Y para que el de adelante tape
    # al de atrás.
    for jugador in sorted(list(jugadores) + list(aliens) + npcs, key=lambda j: j.hitbox.bottom):
        jugador.dibujar(screen, offset)
        if mostrar_hitboxes:
            # Hitboxes del personaje: la de colisión y la de interacción.
            interaccion = getattr(jugador, "interactable_hitbox", None)
            if interaccion is not None:
                pygame.draw.rect(screen, COLOR_INTERACCION,
                                 _a_pantalla(interaccion, vista, camara), 1)
            pygame.draw.rect(screen, COLOR_COLISION,
                             _a_pantalla(jugador.hitbox, vista, camara), 2)

    # Oscuridad: encima del mundo y de los personajes, debajo de los avisos.
    # Con [H] se apaga para poder revisar las hitboxes.
    eventos = (extras or {}).get("eventos")
    # Las señales (!, ?, zZ, ...) se dibujan ANTES de la oscuridad: en un
    # apagón quedan tan oscuras como el resto del alien y solo se leen bien
    # donde llega la linterna.
    for alien in aliens:
        alien.dibujar_senal(screen, offset)
    if a_oscuras or campo is not None:
        oscuridad.dibujar(screen, vista, camara, dueño, jugadores, a_oscuras,
                          campo.puntos if campo else None)
    if a_oscuras:
        dibujar_brillo_caja(screen, offset, dueño, eventos, tiempo_ms)
    # Los ojos de la Sombra brillan encima de la oscuridad: a oscuras es lo
    # único que se le ve (sombra.py).
    for alien in aliens:
        ojos = getattr(alien, "dibujar_ojos", None)
        if ojos is not None:
            ojos(screen, offset, tiempo_ms)
    _dibujar_ruido(screen, offset, dueño)
    if extras:
        # Sintonía (Resonante): los pasos de los aliens que están en su
        # pantalla pero no ve (detrás de una pared o a oscuras).
        dibujo_roles.dibujar_pasos(screen, offset, camara, dueño, todos_los_aliens, aliens,
                                   a_oscuras, tiempo_ms)

    if extras:
        mision_dibujo.dibujar_encima(screen, offset, camara, extras.get("mision"), tiempo_ms)
        dibujo_roles.dibujar_encima(screen, offset, camara, dueño, extras, tiempo_ms)
        dibujo_roles.dibujar_flechas(screen, vista, camara, dueño, extras)
        # La roja primero: en un apagón manda, y las otras se corren si
        # apuntan casi para el mismo lado (screens/flechas.py).
        flechas.empezar()
        dibujar_flecha_caja(screen, vista, camara, dueño, extras.get("eventos"), tiempo_ms)
        dibujo_celular.dibujar_lugar(screen, vista, camara, dueño, extras.get("nexus"), tiempo_ms)
        mision_dibujo.dibujar_flecha_objetivo(screen, vista, camara, dueño, extras.get("mision"),
                                              extras.get("dificultad"), extras.get("nexus"),
                                              tiempo_ms)

    screen.set_clip(clip_previo)


_mapas_emision = {}


def render_mapa_emision(screen, vista, jugador, mundo):
    """El mapa de la nave para escoger dónde cae la señal de la Emisión.

    Solo se ve el Resonante (para no mandar los aliens encima de alguien por
    error, hay que saber dónde está uno mismo) y el cursor, con el círculo de
    hasta dónde se oye la señal. Guarda en el panel el rect y la escala del
    mapa para que el clic del mouse se pueda pasar a coordenadas del mundo.
    """
    from entidades.acciones_rol import RADIO_EMISION
    panel = jugador.panel
    margen = 24
    alto_pie = 28
    disponible = vista.inflate(-margen * 2, -margen * 2 - alto_pie)
    escala = min(disponible.width / mundo.ancho, disponible.height / mundo.alto)
    tam = (max(1, int(mundo.ancho * escala)), max(1, int(mundo.alto * escala)))
    clave = (id(mundo.imagen), tam, salas_selladas.clave_cache(mundo))
    if clave not in _mapas_emision:
        mini = salas_selladas.oscurecer_miniatura(pygame.transform.smoothscale(mundo.imagen, tam), mundo)
        mini.fill((150, 150, 175), special_flags=pygame.BLEND_RGB_MULT)
        _mapas_emision[clave] = mini
    rect = pygame.Rect(0, 0, *tam)
    rect.centerx = vista.centerx
    rect.y = disponible.y + (disponible.height - tam[1]) // 2
    panel["rect_mapa"], panel["escala_mapa"] = rect, escala

    fondo = pygame.Surface(vista.size, pygame.SRCALPHA)
    fondo.fill((8, 8, 18, 200))
    screen.blit(fondo, vista.topleft)
    screen.blit(_mapas_emision[clave], rect.topleft)
    pygame.draw.rect(screen, (233, 120, 200), rect, 2)

    def a_mapa(p):
        return int(rect.x + p[0] * escala), int(rect.y + p[1] * escala)

    t = pygame.time.get_ticks()
    # Él mismo.
    yo = a_mapa(jugador.hitbox.center)
    pygame.draw.circle(screen, (255, 255, 255), yo, 7 + int(2 * math.sin(t / 200)), 2)
    pygame.draw.circle(screen, (233, 120, 200), yo, 4)
    # El cursor y hasta dónde llega la señal.
    cx, cy = a_mapa(panel["cursor_mapa"])
    radio = max(4, int(RADIO_EMISION * escala))
    capa = pygame.Surface((radio * 2 + 4, radio * 2 + 4), pygame.SRCALPHA)
    pygame.draw.circle(capa, (255, 214, 64, 40), (radio + 2, radio + 2), radio)
    pygame.draw.circle(capa, (255, 214, 64, 150), (radio + 2, radio + 2), radio, 1)
    clip_previo = screen.get_clip()
    screen.set_clip(rect.clip(clip_previo))       # el círculo no se sale del mapa
    screen.blit(capa, (cx - radio - 2, cy - radio - 2))
    screen.set_clip(clip_previo)
    for d in (-1, 1):
        pygame.draw.line(screen, (255, 214, 64), (cx + d * 4, cy), (cx + d * 12, cy), 2)
        pygame.draw.line(screen, (255, 214, 64), (cx, cy + d * 4), (cx, cy + d * 12), 2)
    pygame.draw.circle(screen, (255, 214, 64), (cx, cy), 3)

    texto_pie = (f"[clic] o [mover + {jugador.nombre_tecla('interactuar')}] poner señal   "
                 f"[{jugador.nombre_tecla('habilidad')}] cancelar")
    # La letra más grande que quepa en el ancho de la vista.
    for tam in (18, 16, 14, 13, 12, 11):
        f = fuente_de_tamano(tam)
        if f.size(texto_pie)[0] <= vista.width - 24:
            break
    titulo = f.render("Emisión modulada: ¿dónde cae la señal?", True, (233, 120, 200))
    screen.blit(titulo, (rect.x, rect.y - titulo.get_height() - 4))
    pie = f.render(texto_pie, True, (200, 210, 235))
    screen.blit(pie, (vista.centerx - pie.get_width() // 2, rect.bottom + 8))


def _dibujar_ruido(screen, offset, dueño):
    """El anillo de ruido del jugador: si un alien queda adentro, lo oye.

    Celeste cuando va en sigilo, para que se note que la tecla sirve.
    """
    if (getattr(dueño, "preso", None) is not None or not hasattr(dueño, "radio_ruido")
            or not getattr(dueño, "puede_moverse", True)):
        return
    centro = (dueño.hitbox.centerx - offset[0], dueño.hitbox.centery - offset[1])
    radio = int(dueño.radio_ruido)
    sigilo = getattr(dueño, "sigilo", False)
    if sigilo:
        color = (110, 220, 255)
    elif dueño.pulso > 70:
        color = (240, 90, 80)
    else:
        color = (150, 160, 190)
    pygame.draw.circle(screen, color, centro, radio, 1)
    if sigilo:
        pygame.draw.circle(screen, color, centro, max(4, radio - 4), 1)


def _envolver(texto, f, ancho):
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = f"{actual} {palabra}".strip()
        if f.size(prueba)[0] <= ancho or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def render_escolta(screen, vista, jugador, escoltado, tapado=None, red=None):
    """Debajo de las vidas, lo que está haciendo ahora: a quién lleva a la
    cápsula (npcs.py; muestra el nombre que se ve, aunque sea el Cambiaformas
    disfrazado) y qué está verificando en NEXUS (o si ya tiene la foto)."""
    lineas = []
    usuario = escoltado(jugador) if escoltado is not None else None
    if usuario:
        lineas.append((f"Te sigue: {usuario}  ->  cápsula", (120, 230, 150)))
    if red is not None and not jugador.preso:
        from redes import celular as logica
        fotos = [p for p in red.evidencias.get(jugador, []) if logica.es_mision_activa(red, p)]
        yendo = red.investigando.get(jugador)
        if fotos:
            lineas.append((f"Foto lista: publícala en NEXUS [{jugador.nombre_tecla('celular')}]",
                           (120, 230, 150)))
        elif yendo is not None and logica.es_mision_activa(red, yendo):
            lugar = logica.nombre_lugar(yendo) or "el lugar"
            lineas.append((f"Verificando: {lugar}  ->  sigue la flecha azul", (120, 190, 255)))
    jugador.hud_abajo = 0           # hasta dónde llega esto (el mensaje va debajo)
    if not lineas:
        return
    from screens.paneles import fila_vidas
    corazones, _ = fila_vidas(vista, jugador, tapado)
    y = corazones.bottom + 2
    f = fuente_de_tamano(max(13, min(16, vista.width // 50)))
    for texto, color in lineas:
        img = f.render(texto, True, color)
        fondo = pygame.Surface((img.get_width() + 16, img.get_height() + 8), pygame.SRCALPHA)
        fondo.fill((14, 15, 28, 170))
        screen.blit(fondo, (corazones.x, y))
        screen.blit(img, (corazones.x + 8, y + 4))
        y += img.get_height() + 10
    jugador.hud_abajo = y


def render_tutorial(screen, vista, jugador, tutorial):
    """El paso del tutorial de este jugador, abajo del centro de su vista."""
    if tutorial is None or not tutorial.activo or not getattr(jugador, "puede_moverse", True):
        return   # los puestos sin mando todavía no se mueven: no hay qué enseñarles
    datos = tutorial.texto(jugador)
    if datos is None:
        return
    paso, total, texto = datos
    pequena = vista.height < 500
    f = fuente_de_tamano(15 if pequena else 18)
    f_chica = fuente_de_tamano(12 if pequena else 14)
    ancho = min(vista.width - 40, 600)
    lineas = _envolver(texto, f, ancho - 32)
    alto = 40 + len(lineas) * f.get_linesize() + f_chica.get_linesize()
    caja = pygame.Rect(0, 0, ancho, alto)
    if pequena:
        # Con 3 o 4 jugadores abajo no cabe: ahí van el pulso, la pista y la
        # barra de progreso. Se pone arriba, debajo del HUD y los mensajes; en
        # la fila de arriba, además, debajo del cartel de la IA (y=100..152).
        caja.midtop = (vista.centerx, vista.y + (160 if vista.top == 0 else 108))
    else:
        caja.midtop = (vista.centerx, vista.centery + vista.height // 7)
    fondo = pygame.Surface(caja.size, pygame.SRCALPHA)
    fondo.fill((12, 14, 30, 225))
    screen.blit(fondo, caja.topleft)
    pygame.draw.rect(screen, (90, 220, 230), caja, 2, border_radius=6)
    hechos, necesarios = tutorial.listos()
    titulo = f_chica.render(f"TUTORIAL  {paso}/{total}   ·   los aliens despiertan cuando "
                            f"todos terminen ({hechos}/{necesarios})", True, (90, 220, 230))
    if titulo.get_width() > caja.width - 32:
        titulo = f_chica.render(f"TUTORIAL  {paso}/{total}   ·   listos {hechos}/{necesarios}",
                                True, (90, 220, 230))
    screen.blit(titulo, (caja.x + 16, caja.y + 10))
    y = caja.y + 14 + f_chica.get_linesize()
    for linea in lineas:
        screen.blit(f.render(linea, True, (240, 242, 255)), (caja.x + 16, y))
        y += f.get_linesize()
    if tutorial.esta_listo(jugador):
        return
    ultimo = paso == total
    pie = f_chica.render(f"[{jugador.nombre_tecla('habilidad')}] "
                         + ("terminar" if ultimo else "siguiente"), True, (150, 156, 190))
    screen.blit(pie, (caja.right - pie.get_width() - 14, caja.bottom - pie.get_height() - 8))


def render_evento(screen, eventos, bajar=0):
    """Aviso arriba al centro mientras dura un evento aleatorio."""
    if eventos is None:
        return
    texto = eventos.texto()
    if texto is None:
        return
    color = eventos.color()
    f = fuente_de_tamano(18)
    img = f.render(texto, True, color)
    # Debajo del cartel de la IA (y=100..152): más arriba chocaba con los
    # mensajes de cada jugador. No coincide con el tutorial (no hay eventos
    # mientras dura), que con 3 o 4 jugadores usa este mismo lugar.
    caja = img.get_rect(midtop=(screen.get_width() // 2, 160 + bajar)).inflate(28, 10)
    fondo = pygame.Surface(caja.size, pygame.SRCALPHA)
    fondo.fill((10, 8, 20, 220))
    screen.blit(fondo, caja.topleft)
    if (pygame.time.get_ticks() // 400) % 2:
        pygame.draw.rect(screen, color, caja, 2, border_radius=4)
    screen.blit(img, img.get_rect(center=caja.center))


def _dibujar_escondite(screen, escondite, offset, dueño):
    """Casillero provisional (falta el arte): una caja de metal con rendijas."""
    entrada = escondite["rect"]
    caja = pygame.Rect(0, 0, 50, 78)
    caja.midbottom = (entrada.centerx - offset[0], entrada.top + 6 - offset[1])

    mio = escondite["ocupante"] is dueño
    cerca = getattr(dueño, "escondite_cerca", None) is escondite
    revisado = escondite.get("revisado_por") is not None

    pygame.draw.rect(screen, (10, 12, 20), caja.move(3, 3), border_radius=4)
    pygame.draw.rect(screen, (78, 96, 120), caja, border_radius=4)
    borde = (236, 70, 60) if revisado else (255, 214, 64) if (cerca or mio) else (34, 40, 58)
    pygame.draw.rect(screen, borde, caja, 3 if (cerca or mio or revisado) else 2, border_radius=4)
    for i in range(4):
        y = caja.y + 12 + i * 7
        pygame.draw.line(screen, (34, 40, 58), (caja.x + 12, y), (caja.right - 12, y), 2)
    pygame.draw.circle(screen, (200, 205, 220), (caja.right - 10, caja.centery + 8), 3)

    if cerca or mio:
        texto = "Escondido" if mio else escondite["nombre"]
        etiqueta = fuente("small").render(texto, True, (255, 214, 64))
        sombra = fuente("small").render(texto, True, COLOR_SOMBRA)
        pos = (caja.centerx - etiqueta.get_width() // 2, caja.y - etiqueta.get_height() - 4)
        screen.blit(sombra, (pos[0] + 2, pos[1] + 2))
        screen.blit(etiqueta, pos)


# Sprite de las terminales NEXUS (de Anny). Si no está, se marcan con un
# círculo en el piso como las demás zonas.
RUTA_SPRITE_NEXUS = os.path.join("Imagenes", "Objetos", "terminal.png")
ESCALA_NEXUS = 1.5
_sprite_nexus = []


def sprite_nexus():
    if not _sprite_nexus:
        try:
            base = pygame.image.load(RUTA_SPRITE_NEXUS).convert_alpha()
            _sprite_nexus.append(pygame.transform.scale(
                base, (int(base.get_width() * ESCALA_NEXUS), int(base.get_height() * ESCALA_NEXUS))))
        except (pygame.error, FileNotFoundError):
            _sprite_nexus.append(None)
    return _sprite_nexus[0]


def _dibujar_terminal_nexus(screen, rect, zona, encima, sprite):
    """La terminal parada al fondo de su zona: el jugador la usa parándose
    enfrente. Con borde amarillo si está encima."""
    color = zona.get("color", COLOR_ZONA)
    # La base queda un poco arriba del centro: quien la usa se para enfrente
    # (se dibuja encima de ella), no adentro.
    caja = sprite.get_rect(midbottom=(rect.centerx, rect.centery - 24))
    if encima:
        brillo = pygame.Surface(caja.inflate(24, 24).size, pygame.SRCALPHA)
        pygame.draw.ellipse(brillo, (*color, 60), brillo.get_rect())
        screen.blit(brillo, caja.inflate(24, 24).topleft)
    screen.blit(sprite, caja)
    if encima:
        pygame.draw.rect(screen, (255, 214, 64), caja.inflate(6, 6), 2, border_radius=6)
    etiqueta = fuente("small").render(zona["nombre"], True, color)
    sombra = fuente("small").render(zona["nombre"], True, COLOR_SOMBRA)
    pos = (caja.centerx - etiqueta.get_width() // 2, caja.top - etiqueta.get_height() - 4)
    screen.blit(sombra, (pos[0] + 2, pos[1] + 2))
    screen.blit(etiqueta, pos)


def _dibujar_zona(screen, rect, zona, dueño):
    """Marca una zona en el piso, más brillante si el jugador está encima."""
    encima = getattr(dueño, "zona_cerca", None) is zona
    color = zona.get("color", COLOR_ZONA)
    if str(zona.get("clave", "")).startswith("nexus") and sprite_nexus() is not None:
        _dibujar_terminal_nexus(screen, rect, zona, encima, sprite_nexus())
        return
    grosor = 4 if encima else 2

    marca = pygame.Surface(rect.size, pygame.SRCALPHA)
    marca.fill((*color, 70 if encima else 38))
    screen.blit(marca, rect.topleft)
    pygame.draw.ellipse(screen, color, rect, grosor)

    etiqueta = fuente("small").render(zona["nombre"], True, color)
    sombra = fuente("small").render(zona["nombre"], True, COLOR_SOMBRA)
    pos = (rect.centerx - etiqueta.get_width() // 2, rect.top - etiqueta.get_height() - 4)
    screen.blit(sombra, (pos[0] + 2, pos[1] + 2))
    screen.blit(etiqueta, pos)


def _a_pantalla(rect, vista, camara):
    """Pasa un rect de coordenadas del mundo a coordenadas de pantalla."""
    return pygame.Rect(
        rect.x - camara.x + vista.x,
        rect.y - camara.y + vista.y,
        rect.width, rect.height,
    )


def _dibujar_separadores(screen, viewports, color=COLOR_SEPARADOR,
                         grosor=GROSOR_SEPARADOR):
    """Dibuja el borde interior de cada viewport.

    Antes se trazaban líneas de lado a lado de la pantalla a la altura de cada
    borde. Con dos o cuatro jugadores daba igual porque los cortes van de punta
    a punta, pero con tres la línea vertical que separa a J1 de J2 seguía bajando
    y partía en dos la vista de J3. Recorriendo los bordes de cada viewport, el
    separador se dibuja solo donde de verdad hay dos vistas pegadas.
    """
    ancho, alto = screen.get_size()
    mitad = max(1, grosor // 2)
    for vista in viewports:
        if vista.left > 0:
            pygame.draw.rect(screen, color, (vista.left - mitad, vista.top, grosor, vista.height))
        if vista.right < ancho:
            pygame.draw.rect(screen, color, (vista.right - mitad, vista.top, grosor, vista.height))
        if vista.top > 0:
            pygame.draw.rect(screen, color, (vista.left, vista.top - mitad, vista.width, grosor))
        if vista.bottom < alto:
            pygame.draw.rect(screen, color, (vista.left, vista.bottom - mitad, vista.width, grosor))
