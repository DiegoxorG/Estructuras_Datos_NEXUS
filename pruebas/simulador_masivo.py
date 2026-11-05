"""Simulador masivo: muchas partidas de 2, 3 y 4 bots, sin ventana, para cazar bugs.

    python pruebas/simulador_masivo.py                       (24 partidas: 2/3/4 x 4 dificultades)
    python pruebas/simulador_masivo.py -n 120 -p 3           (120 partidas en 3 procesos)
    python pruebas/simulador_masivo.py -n 8 -j 4 -d dificil  (solo 4 jugadores en Difícil)
    python pruebas/simulador_masivo.py -n 12 --semilla 500 --sin-dibujo --max-s 300
    python pruebas/simulador_masivo.py -n 1 --semilla 37 -v  (repetir una partida y ver el detalle)

Es el hermano grande de pruebas/simulador.py. Aquel mide el balance de la
misión con dos bots que no usan nada más; este juega como juegan los grupos
de verdad, para recorrer la mayor cantidad posible de estados del juego:

- De 2 a 4 jugadores, en las cuatro dificultades, con roles al azar (con
  semilla: la partida N con la semilla S siempre es la misma).
- Pasa por los menús de verdad (cantidad, dificultad, "¿con qué juega cada
  uno?" y la selección de rol), con las teclas de cada uno.
- Los jugadores 3 y 4 juegan con mando: se "conectan" dos mandos falsos
  (MandoFalso) y su entrada pasa por juego/mandos.py como la de un control de
  Xbox (cruceta, botones y eventos JOYBUTTONDOWN/JOYHATMOTION). A veces el
  jugador 2 también escoge un mando, y a veces se juega sin mandos (el 3 y el
  4 no se mueven, como en el juego real sin mandos).
- Los bots caminan con BFS sobre una cuadrícula del mapa hacia lo que dice la
  flecha de la misión (Mision.punto_objetivo), interactúan y mantienen la
  tecla, rescatan, prenden la caja de fusibles, abren las puertas para dos,
  usan el celular (NEXUS: investigar, desmentir, compartir, rastrear,
  reportar, cambiar de pestaña), el árbol de habilidades y las habilidades,
  se esconden, se dejan atrapar a propósito de vez en cuando, sueltan cosas,
  abren la pausa y las Terminales NEXUS. Todo con algo de azar (con semilla).

Lo que detecta y cuenta (el resumen final dice cuántas partidas tuvieron
cada tipo de problema):

    excepcion            algo reventó (con el traceback)
    inalcanzable         algo de la misión (consola, nota, pieza, celda,
                         caja de fusibles...) no se alcanza desde el inicio
                         caminando, ni con todas las puertas abiertas
    mision_imposible     piezas, decodificador o kit que ya no alcanzan
    jugador_en_pared     la hitbox de un jugador libre se solapa con paredes
    alien_en_pared       la hitbox de un alien se solapa con paredes
    alien_atascado       un alien patrullando sin avanzar más de 4 s
    bot_trabado          un bot con meta que no se mueve en 8 s (puede ser del bot)
    panel_sin_cerrar     un panel que no se deja cerrar con las teclas
    estado_imposible     vidas negativas, preso sin celda, cursor fuera de
                         rango, fuera del mapa, eliminado que se mueve...
    sin_terminar         llegó al límite de tiempo simulado sin ganar ni perder
    cuadro_lento         actualizar o dibujar tardó más de 25 ms

Ojo: "bot_trabado" y "sin_terminar" muchas veces son límites de los bots (no
son tan buenos como una persona). El resto casi siempre es del juego.
"""

import argparse
import math
import os
import random
import sys
import time
import traceback
from collections import Counter, defaultdict, deque

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

DT = 1000 // 60
PASO = 16                 # lado de la celda de la cuadrícula de los bots
RADIO_EVITAR = 240
LIMITE_LENTO_MS = 25
DIFICULTADES_SIM = ("facil", "normal", "dificil", "inteligente")
CANTIDADES_SIM = (2, 3, 4)


# -- Lo que se carga en cada proceso ----------------------------------------------------

pygame = App = None
TECLAS = None


class Teclas(dict):
    """Lo que devuelve pygame.key.get_pressed() en la simulación."""

    def __getitem__(self, k):
        return self.get(k, False)


def _preparar_proceso(mapa=None):
    """Importa el juego (una vez por proceso) y parchea lo que hace falta."""
    global pygame, App, TECLAS
    if App is not None:
        return
    import pygame as _pygame
    _pygame.init()
    pygame = _pygame
    from juego import app as _app
    from juego import objetos_mapa, historial_logros
    App = _app
    if mapa:
        objetos_mapa.mapa_activo = lambda: mapa
    # Que las partidas simuladas no se anoten en Guardado/logros.json.
    historial_logros.agregar = lambda claves: None
    App.historial_logros.agregar = historial_logros.agregar
    TECLAS = Teclas()
    pygame.key.get_pressed = lambda: TECLAS


class MandoFalso:
    """Un "control de Xbox" que maneja el bot: lo que lee juego/mandos.py
    (botones, cruceta y ejes) sale de aquí."""

    _siguiente_id = 900

    def __init__(self):
        MandoFalso._siguiente_id += 1
        self.id = MandoFalso._siguiente_id
        self.botones = set()
        self.hat = (0, 0)

    def get_instance_id(self):
        return self.id

    def init(self):
        pass

    def get_button(self, i):
        return 1 if i in self.botones else 0

    def get_numhats(self):
        return 1

    def get_hat(self, i):
        return self.hat

    def get_numaxes(self):
        return 6

    def get_axis(self, i):
        from juego.mandos import EJE_LT
        return -1.0 if i == EJE_LT else 0.0

    def soltar_todo(self):
        self.botones.clear()
        self.hat = (0, 0)


# -- Entrada: teclado y mando ------------------------------------------------------------------

BOTON_DE = {"interactuar": "A", "habilidad": "X", "habilidades": "Y", "celular": "RB",
            "volver": "B", "soltar": "B", "pausa": "START"}


class Entrada:
    """Las manos de un jugador: mantener y presionar sus teclas, sea con
    teclado (esquemas 0 y 1) o con mando (2 y 3)."""

    def __init__(self, g, esquema):
        self.g, self.esquema = g, esquema
        from entidades.jugador import TECLAS_POR_PUESTO
        self.teclas = TECLAS_POR_PUESTO[esquema]

    @property
    def mando(self):
        return self.g.mandos.por_puesto.get(self.esquema)

    def soltar_todo(self):
        if self.mando is not None:
            self.mando.soltar_todo()

    def mantener(self, accion, si=True):
        """Mantener (moverse, interactuar, sigilo)."""
        from juego.mandos import BOTONES
        mando = self.mando
        if mando is not None:
            if accion in ("arriba", "abajo", "izquierda", "derecha"):
                hx, hy = mando.hat
                if si:
                    if accion == "arriba": hy = 1
                    if accion == "abajo": hy = -1
                    if accion == "izquierda": hx = -1
                    if accion == "derecha": hx = 1
                mando.hat = (hx, hy)
                return
            boton = "LB" if accion == "sigilo" else BOTON_DE.get(accion)
            if boton is not None and si:
                mando.botones.add(BOTONES[boton])
            return
        if accion in ("arriba", "abajo", "izquierda", "derecha"):
            from Movimiento.Personaje import CONTROLES_WASD, CONTROLES_FLECHAS
            controles = (CONTROLES_WASD, CONTROLES_FLECHAS)[self.esquema]
            for k in controles[accion][:1]:
                TECLAS[k] = si or TECLAS.get(k, False)
            return
        for k in self.teclas.get(accion, ())[:1]:
            TECLAS[k] = si or TECLAS.get(k, False)

    def presionar(self, accion):
        """Presionar una vez (KEYDOWN, o el evento del mando)."""
        g = self.g
        mando = self.mando
        if mando is not None:
            from juego.mandos import BOTONES
            if accion in ("arriba", "abajo", "izquierda", "derecha"):
                valor = {"arriba": (0, 1), "abajo": (0, -1), "izquierda": (-1, 0),
                         "derecha": (1, 0)}[accion]
                ev = pygame.event.Event(pygame.JOYHATMOTION, joy=0, instance_id=mando.id,
                                        hat=0, value=valor)
            else:
                ev = pygame.event.Event(pygame.JOYBUTTONDOWN, joy=0, instance_id=mando.id,
                                        button=BOTONES[BOTON_DE[accion]])
            for puesto, acc in g.mandos.evento(ev):
                g._tecla_mando(puesto, acc)
            return
        if accion == "pausa":
            g._manejar_tecla(pygame.K_ESCAPE)
            return
        if accion == "volver":
            accion = "celular"
        teclas = self.teclas.get(accion, ())
        if teclas:
            g._manejar_tecla(teclas[0])


