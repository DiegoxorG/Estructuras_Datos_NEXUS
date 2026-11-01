"""Prueba: una partida entera ganada en Normal, con NEXUS y el Cambiaformas.

    python pruebas/prueba_victoria.py

Consolas, piezas, la cápsula que no se repara sin planos, los planos al 70%
de confianza (Normal), la huida y la victoria. Revisa también la flecha al
objetivo en cada parte.
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
from misiones import mision as M
objetos_mapa.mapa_activo = lambda: "Nave"      # sin tocar el mapa activo real
DT = 1000 // 60


def nueva_partida(roles):
    g = App.Game()
    from juego.dificultad import Dificultad
    g.dificultad = Dificultad('normal')
    def avanzar():
        for _ in range(80):
            if g.transitions.is_idle(): break
            g.transitions.update(g, 33)
    g._activar_opcion_menu("jugar"); avanzar(); g.current_screen = "cantidad"
    g._manejar_tecla(pygame.K_RETURN); avanzar(); g.current_screen = "roles"
    nombres = [r["nombre"] for r in App.ROLES]
    g.seleccion_roles[0]["cursor"] = nombres.index(roles[0]); g._manejar_tecla(pygame.K_e)
    g.seleccion_roles[1]["cursor"] = nombres.index(roles[1]); g._manejar_tecla(pygame.K_RETURN)
    avanzar(); g.current_screen = "partida"
    # El tutorial ya no se acaba solo: aquí se da por terminado (con el
    # tutorial abierto la puerta de la prisión no abre).
    if g.tutorial is not None:
        g.saltar_tutorial()
        g.presentacion = None   # la ventana de alien nuevo pausaría la prueba
    # NEXUS se prueba aparte (prueba_nexus.py): aquí no mete rumores ni pide planos.
    # Y el Cambiaformas también (prueba_cambiaformas.py).
    return g


def poner(j, punto):
    j.personaje.hitbox.center = (int(punto[0]), int(punto[1]))
    j.personaje.sync_sprite_from_hitbox()


def calmar_aliens(g):
    for a in g.aliens:
        a.descanso_ms = 10 ** 9; a.punto_ruido = None; a.escondite_objetivo = None


def frames(g, n):
    for _ in range(n):
        g._actualizar_partida(DT)


def cap(g, nombre):
    g._dibujar(); pygame.display.flip()
    pygame.image.save(g.screen, os.path.join(OUT, nombre))


def mantener(g, j, segundos):
    for _ in range(int(segundos * 1000 / DT) + 2):
        g.mision.mantener(j, DT)
        g.mision.actualizar(DT)



g = nueva_partida(("Tecnomante", "Forjador"))
tec, forj = g.jugadores
m = g.mision
assert g.dificultad.clave == "normal" and g.nexus.umbral_planos == 0.70
g.cambiaformas.calma_ms = 10 ** 9
g.nexus.reloj_rumor_ms = 10 ** 9
calmar_aliens(g)
m.abrir_puerta(tec)
for consola in m.consolas:
    poner(tec, consola["rect"].center)
    mantener(g, tec, M.SABOTAJE_ROL_S)
frames(g, 2)
assert m.fase == "capsula", m.fase
print("flecha forjador:", m.punto_objetivo(forj)[1], "| tecnomante:", m.punto_objetivo(tec)[1])
for pieza in g.piezas[:3]:
    poner(forj, pieza["rect"].center)
    frames(g, 1)
poner(forj, m.capsula.center); poner(tec, m.capsula.center)
assert m.interactuar(forj) and m.piezas_entregadas == 3
mantener(g, forj, M.REPARACION_ROL_S)
assert m.reparacion == 0 and m.fase == "capsula", "sin planos no se repara"
print("sin planos:", m.objetivo(), "| flecha:", m.punto_objetivo(forj))
red = g.nexus
presos = red._presos()
for n in presos[: int(len(presos) * 0.8)]:
    red.grafo.datos[n]["color"] = "verde"
frames(g, 3)
assert red.planos, red.barras()
mantener(g, forj, M.REPARACION_ROL_S)
assert m.fase == "huida", m.fase
print("con planos (70%): reparada | flecha:", m.punto_objetivo(tec)[1])
calmar_aliens(g); g.cambiaformas.descanso_ms = 10**9
poner(tec, m.capsula.center); poner(forj, m.capsula.center)
frames(g, 3)
assert m.resultado == "victoria", m.resultado
for _ in range(80):
    if g.transitions.is_idle(): break
    g.transitions.update(g, 33)
g.current_screen = "resultados"
cap(g, "victoria_normal.png")
print("VICTORIA en Normal con NEXUS y Cambiaformas")
print("\nTODO OK")
