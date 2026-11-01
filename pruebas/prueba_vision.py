"""Prueba del campo de visión (vision.py): los jugadores no ven a través de
las paredes ni de las compuertas bajadas, y los aliens que no ven no se dibujan.

    python pruebas/prueba_vision.py
"""

import os, sys, time
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
from juego import vision
objetos_mapa.mapa_activo = lambda: "Nave"

# ================= Campo sin juego: una pared sola =================
pared = pygame.Rect(100, -50, 20, 100)
c = vision.Campo((0, 0), [pared], radio=500)
assert c.ve_punto((90, 0)), "antes de la pared se ve"
assert not c.ve_punto((300, 0)), "detrás de la pared no"
assert c.ve_punto((300, 200)), "por el lado de la pared sí"
assert not c.ve_punto((0, 600)), "más allá del radio no"
assert len(c.puntos) >= vision.RAYOS
# Detrás de la pared el polígono no llega más allá de la pared.
assert all(x <= pared.right + vision.ENTRA_EN_PARED + 1 for x, y in c.puntos if abs(y) < 40)
print("Campo: la pared tapa lo de atrás")

# El mismo origen con las mismas paredes reusa el cálculo.
assert vision.campo_de((0, 0), [pared], 500) is vision.campo_de((0, 0), [pared], 500)
# Moverse menos que la rejilla (PASO_ORIGEN) no lo recalcula; más, sí.
assert vision.campo_de((0, 0), [pared], 500) is vision.campo_de((1, 0), [pared], 500)
assert vision.campo_de((0, 0), [pared], 500) is not vision.campo_de((vision.PASO_ORIGEN, 0), [pared], 500)


# ================= En la partida =================
NOM = [r["nombre"] for r in App.ROLES]
g = App.Game()
g.screen = pygame.Surface((1366, 768)); g.ancho, g.alto = 1366, 768
g.cantidad_jugadores = 4; g.abrir_seleccion_roles()
def avanzar():
    for _ in range(80):
        if g.transitions.is_idle(): break
        g.transitions.update(g, 33)
avanzar()
for i, e in enumerate(g.seleccion_roles):
    e["listo"], e["rol"] = True, NOM[i]
g.iniciar_partida(); avanzar()
g.current_screen = "partida"; g.saltar_tutorial()
mundo = g.mundo
assert g._extras_dibujo()["vision"], "el campo de visión está siempre"
assert not g._extras_dibujo()["oscuridad"], "la linterna solo en un apagón"


def poner(cosa, centro):
    cosa.hitbox.center = centro
    if hasattr(cosa, "sync_sprite_from_hitbox"):
        cosa.sync_sprite_from_hitbox()


# Una pared gruesa: un jugador a un lado y un alien al otro, a la misma altura.
jugador, alien = g.jugadores[0], g.aliens[0]
encontrado = None
for pared in sorted(mundo.paredes, key=lambda r: -r.height):
    if pared.width > 300:
        continue
    for y in range(pared.top + 60, pared.bottom - 60, 40):
        izq = (pared.left - 50, y)
        der = (pared.right + 50, y)
        libre = lambda p: not mundo.colisiona(pygame.Rect(p[0] - 20, p[1] - 12, 40, 24))
        if libre(izq) and libre(der):
            encontrado = izq, der
            break
    if encontrado:
        break
assert encontrado, "no hay una pared con espacio a los dos lados"
izq, der = encontrado
for otro in g.jugadores[1:]:
    poner(otro.personaje, mundo.punto_libre((40, 40)))
poner(jugador.personaje, izq)
poner(alien, der)
for a in g.aliens[1:]:
    poner(a, mundo.punto_libre((mundo.ancho - 60, mundo.alto - 60)))

obs = vision.obstaculos(mundo, g.puertas_dobles, g.compuertas)
campo = vision.campo_de(jugador.hitbox.center, obs)
assert not campo.ve_a(alien.hitbox), "el alien está detrás de la pared"
poner(alien, (izq[0] - 80, izq[1]))
if not mundo.colisiona(alien.hitbox):
    assert campo.ve_a(alien.hitbox), "al lado del jugador sí se ve"
print("Partida: un alien detrás de una pared no se ve; al lado sí")

# Los aliens que no se ven no se dibujan.
dibujados = []
original = type(alien).dibujar
type(alien).dibujar = lambda self, *a, **k: (dibujados.append(self), original(self, *a, **k))
poner(alien, der)
dibujados.clear(); g._dibujar()
assert dibujados.count(alien) == 0, "se dibujó el alien que está tras la pared"
pygame.image.save(g.screen, os.path.join(OUT, "vision_a_pared.png"))
g.oscuridad = False      # Pausa > Opciones > Campo de visión y oscuridad
assert not g._extras_dibujo()["vision"], "la opción apaga el campo de visión (para probar)"
dibujados.clear(); g._dibujar()
assert dibujados.count(alien) >= 1, "sin campo de visión se dibuja en la vista que lo alcance"
g.oscuridad = True
assert g._extras_dibujo()["vision"]
type(alien).dibujar = original
print("Dibujo: el alien tras la pared no se dibuja; con la opción apagada sí")

# Una compuerta bajada también tapa la vista.
probada = False
for comp in g.compuertas:
    r = comp["rect"]
    if r.width >= r.height:
        a, b = (r.centerx, r.top - 60), (r.centerx, r.bottom + 60)
    else:
        a, b = (r.left - 60, r.centery), (r.right + 60, r.centery)
    comp["cerrada"] = False
    if not mundo.linea_libre(a, b):
        continue
    comp["cerrada"] = True
    cerrada = vision.campo_de(a, vision.obstaculos(mundo, g.puertas_dobles, g.compuertas))
    comp["cerrada"] = False
    abierta = vision.campo_de(a, vision.obstaculos(mundo, g.puertas_dobles, g.compuertas))
    assert not cerrada.ve_punto(b) and abierta.ve_punto(b), "la compuerta bajada tapa"
    probada = True
    break
print("Compuerta: bajada tapa la vista" if probada else "Compuerta: (no hay una para probar)")

# En un apagón el campo también recorta la linterna.
g.eventos.lanzar("apagon")
assert g._extras_dibujo()["oscuridad"] and g._extras_dibujo()["vision"]
poner(alien, (izq[0] - 80, izq[1]))
g._dibujar()
pygame.image.save(g.screen, os.path.join(OUT, "vision_b_apagon.png"))
g.eventos.restaurar_luz()

# Costo.
g.screen = pygame.Surface((1920, 1080))
inicio = time.perf_counter()
for _ in range(20):
    g._dibujar()
print(f"dibujar a 1080p con campo de visión: {(time.perf_counter() - inicio) / 20 * 1000:.1f} ms")

print("\nTODO OK")
