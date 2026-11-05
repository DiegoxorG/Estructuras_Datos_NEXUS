"""Mandos de Xbox y de PlayStation a la vez, sin mandos de verdad.

    python pruebas/prueba_mandos_xbox_ps.py

Se reemplazan `pygame.joystick.Joystick` y el módulo `pygame._sdl2.controller`
por unos falsos y se fabrican los eventos que mandaría SDL (JOY* y
CONTROLLER* a la vez, como hace con un mando reconocido). Revisa:

- los botones van por posición: abajo interactúa en Xbox (A) y en PS (Cruz);
- una pulsación cuenta una vez aunque lleguen JOYBUTTONDOWN y CONTROLLERBUTTONDOWN;
- un mando que SDL no reconoce sigue con los números de Xbox (respaldo), y
  sin pygame._sdl2.controller todo va por joystick, como antes;
- el tipo de mando sale del nombre (o del GUID);
- cada jugador ve los botones de SU mando (A / Cruz...), y la pantalla de
  controles dice "Mando 1 (Xbox)", "Mando 2 (PlayStation)";
- conectar y desconectar con el juego abierto.

Corre igual con pygame y con pygame-ce.
"""

import os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)
import pygame; pygame.init()
os.makedirs(os.path.join(RAIZ, "pruebas", "capturas"), exist_ok=True)

from juego import app as App
from juego import objetos_mapa
from juego import mandos as M
from juego import tutorial
from screens import seleccion
objetos_mapa.mapa_activo = lambda: "Nave"
NOMBRES = [r["nombre"] for r in App.ROLES]
DT = 1000 // 60

# Los números que manda SDL por joystick (lo que había que evitar).
PS_JOY = {"Cruz": 0, "Circulo": 1, "Cuadrado": 2, "Triangulo": 3, "Share": 4, "PS": 5,
          "Options": 6, "L3": 7, "R3": 8, "L1": 9, "R1": 10}
C = {n: getattr(pygame, "CONTROLLER_BUTTON_" + n) for n in
     ("A", "B", "X", "Y", "BACK", "START", "LEFTSHOULDER", "RIGHTSHOULDER",
      "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT")}


class JoystickFalso:
    def __init__(self, ident, nombre, guid=""):
        self.ident, self.nombre, self.guid = ident, nombre, guid
        self.botones, self.ejes, self.cruceta = set(), [0.0] * 6, (0, 0)
        self.ejes[M.EJE_LT] = -1.0
    def init(self): pass
    def get_instance_id(self): return self.ident
    def get_name(self): return self.nombre
    def get_guid(self): return self.guid
    def get_button(self, b): return b in self.botones
    def get_axis(self, a): return self.ejes[a]
    def get_numaxes(self): return 6
    def get_numhats(self): return 1
    def get_hat(self, i): return self.cruceta


class ControllerFalso:
    """Como pygame._sdl2.controller.Controller: ejes en enteros de SDL."""
    def __init__(self, nombre):
        self.name = nombre
        self.botones, self.ejes = set(), [0] * 6
    def get_button(self, b): return b in self.botones
    def get_axis(self, a): return self.ejes[a]


class SDLFalso:
    """Lo que hay conectado: índice -> (joystick, controller o None)."""
    def __init__(self):
        self.dispositivos = {}
    def init(self): pass
    def is_controller(self, i): return self.dispositivos[i][1] is not None
    def Controller(self, i): return self.dispositivos[i][1]
    def joystick(self, i): return self.dispositivos[i][0]


sdl = SDLFalso()
M._sdl_controller = sdl
pygame.joystick.Joystick = sdl.joystick
pygame.joystick.get_count = lambda: 0      # al abrir no hay nada: llegan por eventos


class Teclas(dict):
    def __getitem__(self, k):
        return self.get(k, False)


pygame.key.get_pressed = lambda: Teclas()


def conectar(indice, ident, nombre, reconocido=True, guid=""):
    joy = JoystickFalso(ident, nombre, guid)
    ctl = ControllerFalso(nombre) if reconocido else None
    sdl.dispositivos[indice] = (joy, ctl)
    eventos = [pygame.event.Event(pygame.JOYDEVICEADDED, device_index=indice)]
    if reconocido:
        eventos.append(pygame.event.Event(pygame.CONTROLLERDEVICEADDED, device_index=indice))
    return joy, ctl, eventos


