"""Dibujo del menú de pausa (la lógica está en pausa.py).

Se dibuja encima de la partida congelada: un velo oscuro sobre todas las
pantallas y una columna de botones al centro, con el mismo estilo que los del
menú principal.
"""

import pygame

from juego.fuentes import fuente, fuente_de_tamano
from juego.mandos import botones_conectados
from juego.ui_components import Button
from screens.paneles import COLOR_TITULO, COLOR_TENUE, COLOR_INFO
from screens.logros import render_arbol_logros


COLOR_VELO = (8, 8, 18, 175)
COLOR_FRANJA = (14, 14, 28)
PISTA = "Flechas + Enter  ·  Esc: volver  ·  Mando: cruceta, A y B"


def _pista():
    """PISTA con los botones de los mandos conectados (A/B o Cruz/Círculo)."""
    return (f"Flechas + Enter  ·  Esc: volver  ·  Mando: cruceta, "
            f"{botones_conectados('interactuar')} y {botones_conectados('volver')}")


def render_pausa(screen, pausa):
    ancho, alto = screen.get_size()
    if pausa.vista == "logros" and pausa.arbol is not None:
        pausa.rects_logros = render_arbol_logros(screen, pausa.arbol, pausa.nodo)
        return
    velo = pygame.Surface((ancho, alto), pygame.SRCALPHA)
    velo.fill(COLOR_VELO)
    screen.blit(velo, (0, 0))

    opciones = pausa.opciones()
    ancho_boton = min(520 if pausa.vista == "opciones" else 420, int(ancho * 0.8))
    alto_boton = 52 if alto >= 600 else 40
    separacion = 14 if alto >= 600 else 8
    alto_total = len(opciones) * alto_boton + (len(opciones) - 1) * separacion
    y = alto // 2 - alto_total // 2 + 30

    titulo = fuente("title").render(pausa.titulo(), True, COLOR_TITULO)
    y_titulo = y - titulo.get_height() - (56 if pausa.subtitulo() else 24)
    screen.blit(titulo, titulo.get_rect(midtop=(ancho // 2, y_titulo)))
    if pausa.subtitulo():
        sub = fuente("small").render(pausa.subtitulo(), True, COLOR_TENUE)
        screen.blit(sub, sub.get_rect(midbottom=(ancho // 2, y - 14)))

    mouse = pygame.mouse.get_pos()
    pausa.rects = []
    for i, (texto, accion) in enumerate(opciones):
        rect = pygame.Rect(ancho // 2 - ancho_boton // 2, y, ancho_boton, alto_boton)
        boton = Button(rect, texto, accion)
        boton.draw(screen, hover=(i == pausa.seleccion or rect.collidepoint(mouse)))
        if accion == "logros" and pausa.arbol is not None:
            cuenta = fuente("small").render(f"{pausa.arbol.obtenidos()}/{pausa.arbol.total()}",
                                            True, (50, 42, 94))
            screen.blit(cuenta, cuenta.get_rect(midright=(rect.right - 16, rect.centery)))
        pausa.rects.append(rect)
        y += alto_boton + separacion

    if pausa.aviso_ms > 0:
        aviso = fuente("body").render(pausa.aviso, True, COLOR_INFO)
        screen.blit(aviso, aviso.get_rect(midtop=(ancho // 2, y + 6)))

    # La pista va en una franja propia, encima de la barra de teclas de la partida.
    pista = fuente_de_tamano(18).render(_pista(), True, COLOR_TENUE)
    if pista.get_width() > ancho - 32:
        pista = fuente_de_tamano(13).render(_pista(), True, COLOR_TENUE)
    franja = pygame.Rect(0, alto - pista.get_height() - 20, ancho, pista.get_height() + 20)
    pygame.draw.rect(screen, COLOR_FRANJA, franja)
    screen.blit(pista, pista.get_rect(center=franja.center))
