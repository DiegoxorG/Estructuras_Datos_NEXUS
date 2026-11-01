"""Salas selladas: el mapa se achica cuando juegan menos.

Con 2 jugadores se juega en 6 salas, con 3 en 8 y con 4 en 10
(SALAS_POR_JUGADORES). Las salas que sobran se sellan al empezar la ronda:
no se puede entrar, se ven oscuras y con franjas de peligro en la entrada, y
todo lo que había adentro (piezas, notas, escondites, terminales, cajas de
fusibles, pruebas, rutas de aliens...) se quita de la partida.

- Una "sala" es un nombre de la herramienta Salas del editor de mapa (todos
  los rectángulos con ese nombre son la misma sala). Los "Pasillo" no cuentan
  como sala y no se sellan, salvo que queden aislados (todo lo que tocan está
  sellado): entonces se sellan también.
- Siempre quedan abiertas Control (inicio), Prisión, General y Bahía (final)
  (SIEMPRE; si el mapa no tiene alguna, se ignora), y también la sala donde
  esté algo de lo que no puede faltar: el inicio, la cápsula, la puerta de la
  prisión y las celdas.
- Las demás se escogen al azar, pero solo combinaciones que (1) dejen todo lo
  abierto conectado y (2) dejen lo suficiente para la misión (MINIMOS: 3
  piezas, una nota, una consola, las pruebas del infiltrado...).

Para lo (1) se usa un **grafo de salas** (Estructuras/grafo.py, el mismo de
NEXUS): cada rectángulo de sala es un nodo y dos rectángulos que se tocan (hay
una puerta entre ellos) tienen una arista en los dos sentidos. Una combinación
sirve si todos los rectángulos abiertos quedan en la misma componente conexa
que el inicio. Después, por si dos rectángulos se tocan a través de una pared,
se comprueba caminando de verdad (Mundo.area_alcanzable); si falla, se prueba
otra combinación.

El sello es una pared más (Mundo.sellar): el rectángulo de la sala, un poco
más grande para comerse el borde, menos todo lo que esté abierto. Así frena a
jugadores, aliens y prisioneros, tapa la vista y la navegación lo rodea.
"""

import itertools
import random
import unicodedata

import pygame

from Estructuras.grafo import Grafo

# APAGADO (oct 30): el grupo decidió jugar siempre con el mapa entero. Todo
# sigue aquí por si se vuelve a querer: basta con ACTIVO = True.
ACTIVO = False
SALAS_POR_JUGADORES = {1: 6, 2: 6, 3: 8, 4: 10}
SIEMPRE = ("Control", "Prisión", "General", "Bahía")
PASILLO = "Pasillo"
MARGEN = 24          # px del mundo: el sello también tapa el borde de la sala
MARGEN_DIBUJO = 340  # lo oscuro llega más lejos: tapa también las paredes de la sala...
PAREDES_ABIERTAS = 130  # ...pero no las de lo abierto (las de un pasillo van a sus lados)
ALFA_SOMBRA = 225
TOQUE = 8            # rectángulos a menos de esto se tocan (hay una puerta)
FRANJA = 14          # grosor de las franjas de peligro en la entrada
INTENTOS = 6         # combinaciones que se comprueban caminando antes de rendirse
PIEZAS_NECESARIAS = 3   # (misiones/mision.py)

# Lo que tiene que quedar en lo abierto (si el mapa lo tiene). Si el mapa tiene
# menos, basta con lo que tenga.
MINIMOS = {"piezas": PIEZAS_NECESARIAS, "notas": 1, "consolas": 1, "fusibles": 1,
           "nexus": 1, "terminales": 1, "paneles": 1, "escondites": 2}

COLOR_SELLO = (3, 3, 8)
COLOR_PELIGRO = (236, 184, 40)
COLOR_LETRERO = (255, 120, 90)


def clave(nombre):
    """"Prisión", "prision " y "PRISION" son la misma sala."""
    sin_tildes = unicodedata.normalize("NFD", str(nombre))
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn").strip().lower()


def es_pasillo(nombre):
    return clave(nombre) == clave(PASILLO)


def salas_para(n_jugadores):
    return SALAS_POR_JUGADORES.get(n_jugadores, max(SALAS_POR_JUGADORES.values()))


# -- Rectángulos ----------------------------------------------------------------------

