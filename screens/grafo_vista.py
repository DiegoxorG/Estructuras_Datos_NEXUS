"""Vista en vivo de los grafos del juego (Pausa > Opciones > Grafo).

En el juego el grafo de NEXUS no se ve a propósito: el celular se ve como una
red social cualquiera. Esta vista es para la sustentación: muestra los grafos
funcionando mientras se juega, igual que la vista del árbol del alien.

Dos vistas:

- **NEXUS** (redes/nexus.py, Estructuras/grafo.py): cada cuenta es un nodo
  (prisioneros, jugadores y bots del Cambiaformas) y cada flecha va de quien
  publica a quien le llega. El color del nodo es lo que cree (verde, gris,
  rojo). Se ve en vivo:
    * la propagación por BFS: el nivel que acaba de recibir la publicación
      parpadea y las flechas por donde le llegó se pintan del color de la
      publicación (rojo un rumor, verde un desmentido, morado una trampa);
    * el camino más corto del último "¿De dónde salió esto?" (amarillo);
    * los bots que se reportaron: su nodo se borra (queda una X un rato);
    * cuántos nodos, aristas y componentes conexas tiene.
  La disposición se calcula con un algoritmo de fuerzas (los nodos se
  repelen y las aristas los atraen) y solo se rehace cuando cambian los nodos.

- **Nave** (juego/navegacion.py): el mapa como grafo de celdas libres. Se ve
  el mapa en chiquito, las celdas que revisó la última búsqueda A*, el camino
  que encontró, y el camino que va siguiendo cada alien y cada prisionero.
"""

import math
import random

import pygame

from juego import salas_selladas
from juego.fuentes import fuente_de_tamano
from screens.paneles import partir_lineas

COLOR_FONDO = (14, 15, 28, 236)
COLOR_BORDE = (120, 132, 190)
COLOR_TITULO = (255, 214, 64)
COLOR_TEXTO = (240, 242, 252)
COLOR_TENUE = (140, 146, 180)
COLOR_ARISTA = (70, 76, 108)
COLOR_NODO = {"verde": (90, 210, 120), "gris": (165, 168, 185), "rojo": (230, 80, 80)}
COLOR_PUB = {"rumor": (240, 90, 80), "compartido": (240, 90, 80), "desmentido": (90, 220, 130),
             "testimonio": (90, 220, 130), "trampa": (190, 120, 255), "normal": (150, 190, 255)}
COLOR_CAMINO = (255, 214, 64)
COLOR_JUGADOR = (120, 190, 255)

RASTREO_VISIBLE_MS = 12000     # cuánto se ve el camino del último rastreo
BORRADO_VISIBLE_MS = 6000      # cuánto se ve la X de un bot borrado


# -- Disposición del grafo de NEXUS ----------------------------------------------------------

_layout = {"nodos": None, "pos": {}}


def _disposicion(grafo):
    """Posición (0-1, 0-1) de cada nodo, con un algoritmo de fuerzas
    (Fruchterman-Reingold). Se rehace solo si cambian los nodos, partiendo
    de las posiciones anteriores para que el dibujo no salte."""
    nodos = sorted(grafo.nodos(), key=str)
    if _layout["nodos"] == nodos:
        return _layout["pos"]
    rng = random.Random(7)
    anterior = _layout["pos"]
    pos = {}
    for i, n in enumerate(nodos):
        if n in anterior:
            pos[n] = list(anterior[n])
        else:
            a = 2 * math.pi * i / max(1, len(nodos))
            pos[n] = [0.5 + 0.35 * math.cos(a) + rng.uniform(-0.03, 0.03),
                      0.5 + 0.35 * math.sin(a) + rng.uniform(-0.03, 0.03)]
    aristas = [(a, b) for a in nodos for b in grafo.vecinos(a) if b in pos]
    k = 0.9 / math.sqrt(max(1, len(nodos)))
    iteraciones = 120 if not anterior else 50
    temp = 0.08
    for _ in range(iteraciones):
        mov = {n: [0.0, 0.0] for n in nodos}
        for i, a in enumerate(nodos):
            for b in nodos[i + 1:]:
                dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
                d = math.hypot(dx, dy) or 0.001
                f = k * k / d
                mov[a][0] += dx / d * f; mov[a][1] += dy / d * f
                mov[b][0] -= dx / d * f; mov[b][1] -= dy / d * f
        for a, b in aristas:
            dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
            d = math.hypot(dx, dy) or 0.001
            f = d * d / k
            mov[a][0] -= dx / d * f; mov[a][1] -= dy / d * f
            mov[b][0] += dx / d * f; mov[b][1] += dy / d * f
        for n in nodos:
            mx, my = mov[n]
            d = math.hypot(mx, my) or 0.001
            paso = min(d, temp)
            pos[n][0] = min(0.95, max(0.05, pos[n][0] + mx / d * paso))
            pos[n][1] = min(0.95, max(0.05, pos[n][1] + my / d * paso))
        temp *= 0.96
    # Se guardan también los de antes que ya no están (para dibujar su X).
    guardado = dict(anterior)
    guardado.update({n: tuple(p) for n, p in pos.items()})
    _layout["nodos"], _layout["pos"] = nodos, guardado
    return guardado


