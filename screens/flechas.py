"""Las flechas que guían al jugador: la amarilla (lo que toca hacer en la
misión), la azul (el lugar del rumor que va a verificar en NEXUS) y la roja
(la caja de fusibles que hay que encender en un apagón, eventos.py).

Van alrededor del propio jugador, apuntando hacia el objetivo, y no en el
borde de su vista: en el borde las tapaban el HUD, el celular, el pulso o el
inventario. Cuando el objetivo ya se ve en pantalla, se marca ahí mismo
(mision_dibujo.py y celular.py) y la flecha no sale, salvo que quede en
la franja del borde, donde lo tapa el HUD (`cerca_del_borde`).

Pueden salir dos a la vez (la roja con la amarilla o la azul). Para que no
se monten, cada vista llama `empezar()` antes de dibujar las suyas: si una
flecha cae casi en la misma dirección que otra ya dibujada, se corre un poco
de lado (SEPARACION), y si su texto choca con otro, se aleja del jugador.
"""

import math

import pygame

from juego.fuentes import fuente_de_tamano

RADIO = 74           # del centro del cuerpo del jugador a la flecha
ALTO_CUERPO = 26     # el centro del cuerpo queda arriba de la hitbox (los pies)
COLOR_SOMBRA = (12, 11, 23)
SEPARACION = math.radians(30)   # ángulo mínimo entre dos flechas del mismo jugador

_angulos = []    # las flechas ya dibujadas en esta vista
_textos = []     # y sus textos (Rect en pantalla)


def empezar():
    """Al empezar a dibujar las flechas de una vista."""
    _angulos.clear()
    _textos.clear()


def _apartar(angulo):
    """Corre `angulo` lo justo para que no quede encima de otra flecha."""
    for _ in range(4):
        cerca = None
        for otro in _angulos:
            d = (angulo - otro + math.pi) % (2 * math.pi) - math.pi
            if abs(d) < SEPARACION:
                cerca = (otro, d)
                break
        if cerca is None:
            break
        otro, d = cerca
        angulo = otro + (SEPARACION if d >= 0 else -SEPARACION)
    return angulo


def cerca_del_borde(vista, punto):
    """¿`punto` (en pantalla) cae en la franja del borde de la vista? Ahí van
    el HUD, la barra de confianza, el pulso y el inventario, y un objetivo que
    está en pantalla pero ahí se pierde: también lleva flecha."""
    adentro = pygame.Rect(vista.x + 110, vista.y + 110, vista.width - 220, vista.height - 220)
    return not adentro.collidepoint(punto)


def flecha_alrededor(screen, vista, camara, dueño, destino, color, texto=None, tiempo_ms=0):
    """Flecha de `color` a RADIO px del jugador, apuntando a `destino` (x, y
    del mundo), con `texto` un poco más afuera."""
    x, y = dueño.hitbox.centerx, dueño.hitbox.centery - ALTO_CUERPO
    cx, cy = x - camara.x + vista.x, y - camara.y + vista.y
    dx, dy = destino[0] - x, destino[1] - y
    distancia = math.hypot(dx, dy) or 1
    angulo = _apartar(math.atan2(dy / distancia, dx / distancia))
    _angulos.append(angulo)
    ux, uy = math.cos(angulo), math.sin(angulo)
    radio = RADIO + 3 * math.sin(tiempo_ms / 220)          # late un poquito: se nota más
    px, py = cx + ux * radio, cy + uy * radio
    tam = 15
    punta = (px + math.cos(angulo) * tam, py + math.sin(angulo) * tam)
    izq = (px + math.cos(angulo + 2.5) * tam, py + math.sin(angulo + 2.5) * tam)
    der = (px + math.cos(angulo - 2.5) * tam, py + math.sin(angulo - 2.5) * tam)
    pygame.draw.polygon(screen, color, [punta, izq, der])
    pygame.draw.polygon(screen, COLOR_SOMBRA, [punta, izq, der], 2)
    if not texto:
        return
    img = fuente_de_tamano(14).render(texto, True, color)
    fondo = pygame.Surface((img.get_width() + 10, img.get_height() + 4), pygame.SRCALPHA)
    fondo.fill((14, 15, 28, 180))
    # Más afuera que la flecha, del mismo lado; si apunta de lado, el texto se
    # corre hacia afuera para no quedar encima del jugador.
    r = fondo.get_rect(center=(px + ux * (32 + fondo.get_width() / 2 * abs(ux)),
                               py + uy * (22 + fondo.get_height() / 2 * abs(uy))))
    r.clamp_ip(vista.inflate(-8, -8))
    for _ in range(5):                       # que no tape el texto de otra flecha
        if r.collidelist(_textos) < 0:
            break
        r.move_ip(round(ux * 22), round(uy * 22) or 22)
        r.clamp_ip(vista.inflate(-8, -8))
    _textos.append(r)
    screen.blit(fondo, r)
    screen.blit(img, img.get_rect(center=r.center))
