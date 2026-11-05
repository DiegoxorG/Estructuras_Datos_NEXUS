"""Mandos (Xbox, PlayStation y parecidos) para los jugadores 3 y 4.

El juego está hecho alrededor del teclado: cada puesto tiene sus teclas
(jugador.py) y todo pregunta "¿está presionada esta tecla?". Para no reescribir
eso, cada botón del mando se traduce a una **tecla virtual**: un número que no
es de ninguna tecla real. Así:

- lo que se mantiene (moverse, mantener E, sigilo) se pregunta igual que con
  el teclado: `teclas[tecla]`, envolviendo `pygame.key.get_pressed()` con
  `Mandos.envolver()`;
- lo que se presiona una vez (interactuar, abrir el árbol...) llega como si
  fuera un KEYDOWN de esa tecla virtual (`Mandos.evento()` -> lista de teclas).

El primer mando que se conecta es el "Mando 1" (esquema 2) y el segundo el
"Mando 2" (esquema 3). Por defecto son de los jugadores 3 y 4, pero cada
jugador puede escoger su control en la pantalla "controles" (app.py): las
teclas virtuales van por esquema, no por puesto. Se pueden conectar y
desconectar con el juego abierto.

En el menú, la cantidad de jugadores y los resultados, el mando hace de
flechas, Enter y Esc, para que se pueda jugar sin tocar el teclado.

Botones, por POSICIÓN (en Xbox / en PlayStation):

    stick izquierdo o cruceta   moverse / elegir opción
    abajo   (A / Cruz)          interactuar (mantener: consolas, paneles...)
    izq.    (X / Cuadrado)      usar la habilidad
    arriba  (Y / Triángulo)     árbol de habilidades
    LB o LT / L1 o L2 (mantener) caminar en sigilo
    RB / R1                     celular (NEXUS)
    der.    (B / Círculo)       volver (en los menús) / soltar / cerrar
    Start / Options             pausa en la partida (en los menús, aceptar)

Cómo se lee cada mando: SDL numera los botones distinto en cada marca (en un
DualShock el botón 4 es Share, no LB). Por eso, si SDL **reconoce** el mando
(`pygame._sdl2.controller.is_controller`), se abre con la API "game
controller", que nombra los botones por posición con los nombres de Xbox
(CONTROLLER_BUTTON_A es el de abajo también en PlayStation). Si no lo
reconoce, o si esa API no se puede importar, se lee como joystick con los
números del control de Xbox (BOTONES / EJES), como antes. Para revisar un
mando: `python pruebas/probar_mando.py`.

Ojo: un mando abierto como controller manda **también** los eventos JOY* de
siempre; esos se ignoran (por instance_id), o cada botón contaría dos veces.
"""

import pygame

try:
    from pygame._sdl2 import controller as _sdl_controller
except Exception:          # pygame viejo o sin _sdl2: todo por joystick
    _sdl_controller = None


# Números de botón y eje del control de Xbox con SDL2 en Windows (XInput).
# Solo para los mandos que SDL no reconoce como controller (respaldo).
BOTONES = {"A": 0, "B": 1, "X": 2, "Y": 3, "LB": 4, "RB": 5, "BACK": 6, "START": 7}
EJE_X, EJE_Y = 0, 1          # stick izquierdo
EJE_LT = 4                   # gatillo izquierdo (-1 suelto, 1 a fondo)
ZONA_MUERTA = 0.45           # el stick tiene que pasar de aquí para contar

# Los mismos botones con la API game controller (por posición, en todo mando).
# Los valores de SDL; getattr por si alguna versión no trae la constante.
BOTONES_CONTROLLER = {
    "A": getattr(pygame, "CONTROLLER_BUTTON_A", 0),
    "B": getattr(pygame, "CONTROLLER_BUTTON_B", 1),
    "X": getattr(pygame, "CONTROLLER_BUTTON_X", 2),
    "Y": getattr(pygame, "CONTROLLER_BUTTON_Y", 3),
    "BACK": getattr(pygame, "CONTROLLER_BUTTON_BACK", 4),
    "START": getattr(pygame, "CONTROLLER_BUTTON_START", 6),
    "LB": getattr(pygame, "CONTROLLER_BUTTON_LEFTSHOULDER", 9),
    "RB": getattr(pygame, "CONTROLLER_BUTTON_RIGHTSHOULDER", 10),
}
CRUCETA_CONTROLLER = {
    getattr(pygame, "CONTROLLER_BUTTON_DPAD_UP", 11): "arriba",
    getattr(pygame, "CONTROLLER_BUTTON_DPAD_DOWN", 12): "abajo",
    getattr(pygame, "CONTROLLER_BUTTON_DPAD_LEFT", 13): "izquierda",
    getattr(pygame, "CONTROLLER_BUTTON_DPAD_RIGHT", 14): "derecha",
}
EJE_C_X = getattr(pygame, "CONTROLLER_AXIS_LEFTX", 0)
EJE_C_Y = getattr(pygame, "CONTROLLER_AXIS_LEFTY", 1)
EJE_C_LT = getattr(pygame, "CONTROLLER_AXIS_TRIGGERLEFT", 4)

