"""Prueba del clic en el mapa de la Emisión con dos pantallas.

    python pruebas/prueba_emision_dos_pantallas.py

El mapa de la Emisión (Resonante) guarda en el panel dónde se dibujó para
pasar el clic del mouse a coordenadas del mundo. Con el modo dos pantallas,
el de J3 se dibuja en la otra pantalla, con coordenadas de ESA pantalla: un
clic en la ventana principal que cayera en ese mismo rect le ponía la señal a
J3 (el mouse de la otra pantalla no cuenta, juego/app.py). Tampoco se pone
con la ventana que presenta a un alien abierta (el juego está detenido).
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
from juego.presentacion_aliens import PresentacionAliens, MIN_ABIERTA_MS
objetos_mapa.mapa_activo = lambda: "Nave"


class Teclas(dict):
    def __getitem__(self, k):
        return self.get(k, False)


pygame.key.get_pressed = lambda: Teclas()


class OtraPantalla:
    """Lo que el juego usa de juego/segunda_pantalla.SegundaPantalla."""
    def __init__(self, tam):
        self.surface = pygame.Surface(tam)
    ancho = property(lambda self: self.surface.get_width())
    alto = property(lambda self: self.surface.get_height())
    def es_suyo(self, evento): return getattr(evento, "window", None) == "otra"
    def espejo(self, origen): pass
    def mostrar(self): pass
    def cerrar(self): pass


g = App.Game()
g.mandos.por_puesto = {}
g.cantidad_jugadores = 3
g.abrir_seleccion_roles(ir=False)
for i, estado in enumerate(g.seleccion_roles):
    estado["listo"], estado["rol"] = True, App.ROLES[i]["nombre"]
g.iniciar_partida()
for _ in range(80):
    if g.transitions.is_idle():
        break
    g.transitions.update(g, 33)
g.saltar_tutorial()
g.presentacion = None
g.segunda = OtraPantalla((1280, 720))
j1, j2, j3 = g.jugadores
assert g._reparto_pantallas() == ([j1, j2], [j3])

# J3 (en la otra pantalla) tiene abierto el mapa de la Emisión.
j3.abrir_panel({"tipo": "emision", "cursor_mapa": list(j3.hitbox.center)})
g._dibujar()
rect = j3.panel["rect_mapa"]
g._manejar_click(rect.center)          # un clic en la ventana PRINCIPAL
assert j3.panel is not None and j3.panel.get("tipo") == "emision", \
    "un clic en la pantalla principal le puso la señal a J3, que está en la otra"
assert not g.senales
print("dos pantallas: un clic en la principal no toca el mapa de J3")

# Sin la otra pantalla, J3 está en la principal y el clic sí le sirve.
g.segunda = None
g._dibujar()
g._manejar_click(j3.panel["rect_mapa"].center)
assert j3.panel is None and len(g.senales) == 1
print("una pantalla: el clic pone la señal de J3")

# Con la ventana del alien nuevo abierta, el clic no hace nada.
g.senales.clear()
j3.recarga_ms = 0
j3.abrir_panel({"tipo": "emision", "cursor_mapa": list(j3.hitbox.center)})
g._dibujar()
g.presentacion = PresentacionAliens(g)
g.presentacion.abrir(j1, g.aliens[0])
g.presentacion.actualizar(MIN_ABIERTA_MS)
g._manejar_click(j3.panel["rect_mapa"].center)
assert j3.panel is not None and not g.senales, "con la presentación abierta se puso la señal"
print("con la presentación de un alien abierta, el clic espera")
print("OK")
