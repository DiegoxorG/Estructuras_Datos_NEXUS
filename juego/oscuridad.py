"""Lo que ve cada jugador: campo de visión y, en un apagón, la linterna.

Sobre cada viewport se multiplica un "mapa de luz" en grises: blanco donde se
ve, gris oscuro donde no.

- Con luz: se ve bien un círculo grande alrededor del jugador, recortado por
  las paredes (el polígono de visión, ver vision.py). Fuera de eso el mapa
  queda en penumbra y los aliens no se dibujan (screens/partida.py).
- En un apagón (eventos.py) la luz es solo un halo chico alrededor del jugador
  y el cono de su linterna, hacia donde camina, también recortados por las
  paredes. Los compañeros llevan un halo chico (se ven entre ellos). De los
  aliens solo se ve el cuerpo, y solo donde llega la luz: no se dibujan sus
  conos, el anillo del Ciego ni sus ojos, y sus señales (!, ?, zZ) quedan
  debajo de la oscuridad. Para volver a verlos hay que prender la caja de
  fusibles.

Cómo se hace sin que pese: el mapa de luz se arma a un cuarto del tamaño del
viewport (ESCALA_LUZ) y se agranda con suavizado. El cono se pinta con varios
polígonos, del más ancho y tenue al más angosto y claro, y los halos son
degradados precalculados que se pegan con BLEND_RGB_MAX (gana el más claro).
El polígono de visión se pinta como máscara y se multiplica. Al agrandar el
mapa chico con smoothscale los bordes quedan difuminados en vez de cortarse
en seco. Al final todo se multiplica con la imagen (BLEND_RGB_MULT).
"""

import math

import pygame

from juego.vision import RADIO_VISION


OPACIDAD = 175               # fuera del campo de visión, con luz (255 = negro)
OPACIDAD_APAGON = 250
RADIO_HALO = 210             # alrededor del jugador
RADIO_HALO_COMPANERO = 110
ALCANCE_LINTERNA = 460       # largo del cono en un apagón (antes 270)
MEDIO_ANGULO_LINTERNA = math.radians(35)
FACTOR_APAGON = 0.75         # cuánto se encogen los halos en un apagón
ESCALA_LUZ = 4               # el mapa de luz se arma a 1/4 y se agranda suavizado
FACTOR_ESCONDIDO = 0.45      # escondido en un casillero se ve poco
CAPAS_CONO = 9               # polígonos del cono: más capas, borde más suave

ANGULO_DIRECCION = {
    "east": 0.0, "south-east": math.pi / 4, "south": math.pi / 2,
    "south-west": 3 * math.pi / 4, "west": math.pi, "north-west": -3 * math.pi / 4,
    "north": -math.pi / 2, "north-east": -math.pi / 4,
}

_capas = {}
_ultimo = {}          # vista.topleft -> (clave, mapa de luz ya agrandado)
_halos = {}


def _capa(tamano, uso="luz"):
    clave = (uso, tamano)
    if clave not in _capas:
        _capas[clave] = pygame.Surface(tamano)
    return _capas[clave]


def _grande(tamano):
    """Superficie del tamaño del viewport donde se agranda el mapa de luz."""
    return _capa(tamano, "grande")


def _gris(opacidad):
    v = 255 - opacidad
    return (v, v, v)


def _halo(radio, inicio=0.35):
    """Círculo blanco en el centro que se va apagando hasta negro en el borde.

    `inicio` es desde qué fracción del radio empieza a apagarse.
    """
    radio = max(8, int(radio))
    if (radio, inicio) not in _halos:
        halo = pygame.Surface((radio * 2, radio * 2))
        halo.fill((0, 0, 0))
        anillos = 48
        for k in range(anillos, 0, -1):
            t = k / anillos                      # 1 en el borde, ~0 en el centro
            opacidad = int(255 * max(0.0, (t - inicio) / (1 - inicio)) ** 1.4)
            pygame.draw.circle(halo, _gris(opacidad), (radio, radio), int(radio * t))
        _halos[(radio, inicio)] = halo
    return _halos[(radio, inicio)]


class Linterna:
    """Hacia dónde apunta la linterna de un jugador. Gira suave, no de golpe."""

    def __init__(self):
        self.angulo = math.pi / 2

    def actualizar(self, direccion):
        objetivo = ANGULO_DIRECCION.get(direccion, self.angulo)
        diferencia = (objetivo - self.angulo + math.pi) % (2 * math.pi) - math.pi
        self.angulo += diferencia * 0.2


