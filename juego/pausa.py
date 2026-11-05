"""Menú de pausa: Esc (o START en el mando) durante la partida.

Mientras está abierto el juego queda congelado: _actualizar_partida no corre,
así que los aliens, el reloj de la ronda, los eventos y el tutorial se
detienen (todo avanza con `dt`, no con el reloj de pygame).

Tiene cuatro vistas:
    "menu"       Continuar / Opciones / Logros / Terminar partida
    "opciones"   volumen del sonido, campo de visión y oscuridad, pantalla completa,
                 y las vistas de prueba: hitboxes, árbol del alien y grafo
                 (NEXUS o la nave, screens/grafo_vista.py)
    "logros"     el árbol de logros de la partida (screens/logros.py)
    "confirmar"  ¿seguro que quieres terminar la partida?

En "logros" el cursor recorre el árbol: arriba/abajo en preorden (pasa por
todos), izquierda sube al padre y derecha baja al primer hijo.

La clase no dibuja nada (eso es screens/pausa.py) ni toca el juego
directamente: `tecla()` y `activar()` devuelven una acción ("continuar",
"terminar", "pantalla_completa"...) y juego/app.py la ejecuta.
"""

import pygame

from juego.audio_manager import audio_manager


OPCIONES_PAUSA = [
    ("Continuar", "continuar"),
    ("Opciones", "opciones"),
    ("Logros", "logros"),
    ("Terminar partida", "confirmar"),
]

OPCIONES_CONFIRMAR = [
    ("No, seguir jugando", "no"),
    ("Sí, terminar", "terminar"),
]

PASO_VOLUMEN = 10
DURACION_AVISO_MS = 1800

ARRIBA = (pygame.K_UP, pygame.K_w)
ABAJO = (pygame.K_DOWN, pygame.K_s)
IZQUIERDA = (pygame.K_LEFT, pygame.K_a)
DERECHA = (pygame.K_RIGHT, pygame.K_d)
ACEPTAR = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)


def mover_en_logros(arbol, nodo, key):
    """Mueve el cursor por el árbol de logros con una tecla y devuelve el nodo.

    Arriba/abajo siguen el preorden (pasan por todos, rama por rama),
    izquierda sube al padre y derecha baja al primer hijo. Lo usan la pausa y
    la pantalla de resultados.
    """
    orden = arbol.preorden()
    nodo = nodo if nodo in orden else orden[0]
    if key in ARRIBA:
        nodo = orden[(orden.index(nodo) - 1) % len(orden)]
    elif key in ABAJO:
        nodo = orden[(orden.index(nodo) + 1) % len(orden)]
    elif key in IZQUIERDA and nodo.padre is not None:
        nodo = nodo.padre
    elif key in DERECHA and nodo.hijos:
        nodo = nodo.hijos[0]
    return nodo


