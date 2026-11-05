"""Prueba de jugar otra partida sin cerrar el juego.

    python pruebas/prueba_nueva_partida.py

Una partida de 4 en Fácil que se termina desde la pausa con las vistas de
prueba prendidas (Pausa > Opciones), y después, desde el menú, otra de 2 en
Difícil: la segunda tiene que arrancar limpia, sin nada de la primera.
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
from data.dificultad import DIFICULTADES
objetos_mapa.mapa_activo = lambda: "Nave"
DT = 1000 // 60
CLAVES = [d["clave"] for d in DIFICULTADES]


class Teclas(dict):
    def __getitem__(self, k):
        return self.get(k, False)


pygame.key.get_pressed = lambda: Teclas()

g = App.Game()
g.mandos.por_puesto = {}       # (sin mandos: el 3 y el 4 no se mueven)


def avanzar():
    for _ in range(80):
        if g.transitions.is_idle():
            break
        g.transitions.update(g, 33)


def jugar(cantidad, dificultad):
    """Del menú a la partida con las teclas, como un jugador."""
    g._activar_opcion_menu("jugar"); avanzar()
    assert g.current_screen == "cantidad"
    g.cantidad_seleccionada = App.OPCIONES.index(cantidad)
    g._manejar_tecla(pygame.K_RETURN); avanzar()
    assert g.current_screen == "dificultad"
    g.dificultad_seleccionada = CLAVES.index(dificultad)
    g._manejar_tecla(pygame.K_RETURN); avanzar()
    assert g.current_screen == "roles"
    for i, estado in enumerate(g.seleccion_roles):
        estado["cursor"] = i
    for i in range(cantidad):
        g._confirmar_rol(i, g.seleccion_roles[i])
    avanzar()
    assert g.current_screen == "partida" and len(g.jugadores) == cantidad


# ---------- Primera partida: 4, Fácil, con las vistas de prueba ----------
jugar(4, "facil")
g.saltar_tutorial()
for _ in range(60):
    g._actualizar_partida(DT)
if g.presentacion is not None:
    g.presentacion.actual = None
g._manejar_tecla(pygame.K_ESCAPE)
assert g.pausa is not None
g.pausa.seleccion = 1; g._manejar_tecla(pygame.K_RETURN)        # Opciones
acciones = [a for _, a in g.pausa.opciones()]
g.pausa.seleccion = acciones.index("grafo")
g._manejar_tecla(pygame.K_RIGHT)
assert g.vista_grafo == "nexus"
g._dibujar()
g._manejar_tecla(pygame.K_ESCAPE)                               # a la pausa
g.pausa.seleccion = 3; g._manejar_tecla(pygame.K_RETURN)        # Terminar partida
g.pausa.seleccion = 1; g._manejar_tecla(pygame.K_RETURN)        # Sí
avanzar()
assert g.current_screen == "menu" and g.pausa is None
print("primera partida: terminada desde la pausa con el grafo de NEXUS a la vista")

# ---------- Segunda partida: 2, Difícil ----------
jugar(2, "dificil")
assert g.vista_grafo is None, "la vista del grafo de la partida anterior no se apaga"
assert not g.mostrar_arbol_alien
assert g.pausa is None and g.tiempo_jugado_ms == 0
assert g.dificultad.clave == "dificil" and all(j.vidas == g.dificultad.vidas for j in g.jugadores)
assert g.tutorial is not None and g.tutorial.activo
assert g.sombra is None or g.sombra not in g.aliens
g._dibujar()
print("segunda partida: arranca limpia (sin el grafo, sin pausa, cronómetro en cero)")
print("OK")