def dibujar(screen, vista, camara, dueño, jugadores, apagon=False, vision=None):
    """Oscurece el viewport `vista` dejando ver lo que ve `dueño`.

    Se arma un "mapa de luz" en grises (blanco = se ve todo, casi negro = no se
    ve nada) y se multiplica con lo que ya está dibujado. Multiplicar es más
    barato que mezclar una capa transparente del tamaño de la pantalla.

    `vision` es el polígono de visión del dueño (vision.py), en coordenadas
    del mundo. Con luz, adentro se ve todo (con el borde del radio difuminado)
    y afuera queda en penumbra. En un apagón la luz es la de la linterna y los
    halos, pero igual recortada por el polígono: no alumbra tras las paredes.
    """
    # Con luz y sin que nada se haya movido (cámara, dueño, su campo de
    # visión), el mapa de luz es el mismo del cuadro anterior: se reusa.
    clave = None
    if not apagon:
        clave = (vista.size, tuple(camara.topleft), dueño.hitbox.center, dueño.escondido,
                 id(vision), len(vision) if vision else 0, vision[0] if vision else None)
        guardado = _ultimo.get(vista.topleft)
        if guardado is not None and guardado[0] == clave:
            screen.blit(guardado[1], vista.topleft, special_flags=pygame.BLEND_RGB_MULT)
            return

    e = ESCALA_LUZ
    chico = (max(1, vista.width // e), max(1, vista.height // e))
    luz = _capa(chico)
    luz.fill((0, 0, 0))
    factor = FACTOR_APAGON if apagon else 1.0
    oscuro = OPACIDAD_APAGON if apagon else OPACIDAD

    def local(p):
        return ((p[0] - camara.x) / e, (p[1] - camara.y) / e)

    if not apagon:
        # Con luz: un círculo grande, parejo hasta cerca del borde.
        radio = RADIO_VISION * (FACTOR_ESCONDIDO if dueño.escondido else 1.0) / e
        halo = _halo(radio, inicio=0.7)
        x, y = local(dueño.hitbox.center)
        luz.blit(halo, (int(x) - halo.get_width() // 2, int(y) - halo.get_height() // 2))

    # El cono de la linterna: capas del más ancho y oscuro al más angosto y
    # claro. Cada capa es un poco más corta, así también se apaga hacia la punta.
    if (apagon and dueño.preso is None and not dueño.escondido
            and getattr(dueño, "sin_linterna_ms", 0) <= 0):    # (la Sombra se la apagó)
        cx, cy = local(dueño.hitbox.center)
        angulo = getattr(getattr(dueño, "linterna", None), "angulo", math.pi / 2)
        alcance = ALCANCE_LINTERNA / e
        for k in range(CAPAS_CONO):
            t = k / (CAPAS_CONO - 1)                   # 0 la de afuera, 1 la de adentro
            medio = MEDIO_ANGULO_LINTERNA * (1.25 - 0.85 * t)
            largo = alcance * (1.05 - 0.45 * t)
            opacidad = int(oscuro - (oscuro - 40) * (0.25 + 0.75 * t) ** 1.3)
            puntos = [(cx, cy)]
            for i in range(11):
                a = angulo - medio + 2 * medio * i / 10
                puntos.append((cx + math.cos(a) * largo, cy + math.sin(a) * largo))
            pygame.draw.polygon(luz, _gris(opacidad), puntos)

    if apagon:
        radio = RADIO_HALO * factor / e
        halo = _halo(radio)
        x, y = local(dueño.hitbox.center)
        luz.blit(halo, (int(x) - halo.get_width() // 2, int(y) - halo.get_height() // 2),
                 special_flags=pygame.BLEND_RGB_MAX)

    # Recorte: lo que tapan las paredes queda a oscuras.
    if vision is not None and len(vision) >= 3:
        mascara = _capa(chico, "mascara")
        mascara.fill((0, 0, 0))
        pygame.draw.polygon(mascara, (255, 255, 255), [local(p) for p in vision])
        luz.blit(mascara, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

    # Halos de los compañeros (en el apagón cada uno lleva su linterna; se ven
    # entre ellos aunque haya una pared en medio).
    if apagon:
        for jugador in jugadores:
            if jugador is dueño or jugador.escondido or getattr(jugador, "eliminado", False):
                continue
            halo = _halo(RADIO_HALO_COMPANERO * factor / e)
            x, y = local(jugador.hitbox.center)
            luz.blit(halo, (int(x) - halo.get_width() // 2, int(y) - halo.get_height() // 2),
                     special_flags=pygame.BLEND_RGB_MAX)

    # Lo que no se ve tampoco queda negro del todo: el mapa se adivina.
    luz.fill(_gris(oscuro), special_flags=pygame.BLEND_RGB_MAX)

    if clave is not None:
        guardado = _ultimo.get(vista.topleft)
        grande = guardado[1] if guardado is not None and guardado[1].get_size() == vista.size \
            else pygame.Surface(vista.size)
        _ultimo[vista.topleft] = (clave, grande)
    else:
        _ultimo.pop(vista.topleft, None)
        grande = _grande(vista.size)
    pygame.transform.smoothscale(luz, vista.size, grande)
    screen.blit(grande, vista.topleft, special_flags=pygame.BLEND_RGB_MULT)