def quitar(ident):
    return [pygame.event.Event(pygame.JOYDEVICEREMOVED, instance_id=ident),
            pygame.event.Event(pygame.CONTROLLERDEVICEREMOVED, instance_id=ident)]


def boton_c(ident, nombre):
    return pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, instance_id=ident, button=C[nombre])


def boton_j(ident, numero):
    return pygame.event.Event(pygame.JOYBUTTONDOWN, instance_id=ident, button=numero, joy=0)


def acciones(m, *eventos):
    salida = []
    for e in eventos:
        salida += m.evento(e)
    return salida


# ---------- Tipo de mando por el nombre ----------
for nombre, tipo in [("Xbox Series X Controller", "xbox"), ("Xbox One Controller", "xbox"),
                     ("XInput Controller #1", "xbox"), ("Xbox Wireless Controller", "xbox"),
                     ("X-Box 360 Pad", "xbox"), ("PS4 Controller", "playstation"),
                     ("PS5 Controller", "playstation"), ("DualSense Wireless Controller", "playstation"),
                     ("Sony Interactive Entertainment Wireless Controller", "playstation"),
                     ("Wireless Controller", "playstation"), ("DUALSHOCK 4", "playstation"),
                     ("Nintendo Switch Pro Controller", "otro"), ("USB Gamepad", "otro"), (None, "otro")]:
    assert M.tipo_por_nombre(nombre) == tipo, (nombre, M.tipo_por_nombre(nombre))
assert M.tipo_por_nombre("USB Gamepad", "030000004c050000e60c000000016800") == "playstation"
assert M.tipo_por_nombre("USB Gamepad", "030000005e040000120b000000016800") == "xbox"
assert M.tipo_por_nombre("Gamepad", "78696e707574010000000000000000000") == "xbox"
print("tipo: Xbox / PlayStation / otro según el nombre (o el GUID)")

# Nombres en pantalla.
assert [M.nombre_boton(a, "xbox") for a in ("interactuar", "habilidad", "habilidades", "volver",
                                            "celular", "sigilo", "pausa")] == \
    ["A", "X", "Y", "B", "RB", "LB", "Start"]
assert [M.nombre_boton(a, "playstation") for a in ("interactuar", "habilidad", "habilidades", "volver",
                                                   "celular", "sigilo", "pausa")] == \
    ["Cruz", "Cuadrado", "Triángulo", "Círculo", "R1", "L1", "Options"]
assert M.nombre_boton("interactuar", "otro") == "A" and M.nombre_boton("arriba", "playstation") == "Stick"
assert M.NOMBRE_BOTON["interactuar"] == "A" and M.NOMBRE_BOTON["celular"] == "RB"
print("nombres: A/X/Y/B/RB/LB/Start en Xbox, Cruz/Cuadrado/Triángulo/Círculo/R1/L1/Options en PS")

# ---------- Mapeo por posición (los dos tipos) y sin doble pulsación ----------
m = M.Mandos()
xbox, ctl_x, ev_x = conectar(0, 11, "Xbox Series X Controller")
ps, ctl_p, ev_p = conectar(1, 22, "DualSense Wireless Controller")
assert acciones(m, *ev_x, *ev_p) == []
assert sorted(m.por_puesto) == [2, 3] and len(m.por_puesto) == 2, "cada mando una vez (dos avisos)"
assert m.tipo(2) == "xbox" and m.tipo(3) == "playstation"
assert all(M.es_controller(x) for x in m.por_puesto.values())
assert m.nombre_esquema(2, "Mando 1") == "Mando 1 (Xbox)"
assert m.nombre_esquema(3, "Mando 2") == "Mando 2 (PlayStation)"

ESPERADO = {"A": "interactuar", "X": "habilidad", "Y": "habilidades", "B": "volver",
            "START": "pausa", "RIGHTSHOULDER": "celular", "DPAD_UP": "arriba",
            "DPAD_DOWN": "abajo", "DPAD_LEFT": "izquierda", "DPAD_RIGHT": "derecha"}
