"""Paneles que se dibujan DENTRO del viewport de un jugador.

La partida es local y en pantalla dividida, así que una tarea no puede abrirse
como una pantalla que tape todo: mientras uno lee una nota o usa una terminal,
los demás tienen que poder seguir caminando por su parte. Por eso estos paneles
se dibujan recortados al viewport de su dueño y nada más.

Un panel es un diccionario, no una clase: lo arma la lógica (juego/app.py, mision.py,
infiltrado.py...) y aquí solo se dibuja. Campos que entiende:

    tipo      "opciones" | "resultado" | "habilidades" | "aviso"
    titulo    encabezado del panel
    cuerpo    lista de líneas de texto (se parten solas si no caben)
    opciones  lista de dicts con "texto" y opcionalmente "detalle"/"bloqueada"
    pie       línea de ayuda de teclas
"""

import math
import re

import pygame

from juego.fuentes import fuente_de_tamano


COLOR_FONDO = (22, 24, 42, 238)
COLOR_BORDE = (120, 132, 190)
COLOR_TITULO = (255, 214, 64)
COLOR_TEXTO = (240, 242, 252)
COLOR_TENUE = (168, 176, 214)
COLOR_SELECCION = (255, 214, 64)
COLOR_SELECCION_FONDO = (52, 57, 92)
COLOR_BLOQUEADA = (104, 108, 132)
COLOR_INFO = (245, 170, 120)

MARGEN = 18


def partir_lineas(texto, f, ancho_max):
    """Parte un párrafo en líneas que quepan en `ancho_max`."""
    palabras = texto.split()
    if not palabras:
        return [""]
    lineas, actual = [], palabras[0]
    for palabra in palabras[1:]:
        prueba = actual + " " + palabra
        if f.size(prueba)[0] <= ancho_max:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    lineas.append(actual)
    return lineas


