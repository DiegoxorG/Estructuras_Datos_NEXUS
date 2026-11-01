"""Prueba del menú de pausa: Esc congela la partida y abre el menú.

    python pruebas/prueba_pausa.py
"""

import os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)
import pygame; pygame.init()
OUT = os.path.join(RAIZ, "pruebas", "capturas")
os.makedirs(OUT, exist_ok=True)

from juego import app as App
from juego import objetos_mapa
from juego.audio_manager import audio_manager
objetos_mapa.mapa_activo = lambda: "Nave"
DT = 1000 // 60


class Teclas(dict):
    def __getitem__(self, k):
        return self.get(k, False)


pygame.key.get_pressed = lambda: Teclas()

g = App.Game()


def avanzar():
    for _ in range(80):
        if g.transitions.is_idle():
            break
        g.transitions.update(g, 33)


g._activar_opcion_menu("jugar"); avanzar(); g.current_screen = "cantidad"
g._manejar_tecla(pygame.K_RETURN); avanzar(); g.current_screen = "roles"
g._manejar_tecla(pygame.K_e); g._manejar_tecla(pygame.K_RETURN)
avanzar(); g.current_screen = "partida"
g.saltar_tutorial()

# Esc ya no saca al menú: abre la pausa.
g._manejar_tecla(pygame.K_ESCAPE)
assert g.current_screen == "partida" and g.pausa is not None and g.pausa.vista == "menu"
assert [a for _, a in g.pausa.opciones()] == ["continuar", "opciones", "logros", "confirmar"]

# Congelado: ni el cronómetro ni los aliens se mueven.
tiempo = g.tiempo_jugado_ms
pos_aliens = [a.centro for a in g.aliens]
for _ in range(120):
    if g.current_screen == "partida" and g.transitions.is_idle():
        if g.pausa is not None:
            g.pausa.actualizar(DT)
        else:
            g._actualizar_partida(DT)
assert g.tiempo_jugado_ms == tiempo
assert [a.centro for a in g.aliens] == pos_aliens
# Las teclas de los jugadores no hacen nada con la pausa abierta.
g._manejar_tecla(pygame.K_l)
assert g.oscuridad is True
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "pausa.png"))
print("Esc abre la pausa y la partida queda congelada")

# Logros abre el árbol; Esc vuelve al menú de pausa (screens/logros.py).
g._manejar_tecla(pygame.K_DOWN); g._manejar_tecla(pygame.K_DOWN)
g._manejar_tecla(pygame.K_RETURN)
assert g.pausa.vista == "logros" and g.pausa.nodo is g.logros.arbol.raiz
g._manejar_tecla(pygame.K_ESCAPE)
assert g.pausa.vista == "menu"
print("Logros abre el árbol y Esc vuelve")

# Opciones: volumen, oscuridad, volver.
g.pausa.seleccion = 1; g._manejar_tecla(pygame.K_RETURN)
assert g.pausa.vista == "opciones"
antes = round(audio_manager.sfx_volume * 100)
g._manejar_tecla(pygame.K_LEFT)
assert round(audio_manager.sfx_volume * 100) == antes - 10
g._manejar_tecla(pygame.K_RIGHT)
g.pausa.seleccion = 1; g._manejar_tecla(pygame.K_RETURN)
assert g.oscuridad is False
g._manejar_tecla(pygame.K_RETURN); assert g.oscuridad is True
# Las vistas de prueba: hitboxes y árbol del alien (ya no hay atajos H/B/N/L).
acciones = [a for _, a in g.pausa.opciones()]
assert acciones == ["efectos", "oscuridad", "pantalla_completa", "hitboxes", "arbol", "grafo", "volver"]
g.pausa.seleccion = 3; g._manejar_tecla(pygame.K_RETURN)
assert g.mostrar_hitboxes is True
g._manejar_tecla(pygame.K_RETURN); assert g.mostrar_hitboxes is False
g.pausa.seleccion = 4
assert not g.mostrar_arbol_alien
g._manejar_tecla(pygame.K_RIGHT)
assert g.mostrar_arbol_alien and g.alien_en_vista == 0 and "1 de" in g.pausa.opciones()[4][0]
g._manejar_tecla(pygame.K_RETURN)
assert g.mostrar_arbol_alien and g.alien_en_vista == 1
for _ in range(len(g.aliens) - 1):
    g._manejar_tecla(pygame.K_RIGHT)
assert not g.mostrar_arbol_alien, "después del último alien vuelve a No"
g._manejar_tecla(pygame.K_LEFT)
assert g.mostrar_arbol_alien and g.alien_en_vista == len(g.aliens) - 1
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "pausa_opciones.png"))
for _ in range(len(g.aliens)):
    g._manejar_tecla(pygame.K_LEFT)
assert not g.mostrar_arbol_alien
g._manejar_tecla(pygame.K_ESCAPE)
assert g.pausa.vista == "menu"
print("Opciones: volumen, oscuridad, hitboxes y árbol del alien; Esc vuelve")

# Continuar.
g.pausa.seleccion = 0; g._manejar_tecla(pygame.K_RETURN)
assert g.pausa is None
g._actualizar_partida(DT)
assert g.tiempo_jugado_ms > tiempo
print("Continuar quita la pausa y el cronómetro sigue")

# Terminar partida pide confirmación; "No" vuelve al menú de pausa.
g._manejar_tecla(pygame.K_ESCAPE)
g.pausa.seleccion = 3; g._manejar_tecla(pygame.K_RETURN)
assert g.pausa.vista == "confirmar"
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "pausa_confirmar.png"))
g._manejar_tecla(pygame.K_RETURN)     # la primera opción es "No"
assert g.pausa.vista == "menu" and g.current_screen == "partida"

# Con el mouse: clic en "Terminar partida" y luego en "Sí".
g._dibujar()
g._manejar_click(g.pausa.rects[3].center)
assert g.pausa.vista == "confirmar"
g._dibujar()
g._manejar_click(g.pausa.rects[1].center)
avanzar()
assert g.current_screen == "menu" and g.pausa is None
print("Terminar partida confirma y vuelve al menú (también con el mouse)")

# El mando: START abre la pausa, B la cierra.
g2 = App.Game()
g2.jugadores, g2.current_screen = g.jugadores, "partida"
g2.mundo = g.mundo
g2._tecla_mando(2, "pausa")
assert g2.pausa is not None
g2._tecla_mando(2, "abajo"); assert g2.pausa.seleccion == 1
g2._tecla_mando(2, "volver"); assert g2.pausa is None
print("Mando: START abre la pausa y B la cierra")
print("OK")
