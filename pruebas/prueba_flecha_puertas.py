"""Prueba de la flecha con varias puertas con código (MapaFinal).

    python pruebas/prueba_flecha_puertas.py

El código de una puerta puede estar en una nota que queda detrás de OTRA
puerta cerrada (sortear_candidatas lo permite si esa otra se puede abrir
antes). La flecha (Mision.punto_objetivo) llevaba a la nota sin leer más
cercana de la puerta más cercana sin mirar si había camino: cuando la que
faltaba era esa nota encerrada, apuntaba a un lugar al que no se podía ir y
el equipo se quedaba dando vueltas (lo encontró pruebas/simulador_masivo.py:
bots "trabados" yendo a la misma nota en muchas partidas). Ahora salta a la
siguiente puerta, la que sí se puede abrir.

Se juega "siguiendo la flecha" con varias semillas: cada nota a la que
apunta tiene que tener camino; se lee, y cada puerta a la que apunta se abre.
"""

import os, sys, random, math
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)
import pygame; pygame.init()

from juego import app as App
from juego import objetos_mapa
from misiones.mision import Mision
objetos_mapa.mapa_activo = lambda: "MapaFinal"


class Teclas(dict):
    def __getitem__(self, k):
        return self.get(k, False)


pygame.key.get_pressed = lambda: Teclas()


def nueva_partida(roles):
    g = App.Game()
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


g = nueva_partida(("Tecnomante", "Forjador", "Biomante", "Resonante"))
assert len(g.mision.puertas) >= 2, "MapaFinal debería tener varias puertas con código"
jugador = g.jugadores[0]
revisadas = casos = 0


def ir_a(punto):
    """Camina hasta ahí (la flecha se calcula desde donde está)."""
    w, h = jugador.personaje.hitbox_w, jugador.personaje.hitbox_h
    x, y = g.mundo.punto_libre((punto[0] - w // 2, punto[1] - h // 2), w, h)
    jugador.personaje.hitbox.topleft = (int(x), int(y))


for semilla in range(40):
    g.mundo.reiniciar_paredes()
    jugador.personaje.hitbox.topleft = jugador.spawn
    g.mision = m = Mision(g, g.objetos, aleatorio=random.Random(semilla))
    m.abrir_puerta(jugador, 0)                      # salieron de la prisión
    # El caso que fallaba, armado a mano: de una puerta cerrada ya leyó todas
    # las notas a las que llega, la que falta (la del código) está detrás de
    # otra puerta cerrada, y está parado junto a una de las que leyó.
    for puerta in m.puertas_cerradas():
        llega = [n for n in puerta["candidatas"] if m._llega(jugador, n["rect"].center)]
        encerradas = [n for n in puerta["candidatas"] if n not in llega]
        if not llega or not encerradas:
            continue
        casos += 1
        for n in llega:
            n["leida_por"].add(jugador)
        # Junto a la puerta (del lado por donde se llega a ella).
        for dx in (-90, 90):
            ir_a((puerta["rect"].centerx + dx, puerta["rect"].centery))
            if m._llega(jugador, llega[0]["rect"].center):
                break
        objetivo = m.punto_objetivo(jugador)
        assert objetivo is not None
        punto, texto = objetivo
        assert not texto.startswith("Lee las notas") or m._llega(jugador, punto), (
            f"semilla {semilla}: la flecha lleva a la nota encerrada en {punto} ({texto})")
    for n in m.notas:
        n["leida_por"].clear()
    jugador.personaje.hitbox.topleft = jugador.spawn
    for paso in range(40):
        objetivo = m.punto_objetivo(jugador)
        if objetivo is None:
            break
        punto, texto = objetivo
        if texto.startswith("Lee las notas"):
            nota = next(n for n in m.notas if n["rect"].center == punto)
            revisadas += 1
            assert m._llega(jugador, punto), (
                f"semilla {semilla}: la flecha lleva a una nota sin camino en {punto} ({texto})")
            nota["leida_por"].add(jugador)
            ir_a(punto)
        elif texto.startswith("Abre la puerta"):
            i = next(i for i, p in enumerate(m.puertas) if p["rect"].center == punto)
            m.abrir_puerta(jugador, i)
            ir_a(punto)
        else:
            break
assert casos > 0, "ninguna semilla armó el caso de la nota detrás de otra puerta"
print(f"Casos de nota detrás de otra puerta: {casos}")
print(f"OK: {revisadas} notas a las que apuntó la flecha, todas con camino (40 semillas)")
