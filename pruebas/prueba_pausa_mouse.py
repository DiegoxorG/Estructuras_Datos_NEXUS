"""Prueba del menú de pausa con el mouse: cambiar de vista con un clic.

    python pruebas/prueba_pausa_mouse.py

Los rects de las opciones los llena el dibujo (screens/pausa.py). Al cambiar
de vista con un clic (Terminar partida -> confirmar, Opciones -> Volver), los
de la vista anterior seguían ahí hasta el siguiente dibujo: si en el mismo
cuadro llegaba un movimiento del mouse, la selección quedaba en una opción que
la vista nueva no tiene y Enter (o izquierda/derecha) tumbaba el juego con un
IndexError.
"""

import os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)
import pygame; pygame.init()
pantalla = pygame.display.set_mode((960, 600))

from juego.pausa import MenuPausa
from screens.pausa import render_pausa


class Juego:
    """Lo que el menú de pausa le pregunta al juego."""
    oscuridad = True
    pantalla_completa = False
    mostrar_hitboxes = False
    mostrar_arbol_alien = False
    aliens = []
    alien_en_vista = 0
    vista_grafo = None
    logros = None


# Terminar partida con el mouse, y el mouse se mueve en el mismo cuadro.
pausa = MenuPausa(Juego())
render_pausa(pantalla, pausa)
donde = pausa.rects[3].center
assert pausa.click(donde) is None and pausa.vista == "confirmar"
pausa.mover_mouse(donde)
assert pausa.seleccion < len(pausa.opciones()), (pausa.seleccion, pausa.opciones())
assert pausa.tecla(pygame.K_RETURN) is None and pausa.vista == "menu", \
    "Enter en la confirmación tiene que ser la primera opción (No)"
print("Terminar partida con el mouse: la confirmación no hereda la selección del menú")

# Opciones > Volver con el mouse, y otra vez un movimiento en el mismo cuadro.
pausa = MenuPausa(Juego())
pausa.seleccion = 1
pausa.tecla(pygame.K_RETURN)
assert pausa.vista == "opciones"
render_pausa(pantalla, pausa)
donde = pausa.rects[-1].center
pausa.click(donde)
assert pausa.vista == "menu"
pausa.mover_mouse(donde)
assert pausa.seleccion < len(pausa.opciones())
for tecla in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_RETURN):
    pausa.tecla(tecla)
render_pausa(pantalla, pausa)
print("Opciones > Volver con el mouse: sin opciones fantasma")
print("OK")