def restar(rect, otro):
    """`rect` menos `otro`: hasta 4 rectángulos."""
    corte = rect.clip(otro)
    if corte.width == 0 or corte.height == 0:
        return [rect]
    piezas = []
    if corte.top > rect.top:
        piezas.append(pygame.Rect(rect.left, rect.top, rect.width, corte.top - rect.top))
    if corte.bottom < rect.bottom:
        piezas.append(pygame.Rect(rect.left, corte.bottom, rect.width, rect.bottom - corte.bottom))
    if corte.left > rect.left:
        piezas.append(pygame.Rect(rect.left, corte.top, corte.left - rect.left, corte.height))
    if corte.right < rect.right:
        piezas.append(pygame.Rect(corte.right, corte.top, rect.right - corte.right, corte.height))
    return piezas


def restar_todos(rects, otros):
    for otro in otros:
        rects = [p for r in rects for p in restar(r, otro)]
    return [r for r in rects if r.width > 2 and r.height > 2]


# -- El grafo de salas ---------------------------------------------------------------

def grafo_de_salas(salas):
    """Nodo = índice del rectángulo en `salas` ([(nombre, Rect)]); arista (en
    los dos sentidos) entre los que se tocan."""
    grafo = Grafo()
    for i, (nombre, rect) in enumerate(salas):
        grafo.agregar_nodo(i, nombre=nombre)
    for i, j in itertools.combinations(range(len(salas)), 2):
        if salas[i][1].inflate(TOQUE, TOQUE).colliderect(salas[j][1]):
            grafo.agregar_arista(i, j)
            grafo.agregar_arista(j, i)
    return grafo


def _alcanzables(grafo, abiertos, inicio):
    """Los nodos de `abiertos` a los que se llega desde `inicio` sin pasar
    por uno cerrado (BFS por niveles del grafo)."""
    if inicio not in abiertos:
        return set()
    niveles = grafo.bfs_niveles(inicio, puede_pasar=lambda n: n in abiertos)
    return {n for nivel in niveles for n in nivel if n in abiertos}


def _sala_de(salas, punto):
    """Índice del rectángulo más chico que contiene `punto`, o None."""
    mejor, area = None, None
    for i, (_, rect) in enumerate(salas):
        if rect.collidepoint(punto) and (area is None or rect.width * rect.height < area):
            mejor, area = i, rect.width * rect.height
    return mejor


# -- Dónde está cada cosa del mapa ----------------------------------------------------

def _puntos(objetos, mundo):
    """{parte: [punto en px del mundo de cada objeto]} de lo que se reparte por
    el mapa (lo que se puede quitar)."""
    W, H = mundo.ancho, mundo.alto

    def px(p):
        if isinstance(p, dict):
            return (p["rx"] * W, p["ry"] * H)
        return (p[0] * W, p[1] * H)

    partes = {}
    for parte in ("piezas", "celdas", "notas", "consolas", "consumibles", "nexus", "fusibles",
                  "pruebas", "escondites", "terminales", "paneles", "compuertas"):
        partes[parte] = [px(o) for o in objetos.get(parte) or []]
    return partes


def _fijos(objetos, mundo):
    """Lo que no puede quedar sellado: inicio, cápsula, puerta y celdas."""
    W, H = mundo.ancho, mundo.alto
    puntos = []
    if objetos.get("spawn"):
        puntos.append((objetos["spawn"][0] * W, objetos["spawn"][1] * H))
    else:
        puntos.append((W / 2, H / 2))
    if objetos.get("capsula"):
        puntos.append((objetos["capsula"][0] * W, objetos["capsula"][1] * H))
    for puerta in objetos.get("puertas_codigo") or []:
        puntos.append((puerta["rx"] * W, puerta["ry"] * H))
    puntos += [(c[0] * W, c[1] * H) for c in objetos.get("celdas") or []]
    return puntos


# -- Escoger qué se sella -------------------------------------------------------------

class Sellado:
    """Lo que quedó sellado en esta ronda (vacío si no se selló nada)."""

    def __init__(self, cerradas=(), rects=(), franjas=(), letreros=(), abiertas=(), sombras=()):
        self.cerradas = list(cerradas)     # nombres de las salas selladas
        self.abiertas = list(abiertas)     # nombres de las que se juegan
        self.rects = list(rects)           # las paredes nuevas (px del mundo)
        self.sombras = list(sombras)       # lo que se dibuja oscuro (un poco más grande)
        self.franjas = list(franjas)       # (Rect, horizontal) en la entrada
        self.letreros = list(letreros)     # (nombre, punto)
        self._imagenes = {}

    def __bool__(self):
        return bool(self.rects)


