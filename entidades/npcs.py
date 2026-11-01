"""Los prisioneros que caminan por la nave.

Cada uno es una cuenta de NEXUS (el mismo nodo del grafo de nexus.py): su
color en la red decide cómo trata a los jugadores cuando pasan cerca.

- verde (confía en ustedes): les da una pista (dónde vio un alien, que tal
  prisionero "anda raro", que verifiquen un rumor).
- gris: charla sin importancia.
- rojo (le cree a los aliens): a veces grita dónde está el jugador y el alien
  más cercano va para allá.

Caminan de un punto de interés a otro (consolas, terminales, escondites...)
buscando el camino con el BFS de navegacion.py. No chocan con los jugadores.

El Cambiaformas (cambiaformas.py) se disfraza de uno de ellos: usa la misma
apariencia (Apariencia) y el mismo letrero con el nombre, pero no habla y su
nombre falla de vez en cuando.

Aspecto: los sprites de Imagenes/Prisioneros/<carpeta>/ (de Joseph), uno por
carpeta, repartidos entre los que caminan. Si no hay ninguno, un muñeco simple
dibujado con formas (data/npcs.ESTILOS). Nunca los de los jugadores.
"""

import math
import os
import random
import zlib

import pygame

from juego import navegacion
from juego.fuentes import fuente_de_tamano
from Movimiento.Personaje import DireccionSuave, detectar_hojas, cargar_animaciones
from data.npcs import (ESTILOS, VELOCIDAD_NPC, ESPERA_NPC_MS, RADIO_CHARLA,
                       ENFRIAMIENTO_CHARLA_MS, DURACION_BURBUJA_MS, PROB_DELATAR,
                       FRASES_VERDE_ALIEN, FRASES_VERDE_CAMBIAFORMAS, FRASES_VERDE_RUMOR,
                       FRASES_VERDE, FRASES_GRIS, FRASES_ROJO, RADIO_HABLAR, DISTANCIA_SEGUIR,
                       RADIO_RESCATE_CAPSULA, PUNTOS_RESCATE, FRASE_PIDE_RESCATE, FRASE_ACEPTA, FRASE_DUDA,
                       FRASE_NIEGA, FRASE_RESCATADO, FRASES_ADVIERTE_ESCOLTA,
                       FRASE_ESPERA, RADIO_SOLTAR, ESPERA_SOLTADO_MS)

LIENZO_W, LIENZO_H, ESCALA = 48, 72, 2    # el muñeco se dibuja a 48x72 y se agranda x2
COLOR_ESTADO = {"verde": (90, 210, 120), "gris": (170, 172, 185), "rojo": (230, 80, 80)}
ANCHO_HITBOX, ALTO_HITBOX = 34, 20

_poses = {}       # (estilo, número, dirección, paso) -> (imagen agrandada, alto de la cabeza)
_carteles = {}    # letrero -> imagen con su fondo

# Sprites de los prisioneros: una carpeta por prisionero en
# Imagenes/Prisioneros/ con el formato de PixelLab
# (<carpeta>_<idle|breathing|walking>_<direccion>.png). Para agregar uno basta
# con poner su carpeta ahí: se reparten solos entre los que caminan.
_RAIZ_PROYECTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA_PRISIONEROS = os.path.join(_RAIZ_PROYECTO, "Imagenes", "Prisioneros")
ESCALA_SPRITE = 1.65       # la de los jugadores: cuadros de 96 px, figura de ~60
FPS_SPRITE = 8
_sprites = {}     # carpeta -> {"animaciones", "pie", "arriba"} o None


def carpetas_prisioneros():
    """Las carpetas de Imagenes/Prisioneros/ que tienen sprites, en orden."""
    if not os.path.isdir(CARPETA_PRISIONEROS):
        return []
    return sorted(c for c in os.listdir(CARPETA_PRISIONEROS)
                  if detectar_hojas(os.path.join(CARPETA_PRISIONEROS, c)))


