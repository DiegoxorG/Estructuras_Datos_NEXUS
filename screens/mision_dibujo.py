"""Dibujo de lo de la misión (mision.py): puerta, notas, consolas, cápsula,
consumibles y los barrotes de quien está encerrado.

Figuras provisionales hasta que llegue el arte: cuando haya sprites, se cambian
aquí sin tocar la lógica.
"""

import math

import pygame

from juego.fuentes import fuente, fuente_de_tamano
from screens.flechas import flecha_alrededor, cerca_del_borde


COLOR_SOMBRA = (12, 11, 23)
COLOR_PUERTA = (150, 60, 70)
COLOR_NOTA = (240, 226, 170)
COLOR_CONSOLA = (180, 110, 255)
COLOR_LISTO = (96, 210, 120)
COLOR_CAPSULA = (90, 220, 230)
# El kit era naranja como las piezas y se confundían: ahora es verde.
COLOR_CONSUMIBLE = {"decodificador": (90, 160, 255), "kit": (110, 210, 140),
                    "fruta": (232, 84, 60), "abono": (176, 128, 80)}


def _texto(screen, texto, centro_x, y, color):
    f = fuente("small")
    img = f.render(texto, True, color)
    sombra = f.render(texto, True, COLOR_SOMBRA)
    pos = (int(centro_x - img.get_width() // 2), int(y))
    screen.blit(sombra, (pos[0] + 2, pos[1] + 2))
    screen.blit(img, pos)


def _en_pantalla(rect, offset):
    return rect.move(-offset[0], -offset[1])


def _barra(screen, x, y, ancho, valor, color):
    pygame.draw.rect(screen, (30, 32, 48), (x, y, ancho, 8))
    pygame.draw.rect(screen, color, (x, y, int(ancho * max(0, min(1, valor))), 8))
    pygame.draw.rect(screen, (200, 205, 225), (x, y, ancho, 8), 1)


COLOR_FLECHA = (255, 214, 64)


def dibujar_flecha_objetivo(screen, vista, camara, dueño, mision, dificultad, red, tiempo_ms):
    """Dificultades fáciles (dificultad.py): una flecha amarilla hacia lo que
    toca hacer (Mision.punto_objetivo). Si ya va a verificar un rumor en NEXUS,
    manda esa flecha (la azul) y esta no sale."""
    if mision is None or dificultad is None or not dificultad.flecha:
        return
    if red is not None and red.investigando.get(dueño) is not None:
        return
    objetivo = mision.punto_objetivo(dueño)
    if objetivo is None:
        return
    (x, y), texto = objetivo
    f = fuente_de_tamano(14)
    if camara.collidepoint(x, y):
        centro = (int(x - camara.x + vista.x), int(y - camara.y + vista.y))
        radio = 34 + int(5 * math.sin(tiempo_ms / 180))
        pygame.draw.circle(screen, COLOR_FLECHA, centro, radio, 2)
        img = f.render(texto, True, COLOR_FLECHA)
        fondo = pygame.Surface((img.get_width() + 10, img.get_height() + 4), pygame.SRCALPHA)
        fondo.fill((14, 15, 28, 180))
        r = fondo.get_rect(midbottom=(centro[0], centro[1] - radio - 4))
        r.clamp_ip(vista.inflate(-8, -8))
        screen.blit(fondo, r)
        screen.blit(img, img.get_rect(center=r.center))
        if not cerca_del_borde(vista, centro):
            return
    # Fuera de pantalla (o en el borde, donde lo tapa el HUD): una flecha
    # alrededor del jugador (screens/flechas.py).
    # Si el objetivo ya está en pantalla (en el borde), su letrero ya salió
    # encima del aro: la flecha va sin texto para no repetirlo.
    flecha_alrededor(screen, vista, camara, dueño, (x, y), COLOR_FLECHA,
                     None if camara.collidepoint(x, y) else texto, tiempo_ms)


def dibujar_piso(screen, offset, camara, dueño, mision, tiempo_ms):
    if mision is None or not mision.activa:
        return
    brillo = 0.6 + 0.4 * math.sin(tiempo_ms / 280)

    varias = len(getattr(mision, "puertas", ())) > 1
    for puerta in getattr(mision, "puertas", ()):
        if puerta["abierta"] or not puerta["rect"].colliderect(camara):
            continue
        r = _en_pantalla(puerta["rect"], offset)
        color = puerta["color"] if varias else COLOR_PUERTA
        pygame.draw.rect(screen, (60, 62, 78), r)
        for i in range(r.top + 6, r.bottom, 14):
            pygame.draw.line(screen, color, (r.left, i), (r.right, i), 4)
        pygame.draw.rect(screen, color, r, 3)
        # La luz del teclado, del color de la puerta (el de las tachuelas de sus notas).
        luz = puerta["color"]
        pygame.draw.circle(screen, luz if brillo > 0.8 else tuple(c // 2 for c in luz),
                           (r.centerx, r.top - 10), 6)

    if mision.capsula is not None and mision.capsula.colliderect(camara):
        r = _en_pantalla(mision.capsula, offset)
        capa = pygame.Surface(r.size, pygame.SRCALPHA)
        alfa = int(60 + 60 * brillo) if mision.fase == "huida" else 40
        capa.fill((*COLOR_CAPSULA, alfa))
        screen.blit(capa, r.topleft)
        pygame.draw.rect(screen, COLOR_CAPSULA, r, 3, border_radius=10)
        _texto(screen, "Cápsula de escape", r.centerx, r.top - 40, COLOR_CAPSULA)
        if mision.fase in ("capsula", "huida"):
            from misiones.mision import PIEZAS_NECESARIAS
            estado = (f"Piezas {mision.piezas_entregadas}/{PIEZAS_NECESARIAS}"
                      if mision.piezas_entregadas < PIEZAS_NECESARIAS else "Reparación")
            _texto(screen, estado, r.centerx, r.top - 20, (230, 235, 250))
            if mision.piezas_entregadas >= PIEZAS_NECESARIAS:
                _barra(screen, r.x + 10, r.bottom + 6, r.width - 20, mision.reparacion, COLOR_LISTO)

    for consola in mision.consolas:
        if not consola["rect"].colliderect(camara):
            continue
        r = _en_pantalla(consola["rect"], offset)
        lista = consola["progreso"] >= 1
        color = COLOR_LISTO if lista else COLOR_CONSOLA
        pygame.draw.rect(screen, (34, 30, 52), r, border_radius=6)
        pygame.draw.rect(screen, tuple(int(c * (1 if lista else brillo)) for c in color),
                         r.inflate(-14, -14), border_radius=4)
        pygame.draw.rect(screen, color, r, 2, border_radius=6)
        if mision.fase == "sabotaje" and not lista:
            _barra(screen, r.x, r.bottom + 4, r.width, consola["progreso"], COLOR_CONSOLA)

    for nota in mision.notas:
        if not nota["rect"].colliderect(camara):
            continue
        r = _en_pantalla(nota["rect"], offset)
        nueva = dueño not in nota["leida_por"]
        if nueva:
            halo = pygame.Surface((r.width + 24, r.height + 24), pygame.SRCALPHA)
            pygame.draw.ellipse(halo, (*COLOR_NOTA, int(70 * brillo)), halo.get_rect())
            screen.blit(halo, (r.x - 12, r.y - 12))
        pygame.draw.rect(screen, COLOR_NOTA if nueva else (150, 145, 120), r.inflate(-6, 0))
        for i in range(3):
            y = r.y + 7 + i * 7
            pygame.draw.line(screen, (120, 110, 80), (r.x + 7, y), (r.right - 7, y), 1)
        if nota.get("de_codigo"):
            # Las de código (vienen con una puerta): tachuela del color de su puerta.
            color = nota.get("color", (220, 60, 60))
            pygame.draw.circle(screen, (30, 24, 24), (r.centerx, r.y + 3), 5)
            pygame.draw.circle(screen, color if nueva else tuple(c * 2 // 3 for c in color),
                               (r.centerx, r.y + 2), 4)
            pygame.draw.rect(screen, color, (r.x + 7, r.bottom - 8, r.width - 14, 3))

    for cons in mision.consumibles:
        if cons["tomado"] or not cons["rect"].colliderect(camara):
            continue
        r = _en_pantalla(cons["rect"], offset)
        color = COLOR_CONSUMIBLE[cons["tipo"]]
        if cons["tipo"] in ("fruta", "abono", "kit", "decodificador"):
            # Su dibujito (el mismo del inventario), con un halo que late.
            from screens.paneles import _icono_objeto
            brillo = 0.6 + 0.4 * math.sin(tiempo_ms / 260)
            halo = pygame.Surface((r.width + 20, r.height + 20), pygame.SRCALPHA)
            pygame.draw.ellipse(halo, (*color, int(80 * brillo)), halo.get_rect())
            screen.blit(halo, (r.x - 10, r.y - 10))
            _icono_objeto(screen, cons["tipo"], r.center, r.width + 6)
            continue
        pygame.draw.rect(screen, (30, 30, 40), r, border_radius=5)
        pygame.draw.rect(screen, color, r.inflate(-10, -10), border_radius=3)
        pygame.draw.rect(screen, color, r, 2, border_radius=5)


def dibujar_encima(screen, offset, camara, mision, tiempo_ms):
    """Barrotes delante de quien está encerrado, y su pedido de ayuda."""
    if mision is None or not mision.activa:
        return
    for celda in mision.celdas:
        preso = celda["preso"]
        if preso is None:
            continue
        hb = preso.personaje.hitbox
        x = hb.centerx - offset[0]
        arriba = int(preso.personaje.y) - offset[1]
        abajo = hb.bottom - offset[1]
        for i in range(-30, 31, 12):
            pygame.draw.line(screen, (150, 155, 170), (x + i, arriba), (x + i, abajo), 3)
        if (tiempo_ms // 500) % 2 == 0:
            _texto(screen, "¡Ayuda!", x, arriba - 24, (255, 120, 120))


def render_progreso(screen, vista, jugador):
    """Barra de lo que está haciendo con la tecla mantenida."""
    progreso = getattr(jugador, "progreso", None)
    if not progreso:
        return
    texto, valor = progreso
    ancho = min(320, vista.width - 80)
    x = vista.centerx - ancho // 2
    from screens.paneles import tope_abajo
    y = min(vista.bottom - 150, tope_abajo(vista, jugador) - 66)   # encima de la pista
    fondo = pygame.Surface((ancho + 20, 46), pygame.SRCALPHA)
    fondo.fill((14, 15, 28, 220))
    screen.blit(fondo, (x - 10, y - 26))
    _texto(screen, texto, vista.centerx, y - 22, (240, 242, 252))
    pygame.draw.rect(screen, (40, 42, 64), (x, y, ancho, 12))
    pygame.draw.rect(screen, COLOR_LISTO, (x, y, int(ancho * valor), 12))
    pygame.draw.rect(screen, (120, 132, 190), (x, y, ancho, 12), 1)
