"""Logros de la partida: quién consigue qué y cuándo.

El árbol (Estructuras/arbol_logros.py, datos en data/logros.py) solo sabe
marcar logros. Este módulo decide CUÁNDO se consigue cada uno, de dos formas:

- Avisos directos: el código donde pasa la cosa llama `logro(juego, clave,
  jugador)` (rescatar, subir una prueba, hackear, entrar a NEXUS...).
- Revisando cada frame (`actualizar`): lo que es un estado y no un momento
  (30 s en sigilo, ver a todos los tipos de alien, un alien frenado por un sello,
  el cambio de fase, que vuelva la luz...).

Se crea uno nuevo en cada partida, así que los logros se reinician solos.
Al conseguir uno sale un aviso abajo al centro de la pantalla
(screens/logros.py) y en el menú de pausa se ve el árbol completo.
"""

import math

from Estructuras.arbol_logros import ArbolLogros
from data.logros import ARBOL_LOGROS

DURACION_AVISO_MS = 3500
DURACION_AVISO_EN_COLA_MS = 2000     # si hay varios esperando, pasan más rápido
MS_PASOS_DE_GATO = 30000
DISTANCIA_SHHH = 100
DISTANCIA_VER_ALIEN = 450
DISTANCIA_OJOS = 600          # a esta distancia se le ven los ojos a la Sombra
MS_ELECTRICISTA = 30000
FASES_SIN_RASTRO = ("sabotaje", "capsula")
MS_SIGILOSO = 3000            # caminar en sigilo este rato (o esconderse) abre la rama
ESPERA_PADRE_MS = 2500        # un hijo que llega antes que su padre espera esto


def logro(juego, clave, jugador=None):
    """Avisa que alguien consiguió un logro. Si la partida no tiene gestor de
    logros (las pruebas que arman el juego a mano), no pasa nada."""
    gestor = getattr(juego, "logros", None)
    if gestor is not None:
        return gestor.conseguir(clave, jugador)
    return []