def _evaluar(salas, grafo, nombres, cerradas, inicio, fijos, puntos):
    """(abiertos, ok): los rectángulos que quedan jugables si se sellan
    `cerradas`, y si la combinación sirve."""
    abiertos_nombre = {i for i, (n, _) in enumerate(salas) if clave(n) not in cerradas}
    alcanzados = _alcanzables(grafo, abiertos_nombre, inicio)
    # Toda sala abierta (no pasillo) tiene que quedar conectada.
    for i in abiertos_nombre:
        if not es_pasillo(salas[i][0]) and i not in alcanzados:
            return alcanzados, False

    def abierto(p):
        i = _sala_de(salas, p)
        return i is None or i in alcanzados

    if not all(abierto(p) for p in fijos):
        return alcanzados, False
    for parte, minimo in MINIMOS.items():
        total = len(puntos.get(parte, ()))
        if sum(1 for p in puntos.get(parte, ()) if abierto(p)) < min(minimo, total):
            return alcanzados, False
    if puntos.get("pruebas"):
        from data.infiltrado import PRUEBAS
        total = len(puntos["pruebas"])
        if sum(1 for p in puntos["pruebas"] if abierto(p)) < min(len(PRUEBAS), total):
            return alcanzados, False
    return alcanzados, True


def candidatas(salas, n_jugadores, objetos, mundo, rng=random):
    """Las combinaciones de salas a sellar que sirven, en orden aleatorio:
    [(cerradas, alcanzados)]. [] si no hay que sellar nada (o no se puede)."""
    nombres = {}
    for nombre, _ in salas:
        if not es_pasillo(nombre):
            nombres.setdefault(clave(nombre), nombre)
    meta = salas_para(n_jugadores)
    if len(nombres) <= meta:
        return []
    fijos = _fijos(objetos, mundo)
    inicio = _sala_de(salas, fijos[0])
    if inicio is None:
        return []
    obligadas = {clave(n) for n in SIEMPRE} & set(nombres)
    for p in fijos:
        i = _sala_de(salas, p)
        if i is not None and not es_pasillo(salas[i][0]):
            obligadas.add(clave(salas[i][0]))
    opcionales = sorted(set(nombres) - obligadas)
    cuantas = len(nombres) - meta              # cuántas se sellan
    if cuantas > len(opcionales):
        cuantas = len(opcionales)              # no alcanza: se sella lo que se pueda
    grafo = grafo_de_salas(salas)
    puntos = _puntos(objetos, mundo)
    combinaciones = list(itertools.combinations(opcionales, cuantas))
    rng.shuffle(combinaciones)
    buenas = []
    for cerradas in combinaciones:
        alcanzados, ok = _evaluar(salas, grafo, nombres, set(cerradas), inicio, fijos, puntos)
        if ok:
            buenas.append((set(cerradas), alcanzados))
    return buenas


