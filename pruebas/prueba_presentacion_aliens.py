"""Prueba de la ventana que presenta a cada tipo de alien (en todas las dificultades).

    python pruebas/prueba_presentacion_aliens.py

1. En todas las dificultades (sin dificultad, en las pruebas, no).
2. Un alien que entra en la pantalla (y en el campo de visión) de alguien abre
   la ventana: el juego queda en pausa hasta que se cierra (no antes de
   MIN_ABIERTA_MS, por si alguien venía apretando una tecla).
3. Cada tipo una sola vez.
4. El Cambiaformas: disfrazado no; revelado, solo cuando termina su susto.
5. Se cierra con interactuar, Enter o el mando. Guarda capturas.
"""

import math, os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)
import pygame; pygame.init()
OUT = os.path.join(RAIZ, "pruebas", "capturas")
os.makedirs(OUT, exist_ok=True)

from juego import app as App
from juego import objetos_mapa, presentacion_aliens
from data.dificultad import DIFICULTADES
objetos_mapa.mapa_activo = lambda: "Nave"
DT = 1000 // 60


class Teclas(dict):
    def __getitem__(self, k):
        return self.get(k, False)


pygame.key.get_pressed = lambda: Teclas()


def nueva_partida(dificultad):
    g = App.Game()
    def avanzar():
        for _ in range(80):
            if g.transitions.is_idle(): break
            g.transitions.update(g, 33)
    g._activar_opcion_menu("jugar"); avanzar(); g._manejar_tecla(pygame.K_RETURN); avanzar()
    g.dificultad_seleccionada = [d["clave"] for d in DIFICULTADES].index(dificultad)
    g._manejar_tecla(pygame.K_RETURN); avanzar()
    g.seleccion_roles[0]["cursor"] = 0; g._manejar_tecla(pygame.K_e)
    g.seleccion_roles[1]["cursor"] = 1; g._manejar_tecla(pygame.K_RETURN); avanzar()
    g.saltar_tutorial()
    return g


def frente_a(g, jugador, alien, cerca=200, lejos=330):
    """Pone al jugador a la vista de `alien` (sin paredes en medio)."""
    for dx in range(-400, 401, 20):
        for dy in range(-300, 301, 20):
            r = jugador.hitbox.copy()
            r.center = (alien.hitbox.centerx + dx, alien.hitbox.centery + dy)
            if (cerca < math.hypot(dx, dy) < lejos and not g.mundo.colisiona(r)
                    and g.mundo.linea_libre(r.center, alien.hitbox.center)):
                jugador.personaje.hitbox.center = r.center
                jugador.personaje.sync_sprite_from_hitbox()
                return
    raise AssertionError("no encontré dónde poner al jugador")


def lejos_de_todos(g, menos=()):
    for a in g.aliens:
        if a not in menos:
            a.hitbox.topleft = (5, 5)
            a.descanso_ms = 10 ** 9


# ---------- 1: en todas las dificultades ----------
from juego.dificultad import Dificultad
assert all(presentacion_aliens.activa_en(Dificultad(d["clave"])) for d in DIFICULTADES)
assert not presentacion_aliens.activa_en(None)
g = nueva_partida("dificil")
assert g.presentacion is not None
print("la ventana de alien nuevo sale en Fácil, Normal, Difícil e Inteligente")

g = nueva_partida("facil")
P = g.presentacion
assert P is not None and not P.abierta
j1, j2 = g.jugadores

# ---------- 2: un tipo nuevo a la vista abre la ventana y pausa ----------
vigia = next(a for a in g.aliens if a.tipo == "vigia")
lejos_de_todos(g, menos=(vigia,))
frente_a(g, j1, vigia)
for _ in range(3):
    g._actualizar_partida(DT)
assert P.abierta and P.actual["tipo"] == "vigia" and P.actual["jugador"] is j1
antes = (vigia.hitbox.center, j1.hitbox.center, g.tiempo_jugado_ms)
for _ in range(10):
    g._actualizar_partida(DT)
