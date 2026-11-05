"""Prueba de un cuadro lento: un tirón no hace saltar la partida.

    python pruebas/prueba_cuadro_lento.py

Si el bucle se traba (F9 abriendo la otra ventana, arrastrar la ventana en
Windows con F11, la laptop que se suspende...), el siguiente `clock.tick()`
devuelve varios segundos. Antes ese `dt` entero llegaba a la partida: el
minijuego del escondite se llenaba de golpe (atrapado sin poder hacer nada),
los sustos y los avisos se saltaban y los relojes de las celdas, los eventos y
el director corrían segundos en un cuadro. Ahora `Game.run` lo recorta a
DT_MAXIMO_MS.
"""

import os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)
import pygame; pygame.init()

from juego import app as App
from juego import objetos_mapa
from entidades.minijuego_latidos import MinijuegoLatidos
objetos_mapa.mapa_activo = lambda: "Nave"
TOPE = getattr(App, "DT_MAXIMO_MS", 100)


class Teclas(dict):
    def __getitem__(self, k):
        return self.get(k, False)


pygame.key.get_pressed = lambda: Teclas()


class RelojTrabado:
    """Un clock que devuelve lo que se le diga en cada tick."""
    def __init__(self, cuadros):
        self.cuadros = list(cuadros)
    def tick(self, fps=0):
        return self.cuadros.pop(0) if self.cuadros else 16
    def get_fps(self):
        return 60.0


g = App.Game()
g.mandos.por_puesto = {}
g.cantidad_jugadores = 2
g.abrir_seleccion_roles(ir=False)
for i, estado in enumerate(g.seleccion_roles):
    estado["listo"], estado["rol"] = True, App.ROLES[i]["nombre"]
g.iniciar_partida()
for _ in range(80):
    if g.transitions.is_idle():
        break
    g.transitions.update(g, 33)
assert g.current_screen == "partida"
g.saltar_tutorial()
g.presentacion = None
for a in g.aliens:
    a.descanso_ms = 10 ** 9

# Un jugador escondido con un alien revisándolo (el minijuego de los latidos).
jugador = g.jugadores[0]
alien = g.aliens[0]
escondite = g.escondites[0]
jugador.esconderse(escondite)
alien.escondite_objetivo = escondite
jugador.minijuego = MinijuegoLatidos(jugador.pulso, alien, escondite)
amenaza = jugador.minijuego.amenaza

# El bucle de verdad (Game.run), con un cuadro trabado de 5 s.
recibidos = []
actualizar = g._actualizar_partida


def espiar(dt=0):
    recibidos.append(dt)
    actualizar(dt)
    if len(recibidos) >= 3:
        g.running = False


g._actualizar_partida = espiar
g.clock = RelojTrabado([16, 5000, 16])
pygame.quit_original, pygame.quit = pygame.quit, lambda: None   # que run() no cierre pygame
try:
    g.run()
except SystemExit:
    pass
pygame.quit = pygame.quit_original

assert recibidos[1] <= TOPE, recibidos
assert jugador.minijuego is not None and not jugador.minijuego.terminado, \
    "un tirón de 5 s llenó el minijuego del escondite de golpe"
assert jugador.minijuego.amenaza < amenaza + 10, (amenaza, jugador.minijuego.amenaza)
assert g.tiempo_jugado_ms <= 16 + TOPE + 16, g.tiempo_jugado_ms
print(f"un cuadro de 5000 ms llega a la partida como {recibidos[1]} ms")
print("OK")
