"""Prueba de las vidas: 3 corazones por jugador, sin vidas queda eliminado, y la
Biomante devuelve vidas con Regeneración.

    python pruebas/prueba_vidas.py
"""

import os, sys, math
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
from entidades import acciones_rol
from entidades.jugador import VIDAS_INICIALES
objetos_mapa.mapa_activo = lambda: "Nave"
DT = 1000 // 60


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
    g._activar_opcion_menu("jugar"); avanzar(); g.current_screen = "cantidad"
    g._manejar_tecla(pygame.K_RETURN); avanzar(); g.current_screen = "roles"
    nombres = [r["nombre"] for r in App.ROLES]
    g.seleccion_roles[0]["cursor"] = nombres.index(roles[0]); g._manejar_tecla(pygame.K_e)
    g.seleccion_roles[1]["cursor"] = nombres.index(roles[1]); g._manejar_tecla(pygame.K_RETURN)
    avanzar(); g.current_screen = "partida"
    g.saltar_tutorial()
    for a in g.aliens:
        a.descanso_ms = 10 ** 9
    return g


g = nueva_partida(("Biomante", "Forjador"))
bio, forj = g.jugadores
assert bio.vidas == forj.vidas == VIDAS_INICIALES
alien = g.aliens[0]

# Cada captura quita una vida y lo encierra; la tercera lo elimina.
g._atrapar(forj, alien)
assert forj.vidas == 2 and forj.preso is not None
g.mision.liberar(forj.preso, bio)
g._atrapar(forj, alien)
assert forj.vidas == 1
g.mision.liberar(forj.preso, bio)
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "vidas_a_una.png"))
print("dos capturas: al Forjador le queda 1 vida")

# La Biomante le devuelve una vida (Regeneración), y no otra hasta la recarga.
bio.arbol.desbloquear("REGENERACION", 999)
forj.personaje.hitbox.center = bio.hitbox.center; forj.personaje.sync_sprite_from_hitbox()
assert acciones_rol.usar_habilidad(g, bio)
assert forj.vidas == 2 and bio.curacion_ms > 0
bio.recarga_ms = 0
acciones_rol.usar_habilidad(g, bio)
assert forj.vidas == 2, "la curación tiene su propia recarga"
for _ in range(int(acciones_rol.RECARGA_CURACION_MS / DT) + 2):
    acciones_rol.actualizar(g, DT)
bio.recarga_ms = 0
acciones_rol.usar_habilidad(g, bio)
assert forj.vidas == 3
acciones_rol.actualizar(g, acciones_rol.RECARGA_CURACION_MS + 1)
bio.recarga_ms = 0
acciones_rol.usar_habilidad(g, bio)
assert forj.vidas == VIDAS_INICIALES, "no pasa de 3"
print("Regeneración: la Biomante le devuelve vidas (máximo 3, cada 40 s)")

# Tres capturas seguidas: eliminado, ya no lo encierran ni lo cazan.
for _ in range(3):
    if forj.preso is not None:
        g.mision.liberar(forj.preso, bio)
    g._atrapar(forj, alien)
assert forj.eliminado and forj.vidas == 0 and forj.preso is None and not forj.cazable
assert not forj.puede_moverse
g._actualizar_partida(DT)
assert g.mision.resultado is None, "con la Biomante viva la partida sigue"
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "vidas_b_eliminado.png"))
print("tercera captura: el Forjador queda eliminado; la partida sigue")

# Los eliminados no suman para ganar: la Biomante sola puede escapar.
g.mision.empezar_huida()
bio.personaje.hitbox.center = g.mision.capsula.center; bio.personaje.sync_sprite_from_hitbox()
g.mision.actualizar(DT)
assert g.mision.resultado == "victoria"
print("victoria con un eliminado: basta con que lleguen los que quedan")

# Si eliminan a todos, se pierde.
g2 = nueva_partida(("Tecnomante", "Resonante"))
for j in g2.jugadores:
    for _ in range(3):
        if j.preso is not None:
            g2.mision.liberar(j.preso, g2.jugadores[0] if j is not g2.jugadores[0] else g2.jugadores[1])
        g2._atrapar(j, g2.aliens[0])
g2.mision.actualizar(DT)
assert all(j.eliminado for j in g2.jugadores) and g2.mision.resultado == "derrota"
print("todos eliminados -> DERROTA")

g3 = nueva_partida(("Biomante", "Tecnomante"))
bio3, tec3 = g3.jugadores

# El Tecnomante eliminado deja 2 decodificadores; el Forjador, un kit, sus
# piezas, y desde ahí cualquiera recoge piezas.
for _ in range(3):
    if tec3.preso is not None:
        g3.mision.liberar(tec3.preso, bio3)
    tec3.personaje.hitbox.center = (int(0.8 * g3.mundo.ancho), int(0.72 * g3.mundo.alto))
    tec3.personaje.sync_sprite_from_hitbox()
    donde = tec3.hitbox.center
    g3._atrapar(tec3, g3.aliens[0])
assert tec3.eliminado
decos = [c for c in g3.mision.consumibles if c["tipo"] == "decodificador" and not c["tomado"]]
assert len(decos) == 1 and math.dist(decos[0]["rect"].center, donde) < 120
print("Tecnomante eliminado: dejó un decodificador (uno solo) donde lo atraparon")

g4 = nueva_partida(("Forjador", "Resonante"))
forj4, res4 = g4.jugadores
forj4.piezas = 2
forj4.objetos.add("decodificador")
piezas_antes = len(g4.piezas)
for _ in range(3):
    if forj4.preso is not None:
        g4.mision.liberar(forj4.preso, res4)
    g4._atrapar(forj4, g4.aliens[0])
assert forj4.eliminado and g4.mision.piezas_para_todos
tipos = [c["tipo"] for c in g4.mision.consumibles if not c["tomado"]]
assert "kit" in tipos and "decodificador" in tipos and len(g4.piezas) == piezas_antes + 2
# La Resonante recoge el kit y lo ve en su inventario.
kit = next(c for c in g4.mision.consumibles if c["tipo"] == "kit" and not c["tomado"])
res4.personaje.hitbox.center = kit["rect"].center; res4.personaje.sync_sprite_from_hitbox()
assert g4.mision.interactuar(res4) and "kit" in res4.objetos
# Se pueden llevar varios del mismo: recoge también el decodificador del
# Forjador y otro más que se le pone a mano.
deco = next(c for c in g4.mision.consumibles if c["tipo"] == "decodificador" and not c["tomado"])
res4.personaje.hitbox.center = deco["rect"].center; res4.personaje.sync_sprite_from_hitbox()
assert g4.mision.interactuar(res4)
res4.objetos.add("decodificador")
assert res4.objetos["decodificador"] == 2
res4.piezas = 3
g4._dibujar(); pygame.image.save(g4.screen, os.path.join(OUT, "vidas_c_inventario.png"))
print("Forjador eliminado: dejó kit, su decodificador y 2 piezas; cualquiera recoge piezas")
print("\nTODO OK")