def _fuente_para(vista):
    """Tamaño de letra proporcional al viewport.

    Con dos jugadores cada mitad es ancha; con cuatro, cada cuarto es chico y
    el mismo texto no cabe. Se escoge según el ancho y el alto disponibles: a
    1366x768 con cuatro jugadores cada vista mide 683x384 y con la letra de
    antes (18) la franja de arriba y los recuadros se comían la vista.
    """
    px = max(13, min(20, vista.width // 36, vista.height // 26))
    return fuente_de_tamano(px)


def _maquetar(panel, f, ancho_texto):
    """Reparte el contenido del panel en líneas y devuelve el alto que pide.

    Devuelve (bloques, alto). `bloques` es la lista de líneas ya partidas, que
    se reutiliza al dibujar para no partir el texto dos veces.
    """
    bloques = []
    if panel.get("titulo"):
        bloques.append(("titulo", panel["titulo"]))
    for parrafo in panel.get("cuerpo", []):
        if parrafo == "":
            bloques.append(("espacio", ""))
        else:
            bloques += [("texto", linea) for linea in partir_lineas(parrafo, f, ancho_texto)]

    paso = f.get_linesize() + 2
    opciones = panel.get("opciones", [])
    alto = MARGEN * 2 + len(bloques) * paso
    if opciones:
        alto += paso  # espacio antes de las opciones

    lineas_opcion = []
    for opcion in opciones:
        lineas = partir_lineas(opcion["texto"], f, ancho_texto - 8)
        lineas_opcion.append(lineas)
        alto += paso * len(lineas) + 6
        if opcion.get("detalle"):
            alto += paso
    if panel.get("pie"):
        alto += paso + 6
    return bloques, lineas_opcion, alto


def render_panel(screen, vista, jugador):
    """Dibuja el panel abierto del jugador dentro de su viewport.

    La letra se encoge hasta que el contenido cabe. Antes el alto se recortaba
    con `min(alto, vista.height - 40)` y el sobrante quedaba fuera de la caja,
    tapado por el recorte: en la práctica se perdían opciones sin avisar.
    """
    panel = jugador.panel
    if panel is None:
        return
    if panel.get("mosaico"):
        render_mosaico(screen, vista, jugador)
        return

    ancho = min(int(vista.width * 0.88), 720)
    ancho_texto = ancho - MARGEN * 2
    alto_max = vista.height - 40

    base = _fuente_para(vista)
    f = base
    bloques, lineas_opcion, alto = _maquetar(panel, f, ancho_texto)
    if alto > alto_max:
        for px in range(base.get_height() - 1, 10, -1):
            f = fuente_de_tamano(px)
            bloques, lineas_opcion, alto = _maquetar(panel, f, ancho_texto)
            if alto <= alto_max:
                break

    paso = f.get_linesize() + 2
    caja = pygame.Rect(0, 0, ancho, min(alto, alto_max))
    caja.center = vista.center

    fondo = pygame.Surface(caja.size, pygame.SRCALPHA)
    fondo.fill(COLOR_FONDO)
    screen.blit(fondo, caja.topleft)
    pygame.draw.rect(screen, COLOR_BORDE, caja, 3)

    clip_previo = screen.get_clip()
    screen.set_clip(caja)

    y = caja.y + MARGEN
    for clase, texto in bloques:
        if clase == "titulo":
            screen.blit(f.render(texto, True, COLOR_TITULO), (caja.x + MARGEN, y))
        elif clase == "texto":
            screen.blit(f.render(texto, True, COLOR_TEXTO), (caja.x + MARGEN, y))
        y += paso

    opciones = panel.get("opciones", [])
    if opciones:
        y += paso

    for i, opcion in enumerate(opciones):
        seleccionada = (i == jugador.cursor)
        bloqueada = opcion.get("bloqueada", False)
        lineas = lineas_opcion[i]

        alto_fila = paso * len(lineas) + (paso if opcion.get("detalle") else 0) + 4
        fila = pygame.Rect(caja.x + MARGEN - 6, y - 3, ancho - MARGEN * 2 + 12, alto_fila)
        if seleccionada:
            pygame.draw.rect(screen, COLOR_SELECCION_FONDO, fila)
            pygame.draw.rect(screen, COLOR_SELECCION, fila, 2)

        color = COLOR_BLOQUEADA if bloqueada else (
            COLOR_SELECCION if seleccionada else COLOR_TEXTO)
        for j, linea in enumerate(lineas):
            marca = ("> " if seleccionada else "  ") if j == 0 else "  "
            screen.blit(f.render(marca + linea, True, color), (caja.x + MARGEN, y))
            y += paso

        if opcion.get("detalle"):
            screen.blit(f.render("    " + opcion["detalle"], True, COLOR_TENUE),
                        (caja.x + MARGEN, y))
            y += paso
        y += 6

    if panel.get("pie"):
        pie = render_texto_mando(f, panel["pie"], COLOR_TENUE)
        screen.blit(pie, (caja.x + MARGEN, caja.bottom - MARGEN - pie.get_height()))

    screen.set_clip(clip_previo)


# -- La Terminal NEXUS: un mosaico con iconos ------------------------------------------------

COLOR_NEXUS = (150, 120, 255)
COLOR_CASO = (240, 96, 205)        # el caso del Cambiaformas, resaltado
COLOR_MOSAICO = (32, 35, 62)
COLOR_MOSAICO_SEL = (56, 61, 104)


def _texto_centrado(screen, lineas, f, centro_x, y, color):
    for linea in lineas:
        img = f.render(linea, True, color)
        screen.blit(img, (centro_x - img.get_width() // 2, y))
        y += f.get_linesize()
    return y


def _ajustar(texto, ancho, alto, tam_max, lineas_max=3):
    """La letra más grande (hasta tam_max) con la que `texto` cabe en la caja."""
    for px in range(tam_max, 9, -1):
        f = fuente_de_tamano(px)
        lineas = partir_lineas(texto, f, ancho)
        if len(lineas) <= lineas_max and len(lineas) * f.get_linesize() <= alto and \
                all(f.size(l)[0] <= ancho for l in lineas):
            return f, lineas
    f = fuente_de_tamano(10)
    return f, partir_lineas(texto, f, ancho)[:lineas_max]


def icono_nexus(screen, nombre, centro, tam, color):
    """Los dibujitos del mosaico de la Terminal NEXUS (formas de pygame)."""
    cx, cy = int(centro[0]), int(centro[1])
    t = max(10, int(tam))
    g = max(2, t // 12)                       # grosor de línea
    oscuro = (16, 17, 32)
    if nombre == "celular":
        cuerpo = pygame.Rect(0, 0, int(t * 0.52), int(t * 0.9))
        cuerpo.center = (cx, cy)
        pygame.draw.rect(screen, color, cuerpo, border_radius=max(3, t // 8))
        pantalla = cuerpo.inflate(-g * 3, -int(t * 0.28))
        pantalla.y = cuerpo.y + int(t * 0.1)
        pygame.draw.rect(screen, oscuro, pantalla, border_radius=2)
        for k in range(3):     # unas burbujitas de chat
            ancho = int(pantalla.width * (0.7 if k % 2 == 0 else 0.5))
            burbuja = pygame.Rect(0, 0, ancho, max(2, t // 12))
            burbuja.topleft = (pantalla.x + 3 if k % 2 == 0 else pantalla.right - ancho - 3,
                               pantalla.y + 4 + k * (pantalla.height - 6) // 3)
            pygame.draw.rect(screen, color, burbuja, border_radius=2)
        pygame.draw.circle(screen, oscuro, (cx, cuerpo.bottom - int(t * 0.08)), max(2, t // 14))
    elif nombre == "lupa":
        r = int(t * 0.28)
        c = (cx - int(t * 0.08), cy - int(t * 0.08))
        pygame.draw.circle(screen, color, c, r, g + 1)
        pygame.draw.line(screen, color, (c[0] + int(r * 0.7), c[1] + int(r * 0.7)),
                         (cx + int(t * 0.38), cy + int(t * 0.38)), g * 2)
        f = fuente_de_tamano(max(9, int(r * 1.3)))
        img = f.render("?", True, color)
        screen.blit(img, img.get_rect(center=c))
    elif nombre == "ubicacion":
        r = int(t * 0.26)
        top = (cx, cy - int(t * 0.12))
        pygame.draw.polygon(screen, color, [(top[0] - r, top[1] + 2), (top[0] + r, top[1] + 2),
                                            (cx, cy + int(t * 0.42))])
        pygame.draw.circle(screen, color, top, r)
        pygame.draw.circle(screen, oscuro, top, max(2, r // 2))
        pygame.draw.ellipse(screen, color, (cx - r, cy + int(t * 0.36), r * 2, max(3, t // 10)), max(1, g // 2))
    elif nombre == "bot":
        cabeza = pygame.Rect(0, 0, int(t * 0.72), int(t * 0.56))
        cabeza.center = (cx, cy + int(t * 0.08))
        pygame.draw.rect(screen, color, cabeza, border_radius=max(3, t // 8))
        pygame.draw.line(screen, color, (cx, cabeza.y), (cx, cabeza.y - int(t * 0.18)), g)
        pygame.draw.circle(screen, color, (cx, cabeza.y - int(t * 0.2)), max(2, t // 12))
        for lado in (-1, 1):
            pygame.draw.circle(screen, oscuro, (cx + lado * int(t * 0.16), cabeza.centery - int(t * 0.04)),
                               max(2, t // 11))
            pygame.draw.rect(screen, color, (cabeza.x - g * 2 if lado < 0 else cabeza.right, cabeza.centery - g,
                                             g * 2, g * 3))
        pygame.draw.line(screen, oscuro, (cx - int(t * 0.14), cabeza.bottom - int(t * 0.12)),
                         (cx + int(t * 0.14), cabeza.bottom - int(t * 0.12)), g)
    elif nombre == "perfil":
        pygame.draw.circle(screen, color, (cx, cy - int(t * 0.14)), int(t * 0.2))
        hombros = pygame.Rect(0, 0, int(t * 0.7), int(t * 0.44))
        hombros.midtop = (cx, cy + int(t * 0.1))
        pygame.draw.ellipse(screen, color, hombros)
        pygame.draw.rect(screen, oscuro, (cx - int(t * 0.4), cy + int(t * 0.34), int(t * 0.8), int(t * 0.2)))
        # Antifaz: no es quien dice ser.
        antifaz = pygame.Rect(0, 0, int(t * 0.42), max(3, int(t * 0.1)))
        antifaz.center = (cx, cy - int(t * 0.16))
        pygame.draw.rect(screen, oscuro, antifaz, border_radius=3)
    elif nombre == "tutorial":
        alto = int(t * 0.56)
        for lado in (-1, 1):
            hoja = [(cx, cy - alto // 2 + 4), (cx + lado * int(t * 0.42), cy - alto // 2),
                    (cx + lado * int(t * 0.42), cy + alto // 2), (cx, cy + alto // 2 + 4)]
            pygame.draw.polygon(screen, color, hoja)
            for k in range(3):
                y = cy - alto // 2 + 8 + k * alto // 4
                pygame.draw.line(screen, oscuro, (cx + lado * int(t * 0.08), y + 1),
                                 (cx + lado * int(t * 0.34), y), max(1, g // 2))
    elif nombre == "cambiaformas":
        r = int(t * 0.4)
        cara = pygame.Rect(0, 0, r * 2, int(r * 2.2))
        cara.center = (cx, cy)
        mitad = pygame.Surface(cara.size, pygame.SRCALPHA)
        pygame.draw.ellipse(mitad, (232, 196, 160), mitad.get_rect())
        pygame.draw.rect(mitad, (0, 0, 0, 0), (cara.width // 2, 0, cara.width, cara.height))
        verde = pygame.Surface(cara.size, pygame.SRCALPHA)
        pygame.draw.ellipse(verde, (110, 200, 130), verde.get_rect())
        pygame.draw.rect(verde, (0, 0, 0, 0), (0, 0, cara.width // 2, cara.height))
        screen.blit(mitad, cara.topleft)
        screen.blit(verde, cara.topleft)
        pygame.draw.ellipse(screen, color, cara, g)
        pygame.draw.line(screen, color, (cx, cara.y + 2), (cx, cara.bottom - 2), max(1, g // 2))
        pygame.draw.circle(screen, (40, 30, 30), (cx - int(r * 0.42), cy - int(r * 0.15)), max(2, r // 6))
        ojo = pygame.Rect(0, 0, int(r * 0.6), int(r * 0.36))
        ojo.center = (cx + int(r * 0.42), cy - int(r * 0.15))
        pygame.draw.ellipse(screen, (20, 20, 20), ojo)
        pygame.draw.ellipse(screen, (255, 220, 80), ojo.inflate(-ojo.width // 2, -2))
        pygame.draw.arc(screen, (60, 40, 40), (cx - int(r * 0.7), cy + int(r * 0.2), int(r * 0.6), int(r * 0.5)),
                        math.pi * 1.1, math.pi * 1.9, max(1, g // 2))
        pygame.draw.line(screen, (30, 70, 40), (cx + int(r * 0.15), cy + int(r * 0.5)),
                         (cx + int(r * 0.7), cy + int(r * 0.42)), max(1, g // 2))
    elif nombre == "salir":
        puerta = pygame.Rect(0, 0, int(t * 0.42), int(t * 0.7))
        puerta.midright = (cx + int(t * 0.1), cy)
        pygame.draw.rect(screen, color, puerta, g)
        pygame.draw.line(screen, color, (cx - int(t * 0.05), cy), (cx + int(t * 0.42), cy), g)
        pygame.draw.polygon(screen, color, [(cx + int(t * 0.46), cy), (cx + int(t * 0.3), cy - int(t * 0.14)),
                                            (cx + int(t * 0.3), cy + int(t * 0.14))])
    else:
        pygame.draw.circle(screen, color, (cx, cy), int(t * 0.38), g)
        f = fuente_de_tamano(max(9, int(t * 0.5)))
        img = f.render("i", True, color)
        screen.blit(img, img.get_rect(center=(cx, cy)))


def render_mosaico(screen, vista, jugador):
    """La Terminal NEXUS como mosaico: la confianza arriba, el caso del
    Cambiaformas resaltado a lo ancho, los temas en mosaicos con su icono y
    Salir abajo. Las filas vienen del panel (`filas`), que es lo mismo que usa
    el cursor para moverse (app.mover_en_mosaico)."""
    panel = jugador.panel
    opciones = panel.get("opciones", [])
    filas = panel.get("filas") or [[i] for i in range(len(opciones))]
    tiempo = pygame.time.get_ticks()
    ancho = min(int(vista.width * 0.94), 800)
    alto = min(vista.height - 24, int(ancho * 0.86))
    caja = pygame.Rect(0, 0, ancho, alto)
    caja.center = vista.center
    m = max(10, ancho // 40)
    fondo = pygame.Surface(caja.size, pygame.SRCALPHA)
    fondo.fill((18, 19, 36, 244))
    screen.blit(fondo, caja.topleft)
    pygame.draw.rect(screen, COLOR_NEXUS, caja, 3, border_radius=10)
    clip_previo = screen.get_clip()
    screen.set_clip(caja)

    # Encabezado: el logo de la red y el título.
    f_tit = fuente_de_tamano(max(13, min(24, ancho // 30)))
    f_peq = fuente_de_tamano(max(10, min(15, ancho // 52)))
    y = caja.y + m
    logo = (caja.x + m + 10, y + f_tit.get_linesize() // 2)
    for dx, dy in ((-7, 5), (7, 5), (0, -7)):
        pygame.draw.line(screen, COLOR_NEXUS, logo, (logo[0] + dx, logo[1] + dy), 2)
        pygame.draw.circle(screen, COLOR_NEXUS, (logo[0] + dx, logo[1] + dy), 3)
    pygame.draw.circle(screen, (255, 255, 255), logo, 3)
    screen.blit(f_tit.render(panel.get("titulo", "NEXUS"), True, COLOR_TEXTO), (caja.x + m + 26, y))
    y += f_tit.get_linesize() + 6

    # La barra de confianza (verde: en ustedes; roja: en los aliens).
    confianza = panel.get("confianza")
    if confianza is not None:
        verde, rojo, umbral = confianza
        barra = pygame.Rect(caja.x + m, y, ancho - 2 * m, max(8, ancho // 70))
        pygame.draw.rect(screen, (60, 62, 84), barra, border_radius=4)
        if verde > 0:
            pygame.draw.rect(screen, (96, 200, 120), (barra.x, barra.y, int(barra.width * verde), barra.height),
                             border_radius=4)
        if rojo > 0:
            w = int(barra.width * rojo)
            pygame.draw.rect(screen, (236, 80, 70), (barra.right - w, barra.y, w, barra.height), border_radius=4)
        x_umbral = barra.x + int(barra.width * umbral)
        pygame.draw.line(screen, (255, 255, 255), (x_umbral, barra.y - 3), (x_umbral, barra.bottom + 3), 2)
        y = barra.bottom + 3
        izq = f_peq.render(f"Confían en ustedes: {int(verde * 100)}%", True, (120, 220, 140))
        der = f_peq.render(f"En los aliens: {int(rojo * 100)}%", True, (245, 130, 120))
        screen.blit(izq, (barra.x, y))
        screen.blit(der, (barra.right - der.get_width(), y))
        planos = f_peq.render(f"planos al {int(umbral * 100)}%", True, COLOR_TENUE)
        if x_umbral - planos.get_width() // 2 > barra.x + izq.get_width() + 8 and \
                x_umbral + planos.get_width() // 2 < barra.right - der.get_width() - 8:
            screen.blit(planos, (x_umbral - planos.get_width() // 2, y))
        y += f_peq.get_linesize() + 2
    for parrafo in panel.get("cuerpo", []):
        for linea in partir_lineas(parrafo, f_peq, ancho - 2 * m)[:2]:
            screen.blit(f_peq.render(linea, True, COLOR_TENUE), (caja.x + m, y))
            y += f_peq.get_linesize()
    y += 6

    # Los mosaicos.
    pie = panel.get("pie")
    alto_pie = f_peq.get_linesize() + 8 if pie else 0
    disponible = caja.bottom - m - alto_pie - y
    pesos = []
    for fila in filas:
        if any(opciones[i].get("destacada") for i in fila):
            pesos.append(1.25)
        elif all(opciones[i].get("icono") == "salir" for i in fila):
            pesos.append(0.5)
        else:
            pesos.append(1.0)
    hueco = max(6, m // 2)
    unidad = (disponible - hueco * (len(filas) - 1)) / max(0.1, sum(pesos))
    for fila, peso in zip(filas, pesos):
        alto_fila = int(unidad * peso)
        ancho_mosaico = (ancho - 2 * m - hueco * (len(fila) - 1)) / len(fila)
        for k, i in enumerate(fila):
            opcion = opciones[i]
            rect = pygame.Rect(int(caja.x + m + k * (ancho_mosaico + hueco)), int(y), int(ancho_mosaico), alto_fila)
            _dibujar_mosaico(screen, rect, opcion, i == jugador.cursor, tiempo)
        y += alto_fila + hueco

    if pie:
        img = render_texto_mando(f_peq, pie, COLOR_TENUE)
        screen.blit(img, (caja.centerx - img.get_width() // 2, caja.bottom - m - img.get_height()))
    screen.set_clip(clip_previo)


def _dibujar_mosaico(screen, rect, opcion, elegido, tiempo):
    icono = opcion.get("icono", "info")
    destacada = opcion.get("destacada", False)
    radio = max(6, rect.height // 8)
    if destacada:
        # El caso del Cambiaformas: fondo magenta y un borde que late.
        latido = 0.5 + 0.5 * math.sin(tiempo / 330)
        pygame.draw.rect(screen, (70, 28, 76) if not elegido else (96, 40, 104), rect, border_radius=radio)
        brillo = tuple(int(c * (0.65 + 0.35 * latido)) for c in COLOR_CASO)
        pygame.draw.rect(screen, COLOR_SELECCION if elegido else brillo, rect, 3, border_radius=radio)
        if elegido:
            pygame.draw.rect(screen, COLOR_CASO, rect.inflate(6, 6), 2, border_radius=radio + 3)
        tam = min(rect.height * 0.78, rect.width * 0.2)
        icono_nexus(screen, icono, (rect.x + 10 + tam / 2 + 4, rect.centery), tam, COLOR_CASO)
        x = int(rect.x + 22 + tam)
        ancho_texto = rect.right - x - 12
        f, lineas = _ajustar(opcion["texto"], ancho_texto, rect.height * 0.5, max(12, min(26, rect.height // 3)), 2)
        f_det = fuente_de_tamano(max(10, f.get_height() * 2 // 3))
        etiqueta = f_det.render("IMPORTANTE", True, (255, 255, 255))
        insignia = etiqueta.get_rect().inflate(10, 4)
        insignia.topright = (rect.right - 10, rect.y + 8)
        alto_texto = len(lineas) * f.get_linesize() + (f_det.get_linesize() if opcion.get("detalle") else 0)
        ty = rect.centery - alto_texto // 2
        for linea in lineas:
            screen.blit(f.render(linea, True, COLOR_SELECCION if elegido else COLOR_TEXTO), (x, ty))
            ty += f.get_linesize()
        if opcion.get("detalle"):
            screen.blit(f_det.render(opcion["detalle"], True, (250, 190, 235)), (x, ty))
        if insignia.left > x + f.size(lineas[0])[0] + 8 or insignia.bottom < rect.centery - alto_texto // 2:
            pygame.draw.rect(screen, COLOR_CASO, insignia, border_radius=4)
            screen.blit(etiqueta, etiqueta.get_rect(center=insignia.center))
        return
    salir = icono == "salir"
    pygame.draw.rect(screen, COLOR_MOSAICO_SEL if elegido else (COLOR_MOSAICO if not salir else (26, 28, 46)),
                     rect, border_radius=radio)
    pygame.draw.rect(screen, COLOR_SELECCION if elegido else (78, 84, 130), rect, 3 if elegido else 1,
                     border_radius=radio)
    color = COLOR_SELECCION if elegido else (COLOR_TENUE if salir else COLOR_NEXUS)
    if salir or rect.height < 70:
        # Bajito: el icono a la izquierda y el texto al lado.
        tam = rect.height * 0.62
        f, lineas = _ajustar(opcion["texto"], rect.width - tam - 30, rect.height - 6,
                             max(11, min(20, rect.height // 2)), 2)
        alto_texto = len(lineas) * f.get_linesize()
        total = tam + 10 + max(f.size(l)[0] for l in lineas)
        x0 = rect.centerx - total / 2
        icono_nexus(screen, icono, (x0 + tam / 2, rect.centery), tam, color)
        ty = rect.centery - alto_texto // 2
        for linea in lineas:
            screen.blit(f.render(linea, True, COLOR_SELECCION if elegido else COLOR_TEXTO), (x0 + tam + 10, ty))
            ty += f.get_linesize()
        return
    # Alto: el icono arriba en un círculo y el texto abajo, centrado.
    tam = min(rect.height * 0.42, rect.width * 0.42)
    centro_icono = (rect.centerx, rect.y + 8 + tam * 0.62)
    pygame.draw.circle(screen, (24, 26, 48), (int(centro_icono[0]), int(centro_icono[1])), int(tam * 0.62))
    icono_nexus(screen, icono, centro_icono, tam * 0.9, color)
    arriba = int(centro_icono[1] + tam * 0.62 + 4)
    f, lineas = _ajustar(opcion["texto"], rect.width - 14, rect.bottom - arriba - 4,
                         max(11, min(19, rect.width // 11)), 3)
    _texto_centrado(screen, lineas, f, rect.centerx, arriba, COLOR_SELECCION if elegido else COLOR_TEXTO)


COLOR_SALA = (150, 205, 255)


def _icono_lugar(screen, centro, tam, color):
    """Un pin de mapa chiquito, dibujado con formas."""
    cx, cy = centro
    r = max(3, tam // 3)
    pygame.draw.polygon(screen, color, [(cx - r, cy - r // 2), (cx + r, cy - r // 2), (cx, cy + r + 2)])
    pygame.draw.circle(screen, color, (cx, cy - r // 2), r)
    pygame.draw.circle(screen, (14, 15, 28), (cx, cy - r // 2), max(1, r // 2))


# -- Franja de arriba de cada vista ----------------------------------------------------
#
# Antes eran tres líneas sobre una franja sólida (rol · controles, objetivo y
# la habilidad) y debajo otra fila con los corazones: con 3 o 4 jugadores se
# comía la quinta parte de cada vista. Ahora es UNA línea sobre un degradado
# (rol · habilidad a la izquierda, sala y puntos a la derecha); el objetivo
# sale debajo solo un rato cada vez que cambia, las vidas se fueron abajo con
# el pulso y los controles ya los dice el tutorial.

OBJETIVO_VISIBLE_MS = 7000      # cuánto se ve el objetivo cada vez que cambia
COLOR_OBJETIVO = (214, 220, 248)
COLOR_SOMBRA_TEXTO = (6, 6, 14)
_cache_degradado = {}


def objetivo_visible(jugador):
    """¿Va la línea del objetivo? Sale cada vez que cambia (al empezar, al
    pasar de fase, con cada consola apagada...) y se esconde a los
    OBJETIVO_VISIBLE_MS: la flecha y la pista de abajo ya dicen qué hacer."""
    objetivo = getattr(jugador, "objetivo", "") or ""
    ahora = pygame.time.get_ticks()
    if getattr(jugador, "_hud_objetivo", None) != objetivo:
        jugador._hud_objetivo = objetivo
        jugador._hud_objetivo_ms = ahora
    return bool(objetivo) and ahora - jugador._hud_objetivo_ms < OBJETIVO_VISIBLE_MS


def alto_hud(vista, jugador=None):
    """La y de pantalla donde termina la franja de arriba de la vista (una
    línea, dos mientras se ve el objetivo). Lo que va "debajo del HUD"
    (mensajes, "Te sigue", el celular, el minimapa) se mide desde aquí."""
    f = _fuente_para(vista)
    lineas = 2 if jugador is not None and objetivo_visible(jugador) else 1
    return vista.y + f.get_linesize() * lineas + 10


def _degradado(ancho, alto):
    """Fondo de la franja: oscuro arriba y transparente hacia abajo, así no
    queda una banda sólida tapando el mapa."""
    clave = (ancho, alto)
    if clave not in _cache_degradado:
        if len(_cache_degradado) > 24:
            _cache_degradado.clear()
        capa = pygame.Surface((max(1, ancho), max(1, alto)), pygame.SRCALPHA)
        solido = alto * 0.5
        for y in range(alto):
            a = 185 if y < solido else int(185 * (1 - (y - solido) / max(1, alto - solido)) ** 1.5)
            pygame.draw.line(capa, (12, 13, 26, a), (0, y), (ancho, y))
        _cache_degradado[clave] = capa
    return _cache_degradado[clave]


# -- Botones de PlayStation -----------------------------------------------------
# La tipografía no trae ✕ ○ □ △ (pruebas/prueba_textos.py): en las pistas el
# texto dice "[Cruz]", "[Círculo]"... y aquí se cambia por el dibujo, con los
# colores de siempre de esos botones.
COLOR_SIMBOLO_PS = {"Cruz": (124, 170, 255), "Círculo": (244, 96, 96),
                    "Cuadrado": (232, 128, 206), "Triángulo": (72, 214, 170)}
_PATRON_PS = re.compile(r"\[(Cruz|Círculo|Cuadrado|Triángulo)\]")


def dibujar_simbolo_ps(screen, nombre, centro, tam, color=None):
    """El símbolo del botón `nombre` ("Cruz", "Círculo"...) en un cuadro de `tam`."""
    color = color or COLOR_SIMBOLO_PS[nombre]
    cx, cy = centro
    r = tam // 2
    grosor = max(2, tam // 7)
    if nombre == "Cruz":
        pygame.draw.line(screen, color, (cx - r, cy - r), (cx + r, cy + r), grosor)
        pygame.draw.line(screen, color, (cx - r, cy + r), (cx + r, cy - r), grosor)
    elif nombre == "Círculo":
        pygame.draw.circle(screen, color, (cx, cy), r, grosor)
    elif nombre == "Cuadrado":
        pygame.draw.rect(screen, color, (cx - r, cy - r, 2 * r, 2 * r), grosor)
    elif nombre == "Triángulo":
        alto = int(r * 1.8)
        puntos = [(cx, cy - alto // 2 - 1), (cx + r, cy + alto // 2), (cx - r, cy + alto // 2)]
        pygame.draw.polygon(screen, color, puntos, grosor)


def render_texto_mando(f, texto, color):
    """Como f.render(texto, True, color), pero "[Cruz]", "[Círculo]",
    "[Cuadrado]" y "[Triángulo]" salen con su símbolo dibujado. Nunca queda
    más ancho que el texto escrito, así que no descuadra nada."""
    partes = _PATRON_PS.split(texto)
    if len(partes) == 1:
        return f.render(texto, True, color)
    tam = max(8, int(f.get_ascent() * 0.62))
    piezas = []          # (imagen o None, nombre del símbolo)
    for i, parte in enumerate(partes):
        if i % 2:
            piezas += [(f.render("[", True, color), None), (None, parte),
                       (f.render("]", True, color), None)]
        elif parte:
            piezas.append((f.render(parte, True, color), None))
    ancho = sum(img.get_width() if img else tam + 4 for img, _ in piezas)
    salida = pygame.Surface((ancho, f.get_height()), pygame.SRCALPHA)
    x = 0
    for img, nombre in piezas:
        if img is not None:
            salida.blit(img, (x, 0))
            x += img.get_width()
        else:
            dibujar_simbolo_ps(salida, nombre, (x + 2 + tam // 2, f.get_ascent() - int(f.get_ascent() * 0.38)), tam)
            x += tam + 4
    return salida


def _con_sombra(screen, f, texto, color, pos, alfa=None):
    """Texto con una sombrita de 1 px: sin franja sólida detrás, así se lee
    encima del piso claro de la nave. Devuelve el ancho."""
    sombra = f.render(texto, True, COLOR_SOMBRA_TEXTO)
    img = f.render(texto, True, color)
    if alfa is not None:
        sombra.set_alpha(alfa)
        img.set_alpha(alfa)
    screen.blit(sombra, (pos[0] + 1, pos[1] + 1))
    screen.blit(img, pos)
    return img.get_width()


def _recortar(f, texto, ancho):
    """`texto` cortado con "..." para que quepa en `ancho` ("" si ni eso)."""
    if f.size(texto)[0] <= ancho:
        return texto
    while texto and f.size(texto + "...")[0] > ancho:
        texto = texto[:-1]
    return (texto.rstrip() + "...") if texto else ""


def _hueco_fila(vista, y, alto, tapado):
    """(izquierda, derecha) libres de una fila de la vista, sin lo que tapa
    la barra de confianza (que va arriba al centro, sobre el corte)."""
    izq, der = vista.x + 12, vista.right - 12
    if tapado is not None and tapado.colliderect(pygame.Rect(vista.x, y, vista.width, alto)):
        if tapado.centerx < vista.centerx:
            izq = max(izq, tapado.right + 12)
        else:
            der = min(der, tapado.left - 12)
    return izq, der


def render_hud(screen, vista, jugador, segundos_restantes=None, tapado=None):
    """La franja de arriba: rol y su habilidad, la sala (o el reloj) y los
    puntos; y un rato el objetivo, cuando cambia."""
    f = _fuente_para(vista)
    paso = f.get_linesize()
    ver_objetivo = objetivo_visible(jugador)
    abajo = alto_hud(vista, jugador)
    screen.blit(_degradado(vista.width, abajo - vista.y + 18), vista.topleft)

    y = vista.y + 5
    izq, der = _hueco_fila(vista, y, paso, tapado)

    # Derecha: puntos y, a su izquierda, la sala donde está (o el reloj).
    x = der - f.size(f"{jugador.puntos} pts")[0]
    _con_sombra(screen, f, f"{jugador.puntos} pts", COLOR_TITULO, (x, y))
    if segundos_restantes is not None:
        reloj = _formato_reloj(segundos_restantes)
        x -= f.size(reloj)[0] + 20
        _con_sombra(screen, f, reloj, COLOR_TEXTO, (x, y))
    elif getattr(jugador, "sala", None):
        nueva = getattr(jugador, "sala_cambio_ms", 0) > 0
        color = COLOR_TITULO if nueva else COLOR_SALA
        x -= f.size(jugador.sala)[0] + 20
        _con_sombra(screen, f, jugador.sala, color, (x, y))
        _icono_lugar(screen, (x - 11, y + paso // 2 - 1), paso - 4, color)
        x -= 22
    limite = x - 16

    # Izquierda: el rol y el estado de su habilidad (recarga, lista, escoger).
    xi = izq + _con_sombra(screen, f, jugador.rol or "", COLOR_TEXTO, (izq, y))
    if jugador.info:
        texto = _recortar(f, "  ·  " + jugador.info, limite - xi)
        if texto:
            xi += _con_sombra(screen, f, texto, COLOR_INFO, (xi, y))
    # Lo que queda libre en el medio (ahí va el aviso de NEXUS).
    jugador.hud_hueco = (xi + 18, limite)

    if ver_objetivo:
        y += paso
        izq2, der2 = _hueco_fila(vista, y, paso, tapado)
        texto = _recortar(f, jugador.objetivo, der2 - izq2)
        resta = OBJETIVO_VISIBLE_MS - (pygame.time.get_ticks() - jugador._hud_objetivo_ms)
        alfa = 255 if resta > 600 else max(0, int(255 * resta / 600))
        _con_sombra(screen, f, texto, COLOR_OBJETIVO, (izq2, y), alfa)


def _formato_reloj(segundos):
    segundos = max(0, int(segundos))
    return f"{segundos // 60}:{segundos % 60:02d}"


def fila_bajo_hud(vista, jugador):
    """La fila justo debajo de la franja de arriba: ahí van "Te sigue...",
    "Verificando..." (partida.render_escolta) y los mensajes."""
    f = _fuente_para(vista)
    return pygame.Rect(vista.x + 8, alto_hud(vista, jugador) + 2, vista.width - 16, f.get_height() + 8)


def _tramos_libres(desde, hasta, ocupados):
    """Los pedazos de [desde, hasta] que no tocan ningún (inicio, fin) ocupado."""
    tramos = [(desde, hasta)]
    for a, z in ocupados:
        nuevos = []
        for t0, t1 in tramos:
            if z <= t0 or a >= t1:
                nuevos.append((t0, t1))
                continue
            if a > t0:
                nuevos.append((t0, a))
            if z < t1:
                nuevos.append((z, t1))
        tramos = nuevos
    return tramos


def render_mensaje(screen, vista, jugador, tapado=None):
    """Mensajito flotante de feedback, debajo de la franja de arriba (y de lo
    que dice render_escolta, si hay algo)."""
    if not jugador.mensaje:
        return
    f = _fuente_para(vista)
    fila = fila_bajo_hud(vista, jugador)
    if getattr(jugador, "hud_abajo", 0):
        fila.y = jugador.hud_abajo + 4
    # Ni debajo de la barra de confianza ni del cartel de la IA, que va
    # justo debajo de ella (más ancho), ni detrás del celular.
    ocupados = []
    if tapado is not None:
        # La columna de lo global (barra, aviso del evento y cartel de la IA,
        # celular.columna_avisos), que es más ancha que la barra.
        mitad = int(min(580, max(320, tapado.centerx * 2 * 0.32))) // 2
        ocupados.append((min(tapado.left, tapado.centerx - mitad) - 10,
                         max(tapado.right, tapado.centerx + mitad) + 10))
    if jugador.panel is not None and jugador.panel.get("tipo") == "celular":
        from screens.celular import _marco                       # ni detrás del celular
        telefono, _ = _marco(vista, tapado, jugador)
        ocupados.append((telefono.left - 12, telefono.right + 12))
    t0, t1 = max(_tramos_libres(fila.left, fila.right, ocupados),
                 key=lambda t: t[1] - t[0], default=(fila.left, fila.right))
    disponible = t1 - t0 - 20
    minimo = max(12, f.get_height() - 4)
    for px in range(f.get_height(), minimo - 1, -1):
        etiqueta = fuente_de_tamano(px).render(jugador.mensaje, True, jugador.mensaje_color)
        if etiqueta.get_width() <= disponible:
            caja = etiqueta.get_rect(centerx=(t0 + t1) // 2, top=fila.y + 4)
            _caja_mensaje(screen, [etiqueta], caja)
            return
    # No cabe en una línea: en renglones, en ese mismo pedazo.
    renglones = partir_lineas(jugador.mensaje, f, max(80, disponible))
    imgs = [f.render(r, True, jugador.mensaje_color) for r in renglones]
    caja = pygame.Rect(0, 0, max(i.get_width() for i in imgs), len(imgs) * f.get_linesize())
    caja.midtop = ((t0 + t1) // 2, fila.y + 4)
    _caja_mensaje(screen, imgs, caja)


def _caja_mensaje(screen, imgs, caja):
    fondo = pygame.Surface((caja.width + 20, caja.height + 10), pygame.SRCALPHA)
    fondo.fill((14, 15, 28, 215))
    screen.blit(fondo, (caja.x - 10, caja.y - 5))
    paso = caja.height // max(1, len(imgs))
    for k, img in enumerate(imgs):
        screen.blit(img, img.get_rect(midtop=(caja.centerx, caja.y + k * paso)))


def tope_abajo(vista, jugador):
    """Hasta dónde puede bajar lo que va abajo al centro (la pista y la barra
    de progreso): el borde de arriba del tutorial si está en esta vista (lo
    anotó partida.render_tutorial en el cuadro anterior), o el de la vista."""
    anotado = getattr(jugador, "hud_tutorial", None)
    if anotado is not None and anotado[0] == tuple(vista):
        return anotado[1]
    return vista.bottom


def render_pista_zona(screen, vista, jugador):
    """Aviso de 'presiona X para ...' sobre una zona, un escondite o adentro."""
    if jugador.ocupado or getattr(jugador, "minijuego", None) is not None:
        return
    tecla = jugador.nombre_tecla('interactuar')
    if getattr(jugador, "preso", None) is not None:
        texto = "Encerrado: espera a que te saquen"
    elif getattr(jugador, "escondido", False):
        texto = f"[{tecla}] Salir del escondite"
    elif getattr(jugador, "pista_mision", None):
        texto = f"[{tecla}] {jugador.pista_mision}"
    elif jugador.zona_cerca is not None:
        texto = f"[{tecla}] {jugador.zona_cerca['nombre']}"
    elif getattr(jugador, "estacion_cerca", None) is not None:
        estacion = jugador.estacion_cerca
        accion = "Usar terminal" if estacion["tipo"] == "terminal" else "Reparar panel"
        texto = f"[{tecla}] {accion}"
    elif getattr(jugador, "escondite_cerca", None) is not None:
        texto = f"[{tecla}] Esconderse"
    else:
        return
    f = _fuente_para(vista)
    etiqueta = render_texto_mando(f, texto, COLOR_TITULO)
    caja = etiqueta.get_rect()
    caja.centerx = vista.centerx
    # Bien arriba del borde: abajo a la izquierda va el pulso y abajo al
    # centro, mientras dura, el tutorial (render_tutorial anota su borde).
    caja.bottom = min(vista.bottom - 96, tope_abajo(vista, jugador) - 12)

    fondo = pygame.Surface((caja.width + 24, caja.height + 12), pygame.SRCALPHA)
    fondo.fill((14, 15, 28, 225))
    screen.blit(fondo, (caja.x - 12, caja.y - 6))
    pygame.draw.rect(screen, COLOR_BORDE, (caja.x - 12, caja.y - 6,
                                           caja.width + 24, caja.height + 12), 2)
    screen.blit(etiqueta, caja.topleft)


# -- Pulso ----------------------------------------------------------------------

COLOR_PULSO_CALMA = (96, 200, 120)
COLOR_PULSO_ALERTA = (255, 196, 64)
COLOR_PULSO_PANICO = (236, 70, 60)

# El borde rojo del viewport se cachea por tamaño: armarlo cuesta, y el
# tamaño del viewport solo cambia al alternar F11.
_cache_vineta = {}


def _color_pulso(pulso):
    if pulso < 45:
        return COLOR_PULSO_CALMA
    if pulso < 72:
        return COLOR_PULSO_ALERTA
    return COLOR_PULSO_PANICO


def _intensidad_latido(fase):
    """Qué tan "lleno" está el corazón en esta fase del latido (0 a 1).

    Un latido real son dos golpes seguidos (pum-pum) y una pausa; esto lo
    imita con dos picos al principio de cada ciclo.
    """
    if fase < 0.12:
        return 1 - abs(fase - 0.06) / 0.06
    if 0.18 < fase < 0.28:
        return 0.6 * (1 - abs(fase - 0.23) / 0.05)
    return 0.0


def _dibujar_corazon(screen, centro, tamano, color):
    cx, cy = centro
    r = max(3, int(tamano * 0.3))
    pygame.draw.circle(screen, color, (int(cx - r * 0.85), int(cy - r * 0.3)), r)
    pygame.draw.circle(screen, color, (int(cx + r * 0.85), int(cy - r * 0.3)), r)
    pygame.draw.polygon(screen, color, [
        (cx - r * 1.8, cy - r * 0.05),
        (cx + r * 1.8, cy - r * 0.05),
        (cx, cy + r * 1.9),
    ])


def _tam_corazon_vida(vista):
    return max(14, min(20, vista.width // 48))


def _ancho_vidas(vista, jugador):
    """Lo que ocupan los corazones de las vidas dentro del recuadro del pulso."""
    from entidades.jugador import VIDAS_INICIALES
    if jugador is None or getattr(jugador, "vidas", None) is None:
        return 0
    tam = _tam_corazon_vida(vista)
    if getattr(jugador, "vidas_infinitas", False):
        return tam + 6 + ancho_infinito(tam)
    return getattr(jugador, "vidas_max", VIDAS_INICIALES) * (tam + 5)


def _medidas_pulso(screen, vista, jugador=None):
    """El recuadro de abajo a la izquierda: corazón que late, lpm y, en la
    misma línea, las vidas; debajo la barra del pulso. (Antes las vidas
    tenían su propia fila arriba, debajo del HUD.)"""
    f = _fuente_para(vista)
    ancho_barra = max(110, min(200, vista.width // 5))
    alto_barra = max(8, f.get_linesize() // 2 - 2)
    x = vista.x + 16
    base = vista.bottom - 14
    ancho = max(ancho_barra + 56, 40 + f.size("100 lpm")[0] + 16 + _ancho_vidas(vista, jugador) + 10)
    fondo = pygame.Rect(x - 8, base - alto_barra - f.get_linesize() - 16,
                        ancho, alto_barra + f.get_linesize() + 24)
    return f, ancho_barra, alto_barra, x, base, fondo


def rect_pulso(screen, vista, jugador=None):
    """Dónde va el recuadro del pulso (para poner cosas justo encima: el mapa
    del Tecnomante, roles.render_minimapa, y el tutorial)."""
    return _medidas_pulso(screen, vista, jugador)[5]


def render_pulso(screen, vista, jugador):
    """Corazón que late al ritmo del pulso, los lpm, las vidas y la barra,
    abajo a la izquierda."""
    color = _color_pulso(jugador.pulso)
    golpe = _intensidad_latido(jugador.fase_latido)
    f, ancho_barra, alto_barra, x, base, fondo = _medidas_pulso(screen, vista, jugador)
    capa = pygame.Surface(fondo.size, pygame.SRCALPHA)
    capa.fill((14, 15, 28, 190))
    screen.blit(capa, fondo.topleft)

    tamano = 26 + golpe * 8
    _dibujar_corazon(screen, (x + 16, fondo.centery), tamano, color)

    texto = f.render(f"{jugador.latidos_por_minuto} lpm", True, COLOR_TEXTO)
    screen.blit(texto, (x + 40, fondo.y + 6))

    barra = pygame.Rect(x + 40, base - alto_barra - 2, ancho_barra, alto_barra)
    pygame.draw.rect(screen, (40, 42, 64), barra)
    lleno = barra.copy()
    lleno.width = int(barra.width * jugador.pulso / 100)
    pygame.draw.rect(screen, color, lleno)
    pygame.draw.rect(screen, COLOR_BORDE, barra, 1)

    # Las vidas, a la derecha de los lpm.
    ancho_vidas = _ancho_vidas(vista, jugador)
    if ancho_vidas:
        _dibujar_vidas(screen, vista, jugador,
                       (fondo.right - 10 - ancho_vidas, fondo.y + 6 + f.get_linesize() // 2))

    if jugador.visto:
        aviso = f.render("¡TE VEN!", True, COLOR_PULSO_PANICO)
        caja = aviso.get_rect(bottomleft=(fondo.x + 6, fondo.y - 6))
        tapa = pygame.Surface(caja.inflate(12, 6).size, pygame.SRCALPHA)
        tapa.fill((14, 15, 28, 205))
        screen.blit(tapa, caja.inflate(12, 6).topleft)
        screen.blit(aviso, caja.topleft)


def _vineta(tamano):
    """Borde rojo que se desvanece hacia el centro, para un viewport."""
    if tamano not in _cache_vineta:
        ancho, alto = tamano
        capa = pygame.Surface(tamano, pygame.SRCALPHA)
        grosor = max(24, min(ancho, alto) // 6)
        for i in range(grosor):
            alfa = int(170 * (1 - i / grosor) ** 2)
            pygame.draw.rect(capa, (200, 20, 30, alfa), (i, i, ancho - 2 * i, alto - 2 * i), 1)
        # Solo los bordes: el centro es transparente y mezclarlo cada cuadro
        # era lo más caro del dibujo (una capa del tamaño de la vista).
        tiras = []
        for r in ((0, 0, ancho, grosor), (0, alto - grosor, ancho, grosor),
                  (0, grosor, grosor, alto - 2 * grosor),
                  (ancho - grosor, grosor, grosor, alto - 2 * grosor)):
            rect = pygame.Rect(r)
            if rect.width > 0 and rect.height > 0:
                tiras.append((capa.subsurface(rect).copy(), rect.topleft))
        _cache_vineta[tamano] = tiras
    return _cache_vineta[tamano]


def render_tension(screen, vista, jugador):
    """Bordes rojos que laten cuando el pulso está alto."""
    if jugador.pulso < 55:
        return
    fuerza = (jugador.pulso - 55) / 45
    golpe = _intensidad_latido(jugador.fase_latido)
    alfa = int(255 * min(1.0, fuerza * (0.55 + 0.45 * golpe)))
    if alfa <= 0:
        return
    tiras = _vineta_nivel(vista.size, alfa)
    if tiras is not None:
        for tira, (dx, dy) in tiras:
            screen.blit(tira, (vista.x + dx, vista.y + dy), special_flags=pygame.BLEND_PREMULTIPLIED)
        return
    for tira, (dx, dy) in _vineta(vista.size):
        tira.set_alpha(alfa)
        screen.blit(tira, (vista.x + dx, vista.y + dy))


NIVELES_VINETA = 12
_cache_vineta_niveles = {}


def _vineta_nivel(tamano, alfa):
    """La viñeta ya mezclada con un nivel de `alfa` (12 niveles) y con el
    alfa premultiplicado: así se pega con el mezclador rápido de pygame. Antes
    se le ponía `set_alpha` a las tiras cada cuadro, y ese mezclado (alfa por
    pixel por alfa de la superficie) era lo más lento del dibujo justo cuando
    hay tensión: con el pulso alto, ~1.6 ms por vista a 1080p (ahora la mitad).
    None si este pygame no tiene `premul_alpha` (se usa la forma de antes)."""
    if not hasattr(pygame.Surface, "premul_alpha"):
        return None
    nivel = max(1, min(NIVELES_VINETA, round(alfa / 255 * NIVELES_VINETA)))
    clave = (tuple(tamano), nivel)
    if clave not in _cache_vineta_niveles:
        if len(_cache_vineta_niveles) > 4 * NIVELES_VINETA:     # cambió el tamaño de las vistas
            _cache_vineta_niveles.clear()
        tiras = []
        for tira, posicion in _vineta(tamano):
            capa = tira.copy()
            capa.fill((255, 255, 255, int(255 * nivel / NIVELES_VINETA)), special_flags=pygame.BLEND_RGBA_MULT)
            tiras.append((capa.premul_alpha(), posicion))
        _cache_vineta_niveles[clave] = tiras
    return _cache_vineta_niveles[clave]


# -- Escondites y minijuego ---------------------------------------------------------

COLOR_AMENAZA = (236, 70, 60)
COLOR_ZONA_VERDE = (96, 200, 120)
_cache_escondido = {}


def render_escondido(screen, vista, jugador):
    """Adentro del escondite: todo oscuro salvo una rendija a la altura de los ojos."""
    if not getattr(jugador, "escondido", False):
        return
    if vista.size not in _cache_escondido:
        capa = pygame.Surface(vista.size, pygame.SRCALPHA)
        capa.fill((4, 5, 10, 205))
        alto_rendija = max(40, vista.height // 7)
        centro = vista.height // 2
        for i in range(alto_rendija):
            # La rendija se aclara hacia el centro.
            d = abs(i - alto_rendija / 2) / (alto_rendija / 2)
            alfa = int(205 * d ** 2)
            pygame.draw.line(capa, (4, 5, 10, alfa), (0, centro - alto_rendija // 2 + i),
                             (vista.width, centro - alto_rendija // 2 + i))
        _cache_escondido[vista.size] = capa
    screen.blit(_cache_escondido[vista.size], vista.topleft)


def render_minijuego(screen, vista, jugador):
    """La barra de timing y, al lado, la de cuánto le falta al alien para entrar."""
    juego = getattr(jugador, "minijuego", None)
    if juego is None:
        return
    f = _fuente_para(vista)
    ancho = max(260, min(480, vista.width - 60))
    alto = f.get_linesize() * 3 + 74
    panel = pygame.Rect(0, 0, ancho, alto)
    panel.centerx = vista.centerx
    panel.bottom = vista.bottom - 96

    capa = pygame.Surface(panel.size, pygame.SRCALPHA)
    capa.fill(COLOR_FONDO)
    screen.blit(capa, panel.topleft)
    borde = COLOR_BORDE
    if juego.destello_ms > 0:
        borde = COLOR_ZONA_VERDE if juego.destello == "acierto" else COLOR_AMENAZA
    pygame.draw.rect(screen, borde, panel, 3 if juego.destello_ms > 0 else 2)

    titulo = f.render("¡Un alien revisa tu escondite!", True, COLOR_AMENAZA)
    screen.blit(titulo, (panel.x + 14, panel.y + 10))
    tecla = jugador.nombre_tecla("interactuar")
    pista = render_texto_mando(f, f"[{tecla}] cuando la aguja esté en verde", COLOR_TEXTO)
    screen.blit(pista, (panel.x + 14, panel.y + 10 + f.get_linesize()))

    # Barra de timing.
    ancho_lateral = 30
    barra = pygame.Rect(panel.x + 14, panel.y + 22 + f.get_linesize() * 2,
                        panel.width - 28 - ancho_lateral - 18, 26)
    pygame.draw.rect(screen, (40, 42, 64), barra)
    inicio, fin = juego.zona
    verde = pygame.Rect(barra.x + int(inicio * barra.width), barra.y,
                        max(2, int((fin - inicio) * barra.width)), barra.height)
    pygame.draw.rect(screen, COLOR_ZONA_VERDE, verde)
    pygame.draw.rect(screen, COLOR_BORDE, barra, 2)
    x_aguja = barra.x + int(juego.aguja * barra.width)
    pygame.draw.rect(screen, (250, 250, 255), (x_aguja - 3, barra.y - 6, 6, barra.height + 12))

    calma = f.render(f"{jugador.latidos_por_minuto} lpm", True, _color_pulso(jugador.pulso))
    screen.blit(calma, (barra.x, barra.bottom + 8))

    # Barra lateral: el alien está por entrar. Se llena de abajo hacia arriba.
    f_chica = fuente_de_tamano(max(10, f.get_height() - 5))
    etiqueta = f_chica.render("ALIEN", True, COLOR_AMENAZA)
    lateral = pygame.Rect(barra.right + 18, panel.y + 12, ancho_lateral,
                          panel.height - 30 - etiqueta.get_height())
    pygame.draw.rect(screen, (40, 42, 64), lateral)
    alto_lleno = int(lateral.height * juego.amenaza / 100)
    lleno = pygame.Rect(lateral.x, lateral.bottom - alto_lleno, lateral.width, alto_lleno)
    pygame.draw.rect(screen, COLOR_AMENAZA, lleno)
    pygame.draw.rect(screen, COLOR_BORDE, lateral, 2)
    screen.blit(etiqueta, (lateral.centerx - etiqueta.get_width() // 2, lateral.bottom + 6))


# -- Vidas -------------------------------------------------------------------------

COLOR_VIDA = (236, 64, 82)
COLOR_VIDA_VACIA = (60, 40, 52)


def dibujar_corazon(screen, centro, tam, lleno, color=COLOR_VIDA):
    """Un corazón de `tam` px de ancho: dos círculos y un triángulo."""
    cx, cy = centro
    r = max(2, tam // 4)
    relleno = color if lleno else COLOR_VIDA_VACIA
    for dx in (-r, r):
        pygame.draw.circle(screen, relleno, (cx + dx, cy - r // 2), r)
    pygame.draw.polygon(screen, relleno, [(cx - 2 * r, cy - r // 3), (cx + 2 * r, cy - r // 3),
                                          (cx, cy + int(r * 1.9))])
    borde = (255, 230, 235) if lleno else (120, 90, 100)
    # Contorno: los dos lóbulos y la punta.
    pygame.draw.arc(screen, borde, (cx - 2 * r, cy - r // 2 - r, 2 * r, 2 * r), 0.3, 3.4, 1)
    pygame.draw.arc(screen, borde, (cx, cy - r // 2 - r, 2 * r, 2 * r), -0.3, 2.85, 1)
    pygame.draw.line(screen, borde, (cx - 2 * r, cy - r // 3), (cx, cy + int(r * 1.9)), 1)
    pygame.draw.line(screen, borde, (cx + 2 * r, cy - r // 3), (cx, cy + int(r * 1.9)), 1)
    if lleno:
        pygame.draw.circle(screen, (255, 200, 210), (cx - r, cy - r), max(1, r // 3))


def render_vidas(screen, vista, jugador, tapado=None):
    """Las vidas ya no van solas: se dibujan dentro del recuadro del pulso
    (render_pulso). Se deja el nombre para quien la llame."""
    return


def _dibujar_vidas(screen, vista, jugador, inicio):
    """Los corazones de las vidas desde `inicio` (borde izquierdo, centro en
    y). El que se acaba de perder (o de recuperar) parpadea un momento."""
    from entidades.jugador import VIDAS_INICIALES
    vidas = getattr(jugador, "vidas", None)
    if vidas is None:
        return
    tam = _tam_corazon_vida(vista)
    x = inicio[0] + tam // 2
    y = inicio[1]
    parpadeo = getattr(jugador, "vida_cambio_ms", 0) > 0 and (pygame.time.get_ticks() // 120) % 2
    if getattr(jugador, "vidas_infinitas", False):
        # Fácil: no se pierden vidas. Un corazón (parpadea si te atrapan) y ∞.
        dibujar_corazon(screen, (x, y), tam, True, (255, 240, 240) if parpadeo else COLOR_VIDA)
        dibujar_infinito(screen, (x + tam // 2 + 6 + ancho_infinito(tam) // 2, y), tam,
                         (255, 230, 235))
        return
    for i in range(getattr(jugador, "vidas_max", VIDAS_INICIALES)):
        lleno = i < vidas
        if parpadeo and i == vidas:      # el que se acaba de perder
            dibujar_corazon(screen, (x + i * (tam + 5), y), tam, True, (255, 240, 240))
            continue
        dibujar_corazon(screen, (x + i * (tam + 5), y), tam, lleno)


def ancho_infinito(tam):
    return int(tam * 1.5)


def dibujar_infinito(screen, centro, tam, color, grosor=None):
    """El símbolo de infinito (la letra del juego no lo trae): una lemniscata de
    `ancho_infinito(tam)` px de ancho."""
    cx, cy = centro
    a = ancho_infinito(tam) / 2
    puntos = []
    for i in range(48):
        t = i * 2 * math.pi / 48
        d = 1 + math.sin(t) ** 2
        puntos.append((cx + a * math.cos(t) / d, cy + a * math.sin(t) * math.cos(t) / d * 1.3))
    pygame.draw.lines(screen, color, True, puntos, grosor or max(2, tam // 9))


_capas_eliminado = {}


def render_eliminado(screen, vista, jugador):
    """Si el jugador ya no tiene vidas, su mitad de la pantalla lo dice.

    La capa (velo y letreros) se arma una vez por tamaño de vista: antes era
    una superficie del tamaño de la vista, nueva, y tres textos por cuadro."""
    if not getattr(jugador, "eliminado", False):
        return
    veces = getattr(jugador, "vidas_max", 3)
    clave = (tuple(vista.size), veces)
    capa = _capas_eliminado.get(clave)
    if capa is None:
        if len(_capas_eliminado) > 8:
            _capas_eliminado.clear()
        capa = pygame.Surface(vista.size, pygame.SRCALPHA)
        capa.fill((20, 6, 10, 170))
        f = _fuente_para(vista)
        from juego.fuentes import fuente_de_tamano
        grande = fuente_de_tamano(max(24, min(48, vista.width // 14)))
        centro = (vista.width // 2, vista.height // 2)
        titulo = grande.render("ELIMINADO", True, COLOR_VIDA)
        capa.blit(titulo, titulo.get_rect(center=(centro[0], centro[1] - grande.get_linesize())))
        for i, (texto, color) in enumerate(((f"Te atraparon {veces} {'vez' if veces == 1 else 'veces'}.",
                                              COLOR_TEXTO),
                                             ("Tus compañeros siguen: ¡ánimo desde afuera!", COLOR_TENUE))):
            img = f.render(texto, True, color)
            capa.blit(img, img.get_rect(center=(centro[0], centro[1] + i * (f.get_linesize() + 6))))
        _capas_eliminado[clave] = capa
    screen.blit(capa, vista.topleft)


# -- Inventario ------------------------------------------------------------------------

def _icono_objeto(screen, tipo, centro, tam):
    """Dibujitos de los objetos: pieza (engranaje), decodificador (chip) y kit
    (llave inglesa)."""
    from screens.mision_dibujo import COLOR_CONSUMIBLE
    cx, cy = centro
    if tipo == "pieza":
        color = (255, 170, 50)
        for i in range(6):
            a = i * math.pi / 3
            pygame.draw.circle(screen, color, (int(cx + math.cos(a) * tam * 0.32),
                                               int(cy + math.sin(a) * tam * 0.32)), max(2, tam // 7))
        pygame.draw.circle(screen, color, (cx, cy), int(tam * 0.3))
        pygame.draw.circle(screen, (40, 30, 10), (cx, cy), max(2, tam // 8))
    elif tipo == "decodificador":
        # Un aparatito de mano: antena con luz, pantalla con código y botones.
        color = COLOR_CONSUMIBLE["decodificador"]
        t = max(14, tam)
        cuerpo = pygame.Rect(0, 0, int(t * 0.52), int(t * 0.74))
        cuerpo.center = (cx, cy + int(t * 0.06))
        antena = (cuerpo.right - int(t * 0.12), cuerpo.y)
        pygame.draw.line(screen, (150, 160, 190), antena, (antena[0] + int(t * 0.06), cuerpo.y - int(t * 0.2)), 2)
        luz = (255, 90, 90) if (pygame.time.get_ticks() // 400) % 2 else (120, 40, 40)
        pygame.draw.circle(screen, luz, (antena[0] + int(t * 0.06), cuerpo.y - int(t * 0.22)), max(2, t // 14))
        pygame.draw.rect(screen, (26, 34, 58), cuerpo, border_radius=max(3, t // 9))
        pygame.draw.rect(screen, color, cuerpo, 2, border_radius=max(3, t // 9))
        pantalla = pygame.Rect(0, 0, cuerpo.width - int(t * 0.14), int(t * 0.3))
        pantalla.midtop = (cx, cuerpo.y + int(t * 0.08))
        pygame.draw.rect(screen, (10, 40, 30), pantalla, border_radius=2)
        for k in range(3):     # líneas de "código" que corren
            largo = int(pantalla.width * (0.35 + 0.5 * ((k * 37 + pygame.time.get_ticks() // 250) % 7) / 7))
            y = pantalla.y + 3 + k * max(2, (pantalla.height - 5) // 3)
            pygame.draw.line(screen, (90, 240, 150), (pantalla.x + 3, y), (pantalla.x + 3 + largo - 6, y), 1)
        for k, col in enumerate(((240, 90, 90), (250, 210, 80), (90, 200, 255))):
            pygame.draw.circle(screen, col, (cuerpo.x + int(cuerpo.width * (k + 1) / 4),
                                             cuerpo.bottom - int(t * 0.15)), max(2, t // 15))
    elif tipo == "kit":
        # Caja de herramientas verde con asa, cierre y una llave inglesa asomándose.
        color = COLOR_CONSUMIBLE["kit"]
        oscuro = (40, 92, 60)
        t = max(14, tam)
        caja = pygame.Rect(0, 0, int(t * 0.86), int(t * 0.5))
        caja.midbottom = (cx, cy + int(t * 0.34))
        # La llave, detrás de la tapa.
        llave_a = (caja.x + int(t * 0.18), caja.y + 2)
        llave_b = (caja.x + int(t * 0.4), caja.y - int(t * 0.3))
        pygame.draw.line(screen, (190, 196, 210), llave_a, llave_b, max(3, t // 9))
        pygame.draw.circle(screen, (190, 196, 210), llave_b, max(3, t // 8))
        pygame.draw.circle(screen, (26, 30, 44), (llave_b[0] + 2, llave_b[1] - 2), max(1, t // 16))
        asa = pygame.Rect(0, 0, int(t * 0.4), int(t * 0.26))
        asa.midbottom = (cx + int(t * 0.1), caja.y + 3)
        pygame.draw.rect(screen, (150, 156, 170), asa, max(2, t // 14), border_radius=4)
        pygame.draw.rect(screen, color, caja, border_radius=4)
        tapa = pygame.Rect(caja.x, caja.y, caja.width, int(caja.height * 0.36))
        pygame.draw.rect(screen, (140, 230, 165), tapa, border_top_left_radius=4, border_top_right_radius=4)
        pygame.draw.line(screen, oscuro, (caja.x, tapa.bottom), (caja.right - 1, tapa.bottom), 2)
        pygame.draw.rect(screen, oscuro, caja, 2, border_radius=4)
        cierre = pygame.Rect(0, 0, max(4, int(t * 0.16)), max(4, int(t * 0.14)))
        cierre.center = (caja.centerx, tapa.bottom)
        pygame.draw.rect(screen, (250, 210, 80), cierre, border_radius=2)
        pygame.draw.rect(screen, (120, 90, 20), cierre, 1, border_radius=2)
    elif tipo == "fruta":
        color = COLOR_CONSUMIBLE["fruta"]
        r = max(4, int(tam * 0.32))
        pygame.draw.circle(screen, color, (cx, cy + 2), r)
        pygame.draw.circle(screen, (255, 170, 140), (cx - r // 3, cy - r // 3 + 2), max(1, r // 3))
        pygame.draw.line(screen, (90, 60, 30), (cx, cy - r + 2), (cx + 2, cy - r - 4), 2)
        hoja = pygame.Rect(0, 0, max(4, r), max(3, r // 2))
        hoja.midleft = (cx + 2, cy - r - 2)
        pygame.draw.ellipse(screen, (100, 190, 80), hoja)
    elif tipo == "abono":
        color = COLOR_CONSUMIBLE["abono"]
        saco = pygame.Rect(0, 0, int(tam * 0.6), int(tam * 0.66))
        saco.center = (cx, cy + 2)
        pygame.draw.rect(screen, color, saco, border_radius=6)
        pygame.draw.rect(screen, (90, 60, 34), saco, 2, border_radius=6)
        pygame.draw.line(screen, (90, 60, 34), (saco.x + 4, saco.y + 5), (saco.right - 4, saco.y + 5), 2)
        pygame.draw.circle(screen, (100, 190, 80), (cx, cy + 4), max(2, tam // 9))
    elif tipo.startswith("prueba_"):
        from screens.infiltrado_dibujo import icono_prueba
        icono_prueba(screen, tipo, centro, tam)


NOMBRE_OBJETO = {"pieza": ("Pieza", "Piezas"),
                 "decodificador": ("Decodificador", "Decodificadores"),
                 "kit": ("Kit de herramientas", "Kits de herramientas"),
                 "fruta": ("Fruta (para el Guardia)", "Frutas"),
                 "abono": ("Abono (para la planta)", "Abonos"),
                 # Las pruebas del infiltrado (data/infiltrado.py).
                 "prueba_audio": ("Audio interceptado", "Audios interceptados"),
                 "prueba_expediente": ("Expediente", "Expedientes"),
                 "prueba_captura": ("Captura de cámara", "Capturas de cámara")}


def _objetos_de(jugador):
    objetos = []
    if getattr(jugador, "piezas", 0) > 0:
        objetos.append(("pieza", jugador.piezas))
    inventario = getattr(jugador, "objetos", {})
    for tipo in ("decodificador", "kit", "fruta", "abono",
                 "prueba_audio", "prueba_expediente", "prueba_captura"):
        cantidad = inventario.get(tipo, 0) if hasattr(inventario, "get") else int(tipo in inventario)
        if cantidad > 0:
            objetos.append((tipo, cantidad))
    return objetos


def ancho_inventario(vista, jugador):
    """Más o menos lo que ocupa el cuadrito del inventario abajo a la derecha
    (0 si va con las manos vacías): el tutorial se acomoda al lado."""
    if getattr(jugador, "eliminado", False) or not _objetos_de(jugador):
        return 0
    return max(150, min(240, vista.width // 4))


def render_inventario(screen, vista, jugador):
    """Lo que lleva el jugador, en un cuadrito abajo a la derecha de su vista:
    una fila por objeto, con su dibujito y "x3 Piezas". Con las manos vacías
    no se dibuja nada (antes quedaba un "Inventario: vacío" fijo)."""
    if getattr(jugador, "eliminado", False):
        return
    objetos = _objetos_de(jugador)
    if not objetos:
        return
    f = fuente_de_tamano(max(11, min(15, vista.width // 60)))
    tam = max(18, min(26, vista.width // 40))
    titulo = None
    if hasattr(jugador, "nombre_tecla"):
        titulo = f.render(f"[{jugador.nombre_tecla('soltar')}] soltar", True, COLOR_TENUE)
    textos = [f.render(f"x{n} {NOMBRE_OBJETO[t][n > 1]}", True, COLOR_TEXTO) for t, n in objetos]
    ancho = max([titulo.get_width() if titulo else 0] + [tam + 8 + t.get_width() for t in textos]) + 16
    fila = max(tam, f.get_linesize()) + 4
    alto_titulo = titulo.get_height() + 6 if titulo else 0
    alto = alto_titulo + 6 + len(objetos) * fila
    caja = pygame.Rect(0, 0, ancho, alto)
    caja.bottomright = (vista.right - 12, vista.bottom - 12)
    fondo = pygame.Surface(caja.size, pygame.SRCALPHA)
    fondo.fill((14, 15, 28, 205))
    screen.blit(fondo, caja.topleft)
    pygame.draw.rect(screen, (70, 76, 110), caja, 1, border_radius=4)
    y = caja.y + 4
    if titulo:
        screen.blit(titulo, (caja.x + 8, y))
        y += alto_titulo
    for (tipo, _), texto in zip(objetos, textos):
        centro = (caja.x + 8 + tam // 2, y + fila // 2)
        _icono_objeto(screen, tipo, centro, tam)
        screen.blit(texto, (caja.x + 8 + tam + 8, y + (fila - texto.get_height()) // 2))
        y += fila