class MenuPausa:
    def __init__(self, juego):
        self.juego = juego
        self.vista = "menu"
        self.seleccion = 0
        self.aviso = ""           # texto corto bajo los botones ("Próximamente")
        self.aviso_ms = 0
        self.rects = []           # rects de las opciones, los llena el dibujo (para el mouse)
        self.nodo = None          # logro seleccionado en la vista "logros"
        self.rects_logros = {}    # nodo -> rect, también los llena el dibujo

    # -- Qué hay en cada vista ---------------------------------------------------

    def opciones(self):
        """Lista de (texto, acción) de la vista actual."""
        if self.vista == "logros":
            return []
        if self.vista == "opciones":
            efectos = round(audio_manager.sfx_volume * 100)
            return [
                (f"Sonido: < {efectos}% >", "efectos"),
                ("Campo de visión y oscuridad: " + ("Sí" if self.juego.oscuridad else "No"), "oscuridad"),
                ("Pantalla completa: " + ("Sí" if self.juego.pantalla_completa else "No"),
                 "pantalla_completa"),
                ("Ver hitboxes: " + ("Sí" if self.juego.mostrar_hitboxes else "No"), "hitboxes"),
                (f"Árbol del alien: < {self._texto_arbol()} >", "arbol"),
                (f"Grafo: < {self._texto_grafo()} >", "grafo"),
                ("Volver", "volver"),
            ]
        if self.vista == "confirmar":
            return OPCIONES_CONFIRMAR
        return OPCIONES_PAUSA

    def _texto_arbol(self):
        if not self.juego.mostrar_arbol_alien or not self.juego.aliens:
            return "No"
        return f"{self.juego.alien_en_vista + 1} de {len(self.juego.aliens)}"

    VISTAS_GRAFO = [None, "nexus", "nave"]

    def _texto_grafo(self):
        return {None: "No", "nexus": "NEXUS", "nave": "Nave"}[getattr(self.juego, "vista_grafo", None)]

    def _cambiar_grafo(self, signo):
        """Ciclo No -> NEXUS -> Nave -> No (screens/grafo_vista.py)."""
        juego = self.juego
        vistas = self.VISTAS_GRAFO
        actual = vistas.index(getattr(juego, "vista_grafo", None))
        juego.vista_grafo = vistas[(actual + signo) % len(vistas)]
        if juego.vista_grafo is not None:
            juego.mostrar_arbol_alien = False     # una vista de prueba a la vez

    def _cambiar_arbol(self, signo):
        """Ciclo No -> alien 1 -> alien 2 -> ... -> No (o al revés)."""
        juego = self.juego
        total = len(juego.aliens)
        if total == 0:
            juego.mostrar_arbol_alien = False
            return
        # 0 = apagado, 1..total = qué alien se ve.
        actual = juego.alien_en_vista + 1 if juego.mostrar_arbol_alien else 0
        nuevo = (actual + signo) % (total + 1)
        juego.mostrar_arbol_alien = nuevo > 0
        if nuevo > 0:
            juego.alien_en_vista = nuevo - 1
            juego.vista_grafo = None

    def titulo(self):
        return {"opciones": "Opciones", "confirmar": "¿Terminar la partida?"}.get(self.vista, "Pausa")

    def subtitulo(self):
        if self.vista == "confirmar":
            return "Se pierde todo lo que llevan de esta partida."
        return ""

    # -- Entrada -----------------------------------------------------------------

    def actualizar(self, dt):
        self.aviso_ms = max(0, self.aviso_ms - dt)

    def _ir_a(self, vista):
        self.vista = vista
        self.seleccion = 0
        self.aviso_ms = 0
        # Los rects eran de la vista anterior (los vuelve a llenar el dibujo):
        # un movimiento del mouse en el mismo cuadro dejaba la selección en
        # una opción que esta vista no tiene, y Enter tumbaba el juego.
        self.rects = []
        self.rects_logros = {}

    @property
    def arbol(self):
        gestor = getattr(self.juego, "logros", None)
        return gestor.arbol if gestor is not None else None

    def _tecla_logros(self, key):
        if key in (pygame.K_ESCAPE, pygame.K_BACKSPACE) or key in ACEPTAR:
            self._ir_a("menu")
            self.seleccion = 2
            return
        self.nodo = mover_en_logros(self.arbol, self.nodo, key)

    def tecla(self, key):
        """Procesa una tecla. Devuelve la acción para juego/app.py, o None."""
        if self.vista == "logros":
            self._tecla_logros(key)
            return None
        n = len(self.opciones())
        if key == pygame.K_ESCAPE:
            if self.vista == "menu":
                return "continuar"
            self._ir_a("menu")
            return None
        if key in ARRIBA:
            self.seleccion = (self.seleccion - 1) % n
        elif key in ABAJO:
            self.seleccion = (self.seleccion + 1) % n
        elif key in IZQUIERDA:
            return self._ajustar(-1)
        elif key in DERECHA:
            return self._ajustar(+1)
        elif key in ACEPTAR:
            return self.activar(self.seleccion)
        return None

    def click(self, pos):
        if self.vista == "logros":
            self.mover_mouse(pos)
            return None
        for i, rect in enumerate(self.rects):
            if rect.collidepoint(pos):
                self.seleccion = i
                return self.activar(i)
        return None

    def mover_mouse(self, pos):
        if self.vista == "logros":
            for nodo, rect in self.rects_logros.items():
                if rect.collidepoint(pos):
                    self.nodo = nodo
            return
        for i, rect in enumerate(self.rects):
            if rect.collidepoint(pos):
                self.seleccion = i
                return

    def _ajustar(self, signo):
        """Izquierda/derecha sobre una opción con valor."""
        accion = self.opciones()[self.seleccion][1]
        if accion == "efectos":
            nuevo = _limitar(round(audio_manager.sfx_volume * 100) + signo * PASO_VOLUMEN)
            audio_manager.apply_sfx_volume(nuevo)
        elif accion == "arbol":
            self._cambiar_arbol(signo)
        elif accion == "grafo":
            self._cambiar_grafo(signo)
        elif accion in ("oscuridad", "pantalla_completa", "hitboxes"):
            return self.activar(self.seleccion)
        return None

    def activar(self, indice):
        accion = self.opciones()[indice][1]
        if self.vista == "menu":
            if accion == "opciones":
                self._ir_a("opciones")
            elif accion == "confirmar":
                self._ir_a("confirmar")
            elif accion == "logros":
                if self.arbol is None:
                    self.aviso, self.aviso_ms = "Esta partida no tiene logros", DURACION_AVISO_MS
                else:
                    self._ir_a("logros")
                    self.nodo = self.arbol.raiz
            elif accion == "continuar":
                return "continuar"
            return None
        if self.vista == "confirmar":
            if accion == "terminar":
                return "terminar"
            self._ir_a("menu")
            return None
        # Opciones
        if accion == "efectos":
            # Con Enter (o A en el mando) da la vuelta: 0, 10, ... 100, 0.
            actual = round(audio_manager.sfx_volume * 100)
            audio_manager.apply_sfx_volume(0 if actual >= 100 else _limitar(actual + PASO_VOLUMEN))
        elif accion == "oscuridad":
            self.juego.oscuridad = not self.juego.oscuridad
        elif accion == "pantalla_completa":
            return "pantalla_completa"
        elif accion == "hitboxes":
            self.juego.mostrar_hitboxes = not self.juego.mostrar_hitboxes
        elif accion == "arbol":
            self._cambiar_arbol(1)
        elif accion == "grafo":
            self._cambiar_grafo(1)
        elif accion == "volver":
            self._ir_a("menu")
            self.seleccion = 1
        return None


def _limitar(valor):
    return max(0, min(100, int(valor)))
