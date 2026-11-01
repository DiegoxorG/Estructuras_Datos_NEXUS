"""Mandos (controles de Xbox y parecidos) para los jugadores 3 y 4.

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

Botones (control de Xbox en Windows; si en otro mando salen cambiados, se
ajusta BOTONES / EJES con `python pruebas/probar_mando.py`):

    stick izquierdo o cruceta   moverse / elegir opción
    A                           interactuar (mantener: consolas, paneles...)
    X                           usar la habilidad
    Y                           árbol de habilidades
    LB o LT (mantener)          caminar en sigilo
    RB                          celular (NEXUS)
    B                           volver (solo en los menús)
    START                       pausa en la partida (en los menús, aceptar)
"""

import pygame


# Números de botón y eje del control de Xbox con SDL2 en Windows (XInput).
BOTONES = {"A": 0, "B": 1, "X": 2, "Y": 3, "LB": 4, "RB": 5, "BACK": 6, "START": 7}
EJE_X, EJE_Y = 0, 1          # stick izquierdo
EJE_LT = 4                   # gatillo izquierdo (-1 suelto, 1 a fondo)
ZONA_MUERTA = 0.45           # el stick tiene que pasar de aquí para contar

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


NOMBRE_BOTON = {"interactuar": "A", "habilidad": "X", "habilidades": "Y", "celular": "RB", "soltar": "B",
                "sigilo": "LB", "arriba": "Stick", "abajo": "Stick",
                "izquierda": "Stick", "derecha": "Stick", "volver": "B"}


class _TeclasConMando:
    """Lo que devuelve pygame.key.get_pressed(), más las teclas virtuales."""

    def __init__(self, base, mandos):
        self.base, self.mandos = base, mandos

    def __getitem__(self, tecla):
        if es_virtual(tecla):
            return self.mandos.presionada(tecla)
        return self.base[tecla]


class Mandos:
    def __init__(self):
        self.por_puesto = {}       # puesto -> pygame.joystick.Joystick
        self._stick_y = {}         # puesto -> -1/0/1 (para no repetir en los menús)
        self._stick_x = {}
        try:
            pygame.joystick.init()
            for i in range(pygame.joystick.get_count()):
                self._conectar(pygame.joystick.Joystick(i))
        except pygame.error:
            pass

    # -- Conexión ----------------------------------------------------------------

    def _conectar(self, joy):
        if any(j.get_instance_id() == joy.get_instance_id() for j in self.por_puesto.values()):
            return None
        for puesto in PUESTOS_CON_MANDO:
            if puesto not in self.por_puesto:
                joy.init()
                self.por_puesto[puesto] = joy
                return puesto
        return None

    def _desconectar(self, instance_id):
        for puesto, joy in list(self.por_puesto.items()):
            if joy.get_instance_id() == instance_id:
                del self.por_puesto[puesto]
                return puesto
        return None

    def hay_mando(self, puesto):
        return puesto in self.por_puesto

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
            if accion in ("arriba", "abajo", "izquierda", "derecha"):
                dx, dy = self._direccion(joy)
                return {"arriba": dy < 0, "abajo": dy > 0,
                        "izquierda": dx < 0, "derecha": dx > 0}[accion]
            if accion == "sigilo":
                lt = joy.get_axis(EJE_LT) if joy.get_numaxes() > EJE_LT else -1
                return bool(joy.get_button(BOTONES["LB"])) or lt > 0.3
            boton = {"interactuar": "A", "habilidad": "X", "habilidades": "Y",
                     "volver": "B", "celular": "RB", "soltar": "B"}[accion]
            return bool(joy.get_button(BOTONES[boton]))
        except pygame.error:
            return False

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
        desconexión (devuelve [] en ese caso).
        """
        if ev.type == pygame.JOYDEVICEADDED:
            try:
                self._conectar(pygame.joystick.Joystick(ev.device_index))
            except pygame.error:
                pass
            return []
        if ev.type == pygame.JOYDEVICEREMOVED:
            self._desconectar(ev.instance_id)
            return []
        puesto = self._puesto_de(getattr(ev, "instance_id", None))
        if puesto is None:
            return []
        if ev.type == pygame.JOYBUTTONDOWN:
            nombre = next((n for n, b in BOTONES.items() if b == ev.button), None)
            accion = {"A": "interactuar", "X": "habilidad", "Y": "habilidades",
                      "B": "volver", "START": "pausa", "RB": "celular"}.get(nombre)
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
            # El stick como "flecha" para elegir opciones: una vez por empujón.
            nuevo = -1 if ev.value < -0.6 else (1 if ev.value > 0.6 else 0)
            if abs(ev.value) < 0.3:
                nuevo = 0
            antes = self._stick_y.get(puesto, 0)
            if nuevo != 0 and antes == 0:
                self._stick_y[puesto] = nuevo
                return [(puesto, "arriba" if nuevo < 0 else "abajo")]
            if nuevo == 0:
                self._stick_y[puesto] = 0
        if ev.type == pygame.JOYAXISMOTION and ev.axis == EJE_X:
            nuevo = -1 if ev.value < -0.6 else (1 if ev.value > 0.6 else 0)
            if abs(ev.value) < 0.3:
                nuevo = 0
            antes = self._stick_x.get(puesto, 0)
            if nuevo != 0 and antes == 0:
                self._stick_x[puesto] = nuevo
                return [(puesto, "izquierda" if nuevo < 0 else "derecha")]
            if nuevo == 0:
                self._stick_x[puesto] = 0
        return []