# -- Dibujo ------------------------------------------------------------------------------

def _panel(screen, titulo):
    ancho, alto = screen.get_size()
    panel = pygame.Rect(0, 0, min(ancho - 40, 1700), min(alto - 40, 940))
    panel.center = (ancho // 2, alto // 2)
    capa = pygame.Surface(panel.size, pygame.SRCALPHA)
    capa.fill(COLOR_FONDO)
    screen.blit(capa, panel.topleft)
    pygame.draw.rect(screen, COLOR_BORDE, panel, 2)
    f = fuente_de_tamano(max(16, min(24, panel.width // 48)))
    screen.blit(f.render(titulo, True, COLOR_TITULO), (panel.x + 18, panel.y + 12))
    return panel, panel.y + 12 + f.get_linesize() + 6


def _flecha(screen, color, a, b, radio_b, grosor=1):
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = math.hypot(dx, dy)
    if d < radio_b + 4:
        return
    ux, uy = dx / d, dy / d
    fin = (b[0] - ux * (radio_b + 2), b[1] - uy * (radio_b + 2))
    pygame.draw.line(screen, color, a, fin, grosor)
    tam = 5 + grosor
    izq = (fin[0] - ux * tam - uy * tam * 0.6, fin[1] - uy * tam + ux * tam * 0.6)
    der = (fin[0] - ux * tam + uy * tam * 0.6, fin[1] - uy * tam - ux * tam * 0.6)
    pygame.draw.polygon(screen, color, [fin, izq, der])


def _columna_texto(screen, x, y, ancho, lineas, f):
    for color, texto in lineas:
        if not texto:
            y += f.get_linesize() // 2
            continue
        for renglon in partir_lineas(texto, f, ancho):
            screen.blit(f.render(renglon, True, color), (x, y))
            y += f.get_linesize()
    return y


def render_grafo_nexus(screen, red):
    if red is None:
        return
    panel, y0 = _panel(screen, "Grafo de NEXUS (en vivo)")
    grafo = red.grafo
    info_ancho = min(330, panel.width // 3)
    area = pygame.Rect(panel.x + 12, y0, panel.width - info_ancho - 36, panel.bottom - y0 - 12)
    pos = _disposicion(grafo)
    t = red.tiempo_ms
    ahora = pygame.time.get_ticks()

    def punto(n):
        x, y = pos[n]
        return (int(area.x + x * area.width), int(area.y + y * area.height))

    radio = max(7, min(13, area.width // 70))
    f_nodo = fuente_de_tamano(11)

    # Aristas normales.
    for a in grafo.nodos():
        for b in grafo.vecinos(a):
            _flecha(screen, COLOR_ARISTA, punto(a), punto(b), radio)

    # Propagaciones activas: el árbol BFS por donde va llegando cada una.
    frontera = {}
    for prop in red.propagaciones:
        pub = prop.pub
        color = COLOR_PUB.get(pub.tipo, COLOR_TEXTO)
        for nodo, de_quien in pub.via.items():
            if nodo in grafo and de_quien in grafo and nodo != de_quien:
                _flecha(screen, color, punto(de_quien), punto(nodo), radio, 3)
        for n in prop.frontera:
            if n in grafo:
                frontera[n] = color

    # Camino más corto del último rastreo.
    if red.ultimo_rastreo is not None and t - red.ultimo_rastreo[1] < RASTREO_VISIBLE_MS:
        camino = [n for n in red.ultimo_rastreo[0] if n in pos]
        for a, b in zip(camino, camino[1:]):
            _flecha(screen, COLOR_CAMINO, punto(a), punto(b), radio, 4)

    # Nodos.
    rumores = red.rumores_activos()
    for n in grafo.nodos():
        datos = grafo.datos[n]
        c = punto(n)
        tipo = datos["tipo"]
        relleno = COLOR_NODO.get(datos.get("color"), COLOR_NODO["gris"])
        r = radio + (3 if tipo == "jugador" else 0)
        if n in frontera:
            pulso = 4 + int(3 * math.sin(ahora / 120))
            pygame.draw.circle(screen, frontera[n], c, r + pulso, 2)
        pygame.draw.circle(screen, relleno, c, r)
        if tipo == "jugador":
            pygame.draw.circle(screen, COLOR_JUGADOR, c, r, 3)
        elif tipo == "bot":
            pygame.draw.circle(screen, (40, 10, 10), c, r, 3)
            pygame.draw.line(screen, (40, 10, 10), (c[0] - r // 2, c[1]), (c[0] + r // 2, c[1]), 2)
        else:
            pygame.draw.circle(screen, (20, 20, 30), c, r, 1)
        if any(n in p.alcanzados for p in rumores):
            pygame.draw.circle(screen, COLOR_PUB["rumor"], (c[0] + r - 2, c[1] - r + 2), 3)
        etiqueta = datos.get("usuario", n)
        img = f_nodo.render(etiqueta, True, COLOR_JUGADOR if tipo == "jugador" else COLOR_TENUE)
        screen.blit(img, img.get_rect(midtop=(c[0], c[1] + r + 2)))

    # Bots borrados hace poco (eliminar_nodo).
    for nodo, usuario, cuando in red.borrados:
        if t - cuando < BORRADO_VISIBLE_MS and nodo in pos:
            c = punto(nodo)
            pygame.draw.line(screen, COLOR_NODO["rojo"], (c[0] - radio, c[1] - radio), (c[0] + radio, c[1] + radio), 3)
            pygame.draw.line(screen, COLOR_NODO["rojo"], (c[0] - radio, c[1] + radio), (c[0] + radio, c[1] - radio), 3)
            img = f_nodo.render(f"{usuario} (borrado)", True, COLOR_NODO["rojo"])
            screen.blit(img, img.get_rect(midtop=(c[0], c[1] + radio + 2)))

    # Columna de información.
    f = fuente_de_tamano(max(12, min(16, panel.width // 80)))
    x = area.right + 18
    verde, rojo = red.barras()
    presos = len(red._presos())
    lineas = [
        (COLOR_TEXTO, f"Nodos: {len(grafo)}   Aristas: {grafo.aristas()}"),
        (COLOR_TEXTO, f"Componentes conexas: {len(grafo.componentes())}"),
        (COLOR_TEXTO, f"Prisioneros: {presos}   Bots: {len(red.bots())}"),
        (COLOR_NODO["verde"], f"Verdes: {int(verde * 100)}%  (planos al {int(red.umbral_planos * 100)}%)"),
        (COLOR_NODO["rojo"], f"Rojos: {int(rojo * 100)}%"),
        (None, ""),
        (COLOR_TITULO, "Publicaciones viajando (BFS)"),
    ]
    if red.propagaciones:
        for prop in red.propagaciones[:5]:
            pub = prop.pub
            lineas.append((COLOR_PUB.get(pub.tipo, COLOR_TEXTO),
                           f"{pub.tipo} de {red.usuario(pub.autor)}: nivel {prop.niveles}, "
                           f"le llegó a {len(pub.alcanzados)}"))
    else:
        lineas.append((COLOR_TENUE, "Ninguna en este momento."))
    lineas += [
        (None, ""),
        (COLOR_TITULO, "Qué se ve"),
        (COLOR_TENUE, "Nodo = cuenta; flecha = a quién le llega lo que publica. "
                      "Borde azul: jugador. Raya negra: bot del Cambiaformas. "
                      "Punto rojo: le llegó un rumor."),
        (COLOR_PUB["rumor"], "Rumor avanzando un nivel por tick (BFS): solo lo reenvían los rojos."),
        (COLOR_PUB["desmentido"], "Desmentido: lo reenvían los verdes."),
        (COLOR_CAMINO, "Amarillo: camino más corto del último \"¿De dónde salió esto?\"."),
        (COLOR_NODO["rojo"], "X: bot reportado (se borra el nodo y sus aristas)."),
    ]
    _columna_texto(screen, x, y0, panel.right - x - 14, lineas, f)


# -- Grafo de la nave -------------------------------------------------------------------------

_mapa_chico = {}


def render_grafo_nave(screen, mundo, aliens=(), npcs=(), jugadores=()):
    if mundo is None:
        return
    from juego import navegacion
    panel, y0 = _panel(screen, "Grafo de la nave: celdas libres y A* (en vivo)")
    info_ancho = min(320, panel.width // 3)
    area = pygame.Rect(panel.x + 12, y0, panel.width - info_ancho - 36, panel.bottom - y0 - 12)
    escala = min(area.width / mundo.ancho, area.height / mundo.alto)
    tam = (int(mundo.ancho * escala), int(mundo.alto * escala))
    origen = (area.x + (area.width - tam[0]) // 2, area.y + (area.height - tam[1]) // 2)
    nav = navegacion.de_mundo(mundo, 34, 20)

    clave = (id(mundo), tam, id(nav))
    if clave not in _mapa_chico:
        img = salas_selladas.oscurecer_miniatura(pygame.transform.smoothscale(mundo.imagen, tam), mundo)
        oscuro = pygame.Surface(tam)
        oscuro.fill((95, 95, 110))
        img.blit(oscuro, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        # Cada celda libre (nodo del grafo) como un puntito.
        puntos = pygame.Surface(tam, pygame.SRCALPHA)
        for cx, cy in nav.libre:
            x = int((cx + nav.ancho / 2) * escala)
            y = int((cy + nav.alto / 2) * escala)
            if 0 <= x < tam[0] and 0 <= y < tam[1]:
                puntos.set_at((x, y), (120, 200, 255, 140))
        img.blit(puntos, (0, 0))
        _mapa_chico.clear()
        _mapa_chico[clave] = img
    screen.blit(_mapa_chico[clave], origen)

    def a_pantalla(p):
        return (int(origen[0] + p[0] * escala), int(origen[1] + p[1] * escala))

    # La última búsqueda A*: las celdas que revisó y el camino que salió.
    ultima = navegacion.Navegacion.ultima_busqueda
    explorados = 0
    if ultima is not None and ultima.get("nav") is not None:
        n = ultima["nav"]
        explorados = len(ultima["explorados"])
        capa = pygame.Surface(tam, pygame.SRCALPHA)
        lado = max(1, int(n.paso * escala))
        for cx, cy in ultima["explorados"]:
            capa.fill((255, 214, 64, 70), (int((cx + n.ancho / 2) * escala) - lado // 2,
                                          int((cy + n.alto / 2) * escala) - lado // 2, lado, lado))
        screen.blit(capa, origen)
        camino = ultima.get("camino") or []
        if camino:
            puntos = [a_pantalla(ultima["desde"])] + [a_pantalla(p) for p in camino]
            if len(puntos) >= 2:
                pygame.draw.lines(screen, COLOR_CAMINO, False, puntos, 3)

    # Caminos que van siguiendo ahora.
    for npc in npcs:
        ruta = getattr(npc, "ruta", None)
        if ruta:
            puntos = [a_pantalla(npc.centro)] + [a_pantalla(p) for p in ruta]
            pygame.draw.lines(screen, COLOR_NODO["verde"], False, puntos, 1)
        pygame.draw.circle(screen, COLOR_NODO["verde"], a_pantalla(npc.centro), 3)
    for alien in aliens:
        ruta = getattr(alien, "ruta_ruido", None)
        if ruta:
            puntos = [a_pantalla(alien.centro)] + [a_pantalla(p) for p in ruta]
            pygame.draw.lines(screen, COLOR_NODO["rojo"], False, puntos, 2)
        disfrazado = getattr(alien, "disfrazado", False)
        pygame.draw.circle(screen, (190, 120, 255) if disfrazado else COLOR_NODO["rojo"],
                           a_pantalla(alien.centro), 5)
    for j in jugadores:
        if getattr(j, "eliminado", False):
            continue
        pygame.draw.circle(screen, COLOR_JUGADOR, a_pantalla(j.hitbox.center), 5)
        pygame.draw.circle(screen, (10, 10, 20), a_pantalla(j.hitbox.center), 5, 1)

    f = fuente_de_tamano(max(12, min(16, panel.width // 80)))
    x = area.right + 18
    vecinos = nav._vecinos()
    aristas = sum(len(v) for v in vecinos.values())
    nav._componentes()
    componentes = len(nav._celdas_comp)
    lineas = [
        (COLOR_TEXTO, f"Nodos (celdas libres de {nav.paso} px): {len(nav.libre)}"),
        (COLOR_TEXTO, f"Aristas (8 vecinas, sin cortar esquinas): {aristas}"),
        (COLOR_TEXTO, f"Zonas separadas por paredes (componentes): {componentes}"),
        (COLOR_TEXTO, f"Caminos guardados: {len(nav._guardados)}"),
        (COLOR_CAMINO, f"Última búsqueda A*: revisó {explorados} celdas"),
        (None, ""),
        (COLOR_TITULO, "Qué se ve"),
        (COLOR_TENUE, "Puntos azules: cada celda libre es un nodo del grafo."),
        (COLOR_CAMINO, "Amarillo: lo que revisó la última búsqueda A* y el camino que encontró."),
        (COLOR_NODO["rojo"], "Rojo: aliens y el camino que siguen hacia un ruido."),
        ((190, 120, 255), "Morado: el Cambiaformas disfrazado."),
        (COLOR_NODO["verde"], "Verde: prisioneros y su camino."),
        (COLOR_JUGADOR, "Azul: jugadores."),
        (None, ""),
        (COLOR_TENUE, "A* es un BFS que primero prueba las celdas que van hacia la meta: "
                      "revisa muchas menos que un BFS normal y el camino sale igual de bueno."),
    ]
    _columna_texto(screen, x, y0, panel.right - x - 14, lineas, f)
