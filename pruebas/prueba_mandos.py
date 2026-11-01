"""Prueba de los mandos (jugadores 3 y 4) sin un mando de verdad.

    python pruebas/prueba_mandos.py

Se inyecta un mando falso que dice qué botones están presionados y se
mandan eventos como los que manda pygame. Para probar el control real:
python pruebas/probar_mando.py.
"""

import os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)
import pygame; pygame.init()
OUT = os.path.join(RAIZ, "pruebas", "capturas")

from juego import app as App
from juego import objetos_mapa
from juego import mandos as M
objetos_mapa.mapa_activo = lambda: "Nave"
DT = 1000 // 60
NOMBRES = [r["nombre"] for r in App.ROLES]


class MandoFalso:
    def __init__(self, ident):
        self.ident = ident
        self.botones, self.ejes, self.cruceta = set(), [0.0] * 6, (0, 0)
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
mando = MandoFalso(77)
mando.ejes[M.EJE_LT] = -1.0


def boton(nombre):
    return pygame.event.Event(pygame.JOYBUTTONDOWN, instance_id=77, button=M.BOTONES[nombre], joy=0)


g = App.Game()
g.mandos.por_puesto = {2: mando}

# Menú y cantidad con la cruceta y A.
g.current_screen = "cantidad"
antes = g.cantidad_seleccionada
pygame.event.post(pygame.event.Event(pygame.JOYHATMOTION, instance_id=77, value=(0, -1), hat=0, joy=0))
g._manejar_eventos()
assert g.cantidad_seleccionada != antes, "la cruceta mueve la selección en los menús"
print("menús: la cruceta del mando elige")

# Partida de 3: el jugador 3 tiene mando.
def avanzar():
    for _ in range(80):
        if g.transitions.is_idle(): break
        g.transitions.update(g, 33)


g.cantidad_jugadores = 3
g.abrir_seleccion_roles()
avanzar()
assert g.seleccion_roles[2]["tecla_ok"] == "A" and g.seleccion_roles[2]["tecla_mover"] == "Stick"
for i, e in enumerate(g.seleccion_roles[:2]):
    e["listo"], e["rol"] = True, NOMBRES[i]
g.current_screen = "roles"
g.seleccion_roles[2]["cursor"] = 2
pygame.event.post(boton("A"))
g._manejar_eventos()
assert g.current_screen != "roles" or g.seleccion_roles[2]["listo"], "A confirma el rol"
avanzar()
g.current_screen = "partida"
j3 = g.jugadores[2]
assert j3.con_mando and j3.puede_moverse and j3.nombre_tecla("interactuar") == "A"
assert not g.jugadores[2 - 1].con_mando
g.saltar_tutorial()
g.presentacion = None   # la ventana de alien nuevo pausaría la prueba
for a in g.aliens:
    a.descanso_ms = 10 ** 9
print("selección: el mando escoge rol; el jugador 3 se puede mover")

# Moverse con el stick, y en sigilo con LB.
x0 = j3.hitbox.x
mando.ejes[M.EJE_X] = 1.0
for _ in range(20):
    g._actualizar_partida(DT)
normal = j3.hitbox.x - x0
mando.botones.add(M.BOTONES["LB"])
x0 = j3.hitbox.x
for _ in range(20):
    g._actualizar_partida(DT)
lento = j3.hitbox.x - x0
mando.ejes[M.EJE_X] = 0.0
mando.botones.clear()
assert normal > 0 and 0 < lento < normal, (normal, lento)
print(f"stick: avanza {normal}px; con LB (sigilo) {lento}px")

# Cruceta también mueve.
y0 = j3.hitbox.y
mando.cruceta = (0, 1)
for _ in range(15):
    g._actualizar_partida(DT)
mando.cruceta = (0, 0)
assert j3.hitbox.y < y0
print("cruceta: mueve hacia arriba")

# Y abre el árbol; B lo cierra.
pygame.event.post(boton("Y"))
g._manejar_eventos()
assert j3.panel is not None and j3.panel.get("tipo") == "habilidades"
pygame.event.post(boton("B"))
g._manejar_eventos()
assert j3.panel is None
print("Y abre el árbol de habilidades, B lo cierra")

# Mantener A cuenta como mantener la tecla de interactuar.
mando.botones.add(M.BOTONES["A"])
teclas = g.mandos.envolver(Teclas())
assert any(teclas[k] for k in j3.teclas["interactuar"])
mando.botones.clear()

g._dibujar()
pygame.image.save(g.screen, os.path.join(OUT, "mandos_partida.png"))

# Sin mando, el jugador 4 sigue quieto, y si se desconecta el del 3, también.
g.mandos.por_puesto = {}
g._sincronizar_mandos()
assert not j3.puede_moverse
print("desconectado: el jugador 3 deja de moverse")