# -- Cuadrícula y caminos (BFS) -----------------------------------------------------------------

class Mapa:
    """Cuadrícula de dónde cabe un jugador, para buscar caminos con BFS."""

    def __init__(self, g):
        self.g = g
        j = g.jugadores[0]
        self.w, self.h = j.personaje.hitbox_w, j.personaje.hitbox_h
        m = g.mundo
        base = m.paredes_base
        self.libre = set()
        for x in range(0, m.ancho - self.w, PASO):
            for y in range(0, m.alto - self.h, PASO):
                if pygame.Rect(x, y, self.w, self.h).collidelist(base) == -1:
                    self.libre.add((x, y))
        self._extra = None
        self._extra_cuadro = -1

    def bloqueos(self):
        """Lo que hoy cierra el paso además del mapa fijo (puertas, compuertas)."""
        g = self.g
        from juego.mundo import paredes_extra
        extra = paredes_extra(g.mundo)
        extra += [p["rect"] for p in g.puertas_dobles if not p["abierta"]]
        extra += [c["rect"] for c in g.compuertas if c["cerrada"]]
        return extra

    def celda_de(self, punto):
        x0, y0 = punto[0] - self.w / 2, punto[1] - self.h / 2
        return (int(x0) // PASO * PASO, int(y0) // PASO * PASO)

    def _inicio(self, desde, ok):
        x0, y0 = desde[0] - self.w / 2, desde[1] - self.h / 2
        candidatas = [(int(x0) // PASO * PASO + dx, int(y0) // PASO * PASO + dy)
                      for dx in (-PASO, 0, PASO, 2 * PASO) for dy in (-PASO, 0, PASO, 2 * PASO)]
        candidatas = [c for c in candidatas if ok(c)] or [self.celda_de(desde)]
        return min(candidatas, key=lambda c: math.dist(c, (x0, y0)))

    def alcanzables(self, desde, extra=()):
        """Todas las celdas a las que se llega desde `desde` (BFS)."""
        def ok(c):
            if c not in self.libre:
                return False
            return not extra or pygame.Rect(c[0], c[1], self.w, self.h).collidelist(extra) == -1
        inicio = self._inicio(desde, ok)
        vistos = {inicio}
        cola = deque([inicio])
        while cola:
            c = cola.popleft()
            for dx, dy in ((PASO, 0), (-PASO, 0), (0, PASO), (0, -PASO)):
                v = (c[0] + dx, c[1] + dy)
                if v not in vistos and ok(v):
                    vistos.add(v)
                    cola.append(v)
        return vistos

    def componentes(self, extra):
        """Celda -> número de su componente conexa con `extra` cerrado
        (guardado por la lista de bloqueos: se rehace solo si cambia)."""
        firma = tuple(sorted(tuple(r) for r in extra))
        cache = self.__dict__.setdefault("_componentes", {})
        if firma in cache:
            return cache[firma]
        if len(cache) > 64:
            cache.clear()
        libres = self.libre
        if extra:
            libres = {c for c in libres
                      if pygame.Rect(c[0], c[1], self.w, self.h).collidelist(extra) == -1}
        comp = {}
        n = 0
        for c0 in libres:
            if c0 in comp:
                continue
            n += 1
            comp[c0] = n
            cola = deque([c0])
            while cola:
                c = cola.popleft()
                for dx, dy in ((PASO, 0), (-PASO, 0), (0, PASO), (0, -PASO)):
                    v = (c[0] + dx, c[1] + dy)
                    if v in libres and v not in comp:
                        comp[v] = n
                        cola.append(v)
        cache[firma] = comp
        return comp

    def llega(self, desde, hasta, radio, extra=None):
        """¿Se puede ir caminando de `desde` a menos de `radio` de `hasta`?"""
        if extra is None:
            extra = self.bloqueos()
        comp = self.componentes(extra)
        inicio = self._inicio(desde, lambda c: c in comp)
        n = comp.get(inicio)
        if n is None:
            return False
        cx, cy = self.celda_de(hasta)
        r = int(radio // PASO) + 2
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                c = (cx + dx * PASO, cy + dy * PASO)
                if comp.get(c) == n and math.dist((c[0] + self.w / 2, c[1] + self.h / 2), hasta) <= radio:
                    return True
        return False

    def cerca_de(self, celdas, punto, radio):
        """¿Alguna de `celdas` deja el centro del jugador a `radio` de `punto`?"""
        cx, cy = self.celda_de(punto)
        r = int(radio // PASO) + 2
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                c = (cx + dx * PASO, cy + dy * PASO)
                if c in celdas and math.dist((c[0] + self.w / 2, c[1] + self.h / 2), punto) <= radio:
                    return True
        return False

    def zona_de(self, alien):
        ax, ay = alien.centro
        alcance = max(RADIO_EVITAR, alien.alcance_vision * 0.85)
        medio = alien.datos["medio_angulo"] + 0.15
        r = int(alcance // PASO) + 1
        bx, by = int(ax - self.w / 2) // PASO * PASO, int(ay - self.h / 2) // PASO * PASO
        zona = set()
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                d2 = (dx * dx + dy * dy) * PASO * PASO
                if d2 <= RADIO_EVITAR ** 2:
                    zona.add((bx + dx * PASO, by + dy * PASO))
                elif d2 <= alcance ** 2 and medio > 0.15:
                    dif = (math.atan2(dy, dx) - alien.angulo + math.pi) % (2 * math.pi) - math.pi
                    if abs(dif) <= medio:
                        zona.add((bx + dx * PASO, by + dy * PASO))
        return zona

    def camino(self, desde, hasta, cerca=0, evitar=(), extra=None, max_nodos=60000):
        """Lista de celdas de `desde` a cerca de `hasta`, o None."""
        if extra is None:
            extra = self.bloqueos()
        if not self.llega(desde, hasta, max(PASO, cerca) + 24, extra):
            return None
        prohibidas = set()
        for alien in evitar:
            prohibidas |= self.zona_de(alien)

        def ok(c):
            if c not in self.libre or c in prohibidas:
                return False
            return not extra or pygame.Rect(c[0], c[1], self.w, self.h).collidelist(extra) == -1
        inicio = self._inicio(desde, ok)
        meta = (hasta[0] - self.w / 2, hasta[1] - self.h / 2)
        radio = max(PASO, cerca)
        previo = {inicio: None}
        cola = deque([inicio])
        mejor = None
        while cola and len(previo) < max_nodos:
            c = cola.popleft()
            if math.dist(c, meta) <= radio:
                mejor = c
                break
            for dx, dy in ((PASO, 0), (-PASO, 0), (0, PASO), (0, -PASO)):
                v = (c[0] + dx, c[1] + dy)
                if v not in previo and ok(v):
                    previo[v] = c
                    cola.append(v)
        if mejor is None:
            return None
        ruta = []
        while mejor is not None:
            ruta.append(mejor)
            mejor = previo[mejor]
        return ruta[::-1]

    def huida(self, desde, peligro, pasos=40):
        extra = self.bloqueos()
        def ok(c):
            return c in self.libre and (not extra or pygame.Rect(c[0], c[1], self.w, self.h).collidelist(extra) == -1)
        inicio = self._inicio(desde, ok)
        previo, nivel = {inicio: None}, {inicio: 0}
        cola = deque([inicio])
        mejor, mejor_d = inicio, 0
        while cola:
            c = cola.popleft()
            d = math.dist((c[0] + self.w / 2, c[1] + self.h / 2), peligro)
            if d > mejor_d:
                mejor, mejor_d = c, d
            if nivel[c] >= pasos:
                continue
            for dx, dy in ((PASO, 0), (-PASO, 0), (0, PASO), (0, -PASO)):
                v = (c[0] + dx, c[1] + dy)
                if v not in previo and ok(v):
                    previo[v], nivel[v] = c, nivel[c] + 1
                    cola.append(v)
        ruta = []
        while mejor is not None:
            ruta.append(mejor)
            mejor = previo[mejor]
        return ruta[::-1]


# -- Registro de problemas ------------------------------------------------------------------------

class Registro:
    def __init__(self, partida):
        self.partida = partida
        self.problemas = []          # (tipo, firma, detalle)
        self._firmas = set()
        self.lentos = []             # (ms, qué, contexto)

    def anotar(self, tipo, firma, detalle):
        """Un problema; los repetidos (misma firma) se anotan una sola vez."""
        clave = (tipo, firma)
        if clave in self._firmas:
            return
        self._firmas.add(clave)
        self.problemas.append((tipo, str(firma), str(detalle)))


# -- Los bots ----------------------------------------------------------------------------------------

def _paso_rapido(rng, prob_por_s):
    """True con probabilidad `prob_por_s` por segundo (un cuadro es DT ms)."""
    return rng.random() < prob_por_s * DT / 1000


class Bot:
    def __init__(self, g, jugador, mapa, rng, registro):
        self.g, self.j, self.mapa, self.rng, self.reg = g, jugador, mapa, rng, registro
        self.entrada = Entrada(g, jugador.esquema)
        self.meta = None
        self.ruta = []
        self.replan_ms = 0
        self.quieto_ms = 0
        self.ultimo = jugador.hitbox.topleft
        self.huir_ms = 0
        self.en_meta_ms = 0
        self.espera_teclas = 0        # cuadros hasta la próxima tecla "de una vez"
        self.panel_ms = 0
        self.con_panel_ms = 0        # cuánto lleva con algún panel abierto (aunque cambie)
        self.panel_id = None
        self.plan_celular = None
        self.celular_ms = rng.randint(8000, 40000)   # cuándo mirar el celular
        self.arbol_ms = rng.randint(5000, 30000)
        self.habilidad_ms = rng.randint(4000, 20000)
        self.soltar_ms = rng.randint(60000, 240000)
        self.pausa_ms = rng.randint(30000, 200000)
        self.escondido_ms = 0
        self.suicida_ms = 0           # se deja atrapar a propósito
        self.proxima_suicida = rng.randint(40000, 400000)
        self.explorar = None
        self.ha_esperado = 0

    # -- Utilidades ---------------------------------------------------------------------
    def presionar(self, accion):
        if self.espera_teclas > 0:
            return False
        self.entrada.presionar(accion)
        self.espera_teclas = self.rng.randint(3, 9)
        return True

    def libre(self):
        j = self.j
        return j.preso is None and not j.eliminado and j.puede_moverse

    def _ir(self, destino, cerca, dt, evitar=True):
        """Planea (cada tanto) y camina hacia `destino`."""
        j = self.j
        self.replan_ms -= dt
        if destino != self.meta or self.replan_ms <= 0 or not self.ruta:
            self.meta = destino
            peligro = []
            if evitar and self.suicida_ms <= 0:
                peligro = [a for a in self.g.aliens
                           if a.descanso_ms <= 0 and not getattr(a, "disfrazado", False)
                           and not getattr(a, "oculta", False)
                           and math.dist(a.centro, destino) > RADIO_EVITAR
                           and 60 < math.dist(a.centro, j.hitbox.center) < 1300]
            ruta = None
            self.esperando = False
            if peligro and self.ha_esperado < 9000:
                ruta = self.mapa.camino(j.hitbox.center, destino, cerca, peligro, max_nodos=12000)
                if ruta is None:
                    # Todos los caminos pasan por donde ve un alien: espera
                    # quieto (en sigilo) un rato antes de arriesgarse.
                    self.ha_esperado += 450
                    if self.mapa.llega(j.hitbox.center, destino, cerca + 84):
                        self.esperando = True
                        self.ruta = []
                        self.replan_ms = 450
                        return
            if ruta is None:
                ruta = self.mapa.camino(j.hitbox.center, destino, cerca)
                if ruta is None:
                    # Lo que está detrás de algo (una puerta, una consola en la
                    # pared): basta con llegar cerca.
                    ruta = self.mapa.camino(j.hitbox.center, destino, cerca + 60)
                if ruta is not None:
                    self.ha_esperado = 0
            self.ruta = ruta or []
            self.replan_ms = 450 + self.rng.randint(0, 200)
        self._seguir()

    def _seguir(self):
        j = self.j
        while self.ruta and abs(self.ruta[0][0] - j.hitbox.x) <= 3 and abs(self.ruta[0][1] - j.hitbox.y) <= 3:
            self.ruta.pop(0)
        if not self.ruta:
            return
        tx, ty = self.ruta[0]
        x, y = j.hitbox.topleft
        # Si lleva unos cuadros sin avanzar, se alinea del todo a la celda: a
        # 2 px de la fila de la ruta puede rozar una esquina y no pasar.
        if (x, y) == getattr(self, "_pos_seguir", None):
            self._sin_avance = getattr(self, "_sin_avance", 0) + 1
        else:
            self._sin_avance = 0
        self._pos_seguir = (x, y)
        margen = 0 if self._sin_avance > 4 else 2
        if self._sin_avance > 4 and abs(tx - x) > 2 and abs(ty - y) > 0:
            # Primero alinear el otro eje (sin empujar contra la esquina).
            self.entrada.mantener("abajo" if ty > y else "arriba")
            return
        if tx - x > margen: self.entrada.mantener("derecha")
        if x - tx > margen: self.entrada.mantener("izquierda")
        if ty - y > margen: self.entrada.mantener("abajo")
        if y - ty > margen: self.entrada.mantener("arriba")

    # -- Paneles ------------------------------------------------------------------------
    def _mover_cursor_a(self, indice, total):
        """Una tecla hacia `indice` (el más corto); True si ya está ahí."""
        j = self.j
        if total <= 0 or j.cursor == indice:
            return True
        abajo = (indice - j.cursor) % total
        self.presionar("abajo" if abajo <= total - abajo else "arriba")
        return False

    def manejar_panel(self, dt):
        g, j = self.g, self.j
        panel = j.panel
        if id(panel) != self.panel_id:
            self.panel_id = id(panel)
            self.panel_ms = 0
            self.panel_objetivo = None
        self.panel_ms += dt
        self.con_panel_ms += dt
        tipo, accion = panel.get("tipo"), panel.get("accion")
        if self.con_panel_ms > 25000:
            self.reg.anotar("panel_sin_cerrar", (tipo, accion, panel.get("vista")),
                            f"{j.rol}: panel {tipo}/{accion}/{panel.get('vista')} abierto 25 s")
            self.con_panel_ms = 0
        if self.con_panel_ms > 12000:
            # Que se cierre como sea: cada tecla de cerrar que exista.
            self.presionar(self.rng.choice(("celular", "habilidades", "soltar", "volver",
                                            "interactuar", "habilidad")))
            return
        if self.panel_ms < self.rng.randint(150, 500):
            return       # "leyendo"
        if tipo in ("aviso", "resultado"):
            self.presionar("interactuar")
            return
        if tipo == "habilidades":
            opciones = j.arbol.opciones()
            pagables = [i for i, n in enumerate(opciones) if n.costo <= j.puntos_para_habilidades]
            if not pagables or self.panel_ms > 4000:
                self.presionar("habilidades")
                return
            if self.panel_objetivo is None:
                self.panel_objetivo = self.rng.choice(pagables)
            if self._mover_cursor_a(self.panel_objetivo, len(opciones)):
                self.presionar("interactuar")
                self.panel_objetivo = None
            return
        if tipo == "emision":
            cursor = panel.get("cursor_mapa")
            meta = getattr(self, "_meta_emision", None)
            if meta is None:
                alien = min(g.aliens, key=lambda a: math.dist(a.centro, j.hitbox.center), default=None)
                meta = alien.centro if alien is not None else j.hitbox.center
                meta = (meta[0] + self.rng.randint(-300, 300), meta[1] + self.rng.randint(-300, 300))
                self._meta_emision = meta
            if cursor and math.dist(cursor, meta) > 40 and self.panel_ms < 3500:
                if meta[0] - cursor[0] > 20: self.entrada.mantener("derecha")
                if cursor[0] - meta[0] > 20: self.entrada.mantener("izquierda")
                if meta[1] - cursor[1] > 20: self.entrada.mantener("abajo")
                if cursor[1] - meta[1] > 20: self.entrada.mantener("arriba")
                return
            if self.rng.random() < 0.15:
                self.presionar("habilidad")         # se arrepiente: cierra sin gastar
            else:
                self.presionar("interactuar")
            self._meta_emision = None
            return
        if tipo == "celular":
            self._manejar_celular(panel)
            return
        if accion == "codigo":
            if self.panel_objetivo is None:
                puerta = g.mision.puertas[panel.get("puerta", 0)]
                sabe = any(puerta["codigo"] in n["texto"] and n["leida_por"] & set(g.jugadores)
                           for n in g.mision.notas)
                if sabe and self.rng.random() < 0.95:
                    self.panel_objetivo = panel["codigos"].index(puerta["codigo"])
                elif not sabe and self.rng.random() < 0.6:
                    self.panel_objetivo = -1          # se va sin marcar
                else:
                    self.panel_objetivo = self.rng.randrange(len(panel["codigos"]))
            if self.panel_objetivo == -1:
                self.presionar("soltar" if self.rng.random() < 0.5 else "celular")
                if self.panel_ms > 3000:
                    self.panel_objetivo = 0
                return
            if self._mover_cursor_a(self.panel_objetivo, len(panel["opciones"])):
                self.presionar("interactuar")
            return
        if accion == "soltar":
            if self.panel_objetivo is None:
                self.panel_objetivo = self.rng.randrange(len(panel["opciones"]))
            if self._mover_cursor_a(self.panel_objetivo, len(panel["opciones"])):
                self.presionar("interactuar" if self.rng.random() < 0.7 else "soltar")
            return
        if accion in ("ayuda_menu", "ayuda_tema", "infiltrado_menu", "infiltrado_acusar"):
            # La Terminal NEXUS: mirar un par de cosas y salir.
            if self.panel_ms > 3000 or self.rng.random() < 0.2:
                self.presionar("celular")
                return
            opciones = panel.get("opciones", [])
            if panel.get("filas") and self.rng.random() < 0.5:
                self.presionar(self.rng.choice(("arriba", "abajo", "izquierda", "derecha")))
            elif opciones:
                if self.rng.random() < 0.5:
                    self.presionar(self.rng.choice(("arriba", "abajo")))
                else:
                    self.presionar("interactuar")
            return
        # Cualquier otro panel: probar teclas y cerrar.
        self.presionar(self.rng.choice(("interactuar", "celular", "soltar", "abajo")))

    def _manejar_celular(self, panel):
        g, j = self.g, self.j
        red = g.nexus
        vista = panel.get("vista")
        opciones = panel.get("opciones", [])
        if red is None:
            self.presionar("celular")
            return
        if self.con_panel_ms > 7000:
            self.presionar("celular")       # atrás, atrás... hasta cerrar
            return
        if vista == "feed":
            con_foto = [p for p in red.evidencias.get(j, []) if not p.desmentida]
            pendiente = [p for p in red.rumores_activos()
                         if red.nodo_de(j) in p.alcanzados and p not in red.evidencias.get(j, [])]
            from redes import celular as cel
            if con_foto or (pendiente and red.investigando.get(j) is None):
                if cel.pestana_de(red, j) != "misiones":
                    self.presionar(self.rng.choice(("izquierda", "derecha")))
                    return
                buscadas = con_foto or pendiente
                indices = [i for i, (_t, pub) in enumerate(opciones) if pub in buscadas]
                if indices:
                    if self._mover_cursor_a(indices[0], len(opciones)):
                        self.presionar("interactuar")
                    return
            # Nada que hacer: mirar al azar.
            r = self.rng.random()
            if r < 0.25:
                self.presionar(self.rng.choice(("izquierda", "derecha")))
            elif r < 0.45 and opciones:
                self.presionar(self.rng.choice(("arriba", "abajo")))
            elif r < 0.6 and opciones:
                self.presionar("interactuar")
            elif self.con_panel_ms > 2500:
                self.presionar("celular")
            return
        acciones = [o[1] for o in opciones]
        if vista == "post":
            preferidas = [a for a in ("desmentir", "investigar") if a in acciones]
            if preferidas and self.rng.random() < 0.9:
                objetivo = acciones.index(preferidas[0])
            else:
                objetivo = self.rng.randrange(len(acciones))
                if acciones[objetivo] == "compartir" and self.rng.random() < 0.7:
                    objetivo = acciones.index("volver")
            if self._mover_cursor_a(objetivo, len(opciones)):
                self.presionar("interactuar")
            return
        if vista == "ubicacion":
            objetivo = 1 if self.rng.random() < 0.8 else 0      # casi siempre recortada
            if self._mover_cursor_a(objetivo, len(opciones)):
                self.presionar("interactuar")
            return
        if vista in ("origen", "mensaje"):
            objetivo = self.rng.randrange(len(opciones)) if opciones else 0
            if opciones and self._mover_cursor_a(objetivo, len(opciones)):
                self.presionar("interactuar")
            elif not opciones:
                self.presionar("celular")
            return
        self.presionar("celular")

    # -- Decidir a dónde ir ------------------------------------------------------------
    def decidir(self):
        """(destino, cerca, qué hacer al llegar: None, "presionar" o "mantener")."""
        g, j, m = self.g, self.j, self.g.mision
        c = j.hitbox.center
        if self.suicida_ms > 0:
            alien = min((a for a in g._aliens_a_la_vista() if a.descanso_ms <= 0),
                        key=lambda a: math.dist(a.centro, c), default=None)
            if alien is not None:
                return alien.centro, 20, None
        # Apagón: a la caja buena.
        ev = g.eventos
        if ev is not None and ev.apagon and ev.caja is not None:
            otros = [b for b in self.otros if b.libre()]
            mio = math.dist(c, ev.caja["rect"].center)
            if not otros or mio <= min(math.dist(b.j.hitbox.center, ev.caja["rect"].center) for b in otros) + 300:
                return ev.caja["rect"].center, 30, "mantener"
        # Rescatar a un compañero encerrado.
        from misiones.mision import RADIO_RESCATE
        presos = [b.j for b in self.otros if b.j.preso is not None]
        if presos and m is not None and m.activa:
            preso = min(presos, key=lambda p: math.dist(p.preso["punto"], c))
            return preso.preso["punto"], RADIO_RESCATE - 40, "presionar"
        # Una puerta para dos que corta el camino: cada uno a un panel.
        destino = None
        objetivo = m.punto_objetivo(j) if m is not None and m.activa else None
        if objetivo is not None:
            destino = objetivo[0]
        doble = self._puerta_doble(destino)
        if doble is not None:
            return doble, 20, "mantener"
        if destino is not None:
            texto = objetivo[1]
            hace = "presionar"
            if "puerta" in texto:
                cerca = 60
            if any(p in texto for p in ("Hackea", "Repara", "crecer", "abono en", "Cuida")):
                hace = "mantener"
            if "Desmiente" in texto:
                hace = None
            return destino, cerca if "puerta" in texto else 24, hace
        # Nada que hacer: explorar o seguir a alguien.
        if self.explorar is None or math.dist(c, self.explorar) < 60 or self.rng.random() < 0.002:
            comp = self.mapa.componentes(self.mapa.bloqueos())
            inicio = self.mapa._inicio(c, lambda x: x in comp)
            mias = [x for x, n in comp.items() if n == comp.get(inicio)] or list(self.mapa.libre)
            celda = mias[self.rng.randrange(len(mias))]
            self.explorar = (celda[0] + self.mapa.w / 2, celda[1] + self.mapa.h / 2)
        return self.explorar, 40, None

    def _puerta_doble(self, destino):
        """El panel de una puerta para dos si hace falta abrirla para llegar."""
        g, j = self.g, self.j
        cerradas = [p for p in g.puertas_dobles if not p["abierta"]]
        if not cerradas or destino is None or g.sin_luz:
            return None
        if self.mapa.llega(j.hitbox.center, destino, 90):
            return None
        sin_dobles = [r for r in self.mapa.bloqueos()
                      if not any(r == p["rect"] for p in g.puertas_dobles)]
        if not self.mapa.llega(j.hitbox.center, destino, 90, sin_dobles):
            return None       # la puerta para dos no es lo que tapa
        libres = [b for b in [self] + self.otros if b.libre()]
        if len(libres) < 2:
            return None
        puerta = min(cerradas, key=lambda p: math.dist(p["rect"].center, j.hitbox.center))
        orden = sorted(libres, key=lambda b: b.j.puesto)
        i = orden.index(self) % 2
        return puerta["paneles"][i].center

    # -- Cada cuadro ----------------------------------------------------------------------
    def actualizar(self, dt):
        g, j = self.g, self.j
        self.espera_teclas -= 1
        for nombre in ("celular_ms", "arbol_ms", "habilidad_ms", "soltar_ms", "pausa_ms",
                       "proxima_suicida"):
            setattr(self, nombre, getattr(self, nombre) - dt)
        self.suicida_ms -= dt
        if j.eliminado or not j.puede_moverse:
            if self.rng.random() < 0.01:
                self.presionar(self.rng.choice(("interactuar", "celular", "habilidades")))
            return
        if g.en_tutorial:
            # Moverse un poco y pasar los pasos con la tecla de habilidad.
            self.entrada.mantener(self.rng.choice(("arriba", "abajo", "izquierda", "derecha")))
            self.entrada.mantener("sigilo", self.rng.random() < 0.5)
            if not g.tutorial.esta_listo(j) and self.rng.random() < 0.1:
                self.presionar("habilidad")
            return
        if j.preso is not None:
            if self.rng.random() < 0.005:
                self.presionar(self.rng.choice(("interactuar", "habilidad", "celular", "soltar")))
            return
        if j.escondido:
            self.escondido_ms -= dt
            if j.minijuego is not None:
                if j.minijuego.aguja_en_zona() and self.rng.random() < 0.7:
                    self.presionar("interactuar")
                return
            if self.escondido_ms <= 0:
                self.presionar("interactuar")      # salir
            return
        if j.panel is not None:
            self.manejar_panel(dt)
            return
        self.con_panel_ms = 0

        # -- Caminando --
        if self.proxima_suicida <= 0:
            self.proxima_suicida = self.rng.randint(80000, 400000)
            self.suicida_ms = 15000
        perseguidor = next((a for a in g._aliens_a_la_vista()
                            if a.descanso_ms <= 0 and (a.objetivo is j or (
                                math.dist(a.centro, j.hitbox.center) < 200 and j.cazable))), None)
        if perseguidor is not None and self.suicida_ms <= 0:
            # ¿Esconderse? Si hay un escondite a mano, a veces.
            esc = g.escondite_bajo(j)
            if esc is not None and self.rng.random() < 0.5:
                if self.presionar("interactuar"):
                    self.escondido_ms = self.rng.randint(2000, 9000)
                return
            self.huir_ms -= dt
            if self.huir_ms <= 0 or not self.ruta:
                self.ruta = self.mapa.huida(j.hitbox.center, perseguidor.centro)
                self.huir_ms = 500
                self.meta = None
            self._seguir()
            self._vigilar_trabado(dt, True)
            return

        # Cosas de vez en cuando.
        if self.celular_ms <= 0 and g.nexus is not None:
            self.celular_ms = self.rng.randint(15000, 60000)
            if self.presionar("celular"):
                return
        if g.nexus is not None and self.celular_ms < 50000 and (
                red_tiene_foto(g.nexus, j) or (_paso_rapido(self.rng, 0.02) and g.nexus.rumores_activos())):
            self.celular_ms = self.rng.randint(15000, 60000)
            if self.presionar("celular"):
                return
        if self.arbol_ms <= 0:
            self.arbol_ms = self.rng.randint(10000, 45000)
            opciones = j.arbol.opciones()
            if any(n.costo <= j.puntos_para_habilidades for n in opciones) or self.rng.random() < 0.2:
                if self.presionar("habilidades"):
                    return
        if self.habilidad_ms <= 0:
            self.habilidad_ms = self.rng.randint(6000, 30000)
            if self.presionar("habilidad"):
                return
        if self.soltar_ms <= 0:
            self.soltar_ms = self.rng.randint(60000, 240000)
            if self.presionar("soltar"):
                return
        if self.pausa_ms <= 0 and j.puesto == 0:
            self.pausa_ms = self.rng.randint(60000, 300000)
            self.presionar("pausa")
            return
        # Esconderse a propósito de vez en cuando.
        esc = g.escondite_bajo(j)
        if esc is not None and self.rng.random() < 0.01:
            if self.presionar("interactuar"):
                self.escondido_ms = self.rng.randint(1500, 6000)
                return

        destino, cerca, hace = self.decidir()
        llego = math.dist(j.hitbox.center, destino) <= max(cerca, 24) + 18
        if llego:
            self.en_meta_ms += dt
            self.ruta = []
            if hace == "mantener":
                self.entrada.mantener("interactuar")
                if self.en_meta_ms > 400 and self.rng.random() < 0.01:
                    self.presionar("interactuar")
            elif hace == "presionar":
                if self.en_meta_ms > 150 and self.rng.random() < 0.08:
                    self.presionar("interactuar")
                if self.en_meta_ms > 1500:
                    self.entrada.mantener("interactuar")
            else:
                # Llegó y no hay nada que hacer: seguir explorando un poco.
                if self.en_meta_ms > 2000:
                    self.explorar = None
        else:
            self.en_meta_ms = 0
            self._ir(destino, cerca, dt)
        cerca_alien = any(math.dist(a.centro, j.hitbox.center) < 650 and a.objetivo is not j
                          for a in g._aliens_a_la_vista())
        self.entrada.mantener("sigilo", (cerca_alien or getattr(self, "esperando", False))
                              and self.suicida_ms <= 0)
        self._vigilar_trabado(dt, not llego, destino)

    def _vigilar_trabado(self, dt, con_meta, destino=None):
        j = self.j
        if con_meta and j.hitbox.topleft == self.ultimo and not self.g.sin_luz \
                and not getattr(self, "esperando", False):
            self.quieto_ms += dt
            if self.quieto_ms > 8000:
                hay_ruta = bool(self.ruta)
                self.reg.anotar("bot_trabado",
                                (self.g.mision.fase if self.g.mision else None, j.rol,
                                 self.mapa.celda_de(j.hitbox.center)),
                                f"{j.rol} quieto 8 s en {j.hitbox.center} hacia {destino} "
                                f"(fase {self.g.mision.fase if self.g.mision else None}, "
                                f"{'con' if hay_ruta else 'sin'} ruta)")
                self.quieto_ms = 0
                self.ruta = []
                self.explorar = None
        else:
            self.quieto_ms = 0
        self.ultimo = j.hitbox.topleft


def red_tiene_foto(red, jugador):
    return any(not p.desmentida for p in red.evidencias.get(jugador, []))


# -- Revisiones -------------------------------------------------------------------------------------

FASES = ("prision", "sabotaje", "capsula", "huida", None)


def revisar_alcance(g, mapa, reg):
    """Al empezar: ¿se llega caminando a todo lo de la misión? (con las
    puertas con código, las de dos y las compuertas abiertas)."""
    m = g.mision
    j0 = g.jugadores[0]
    celdas = mapa.alcanzables(j0.hitbox.center, extra=())
    if m is None or not m.activa:
        return celdas
    from misiones.mision import RADIO_RESCATE
    from misiones.puertas import RADIO_PANEL
    from misiones.eventos import RADIO_CAJA
    cosas = []
    cosas += [("consola", k["rect"].center, 50) for k in m.consolas]
    cosas += [("capsula", m.capsula.center, 110)]
    cosas += [("celda", c["punto"], RADIO_RESCATE - 10) for c in m.celdas]
    for p in m.puertas:
        cosas += [("nota_candidata", n["rect"].center, 45) for n in p["candidatas"]]
        cosas.append((f"puerta_{p['nombre']}", p["rect"].center, 90))
    cosas += [("consumible_" + c["tipo"], c["rect"].center, 30) for c in m.consumibles]
    cosas += [("pieza", p["rect"].center, 20) for p in g.piezas]
    if g.eventos is not None:
        cosas += [("caja_fusibles", c["rect"].center, RADIO_CAJA - 5) for c in g.eventos.cajas]
    for d in g.puertas_dobles:
        cosas += [("panel_puerta_doble", p.center, RADIO_PANEL - 5) for p in d["paneles"]]
    cosas += [("terminal_nexus", z["rect"].center, 30) for z in g.zonas]
    bahia = g.guardia_planta
    if bahia is not None and bahia.planta is not None:
        cosas.append(("planta", bahia.planta["rect"].center, 60))
    for nombre, punto, radio in cosas:
        if not mapa.cerca_de(celdas, punto, radio):
            reg.anotar("inalcanzable", (g.mundo.nombre_mapa, nombre, tuple(int(v) for v in punto)),
                       f"{nombre} en {punto} no se alcanza caminando desde el inicio "
                       f"(mapa {g.mundo.nombre_mapa}, {len(g.jugadores)} jugadores)")
    return celdas


def revisar_estado(g, mapa, reg, alcanzables, t_ms, vistos):
    """Invariantes de la partida (lo que nunca debería pasar)."""
    m = g.mision
    mundo = g.mundo
    def mal(firma, detalle):
        reg.anotar("estado_imposible", firma, f"t={t_ms / 1000:.0f}s: {detalle}")
    for j in g.jugadores:
        h = j.hitbox
        if j.vidas < 0 or j.vidas > j.vidas_max:
            mal(("vidas", j.vidas), f"{j.rol} con {j.vidas} vidas (máx {j.vidas_max})")
        if j.piezas < 0:
            mal(("piezas_jugador",), f"{j.rol} con {j.piezas} piezas")
        if any(v <= 0 for v in j.objetos.values()):
            mal(("inventario",), f"{j.rol}: inventario con cantidades <= 0: {dict(j.objetos)}")
        if j.eliminado and (j.puede_moverse or j.preso is not None or j.escondido):
            mal(("eliminado_activo",), f"{j.rol} eliminado pero puede_moverse={j.puede_moverse} "
                                       f"preso={j.preso is not None} escondido={j.escondido}")
        if j.preso is not None:
            if m is None or not any(c is j.preso for c in m.celdas):
                mal(("preso_sin_celda",), f"{j.rol} preso en una celda que no es de la misión")
            elif j.preso["preso"] is not j:
                mal(("celda_de_otro",), f"{j.rol} preso pero su celda dice "
                                        f"{getattr(j.preso['preso'], 'rol', None)}")
        if j.escondido and j.escondite.get("ocupante") is not j:
            mal(("escondite_ajeno",), f"{j.rol} escondido en un escondite cuyo ocupante es otro")
        if j.escondido and j.preso is not None:
            mal(("escondido_y_preso",), f"{j.rol} escondido y preso a la vez")
        if not (0 <= h.left and h.right <= mundo.ancho and 0 <= h.top and h.bottom <= mundo.alto):
            mal(("fuera_del_mapa", j.rol), f"{j.rol} fuera del mapa: {h}")
        if j.panel is not None:
            total = g._total_opciones(j)
            if total > 0 and not 0 <= j.cursor < total and not j.panel.get("filas"):
                mal(("cursor", j.panel.get("tipo"), j.panel.get("accion"), j.panel.get("vista")),
                    f"{j.rol}: cursor {j.cursor} con {total} opciones en "
                    f"{j.panel.get('tipo')}/{j.panel.get('accion')}/{j.panel.get('vista')}")
            if j.preso is not None or j.eliminado:
                mal(("panel_preso", j.panel.get("tipo")), f"{j.rol} con un panel abierto estando "
                                                          f"{'preso' if j.preso else 'eliminado'}")
        if j.minijuego is not None and not j.escondido:
            mal(("minijuego_fuera",), f"{j.rol} con minijuego del escondite sin estar escondido")
        # Metido en una pared (libre y caminando).
        if j.preso is None and not j.escondido and not j.eliminado and j.puede_moverse:
            if g._colisiona_jugador(h):
                firma = ("jugador_en_pared", j.rol, mapa.celda_de(h.center))
                if firma not in vistos:
                    vistos[firma] = t_ms
                elif t_ms - vistos[firma] > 500:
                    reg.anotar("jugador_en_pared", (mapa.celda_de(h.center),),
                               f"t={t_ms / 1000:.0f}s: {j.rol} con la hitbox {h} dentro de una pared "
                               f"o puerta (fase {m.fase if m else None})")
            else:
                for clave in [k for k in vistos if k[0] == "jugador_en_pared" and k[1] == j.rol]:
                    del vistos[clave]
    for e in g.escondites:
        o = e.get("ocupante")
        if o is not None and o.escondite is not e:
            mal(("escondite_huerfano",), f"escondite con ocupante {o.rol} que no está adentro")
    if g.equipo.puntos < 0:
        mal(("puntos_equipo",), f"puntos del equipo negativos: {g.equipo.puntos}")
    for a in g.aliens:
        if getattr(a, "oculta", False):
            continue
        if not (0 <= a.hitbox.centerx <= mundo.ancho and 0 <= a.hitbox.centery <= mundo.alto):
            mal(("alien_fuera", a.nombre), f"{a.nombre} fuera del mapa: {a.hitbox}")
        if mundo.colisiona(a.hitbox):
            firma = ("alien_en_pared", a.nombre)
            if firma not in vistos:
                vistos[firma] = t_ms
            elif t_ms - vistos[firma] > 1000:
                reg.anotar("alien_en_pared", (a.tipo, mapa.celda_de(a.hitbox.center)),
                           f"t={t_ms / 1000:.0f}s: {a.nombre} ({a.accion}) con la hitbox {a.hitbox} "
                           f"dentro de una pared")
        else:
            vistos.pop(("alien_en_pared", a.nombre), None)
        if getattr(a, "atascado_ms", 0) > 4000 and a.accion in ("PATRULLAR", "VOLVER") \
                and not a.aturdido and a.descanso_ms <= 0:
            reg.anotar("alien_atascado", (a.nombre, a.accion, mapa.celda_de(a.centro)),
                       f"t={t_ms / 1000:.0f}s: {a.nombre} {a.accion} atascado en {a.centro}")
    if m is None or not m.activa:
        return
    if m.fase not in FASES:
        mal(("fase", m.fase), f"fase desconocida {m.fase}")
    if not 0 <= m.piezas_entregadas <= 3:
        mal(("piezas_entregadas", m.piezas_entregadas), f"piezas entregadas {m.piezas_entregadas}")
    if any(not 0 <= k["progreso"] <= 1 for k in m.consolas) or not 0 <= m.reparacion <= 1:
        mal(("progreso",), "progreso de consola o reparación fuera de [0, 1]")
    for c in m.celdas:
        p = c["preso"]
        if p is not None and p.preso is not c:
            mal(("celda_huerfana",), f"celda con preso {p.rol} que no está en ella")
    # ¿Se puede terminar todavía?
    from misiones.mision import PIEZAS_NECESARIAS
    vivos = [j for j in g.jugadores if not j.eliminado and j.puede_moverse]
    if m.fase in ("prision", "sabotaje", "capsula") and m.piezas_entregadas < PIEZAS_NECESARIAS:
        sueltas = sum(1 for p in g.piezas if not p["recogida"])
        llevan = sum(j.piezas for j in g.jugadores)
        if sueltas + llevan + m.piezas_entregadas < PIEZAS_NECESARIAS:
            reg.anotar("mision_imposible", ("piezas",),
                       f"t={t_ms / 1000:.0f}s: quedan {sueltas} sueltas + {llevan} en manos + "
                       f"{m.piezas_entregadas} entregadas < {PIEZAS_NECESARIAS} (fase {m.fase})")
    if vivos and m.fase == "sabotaje" and any(k["progreso"] < 1 for k in m.consolas):
        tecno = any(j.rol == "Tecnomante" for j in vivos)
        deco = (any(c["tipo"] == "decodificador" and not c["tomado"] for c in m.consumibles)
                or any("decodificador" in j.objetos for j in vivos))
        if not tecno and not deco:
            reg.anotar("mision_imposible", ("decodificador",),
                       f"t={t_ms / 1000:.0f}s: sin Tecnomante y sin decodificador en el mapa")
    if vivos and m.fase == "capsula":
        forj = any(j.rol == "Forjador" for j in vivos)
        kit = (any(c["tipo"] == "kit" and not c["tomado"] for c in m.consumibles)
               or any("kit" in j.objetos for j in vivos))
        if not forj and not kit:
            reg.anotar("mision_imposible", ("kit",),
                       f"t={t_ms / 1000:.0f}s: sin Forjador y sin kit en el mapa")
    # Lo que aparece a mitad de partida (lo que sueltan, rumores) también se tiene que alcanzar.
    nuevos = [("consumible_" + c["tipo"], c["rect"].center, 30) for c in m.consumibles if not c["tomado"]]
    nuevos += [("pieza", p["rect"].center, 20) for p in g.piezas if not p["recogida"]]
    if g.nexus is not None:
        nuevos += [("lugar_rumor", p.lugar, 60) for p in g.nexus.rumores_activos() if p.lugar is not None]
    for nombre, punto, radio in nuevos:
        clave = ("alcance", nombre, tuple(int(v) for v in punto))
        if clave in vistos:
            continue
        vistos[clave] = t_ms
        if not mapa.cerca_de(alcanzables, punto, radio):
            reg.anotar("inalcanzable", (g.mundo.nombre_mapa, nombre, tuple(int(v) for v in punto)),
                       f"t={t_ms / 1000:.0f}s: {nombre} en {punto} no se alcanza caminando "
                       f"(mapa {g.mundo.nombre_mapa})")


# -- Una partida ----------------------------------------------------------------------------------------

def preparar_partida(cfg, rng, reg):
    """Arma la partida pasando por los menús de verdad."""
    from data.roles import ROLES
    g = App.Game()
    con_mandos = cfg["mandos"]
    if con_mandos:
        for puesto in (2, 3):
            g.mandos.por_puesto[puesto] = MandoFalso()

    def avanzar():
        for _ in range(200):
            if g.transitions.is_idle():
                return
            g.transitions.update(g, 33)

    # Menú -> Jugar.
    accion_jugar = [b.action for b in g.menu_buttons].index("jugar")
    while g.menu_selected != accion_jugar:
        g._manejar_tecla(pygame.K_DOWN)
    g._manejar_tecla(pygame.K_RETURN); avanzar()
    assert g.current_screen == "cantidad", g.current_screen
    from screens.seleccion import OPCIONES
    while OPCIONES[g.cantidad_seleccionada] != cfg["jugadores"]:
        g._manejar_tecla(pygame.K_DOWN)
    g._manejar_tecla(pygame.K_RETURN); avanzar()
    assert g.current_screen == "dificultad", g.current_screen
    from data.dificultad import DIFICULTADES
    claves = [d["clave"] for d in DIFICULTADES]
    while claves[g.dificultad_seleccionada] != cfg["dificultad"]:
        g._manejar_tecla(pygame.K_DOWN)
    g._manejar_tecla(pygame.K_RETURN); avanzar()
    # ¿Con qué juega cada uno? (solo sale con mandos conectados)
    if g.current_screen == "controles":
        for esquema in cfg["esquemas"]:
            Entrada(g, esquema).presionar("interactuar")
        avanzar()
    assert g.current_screen == "roles", g.current_screen
    nombres = [r["nombre"] for r in ROLES]
    for puesto, rol in enumerate(cfg["roles"]):
        estado = g.seleccion_roles[puesto]
        entrada = Entrada(g, estado["esquema"])
        for _ in range(10):
            if nombres[estado["cursor"]] == rol:
                break
            entrada.presionar("abajo")
        entrada.presionar("interactuar")
    avanzar()
    assert g.current_screen == "partida", f"no empezó la partida: {g.current_screen}"
    return g


def configuracion(i, semilla, jugadores=None, dificultades=None, mapa=None):
    """La configuración de la partida i (determinista con la semilla)."""
    from data.roles import ROLES
    rng = random.Random(semilla * 7919 + i)
    cantidades = jugadores or CANTIDADES_SIM
    difs = dificultades or DIFICULTADES_SIM
    combos = [(n, d) for n in cantidades for d in difs]
    n, dif = combos[i % len(combos)]
    roles = rng.sample([r["nombre"] for r in ROLES], n)
    mandos = n == 2 and rng.random() < 0.5 or n > 2 and rng.random() < 0.9
    if mandos:
        esquemas = list(range(n))
        if n == 2 and rng.random() < 0.5:
            esquemas = rng.sample([0, 1, 2, 3], 2)
        elif rng.random() < 0.3:
            esquemas = rng.sample([0, 1, 2, 3], n)
    else:
        esquemas = list(range(n))
    # Partidas "asistidas": los aliens ven y oyen menos, para que los bots (que
    # son peores que una persona en sigilo) lleguen a las fases del final.
    asistida = rng.random() < 0.5
    # Partidas con "atajo": al terminar el tutorial ya abrieron las puertas con
    # código y apagaron las consolas (como si lo hubieran hecho), para que
    # también se jueguen la cápsula, los planos y la huida.
    atajo = "capsula" if rng.random() < 0.45 else None
    return {"i": i, "semilla": semilla * 100003 + i, "jugadores": n, "dificultad": dif,
            "roles": roles, "mandos": mandos, "esquemas": esquemas, "mapa": mapa,
            "asistida": asistida, "atajo": atajo}


def jugar(cfg, max_s=480, dibujar=True, cada_dibujo=6, verbose=False):
    """Juega una partida y devuelve un resumen (dict) con sus problemas."""
    _preparar_proceso(cfg.get("mapa"))
    random.seed(cfg["semilla"])
    rng = random.Random(cfg["semilla"])
    reg = Registro(cfg["i"])
    resumen = {"cfg": cfg, "resultado": None, "duracion_s": 0, "fases": {}, "capturas": 0,
               "problemas": reg.problemas, "lentos": reg.lentos, "cuadros": 0,
               "ms_actualizar": 0.0, "ms_dibujar": 0.0, "dibujos": 0, "planos": None}
    t_ms = 0
    g = None
    fase = None
    try:
        g = preparar_partida(cfg, rng, reg)
        if cfg.get("asistida") and g.dificultad is not None:
            original = g.dificultad.valor
            def valor(nombre, original=original):
                v = original(nombre)
                return v * 0.45 if nombre in ("vision_aliens", "oido_aliens") else v
            g.dificultad.valor = valor
        mapa = Mapa(g)
        alcanzables = revisar_alcance(g, mapa, reg)
        bots = [Bot(g, j, mapa, rng, reg) for j in g.jugadores]
        for b in bots:
            b.otros = [o for o in bots if o is not b]
        vistos = {}
        cuadro = 0
        atajo_pendiente = cfg.get("atajo")
        while t_ms < max_s * 1000 and g.current_screen == "partida":
            TECLAS.clear()
            for b in bots:
                b.entrada.soltar_todo()
            if g.pausa is not None:
                # La pausa: moverse un poco por el menú y volver.
                if rng.random() < 0.05:
                    tecla = rng.choice((pygame.K_DOWN, pygame.K_UP, pygame.K_ESCAPE, pygame.K_ESCAPE))
                    g._manejar_tecla(tecla)
            else:
                orden = list(bots)
                rng.shuffle(orden)
                for b in orden:
                    b.actualizar(DT)
            t0 = time.perf_counter()
            if g.transitions.is_idle():
                if g.pausa is not None:
                    g.pausa.actualizar(DT)
                else:
                    g._actualizar_partida(DT)
            g.transitions.update(g, DT)
            t1 = time.perf_counter()
            ms_act = (t1 - t0) * 1000
            resumen["ms_actualizar"] += ms_act
            cuadro += 1
            contexto = None
            if ms_act > LIMITE_LENTO_MS:
                contexto = _contexto(g)
                reg.lentos.append((round(ms_act, 1), "actualizar", contexto))
            if dibujar and cuadro % cada_dibujo == 0:
                t2 = time.perf_counter()
                g._dibujar()
                ms_dib = (time.perf_counter() - t2) * 1000
                resumen["ms_dibujar"] += ms_dib
                resumen["dibujos"] += 1
                if ms_dib > LIMITE_LENTO_MS:
                    reg.lentos.append((round(ms_dib, 1), "dibujar", contexto or _contexto(g)))
            if g.current_screen != "partida" or g.mision is None:
                break
            if g.mision.resultado:
                break
            if g.mision.fase != fase:
                fase = g.mision.fase
                resumen["fases"][str(fase)] = round(t_ms / 1000)
            if atajo_pendiente and not g.en_tutorial:
                atajo_pendiente = None
                m = g.mision
                for i, puerta in enumerate(m.puertas):
                    if not puerta["abierta"]:
                        m.abrir_puerta(None, i)
                for consola in m.consolas:
                    consola["progreso"] = 1.0
            if cuadro % 10 == 0:
                revisar_estado(g, mapa, reg, alcanzables, t_ms, vistos)
            t_ms += DT
        resumen["cuadros"] = cuadro
    except Exception:
        tb = traceback.format_exc()
        ultima = tb.strip().splitlines()
        donde = [l.strip() for l in ultima if l.strip().startswith("File")][-1:] or ["?"]
        reg.anotar("excepcion", (ultima[-1][:120], donde[0]), f"t={t_ms / 1000:.1f}s\n{tb}")
    if g is not None and g.mision is not None:
        resumen["resultado"] = g.mision.resultado or ("sin terminar" if t_ms >= max_s * 1000 else
                                                       g.current_screen)
        resumen["capturas"] = sum(j.veces_atrapado for j in g.jugadores)
        resumen["planos"] = g.nexus.planos if g.nexus is not None else None
        resumen["fase_final"] = g.mision.fase
        if resumen["resultado"] == "sin terminar":
            reg.anotar("sin_terminar", (g.mision.fase,),
                       f"{max_s} s sin terminar, en fase {g.mision.fase} "
                       f"(piezas {g.mision.piezas_entregadas}, planos {resumen['planos']}, "
                       f"vivos {sum(not j.eliminado for j in g.jugadores)})")
    resumen["duracion_s"] = round(t_ms / 1000)
    if reg.lentos:
        reg.anotar("cuadro_lento", ("partida",),
                   f"{len(reg.lentos)} cuadros > {LIMITE_LENTO_MS} ms; peor "
                   f"{max(reg.lentos)[0]} ms ({max(reg.lentos)[1]})")
    # Que no viaje la partida entera entre procesos.
    resumen["lentos"] = sorted(reg.lentos, reverse=True)[:5]
    if verbose:
        _imprimir_partida(resumen)
    return resumen


def _contexto(g):
    m = g.mision
    partes = [f"fase={m.fase if m else None}", f"aliens={len(g.aliens)}"]
    if g.eventos is not None and g.eventos.apagon:
        partes.append("apagon")
    paneles = [str((j.panel or {}).get("tipo")) for j in g.jugadores if j.panel]
    if paneles:
        partes.append("paneles=" + "+".join(paneles))
    return " ".join(partes)


def _imprimir_partida(r):
    cfg = r["cfg"]
    print(f"#{cfg['i']} {cfg['jugadores']}J {cfg['dificultad']:<11} {'+'.join(cfg['roles'])} "
          f"esquemas={cfg['esquemas']}{'' if cfg['mandos'] else ' (sin mandos)'}"
          f"{' asistida' if cfg.get('asistida') else ''}"
          f"{' atajo=' + cfg['atajo'] if cfg.get('atajo') else ''}: "
          f"{str(r['resultado']).upper()} en {r['duracion_s']} s | capturas {r['capturas']} "
          f"| fases {r['fases']}")
    for tipo, firma, detalle in r["problemas"]:
        print(f"   [{tipo}] {detalle.splitlines()[0] if tipo != 'excepcion' else detalle}")
    sys.stdout.flush()


def _trabajo(args):
    cfg, max_s, dibujar, cada, verbose = args
    try:
        return jugar(cfg, max_s, dibujar, cada, verbose)
    except Exception:
        return {"cfg": cfg, "resultado": "error del simulador", "duracion_s": 0, "fases": {},
                "capturas": 0, "lentos": [], "cuadros": 0, "ms_actualizar": 0, "ms_dibujar": 0,
                "dibujos": 0, "problemas": [("excepcion", "simulador", traceback.format_exc())]}


# -- Resumen ------------------------------------------------------------------------------------------

def resumir(resultados, segundos):
    por_tipo = Counter()          # partidas con al menos un problema de ese tipo
    ocurrencias = Counter()
    ejemplos = defaultdict(list)  # (tipo, firma) -> [partidas]
    detalle = {}
    resultados_por_cfg = defaultdict(Counter)
    lentos = []
    for r in resultados:
        cfg = r["cfg"]
        resultados_por_cfg[(cfg["jugadores"], cfg["dificultad"])][r["resultado"]] += 1
        tipos = set()
        for tipo, firma, det in r["problemas"]:
            tipos.add(tipo)
            ocurrencias[tipo] += 1
            ejemplos[(tipo, firma)].append(cfg["i"])
            detalle.setdefault((tipo, firma), det)
        por_tipo.update(tipos)
        lentos += [(ms, que, ctx, cfg["i"]) for ms, que, ctx in r.get("lentos", [])]
    total = len(resultados)
    print("\n" + "=" * 78)
    print(f"{total} partidas en {segundos:.0f} s")
    print("\nResultados por configuración (jugadores, dificultad):")
    for clave in sorted(resultados_por_cfg):
        print(f"   {clave[0]}J {clave[1]:<11} {dict(resultados_por_cfg[clave])}")
    cuadros = sum(r.get("cuadros", 0) for r in resultados) or 1
    dibujos = sum(r.get("dibujos", 0) for r in resultados) or 1
    print(f"\nTiempo medio por cuadro: actualizar "
          f"{sum(r.get('ms_actualizar', 0) for r in resultados) / cuadros:.2f} ms, dibujar "
          f"{sum(r.get('ms_dibujar', 0) for r in resultados) / dibujos:.2f} ms")
    print("\nProblemas (partidas con al menos uno / veces distintas):")
    for tipo in ("excepcion", "inalcanzable", "mision_imposible", "jugador_en_pared",
                 "alien_en_pared", "alien_atascado", "bot_trabado", "panel_sin_cerrar",
                 "estado_imposible", "sin_terminar", "cuadro_lento"):
        print(f"   {tipo:<18} {por_tipo[tipo]:>4} / {total:<4} ({ocurrencias[tipo]} distintas)")
    print("\nDetalle (cada problema distinto, con las partidas donde salió):")
    for (tipo, firma), partidas in sorted(ejemplos.items(), key=lambda kv: (kv[0][0], -len(kv[1]))):
        if tipo in ("cuadro_lento",):
            continue
        det = detalle[(tipo, firma)]
        lineas = det.splitlines()
        cabeza = lineas[0] if tipo != "excepcion" else " | ".join(lineas[-3:])
        print(f" - [{tipo}] x{len(partidas)} (partidas {partidas[:8]}{'...' if len(partidas) > 8 else ''})")
        print(f"     {cabeza[:300]}")
        if tipo == "excepcion":
            print("     " + "\n     ".join(lineas[-14:]))
    if lentos:
        lentos.sort(reverse=True)
        print("\nCuadros más lentos:")
        for ms, que, ctx, i in lentos[:12]:
            print(f"   {ms:>7.1f} ms {que:<10} partida {i}: {ctx}")
    return por_tipo


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("-n", "--partidas", type=int, default=24)
    p.add_argument("-j", "--jugadores", default="2,3,4", help="p. ej. 2,3,4 o 4")
    p.add_argument("-d", "--dificultad", default=",".join(DIFICULTADES_SIM),
                   help="facil, normal, dificil, inteligente (separadas por coma)")
    p.add_argument("--semilla", type=int, default=1)
    p.add_argument("--desde", type=int, default=0, help="índice de la primera partida")
    p.add_argument("--max-s", type=int, default=480, help="segundos simulados por partida")
    p.add_argument("--sin-dibujo", action="store_true", help="no llamar al dibujado")
    p.add_argument("--cada-dibujo", type=int, default=6, help="dibujar cada N cuadros")
    p.add_argument("-p", "--procesos", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    p.add_argument("--mapa", default=None, help="mapa a usar (por defecto el activo)")
    p.add_argument("-v", "--verbose", action="store_true", help="una línea por partida")
    a = p.parse_args()
    jugadores = tuple(int(x) for x in a.jugadores.split(","))
    for n in jugadores:
        if not 2 <= n <= 4:
            p.error("el juego es de 2 a 4 jugadores")
    difs = tuple(a.dificultad.split(","))
    for d in difs:
        if d not in DIFICULTADES_SIM:
            p.error(f"dificultad desconocida: {d}")
    cfgs = [configuracion(i, a.semilla, jugadores, difs, a.mapa)
            for i in range(a.desde, a.desde + a.partidas)]
    tareas = [(cfg, a.max_s, not a.sin_dibujo, a.cada_dibujo, False) for cfg in cfgs]
    inicio = time.perf_counter()
    resultados = []
    if a.procesos <= 1 or len(tareas) == 1:
        for t in tareas:
            r = _trabajo(t)
            _imprimir_partida(r) if a.verbose or len(tareas) == 1 else None
            resultados.append(r)
    else:
        import multiprocessing as mp
        with mp.get_context("spawn").Pool(a.procesos, maxtasksperchild=4) as pool:
            for r in pool.imap_unordered(_trabajo, tareas):
                if a.verbose:
                    _imprimir_partida(r)
                else:
                    print(".", end="", flush=True)
                resultados.append(r)
    resultados.sort(key=lambda r: r["cfg"]["i"])
    por_tipo = resumir(resultados, time.perf_counter() - inicio)
    graves = sum(por_tipo[t] for t in ("excepcion", "estado_imposible", "mision_imposible",
                                       "jugador_en_pared", "inalcanzable"))
    sys.exit(1 if graves else 0)


if __name__ == "__main__":
    main()
