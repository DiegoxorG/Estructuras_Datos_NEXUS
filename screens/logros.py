"""Dibujo de los logros: el aviso cuando se consigue uno y el árbol completo
(menú de pausa > Logros).

El árbol se dibuja de izquierda a derecha como el de Minecraft: la raíz a la
izquierda, cada columna es un nivel de profundidad y las posiciones salen del
recorrido en postorden de ArbolLogros.posiciones().
"""

import pygame

from data.logros import COLOR_RAMA
from juego.fuentes import fuente, fuente_de_tamano

COLOR_FONDO_ARBOL = (14, 14, 28)
COLOR_LINEA = (90, 96, 130)
COLOR_LINEA_OBTENIDA = (200, 205, 230)
COLOR_OCULTO = (60, 62, 80)
COLOR_TEXTO = (240, 242, 252)
COLOR_TENUE = (150, 156, 190)
COLOR_SELECCION = (255, 214, 64)


def _color(nodo):
    return COLOR_RAMA.get(nodo.rama, COLOR_TEXTO)


def _oscuro(color, f=0.35):
    return tuple(int(c * f) for c in color)


# -- Aviso al conseguir uno ---------------------------------------------------------------

def render_aviso_logro(screen, gestor):
    """Cartel abajo al centro: "LOGRO  Fantasma" y su descripción."""
    if gestor is None or not gestor.avisos:
        return
    nodo, ms = gestor.avisos[0]
    ancho, alto = screen.get_size()
    color = _color(nodo)
    f_titulo = fuente_de_tamano(22 if ancho >= 1200 else 18)
    f_desc = fuente_de_tamano(15 if ancho >= 1200 else 13)
    titulo = f_titulo.render(nodo.nombre, True, COLOR_TEXTO)
    etiqueta = f_desc.render("¡LOGRO!", True, color)
    desc = f_desc.render(nodo.descripcion, True, COLOR_TENUE)
    tam_icono = 40
    caja = pygame.Rect(0, 0, max(titulo.get_width() + etiqueta.get_width() + 12,
                                 desc.get_width()) + tam_icono + 44,
                       max(tam_icono, titulo.get_height() + desc.get_height()) + 20)
    caja.midbottom = (ancho // 2, alto - 130)
    # Entra deslizándose y se va apagando al final.
    entrada = min(1.0, (3500 - ms) / 250) if ms <= 3500 else 1.0
    caja.y += int((1 - max(0.0, entrada)) * 40)
    alfa = 235 if ms > 400 else int(235 * ms / 400)
    fondo = pygame.Surface(caja.size, pygame.SRCALPHA)
    fondo.fill((16, 16, 30, alfa))
    screen.blit(fondo, caja.topleft)
    pygame.draw.rect(screen, color, caja, 2, border_radius=6)
    icono = pygame.Rect(caja.x + 12, caja.centery - tam_icono // 2, tam_icono, tam_icono)
    _caja_nodo(screen, icono, nodo, "obtenido")
    x = icono.right + 12
    y = caja.y + 10
    screen.blit(etiqueta, (x, y + (titulo.get_height() - etiqueta.get_height()) // 2))
    screen.blit(titulo, (x + etiqueta.get_width() + 12, y))
    screen.blit(desc, (x, y + titulo.get_height() + 2))


# -- Árbol completo ------------------------------------------------------------------------

def estado(nodo, catalogo=False):
    """En el catálogo del menú se ven todos (los que faltan, sin palomita)."""
    if nodo.obtenido:
        return "obtenido"
    return "visible" if nodo.visible or catalogo else "oculto"


def _caja_nodo(screen, rect, nodo, est, seleccionado=False):
    color = _color(nodo)
    if est == "obtenido":
        pygame.draw.rect(screen, _oscuro(color, 0.55), rect, border_radius=5)
        pygame.draw.rect(screen, color, rect, 3, border_radius=5)
        # Visto bueno.
        a = (rect.x + rect.w * 0.25, rect.y + rect.h * 0.52)
        b = (rect.x + rect.w * 0.43, rect.y + rect.h * 0.70)
        c = (rect.x + rect.w * 0.76, rect.y + rect.h * 0.30)
        pygame.draw.lines(screen, COLOR_TEXTO, False, [a, b, c], max(2, rect.w // 10))
    elif est == "visible":
        pygame.draw.rect(screen, (26, 26, 42), rect, border_radius=5)
        pygame.draw.rect(screen, color, rect, 2, border_radius=5)
        punto = pygame.Rect(0, 0, rect.w // 4, rect.h // 4)
        punto.center = rect.center
        pygame.draw.rect(screen, _oscuro(color, 0.7), punto, border_radius=2)
    else:
        pygame.draw.rect(screen, (22, 22, 34), rect, border_radius=5)
        pygame.draw.rect(screen, COLOR_OCULTO, rect, 2, border_radius=5)
        q = fuente_de_tamano(max(10, rect.h - 10)).render("?", True, COLOR_OCULTO)
        screen.blit(q, q.get_rect(center=rect.center))
    if seleccionado:
        pygame.draw.rect(screen, COLOR_SELECCION, rect.inflate(8, 8), 2, border_radius=7)


def render_arbol_logros(screen, arbol, seleccionado=None, catalogo=None):
    """Dibuja el árbol entero. Devuelve {nodo: rect} para el mouse.

    `catalogo` ({clave: veces}): el de "Logros" en el menú principal. Se ven
    todos, con nombre y descripción, y los obtenidos son los que salieron
    alguna vez en este computador (juego/historial_logros.py)."""
    ancho, alto = screen.get_size()
    screen.fill(COLOR_FONDO_ARBOL)
    es_catalogo = catalogo is not None

    f_titulo = fuente("subtitle")
    titulo = f_titulo.render("Todos los logros" if es_catalogo else "Logros de esta partida",
                             True, COLOR_SELECCION)
    screen.blit(titulo, (32, 20))
    cuenta = f_titulo.render(f"{arbol.obtenidos()}/{arbol.total()}", True, COLOR_TEXTO)
    screen.blit(cuenta, (ancho - cuenta.get_width() - 32, 20))

    alto_info = 104
    area = pygame.Rect(32, 30 + titulo.get_height() + 12, ancho - 64,
                       alto - (30 + titulo.get_height() + 12) - alto_info - 44)
    pos = arbol.posiciones()
    if not pos:
        return {}
    columnas = max(c for c, _ in pos.values()) + 1
    filas = max(f for _, f in pos.values()) + 1
    paso_x = area.width / columnas
    paso_y = area.height / filas
    tam = int(max(14, min(34, paso_y - 6, paso_x * 0.22)))
    f_nombre = fuente_de_tamano(max(10, min(16, int(tam * 0.55))))

    def centro(nodo):
        c, f = pos[nodo]
        return (int(area.x + c * paso_x + tam / 2 + 4), int(area.y + (f + 0.5) * paso_y))

    # Primero se arman las etiquetas (pueden ir en dos líneas si no caben), para
    # que los conectores salgan de donde termina el nombre y no lo tachen.
    maximo = int(paso_x - tam - 34)
    etiquetas = {}
    for nodo in arbol.preorden():
        est = estado(nodo, es_catalogo)
        nombre = nodo.nombre if est != "oculto" else "???"
        color = COLOR_TEXTO if est == "obtenido" else (COLOR_TENUE if est == "visible" else COLOR_OCULTO)
        etiquetas[nodo] = (est, _renglones(nombre, f_nombre, maximo, color))

    def fin_etiqueta(nodo):
        cx, _ = centro(nodo)
        return cx + tam // 2 + 6 + max(r.get_width() for r in etiquetas[nodo][1])

    # Conectores en ángulo: del final del nombre del padre a un codo justo
    # antes de la columna de los hijos, y de ahí a cada hijo.
    for nodo in arbol.preorden():
        if not nodo.hijos:
            continue
        _, py = centro(nodo)
        hx0, _ = centro(nodo.hijos[0])
        codo = hx0 - tam // 2 - 12
        inicio = min(fin_etiqueta(nodo) + 6, codo)
        obtenido_alguno = any(h.obtenido for h in nodo.hijos)
        pygame.draw.line(screen, COLOR_LINEA_OBTENIDA if obtenido_alguno else COLOR_LINEA,
                         (inicio, py), (codo, py), 2)
        for hijo in nodo.hijos:
            hx, hy = centro(hijo)
            color = COLOR_LINEA_OBTENIDA if hijo.obtenido else COLOR_LINEA
            pygame.draw.lines(screen, color, False, [(codo, py), (codo, hy), (hx - tam // 2, hy)], 2)

    rects = {}
    for nodo in arbol.preorden():
        cx, cy = centro(nodo)
        rect = pygame.Rect(0, 0, tam, tam)
        rect.center = (cx, cy)
        est, renglones = etiquetas[nodo]
        _caja_nodo(screen, rect, nodo, est, nodo is seleccionado)
        alto_texto = sum(r.get_height() for r in renglones)
        y = cy - alto_texto // 2
        zona = rect.copy()
        for r in renglones:
            screen.blit(r, (rect.right + 6, y))
            zona.union_ip(r.get_rect(topleft=(rect.right + 6, y)))
            y += r.get_height()
        rects[nodo] = zona

    _info(screen, pygame.Rect(32, alto - alto_info - 36, ancho - 64, alto_info), seleccionado, catalogo)
    pista = fuente_de_tamano(15).render(
        "Flechas: moverse por el árbol (izq: padre, der: hijo)  ·  Esc: volver", True, COLOR_TENUE)
    screen.blit(pista, pista.get_rect(midbottom=(ancho // 2, alto - 10)))
    return rects


def _renglones(texto, f, maximo, color):
    """El nombre en una línea, o en dos si no cabe (partido por una palabra)."""
    if f.size(texto)[0] <= maximo or " " not in texto:
        return [f.render(texto, True, color)]
    palabras = texto.split()
    mejor = None
    for i in range(1, len(palabras)):
        a, b = " ".join(palabras[:i]), " ".join(palabras[i:])
        ancho = max(f.size(a)[0], f.size(b)[0])
        if mejor is None or ancho < mejor[0]:
            mejor = (ancho, a, b)
    return [f.render(mejor[1], True, color), f.render(mejor[2], True, color)]


def _info(screen, caja, nodo, catalogo=None):
    fondo = pygame.Surface(caja.size, pygame.SRCALPHA)
    fondo.fill((24, 24, 44, 230))
    screen.blit(fondo, caja.topleft)
    if nodo is None:
        return
    color = _color(nodo)
    pygame.draw.rect(screen, color, caja, 2, border_radius=6)
    est = estado(nodo, catalogo is not None)
    f1, f2 = fuente_de_tamano(22), fuente_de_tamano(16)
    if est == "oculto":
        nombre = "???"
        desc = (f"Consigue primero «{nodo.padre.nombre}»." if nodo.padre and nodo.padre.visible
                else "Sigue jugando para descubrirlo.")
        abajo = ""
    else:
        nombre, desc = nodo.nombre, nodo.descripcion
        if catalogo is not None:
            veces = catalogo.get(nodo.clave, 0)
            abajo = (f"Conseguido en {veces} partida{'s' if veces != 1 else ''}" if veces
                     else "Todavía no lo consiguen en este computador")
        elif est == "obtenido":
            quien = f"el {nodo.quien}" if nodo.quien else "el equipo"
            abajo = (f"Conseguido por {quien} (al conseguir uno que sale de este)"
                     if nodo.por_camino else f"Conseguido por {quien}")
        else:
            abajo = "Pendiente"
    x, y = caja.x + 16, caja.y + 10
    screen.blit(f1.render(nombre, True, color if est != "oculto" else COLOR_TENUE), (x, y))
    y += f1.get_linesize()
    screen.blit(f2.render(desc, True, COLOR_TEXTO), (x, y))
    y += f2.get_linesize() + 2
    if abajo:
        screen.blit(f2.render(abajo, True, (120, 230, 150) if est == "obtenido" else COLOR_TENUE),
                    (x, y))
