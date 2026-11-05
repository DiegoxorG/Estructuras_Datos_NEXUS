"""Prueba: 3 o 4 jugadores sin mandos, con el Tecnomante o el Forjador en un
puesto de mando.

    python pruebas/prueba_roles_sin_mando.py

Sin mandos conectados, los jugadores 3 y 4 escogen rol con el teclado pero en
partida no se mueven (README, "Como se juega"). La misión ya no los contaba
para ganar ni perder, pero sí para saber qué roles había: si el Tecnomante o
el Forjador quedaban en esos puestos no salían el decodificador ni el kit, y
como nadie que se moviera podía hackear las consolas o recoger las piezas, la
misión no se podía terminar (lo encontró pruebas/simulador_masivo.py: partidas
de 4 sin mandos atascadas en la cápsula con 0 piezas).
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
objetos_mapa.mapa_activo = lambda: "Nave"


class Teclas(dict):
    def __getitem__(self, k):
        return self.get(k, False)


pygame.key.get_pressed = lambda: Teclas()


def nueva_partida(roles):
    g = App.Game()
    g.mandos.por_puesto.clear()          # sin mandos conectados
    def avanzar():
        for _ in range(80):
            if g.transitions.is_idle(): break
            g.transitions.update(g, 33)
    g._activar_opcion_menu("jugar"); avanzar()
    g.cantidad_seleccionada = len(roles) - 2
    g._manejar_tecla(pygame.K_RETURN); avanzar()
    g.current_screen = "roles"
    g.abrir_seleccion_roles(ir=False)
    for estado, rol in zip(g.seleccion_roles, roles):
        estado["listo"], estado["rol"] = True, rol
    g.iniciar_partida(); avanzar()
    g.saltar_tutorial()
    return g


# El Tecnomante (puesto 3) y el Forjador (puesto 4) no se mueven.
g = nueva_partida(("Biomante", "Resonante", "Tecnomante", "Forjador"))
m = g.mision
assert [j.puede_moverse for j in g.jugadores] == [True, True, False, False]
assert m.falta_tecnomante and m.falta_forjador and m.piezas_para_todos, (
    "sin mando, el Tecnomante y el Forjador del puesto 3 y 4 no pueden hacer lo suyo")
tipos = {c["tipo"] for c in m.consumibles}
assert "decodificador" in tipos and "kit" in tipos, f"faltan consumibles: {tipos}"

# Con el Tecnomante en un puesto que sí se mueve, todo como siempre.
g = nueva_partida(("Tecnomante", "Resonante", "Biomante"))
m = g.mision
assert not m.falta_tecnomante and m.falta_forjador
assert "decodificador" not in {c["tipo"] for c in m.consumibles}
print("OK: sin mando, los roles de los puestos 3 y 4 no cuentan para la misión")