# ---------- Cada uno escoge su control (pantalla "controles") ----------
# Dos jugadores, los dos con mando: el jugador 1 toma el Mando 2 y el 2 el Mando 1.
from data.dificultad import DIFICULTADES
uno, dos = MandoFalso(77), MandoFalso(88)
for m in (uno, dos):
    m.ejes[M.EJE_LT] = -1.0
g = App.Game()
g.mandos.por_puesto = {2: uno, 3: dos}


def boton_de(ident, nombre):
    return pygame.event.Event(pygame.JOYBUTTONDOWN, instance_id=ident, button=M.BOTONES[nombre], joy=0)


def pulsar(*eventos):
    for e in eventos:
        pygame.event.post(e)
    g._manejar_eventos()
    avanzar()


g._activar_opcion_menu("jugar"); avanzar()
g.cantidad_seleccionada = 0; pulsar(boton_de(77, "A"))            # 2 jugadores
g.dificultad_seleccionada = [d["clave"] for d in DIFICULTADES].index("normal")
pulsar(boton_de(77, "A"))
assert g.current_screen == "controles" and g.esquemas == [None, None], (g.current_screen, g.esquemas)
pulsar(boton_de(88, "A"))                                        # jugador 1 -> Mando 2
assert g.esquemas == [3, None]
g._dibujar()
pygame.image.save(g.screen, os.path.join(OUT, "controles_eleccion.png"))
pulsar(boton_de(88, "A"))                                        # otra vez: lo suelta
assert g.esquemas == [None, None]
pulsar(boton_de(88, "A"))
pulsar(boton_de(88, "B"))                                        # B también lo suelta
assert g.esquemas == [None, None]
g._manejar_tecla(pygame.K_RETURN); avanzar()                     # jugador 1 -> flechas
assert g.esquemas == [1, None]
g._manejar_tecla(pygame.K_RETURN); avanzar()                     # flechas otra vez: las suelta
assert g.esquemas == [None, None]
pulsar(boton_de(88, "A"))                                        # jugador 1 -> Mando 2
pulsar(boton_de(77, "A"))                                        # jugador 2 -> Mando 1
assert g.esquemas == [3, 2] and g.current_screen == "roles", (g.esquemas, g.current_screen)
assert [e["controles"] for e in g.seleccion_roles] == ["Mando 2", "Mando 1"]
g._manejar_tecla(pygame.K_ESCAPE); avanzar()                     # Esc en roles: a escoger controles otra vez
assert g.current_screen == "controles"
pulsar(boton_de(88, "A")); pulsar(boton_de(77, "A"))
assert g.esquemas == [3, 2] and g.current_screen == "roles"
print("controles: cada uno toma el suyo con su botón; dos no pueden tener el mismo")
# En la selección de rol, E y Enter ya no le escogen a nadie; los mandos sí.
g._manejar_tecla(pygame.K_e); g._manejar_tecla(pygame.K_RETURN)
assert not any(e["listo"] for e in g.seleccion_roles)
g.seleccion_roles[0]["cursor"] = 0; g.seleccion_roles[1]["cursor"] = 1
pulsar(boton_de(88, "A"))
assert g.seleccion_roles[0]["listo"] and not g.seleccion_roles[1]["listo"]
pulsar(boton_de(77, "A"))
avanzar()
assert g.jugadores and [j.esquema for j in g.jugadores] == [3, 2]
j1, j2 = g.jugadores
assert j1.con_mando and j1.puede_moverse and j1.controles_nombre == "Mando 2"
g.current_screen = "partida"
g.saltar_tutorial()
g.presentacion = None   # la ventana de alien nuevo pausaría la prueba
for a in g.aliens:
    a.descanso_ms = 10 ** 9
# El stick del Mando 2 mueve al jugador 1; WASD ya no.
x0 = j1.hitbox.x
dos.ejes[M.EJE_X] = 1.0
for _ in range(15):
    g._actualizar_partida(DT)
dos.ejes[M.EJE_X] = 0.0
assert j1.hitbox.x > x0, "el Mando 2 mueve al jugador 1"
x1, x2 = j1.hitbox.x, j2.hitbox.x
pygame.key.get_pressed = lambda: Teclas({pygame.K_d: True})
for _ in range(15):
    g._actualizar_partida(DT)
pygame.key.get_pressed = lambda: Teclas()
assert j1.hitbox.x == x1 and j2.hitbox.x == x2, "WASD no mueve a nadie"
# B del Mando 1 suelta/cierra cosas del jugador 2 (no del 1).
pygame.event.post(boton_de(77, "Y"))
g._manejar_eventos()
assert j2.panel is not None and j1.panel is None
print("partida: el jugador 1 se mueve con el Mando 2, el 2 con el Mando 1; WASD no hace nada")

# Sin mandos no hay pantalla de controles: cada uno con el de su puesto.
g = App.Game()
g.mandos.por_puesto = {}
g.cantidad_jugadores = 2
g.confirmar_dificultad(); avanzar()
assert g.current_screen == "roles" and g.esquemas == [0, 1]
print("sin mandos: directo a escoger rol (WASD y flechas, como antes)")
print("\nTODO OK")
