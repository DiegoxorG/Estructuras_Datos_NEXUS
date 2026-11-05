"""Prueba de desconectar y volver a conectar un mando con el juego abierto.

    python pruebas/prueba_mando_desconectado.py

Se usan mandos falsos (como en prueba_mandos.py) y los eventos que manda
pygame al conectar (JOYDEVICEADDED, con `device_index`) y desconectar
(JOYDEVICEREMOVED, con `instance_id`):

- mientras carga la partida (la pantalla de carga no deja tocar nada, pero
  los mandos sí se tienen que anotar);
- en la pantalla "¿Con qué juega cada uno?", si se desconecta el mando que
  alguien ya había tomado;
- en plena partida, cuando el único que queda en pie juega con mando: que se
  le suelte el cable no es perder la partida.
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
from juego import mandos as M
objetos_mapa.mapa_activo = lambda: "Nave"
DT = 1000 // 60


class MandoFalso:
    def __init__(self, ident):
        self.ident = ident
        self.botones, self.ejes, self.cruceta = set(), [0.0] * 6, (0, 0)
        self.ejes[M.EJE_LT] = -1.0
    def init(self): pass
    def get_instance_id(self): return self.ident
    def get_name(self): return "Mando falso"
    def get_button(self, b): return b in self.botones
    def get_axis(self, a): return self.ejes[a]
    def get_numaxes(self): return 6
    def get_numhats(self): return 1
    def get_hat(self, i): return self.cruceta


class Teclas(dict):
    def __getitem__(self, k):
        return self.get(k, False)


pygame.key.get_pressed = lambda: Teclas()

# pygame.joystick.Joystick(device_index) devuelve el mando falso de ese índice.
conectados = {}
pygame.joystick.Joystick = lambda indice: conectados[indice]


def conectar(indice, mando):
    conectados[indice] = mando
    pygame.event.post(pygame.event.Event(pygame.JOYDEVICEADDED, device_index=indice))


def desconectar(mando):
    pygame.event.post(pygame.event.Event(pygame.JOYDEVICEREMOVED, instance_id=mando.ident))


def avanzar(g):
    for _ in range(80):
        if g.transitions.is_idle():
            break
        g.transitions.update(g, 33)


def partida(g, cantidad):
    g.cantidad_jugadores = cantidad
    g.abrir_seleccion_roles(ir=False)
    for i, estado in enumerate(g.seleccion_roles):
        estado["listo"], estado["rol"] = True, App.ROLES[i]["nombre"]
    g.iniciar_partida()
    avanzar(g)
    assert g.current_screen == "partida"
    g.saltar_tutorial()
    g.presentacion = None
    for a in g.aliens:
        a.descanso_ms = 10 ** 9


# ---------- Mientras carga la partida ----------
g = App.Game()
uno, dos = MandoFalso(77), MandoFalso(88)
g.mandos.por_puesto = {2: uno, 3: dos}
g.current_screen = "cargando"
g.carga = {"ms": 0, "listo": False, "error": None, "consejo": "", "roles": []}
desconectar(uno)
g._manejar_eventos()
assert sorted(g.mandos.por_puesto) == [3], \
    "el mando que se desconectó durante la carga sigue anotado"
tres = MandoFalso(99)
conectar(0, tres)
g._manejar_eventos()
assert g.mandos.por_puesto.get(2) is tres, "el mando que se conectó durante la carga no se anotó"
pygame.key.get_pressed = lambda: Teclas({pygame.K_RETURN: True})
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
g._manejar_eventos()
assert g.current_screen == "cargando" and g.pausa is None, "las teclas siguen sin hacer nada al cargar"
pygame.key.get_pressed = lambda: Teclas()
print("cargando: los mandos que se conectan o desconectan quedan anotados")

# Si un mando cambia mientras el otro hilo arma a los jugadores, al terminar
# de cargar se revisa otra vez quién tiene mando.
g = App.Game()
g.mandos.por_puesto = {2: uno}
partida(g, 3)
j3 = g.jugadores[2]
assert j3.con_mando
g.mandos.por_puesto = {}                     # (se fue justo mientras cargaba)
g.current_screen = "cargando"
g.carga = {"ms": g.MIN_CARGA_MS, "listo": True, "error": None, "consejo": "", "roles": []}
g._actualizar_carga(DT)
assert not j3.con_mando and not j3.puede_moverse, "al terminar de cargar no se revisan los mandos"
print("al terminar de cargar se revisa quién tiene mando")

# ---------- ¿Con qué juega cada uno? ----------
g = App.Game()
conectados.clear()
g.mandos.por_puesto = {2: uno, 3: dos}
g.cantidad_jugadores = 2
g.abrir_controles(); avanzar(g)
assert g.current_screen == "controles" and g.esquemas == [None, None]
pygame.event.post(pygame.event.Event(pygame.JOYBUTTONDOWN, instance_id=77, button=M.BOTONES["A"], joy=0))
g._manejar_eventos(); avanzar(g)
assert g.esquemas == [2, None]
desconectar(uno)
g._manejar_eventos()
assert g.esquemas == [None, None], \
    f"el jugador 1 se queda con un mando que ya no está: {g.esquemas}"
g._dibujar()
print("controles: si se desconecta un mando ya tomado, queda libre otra vez")

# ---------- En partida: el único en pie juega con mando ----------
g = App.Game()
conectados.clear()
g.mandos.por_puesto = {2: uno}
partida(g, 3)
j1, j2, j3 = g.jugadores
assert j3.con_mando and j3.puede_moverse
j1.eliminar(); j2.eliminar()
g._actualizar_partida(DT)
assert g.mision.resultado is None
desconectar(uno)
g._manejar_eventos()
assert not j3.puede_moverse
for _ in range(30):
    g._actualizar_partida(DT)
assert g.mision.resultado is None and g.transitions.is_idle(), \
    "se soltó el cable del mando y la partida se dio por perdida"
g._dibujar()
# Lo vuelve a conectar (otro instance_id, como hace SDL) y sigue jugando.
otra_vez = MandoFalso(78)
conectar(0, otra_vez)
g._manejar_eventos()
assert g.mandos.por_puesto.get(2) is otra_vez and j3.con_mando and j3.puede_moverse
x0 = j3.hitbox.x
otra_vez.ejes[M.EJE_X] = 1.0
for _ in range(15):
    g._actualizar_partida(DT)
otra_vez.ejes[M.EJE_X] = 0.0
assert j3.hitbox.x > x0, "con el mando otra vez conectado se mueve"
print("partida: desconectar el mando del último en pie no es perder; al reconectarlo sigue")

# Y si nunca tuvo mando (3 jugadores sin mandos) y eliminan a los otros dos,
# sí se pierde, como antes: el 3 no puede jugar.
g = App.Game()
g.mandos.por_puesto = {}
partida(g, 3)
j1, j2, j3 = g.jugadores
assert not j3.puede_moverse
j1.eliminar(); j2.eliminar()
g._actualizar_partida(DT)
assert g.mision.resultado == "derrota"
print("sin mando desde el principio: eliminar a los otros dos sigue siendo perder")
print("OK")
