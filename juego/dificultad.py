"""La dificultad de la partida: Fácil, Normal, Difícil o Inteligente.

Los números están en data/dificultad.py. El juego guarda un `Dificultad` en
`Game.dificultad` y cada parte le pregunta lo suyo con `valor(juego, nombre,
por_defecto)`: si la partida no tiene dificultad (las pruebas que arman el
juego a mano), se usa `por_defecto`: los números base del juego (Pesadilla).

Inteligente tiene un "director": cada 4 s mira cómo va el equipo (cuánto
avanzó la misión contra el reloj, la confianza en NEXUS, cuántas veces los
atraparon hace poco y cuántas vidas les quedan) y sube o baja un nivel
continuo entre Fácil (0) y Pesadilla (3). Los valores de en medio se
interpolan.
"""

from data.dificultad import (DIFICULTADES, AJUSTES, RITMO_MISION_S, VIDAS, UMBRAL_PLANOS, FLECHA, FUGA_MS,
                             VIDAS_INFINITAS, PRESENTAR_ALIENS, NIVEL_INICIAL, NIVEL_MIN, NIVEL_MAX, REVISAR_CADA_MS,
                             PASO_MAX, VENTANA_CAPTURAS_MS, NOMBRES_NIVEL)

NIVEL_FIJO = {"facil": 0.0, "normal": 1.0, "dificil": 2.0}


def de(juego):
    return getattr(juego, "dificultad", None)


def valor(juego, nombre, por_defecto):
    d = de(juego)
    return d.valor(nombre) if d is not None else por_defecto


def nombre_de(clave):
    return next((d["nombre"] for d in DIFICULTADES if d["clave"] == clave), clave)


def _interpolar(valores, nivel):
    """Valor en un nivel continuo (0 Fácil, 1 Normal, 2 Difícil, 3 Pesadilla).
    Por encima del último sigue la misma pendiente."""
    ultimo = len(valores) - 1
    if nivel <= 0:
        return valores[0]
    if nivel >= ultimo:
        return valores[ultimo] + (valores[ultimo] - valores[ultimo - 1]) * (nivel - ultimo)
    i = int(nivel)
    t = nivel - i
    return valores[i] + (valores[i + 1] - valores[i]) * t


class Dificultad:
    def __init__(self, clave):
        if clave not in [d["clave"] for d in DIFICULTADES]:
            raise ValueError(f"dificultad desconocida: {clave}")
        self.clave = clave
        self.nombre = nombre_de(clave)
        self.inteligente = clave == "inteligente"
        self.nivel = NIVEL_INICIAL if self.inteligente else NIVEL_FIJO.get(clave)
        self.nivel_max = self.nivel or 0.0      # hasta dónde llegó (para los resultados)
        self.reloj_ms = REVISAR_CADA_MS
        self.capturas = []                      # cuándo atraparon a alguien (ms de partida)
        self.tiempo_ms = 0

    # -- Lo que preguntan los demás -----------------------------------------------------

    def valor(self, nombre):
        return _interpolar(AJUSTES[nombre], self.nivel)

    @property
    def vidas(self):
        return VIDAS[self.clave]

    @property
    def vidas_infinitas(self):
        return self.clave in VIDAS_INFINITAS

    @property
    def presenta_aliens(self):
        """Si la primera vez que se ve cada alien sale la ventana que lo explica."""
        return self.clave in PRESENTAR_ALIENS

    @property
    def umbral_planos(self):
        return UMBRAL_PLANOS[self.clave]

    @property
    def flecha(self):
        """Si se dibuja la flecha al objetivo."""
        if self.inteligente:
            return self.nivel < 1.5
        return FLECHA[self.clave]

    @property
    def fuga_ms(self):
        """Cuánto tarda en salir solo de la celda (None = no sale solo)."""
        if self.inteligente:
            return {"Fácil": FUGA_MS["facil"], "Normal": FUGA_MS["normal"],
                    "Difícil": FUGA_MS["dificil"], "Pesadilla": FUGA_MS["pesadilla"]}.get(self.nombre_nivel())
        return FUGA_MS[self.clave]

    def nombre_nivel(self, nivel=None):
        """"Fácil", "Normal", "Difícil" o "Pesadilla" según el nivel."""
        nivel = self.nivel if nivel is None else nivel
        return next(nombre for tope, nombre in NOMBRES_NIVEL if nivel < tope)

    # -- El director (solo Inteligente) ----------------------------------------------------

    def al_atrapar(self):
        self.capturas.append(self.tiempo_ms)

    def actualizar(self, dt, juego):
        self.tiempo_ms += dt
        if not self.inteligente:
            return
        self.reloj_ms -= dt
        if self.reloj_ms > 0:
            return
        self.reloj_ms = REVISAR_CADA_MS
        antes = self.nombre_nivel()
        r = self.rendimiento(juego)
        self.nivel = max(NIVEL_MIN, min(NIVEL_MAX, self.nivel + r * PASO_MAX))
        self.nivel_max = max(self.nivel_max, self.nivel)
        despues = self.nombre_nivel()
        if despues != antes and hasattr(juego, "decir"):
            subio = [n for _, n in NOMBRES_NIVEL].index(despues) > \
                [n for _, n in NOMBRES_NIVEL].index(antes)
            juego.decir("dificultad_sube" if subio else "dificultad_baja", None, True)

    def rendimiento(self, juego):
        """De -1 (les va muy mal: aflojar) a 1 (les va muy bien: apretar)."""
        jugadores = [j for j in juego.jugadores if not getattr(j, "eliminado", False)] \
            or list(juego.jugadores)
        n = max(1, len(juego.jugadores))
        r = 0.0
        # El ritmo de la misión (no hay límite de tiempo): ¿van más rápido o más
        # lento que una partida bien jugada (RITMO_MISION_S)?
        progreso = progreso_mision(getattr(juego, "mision", None))
        if progreso is not None:
            usado = getattr(juego, "tiempo_jugado_ms", 0) / (RITMO_MISION_S * 1000)
            r += max(-1.2, 1.2 * (progreso - usado / 0.85))
        # NEXUS.
        red = getattr(juego, "nexus", None)
        if red is not None:
            verde, rojo = red.barras()
            r += 0.4 * (verde - rojo)
        # Capturas recientes y vidas.
        self.capturas = [t for t in self.capturas if self.tiempo_ms - t <= VENTANA_CAPTURAS_MS]
        r -= 0.6 * len(self.capturas) / n
        presos = sum(1 for j in jugadores if j.preso)
        r -= 0.3 * presos / n
        maximo = max(1, getattr(jugadores[0], "vidas_max", self.vidas)) if jugadores else 1
        vidas = sum(getattr(j, "vidas", maximo) for j in juego.jugadores) / (n * maximo)
        r += 0.3 * (vidas - 0.7)
        return max(-1.0, min(1.0, r))


def progreso_mision(mision):
    """Cuánto llevan de la misión, de 0 a 1 (None si el mapa no tiene misión)."""
    if mision is None or not getattr(mision, "activa", False):
        return None
    if mision.resultado == "victoria" or mision.fase == "huida":
        return 1.0
    if mision.fase == "prision":
        return 0.05
    if mision.fase == "sabotaje":
        hechas = sum(c["progreso"] >= 1 for c in mision.consolas)
        return 0.15 + 0.35 * hechas / max(1, len(mision.consolas))
    if mision.fase == "capsula":
        return min(0.95, 0.5 + 0.08 * mision.piezas_entregadas + 0.25 * mision.reparacion)
    return 0.0
