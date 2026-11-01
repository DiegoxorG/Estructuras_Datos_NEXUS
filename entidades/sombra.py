"""La Sombra: el alien de los apagones (idea de Joseph).

Solo existe mientras la nave está a oscuras: aparece unos segundos después de
que se va la luz, lejos de todos y donde nadie la ve, y se disuelve cuando
alguien prende la caja de fusibles (Game._actualizar_sombra). Es mediana,
encorvada, de brazos largos y una boca llena de dientes.

- En la oscuridad solo se le ven los ojos, que brillan (se dibujan encima de
  la capa de oscuridad: `dibujar_ojos`). Cuando una linterna la alumbra se
  ve el resto.
- Como los ángeles llorones: mientras el cono de una linterna la alumbra no
  se puede mover (el halo chico de cada uno deja verla, pero no la frena). Si le dan la espalda, se acerca rápido y en
  silencio (solo un susurro).
- Si la alumbran mucho rato (LUZ_PARA_ESFUMARSE_MS) se esfuma y aparece en
  otro lado.
- Si alcanza a alguien le apaga la linterna, nunca lo atrapa: un rato
  (Fácil, Normal, Difícil) o hasta que alguien prenda la caja de fusibles
  (Pesadilla, en Inteligente). Después se esfuma (Game._sombra_alcanza). A quien ya está sin
  linterna no lo persigue: va por los demás.
- No revisa escondites: meterse en uno es una forma de esperar la luz.

Su comportamiento es un árbol binario de decisión, como el de los demás
aliens (data/comportamiento_sombra.py); este archivo responde sus preguntas
(percibir) y ejecuta sus hojas (_ejecutar). No tiene arte todavía: su figura
se dibuja con formas (`figura_sombra`).
"""

import math
import random

import pygame

from entidades.alien import Alien, DISTANCIA_ATRAPAR, _distancia
from Estructuras.arbol_comportamiento import ArbolComportamiento
from data.comportamiento_sombra import ARBOL_SOMBRA
from juego import vision
from juego.oscuridad import ALCANCE_LINTERNA, MEDIO_ANGULO_LINTERNA

ALCANCE_SENTIR = 1500           # siente a quien esté a oscuras hasta esta distancia
LUZ_PARA_ESFUMARSE_MS = 3000    # alumbrada este rato seguido, se esfuma
OCULTA_TRAS_LUZ_MS = 4000       # ...y tarda esto en volver a aparecer
OCULTA_TRAS_ALCANZAR_MS = 8000  # después de alcanzar a alguien
COLOR_OJOS = (255, 226, 140)