def _armar(salas, cerradas, alcanzados):
    """El Sellado de una combinación: paredes, franjas y letreros."""
    cerrados = [i for i in range(len(salas)) if i not in alcanzados]
    abiertos = [salas[i][1] for i in alcanzados]
    rects, sombras = [], []
    for i in cerrados:
        rects += restar_todos([salas[i][1].inflate(MARGEN * 2, MARGEN * 2)], abiertos)
        sombras.append(salas[i][1].inflate(MARGEN_DIBUJO * 2, MARGEN_DIBUJO * 2))
    # Lo oscuro no tapa lo abierto ni sus paredes: las de un pasillo van a lo
    # largo (arriba y abajo si es horizontal), las de una sala, alrededor.
    protegidos = []
    for i in alcanzados:
        nombre, a = salas[i]
        if not es_pasillo(nombre):
            protegidos.append(a.inflate(PAREDES_ABIERTAS, PAREDES_ABIERTAS))
        elif a.width >= a.height:
            protegidos.append(a.inflate(0, PAREDES_ABIERTAS * 2))
        else:
            protegidos.append(a.inflate(PAREDES_ABIERTAS * 2, 0))
    # Sin encimarse (si no, donde se pisan dos se ve más oscuro). Lo que es
    # pared siempre se ve oscuro, aunque esté cerca de lo abierto.
    unidas = []
    for r in restar_todos(sombras, protegidos) + rects:
        unidas += restar_todos([r], unidas)
    sombras = unidas
    # Franjas de peligro donde el sello le cierra el paso a algo abierto: de
    # frente y a lo ancho (la entrada), no donde solo lo roza de lado.
    franjas = []
    for r in rects:
        for a in abiertos:
            franja = r.clip(a.inflate(FRANJA * 2, FRANJA * 2))
            if franja.width <= 2 or franja.height <= 2:
                continue
            de_lado = r.right <= a.left + 2 or r.left >= a.right - 2     # a la izquierda o derecha
            if de_lado and franja.height >= 0.6 * a.height:
                franjas.append((franja, False))
            elif not de_lado and franja.width >= 0.6 * a.width:
                franjas.append((franja, True))
    letreros, vistos = [], set()
    for i in sorted(cerrados, key=lambda i: -salas[i][1].width * salas[i][1].height):
        nombre = salas[i][0]
        if clave(nombre) in vistos or es_pasillo(nombre):
            continue
        vistos.add(clave(nombre))
        letreros.append((nombre, salas[i][1].center))
    nombres_abiertos = sorted({salas[i][0] for i in alcanzados if not es_pasillo(salas[i][0])})
    return Sellado(sorted(cerradas), rects, franjas, letreros, nombres_abiertos, sombras)


def _comprobar(mundo, sellado, salas, alcanzados, desde):
    """¿De verdad se llega caminando a todas las salas abiertas?"""
    mundo.sellar(sellado.rects)
    celdas = mundo.area_alcanzable(desde, 34, 20, paso=16)
    for i in alcanzados:
        nombre, rect = salas[i]
        if es_pasillo(nombre):
            continue
        if not any(rect.collidepoint(x + 17, y + 10) for x, y in celdas):
            return False
    return True


def aplicar(objetos, mundo, salas, n_jugadores, rng=random):
    """Escoge qué salas se sellan, pone sus paredes en `mundo` y quita de
    `objetos` lo que quedó adentro. Devuelve el Sellado (también queda en
    `mundo.sellado`, para dibujarlo)."""
    mundo.sellar([])
    sellado = Sellado()
    if not ACTIVO:
        mundo.sellado = sellado
        return sellado
    combinaciones = candidatas(salas, n_jugadores, objetos, mundo, rng)
    desde = _fijos(objetos, mundo)[0]
    for cerradas, alcanzados in combinaciones[:INTENTOS]:
        prueba = _armar(salas, cerradas, alcanzados)
        if _comprobar(mundo, prueba, salas, alcanzados, desde):
            sellado = prueba
            break
    else:
        if combinaciones:
            print("[AVISO] No se pudo sellar ninguna combinación de salas sin dejar algo "
                  "aislado: se juega con todo el mapa.")
        mundo.sellar([])
    mundo.sellado = sellado
    if sellado:
        quitar_lo_sellado(objetos, mundo, sellado)
    return sellado


def quitar_lo_sellado(objetos, mundo, sellado):
    """Quita de `objetos` (en su lugar) lo que quedó dentro de un sello."""
    W, H = mundo.ancho, mundo.alto

    def sellado_en(rx, ry):
        p = (int(rx * W), int(ry * H))
        return any(r.collidepoint(p) for r in sellado.rects)

    for parte in ("piezas", "celdas", "notas", "consolas", "consumibles", "nexus", "fusibles",
                  "pruebas"):
        objetos[parte] = [o for o in objetos.get(parte) or [] if not sellado_en(o[0], o[1])]
    for parte in ("escondites", "terminales", "paneles", "compuertas"):
        objetos[parte] = [o for o in objetos.get(parte) or [] if not sellado_en(o["rx"], o["ry"])]
    # Una puerta para dos con la puerta o un panel adentro ya no se abriría: se quita.
    objetos["puertas_dobles"] = [
        d for d in objetos.get("puertas_dobles") or []
        if not sellado_en(d["rx"], d["ry"]) and not any(sellado_en(x, y) for x, y in d.get("paneles", []))]
    # Las rutas de los aliens pierden los puntos sellados; si no les queda
    # ninguno, ese alien no sale.
    rutas, tipos = [], []
    tipos_viejos = objetos.get("tipos_aliens") or []
    for i, ruta in enumerate(objetos.get("rutas_aliens") or []):
        quedan = [p for p in ruta if not sellado_en(p[0], p[1])]
        if quedan:
            rutas.append(quedan)
            if i < len(tipos_viejos):
                tipos.append(tipos_viejos[i])
    objetos["rutas_aliens"], objetos["tipos_aliens"] = rutas, tipos