def _distancia(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


class GestorLogros:
    def __init__(self, juego):
        self.juego = juego
        self.arbol = ArbolLogros(ARBOL_LOGROS)
        self.avisos = []                 # [nodo, ms restantes]; se muestra el primero
        self.sigilo_ms = {}              # id(jugador) -> ms caminando en sigilo
        self.capturas_total = 0
        self.capturas_fase = 0
        self.fase = None
        self.puerta_vista = False
        self.apagon = False
        self.apagon_ms = 0
        self.tipos_vistos = set()
        self.cansados = set()            # id de los aliens que están cansados ahora
        # Un logro que llega antes que su padre (casi siempre en el mismo
        # instante) espera un momento a que llegue el padre: [clave, rol, ms].
        self.pendientes = []

    # -- Conseguir -----------------------------------------------------------------------

    def conseguir(self, clave, jugador=None, esperar=True):
        quien = getattr(jugador, "rol", None) if jugador is not None else None
        nodo = self.arbol.buscar(clave)
        if nodo is None or nodo.obtenido:
            return []
        if esperar and self.arbol.falta_un_padre(clave):
            if all(p[0] != clave for p in self.pendientes):
                self.pendientes.append([clave, quien, ESPERA_PADRE_MS])
            return []
        return self._dar(clave, quien)

    def _dar(self, clave, quien):
        nuevos = self.arbol.conseguir(clave, quien)
        for nodo in nuevos:
            self.avisos.append([nodo, DURACION_AVISO_MS])
        if nuevos and hasattr(self.juego, "sonar"):
            self.juego.sonar("logro", 0.6)
        return nuevos

    def _pendientes(self, dt, todos=False):
        """Da los que ya tienen a su padre; los que esperaron demasiado (o
        `todos`, al terminar la partida), igual, marcando el camino."""
        for pendiente in list(self.pendientes):
            clave, quien, _ = pendiente
            pendiente[2] -= dt
            if self.tiene(clave):
                self.pendientes.remove(pendiente)
            elif todos or pendiente[2] <= 0 or not self.arbol.falta_un_padre(clave):
                self.pendientes.remove(pendiente)
                self._dar(clave, quien)

    def tiene(self, clave):
        nodo = self.arbol.buscar(clave)
        return nodo is not None and nodo.obtenido

    # -- Lo que avisa el juego -----------------------------------------------------------

    def al_atrapar(self, jugador):
        self.capturas_total += 1
        self.capturas_fase += 1

    def al_terminar(self):
        """Fin de la ronda: los logros de escapar."""
        mision = getattr(self.juego, "mision", None)
        if mision is None or mision.resultado != "victoria":
            return
        self.conseguir("libertad")
        if not any(getattr(j, "eliminado", False) for j in self.juego.jugadores):
            self.conseguir("todos_a_bordo")
        if self.capturas_total == 0:
            self.conseguir("nadie_me_vio")
        self._pendientes(0, todos=True)

    # -- Cada frame ----------------------------------------------------------------------

    def actualizar(self, dt):
        if self.avisos:
            self.avisos[0][1] -= dt
            if len(self.avisos) > 1:
                self.avisos[0][1] = min(self.avisos[0][1], DURACION_AVISO_EN_COLA_MS)
            if self.avisos[0][1] <= 0:
                self.avisos.pop(0)

        juego = self.juego
        if getattr(juego, "en_tutorial", False):
            return
        self.conseguir("despertar")
        self._pendientes(dt)
        self._mision()
        self._luz(dt)
        self._jugadores(dt)
        self._aliens()
        self._sombra()

    def _mision(self):
        mision = getattr(self.juego, "mision", None)
        if mision is None or not mision.activa:
            return
        if mision.puerta is not None and mision.puerta_abierta and not self.puerta_vista:
            self.puerta_vista = True
            quien = getattr(mision, "abrio", None)
            self.conseguir("codigo_roto", quien)
            if quien is not None and getattr(mision, "codigos_fallidos", 0) == 0:
                self.conseguir("a_la_primera", quien)
        if self.fase is not None and mision.fase != self.fase:
            if self.fase == "sabotaje":
                self.conseguir("sin_rumbo")
            if self.capturas_fase == 0 and self.fase in FASES_SIN_RASTRO:
                self.conseguir("sin_rastro")
            self.capturas_fase = 0
        self.fase = mision.fase
        from misiones.mision import PIEZAS_NECESARIAS
        if mision.piezas_entregadas >= PIEZAS_NECESARIAS:
            self.conseguir("chatarrero")

    def _luz(self, dt):
        eventos = getattr(self.juego, "eventos", None)
        if eventos is None:
            return
        if eventos.apagon:
            if not self.apagon:
                self.conseguir("a_oscuras")
            self.apagon = True
            self.apagon_ms += dt
        elif self.apagon:
            self.apagon = False
            quien = getattr(eventos, "restauro", None)
            self.conseguir("hagase_la_luz", quien)
            if self.apagon_ms < MS_ELECTRICISTA:
                self.conseguir("electricista", quien)
            self.apagon_ms = 0
            # La Sombra en ese apagón (Game._actualizar_sombra lo anota al
            # sacarla): ¿quien prendió la caja la tenía cerca? ¿alcanzó a alguien?
            info = getattr(self.juego, "sombra_al_volver_la_luz", None)
            if info:
                if info.get("cerca"):
                    self.conseguir("luz_salvadora", quien)
                if not info.get("alcanzo"):
                    self.conseguir("sin_miedo", quien)
                self.juego.sombra_al_volver_la_luz = None

    def _jugadores(self, dt):
        aliens = getattr(self.juego, "aliens", ())
        for jugador in self.juego.jugadores:
            if jugador.escondido and not jugador.eliminado and jugador.preso is None:
                self.conseguir("sigiloso", jugador)
            if jugador.eliminado or jugador.preso is not None or jugador.escondido:
                continue
            camina_en_sigilo = jugador.sigilo and jugador.personaje.moviendose
            if camina_en_sigilo:
                ms = self.sigilo_ms.get(id(jugador), 0) + dt
                self.sigilo_ms[id(jugador)] = ms
                if ms >= MS_SIGILOSO:
                    self.conseguir("sigiloso", jugador)
                if ms >= MS_PASOS_DE_GATO:
                    self.conseguir("pasos_de_gato", jugador)
            centro = jugador.hitbox.center
            for alien in aliens:
                d = _distancia(alien.centro, centro)
                # El Cambiaformas cuenta cuando se le ve como es (disfrazado
                # es un prisionero más).
                # A la Sombra, alumbrada (a oscuras solo se le ven los ojos).
                if (d <= DISTANCIA_VER_ALIEN and not getattr(alien, "disfrazado", False)
                        and getattr(alien, "se_ve", True)):
                    self.tipos_vistos.add(alien.tipo)
                    self.conseguir("primer_encuentro", jugador)
                    if alien.tipo == "cambiaformas":
                        self.conseguir("cara_a_cara", jugador)
                if (alien.tipo == "ciego" and d <= DISTANCIA_SHHH and camina_en_sigilo
                        and alien.objetivo is None
                        and alien.accion not in ("PERSEGUIR", "ATRAPAR", "REVISAR_ESCONDITE",
                                                 "DESCANSAR")):
                    self.conseguir("shhh", jugador)
        # Todos los tipos que hay en la partida, el Cambiaformas y la Sombra
        # incluidos (la Sombra solo está en `aliens` en los apagones).
        tipos = {a.tipo for a in aliens}
        for unico in (getattr(self.juego, "cambiaformas", None), getattr(self.juego, "sombra", None)):
            if unico is not None:
                tipos.add(unico.tipo)
        if len(tipos) >= 2 and tipos <= self.tipos_vistos:
            self.conseguir("conoce_a_tu_enemigo")

    def _sombra(self):
        """"Ojos en la oscuridad": alguien tiene a la Sombra en su campo de
        visión (a oscuras se le ven los ojos). "No parpadees" lo avisa
        sombra.py; "Luz salvadora" y "Sin miedo" se dan en `_luz`."""
        juego = self.juego
        sombra = getattr(juego, "sombra", None)
        if sombra is None or sombra not in getattr(juego, "aliens", ()) or sombra.oculta \
                or self.tiene("ojos_en_la_oscuridad"):
            return
        from juego import vision
        obstaculos = vision.obstaculos(juego.mundo, getattr(juego, "puertas_dobles", ()),
                                       getattr(juego, "compuertas", ()))
        for jugador in juego.jugadores:
            if (jugador.preso is not None or jugador.escondido or getattr(jugador, "eliminado", False)
                    or _distancia(jugador.hitbox.center, sombra.centro) > DISTANCIA_OJOS):
                continue
            if vision.campo_de(jugador.hitbox.center, obstaculos).ve_a(sombra.hitbox):
                self.conseguir("ojos_en_la_oscuridad", jugador)
                return

    def _aliens(self):
        juego = self.juego
        vivos = [j for j in juego.jugadores if not j.eliminado and j.preso is None]
        for alien in getattr(juego, "aliens", ()):
            if alien.cansado and id(alien) not in self.cansados:
                self.cansados.add(id(alien))
                if alien.tipo == "cazador" and vivos:
                    cerca = min(vivos, key=lambda j: _distancia(j.hitbox.center, alien.centro))
                    if _distancia(cerca.hitbox.center, alien.centro) <= 500:
                        self.conseguir("agotalo", cerca)
            elif not alien.cansado:
                self.cansados.discard(id(alien))
        bloqueos = getattr(getattr(juego, "mundo", None), "bloqueos_alien", None)
        if bloqueos:
            for alien in getattr(juego, "aliens", ()):
                if alien.hitbox.inflate(16, 16).collidelist(bloqueos) != -1:
                    forjador = next((j for j in juego.jugadores if j.rol == "Forjador"), None)
                    self.conseguir("por_aqui_no", forjador)
                    break