class Sombra(Alien):
    def __init__(self, juego, numero):
        super().__init__(numero, [(0, 0)], ArbolComportamiento(ARBOL_SOMBRA), "sombra")
        self.juego = juego
        self.nombre = "La Sombra"
        self.alumbrada = False
        self.quien_alumbra = None
        self.luz_ms = 0
        self.oculta_ms = 0
        self.presa = None
        self.merodeo = None
        self.rng = random.Random()

    # -- Estado -------------------------------------------------------------------

    @property
    def oculta(self):
        """Esfumada: no se dibuja, no asusta, no atrapa."""
        return self.oculta_ms > 0

    @property
    def se_ve(self):
        """Para el logro "Conoce a tu enemigo": hay que verla alumbrada."""
        return self.alumbrada and not self.oculta

    def aparecer(self, punto):
        self.hitbox.center = (int(punto[0]), int(punto[1]))
        self.oculta_ms = self.luz_ms = self.descanso_ms = 0
        self.alumbrada = False
        self.presa = self.merodeo = None
        self.ruta_ruido, self._destino_ruta, self._buscando_hacia = [], None, None

    def esfumarse(self, ms):
        self.oculta_ms = ms
        self.luz_ms = 0
        self.alumbrada = False
        self.presa = None
        self.ruta_ruido, self._destino_ruta, self._buscando_hacia = [], None, None

    # -- Percepción ---------------------------------------------------------------

    def alumbrada_por(self, jugador, mundo):
        """¿La apunta la linterna de `jugador` (sin paredes en medio)? Los
        mismos números con los que oscuridad.py pinta el cono. El halo chico
        alrededor de cada uno NO la congela (se le ve el cuerpo, pero sigue):
        hay que mirarla de frente."""
        if (jugador.preso is not None or jugador.escondido or getattr(jugador, "eliminado", False)
                or not getattr(jugador, "puede_moverse", True)
                or getattr(jugador, "sin_linterna_ms", 0) > 0):
            return False
        dx = self.centro[0] - jugador.hitbox.centerx
        dy = self.centro[1] - jugador.hitbox.centery
        distancia = math.hypot(dx, dy)
        if distancia > ALCANCE_LINTERNA * 0.95:
            return False
        if distancia > 24:
            linterna = getattr(getattr(jugador, "linterna", None), "angulo", math.pi / 2)
            diferencia = (math.atan2(dy, dx) - linterna + math.pi) % (2 * math.pi) - math.pi
            if abs(diferencia) > MEDIO_ANGULO_LINTERNA * 1.1:
                return False
        juego = self.juego
        campo = vision.campo_de(jugador.hitbox.center, vision.obstaculos(
            mundo, getattr(juego, "puertas_dobles", ()), getattr(juego, "compuertas", ())))
        return campo.ve_a(self.hitbox)

    def percibir(self, jugadores, mundo, escondites=()):
        if self.oculta:
            self.alumbrada, self.presa = False, None
            return {"recuperandose": self.descanso_ms > 0, "esfumada": True, "alumbrada": False,
                    "presa_al_alcance": False, "siente_a_alguien": False}
        self.quien_alumbra = next((j for j in jugadores if self.alumbrada_por(j, mundo)), None)
        self.alumbrada = self.quien_alumbra is not None
        cerca = [j for j in jugadores if j.cazable and not j.escondido
                 and getattr(j, "sin_linterna_ms", 0) <= 0       # ese ya está a oscuras
                 and _distancia(self.centro, j.hitbox.center) <= ALCANCE_SENTIR]
        self.presa = min(cerca, key=lambda j: _distancia(self.centro, j.hitbox.center), default=None)
        choca = getattr(mundo, "colisiona_alien", None)
        al_alcance = (self.presa is not None
                      and _distancia(self.centro, self.presa.hitbox.center) <= DISTANCIA_ATRAPAR
                      and (mundo.linea_libre(self.centro, self.presa.hitbox.center, colisiona=choca)
                           if choca else True))
        return {
            "recuperandose": self.descanso_ms > 0,
            "esfumada": False,
            "alumbrada": self.alumbrada,
            "presa_al_alcance": al_alcance,
            "siente_a_alguien": self.presa is not None,
        }

    # -- Acciones -----------------------------------------------------------------

    def _ejecutar(self, accion, dt, factor, mundo, al_atrapar, al_revisar=None):
        if accion != "CONGELARSE":
            self.luz_ms = max(0, self.luz_ms - dt)
        if accion == "DESCANSAR":
            return
        if accion == "ESFUMARSE":
            self.oculta_ms -= dt
            if self.oculta_ms <= 0:
                punto = self.juego._punto_para_sombra() if hasattr(self.juego, "_punto_para_sombra") else None
                if punto is None:
                    self.oculta_ms = 1000          # nadie libre o ningún lugar a oscuras: espera
                else:
                    self.aparecer(punto)
            return
        if accion == "CONGELARSE":
            # Quieta como una estatua mientras la alumbren; si es mucho rato,
            # se esfuma.
            self.luz_ms += dt
            if self.luz_ms >= LUZ_PARA_ESFUMARSE_MS:
                from misiones.logros import logro
                logro(self.juego, "no_parpadees", getattr(self, "quien_alumbra", None))
                self.esfumarse(OCULTA_TRAS_LUZ_MS)
            return
        if accion == "ALCANZAR":
            presa = self.presa
            if presa is not None and hasattr(self.juego, "_sombra_alcanza"):
                self.juego._sombra_alcanza(presa, self)
            elif presa is not None and al_atrapar is not None:
                al_atrapar(presa, self)
            self.esfumarse(OCULTA_TRAS_ALCANZAR_MS)
            return
        if accion == "ACECHAR":
            self.merodeo = None
            if self._ir_por_camino(self.presa.hitbox.center, self.datos["vel_perseguir"] * factor,
                                   dt, mundo):
                pass                             # no hay camino: la siguiente vez lo intenta de nuevo
            return
        if accion == "MERODEAR":
            puntos = getattr(getattr(self.juego, "npcs", None), "puntos", None) or []
            if self.merodeo is None and puntos:
                self.merodeo = self.rng.choice(puntos)
            if self.merodeo is not None and self._ir_por_camino(
                    self.merodeo, self.datos["vel_patrulla"] * factor, dt, mundo):
                self.merodeo = None

    # -- Dibujo -------------------------------------------------------------------

    def _rect_figura(self, imagen, offset):
        return imagen.get_rect(midbottom=(self.hitbox.centerx - offset[0],
                                          self.hitbox.bottom - offset[1] + 4))

    def _imagen(self):
        izquierda = math.cos(self.angulo) < 0
        fase = int(self.tiempo_ms / 110) % 4 if self.moviendose else 0
        return figura_sombra(fase, izquierda, self.moviendose), izquierda, fase

    def dibujar(self, screen, offset):
        if self.oculta:
            return
        imagen, _, _ = self._imagen()
        rect = self._rect_figura(imagen, offset)
        sombra = pygame.Rect(0, 0, 40, 10)
        sombra.center = (rect.centerx, self.hitbox.bottom - offset[1])
        pygame.draw.ellipse(screen, (6, 5, 10), sombra)
        screen.blit(imagen, rect)

    def _caja_figura(self, offset):
        imagen, _, _ = self._imagen()
        return self._rect_figura(imagen, offset)

    def dibujar_ojos(self, screen, offset, tiempo_ms):
        """Los ojos, encima de la oscuridad: es lo único que se le ve a oscuras.
        Parpadean de vez en cuando."""
        if self.oculta or (self.tiempo_ms + self.numero * 977) % 3700 < 130:
            return
        imagen, izquierda, fase = self._imagen()
        rect = self._rect_figura(imagen, offset)
        e = ESCALA_FIGURA
        for i, (x, y, r) in enumerate(OJOS):
            brillo = _brillo(10 if i < 2 else 6)
            x = (ANCHO_FIGURA - 1 - x) if izquierda else x
            px, py = rect.x + int(x * e), rect.y + int(y * e)
            screen.blit(brillo, (px - brillo.get_width() // 2, py - brillo.get_height() // 2),
                        special_flags=pygame.BLEND_RGB_ADD)
            pygame.draw.circle(screen, (255, 250, 225), (px, py), max(1, int(r * e)))

    def dibujar_senal(self, screen, offset):
        return          # no avisa nada: es sigilosa

    def dibujar_vision(self, screen, offset):
        return          # no tiene cono: no ve, siente


# -- Su figura (dibujada con formas, hasta que haya arte) --------------------------------

ANCHO_FIGURA, ALTO_FIGURA = 72, 84    # se dibuja así y se agranda ESCALA_FIGURA (pixelado)
ESCALA_FIGURA = 1.45
OJOS = [(53, 14, 2), (64, 12, 2), (57, 19, 1), (67, 18, 1)]   # (x, y, radio) mirando a la derecha
_figuras = {}
_brillos = {}

PIEL = (118, 98, 138)         # gris violáceo: a oscuras no se ve, con la linterna sí
PIEL_OSCURA = (74, 58, 92)
PIEL_CLARA = (170, 146, 190)
CONTORNO = (14, 8, 20)
BOCA = (168, 28, 50)
DIENTE = (244, 236, 214)


def _brillo(radio=11):
    """Halo de un ojo: se suma a lo que hay debajo (BLEND_RGB_ADD)."""
    if radio not in _brillos:
        capa = pygame.Surface((radio * 2, radio * 2))
        capa.fill((0, 0, 0))
        for k in range(radio, 0, -1):
            t = 1 - k / radio
            pygame.draw.circle(capa, tuple(int(c * t ** 1.6) for c in COLOR_OJOS), (radio, radio), k)
        _brillos[radio] = capa
    return _brillos[radio]


def figura_sombra(fase=0, izquierda=False, caminando=False):
    """La Sombra mirando a la derecha (o a la izquierda), en una de 4 fases de
    caminar. Encorvada, brazos largos hasta el piso, púas en la espalda y una
    boca abierta llena de dientes."""
    clave = (fase if caminando else 0, izquierda)
    if clave in _figuras:
        return _figuras[clave]
    s = pygame.Surface((ANCHO_FIGURA, ALTO_FIGURA), pygame.SRCALPHA)
    paso = (0, 5, 0, -5)[fase] if caminando else 0
    piso = ALTO_FIGURA - 3

    def linea(color, puntos, ancho):
        pygame.draw.lines(s, CONTORNO, False, puntos, ancho + 2)
        pygame.draw.lines(s, color, False, puntos, ancho)

    # Piernas (la de atrás más oscura) y brazo de atrás.
    linea(PIEL_OSCURA, [(30, 54), (22 - paso, 66), (27 - paso, piso)], 4)
    linea(PIEL_OSCURA, [(42, 34), (50 + paso // 2, 50), (49 + paso // 2, piso - 6)], 3)
    # Torso encorvado.
    torso = [(26, 58), (18, 44), (22, 30), (34, 22), (48, 24), (52, 36), (46, 52), (36, 58)]
    pygame.draw.polygon(s, PIEL, torso)
    pygame.draw.polygon(s, CONTORNO, torso, 2)
    for y in (34, 40, 46):                                       # costillas
        pygame.draw.line(s, PIEL_CLARA, (30, y), (44, y - 3), 2)
    for x, y in ((20, 40), (22, 32), (28, 25)):                  # púas de la espalda
        pygame.draw.polygon(s, PIEL_CLARA, [(x, y), (x - 7, y - 7), (x + 3, y - 2)])
    # Pierna de adelante.
    linea(PIEL, [(38, 54), (46 + paso, 66), (42 + paso, piso)], 4)
    # Cabeza alargada hacia adelante con la boca abierta.
    cabeza = [(46, 26), (48, 12), (58, 6), (70, 12), (70, 22), (64, 26), (54, 32)]
    pygame.draw.polygon(s, PIEL, cabeza)
    pygame.draw.polygon(s, CONTORNO, cabeza, 2)
    boca = [(54, 24), (70, 22), (68, 36), (56, 34)]
    pygame.draw.polygon(s, BOCA, boca)
    pygame.draw.polygon(s, CONTORNO, boca, 1)
    for x in range(56, 69, 3):                                   # dientes de arriba y de abajo
        pygame.draw.polygon(s, DIENTE, [(x, 24), (x + 2, 24), (x + 1, 28)])
        pygame.draw.polygon(s, DIENTE, [(x, 34), (x + 2, 34), (x + 1, 30)])
    for x, y, r in OJOS:                                         # ojos (el brillo va aparte)
        pygame.draw.circle(s, (200, 180, 120), (x, y), r + 1)
    # Brazo de adelante, larguísimo, con garras casi en el piso.
    mano = (60 - paso // 2, piso - 10)
    linea(PIEL, [(46, 30), (60, 44), mano], 3)
    for dx in (-4, 0, 4):
        pygame.draw.line(s, PIEL_CLARA, mano, (mano[0] + dx, mano[1] + 8), 2)
    s = pygame.transform.scale(s, (round(ANCHO_FIGURA * ESCALA_FIGURA), round(ALTO_FIGURA * ESCALA_FIGURA)))
    if izquierda:
        s = pygame.transform.flip(s, True, False)
    _figuras[clave] = s
    return s
