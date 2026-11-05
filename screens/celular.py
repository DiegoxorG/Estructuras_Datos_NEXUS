"""Dibujo del celular (NEXUS) y de lo que NEXUS pone en la pantalla.

- render_celular: el teléfono abierto, a la derecha del viewport del jugador.
  Se ve como una red social cualquiera (publicaciones, compartir, reportar);
  el grafo de nexus.py no se dibuja.
- render_confianza: la barra de confianza de la tripulación, UNA para todo el
  equipo, arriba al centro (con 3 jugadores, en el cuarto cuadro): verde (confían en ustedes) desde la izquierda,
  roja (en los aliens) desde la derecha y gris en medio; cada parte mide su %.
  La raya blanca marca cuánto verde hace falta para los planos.
- render_aviso_celular: en el HUD de cada uno, su tecla del celular y lo nuevo.
- dibujar_lugar: la flecha y el aro hacia el lugar que el jugador está
  investigando.
"""

import math
import zlib

import pygame

from juego.fuentes import fuente_de_tamano
from screens.flechas import flecha_alrededor, cerca_del_borde
from screens.paneles import partir_lineas
from data.nexus import UMBRAL_PLANOS

COLOR_CARCASA = (18, 18, 26)
COLOR_PANTALLA = (238, 240, 247)
COLOR_TARJETA = (255, 255, 255)
COLOR_TARJETA_SEL = (226, 236, 255)
COLOR_BORDE_SEL = (70, 120, 230)
COLOR_TEXTO = (30, 32, 44)
COLOR_TENUE = (110, 116, 140)
COLOR_MARCA = (52, 108, 220)
COLOR_VERDE = (60, 190, 110)
COLOR_ROJO = (225, 70, 70)
COLOR_SOMBRA = (12, 11, 23)
COLOR_LUGAR = (90, 170, 255)

AVATARES = [(239, 108, 110), (99, 160, 234), (120, 200, 140), (240, 180, 80),
            (176, 120, 220), (90, 196, 200), (230, 130, 190), (150, 160, 180)]


def _avatar(screen, centro, radio, usuario, f):
    color = AVATARES[zlib.crc32(usuario.encode("utf-8")) % len(AVATARES)]
    pygame.draw.circle(screen, color, centro, radio)
    letra = usuario.lstrip("@")[:1].upper() or "?"
    img = f.render(letra, True, (255, 255, 255))
    screen.blit(img, img.get_rect(center=centro))