def sprites_prisionero(carpeta):
    """Animaciones de esa carpeta (se cargan una sola vez), o None."""
    if carpeta in _sprites:
        return _sprites[carpeta]
    if not carpeta or pygame.display.get_surface() is None:
        return None
    resultado = None
    animaciones = cargar_animaciones(os.path.join(CARPETA_PRISIONEROS, carpeta),
                                     escala=ESCALA_SPRITE, ancho_ratio=1.0)
    muestra = (animaciones.get("idle", {}).get("south") or [None])[0]
    if muestra is not None:
        contenido = muestra.get_bounding_rect()
        resultado = {"animaciones": animaciones,
                     "pie": muestra.get_height() - contenido.bottom,   # aire bajo los pies
                     "arriba": contenido.top}                           # aire sobre la cabeza
    _sprites[carpeta] = resultado
    return resultado


VECINOS_PASEO = 6     # entre cuántos puntos cercanos escoge a dónde ir


class Apariencia:
    """Cómo se ve un prisionero: su sprite (o, si no tiene, un muñeco simple
    dibujado con formas), su letrero y su burbuja.

    `sprite` es una carpeta de Imagenes/Prisioneros/ (o None). `estilo` es uno
    de data/npcs.ESTILOS: color del overol, piel y pelo del muñeco. El
    Cambiaformas se disfraza copiando todo eso y el usuario de un prisionero.
    """

    ALTO = 66

    def __init__(self, estilo, usuario, numero=0, sprite=None):
        self.estilo, self.usuario = estilo, usuario
        self.numero = numero        # el número del overol
        self.sprite = sprite
        # Reloj propio para la animación: solo avanza cuando el juego se
        # actualiza (en la pausa no respiran). Arranca desfasado para que no
        # respiren todos a la vez.
        self.reloj_ms = zlib.crc32(usuario.encode()) % 1000
        self.direccion = "south"
        self.fase = 0.0             # para el balanceo al caminar
        self.moviendose = False
        self._giro = DireccionSuave()

    def animar(self, dx, dy, dt=0):
        self.reloj_ms += dt
        self.direccion = self._giro.actualizar(dx, dy)
        self.moviendose = self._giro.moviendose
        if self.moviendose:
            self.fase += 0.28
        else:
            self.fase = 0.0

    def _paso(self):
        # Entero: así hay pocas poses distintas y se pueden guardar ya dibujadas.
        return round(math.sin(self.fase) * 5) if self.moviendose else 0

    def _cuerpo(self, screen, x, pies):
        e = self.estilo
        overol, piel, pelo = e["overol"], e["piel"], e["pelo"]
        oscuro = tuple(max(0, c - 50) for c in overol)
        paso = self._paso()
        mira = self.direccion
        de_lado = "east" in mira or "west" in mira
        hacia = 1 if "east" in mira else (-1 if "west" in mira else 0)
        de_espaldas = mira.startswith("north")

        sombra = pygame.Rect(0, 0, 30, 9)
        sombra.center = (x, pies)
        pygame.draw.ellipse(screen, (12, 12, 20), sombra)
        # Piernas y zapatos.
        for lado, desfase in ((-1, paso), (1, -paso)):
            pierna = pygame.Rect(0, 0, 8, 18)
            pierna.midbottom = (x + lado * 5 + (desfase if de_lado else 0), pies - 2 - (0 if de_lado else abs(desfase) * 0.4))
            pygame.draw.rect(screen, oscuro, pierna, border_radius=3)
            zapato = pygame.Rect(0, 0, 10, 5)
            zapato.midtop = (pierna.centerx + hacia * 2, pierna.bottom - 3)
            pygame.draw.rect(screen, (40, 36, 40), zapato, border_radius=2)
        # Torso (overol).
        torso = pygame.Rect(0, 0, 26, 26)
        torso.midbottom = (x, pies - 16)
        pygame.draw.rect(screen, overol, torso, border_radius=7)
        pygame.draw.rect(screen, oscuro, torso, 2, border_radius=7)
        if not de_espaldas and not de_lado:
            num = fuente_de_tamano(10).render(str(self.numero), True, (250, 250, 250))
            screen.blit(num, num.get_rect(center=(x, torso.centery + 2)))
        # Brazos.
        for lado, desfase in ((-1, -paso), (1, paso)):
            hombro = (x + lado * 12, torso.y + 6)
            mano = (x + lado * 14 + (desfase if de_lado else 0), torso.bottom - 2 + (0 if de_lado else desfase * 0.5))
            pygame.draw.line(screen, overol, hombro, mano, 6)
            pygame.draw.circle(screen, piel, (int(mano[0]), int(mano[1])), 3)
        # Cabeza.
        centro = (x + hacia * 2, torso.y - 9)
        pygame.draw.circle(screen, piel, centro, 11)
        tipo = e["tipo_pelo"]
        if tipo == "gorro":
            pygame.draw.ellipse(screen, oscuro, (centro[0] - 12, centro[1] - 13, 24, 13))
        elif tipo != "calvo":
            pygame.draw.ellipse(screen, pelo, (centro[0] - 11, centro[1] - 12, 22, 12))
            if tipo == "largo":
                pygame.draw.rect(screen, pelo, (centro[0] - 11, centro[1] - 5, 5, 13), border_radius=2)
                pygame.draw.rect(screen, pelo, (centro[0] + 6, centro[1] - 5, 5, 13), border_radius=2)
        if de_espaldas:
            if tipo not in ("calvo",):
                pygame.draw.circle(screen, pelo if tipo != "gorro" else oscuro, centro, 10)
        else:
            for ojo in ((-4, 0), (4, 0)) if not de_lado else ((hacia * 5, 0),):
                pygame.draw.circle(screen, (30, 30, 40), (centro[0] + ojo[0], centro[1] + 1), 2)
        return centro[1] - 14

    def dibujar(self, screen, centro_pies, offset, letrero=None, color_estado=None, burbuja=None):
        datos = sprites_prisionero(self.sprite) if self.sprite else None
        cabeza = self._dibujar_sprite(screen, centro_pies, offset, datos) if datos else None
        if cabeza is None:
            cabeza = self._dibujar_muneco(screen, centro_pies, offset)
        if letrero:
            cartel = _carteles.get(letrero)
            if cartel is None:
                if len(_carteles) > 200:
                    _carteles.clear()
                img = fuente_de_tamano(12).render(letrero, True, (235, 236, 245))
                cartel = pygame.Surface((img.get_width() + 18, img.get_height() + 4), pygame.SRCALPHA)
                cartel.fill((10, 10, 20, 150))
                cartel.blit(img, (14, 2))
                _carteles[letrero] = cartel
            caja = cartel.get_rect(midbottom=(cabeza[0], cabeza[1] + 2))
            screen.blit(cartel, caja.topleft)
            if color_estado:
                pygame.draw.circle(screen, color_estado, (caja.x + 7, caja.centery), 3)
            cabeza = (cabeza[0], caja.y - 2)
        if burbuja:
            _burbuja(screen, cabeza, burbuja)

    def _dibujar_sprite(self, screen, centro_pies, offset, datos):
        """Dibuja el cuadro que toca y devuelve dónde queda la cabeza (o None
        si a esa animación le falta la dirección)."""
        estado = "walking" if self.moviendose else "breathing"
        frames = datos["animaciones"].get(estado, {}).get(self.direccion) or []
        if not frames:
            return None
        cuadro = int(self.reloj_ms / (1000 / FPS_SPRITE)) % len(frames)
        imagen = frames[cuadro]
        x = int(centro_pies[0] - offset[0])
        pies = int(centro_pies[1] - offset[1] + 6)      # mismo suelo que el muñeco
        sombra = pygame.Rect(0, 0, 34, 10)
        sombra.center = (x, pies)
        pygame.draw.ellipse(screen, (12, 12, 20), sombra)
        rect = imagen.get_rect(midbottom=(x, pies + datos["pie"]))
        screen.blit(imagen, rect)
        return (x, rect.y + datos["arriba"] - 2)

    def _dibujar_muneco(self, screen, centro_pies, offset):
        """El muñeco de formas (sin sprite). Devuelve dónde queda la cabeza."""
        # Se dibuja chico y se agranda (pixelado) para que mida como los
        # jugadores. Cada pose queda guardada: redibujarla con formas en cada
        # cuadro (y en cada pantalla) era de lo más caro del dibujo.
        clave = (tuple(sorted(self.estilo.items())), self.numero, self.direccion, self._paso())
        pose = _poses.get(clave)
        if pose is None:
            lienzo = pygame.Surface((LIENZO_W, LIENZO_H), pygame.SRCALPHA)
            arriba = self._cuerpo(lienzo, LIENZO_W // 2, LIENZO_H - 6)
            pose = _poses[clave] = (pygame.transform.scale(lienzo, (LIENZO_W * ESCALA, LIENZO_H * ESCALA)),
                                    arriba)
        grande, arriba = pose
        x = int(centro_pies[0] - offset[0])
        pies = int(centro_pies[1] - offset[1] + 6)
        screen.blit(grande, (x - LIENZO_W * ESCALA // 2, pies - (LIENZO_H - 6) * ESCALA))
        return (x, pies - (LIENZO_H - 6 - arriba) * ESCALA - 2)


def _burbuja(screen, punta, texto):
    from screens.paneles import partir_lineas
    f = fuente_de_tamano(13)
    lineas = partir_lineas(texto, f, 230)
    ancho = max(f.size(l)[0] for l in lineas) + 16
    alto = f.get_linesize() * len(lineas) + 10
    caja = pygame.Rect(0, 0, ancho, alto)
    caja.midbottom = (punta[0], punta[1] - 8)
    pygame.draw.rect(screen, (250, 250, 255), caja, border_radius=8)
    pygame.draw.rect(screen, (40, 40, 60), caja, 2, border_radius=8)
    pygame.draw.polygon(screen, (250, 250, 255), [(punta[0] - 6, caja.bottom - 1),
                                                   (punta[0] + 6, caja.bottom - 1),
                                                   (punta[0], caja.bottom + 7)])
    y = caja.y + 5
    for linea in lineas:
        screen.blit(f.render(linea, True, (25, 25, 40)), (caja.x + 8, y))
        y += f.get_linesize()


def direccion_texto(desde, hasta):
    """"norte", "sureste"... de un punto a otro (y crece hacia abajo)."""
    dx, dy = hasta[0] - desde[0], hasta[1] - desde[1]
    angulo = math.degrees(math.atan2(-dy, dx)) % 360
    nombres = ["este", "noreste", "norte", "noroeste", "oeste", "suroeste", "sur", "sureste"]
    return nombres[int((angulo + 22.5) // 45) % 8]


class NPC:
    """Un prisionero que camina. `nodo` es su cuenta en NEXUS."""

    def __init__(self, nodo, usuario, apariencia, punto, rng):
        self.nodo, self.usuario = nodo, usuario
        self.apariencia = apariencia
        self.hitbox = pygame.Rect(0, 0, ANCHO_HITBOX, ALTO_HITBOX)
        self.hitbox.center = punto
        self.rng = rng
        self.ruta = []
        self.espera_ms = rng.uniform(*ESPERA_NPC_MS)
        self.burbuja, self.burbuja_ms = None, 0
        self.charla_ms = rng.uniform(0, 6000)
        self.atascado_ms = 0
        self._resto = [0.0, 0.0]
        self.siguiendo = None       # el jugador que lo lleva a la cápsula
        self.lejos_ms = 0

    @property
    def centro(self):
        return self.hitbox.center

    def decir(self, texto):
        self.burbuja, self.burbuja_ms = texto, DURACION_BURBUJA_MS

    def actualizar(self, dt, juego, puntos):
        self.burbuja_ms = max(0, self.burbuja_ms - dt)
        self.charla_ms = max(0, self.charla_ms - dt)
        antes = self.hitbox.center
        if self.siguiendo is not None:
            self._seguir(dt, juego)
        else:
            caminar(self, dt, juego, puntos, VELOCIDAD_NPC)
        self.apariencia.animar(self.hitbox.centerx - antes[0], self.hitbox.centery - antes[1], dt)

    def _seguir(self, dt, juego):
        """Va detrás de quien lo lleva. Si lo pierde (o lo atrapan), se queda."""
        guia = self.siguiendo
        if guia.preso or getattr(guia, "eliminado", False):
            self.siguiendo = None
            self.decir("¡Lo atraparon! Me quedo aquí...")
            return
        d = math.dist(self.centro, guia.hitbox.center)
        self.lejos_ms = self.lejos_ms + dt if d > 450 else 0
        if self.lejos_ms > 4000:
            self.siguiendo = None
            self.decir("¡Espérame! ...me perdí.")
            return
        if d > DISTANCIA_SEGUIR:
            if not self.ruta or math.dist(self.ruta[-1], guia.hitbox.center) > 80:
                nav = navegacion.de_mundo(juego.mundo, self.hitbox.width, self.hitbox.height)
                self.ruta = list(nav.camino(self.centro, guia.hitbox.center, parcial=True, sellos=False,
                                            puede_esperar=True) or [])
                self.espera_ms = 0
            if self.ruta:
                caminar(self, dt, juego, [guia.hitbox.center], 3.4)
        else:
            self.ruta = []

    def dibujar(self, screen, offset):
        color = None
        juego = getattr(self, "juego", None)
        red = getattr(juego, "nexus", None) if juego is not None else None
        if red is not None and self.nodo in red.grafo:
            color = COLOR_ESTADO.get(red.color(self.nodo))
        self.apariencia.dibujar(screen, self.hitbox.center, offset, self.usuario, color,
                                self.burbuja if self.burbuja_ms > 0 else None)


def caminar(quien, dt, juego, puntos, velocidad, choca=None):
    """Camina de un punto de interés a otro con BFS; espera un rato en cada uno.

    `choca` es con qué se choca (por defecto `mundo.colisiona_npc`: paredes,
    puerta del código y puertas para dos cerradas; el Cambiaformas pasa las de
    los aliens, que además incluyen los sellos del Forjador)."""
    if quien.espera_ms > 0:
        quien.espera_ms -= dt
        return
    mundo = juego.mundo
    if not quien.ruta:
        # A uno de los puntos más cercanos (no al otro lado de la nave): así
        # pasea como alguien de verdad y el camino sale barato de calcular.
        destino = getattr(quien, "destino_paseo", None)
        if destino is None:
            cerca = sorted(puntos, key=lambda p: math.dist(p, quien.hitbox.center))[1:VECINOS_PASEO + 1]
            destino = quien.rng.choice(cerca or puntos)
        nav = navegacion.de_mundo(mundo, quien.hitbox.width, quien.hitbox.height)
        # Los prisioneros cruzan los sellos del Forjador (son para los aliens);
        # el Cambiaformas, que pasa su propio `choca`, no. Un camino largo se
        # busca de a pedazos en varios cuadros (por_partes): mientras tanto
        # espera, y vuelve a pedir el mismo destino.
        camino = nav.camino(quien.hitbox.center, destino, puede_esperar=True, sellos=choca is not None,
                            por_partes=True, quien=id(quien))
        if not camino:
            # Sin camino, espera un rato; si solo era su turno, poquito.
            quien.destino_paseo = destino if nav.ocupada else None
            quien.espera_ms = 50 if nav.ocupada else 400
            return
        quien.destino_paseo = None
        quien.ruta = list(camino)
    objetivo = quien.ruta[0]
    dx, dy = objetivo[0] - quien.hitbox.centerx, objetivo[1] - quien.hitbox.centery
    distancia = math.hypot(dx, dy)
    factor = min(3.0, dt / (1000 / 60)) if dt else 1.0
    paso = velocidad * factor
    if distancia <= max(4, paso):
        quien.ruta.pop(0)
        if not quien.ruta:
            quien.espera_ms = quien.rng.uniform(*ESPERA_NPC_MS)
        return
    antes = quien.hitbox.center
    for ex, ey in ((dx / distancia * paso, 0), (0, dy / distancia * paso)):
        previo = quien.hitbox.copy()
        quien._resto[0] += ex
        quien._resto[1] += ey
        mx, my = int(quien._resto[0]), int(quien._resto[1])
        quien._resto[0] -= mx
        quien._resto[1] -= my
        quien.hitbox.move_ip(mx, my)
        if (choca or getattr(mundo, "colisiona_npc", mundo.colisiona))(quien.hitbox):
            quien.hitbox = previo
    if quien.hitbox.center == antes:
        quien.atascado_ms += dt
        if quien.atascado_ms > 1500:
            quien.ruta, quien.atascado_ms = [], 0
    else:
        quien.atascado_ms = 0


def distancia_a_rect(punto, rect):
    """Distancia de un punto al borde de un rect (0 si está adentro)."""
    dx = max(rect.left - punto[0], 0, punto[0] - rect.right)
    dy = max(rect.top - punto[1], 0, punto[1] - rect.bottom)
    return math.hypot(dx, dy)


class GestorNPCs:
    """Los prisioneros de la partida y los puntos por donde caminan."""

    def __init__(self, juego, cuentas, rng=None):
        """`cuentas`: [(nodo, datos de la cuenta)] de los que salen a caminar."""
        self.juego = juego
        self.rng = rng or random.Random()
        self.puntos = self._puntos_de_interes()
        self.npcs = []
        self.rescatados = []
        self.avisados_rescate = set()   # a quién ya le pidió un verde que lo rescate
        carpetas = carpetas_prisioneros()
        for i, (nodo, cuenta) in enumerate(cuentas):
            apariencia = Apariencia(ESTILOS[i % len(ESTILOS)], cuenta["usuario"],
                                    self.rng.randint(10, 99),
                                    carpetas[i % len(carpetas)] if carpetas else None)
            punto = self.rng.choice(self.puntos) if self.puntos else (100, 100)
            npc = NPC(nodo, cuenta["usuario"], apariencia, punto, self.rng)
            npc.juego = juego
            self.npcs.append(npc)

    def _puntos_de_interes(self):
        """Lugares a los que van los prisioneros: afuera de la prisión."""
        j = self.juego
        mundo = j.mundo
        semilla = None
        mision = getattr(j, "mision", None)
        if mision is not None and mision.capsula is not None:
            semilla = mision.capsula.center
        lugares = [z["rect"].center for z in getattr(j, "zonas", [])]
        lugares += [e["rect"].midbottom for e in getattr(j, "escondites", [])]
        lugares += [t["rect"].center for t in getattr(j, "terminales", [])]
        if mision is not None:
            lugares += [c["rect"].center for c in mision.consolas]
        nav = navegacion.de_mundo(mundo, ANCHO_HITBOX, ALTO_HITBOX)
        if semilla is None:
            semilla = lugares[0] if lugares else (mundo.ancho // 2, mundo.alto // 2)
        alcanzables = mundo.area_alcanzable(semilla, ANCHO_HITBOX, ALTO_HITBOX, paso=48)
        puntos = []
        # Las puertas para dos cerradas no cuentan aquí: se abren durante la
        # partida, y si no, con la cápsula detrás de una (MapaE2) todos los
        # prisioneros quedarían en ese lado. Mientras esté cerrada, igual no la
        # cruzan: la búsqueda de caminos sí la tiene en cuenta.
        puertas, mundo.puertas_alien = getattr(mundo, "puertas_alien", []), []
        for p in lugares:
            x, y = mundo.punto_libre((p[0] - ANCHO_HITBOX // 2, p[1] + 30), ANCHO_HITBOX, ALTO_HITBOX)
            centro = (int(x + ANCHO_HITBOX // 2), int(y + ALTO_HITBOX // 2))
            if nav.camino(semilla, centro, sellos=False) is not None:
                puntos.append(centro)
        mundo.puertas_alien = puertas
        # Y unos cuantos puntos sueltos de los pasillos.
        sueltos = [(c[0] + ANCHO_HITBOX // 2, c[1] + ALTO_HITBOX // 2) for c in alcanzables]
        if sueltos:
            puntos += self.rng.sample(sueltos, min(12, len(sueltos)))
        return puntos

    def actualizar(self, dt):
        juego = self.juego
        mision = getattr(juego, "mision", None)
        for npc in list(self.npcs):
            npc.actualizar(dt, juego, self.puntos)
            if npc.siguiendo is not None:
                if (mision is not None and mision.capsula is not None
                        and distancia_a_rect(npc.centro, mision.capsula) <= RADIO_RESCATE_CAPSULA):
                    self.rescatar(npc)
                continue
            self._charlar(npc)

    # -- Rescate ------------------------------------------------------------------------

    def cerca(self, jugador):
        """El prisionero (o el Cambiaformas disfrazado) con el que puede hablar."""
        candidatos = [n for n in self.npcs if n.siguiendo is None]
        cf = getattr(self.juego, "cambiaformas", None)
        if cf is not None and cf.disfrazado and cf.siguiendo is None:
            candidatos.append(cf)
        cerca = [n for n in candidatos
                 if math.dist(n.centro, jugador.hitbox.center) <= RADIO_HABLAR]
        return min(cerca, key=lambda n: math.dist(n.centro, jugador.hitbox.center), default=None)

    def escoltado(self, jugador):
        """A quién lleva (el nombre que se ve, aunque sea el Cambiaformas)."""
        npc = next((n for n in self.npcs if n.siguiendo is jugador), None)
        if npc is not None:
            return npc.usuario
        cf = getattr(self.juego, "cambiaformas", None)
        if cf is not None and cf.siguiendo is jugador and cf.apariencia is not None:
            return cf.apariencia.usuario
        return None

    def seguidor(self, jugador):
        """El que lo va siguiendo (un prisionero o el Cambiaformas disfrazado), o None."""
        npc = next((n for n in self.npcs if n.siguiendo is jugador), None)
        if npc is not None:
            return npc
        cf = getattr(self.juego, "cambiaformas", None)
        if cf is not None and cf.siguiendo is jugador and cf.apariencia is not None:
            return cf
        return None

    @staticmethod
    def _nombre(quien):
        return quien.usuario if hasattr(quien, "usuario") else quien.apariencia.usuario

    def _seguidor_cerca(self, jugador):
        quien = self.seguidor(jugador)
        if quien is not None and math.dist(quien.centro, jugador.hitbox.center) <= RADIO_SOLTAR:
            return quien
        return None

    def pista(self, jugador):
        seguidor = self.seguidor(jugador)
        if seguidor is not None:
            if self._seguidor_cerca(jugador) is not None:
                return f"Decirle a {self._nombre(seguidor)} que te espere aquí"
            return None
        quien = self.cerca(jugador)
        if quien is None:
            return None
        return f"Pedirle a {self._nombre(quien)} que venga a la cápsula"

    def soltar(self, jugador):
        """Junto al que lo sigue: "espérame aquí". Deja de seguirlo y se queda
        quieto un rato (ESPERA_SOLTADO_MS) por si vuelve por él; después
        vuelve a pasear. El Cambiaformas disfrazado también, pero sin hablar
        (como cuando aceptó: una pista). True si soltó a alguien."""
        quien = self._seguidor_cerca(jugador)
        if quien is None:
            return False
        if isinstance(quien, NPC):
            quien.siguiendo, quien.ruta, quien.lejos_ms = None, [], 0
            quien.destino_paseo = None
            quien.espera_ms = ESPERA_SOLTADO_MS
            quien.decir(FRASE_ESPERA)
            jugador.avisar(f"{quien.usuario} se queda esperándote aquí.", (210, 210, 220))
        else:
            quien.siguiendo, quien.siguiendo_solo_ms = None, 0
            quien.burbuja, quien.burbuja_ms = "...", 2500
            jugador.avisar(f"{quien.apariencia.usuario} asiente y se queda.", (210, 210, 220))
        if hasattr(self.juego, "sonar"):
            self.juego.sonar("menu_ok", 0.4)
        return True

    def hablar(self, jugador):
        """Interactuar cerca de un prisionero: "¿vienes conmigo?" (o, junto al
        que ya lo sigue, "espérame aquí"). True si había alguien."""
        if self.soltar(jugador):
            return True
        quien = self.cerca(jugador)
        if quien is None:
            return False
        seguidor = self.seguidor(jugador)
        if seguidor is not None:
            jugador.avisar(f"Ya llevas a {self._nombre(seguidor)}. Para que te espere, "
                           f"[{jugador.nombre_tecla('interactuar')}] junto a él.", (255, 214, 64))
            return True
        if not isinstance(quien, NPC):
            quien.pedir_que_siga(jugador)       # el Cambiaformas: acepta callado
            jugador.avisar(f"{quien.apariencia.usuario} asiente y te sigue.", (210, 210, 220))
            return True
        red = getattr(self.juego, "nexus", None)
        color = red.color(quien.nodo) if red is not None and quien.nodo in red.grafo else "gris"
        if color == "verde":
            quien.siguiendo, quien.ruta, quien.espera_ms = jugador, [], 0
            quien.decir(FRASE_ACEPTA)
            jugador.avisar(f"{quien.usuario} te sigue. Llévalo a la cápsula.", COLOR_ESTADO["verde"])
        elif color == "rojo":
            quien.decir(FRASE_NIEGA)
            jugador.avisar(f"{quien.usuario} no confía en ustedes.", COLOR_ESTADO["rojo"])
        else:
            quien.decir(FRASE_DUDA)
            jugador.avisar(f"{quien.usuario} todavía no les cree.", (210, 210, 220))
        return True

    def rescatar(self, npc):
        """Llegó a la cápsula: queda a salvo y cuenta en NEXUS que lo salvaron."""
        guia = npc.siguiendo
        self.npcs.remove(npc)
        self.rescatados.append(npc.usuario)
        if guia is not None:
            guia.sumar_puntos(PUNTOS_RESCATE)
            guia.avisar(f"¡{npc.usuario} está a salvo en la cápsula! +{PUNTOS_RESCATE}",
                        COLOR_ESTADO["verde"])
            from misiones.logros import logro
            logro(self.juego, "rescate", guia)
            if hasattr(self.juego, "decir"):
                self.juego.decir("prisionero_rescatado", getattr(guia, "rol", None))
        red = getattr(self.juego, "nexus", None)
        if red is not None:
            red.publicar_testimonio(npc.nodo, FRASE_RESCATADO)
        if hasattr(self.juego, "sonar"):
            self.juego.sonar("acierto", 0.7)

    def _charlar(self, npc):
        """Si un jugador pasa cerca y lo ve, le dice algo según su color en NEXUS."""
        if npc.charla_ms > 0:
            return
        juego = self.juego
        cerca = [j for j in juego.jugadores
                 if not j.preso and not getattr(j, "eliminado", False) and not j.escondido
                 and math.dist(j.hitbox.center, npc.centro) <= RADIO_CHARLA
                 and juego.mundo.linea_libre(j.hitbox.center, npc.centro)]
        if not cerca:
            return
        jugador = cerca[0]
        red = getattr(juego, "nexus", None)
        color = red.color(npc.nodo) if red is not None and npc.nodo in red.grafo else "gris"
        npc.charla_ms = ENFRIAMIENTO_CHARLA_MS
        texto = self._frase(npc, jugador, color)
        npc.decir(texto)
        aviso = f"{npc.usuario}: {texto}"
        if texto == FRASE_PIDE_RESCATE:
            aviso += f" [{jugador.nombre_tecla('interactuar')}] a su lado"
        jugador.avisar(aviso,
                       COLOR_ESTADO["verde"] if color == "verde" else
                       COLOR_ESTADO["rojo"] if color == "rojo" else (210, 210, 220))

    def _frase(self, npc, jugador, color):
        juego = self.juego
        rng = self.rng
        if color == "rojo":
            texto = rng.choice(FRASES_ROJO)
            if "{usuario}" in texto:
                if rng.random() < PROB_DELATAR:
                    aliens = [a for a in juego.aliens if not getattr(a, "disfrazado", False)]
                    if aliens:
                        alien = min(aliens, key=lambda a: math.dist(a.centro, jugador.hitbox.center))
                        alien.oir(jugador.hitbox.center)
                    cf = getattr(juego, "cambiaformas", None)
                    if cf is not None:
                        cf.enterarse(jugador)
                return texto.format(usuario="@" + jugador.rol.lower())
            return texto
        if color == "verde":
            cf = getattr(juego, "cambiaformas", None)
            if (cf is not None and cf.siguiendo is not None and cf.apariencia is not None
                    and math.dist(cf.centro, npc.centro) < 350):
                return rng.choice(FRASES_ADVIERTE_ESCOLTA).format(usuario=cf.apariencia.usuario)
            if jugador not in self.avisados_rescate:
                # La primera vez, que se entere de que puede llevárselo.
                self.avisados_rescate.add(jugador)
                return FRASE_PIDE_RESCATE
            if (cf is not None and cf.disfrazado and cf.apariencia is not None
                    and math.dist(cf.centro, npc.centro) < 600 and rng.random() < 0.6):
                return rng.choice(FRASES_VERDE_CAMBIAFORMAS).format(usuario=cf.apariencia.usuario)
            aliens = [a for a in juego.aliens if not getattr(a, "disfrazado", False)]
            if aliens and rng.random() < 0.6:
                alien = min(aliens, key=lambda a: math.dist(a.centro, npc.centro))
                return rng.choice(FRASES_VERDE_ALIEN).format(
                    alien=alien.nombre, direccion=direccion_texto(jugador.hitbox.center, alien.centro))
            red = getattr(juego, "nexus", None)
            if red is not None and red.rumores_activos():
                from data.nexus import NOMBRE_LUGAR
                lugar = NOMBRE_LUGAR.get(red.rumores_activos()[0].rumor["lugar"], "la nave")
                return rng.choice(FRASES_VERDE_RUMOR).format(lugar=lugar)
            return rng.choice(FRASES_VERDE)
        return rng.choice(FRASES_GRIS)