for ident, puesto in ((11, 2), (22, 3)):
    for boton, accion in ESPERADO.items():
        assert acciones(m, boton_c(ident, boton)) == [(puesto, accion)], (ident, boton)
    assert acciones(m, boton_c(ident, "LEFTSHOULDER"), boton_c(ident, "BACK")) == []
# Los JOY* del mismo mando no cuentan: con los números de PS, L1 (9) no es
# nada y Share (4) caía en LB; Options (6) caía en BACK y L3 (7) en START.
for numero in range(15):
    assert acciones(m, boton_j(22, numero), boton_j(11, numero)) == []
assert acciones(m, pygame.event.Event(pygame.JOYHATMOTION, instance_id=22, value=(0, 1), hat=0, joy=0),
                pygame.event.Event(pygame.JOYAXISMOTION, instance_id=22, axis=1, value=-1.0, joy=0)) == []
# El stick del controller en los menús: una vez por empujón (enteros de SDL).
eje = lambda ident, a, v: pygame.event.Event(pygame.CONTROLLERAXISMOTION, instance_id=ident, axis=a, value=v)
assert acciones(m, eje(22, M.EJE_C_Y, 32767), eje(22, M.EJE_C_Y, 30000)) == [(3, "abajo")]
assert acciones(m, eje(22, M.EJE_C_Y, 0), eje(22, M.EJE_C_Y, -32768)) == [(3, "arriba")]
assert acciones(m, eje(11, M.EJE_C_X, 32767)) == [(2, "derecha")]
print("posición: abajo interactúa, izquierda habilidad, arriba árbol, derecha volver, R1/RB celular (en los dos)")
print("sin doble pulsación: los JOY* de un mando abierto como controller se ignoran")

# Lo que se mantiene (moverse, sigilo, mantener A/Cruz).
v = lambda puesto, accion: m.presionada(M.tecla_virtual(puesto, accion))
for ctl, puesto in ((ctl_x, 2), (ctl_p, 3)):
    assert not any(v(puesto, a) for a in M.ACCIONES)
    ctl.botones.add(C["A"]); assert v(puesto, "interactuar") and not v(puesto, "habilidad")
    ctl.botones = {C["X"]}; assert v(puesto, "habilidad")
    ctl.botones = {C["B"]}; assert v(puesto, "soltar") and v(puesto, "volver")
    ctl.botones = {C["RIGHTSHOULDER"]}; assert v(puesto, "celular") and not v(puesto, "sigilo")
    ctl.botones = {C["LEFTSHOULDER"]}; assert v(puesto, "sigilo")
    ctl.botones = set(); ctl.ejes[M.EJE_C_LT] = 20000; assert v(puesto, "sigilo"), "LT / L2 a fondo"
    ctl.ejes[M.EJE_C_LT] = 0; assert not v(puesto, "sigilo")
    ctl.botones = {C["DPAD_UP"]}; assert v(puesto, "arriba") and not v(puesto, "abajo")
    ctl.botones = {C["DPAD_LEFT"]}; assert v(puesto, "izquierda")
    ctl.botones = set(); ctl.ejes[M.EJE_C_X] = 32000; assert v(puesto, "derecha")
    ctl.ejes[M.EJE_C_X] = 0; ctl.ejes[M.EJE_C_Y] = -32000; assert v(puesto, "arriba")
    ctl.ejes[M.EJE_C_Y] = 5000; assert not v(puesto, "abajo"), "zona muerta"
    ctl.ejes = [0] * 6
# Que el joystick de un controller tenga botones apretados no cuenta (son otros números).
ps.botones = {4, 5, 7}
assert not any(v(3, a) for a in M.ACCIONES)
ps.botones = set()
print("mantener: cruceta y stick mueven, L1/LB o L2/LT sigilo, en los dos tipos")