assert (vigia.hitbox.center, j1.hitbox.center, g.tiempo_jugado_ms) == antes, "en pausa no se mueve nada"
g._manejar_tecla(pygame.K_RETURN)
assert P.abierta, "no se cierra antes de MIN_ABIERTA_MS"
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "presentacion_a_vigia.png"))
for _ in range(presentacion_aliens.MIN_ABIERTA_MS // DT + 1):
    g._actualizar_partida(DT)
g._manejar_tecla(j1.teclas["interactuar"][0])
assert not P.abierta
print("el Vigía a la vista: ventana, juego en pausa, se cierra con interactuar")

# ---------- 3: cada tipo una vez ----------
for _ in range(30):
    g._actualizar_partida(DT)
assert not P.abierta and "vigia" in P.presentados
print("el mismo tipo no se vuelve a presentar")

# Detrás de una pared, no.
ciego = next(a for a in g.aliens if a.tipo == "ciego")
lejos_de_todos(g, menos=(ciego,))
ciego.hitbox.center = (j1.hitbox.centerx + 200, j1.hitbox.centery)
from juego import vision
campo = vision.campo_de(j1.hitbox.center, vision.obstaculos(g.mundo, g.puertas_dobles, g.compuertas))
if not campo.ve_a(ciego.hitbox):
    g._actualizar_partida(DT)
    assert not P.abierta, "si no lo ve, no se presenta"
    print("un alien detrás de una pared no abre la ventana")

# ---------- 4: el Cambiaformas ----------
cf = g.cambiaformas
assert cf is not None and cf.disfrazado
lejos_de_todos(g, menos=(cf,))
cf.hitbox.center = j2.hitbox.center
frente_a(g, j2, cf, 60, 160)
for _ in range(5):
    g._actualizar_partida(DT)
assert not P.abierta, "disfrazado no se presenta"
cf.descanso_ms = 0
cf.presa = j2
cf._revelarse()
assert not cf.disfrazado and j2.susto_ms > 0
g._atrapar = lambda *a: None       # (que no lo atrape mientras tanto)
for _ in range(200):
    g._actualizar_partida(DT)
    if P.abierta:
        break
assert P.abierta and P.actual["tipo"] == "cambiaformas"
assert j2.susto_ms == 0 and cf.transformando_ms <= 0, "primero termina el susto de la transformación"
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "presentacion_b_cambiaformas.png"))
print("Cambiaformas: se presenta revelado y después de su susto")

# ---------- 5: con el mando ----------
for _ in range(presentacion_aliens.MIN_ABIERTA_MS // DT + 1):
    g._actualizar_partida(DT)
g._tecla_mando(2, "interactuar")
assert not P.abierta
print("se cierra con el mando")

# ---------- 6: escondido también se presenta (pero no en pleno minijuego) ----------
g = nueva_partida("facil")
P = g.presentacion
j1, j2 = g.jugadores
vigia = next(a for a in g.aliens if a.tipo == "vigia")
lejos_de_todos(g, menos=(vigia,))
vigia.descanso_ms = 10 ** 9          # que no lo oiga ni se mueva
for a in g.aliens:
    a.descanso_ms = 10 ** 9


def a_la_vista_de_un_escondite():
    for e in g.escondites:
        j1.esconderse(e)
        for dx in range(-300, 301, 30):
            for dy in range(-220, 221, 30):
                vigia.hitbox.center = (e["rect"].centerx + dx, e["rect"].centery + dy)
                if (math.hypot(dx, dy) > 150 and not g.mundo.colisiona(vigia.hitbox)
                        and P.ve_en_pantalla(j1, vigia)):
                    return e
        j1.salir_del_escondite()
    raise AssertionError("no encontré un escondite con el Vigía a la vista")


e = a_la_vista_de_un_escondite()
j1.minijuego = object()               # en pleno minijuego: no
for _ in range(3):
    P.revisar()
assert not P.abierta
j1.minijuego = None
P.revisar()
assert P.abierta and P.actual["jugador"] is j1 and P.actual["tipo"] == "vigia"
print("escondido, el alien nuevo también se presenta (salvo en pleno minijuego)")
print("\nTODO OK")