# Eventos de mando que app.py le pasa a Mandos.evento(). Los de controller
# solo existen con SDL2 (getattr: si no, -1, que no es de ningún evento).
_EV = lambda nombre: getattr(pygame, nombre, -1)
EVENTOS_CONEXION = (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED,
                    _EV("CONTROLLERDEVICEADDED"), _EV("CONTROLLERDEVICEREMOVED"))
EVENTOS_ENTRADA = (pygame.JOYBUTTONDOWN, pygame.JOYHATMOTION, pygame.JOYAXISMOTION,
                   _EV("CONTROLLERBUTTONDOWN"), _EV("CONTROLLERAXISMOTION"))
EVENTOS_MANDO = EVENTOS_ENTRADA + EVENTOS_CONEXION

# Puestos (0 = jugador 1) que juegan con mando, en orden de conexión.
PUESTOS_CON_MANDO = (2, 3)

# Teclas virtuales: muy por encima de cualquier código de tecla de pygame.
BASE_VIRTUAL = 0x7F000000
ACCIONES = ("arriba", "abajo", "izquierda", "derecha", "interactuar", "habilidad",
            "habilidades", "sigilo", "volver", "celular", "soltar")


def tecla_virtual(puesto, accion):
    return BASE_VIRTUAL + puesto * 32 + ACCIONES.index(accion)


def es_virtual(tecla):
    return isinstance(tecla, int) and tecla >= BASE_VIRTUAL


def accion_de(tecla):
    """(puesto, acción) de una tecla virtual."""
    resto = tecla - BASE_VIRTUAL
    return resto // 32, ACCIONES[resto % 32]


# Qué botón (por su nombre de Xbox, o sea por posición) hace cada acción.
BOTON_DE_ACCION = {"interactuar": "A", "habilidad": "X", "habilidades": "Y",
                   "celular": "RB", "soltar": "B", "volver": "B", "sigilo": "LB",
                   "pausa": "START"}
# Y al revés, para los eventos de botón (LB no está: el sigilo se mantiene).
ACCION_DE_BOTON = {"A": "interactuar", "X": "habilidad", "Y": "habilidades",
                   "B": "volver", "START": "pausa", "RB": "celular"}

# Cómo se llama cada botón en pantalla según el mando. La tipografía del juego
# no trae ✕ ○ □ △ (ver pruebas/prueba_textos.py): en el texto van con nombre
# y screens/paneles.py dibuja el símbolo donde hay espacio.
NOMBRES_BOTONES = {
    "xbox": {"A": "A", "B": "B", "X": "X", "Y": "Y", "LB": "LB", "RB": "RB",
             "LT": "LT", "START": "Start", "BACK": "Back"},
    "playstation": {"A": "Cruz", "B": "Círculo", "X": "Cuadrado", "Y": "Triángulo",
                    "LB": "L1", "RB": "R1", "LT": "L2", "START": "Options", "BACK": "Share"},
}
NOMBRE_TIPO = {"xbox": "Xbox", "playstation": "PlayStation", "otro": "mando"}


def nombre_boton(accion, tipo="xbox"):
    """Cómo se escribe en pantalla el botón de `accion` en un mando de `tipo`
    ("otro" se escribe como Xbox: la mayoría de mandos genéricos lo imitan)."""
    if accion in ("arriba", "abajo", "izquierda", "derecha"):
        return "Stick"
    boton = BOTON_DE_ACCION.get(accion)
    if boton is None:
        return "?"
    return NOMBRES_BOTONES.get(tipo, NOMBRES_BOTONES["xbox"])[boton]


# Lo de siempre (Xbox): lo usa quien no sabe de qué mando se trata.
NOMBRE_BOTON = {accion: nombre_boton(accion) for accion in
                ("interactuar", "habilidad", "habilidades", "celular", "soltar", "sigilo",
                 "arriba", "abajo", "izquierda", "derecha", "volver")}


# -- Qué mando es ------------------------------------------------------------------