# -- Dibujo -----------------------------------------------------------------------------

def _rayas(tam, horizontal):
    """Franjas de peligro (amarillo y negro en diagonal) de tamaño `tam`."""
    img = pygame.Surface(tam)
    img.fill(COLOR_SELLO)
    paso = 16
    alto = tam[1] if horizontal else tam[0]
    for x in range(-tam[1] - tam[0], tam[0] + tam[1], paso):
        pygame.draw.polygon(img, COLOR_PELIGRO, [(x, 0), (x + paso // 2, 0),
                                                 (x + paso // 2 + tam[1], tam[1]), (x + tam[1], tam[1])])
    return img


def dibujar(screen, offset, camara, mundo, tiempo_ms=0):
    """Encima del mapa (antes de todo lo demás): lo sellado oscuro, las
    franjas en las entradas y el letrero de cada sala."""
    sellado = getattr(mundo, "sellado", None)
    if not sellado:
        return
    for i, r in enumerate(sellado.sombras):
        if not r.colliderect(camara):
            continue
        k = ("sombra", i)
        if k not in sellado._imagenes:
            img = pygame.Surface(r.size)
            img.fill(COLOR_SELLO)
            img.set_alpha(ALFA_SOMBRA)
            sellado._imagenes[k] = img
        # Solo el pedazo que se ve.
        visible = r.clip(camara)
        screen.blit(sellado._imagenes[k], (visible.x - offset[0], visible.y - offset[1]),
                    area=visible.move(-r.x, -r.y))
    for franja, horizontal in sellado.franjas:
        if not franja.colliderect(camara):
            continue
        k = ("franja", franja.size, horizontal)
        if k not in sellado._imagenes:
            sellado._imagenes[k] = _rayas(franja.size, horizontal)
        screen.blit(sellado._imagenes[k], franja.move(-offset[0], -offset[1]))
    from juego.fuentes import fuente_de_tamano
    for nombre, punto in sellado.letreros:
        if not camara.inflate(400, 200).collidepoint(punto):
            continue
        k = ("letrero", nombre)
        if k not in sellado._imagenes:
            arriba = fuente_de_tamano(30).render("SALA SELLADA", True, COLOR_LETRERO)
            abajo = fuente_de_tamano(18).render(nombre, True, (200, 200, 215))
            img = pygame.Surface((max(arriba.get_width(), abajo.get_width()) + 24,
                                  arriba.get_height() + abajo.get_height() + 16), pygame.SRCALPHA)
            img.blit(arriba, arriba.get_rect(midtop=(img.get_width() // 2, 6)))
            img.blit(abajo, abajo.get_rect(midtop=(img.get_width() // 2, 10 + arriba.get_height())))
            sellado._imagenes[k] = img
        img = sellado._imagenes[k]
        screen.blit(img, img.get_rect(center=(punto[0] - offset[0], punto[1] - offset[1])))


def oscurecer_miniatura(mini, mundo):
    """Pinta lo sellado en una miniatura del mapa (el minimapa y compañía)."""
    sellado = getattr(mundo, "sellado", None)
    if not sellado:
        return mini
    ex, ey = mini.get_width() / mundo.ancho, mini.get_height() / mundo.alto
    for r in sellado.sombras or sellado.rects:
        pygame.draw.rect(mini, COLOR_SELLO, pygame.Rect(int(r.x * ex), int(r.y * ey),
                                                        max(1, int(r.width * ex) + 1),
                                                        max(1, int(r.height * ey) + 1)))
    return mini


def clave_cache(mundo):
    """Para las cachés de las miniaturas: cambia si cambia lo sellado."""
    sellado = getattr(mundo, "sellado", None)
    return id(sellado) if sellado else None