# ---------- Respaldo por joystick ----------
generico, _, ev_g = conectar(2, 33, "USB Gamepad", reconocido=False)
m2 = M.Mandos()
acciones(m2, *ev_g)
assert m2.por_puesto[2] is generico and not M.es_controller(generico) and m2.tipo(2) == "otro"
assert acciones(m2, boton_j(33, M.BOTONES["A"])) == [(2, "interactuar")]
assert acciones(m2, boton_j(33, M.BOTONES["RB"])) == [(2, "celular")]
assert acciones(m2, boton_j(33, M.BOTONES["START"])) == [(2, "pausa")]
generico.botones = {M.BOTONES["LB"]}
assert m2.presionada(M.tecla_virtual(2, "sigilo"))
generico.botones = set(); generico.cruceta = (0, 1)
assert m2.presionada(M.tecla_virtual(2, "arriba"))
generico.cruceta = (0, 0)
# Sin pygame._sdl2.controller: el Xbox también va por joystick, como antes.
M._sdl_controller = None
m3 = M.Mandos()
acciones(m3, *ev_x)
assert m3.por_puesto[2] is xbox and m3.tipo(2) == "xbox"
assert acciones(m3, boton_j(11, 0), boton_c(11, "A")) == [(2, "interactuar")]
M._sdl_controller = sdl
print("respaldo: un mando no reconocido (o sin _sdl2.controller) usa los números de Xbox")

# ---------- En el juego: un mando de cada tipo ----------
def avanzar(g):
    for _ in range(80):
        if g.transitions.is_idle():
            break
        g.transitions.update(g, 33)


def pulsar(g, *eventos):
    for e in eventos:
        pygame.event.post(e)
    g._manejar_eventos()
    avanzar(g)


g = App.Game()
pulsar(g, *ev_x, *ev_p)
assert sorted(g.mandos.por_puesto) == [2, 3]

# Cada pulsación llega una vez a _tecla_mando aunque SDL mande los dos eventos.
llamadas = []
original = g._tecla_mando
g._tecla_mando = lambda puesto, accion: llamadas.append((puesto, accion))
pulsar(g, boton_c(22, "A"), boton_j(22, PS_JOY["Cruz"]), boton_c(11, "RIGHTSHOULDER"), boton_j(11, 5))
assert llamadas == [(3, "interactuar"), (2, "celular")], llamadas
del g._tecla_mando
print("juego: una pulsación = una acción, con JOY* y CONTROLLER* en la cola")

# Pantalla "¿Con qué juega cada uno?": qué mando es cada uno.
from data.dificultad import DIFICULTADES
textos = []
fuente_real = seleccion.fuente_de_tamano


class FuenteEspia:
    def __init__(self, f): self.f = f
    def render(self, texto, *a):
        textos.append(texto)
        return self.f.render(texto, *a)
    def __getattr__(self, n): return getattr(self.f, n)


seleccion.fuente_de_tamano = lambda tam: FuenteEspia(fuente_real(tam))
g._activar_opcion_menu("jugar"); avanzar(g)
g.cantidad_seleccionada = 0; pulsar(g, boton_c(11, "A"))          # 2 jugadores
g.dificultad_seleccionada = [d["clave"] for d in DIFICULTADES].index("normal")
pulsar(g, boton_c(22, "A"))                                        # Cruz también acepta
assert g.current_screen == "controles", g.current_screen
g._dibujar()
assert "Mando 1 (Xbox)" in textos and "Mando 2 (PlayStation)" in textos, textos
assert "[A] tomar" in textos and "[Cruz] tomar" in textos, textos
assert "[ESC] o B/Círculo: volver a la dificultad" in textos, textos
pulsar(g, boton_c(22, "A"))                                        # jugador 1 -> PS
textos.clear(); g._dibujar()
assert "Mando 2 (PlayStation)" in textos and "Jugador 1" in textos
pygame.image.save(g.screen, os.path.join(RAIZ, "pruebas", "capturas", "controles_xbox_ps.png"))
seleccion.fuente_de_tamano = fuente_real
pulsar(g, boton_c(11, "A"))                                        # jugador 2 -> Xbox
assert g.esquemas == [3, 2] and g.current_screen == "roles", (g.esquemas, g.current_screen)
assert [e["tecla_ok"] for e in g.seleccion_roles] == ["Cruz", "A"]
print("controles: 'Mando 1 (Xbox)', 'Mando 2 (PlayStation)', [A] / [Cruz] tomar")