_NOMBRES_XBOX = ("xbox", "x-box", "xinput", "microsoft")
_NOMBRES_PS = ("ps3", "ps4", "ps5", "dualsense", "dualshock", "playstation",
               "sony", "wireless controller")


def tipo_por_nombre(nombre, guid=None):
    """"xbox", "playstation" u "otro" según el nombre que da SDL y, si no
    alcanza, el fabricante que va dentro del GUID.

    Ninguna versión de pygame ni de pygame-ce expone el tipo que sabe SDL
    (SDL_GameControllerGetType), así que se adivina. Xbox va primero: el de
    Xbox se llama "Xbox Wireless Controller" y "Wireless Controller" a secas
    es como se anuncia un DualShock 4.
    """
    n = (nombre or "").lower()
    if any(p in n for p in _NOMBRES_XBOX):
        return "xbox"
    if any(p in n for p in _NOMBRES_PS):
        return "playstation"
    g = (guid or "").lower()
    # GUID de SDL2: bytes 4-5 = fabricante (little endian). 054c Sony, 045e
    # Microsoft; los de XInput en Windows empiezan con "xinput" en ASCII.
    if g.startswith("78696e707574") or g[8:12] == "5e04":
        return "xbox"
    if g[8:12] == "4c05":
        return "playstation"
    return "otro"


class MandoSDL:
    """Un mando que SDL reconoce como controller: botones por posición.

    Por fuera se parece al Joystick (get_instance_id, get_name) para que el
    resto del código y las pruebas los traten igual."""

    es_controller = True

    def __init__(self, controlador, joy):
        self.controlador, self.joy = controlador, joy
        self.tipo = tipo_por_nombre(self.get_name(), _guid(joy))

    def get_instance_id(self):
        return self.joy.get_instance_id()

    def get_name(self):
        nombre = getattr(self.controlador, "name", None)
        if callable(nombre):
            nombre = nombre()
        return nombre or self.joy.get_name()

    def boton(self, nombre):
        return bool(self.controlador.get_button(BOTONES_CONTROLLER[nombre]))

    def eje(self, eje):
        return _normalizar(self.controlador.get_axis(eje))

    def direccion(self):
        c = self.controlador
        dx = int(bool(c.get_button(CRUCETA_INV["derecha"]))) - int(bool(c.get_button(CRUCETA_INV["izquierda"])))
        dy = int(bool(c.get_button(CRUCETA_INV["abajo"]))) - int(bool(c.get_button(CRUCETA_INV["arriba"])))
        if dx == 0 and dy == 0:
            ax, ay = self.eje(EJE_C_X), self.eje(EJE_C_Y)
            dx = -1 if ax < -ZONA_MUERTA else (1 if ax > ZONA_MUERTA else 0)
            dy = -1 if ay < -ZONA_MUERTA else (1 if ay > ZONA_MUERTA else 0)
        return dx, dy


CRUCETA_INV = {accion: boton for boton, accion in CRUCETA_CONTROLLER.items()}


def _normalizar(valor):
    """Los ejes de controller vienen de -32768 a 32767 (los gatillos de 0 a
    32767); los de joystick, de -1 a 1. Todo queda de -1 a 1."""
    if abs(valor) > 1.5:
        return max(-1.0, min(1.0, valor / 32767))
    return float(valor)


def _guid(joy):
    try:
        return joy.get_guid()
    except (AttributeError, pygame.error):
        return None


def es_controller(mando):
    return getattr(mando, "es_controller", False)


def tipo_de_mando(mando):
    """El tipo de un mando de `Mandos.por_puesto` (MandoSDL o Joystick)."""
    tipo = getattr(mando, "tipo", None)
    if tipo:
        return tipo
    try:
        return tipo_por_nombre(mando.get_name(), _guid(mando))
    except (AttributeError, pygame.error):
        return "otro"


def tipo_de(esquema):
    """Tipo del mando conectado en `esquema`, según los Mandos del juego
    abierto (el último creado). "xbox" si no hay: lo de siempre."""
    activos = Mandos.activo
    if activos is None:
        return "xbox"
    return activos.tipo(esquema)


def botones_conectados(accion):
    """El botón de `accion` en los mandos conectados, para las pistas que
    son de todos (pausa, resultados): "A", "Cruz" o "A/Cruz". Sin mandos, el
    de Xbox, como antes."""
    activos = Mandos.activo
    nombres = []
    for puesto in sorted(activos.por_puesto) if activos is not None else ():
        nombre = nombre_boton(accion, activos.tipo(puesto))
        if nombre not in nombres:
            nombres.append(nombre)
    return "/".join(nombres) or nombre_boton(accion)


