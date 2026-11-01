"""Prueba de qué hace un alien cuando un sello del Forjador le corta la ruta
(entidades/alien._elegir_punto_patrulla, navegacion.distancia_camino).

    python pruebas/prueba_sellos.py

Con el sello levantado, el alien patrulla solo su lado: no da la vuelta a
media nave para llegar a los puntos del otro lado (antes, el Vigía entre
Comando y Biosfera se iba por Laboratorio, General y Residencial). Se prueba
con cada sello de MapaFinal que corta una ruta: durante 40 s de patrulla el
alien no se aleja de su ruta. Y al bajar el sello, vuelve a recorrerla toda.
"""

import os, sys, math
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)
import pygame; pygame.init()

from juego import app as App
from juego import objetos_mapa, navegacion
objetos_mapa.mapa_activo = lambda: "MapaFinal"
DT = 1000 // 60


class Teclas(dict):
    def __getitem__(self, k):
        return self.get(k, False)


pygame.key.get_pressed = lambda: Teclas()

g = App.Game()
g.screen = pygame.display.set_mode((1280, 720))
def avanzar():
    for _ in range(80):
        if g.transitions.is_idle(): break
        g.transitions.update(g, 33)
g._activar_opcion_menu("jugar"); avanzar(); g._manejar_tecla(pygame.K_RETURN); avanzar()
g._manejar_tecla(pygame.K_RETURN); avanzar()
g.seleccion_roles[0]["cursor"] = 0; g._manejar_tecla(pygame.K_e)
g.seleccion_roles[1]["cursor"] = 1; g._manejar_tecla(pygame.K_RETURN); avanzar()
g.current_screen = "partida"
g.saltar_tutorial()
mundo = g.mundo
for i in range(len(g.mision.puertas)):
    g.mision.abrir_puerta(None, i)

# distancia_camino: igual a lo que mide el camino; None si se pasa del tope.
nav = navegacion.de_mundo(mundo, 34, 20)
a, b = (2963, 752), (1886, 750)
d = nav.distancia_camino(a, b, 5000)
assert d is not None and abs(d - math.dist(a, b)) < 120, d
assert nav.distancia_camino(a, b, math.dist(a, b) * 0.5) is None
print(f"distancia_camino: {d:.0f} px (en línea recta {math.dist(a, b):.0f})")

casos = []
for panel in g.paneles:
    sello = panel.get("sello_rect")
    if sello is None:
        continue
    for alien in g.aliens:
        ruta = list(getattr(alien, "ruta", None) or [])
        n = len(ruta)
        if n > 1 and any(sello.inflate(20, 20).clipline(ruta[k], ruta[(k + 1) % n]) for k in range(n)):
            casos.append((sello, alien, ruta))
assert casos, "MapaFinal no tiene sellos que corten rutas"


def patrullar(alien, segundos):
    """Solo ese alien, sin jugadores a la vista: patrulla. Devuelve lo más
    que se alejó de su ruta (de cualquier tramo)."""
    lejos = 0.0
    for _ in range(int(segundos * 1000 / DT)):
        alien.actualizar(DT, mundo, [], None, [], None)
        x, y = alien.centro
        cerca = min(_a_tramo((x, y), alien.ruta[k], alien.ruta[(k + 1) % len(alien.ruta)])
                    for k in range(len(alien.ruta)))
        lejos = max(lejos, cerca)
    return lejos


def _a_tramo(p, a, b):
    ax, ay = a; bx, by = b
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
    return math.dist(p, (ax + t * dx, ay + t * dy))


for sello, alien, ruta in casos:
    mundo.bloqueos_alien[:] = [sello]
    alien.hitbox.center = ruta[0]
    alien.indice_ruta = 0
    alien.descanso_ms = 0; alien.punto_ruido = None; alien.rastro.clear()
    alien.escondite_objetivo = None; alien.busqueda_ms = 0
    alien._patrulla_revisada = None
    lejos = patrullar(alien, 40)
    print(f"  {alien.nombre:10s} con el sello en {sello.center}: lo más lejos de su ruta = {lejos:.0f} px")
    assert lejos < 260, f"{alien.nombre} se fue lejos de su ruta ({lejos:.0f} px): dio un rodeo"
mundo.bloqueos_alien[:] = []

# Sin el sello, vuelve a recorrer la ruta entera.
sello, alien, ruta = casos[0]
alien.hitbox.center = ruta[0]; alien.indice_ruta = 0; alien._patrulla_revisada = None
vistos = set()
for _ in range(int(90 * 1000 / DT)):
    alien.actualizar(DT, mundo, [], None, [], None)
    vistos.add(alien.indice_ruta)
assert len(vistos) == len(ruta), (len(vistos), len(ruta))
print(f"sin el sello, {alien.nombre} vuelve a recorrer los {len(ruta)} puntos de su ruta")
print("\nTODO OK")
