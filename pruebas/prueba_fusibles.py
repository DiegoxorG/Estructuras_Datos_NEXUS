"""Prueba de qué caja de fusibles falla en un apagón (misiones/eventos.py).

    python pruebas/prueba_fusibles.py

1. Solo falla una caja a la que se llega caminando desde el inicio con lo que
   está cerrado ahora: en MapaFinal, la de la prisión no mientras su puerta
   (con código) esté cerrada. Si no hay ninguna alcanzable, no se va la luz.
2. Cuál falla: en Fácil, casi siempre la más cercana a los jugadores; en
   Normal y Difícil, cada vez más lejos; y en todas, más lejos a medida que
   avanzan en la misión. Inteligente según su nivel.
"""

import os, sys, math, random
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)
import pygame; pygame.init()

from juego import app as App
from juego import objetos_mapa
from juego import dificultad as modulo_dificultad
from juego.dificultad import Dificultad
from screens.seleccion import OPCIONES
objetos_mapa.mapa_activo = lambda: "MapaFinal"
NOMBRES = [r["nombre"] for r in App.ROLES]


class Teclas(dict):
    def __getitem__(self, k):
        return self.get(k, False)


pygame.key.get_pressed = lambda: Teclas()


def nueva_partida(clave="normal"):
    g = App.Game()
    g.screen = pygame.display.set_mode((1280, 720))
    def avanzar():
        for _ in range(80):
            if g.transitions.is_idle(): break
            g.transitions.update(g, 33)
    g._activar_opcion_menu("jugar"); avanzar(); g._manejar_tecla(pygame.K_RETURN); avanzar()
    from data.dificultad import DIFICULTADES
    g.dificultad_seleccionada = [d["clave"] for d in DIFICULTADES].index(clave)
    g._manejar_tecla(pygame.K_RETURN); avanzar()
    g.seleccion_roles[0]["cursor"] = 0; g._manejar_tecla(pygame.K_e)
    g.seleccion_roles[1]["cursor"] = 1; g._manejar_tecla(pygame.K_RETURN); avanzar()
    g.current_screen = "partida"
    g.saltar_tutorial()
    g.presentacion = None
    return g


# ---------- 1. Solo las alcanzables ----------
g = nueva_partida()
ev, m = g.eventos, g.mision
assert len(ev.cajas) >= 2
# Al empezar (en Control, con la puerta del código cerrada) solo las de adentro.
al_inicio = ev._cajas_alcanzables()
assert 0 < len(al_inicio) < len(ev.cajas), [c["rect"].center for c in al_inicio]
celdas = [c["punto"] for c in m.celdas]
def en_prision(caja):
    return min(math.dist(caja["rect"].center, p) for p in celdas) < 900
prision = [c for c in ev.cajas if en_prision(c)]
adentro = [p for p in m.puertas if p.get("adentro")]
if prision and adentro:
    for i, p in enumerate(m.puertas):
        if p not in adentro:
            m.abrir_puerta(None, i)
    alcanzables = ev._cajas_alcanzables()
    assert not any(c in alcanzables for c in prision), "con la puerta de la prisión cerrada, su caja no falla"
    for _ in range(40):
        ev.restaurar_luz()
        ev.lanzar("apagon")
        assert ev.caja not in prision
    m.abrir_puerta(None, m.puertas.index(adentro[0]))
    assert all(c in ev._cajas_alcanzables() for c in prision), "abierta, ya puede fallar"
    print(f"la caja de la prisión solo falla con la puerta {adentro[0]['nombre']} abierta")
ev.restaurar_luz()
# Si no se puede llegar a ninguna, no se va la luz.
todas = list(ev.cajas)
ev.cajas = [c for c in todas if c not in ev._cajas_alcanzables()] or []
if ev.cajas:
    assert "apagon" not in ev.posibles() and ev.lanzar("apagon") is None and not ev.apagon
    print("sin cajas alcanzables, no hay apagón")
ev.cajas = todas
print("solo fallan las cajas a las que se llega:", len(al_inicio), "al empezar de", len(todas))

# ---------- 2. Cuál falla ----------
for i in range(len(m.puertas)):
    m.abrir_puerta(None, i)
cajas = ev._cajas_alcanzables()
j1 = g.jugadores[0]
jugadores = [j for j in g.jugadores]
original = modulo_dificultad.progreso_mision


def lejania_media(clave, progreso, nivel=None):
    g.dificultad = Dificultad(clave)
    if nivel is not None:
        g.dificultad.nivel = nivel
    modulo_dificultad.progreso_mision = lambda mision: progreso
    ev.rng = random.Random(5)
    d = [min(math.dist(c["rect"].center, j.hitbox.center) for j in jugadores) for c in cajas]
    cerca, lejos = min(d), max(d)
    total = 0
    for _ in range(400):
        c = ev.elegir_caja(cajas)
        total += (d[cajas.index(c)] - cerca) / (lejos - cerca)
    return total / 400


medias = {}
for clave in ("facil", "normal", "dificil"):
    medias[clave] = (lejania_media(clave, 0.0), lejania_media(clave, 1.0))
medias["inteligente (Pesadilla)"] = (lejania_media("inteligente", 0.0, 3.0), lejania_media("inteligente", 1.0, 3.0))
modulo_dificultad.progreso_mision = original
for clave, (inicio, fin) in medias.items():
    print(f"  {clave:24s} lejanía media: al empezar {inicio:.2f}, al final {fin:.2f}")
assert medias["facil"][0] < 0.15, "en Fácil, al empezar, casi siempre la más cercana"
assert medias["facil"][0] < medias["normal"][0] < medias["dificil"][0]
assert all(fin > inicio for inicio, fin in medias.values()), "más lejos a medida que avanzan"
print("cuál falla: más cerca en Fácil, más lejos en Difícil, y más lejos al avanzar")
print("\nTODO OK")