# Roles con la cruceta (botón de controller) y Cruz / A.
c0 = g.seleccion_roles[0]["cursor"]
pulsar(g, boton_c(22, "DPAD_DOWN"))
assert g.seleccion_roles[0]["cursor"] != c0, "la cruceta del PS mueve el cursor"
g.seleccion_roles[0]["cursor"] = 0; g.seleccion_roles[1]["cursor"] = 1
pulsar(g, boton_c(22, "A")); pulsar(g, boton_c(11, "A"))
avanzar(g)
assert [j.esquema for j in g.jugadores] == [3, 2]
j_ps, j_x = g.jugadores
assert j_ps.tipo_mando == "playstation" and j_x.tipo_mando == "xbox"
for accion, en_ps, en_x in [("interactuar", "Cruz", "A"), ("habilidad", "Cuadrado", "X"),
                            ("habilidades", "Triángulo", "Y"), ("celular", "R1", "RB"),
                            ("sigilo", "L1", "LB"), ("soltar", "Círculo", "B")]:
    assert j_ps.nombre_tecla(accion) == en_ps and j_x.nombre_tecla(accion) == en_x, accion
t = "{interactuar}: usar.  {habilidad}: habilidad.  {celular}: celular. {sigilo}: sigilo"
assert tutorial.con_teclas(t, j_ps) == "Cruz: usar.  Cuadrado: habilidad.  R1: celular. L1: sigilo"
assert tutorial.con_teclas(t, j_x) == "A: usar.  X: habilidad.  RB: celular. LB: sigilo"
print("pistas: el jugador del PS ve Cruz/Cuadrado/R1/L1; el del Xbox, A/X/RB/LB")

# En partida: el stick del PS mueve a su jugador; Triángulo abre el árbol, Círculo lo cierra.
g.current_screen = "partida"
g.saltar_tutorial()
g.presentacion = None
for a in g.aliens:
    a.descanso_ms = 10 ** 9
x0 = j_ps.hitbox.x
ctl_p.ejes[M.EJE_C_X] = 32767
for _ in range(15):
    g._actualizar_partida(DT)
ctl_p.ejes[M.EJE_C_X] = 0
assert j_ps.hitbox.x > x0
pulsar(g, boton_c(22, "Y"), boton_j(22, PS_JOY["Triangulo"]))
assert j_ps.panel is not None and j_ps.panel.get("tipo") == "habilidades" and j_x.panel is None
pulsar(g, boton_c(22, "B"), boton_j(22, PS_JOY["Circulo"]))
assert j_ps.panel is None
g._dibujar()
pygame.image.save(g.screen, os.path.join(RAIZ, "pruebas", "capturas", "partida_xbox_ps.png"))
print("partida: stick del PS mueve, Triángulo abre el árbol y Círculo lo cierra")

# ---------- Desconectar y volver a conectar con la partida andando ----------
pulsar(g, *quitar(22))
assert sorted(g.mandos.por_puesto) == [2] and not j_ps.con_mando and not j_ps.puede_moverse
assert j_x.con_mando
assert pulsar(g, boton_c(22, "A")) is None and j_ps.panel is None
_, ctl_p2, ev_p2 = conectar(1, 44, "PS4 Controller")
pulsar(g, *ev_p2)
assert g.mandos.hay_mando(3) and g.mandos.tipo(3) == "playstation" and j_ps.con_mando
assert j_ps.nombre_tecla("interactuar") == "Cruz"
# Se desconecta el Xbox y entra uno genérico (no reconocido) en su lugar.
pulsar(g, *quitar(11))
assert not j_x.con_mando
gen, _, ev_g2 = conectar(0, 55, "USB Gamepad", reconocido=False)
pulsar(g, *ev_g2)
assert j_x.con_mando and j_x.nombre_tecla("interactuar") == "A"
x0 = j_x.hitbox.x
gen.ejes[M.EJE_X] = 1.0
for _ in range(15):
    g._actualizar_partida(DT)
gen.ejes[M.EJE_X] = 0.0
assert j_x.hitbox.x > x0, "el genérico mueve por joystick"
print("conectar/desconectar: PS sale y vuelve (PS4), el Xbox se cambia por uno genérico")
print(f"\nTODO OK ({pygame.version.ver})")
