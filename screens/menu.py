"""Pantalla de menú principal.

El fondo (Imagenes/Fondos/FondoDeMenu.jpeg) ya trae el título del juego
dibujado, así que aquí solo se dibujan los botones encima, al estilo del
menú de EmpatiaQuest.
"""

import pygame

from juego.assets import dibujar_fondo_o_color
from juego.fuentes import fuente


OPCIONES_MENU = [
    ("Jugar", "jugar"),
    ("Logros", "logros"),
    ("Ayuda", "ayuda"),
    ("Créditos", "creditos"),
    ("Salir", "salir"),
]

COLOR_PISTA = (194, 216, 248)
COLOR_SOMBRA_PISTA = (14, 16, 30)


def render_menu(screen, botones=None, seleccionado=0):
    # Fondo: usa Imagenes/Fondos/fondo_menu.png (o cualquier imagen de menú
    # que haya en esa carpeta); si no hay ninguna, rellena de color.
    dibujar_fondo_o_color(screen, "Imagenes/Fondos/fondo_menu.png", (35, 40, 60))

    if botones:
        mouse_pos = pygame.mouse.get_pos()
        for i, boton in enumerate(botones):
            hover = boton.contains(mouse_pos) or i == seleccionado
            boton.draw(screen, hover=hover)

    pista = "Mouse o flechas + Enter"
    etiqueta = fuente("small").render(pista, True, COLOR_PISTA)
    sombra = fuente("small").render(pista, True, COLOR_SOMBRA_PISTA)
    rect = etiqueta.get_rect(center=(screen.get_width() // 2, screen.get_height() - 34))
    screen.blit(sombra, rect.move(2, 2))
    screen.blit(etiqueta, rect)