def _tiempo(ms):
    s = int(ms // 1000)
    if s < 60:
        return "ahora" if s < 5 else f"hace {s} s"
    return f"hace {s // 60} min"


# -- La barra de confianza ------------------------------------------------------------------

def _barra_ponderada(screen, rect, verde, rojo, umbral=UMBRAL_PLANOS):
    """Una sola barra: verde desde la izquierda, roja desde la derecha y gris en
    medio (los que no deciden). Cada parte mide lo que pesa en la tripulación.
    La raya blanca marca cuánto verde hace falta para los planos."""
    pygame.draw.rect(screen, (96, 100, 118), rect, border_radius=rect.height // 2)
    ancho_verde = int(rect.width * verde)
    ancho_rojo = int(rect.width * rojo)
    if ancho_verde > 0:
        pygame.draw.rect(screen, COLOR_VERDE, (rect.x, rect.y, ancho_verde, rect.height),
                         border_top_left_radius=rect.height // 2,
                         border_bottom_left_radius=rect.height // 2)
    if ancho_rojo > 0:
        pygame.draw.rect(screen, COLOR_ROJO, (rect.right - ancho_rojo, rect.y, ancho_rojo, rect.height),
                         border_top_right_radius=rect.height // 2,
                         border_bottom_right_radius=rect.height // 2)
    x = rect.x + int(rect.width * umbral)
    pygame.draw.line(screen, (255, 255, 255), (x, rect.y - 3), (x, rect.bottom + 2), 2)
    pygame.draw.rect(screen, (20, 20, 32), rect, 1, border_radius=rect.height // 2)


def _fuente_barra(ancho):
    return fuente_de_tamano(max(12, min(18, ancho // 105)))


def _estado_confianza(red):
    """El renglón de abajo de la barra: qué significa ahora y de qué color."""
    verde, rojo = red.barras()
    if red.planos:
        return "Confianza de la tripulación  ·  ¡planos listos!", COLOR_VERDE
    if rojo > verde:
        return "Los aliens van ganando: están más rápidos y ven más", (245, 150, 140)
    umbral = int(getattr(red, "umbral_planos", UMBRAL_PLANOS) * 100)
    return f"Confianza de la tripulación  ·  planos al {umbral}%", (190, 196, 230)


def _con_renglon(red):
    """En la barra chica (2 y 4 jugadores) el renglón de abajo solo sale
    cuando dice algo que hay que saber: planos listos o aliens ganando."""
    if red is None:
        return False
    verde, rojo = red.barras()
    return bool(red.planos) or rojo > verde


def rect_confianza(screen, cantidad, red=None):
    """Dónde va la barra general. Con 3 jugadores, en el cuarto cuadro (el
    panel del equipo, partida.render_panel_global); si no, chica, pegada
    arriba al centro, encima del corte entre las vistas: lo de cada vista que
    caería debajo se corre (paneles._hueco_fila)."""
    ancho, alto = screen.get_size()
    from screens.partida import tiene_panel
    if tiene_panel(cantidad):
        from screens.partida import rect_panel_global, arriba_confianza_panel
        panel = rect_panel_global(ancho, alto, cantidad)
        f = _fuente_barra(int(panel.width * 2))
        caja = pygame.Rect(0, 0, min(panel.width - 48, 680), f.get_linesize() * 2 + 18)
        caja.midtop = (panel.centerx, panel.y + arriba_confianza_panel(panel))
        return caja
    f = _fuente_barra(ancho)
    alto_caja = f.get_linesize() + 12 + (f.get_linesize() + 2 if _con_renglon(red) else 0)
    caja = pygame.Rect(0, 0, int(min(440, max(250, ancho * 0.23))), alto_caja)
    caja.midtop = (ancho // 2, 2)
    return caja


def columna_avisos(screen, cantidad, red):
    """Dónde se apilan el aviso del evento y el cartel de la IA: debajo de la
    barra de confianza. Devuelve (centro x, y de arriba, ancho máximo)."""
    ancho, alto = screen.get_size()
    from screens.partida import tiene_panel
    if tiene_panel(cantidad):
        from screens.partida import rect_panel_global, arriba_confianza_panel
        panel = rect_panel_global(ancho, alto, cantidad)
        arriba = (rect_confianza(screen, cantidad, red).bottom if red is not None
                  else panel.y + arriba_confianza_panel(panel)) + 14
        return panel.centerx, arriba, panel.width - 40
    # Debajo de la barra y también de la franja de arriba de las vistas
    # cuando muestra el objetivo (dos líneas): si no, el cartel de la IA le
    # tapaba el final del objetivo a la vista de la derecha.
    from screens.partida import calcular_viewports
    from screens.paneles import _fuente_para
    vista = calcular_viewports(ancho, alto, max(1, cantidad))[0]
    arriba = vista.y + _fuente_para(vista).get_linesize() * 2 + 16
    if red is not None:
        arriba = max(arriba, rect_confianza(screen, cantidad, red).bottom + 6)
    return ancho // 2, arriba, int(min(580, max(320, ancho * 0.32)))


def render_confianza(screen, red, cantidad):
    """La confianza de la tripulación, una para todo el equipo."""
    if red is None:
        return
    verde, rojo = red.barras()
    caja = rect_confianza(screen, cantidad, red)
    fondo = pygame.Surface(caja.size, pygame.SRCALPHA)
    fondo.fill((14, 15, 28, 225))
    screen.blit(fondo, caja.topleft)
    pygame.draw.rect(screen, (90, 100, 150), caja, 1, border_radius=8)

    from screens.partida import tiene_panel
    if tiene_panel(cantidad):
        from screens.partida import rect_panel_global
        f = _fuente_barra(int(rect_panel_global(*screen.get_size(), cantidad).width * 2))
    else:
        f = _fuente_barra(screen.get_width())
    izq = f.render(f"Ustedes {int(verde * 100)}%", True, COLOR_VERDE)
    der = f.render(f"{int(rojo * 100)}% Aliens", True, COLOR_ROJO)
    alto_barra = max(10, f.get_height() - 5)
    barra = pygame.Rect(caja.x + izq.get_width() + 18,
                        caja.y + 6 + (f.get_linesize() - alto_barra) // 2,
                        caja.width - izq.get_width() - der.get_width() - 36, alto_barra)
    screen.blit(izq, (caja.x + 10, barra.centery - izq.get_height() // 2))
    screen.blit(der, (caja.right - der.get_width() - 10, barra.centery - der.get_height() // 2))
    _barra_ponderada(screen, barra, verde, rojo, getattr(red, "umbral_planos", UMBRAL_PLANOS))

    if tiene_panel(cantidad) or _con_renglon(red):
        texto, color = _estado_confianza(red)
        from screens.paneles import _recortar
        img = f.render(_recortar(f, texto, caja.width - 16), True, color)
        screen.blit(img, img.get_rect(midbottom=(caja.centerx, caja.bottom - 4)))


def render_aviso_celular(screen, vista, jugador, red):
    """En la franja de arriba de cada uno: cuántas cosas nuevas o por
    verificar tiene en NEXUS, con su tecla. Si no hay nada, no sale (la
    tecla la enseña el tutorial)."""
    if red is None or jugador not in red.vistas:
        return
    from redes import celular as logica
    por_hacer, nuevos = logica.avisos(red, jugador)
    if not por_hacer and not nuevos:
        return
    from screens.paneles import _fuente_para, fila_bajo_hud, _con_sombra
    f = fuente_de_tamano(max(11, min(16, vista.width // 58)))
    tecla = jugador.nombre_tecla('celular')
    partes = [f"NEXUS [{tecla}]"]
    if por_hacer:
        partes.append(f"{por_hacer} por verificar")
    if nuevos:
        partes.append(f"{nuevos} nuevo{'s' if nuevos > 1 else ''}")
    color = (255, 214, 64) if nuevos else (255, 180, 90)
    texto = "  ·  ".join(partes)
    izq, der = getattr(jugador, "hud_hueco", (vista.x + 12, vista.right - 12))
    if f.size(texto)[0] > der - izq:
        texto = f"NEXUS [{tecla}]" + (f" {por_hacer}!" if por_hacer else "") + (f" +{nuevos}" if nuevos else "")
    y = vista.y + 5 + (_fuente_para(vista).get_linesize() - f.get_linesize()) // 2
    if f.size(texto)[0] > der - izq:
        # Ni corto cabe en la franja: va debajo, a la izquierda.
        fila = fila_bajo_hud(vista, jugador)
        izq, der, y = fila.x + 4, fila.right, fila.y + 4
    x = izq + max(0, (der - izq - f.size(texto)[0]) // 2)
    _con_sombra(screen, f, texto, color, (x, y))


# -- El lugar que investiga ------------------------------------------------------------------

def dibujar_lugar(screen, vista, camara, dueño, red, tiempo_ms):
    if red is None:
        return
    pub = red.investigando.get(dueño)
    if pub is None or pub.desmentida or pub.lugar is None:
        return
    x, y = pub.lugar
    if camara.collidepoint(x, y):
        centro = (int(x - camara.x + vista.x), int(y - camara.y + vista.y))
        radio = 30 + int(6 * math.sin(tiempo_ms / 200))
        pygame.draw.circle(screen, COLOR_LUGAR, centro, radio, 3)
        cam = pygame.Rect(0, 0, 22, 15)
        cam.center = centro
        pygame.draw.rect(screen, COLOR_LUGAR, cam, border_radius=3)
        pygame.draw.circle(screen, (255, 255, 255), centro, 4)
        if not cerca_del_borde(vista, centro):
            return
    # Fuera de pantalla (o en el borde, donde lo tapa el HUD): una flecha
    # alrededor del jugador (screens/flechas.py).
    flecha_alrededor(screen, vista, camara, dueño, (x, y), COLOR_LUGAR, None, tiempo_ms)


# -- El celular --------------------------------------------------------------------------------

def _marco(vista, tapado=None, jugador=None):
    """Rect del teléfono y de su pantalla, a la derecha del viewport, debajo
    de la franja de arriba. Si la barra de confianza cae encima (`tapado`),
    el teléfono arranca debajo."""
    if jugador is not None:
        from screens.paneles import alto_hud
        arriba = alto_hud(vista, jugador) + 8
    else:
        arriba = vista.y + min(60, vista.height // 8)
    ancho_previo = int(min(380, max(240, vista.width * 0.46)))
    if tapado is not None and tapado.colliderect(
            pygame.Rect(vista.right - ancho_previo - 14, arriba, ancho_previo, vista.bottom - arriba)):
        arriba = max(arriba, tapado.bottom + 6)
    alto = vista.bottom - arriba - 12
    ancho = int(min(380, max(240, vista.width * 0.46), alto * 0.62 + 60))
    telefono = pygame.Rect(vista.right - ancho - 14, arriba, ancho, alto)
    pantalla = telefono.inflate(-16, -34)
    pantalla.y = telefono.y + 14
    return telefono, pantalla


# Colores de las pestañas y de los estados de una misión.
COLOR_PESTANA = {"misiones": (232, 140, 40), "equipo": (52, 168, 98), "red": (70, 118, 220)}
ESTADOS = {
    "pendiente": ("Por verificar", (232, 140, 40)),
    "en_curso": ("Vas para allá", (52, 108, 220)),
    "foto": ("¡Foto lista! Publícala", (52, 168, 98)),
    "hecha": ("Desmentido", (150, 156, 175)),
    "reportada": ("Suplantación reportada", (150, 156, 175)),
}
COLOR_INFO = (244, 246, 252)


def render_celular(screen, vista, jugador, red, tapado=None):
    panel = jugador.panel
    if panel is None or red is None or jugador not in red.vistas:
        return
    telefono, pantalla = _marco(vista, tapado, jugador)
    pygame.draw.rect(screen, COLOR_SOMBRA, telefono.move(5, 5), border_radius=22)
    pygame.draw.rect(screen, COLOR_CARCASA, telefono, border_radius=22)
    pygame.draw.rect(screen, (70, 72, 92), telefono, 2, border_radius=22)
    pygame.draw.rect(screen, COLOR_PANTALLA, pantalla, border_radius=10)
    pygame.draw.circle(screen, (50, 52, 70), (telefono.centerx, telefono.bottom - 10), 4)

    tam = max(11, min(16, pantalla.width // 22))
    f = fuente_de_tamano(tam)
    fb = fuente_de_tamano(tam + 3)
    fc = fuente_de_tamano(max(10, tam - 2))
    clip = screen.get_clip()
    screen.set_clip(pantalla.clip(clip) if clip else pantalla)

    # Encabezado: el nombre de la red, dónde estás y la confianza.
    vista_cel = panel.get("vista")
    cab = pygame.Rect(pantalla.x, pantalla.y, pantalla.width, fb.get_linesize() + 30)
    pygame.draw.rect(screen, (24, 28, 52), cab, border_top_left_radius=10, border_top_right_radius=10)
    screen.blit(fb.render("NEXUS", True, (150, 200, 255)), (cab.x + 12, cab.y + 5))
    sub = {"post": "Publicación", "origen": "¿De dónde salió?",
           "ubicacion": "Publicar foto", "mensaje": ""}.get(vista_cel, "")
    if sub:
        img = fc.render(sub, True, (190, 196, 230))
        screen.blit(img, (cab.right - img.get_width() - 12, cab.y + 9))
    verde, rojo = red.barras()
    barra = pygame.Rect(cab.x + 12, cab.bottom - 15, cab.width - 24, 8)
    _barra_ponderada(screen, barra, verde, rojo, getattr(red, "umbral_planos", UMBRAL_PLANOS))

    arriba = cab.bottom + 6
    if vista_cel == "feed":
        arriba = _pestanas(screen, pantalla, arriba, jugador, red, panel, fc)
    alto_pie = fc.get_linesize() + 8
    cuerpo = pygame.Rect(pantalla.x + 8, arriba + 4, pantalla.width - 16,
                         pantalla.bottom - arriba - 4 - alto_pie)
    if vista_cel == "feed":
        _feed(screen, cuerpo, jugador, red, panel, f, fb, fc)
    else:
        _detalle(screen, cuerpo, jugador, red, panel, f, fb, fc)

    # Pie: qué tecla hace qué.
    pie = pygame.Rect(pantalla.x, pantalla.bottom - alto_pie, pantalla.width, alto_pie)
    pygame.draw.rect(screen, (226, 230, 240), pie, border_bottom_left_radius=10,
                     border_bottom_right_radius=10)
    partes = [f"[{jugador.nombre_tecla('interactuar')}] abrir" if vista_cel == "feed"
              else f"[{jugador.nombre_tecla('interactuar')}] elegir"]
    if vista_cel == "feed":
        partes.append(f"[{jugador.pista_pestanas()}] pestaña")
    partes.append(f"[{jugador.nombre_tecla('celular')}] {'cerrar' if vista_cel == 'feed' else 'atrás'}")
    texto = "   ".join(partes)
    img = fc.render(texto, True, COLOR_TENUE)
    if img.get_width() > pie.width - 8:
        img = fc.render("  ".join(partes), True, COLOR_TENUE)
    screen.blit(img, img.get_rect(center=pie.center))
    screen.set_clip(clip)


# -- El inicio: pestañas y tarjetas -----------------------------------------------------------

def _pestanas(screen, pantalla, y, jugador, red, panel, fc):
    from redes import celular as logica
    alto = fc.get_linesize() + 12
    actual = panel.get("pestana", "misiones")
    ancho = (pantalla.width - 16 - 8) // 3
    x = pantalla.x + 8
    for clave, nombre in logica.PESTANAS:
        rect = pygame.Rect(x, y, ancho, alto)
        color = COLOR_PESTANA[clave]
        activa = clave == actual
        pygame.draw.rect(screen, color if activa else (226, 230, 240), rect, border_radius=alto // 2)
        if clave == "misiones":
            numero = sum(1 for p in logica.misiones(red, jugador) if logica.es_mision_activa(red, p))
        else:
            numero = logica.sin_ver(red, jugador, clave)
        img = fc.render(nombre, True, (255, 255, 255) if activa else COLOR_TEXTO)
        cx = rect.centerx - (8 if numero else 0)
        screen.blit(img, img.get_rect(center=(cx, rect.centery)))
        if numero:
            r = max(7, fc.get_height() // 2 + 1)
            centro = (min(rect.right - r - 3, cx + img.get_width() // 2 + r + 2), rect.centery)
            pygame.draw.circle(screen, (255, 255, 255) if activa else color, centro, r)
            num = fc.render(str(numero), True, color if activa else (255, 255, 255))
            screen.blit(num, num.get_rect(center=centro))
        x += ancho + 4
    return y + alto + 2


def _cortar_linea(texto, f, ancho):
    """Una sola línea que quepa en `ancho`, con "..." si hubo que cortar."""
    if f.size(texto)[0] <= ancho:
        return texto
    while texto and f.size(texto + "...")[0] > ancho:
        texto = texto[:-1]
    return texto.rstrip() + "..."


def _recortar(texto, f, ancho, maximo):
    lineas = partir_lineas(texto, f, ancho)
    if len(lineas) > maximo:
        lineas = lineas[:maximo]
        lineas[-1] = lineas[-1].rstrip(".,; ") + "..."
    return lineas


def _chip(screen, texto, color, x, y, f, relleno=True):
    img = f.render(texto, True, (255, 255, 255) if relleno else color)
    caja = img.get_rect(topleft=(x, y)).inflate(12, 4)
    caja.topleft = (x, y)
    if relleno:
        pygame.draw.rect(screen, color, caja, border_radius=caja.height // 2)
    else:
        pygame.draw.rect(screen, color, caja, 1, border_radius=caja.height // 2)
    screen.blit(img, img.get_rect(center=caja.center))
    return caja


def _icono(screen, tipo, centro, r, color):
    """Iconitos dibujados con formas (la letra del juego no trae símbolos)."""
    pygame.draw.circle(screen, color, centro, r)
    x, y = centro
    b = (255, 255, 255)
    if tipo == "pendiente":          # lupa
        pygame.draw.circle(screen, b, (x - 2, y - 2), r // 2, 2)
        pygame.draw.line(screen, b, (x + 1, y + 1), (x + r // 2 + 1, y + r // 2 + 1), 3)
    elif tipo == "en_curso":         # pin
        pygame.draw.circle(screen, b, (x, y - 3), r // 2 - 1)
        pygame.draw.polygon(screen, b, [(x - r // 2 + 1, y - 2), (x + r // 2 - 1, y - 2), (x, y + r // 2 + 2)])
        pygame.draw.circle(screen, color, (x, y - 3), max(1, r // 5))
    elif tipo == "foto":             # cámara
        pygame.draw.rect(screen, b, (x - r // 2 - 1, y - r // 3, r + 2, r * 2 // 3 + 1), border_radius=2)
        pygame.draw.circle(screen, color, (x, y), max(2, r // 4))
    elif tipo in ("hecha", "reportada"):   # palomita
        pygame.draw.lines(screen, b, False, [(x - r // 2, y), (x - 2, y + r // 3), (x + r // 2, y - r // 3)], 3)
    else:                            # aviso
        pygame.draw.line(screen, b, (x, y - r // 2), (x, y + 1), 3)
        pygame.draw.circle(screen, b, (x, y + r // 2 - 1), 2)


def _direccion(jugador, pub):
    if pub.lugar is None:
        return ""
    from entidades.npcs import direccion_texto
    import math as _m
    d = _m.dist(jugador.hitbox.center, pub.lugar)
    if d < 120:
        return "aquí cerca"
    return f"al {direccion_texto(jugador.hitbox.center, pub.lugar)}"


def _tarjeta(red, jugador, pestana, pub, f, fb, fc, ancho):
    """Lo que lleva una tarjeta del inicio: título, líneas, chips y colores."""
    from redes import celular as logica
    nuevo = pub.id not in red.vistas[jugador]
    if pestana == "misiones":
        estado = logica.estado_mision(red, jugador, pub)
        texto_estado, color = ESTADOS[estado]
        if estado == "en_curso":
            texto_estado += " · " + _direccion(jugador, pub)
        lugar = logica.nombre_lugar(pub) or "la nave"
        # El título es el lugar: es lo que importa (a dónde hay que ir).
        titulo = lugar[:1].upper() + lugar[1:] if pub.tipo == "rumor" else f"Ayuda: {lugar}"
        hecha = estado in ("hecha", "reportada")
        return {"titulo": titulo, "icono": estado, "color": color, "franja": color,
                "lineas": _recortar(f"\"{pub.texto}\"", fc, ancho, 2), "fuente_lineas": fc,
                "chips": [(texto_estado, color)] + ([("nuevo", (230, 150, 40))] if nuevo and not hecha else []),
                "tiempo": _tiempo(pub.edad_ms), "apagada": hecha}
    usuario = red.usuario(pub.autor)
    chips = []
    if pub.tipo == "desmentido":
        chips.append(("Desmintió un rumor", COLOR_VERDE))
    elif pub.tipo == "compartido":
        chips.append(("Compartió", COLOR_MARCA))
    elif pub.tipo == "testimonio":
        chips.append(("Rescatado", COLOR_VERDE))
    if nuevo and pestana == "equipo":
        chips.append(("nuevo", (230, 150, 40)))
    texto = pub.texto
    return {"titulo": usuario, "avatar": usuario, "color": COLOR_PESTANA[pestana], "franja": None,
            "lineas": _recortar(texto, f if pestana == "equipo" else fc, ancho, 3 if pestana == "equipo" else 2),
            "fuente_lineas": f if pestana == "equipo" else fc,
            "chips": chips, "tiempo": _tiempo(pub.edad_ms), "apagada": False}


VACIO = {
    "misiones": ("Nada por verificar.",
                 "Cuando llegue un rumor o alguien pida ayuda, aparece aquí. Verifica antes de compartir."),
    "equipo": ("Tu equipo no ha publicado nada.",
               "Cuando alguien desmienta un rumor o rescate a un prisionero, sale aquí."),
    "red": ("La red está callada.", "Aquí sale lo que comentan los prisioneros."),
}


def _feed(screen, cuerpo, jugador, red, panel, f, fb, fc):
    pestana = panel.get("pestana", "misiones")
    opciones = panel.get("opciones", [])
    if not opciones:
        titulo, texto = VACIO[pestana]
        y = cuerpo.y + cuerpo.height // 3
        img = f.render(titulo, True, COLOR_TEXTO)
        screen.blit(img, img.get_rect(midtop=(cuerpo.centerx, y)))
        y += f.get_linesize() + 6
        for renglon in partir_lineas(texto, fc, cuerpo.width - 30):
            img = fc.render(renglon, True, COLOR_TENUE)
            screen.blit(img, img.get_rect(midtop=(cuerpo.centerx, y)))
            y += fc.get_linesize()
        return
    margen_texto = 46
    ancho_texto = cuerpo.width - margen_texto - 10
    tarjetas = [_tarjeta(red, jugador, pestana, pub, f, fb, fc, ancho_texto) for _, pub in opciones]
    alturas = []
    for t in tarjetas:
        alto = 10 + f.get_linesize() + len(t["lineas"]) * t["fuente_lineas"].get_linesize()
        alto += (fc.get_linesize() + 8) if t["chips"] else 0
        alturas.append(alto + 8)
    cursor = jugador.cursor % len(opciones)
    # Desde dónde se dibuja para que la seleccionada quede a la vista.
    inicio = 0
    while sum(alturas[inicio:cursor + 1]) + 6 * (cursor - inicio) > cuerpo.height and inicio < cursor:
        inicio += 1
    if inicio > 0:
        img = fc.render(f"{inicio} más arriba", True, COLOR_TENUE)
        screen.blit(img, img.get_rect(midtop=(cuerpo.centerx, cuerpo.y - 2)))
    y = cuerpo.y + (fc.get_linesize() if inicio > 0 else 0)
    for i in range(inicio, len(tarjetas)):
        t = tarjetas[i]
        rect = pygame.Rect(cuerpo.x, y, cuerpo.width, alturas[i])
        if rect.top > cuerpo.bottom:
            break
        sel = i == cursor
        fondo = COLOR_TARJETA_SEL if sel else ((246, 247, 250) if t["apagada"] else COLOR_TARJETA)
        pygame.draw.rect(screen, fondo, rect, border_radius=9)
        if t["franja"] is not None:
            pygame.draw.rect(screen, t["franja"], (rect.x, rect.y, 6, rect.height),
                             border_top_left_radius=9, border_bottom_left_radius=9)
        pygame.draw.rect(screen, COLOR_BORDE_SEL if sel else (214, 218, 230), rect,
                         3 if sel else 1, border_radius=9)
        centro = (rect.x + 24, rect.y + 10 + f.get_linesize() // 2 + 2)
        if t.get("avatar"):
            _avatar(screen, centro, 13, t["avatar"], fc)
        else:
            _icono(screen, t["icono"], centro, 13, t["color"])
        ty = rect.y + 8
        color_titulo = COLOR_TENUE if t["apagada"] else COLOR_TEXTO
        img = fc.render(t["tiempo"], True, COLOR_TENUE)
        screen.blit(img, (rect.right - img.get_width() - 8, ty + 2))
        titulo = _cortar_linea(t["titulo"], f, rect.right - img.get_width() - 16 - (rect.x + margen_texto))
        screen.blit(f.render(titulo, True, color_titulo), (rect.x + margen_texto, ty))
        ty += f.get_linesize() + 2
        fl = t["fuente_lineas"]
        for texto in t["lineas"]:
            screen.blit(fl.render(texto, True, COLOR_TENUE if t["apagada"] else (70, 74, 92)),
                        (rect.x + margen_texto, ty))
            ty += fl.get_linesize()
        x = rect.x + margen_texto
        for texto, color in t["chips"]:
            if x + fc.size(texto)[0] + 12 > rect.right - 6:
                break
            caja = _chip(screen, texto, color, x, ty + 4, fc)
            x = caja.right + 6
        y = rect.bottom + 6
    restantes = len(tarjetas) - i - 1 if rect.top <= cuerpo.bottom else len(tarjetas) - i
    if restantes > 0:
        img = fc.render(f"{restantes} más abajo", True, COLOR_TENUE)
        screen.blit(img, img.get_rect(midbottom=(cuerpo.centerx, cuerpo.bottom + 2)))


# -- Una publicación y lo demás ----------------------------------------------------------------

def _detalle(screen, cuerpo, jugador, red, panel, f, fb, fc):
    from redes import celular as logica
    vista = panel.get("vista")
    y = cuerpo.y
    ancho = cuerpo.width - 16

    def parrafo(texto, color=COLOR_TEXTO, fuente=f, x=None, ancho_max=None):
        nonlocal y
        for renglon in partir_lineas(texto, fuente, ancho_max or ancho):
            screen.blit(fuente.render(renglon, True, color), (x if x is not None else cuerpo.x + 8, y))
            y += fuente.get_linesize()
        y += 4

    def caja_info(lineas):
        """Cajita gris con datos (lugar, quién lo compartió...)."""
        nonlocal y
        if not lineas:
            return
        alto = sum(len(partir_lineas(t, fc, ancho - 24)) for t, _ in lineas) * fc.get_linesize() + 14
        rect = pygame.Rect(cuerpo.x, y, cuerpo.width, alto)
        pygame.draw.rect(screen, COLOR_INFO, rect, border_radius=8)
        pygame.draw.rect(screen, (216, 220, 232), rect, 1, border_radius=8)
        y += 7
        for texto, color in lineas:
            pygame.draw.circle(screen, color, (cuerpo.x + 12, y + fc.get_linesize() // 2), 3)
            for renglon in partir_lineas(texto, fc, ancho - 24):
                screen.blit(fc.render(renglon, True, COLOR_TEXTO), (cuerpo.x + 22, y))
                y += fc.get_linesize()
        y = rect.bottom + 8

    if vista == "post":
        pub = panel["pub"]
        autor = red.via(jugador, pub) if pub.tipo in ("rumor", "trampa") else pub.autor
        usuario = red.usuario(autor)
        _avatar(screen, (cuerpo.x + 20, y + 18), 16, usuario, f)
        screen.blit(f.render(usuario, True, COLOR_TEXTO), (cuerpo.x + 44, y + 4))
        screen.blit(fc.render(_tiempo(pub.edad_ms), True, COLOR_TENUE), (cuerpo.x + 44, y + 6 + f.get_linesize()))
        estado = panel.get("estado")
        if estado:
            texto_estado, color = ESTADOS[estado]
            img = fc.render(texto_estado, True, (255, 255, 255))
            caja = img.get_rect().inflate(12, 4)
            caja.topright = (cuerpo.right, y + 4)
            pygame.draw.rect(screen, color, caja, border_radius=caja.height // 2)
            screen.blit(img, img.get_rect(center=caja.center))
        y += 44
        # El texto de la publicación, en su tarjeta.
        renglones = partir_lineas(pub.texto, f, ancho - 8)
        rect = pygame.Rect(cuerpo.x, y, cuerpo.width, len(renglones) * f.get_linesize() + 16)
        pygame.draw.rect(screen, COLOR_TARJETA, rect, border_radius=8)
        pygame.draw.rect(screen, (214, 218, 230), rect, 1, border_radius=8)
        ty = y + 8
        for renglon in renglones:
            screen.blit(f.render(renglon, True, COLOR_TEXTO), (cuerpo.x + 10, ty))
            ty += f.get_linesize()
        y = rect.bottom + 8
        info = []
        if pub.foto:
            info.append(("Foto: " + pub.foto, COLOR_MARCA))
        lugar = logica.nombre_lugar(pub)
        if pub.tipo in ("rumor", "trampa") and lugar:
            info.append((f"Lugar: {lugar}", (232, 140, 40)))
        if estado == "en_curso":
            info.append((f"Vas para allá ({_direccion(jugador, pub)}). Sigue la flecha azul.", COLOR_MARCA))
        if estado == "foto":
            info.append(("Ya sacaste la foto: publícala para frenar el rumor.", COLOR_VERDE))
        if pub.tipo == "rumor" and pub.desmentida:
            info.append(("Alguien ya lo desmintió con una foto.", COLOR_VERDE))
        if pub.tipo == "trampa" and pub.reportada:
            info.append(("Reportada: no la escribió su dueño.", COLOR_ROJO))
        if pub.tipo in ("rumor", "trampa") and autor != pub.autor:
            info.append((f"{usuario} lo compartió. No dice de dónde lo sacó.", COLOR_TENUE))
        if estado == "pendiente" and pub.tipo == "rumor":
            info.append(("Antes de compartir, verifica: ve al lugar y saca una foto.", COLOR_TENUE))
        caja_info(info)
    elif vista == "origen":
        camino = panel.get("camino") or []
        parrafo("Así te llegó:", COLOR_TENUE, fc)
        paso = max(30, f.get_linesize() + 14)
        x0 = cuerpo.x + 24
        for i, nodo in enumerate(camino):
            nombre = "tú" if nodo == red.nodo_de(jugador) else red.usuario(nodo)
            centro = (x0, y + 12)
            if i + 1 < len(camino):
                pygame.draw.line(screen, (196, 200, 214), centro, (x0, y + 12 + paso), 3)
            _avatar(screen, centro, 11, nombre if nombre != "tú" else "@tu", fc)
            color = COLOR_ROJO if i == 0 else COLOR_TEXTO
            etiqueta = nombre + ("  · lo publicó" if i == 0 else "")
            screen.blit(f.render(etiqueta, True, color), (x0 + 20, y + 12 - f.get_linesize() // 2))
            y += paso
        y += 2
        origen = panel.get("origen")
        pub = panel.get("pub")
        if pub is not None and pub.suplantada:
            caja_info([(f"Publicado desde: dispositivo desconocido. Alguien está usando "
                        f"la cuenta de {red.usuario(origen)}.", COLOR_ROJO)])
        elif origen in red.grafo:
            caja_info([(f"Lo empezó {red.usuario(origen)}. Los demás solo lo pasaron: "
                        "reportarlos a ellos no frena nada.", COLOR_TENUE)])
        else:
            caja_info([("La cuenta que lo empezó ya no existe.", COLOR_TENUE)])
    elif vista == "ubicacion":
        rumor = panel["rumor"]
        caja_info([("Tu foto: " + rumor.rumor["foto"], COLOR_MARCA)])
        caja_info([("Tal cual: se ve dónde estás. Convence a más gente, pero el alien más "
                    "cercano va a ir por ti.", COLOR_ROJO),
                   ("Recortada: nadie sabe dónde estás. Convence a menos gente, pero es "
                    "más seguro.", COLOR_VERDE)])
    elif vista == "mensaje":
        color = panel.get("color", COLOR_TEXTO)
        puntos = panel.get("puntos", 0)
        r = 22
        centro = (cuerpo.centerx, y + r + 6)
        tipo = "hecha" if puntos > 0 else ("en_curso" if puntos == 0 else "aviso")
        _icono(screen, tipo, centro, r, color)
        y += 2 * r + 16
        for renglon in partir_lineas(panel.get("texto", ""), f, ancho):
            img = f.render(renglon, True, COLOR_TEXTO)
            screen.blit(img, img.get_rect(midtop=(cuerpo.centerx, y)))
            y += f.get_linesize()
        if puntos:
            y += 6
            img = fb.render(f"{puntos:+d} puntos", True, color)
            screen.blit(img, img.get_rect(midtop=(cuerpo.centerx, y)))
            y += fb.get_linesize()

    # Botones abajo: el primero (lo principal) va resaltado.
    opciones = panel.get("opciones", [])
    alto_op = f.get_linesize() + 12
    y_op = max(y + 6, cuerpo.bottom - len(opciones) * (alto_op + 6))
    principal = {"investigar", "desmentir", "tal_cual", "recortada", "reportar_suplantacion",
                 "reportar_origen", "cerrar"}
    for i, (texto, accion) in enumerate(opciones):
        rect = pygame.Rect(cuerpo.x, y_op, cuerpo.width, alto_op)
        sel = i == jugador.cursor % len(opciones)
        destacado = accion in principal
        if sel:
            fondo, borde, color = COLOR_BORDE_SEL, COLOR_BORDE_SEL, (255, 255, 255)
        elif destacado:
            fondo, borde, color = (220, 232, 255), COLOR_BORDE_SEL, COLOR_MARCA
        else:
            fondo, borde, color = COLOR_TARJETA, (210, 214, 228), COLOR_TEXTO
        pygame.draw.rect(screen, fondo, rect, border_radius=alto_op // 2)
        pygame.draw.rect(screen, borde, rect, 2 if (sel or destacado) else 1, border_radius=alto_op // 2)
        img = f.render(texto, True, color)
        if img.get_width() > rect.width - 12:
            img = fc.render(texto, True, color)
        screen.blit(img, img.get_rect(center=rect.center))
        y_op += alto_op + 6