class _TeclasConMando:
    """Lo que devuelve pygame.key.get_pressed(), más las teclas virtuales."""

    def __init__(self, base, mandos):
        self.base, self.mandos = base, mandos

    def __getitem__(self, tecla):
        if es_virtual(tecla):
            return self.mandos.presionada(tecla)
        return self.base[tecla]


class Mandos:
    # Los del juego abierto: jugador.py pregunta aquí de qué tipo es el mando
    # de cada uno, para escribir sus botones.
    activo = None

    def __init__(self):
        self.por_puesto = {}       # puesto -> MandoSDL o pygame.joystick.Joystick
        self._stick_y = {}         # puesto -> -1/0/1 (para no repetir en los menús)
        self._stick_x = {}
        Mandos.activo = self
        try:
            pygame.joystick.init()
        except pygame.error:
            return
        if _sdl_controller is not None:
            try:
                _sdl_controller.init()
                if hasattr(_sdl_controller, "set_eventstate"):
                    _sdl_controller.set_eventstate(True)
            except Exception:
                pass
        try:
            for i in range(pygame.joystick.get_count()):
                self._conectar_indice(i)
        except pygame.error:
            pass

    # -- Conexión ----------------------------------------------------------------

    @staticmethod
    def _abrir(indice, joy):
        """El mando `indice` como MandoSDL si SDL lo reconoce; si no, como
        Joystick (con los números de Xbox)."""
        if _sdl_controller is not None:
            try:
                if _sdl_controller.is_controller(indice):
                    return MandoSDL(_sdl_controller.Controller(indice), joy)
            except Exception:
                pass
        return joy

    def _conectar_indice(self, indice):
        try:
            joy = pygame.joystick.Joystick(indice)
            if self._puesto_de(joy.get_instance_id()) is not None:
                return None          # el segundo aviso del mismo mando
            return self._conectar(self._abrir(indice, joy))
        except pygame.error:
            return None

    def _conectar(self, joy):
        if any(j.get_instance_id() == joy.get_instance_id() for j in self.por_puesto.values()):
            return None
        for puesto in PUESTOS_CON_MANDO:
            if puesto not in self.por_puesto:
                if not es_controller(joy):
                    joy.init()
                self.por_puesto[puesto] = joy
                return puesto
        return None

    def _desconectar(self, instance_id):
        for puesto, joy in list(self.por_puesto.items()):
            if joy.get_instance_id() == instance_id:
                del self.por_puesto[puesto]
                self._stick_x.pop(puesto, None)
                self._stick_y.pop(puesto, None)
                return puesto
        return None

    def hay_mando(self, puesto):
        return puesto in self.por_puesto

    def tipo(self, puesto):
        """"xbox", "playstation" u "otro"; "xbox" si no hay mando ahí."""
        mando = self.por_puesto.get(puesto)
        return "xbox" if mando is None else tipo_de_mando(mando)

    def nombre_esquema(self, esquema, nombre):
        """"Mando 1 (Xbox)" para un esquema con mando conectado; si no, `nombre`."""
        mando = self.por_puesto.get(esquema)
        if mando is None:
            return nombre
        tipo = tipo_de_mando(mando)
        return f"{nombre} ({NOMBRE_TIPO[tipo]})" if tipo != "otro" else nombre

    def _puesto_de(self, instance_id):
        for puesto, joy in self.por_puesto.items():
            if joy.get_instance_id() == instance_id:
                return puesto
        return None

    # -- Lo que se mantiene ----------------------------------------------------------

    def presionada(self, tecla):
        puesto, accion = accion_de(tecla)
        joy = self.por_puesto.get(puesto)
        if joy is None:
            return False
        try:
            if es_controller(joy):
                return self._presionada_controller(joy, accion)
            if accion in ("arriba", "abajo", "izquierda", "derecha"):
                dx, dy = self._direccion(joy)
                return {"arriba": dy < 0, "abajo": dy > 0,
                        "izquierda": dx < 0, "derecha": dx > 0}[accion]
            if accion == "sigilo":
                lt = joy.get_axis(EJE_LT) if joy.get_numaxes() > EJE_LT else -1
                return bool(joy.get_button(BOTONES["LB"])) or lt > 0.3
            return bool(joy.get_button(BOTONES[BOTON_DE_ACCION[accion]]))
        except pygame.error:
            return False

    @staticmethod
    def _presionada_controller(mando, accion):
        if accion in ("arriba", "abajo", "izquierda", "derecha"):
            dx, dy = mando.direccion()
            return {"arriba": dy < 0, "abajo": dy > 0,
                    "izquierda": dx < 0, "derecha": dx > 0}[accion]
        if accion == "sigilo":
            # LB/L1 o el gatillo izquierdo (LT/L2: de 0 suelto a 1 a fondo).
            return mando.boton("LB") or mando.eje(EJE_C_LT) > 0.3
        return mando.boton(BOTON_DE_ACCION[accion])

    @staticmethod
    def _direccion(joy):
        dx = dy = 0
        if joy.get_numhats() > 0:
            hx, hy = joy.get_hat(0)
            dx, dy = hx, -hy                 # en la cruceta, arriba es +1
        if dx == 0 and dy == 0 and joy.get_numaxes() > EJE_Y:
            ax, ay = joy.get_axis(EJE_X), joy.get_axis(EJE_Y)
            dx = -1 if ax < -ZONA_MUERTA else (1 if ax > ZONA_MUERTA else 0)
            dy = -1 if ay < -ZONA_MUERTA else (1 if ay > ZONA_MUERTA else 0)
        return dx, dy

    def envolver(self, teclas):
        return _TeclasConMando(teclas, self)

    # -- Lo que se presiona una vez -------------------------------------------------------

    def evento(self, ev):
        """Traduce un evento del mando a teclas virtuales "presionadas".

        Devuelve una lista de (puesto, acción). También maneja la conexión y
        desconexión (devuelve [] en ese caso): llegan dos avisos por mando
        (JOYDEVICE* y CONTROLLERDEVICE*) y el segundo no hace nada.
        """
        if ev.type in (pygame.JOYDEVICEADDED, _EV("CONTROLLERDEVICEADDED")):
            indice = getattr(ev, "device_index", getattr(ev, "which", None))
            if indice is not None:
                self._conectar_indice(indice)
            return []
        if ev.type in (pygame.JOYDEVICEREMOVED, _EV("CONTROLLERDEVICEREMOVED")):
            self._desconectar(getattr(ev, "instance_id", None))
            return []
        puesto = self._puesto_de(getattr(ev, "instance_id", None))
        if puesto is None:
            return []
        mando = self.por_puesto[puesto]
        if es_controller(mando):
            # De este mando solo cuentan los eventos de controller: los JOY*
            # que manda SDL a la vez repetirían cada pulsación.
            if ev.type == _EV("CONTROLLERBUTTONDOWN"):
                if ev.button in CRUCETA_CONTROLLER:
                    return [(puesto, CRUCETA_CONTROLLER[ev.button])]
                nombre = next((n for n, b in BOTONES_CONTROLLER.items() if b == ev.button), None)
                accion = ACCION_DE_BOTON.get(nombre)
                return [(puesto, accion)] if accion else []
            if ev.type == _EV("CONTROLLERAXISMOTION"):
                if ev.axis == EJE_C_Y:
                    return self._stick(puesto, _normalizar(ev.value), self._stick_y, ("arriba", "abajo"))
                if ev.axis == EJE_C_X:
                    return self._stick(puesto, _normalizar(ev.value), self._stick_x, ("izquierda", "derecha"))
            return []
        if ev.type == pygame.JOYBUTTONDOWN:
            nombre = next((n for n, b in BOTONES.items() if b == ev.button), None)
            accion = ACCION_DE_BOTON.get(nombre)
            return [(puesto, accion)] if accion else []
        if ev.type == pygame.JOYHATMOTION:
            hx, hy = ev.value
            if hy == 1:
                return [(puesto, "arriba")]
            if hy == -1:
                return [(puesto, "abajo")]
            # Izquierda/derecha: árbol de logros de la pausa y pestañas del celular.
            if hx == -1:
                return [(puesto, "izquierda")]
            if hx == 1:
                return [(puesto, "derecha")]
            return []
        if ev.type == pygame.JOYAXISMOTION and ev.axis == EJE_Y:
            return self._stick(puesto, ev.value, self._stick_y, ("arriba", "abajo"))
        if ev.type == pygame.JOYAXISMOTION and ev.axis == EJE_X:
            return self._stick(puesto, ev.value, self._stick_x, ("izquierda", "derecha"))
        return []

    @staticmethod
    def _stick(puesto, valor, ultimo, acciones):
        """El stick como "flecha" para elegir opciones: una vez por empujón."""
        nuevo = -1 if valor < -0.6 else (1 if valor > 0.6 else 0)
        if abs(valor) < 0.3:
            nuevo = 0
        antes = ultimo.get(puesto, 0)
        if nuevo != 0 and antes == 0:
            ultimo[puesto] = nuevo
            return [(puesto, acciones[0] if nuevo < 0 else acciones[1])]
        if nuevo == 0:
            ultimo[puesto] = 0
        return []
