"""La ventana que presenta a un tipo de alien nuevo (dificultad Fácil).

En la vista del jugador que lo vio: todo oscurecido menos un círculo alrededor
del alien, un anillo de su color que late, una flecha desde la ventana hasta
él y la ventana con su retrato, su nombre y cómo funciona. En las otras
vistas, un aviso de que el juego está en pausa. La lógica está en
juego/presentacion_aliens.py.
"""

import math

import pygame

from juego.fuentes import fuente_de_tamano
from juego.ambiente import figura_alien
from data.tipos_alien import datos_tipo
from screens.partida import calcular_viewports, _envolver

COLOR_FONDO = (12, 14, 30, 235)
COLOR_TEXTO = (236, 238, 252)
COLOR_SUAVE = (150, 156, 190)


def _a_pantalla(punto, vista, camara):
    return int(punto[0] - camara.x + vista.x), int(punto[1] - camara.y + vista.y)


def render_presentacion(screen, juego):
    presentacion = getattr(juego, "presentacion", None)
    if presentacion is None or not presentacion.abierta:
        return
    actual = presentacion.actual
    jugador, alien, tipo = actual["jugador"], actual["alien"], actual["tipo"]
    if jugador not in juego.jugadores:
        return
    vistas = calcular_viewports(screen.get_width(), screen.get_height(), len(juego.jugadores))
    indice = juego.jugadores.index(jugador)
    if indice >= len(vistas):
        return
    tiempo = pygame.time.get_ticks()
    for i, otra in enumerate(vistas):
        if i != indice:
            _aviso_otra_vista(screen, otra, indice + 1, tipo)

    vista = vistas[indice]
    clip_previo = screen.get_clip()
    screen.set_clip(vista)
    camara = juego.mundo.camara(jugador.hitbox.center, vista.width, vista.height)
    figura = figura_alien(tipo)
    alto_sprite = figura.get_height() if figura is not None else 70
    alto_sprite = max(50, min(140, alto_sprite))
    objetivo = _a_pantalla((alien.hitbox.centerx, alien.hitbox.bottom - alto_sprite // 2), vista, camara)
    radio = int(max(46, alto_sprite * 0.62))
    color = datos_tipo(tipo)["color"]

    # Todo oscuro menos el alien.
    velo = pygame.Surface(vista.size, pygame.SRCALPHA)
    velo.fill((0, 0, 0, 160))
    pygame.draw.circle(velo, (0, 0, 0, 0), (objetivo[0] - vista.x, objetivo[1] - vista.y), radio + 10)
    screen.blit(velo, vista.topleft)
    latido = 0.5 + 0.5 * math.sin(tiempo / 160)
    pygame.draw.circle(screen, color, objetivo, radio + int(5 * latido), 3)

    caja, partes = _armar_caja(vista, objetivo, radio, tipo, presentacion)
    _flecha(screen, caja, objetivo, radio, color)
    _dibujar_caja(screen, caja, partes, color, figura, presentacion, jugador)
    screen.set_clip(clip_previo)


def _armar_caja(vista, objetivo, radio, tipo, presentacion):
    pequena = vista.height < 500
    f_titulo = fuente_de_tamano(18 if pequena else 24)
    f = fuente_de_tamano(13 if pequena else 16)
    f_chica = fuente_de_tamano(11 if pequena else 13)
    ancho = min(vista.width - 30, 640)
    retrato = 0 if pequena else 96
    titulo, parrafos = presentacion.textos()
    lineas = []
    disponible = ancho - (14 + retrato + 16 if retrato else 18) - 18 - f.size("• ")[0]
    for parrafo in parrafos:
        partes = _envolver(parrafo, f, disponible)
        lineas += [("• " if k == 0 else "  ") + linea for k, linea in enumerate(partes)]
    alto = (16 + f_chica.get_linesize() + f_titulo.get_linesize() + 6
            + len(lineas) * f.get_linesize() + 10 + f_chica.get_linesize() + 10)
    alto = max(alto, retrato + 30)
    caja = pygame.Rect(0, 0, ancho, alto)
    caja.centerx = vista.centerx
    # Del lado contrario al alien, sin taparlo.
    arriba = pygame.Rect(caja.x, vista.top + (70 if not pequena else 40), ancho, alto)
    abajo = pygame.Rect(caja.x, vista.bottom - alto - (120 if not pequena else 70), ancho, alto)
    zona_alien = pygame.Rect(0, 0, radio * 2 + 30, radio * 2 + 30)
    zona_alien.center = objetivo
    opciones = [abajo, arriba] if objetivo[1] < vista.centery else [arriba, abajo]
    caja = next((c for c in opciones if not c.colliderect(zona_alien)), opciones[0])
    caja.clamp_ip(vista)
    return caja, {"titulo": titulo, "lineas": lineas, "f_titulo": f_titulo, "f": f,
                  "f_chica": f_chica, "retrato": retrato}


def _flecha(screen, caja, objetivo, radio, color):
    """Del borde de la ventana al anillo del alien, con punta."""
    sale = (max(caja.left + 30, min(caja.right - 30, objetivo[0])),
            caja.bottom if objetivo[1] > caja.centery else caja.top)
    dx, dy = objetivo[0] - sale[0], objetivo[1] - sale[1]
    largo = math.hypot(dx, dy)
    if largo < radio + 24:
        return
    ux, uy = dx / largo, dy / largo
    punta = (objetivo[0] - ux * (radio + 12), objetivo[1] - uy * (radio + 12))
    pygame.draw.line(screen, (10, 10, 20), sale, punta, 8)
    pygame.draw.line(screen, color, sale, punta, 4)
    ancho_punta = 13
    base = (punta[0] - ux * 20, punta[1] - uy * 20)
    puntos = [punta, (base[0] - uy * ancho_punta, base[1] + ux * ancho_punta),
              (base[0] + uy * ancho_punta, base[1] - ux * ancho_punta)]
    pygame.draw.polygon(screen, color, puntos)
    pygame.draw.polygon(screen, (10, 10, 20), puntos, 2)


def _dibujar_caja(screen, caja, partes, color, figura, presentacion, jugador):
    fondo = pygame.Surface(caja.size, pygame.SRCALPHA)
    fondo.fill(COLOR_FONDO)
    screen.blit(fondo, caja.topleft)
    pygame.draw.rect(screen, color, caja, 3, border_radius=8)
    f_titulo, f, f_chica, retrato = partes["f_titulo"], partes["f"], partes["f_chica"], partes["retrato"]
    x = caja.x + 18
    if retrato and figura is not None:
        alto = retrato - 8
        ancho = max(1, int(figura.get_width() * alto / figura.get_height()))
        if ancho > retrato:
            ancho, alto = retrato, max(1, int(figura.get_height() * retrato / figura.get_width()))
        imagen = pygame.transform.scale(figura, (ancho, alto))
        marco = pygame.Rect(caja.x + 14, caja.y + 16, retrato, retrato)
        pygame.draw.rect(screen, (24, 26, 46), marco, border_radius=6)
        screen.blit(imagen, imagen.get_rect(center=marco.center))
        x = marco.right + 16
    y = caja.y + 14
    screen.blit(f_chica.render("ALIEN NUEVO  ·  el juego está en pausa", True, COLOR_SUAVE), (x, y))
    y += f_chica.get_linesize()
    screen.blit(f_titulo.render(partes["titulo"], True, color), (x, y))
    y += f_titulo.get_linesize() + 6
    for linea in partes["lineas"]:
        screen.blit(f.render(linea, True, COLOR_TEXTO), (x, y))
        y += f.get_linesize()
    listo = presentacion.puede_cerrar()
    pie = f_chica.render(f"[{jugador.nombre_tecla('interactuar')}] o [Enter]  continuar", True,
                         COLOR_TEXTO if listo and (pygame.time.get_ticks() // 450) % 2 else COLOR_SUAVE)
    screen.blit(pie, (caja.right - pie.get_width() - 16, caja.bottom - pie.get_height() - 9))


def _aviso_otra_vista(screen, vista, numero, tipo):
    velo = pygame.Surface(vista.size, pygame.SRCALPHA)
    velo.fill((0, 0, 0, 140))
    screen.blit(velo, vista.topleft)
    f = fuente_de_tamano(16 if vista.height < 500 else 19)
    quien = "a la Sombra" if tipo == "sombra" else f"un {datos_tipo(tipo)['nombre']}"
    texto = f.render(f"Pausa: el jugador {numero} encontró {quien}", True, COLOR_TEXTO)
    caja = texto.get_rect(center=vista.center).inflate(30, 16)
    fondo = pygame.Surface(caja.size, pygame.SRCALPHA)
    fondo.fill(COLOR_FONDO)
    screen.blit(fondo, caja.topleft)
    pygame.draw.rect(screen, datos_tipo(tipo)["color"], caja, 2, border_radius=6)
    screen.blit(texto, texto.get_rect(center=caja.center))
