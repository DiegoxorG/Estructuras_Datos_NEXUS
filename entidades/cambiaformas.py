"""El Cambiaformas: un alien único que se disfraza de prisionero.

Camina por la nave con la apariencia de uno de los prisioneros de NEXUS
(npcs.py), escoge a una presa y la sigue de lejos. Cuando la presa está cerca
y sola, se revela (susto: grito y temblor de pantalla) y corre muy rápido un
rato. Si no la atrapa, huye a donde nadie lo vea, se vuelve a disfrazar (de
cualquier prisionero) y vuelve a intentarlo con la misma presa: es
persistente. También revisa los escondites donde vio meterse a su presa.

Es más listo que los demás aliens:
- escoge a la presa más sola y no ataca si tiene un compañero al lado;
- sabe, cada tanto, dónde está su presa aunque no la vea (la acecha);
- usa los rumores de sus cuentas falsas en NEXUS como carnada: se queda
  disfrazado junto al lugar del rumor y espera a quien vaya a verificarlo;
- no se transforma mientras un jugador lo está mirando.

Pistas para descubrirlo (no es injusto): no habla, su nombre falla de vez en
cuando, puede haber dos prisioneros con el mismo nombre, el Escaneo y la
Sintonía lo marcan como alien, y los prisioneros verdes avisan si lo ven raro.

El hackeo del Tecnomante lo aturde, le quita el disfraz y lo hace huir. Si lo
exponen en NEXUS (las 3 pruebas del caso, infiltrado.py) no se puede
disfrazar por un rato.

Su comportamiento es un árbol binario de decisión, como el de los demás
aliens (data/comportamiento_cambiaformas.py); este archivo responde sus
preguntas (percibir) y ejecuta sus hojas (_ejecutar).
"""

import math
import random

import pygame

from entidades.alien import Alien, DISTANCIA_ATRAPAR, DISTANCIA_REVISAR, DURACION_DESCANSO_MS
from Estructuras.arbol_comportamiento import ArbolComportamiento
from data.comportamiento_cambiaformas import ARBOL_CAMBIAFORMAS
from data.npcs import (DANIO_SABOTAJE, DISTANCIA_REVELARSE, DISTANCIA_COMPANIA, VISION,
                       RAFAGA_MS, PISTA_PRESA_MS, RECUERDA_ESCONDITE_MS, HUIDA_MAX_MS,
                       EXPUESTO_MS, DESCANSO_TRAS_FALLAR_MS, GLITCH_CADA_MS, GLITCH_DURA_MS,
                       TRANSFORMARSE_MS, ESPERA_INICIAL_MS, ENFRIAMIENTO_CAZA_MS,
                       TRAMPAS, PRIMERA_TRAMPA_MS, TRAMPA_CADA_MS, DESENMASCARADO_MS,
                       DISTANCIA_SEGUIR_CF, TRAICION_SOLO_MS, RADIO_SABOTAJE,
                       SUSURRO_RADIO, SUSURRO_CADA_MS, MANADA_MS,
                       ESTUDIO_NECESARIO_MS, RADIO_ESTUDIO, DISTANCIA_PASADA, PASADA_MAX_MS,
                       RONDA_MS, RONDA_DISTANCIA, DE_ESPALDAS, ABURRIRSE_MS, ALEJARSE_CALMA_MS,
                       OLVIDA_TRAS_FALLAR, CALMA_TRAS_FALLAR_MS)
from data.nexus import NOMBRE_LUGAR
from misiones.logros import logro
from entidades import npcs
from Movimiento.Personaje import DireccionSuave, ANGULO_DIRECCION
from juego import dificultad
GLITCH = "#%&?!@*"


_VECTOR_DIRECCION = {
    "north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0),
    "north-east": (0.707, -0.707), "north-west": (-0.707, -0.707),
    "south-east": (0.707, 0.707), "south-west": (-0.707, 0.707),
}


def _d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


class Cambiaformas(Alien):
    def __init__(self, juego, numero, apariencias, identidad, punto, rng=None):
        """`apariencias`: {usuario: Apariencia} de los prisioneros que puede
        imitar; `identidad`: el usuario que usa de base (el del caso)."""
        super().__init__(numero, [punto], ArbolComportamiento(ARBOL_CAMBIAFORMAS), "cambiaformas")
        self.nombre = "Cambiaformas"
        self.juego = juego
        self.rng = rng or random.Random()
        self.apariencias = apariencias
        self.identidad = identidad
        self.apariencia = apariencias.get(identidad) or next(iter(apariencias.values()), None)
        self.disfrazado = self.apariencia is not None
        self.presa = None
        self.punto_presa = None          # dónde cree que está su presa
        self.pista_ms = 0
        self.vio_esconderse_ms = 10 ** 9
        self.huida_ms = 0
        self.huir_al_despertar = False
        self.rafaga_ms = 0
        self.transformando_ms = 0
        self._giro = DireccionSuave()       # hacia dónde mira el sprite revelado
        self.calma_ms = int(self._ajuste("cf_espera_ms", ESPERA_INICIAL_MS))  # al empezar se toma su tiempo
        self.revisando = None               # el casillero que está revisando
        self.expuesto_ms = 0
        self.punto_huida = None
        self.ruta = []                   # para merodear (npcs.caminar)
        self.espera_ms = 0
        self.glitch_ms = self.rng.uniform(0, GLITCH_CADA_MS)
        self._resto = [0.0, 0.0]
        self.siguiendo = None            # el jugador que se lo lleva creyendo que es un prisionero
        self.siguiendo_solo_ms = 0
        self.burbuja, self.burbuja_ms = None, 0
        self.trampa_ms = PRIMERA_TRAMPA_MS * self._ajuste("cf_trampas", 1.0)
        self.susurro_ms = 0
        self.manada_ms = 0
        self._manada_ahora = False
        # Estudiar a la presa antes de atacar (no es impulsivo).
        self.conocimiento = {}           # jugador -> ms que lo ha visto de cerca
        self.necesario = {}              # jugador -> ms que necesita para atacarlo (al azar)
        self.modo = "ronda"              # "ronda" (lejos) o "pasada" (se acerca a mirarla)
        self.modo_ms = 0
        self.punto_ronda = None
        self.acompanada_ms = 0           # cuánto lleva viendo que la presa no se separa
        self.yendose_a = None            # se aburrió: a dónde se va antes de merodear
        self._estudiando = False
        self._sola = False
        # Para los resultados.
        self.revelaciones = 0
        self.capturas = 0
        self.sabotajes = 0

    # -- Lo que ven los demás -------------------------------------------------------

    def _ajuste(self, nombre, por_defecto):
        """Lo que dice la dificultad (dificultad.py); sin ella, los números base."""
        return dificultad.valor(self.juego, nombre, por_defecto)

    def _calma_tras_cazar(self):
        return int(self._ajuste("cf_calma_ms", ENFRIAMIENTO_CAZA_MS))

    @property
    def alcance_vision(self):
        return 0          # sin cono: nadie tiene que ver por dónde mira

    def visible_para(self, jugador):
        return (_d(self.centro, jugador.hitbox.center) <= VISION * self.ajuste_vision
                and self.juego.mundo.linea_libre(self.centro, jugador.hitbox.center))

    def _alguien_lo_ve(self):
        return any(self.visible_para(j) for j in self.juego.jugadores
                   if not j.preso and not getattr(j, "eliminado", False))

    # -- Presa --------------------------------------------------------------------------

    def _validos(self, jugadores):
        return [j for j in jugadores if j.cazable and not getattr(j, "eliminado", False)]

    def _elegir_presa(self, jugadores):
        """La más sola: lejos de sus compañeros. A igualdad, la más cercana."""
        validos = self._validos(jugadores)
        if not validos:
            return None

        def puntaje(j):
            otros = [o for o in validos if o is not j]
            soledad = min((_d(j.hitbox.center, o.hitbox.center) for o in otros), default=1500)
            return min(soledad, 1500) - 0.35 * _d(j.hitbox.center, self.centro)
        return max(validos, key=puntaje)

    def _presa_valida(self):
        p = self.presa
        return p is not None and not p.preso and not getattr(p, "eliminado", False) \
            and p.puede_moverse

    # -- Percepción (las preguntas del árbol) ------------------------------------------------

    def percibir(self, jugadores, mundo, escondites=()):
        s = self.siguiendo
        if s is not None and (s.preso or getattr(s, "eliminado", False) or not self.disfrazado):
            self.siguiendo = None
        if not self._presa_valida():
            self.presa = None
            self.objetivo = None
        # Si está cebando con una suplantación, el que llegue solo es su presa.
        red = getattr(self.juego, "nexus", None)
        trampa = red.trampa_activa() if red is not None else None
        if (trampa is not None and self.presa is None and self.disfrazado
                and self.siguiendo is None and self.descanso_ms == 0):
            llegando = [j for j in self._validos(jugadores) if not j.escondido
                        and _d(j.hitbox.center, trampa.lugar) < 350 and self.visible_para(j)]
            if llegando:
                self.presa = min(llegando, key=lambda j: _d(j.hitbox.center, self.centro))
                self.calma_ms = 0
                # Era su plan: a este lo atacó sin tener que estudiarlo más.
                self.conocimiento[self.presa] = self._necesario(self.presa)
        if (self.presa is None and self.descanso_ms == 0 and self.huida_ms == 0
                and self.calma_ms == 0):
            self.presa = self._elegir_presa(jugadores)
            self.pista_ms = 0
            if self.presa is not None:
                self.yendose_a = None      # ya volvió a cazar
        presa = self.presa
        ve_presa = False
        if presa is not None:
            if presa.escondido:
                if self.visible_para(presa) or _d(presa.hitbox.center, self.centro) < 220:
                    self.vio_esconderse_ms = 0
            elif self.visible_para(presa):
                ve_presa = True
                self.punto_presa = presa.hitbox.center
                self.vio_esconderse_ms = 10 ** 9
            elif self.pista_ms <= 0:
                # Es persistente: cada tanto "sabe" dónde está.
                self.punto_presa = presa.hitbox.center
                self.pista_ms = PISTA_PRESA_MS

        # Huyendo sin disfraz, si alguien solo se le pone al alcance, lo ataca.
        if (self.huida_ms > 0 and not self.disfrazado and self.descanso_ms == 0
                and self.calma_ms == 0):
            cerca = [j for j in self._validos(jugadores)
                     if not j.escondido and _d(j.hitbox.center, self.centro) <= DISTANCIA_REVELARSE * 0.8
                     and self.visible_para(j)]
            if cerca:
                self.presa = min(cerca, key=lambda j: _d(j.hitbox.center, self.centro))
                presa = self.presa
                self.punto_presa = presa.hitbox.center
                ve_presa = True
                self.huida_ms = 0
                self.rafaga_ms = RAFAGA_MS

        # Escondite. Mientras revisa uno (minijuego andando) no lo suelta: antes
        # se le borraba cada frame y, sin disfraz, se ponía a huir a mitad del
        # minijuego, se alejaba y volvía una y otra vez.
        revisando = self.revisando
        if (revisando is not None and presa is not None and presa.escondido
                and revisando.get("ocupante") is presa):
            self.escondite_objetivo = revisando
        else:
            if revisando is not None and presa is not None and not presa.escondido \
                    and self.visible_para(presa):
                # Salió del casillero en su cara: ataca.
                self.rafaga_ms = RAFAGA_MS
            self.revisando = None
            self.escondite_objetivo = None
            if presa is not None and presa.escondido and self.vio_esconderse_ms < RECUERDA_ESCONDITE_MS:
                esc = presa.escondite
                if esc is not None and self.escondite_disponible(esc, self):
                    self.escondite_objetivo = esc

        # "Revelado" es estar atacando: sin disfraz y con la carrera andando.
        revelado = not self.disfrazado and self.rafaga_ms > 0
        if (not self.disfrazado and not revelado and self.huida_ms == 0
                and self.descanso_ms == 0 and self.expuesto_ms == 0
                and self.escondite_objetivo is None):
            self._empezar_huida()      # sin disfraz y sin atacar: a esconderse
        distancia = _d(self.centro, presa.hitbox.center) if presa is not None else 1e9
        sola = presa is not None and not any(
            o is not presa and not o.preso and _d(o.hitbox.center, presa.hitbox.center) < DISTANCIA_COMPANIA
            for o in self.juego.jugadores)

        self.objetivo = presa if revelado and ve_presa else None
        self._manada_ahora = (self.disfrazado and ve_presa and not sola
                              and distancia <= DISTANCIA_REVELARSE)
        self._estudiando = (presa is not None and self.disfrazado and ve_presa
                            and distancia <= RADIO_ESTUDIO)
        self._sola = sola
        la_conoce = presa is not None and self.conocimiento.get(presa, 0) >= self._necesario(presa)
        momento = (la_conoce and ve_presa and sola and distancia <= DISTANCIA_REVELARSE
                   and (self.expuesto_ms > 0 or self.desprevenida(presa)))
        return {
            "recuperandose": self.descanso_ms > 0,
            "huyendo": self.huida_ms > 0,
            "lo_escoltan": self.siguiendo is not None,
            "revelado": revelado and presa is not None and not presa.escondido,
            "presa_al_alcance": (revelado and ve_presa and distancia <= DISTANCIA_ATRAPAR),
            "presa_escondida": self.escondite_objetivo is not None,
            "presa_cerca": (self.disfrazado or self.expuesto_ms > 0) and momento,
            "tiene_presa": presa is not None,
            "se_aburrio": presa is not None and self.acompanada_ms >= ABURRIRSE_MS,
            "toca_estudiar": self.modo == "pasada",
            "hay_cebo": self._cebo() is not None,
        }

    def _cebo(self):
        """Dónde esperar: el lugar de su suplantación en NEXUS, o el de un
        rumor sin desmentir de sus cuentas falsas."""
        red = getattr(self.juego, "nexus", None)
        if red is None:
            return None
        trampa = red.trampa_activa()
        if trampa is not None:
            return trampa.lugar
        activos = red.rumores_activos()
        return activos[0].lugar if activos else None

    # -- Frame ------------------------------------------------------------------------------

    def actualizar(self, dt, mundo, jugadores, al_atrapar=None, escondites=(), al_revisar=None):
        self.pista_ms = max(0, self.pista_ms - dt)
        self.calma_ms = max(0, self.calma_ms - dt)
        self.vio_esconderse_ms += dt
        self.expuesto_ms = max(0, self.expuesto_ms - dt)
        self.huida_ms = max(0, self.huida_ms - dt)
        self.glitch_ms -= dt
        if self.glitch_ms < -GLITCH_DURA_MS:
            self.glitch_ms = GLITCH_CADA_MS * self.rng.uniform(0.7, 1.3)
        antes_descanso = self.descanso_ms
        antes = self.hitbox.center
        super().actualizar(dt, mundo, jugadores, al_atrapar, escondites, al_revisar)
        if antes_descanso > 0 and self.descanso_ms == 0 and self.huir_al_despertar:
            self.huir_al_despertar = False
            self._empezar_huida()
        dx, dy = self.hitbox.centerx - antes[0], self.hitbox.centery - antes[1]
        # Merodeando camina con npcs.caminar, que no gira al alien: el sprite
        # revelado mira hacia donde camina (sin temblar, ver DireccionSuave).
        self._giro.actualizar(dx, dy)
        self.moviendose = self._giro.moviendose
        if self.moviendose:
            self.angulo = ANGULO_DIRECCION[self._giro.direccion]
        if self.apariencia is not None:
            self.apariencia.animar(dx, dy, dt)
        self.burbuja_ms = max(0, self.burbuja_ms - dt)
        self._aprender(dt)
        self._susurrar(dt)
        if self._manada_ahora:
            self.manada_ms += dt
            # Solo si ya lo vieron como es: antes, nadie sabe que "no se atrevió".
            logros = getattr(self.juego, "logros", None)
            if self.manada_ms >= MANADA_MS and logros is not None and logros.tiene("cara_a_cara"):
                logro(self.juego, "en_manada")
        self.trampa_ms -= dt
        if self.trampa_ms <= 0:
            self.trampa_ms = self.rng.uniform(*TRAMPA_CADA_MS) * self._ajuste("cf_trampas", 1.0)
            self.suplantar()

    def _aprender(self, dt):
        """Lo que estudia de su presa y la paciencia que le tiene al grupo."""
        self.modo_ms = max(0, self.modo_ms - dt)
        presa = self.presa
        if presa is None:
            self.acompanada_ms = 0
            return
        if self._estudiando:
            self.conocimiento[presa] = self.conocimiento.get(presa, 0) + dt
        # Si la presa nunca se separa del grupo, se aburre de mirarla.
        if self.disfrazado and not self._sola and _d(presa.hitbox.center, self.centro) <= VISION:
            self.acompanada_ms += dt
        elif self._sola:
            self.acompanada_ms = max(0, self.acompanada_ms - dt)

    def _necesario(self, jugador):
        if jugador not in self.necesario:
            self.necesario[jugador] = (self.rng.uniform(*ESTUDIO_NECESARIO_MS)
                                       * self._ajuste("cf_estudio", 1.0))
        return self.necesario[jugador]

    def desprevenida(self, jugador):
        """Cuando menos se lo espera: ocupada (celular, nota, panel, una consola
        o la cápsula) o de espaldas a él."""
        if jugador.ocupado or getattr(jugador, "progreso", None) is not None:
            return True
        mira = getattr(getattr(jugador, "personaje", None), "direccion", None)
        vector = _VECTOR_DIRECCION.get(mira)
        if vector is None:
            return False
        dx, dy = self.centro[0] - jugador.hitbox.centerx, self.centro[1] - jugador.hitbox.centery
        d = math.hypot(dx, dy) or 1
        coseno = (dx * vector[0] + dy * vector[1]) / d
        return coseno < math.cos(math.radians(DE_ESPALDAS))

    def _olvidar(self, jugador, parte):
        """Después de atacar (o fallar), tiene que volver a estudiarla."""
        if jugador is None:
            return
        self.conocimiento[jugador] = self.conocimiento.get(jugador, 0) * (1 - parte)
        self.necesario.pop(jugador, None)
        self.modo, self.modo_ms = "ronda", self.rng.uniform(*RONDA_MS)
        self.punto_ronda = None
        self.acompanada_ms = 0

    def _susurrar(self, dt):
        """Disfrazado, al que tiene cerca le llega un susurro (sin saber de quién)."""
        self.susurro_ms = max(0, self.susurro_ms - dt)
        if not self.disfrazado or self.susurro_ms > 0:
            return
        if any(_d(j.hitbox.center, self.centro) <= SUSURRO_RADIO for j in self._vivos()):
            self.susurro_ms = SUSURRO_CADA_MS
            if hasattr(self.juego, "sonar"):
                self.juego.sonar("susurro", 0.4)

    def suplantar(self):
        """Publica en NEXUS con la cuenta del prisionero que está imitando, para
        atraer a alguien a un lugar y emboscarlo ahí."""
        red = getattr(self.juego, "nexus", None)
        if (red is None or not self.disfrazado or self.apariencia is None
                or self.siguiendo is not None or self.presa is not None
                or red.trampa_activa() is not None):
            return None
        opciones = []
        for tipo in ("terminal", "escondite", "consola", "panel"):
            opciones += [(tipo, p) for p in red._lugares(tipo)]
        vivos = self._vivos()
        # Un lugar lejos de los jugadores (que tengan que caminar hasta allá).
        opciones = [o for o in opciones
                    if all(_d(o[1], j.hitbox.center) > 400 for j in vivos)] or opciones
        if not opciones:
            return None
        tipo, lugar = self.rng.choice(opciones)
        nombre = NOMBRE_LUGAR.get(tipo, "la nave")
        texto = self.rng.choice(TRAMPAS).format(lugar=nombre)
        return red.publicar_trampa(self.apariencia.usuario, texto, lugar, nombre)

    def _ejecutar(self, accion, dt, factor, mundo, al_atrapar, al_revisar=None):
        presa = self.presa
        if accion == "DESCANSAR":
            return
        if accion == "HUIR":
            self._huir(dt, factor, mundo)
            return
        if accion == "REVELARSE":
            self._revelarse()
            return
        if accion == "SEGUIR":
            self._seguir(dt, factor, mundo)
            return
        if accion == "PERSEGUIR":
            if self.transformando_ms > 0:
                # El instante del susto: se transforma ahí mismo y no se mueve.
                self.transformando_ms -= dt
                return
            self.rafaga_ms -= dt
            if self.rafaga_ms <= 0:
                # Se le acabó la carrera: huye y vuelve a intentarlo después.
                self.rafaga_ms = 0
                if presa is not None and not presa.preso:
                    logro(self.juego, "cara_a_cara", presa)      # (se le reveló enfrente)
                    logro(self.juego, "sobreviviente", presa)
                # Falló: ahora la presa lo conoce a él. Tiene que volver a
                # estudiarla y deja pasar un rato antes de intentarlo.
                self._olvidar(presa, OLVIDA_TRAS_FALLAR)
                self.calma_ms = max(self.calma_ms, CALMA_TRAS_FALLAR_MS)
                self.descanso_ms = DESCANSO_TRAS_FALLAR_MS
                self.huir_al_despertar = True
                return
            destino = presa.hitbox.center if self.objetivo is presa else self.punto_presa
            if destino is not None:
                self._ir_por_camino(destino, self.datos["vel_perseguir"] * factor, dt, mundo)
            return
        if accion == "ATRAPAR":
            self.objetivo = presa
            if al_atrapar is not None:
                al_atrapar(presa, self)
            self.capturas += 1
            self._olvidar(presa, 1.0)
            self.descanso_ms = DURACION_DESCANSO_MS
            self.huir_al_despertar = True
            self.rafaga_ms = 0
            self.presa = None
            self.calma_ms = self._calma_tras_cazar()   # satisfecho... por un rato
            return
        if accion == "REVISAR_ESCONDITE":
            esc = self.escondite_objetivo
            if _d(self.centro, esc["rect"].center) > DISTANCIA_REVISAR:
                self._ir_por_camino(esc["rect"].center, self.datos["vel_investigar"] * factor, dt, mundo)
                return
            # Llegó: se muestra como es y se queda quieto frente al casillero
            # hasta que termine el minijuego (rendirse / entrar_al_escondite).
            self.disfrazado = False
            self.rafaga_ms = 0
            self.revisando = esc
            super()._ejecutar("REVISAR_ESCONDITE", dt, factor, mundo, al_atrapar, al_revisar)
            return
        if accion == "ESTUDIAR":
            self._estudiar(dt, factor, mundo)
            return
        if accion == "RONDAR":
            self._rondar(dt, factor, mundo)
            return
        if accion == "ALEJARSE":
            self._alejarse()
            return
        if accion == "ESPERAR_EN_CEBO":
            cebo = self._cebo()
            if cebo is not None and _d(self.centro, cebo) > 90:
                self._ir_por_camino(cebo, self.datos["vel_patrulla"] * 1.3 * factor, dt, mundo)
            return
        # MERODEAR: camina como un prisionero más (si se aburrió de un grupo,
        # primero se va lejos de ellos).
        if self.yendose_a is not None:
            if self._ir_por_camino(self.yendose_a, self.datos["vel_patrulla"] * 1.2 * factor, dt, mundo) \
                    or _d(self.centro, self.yendose_a) < 40:
                self.yendose_a = None
            return
        npcs.caminar(self, dt, self.juego, self.juego.npcs.puntos if self.juego.npcs else
                     [self.centro], self.datos["vel_patrulla"],
                     getattr(mundo, "colisiona_alien", None))

    # -- Acciones ---------------------------------------------------------------------------

    def _estudiar(self, dt, factor, mundo):
        """Una "pasada": se acerca a su presa sin correr, como un prisionero
        más, para mirarla de cerca. Al llegar (o si tarda mucho) se va a rondar.
        Si ya la conoce, se queda cerca esperando a que se descuide."""
        presa, destino = self.presa, self.punto_presa
        if destino is None:
            self.modo, self.modo_ms = "ronda", self.rng.uniform(*RONDA_MS)
            return
        distancia = _d(self.centro, destino)
        la_conoce = self.conocimiento.get(presa, 0) >= self._necesario(presa)
        cerca = DISTANCIA_REVELARSE * 0.85 if la_conoce and self._sola else DISTANCIA_PASADA
        if distancia > cerca:
            velocidad = self.datos["vel_patrulla"] * (1.6 if distancia > 600 else 1.1)
            self._ir_por_camino(destino, velocidad * factor, dt, mundo)
        elif not (la_conoce and self._sola):
            self.modo_ms = 0          # ya la vio de cerca: se va
        if self.modo_ms == 0:
            self.modo, self.modo_ms = "ronda", self.rng.uniform(*RONDA_MS)
            self.punto_ronda = None

    def _rondar(self, dt, factor, mundo):
        """Lejos de su presa, pero no tanto: camina por ahí un rato y después
        vuelve a pasar cerca. Así no parece que la sigue."""
        presa = self.presa
        if self.modo_ms == 0:
            self.modo, self.modo_ms = "pasada", PASADA_MAX_MS
            return
        if self.punto_ronda is None:
            centro = presa.hitbox.center if presa is not None else self.centro
            puntos = self.juego.npcs.puntos if self.juego.npcs else [self.centro]
            lo, hi = RONDA_DISTANCIA
            opciones = [p for p in puntos if lo <= _d(p, centro) <= hi] or puntos
            self.punto_ronda = self.rng.choice(opciones)
        if _d(self.centro, self.punto_ronda) > 40:
            self._ir_por_camino(self.punto_ronda, self.datos["vel_patrulla"] * factor, dt, mundo)

    def _alejarse(self):
        """La presa nunca se separa del grupo: deja de mirarla, se va lejos y
        vuelve a cazar dentro de un rato (puede que a otro)."""
        self.yendose_a = self._escondrijo()
        self._olvidar(self.presa, 0.0)
        self.presa = None
        self.punto_presa = None
        self.calma_ms = int(self.rng.uniform(*ALEJARSE_CALMA_MS))

    def _seguir(self, dt, factor, mundo):
        """Lo llevan creyendo que es un prisionero: lo sigue demasiado pegado y
        traiciona. Si quien lo lleva se queda solo, lo ataca; si llega
        acompañado a la cápsula, la sabotea y huye."""
        guia = self.siguiendo
        if _d(self.centro, guia.hitbox.center) > DISTANCIA_SEGUIR_CF:
            self._ir_por_camino(guia.hitbox.center, max(self.datos["vel_patrulla"] * 2.6, 3.2) * factor,
                                dt, mundo)
        mision = getattr(self.juego, "mision", None)
        acompanado = any(o is not guia and not o.preso
                         and _d(o.hitbox.center, guia.hitbox.center) < DISTANCIA_COMPANIA
                         for o in self.juego.jugadores)
        if (mision is not None and mision.capsula is not None
                and npcs.distancia_a_rect(self.centro, mision.capsula) <= RADIO_SABOTAJE):
            self.sabotear()
            return
        if acompanado:
            self.siguiendo_solo_ms = 0
            return
        self.siguiendo_solo_ms += dt
        if (self.siguiendo_solo_ms >= self._ajuste("cf_traicion_ms", TRAICION_SOLO_MS)
                and self.visible_para(guia)):
            self.presa, self.punto_presa = guia, guia.hitbox.center
            self.siguiendo = None
            self.calma_ms = 0
            self._revelarse()

    def sabotear(self):
        """Llegó a la cápsula con el grupo: arranca una pieza (o deshace parte de
        la reparación), la tira lejos y huye."""
        mision = self.juego.mision
        guia = self.siguiendo
        self.siguiendo = None
        self.sabotajes += 1
        quien = self.apariencia.usuario if self.apariencia else "Ese prisionero"
        # Arranca una pieza Y daña la reparación: si ya estaba lista, deja de
        # estarlo y hay que volver a repararla (antes se podía escapar igual).
        danios = []
        if mision.piezas_entregadas > 0:
            mision.piezas_entregadas -= 1
            from data.estaciones import TAMANO_PIEZA
            puntos = self.juego.npcs.puntos if self.juego.npcs else [self.centro]
            lejos = max(puntos, key=lambda p: _d(p, mision.capsula.center))
            rect = pygame.Rect(0, 0, *TAMANO_PIEZA)
            rect.center = lejos
            self.juego.piezas.append({"rect": rect, "recogida": False})
            danios.append("arrancó una pieza y la tiró lejos")
        if mision.reparacion > 0:
            mision.reparacion = max(0.0, mision.reparacion - DANIO_SABOTAJE)
            danios.append("dañó la reparación")
        if mision.fase == "huida":
            mision.volver_a_reparar()
            danios.append("¡ya no sirve para escapar!")
        danio = ", ".join(danios[:-1]) + " y " + danios[-1] if len(danios) > 1 else (
            danios[0] if danios else "rompió lo que pudo")
        for j in self.juego.jugadores:
            j.avisar(f"¡{quien} era el Cambiaformas! Saboteó la cápsula: {danio}.", (236, 70, 60))
        if guia is not None:
            self._asustar(guia)
        elif hasattr(self.juego, "sonar"):
            self.juego.sonar("cf_revela", 0.9)
        if hasattr(self.juego, "decir"):
            self.juego.decir("sabotaje", getattr(guia, "rol", None))
        self.presa = None
        self.calma_ms = self._calma_tras_cazar()
        self._empezar_huida()

    def pedir_que_siga(self, jugador):
        """Le preguntaron "¿vienes conmigo?": acepta sin decir nada (una pista)."""
        if not self.disfrazado or self.siguiendo is not None:
            return False
        self.siguiendo = jugador
        self.siguiendo_solo_ms = 0
        self.presa = None
        self.burbuja, self.burbuja_ms = "...", 2500
        return True

    def desenmascarar(self):
        """Reportaron su suplantación en NEXUS: pierde el disfraz y huye."""
        if self.siguiendo is not None:
            logro(self.juego, "cara_a_cara", self.siguiendo)    # (lo tenía al lado)
            logro(self.juego, "lobo_con_piel_de_oveja", self.siguiendo)
            self.siguiendo = None
        self.disfrazado = False
        self.rafaga_ms = 0
        self.presa = None
        self.expuesto_ms = max(self.expuesto_ms, DESENMASCARADO_MS)
        self._empezar_huida()

    def _revelarse(self):
        self.revelaciones += 1
        self.disfrazado = False
        self.rafaga_ms = RAFAGA_MS
        self.transformando_ms = TRANSFORMARSE_MS
        presa = self.presa
        if presa is not None:
            self._asustar(presa)
            presa.avisar(f"¡{self.apariencia.usuario if self.apariencia else 'Ese prisionero'} "
                         "era el Cambiaformas!", (236, 70, 60))
        elif hasattr(self.juego, "sonar"):
            self.juego.sonar("cf_revela", 1.0)
        if hasattr(self.juego, "decir"):
            self.juego.decir("cambiaformas", getattr(presa, "rol", None))

    def _asustar(self, jugador):
        """Su susto de transformación (ambiente.py): el prisionero que imitaba
        se vuelve el monstruo en la pantalla de ese jugador."""
        ambiente = getattr(self.juego, "ambiente", None)
        if ambiente is not None:
            ambiente.susto(jugador, "cf_revela", self.apariencia.sprite if self.apariencia else None)
        else:
            jugador.susto_ms = 900

    def _empezar_huida(self):
        self.disfrazado = False
        self.huida_ms = HUIDA_MAX_MS
        self.objetivo = None
        self.ruta_ruido, self._destino_ruta = [], None
        self.punto_huida = self._escondrijo()

    def _vivos(self):
        return [j for j in self.juego.jugadores if not j.preso and not getattr(j, "eliminado", False)]

    def _escondrijo(self):
        """Un punto lejos de todos y que ningún jugador vea."""
        puntos = self.juego.npcs.puntos if self.juego.npcs else [self.centro]
        vivos = self._vivos()
        if not vivos:
            return self.rng.choice(puntos)
        mundo = self.juego.mundo

        def lo_ven(p):
            return any(_d(p, j.hitbox.center) <= VISION and mundo.linea_libre(p, j.hitbox.center)
                       for j in vivos)
        ocultos = [p for p in puntos if not lo_ven(p)] or puntos
        return max(ocultos, key=lambda p: min(_d(p, j.hitbox.center) for j in vivos))

    def _huir(self, dt, factor, mundo):
        if self.punto_huida is not None:
            llego = self._ir_por_camino(self.punto_huida, self.datos["vel_investigar"] * factor, dt, mundo)
        else:
            llego = True
        lejos = all(_d(self.centro, j.hitbox.center) > 350 for j in self.juego.jugadores
                    if not j.preso)
        if not self._alguien_lo_ve():
            if llego or lejos:
                self._disfrazarse()
        elif llego:
            # Llegó, pero alguien lo está mirando: busca otro rincón.
            self.punto_huida = self._escondrijo()
            self.huida_ms = max(self.huida_ms, 3000)

    def _disfrazarse(self):
        if self.expuesto_ms > 0:
            return
        opciones = list(self.apariencias)
        # Prefiere su identidad de siempre; a veces la de otro (puede haber dos iguales).
        usuario = self.identidad if (self.identidad in opciones and self.rng.random() < 0.5) \
            else self.rng.choice(opciones)
        self.apariencia = self.apariencias[usuario]
        self.disfrazado = True
        self.huida_ms = 0
        self.punto_huida = None

    # -- Lo que le hacen los jugadores ---------------------------------------------------------

    def aturdir(self, ms):
        """Hackeo: lo aturde, le quita el disfraz y al despertar huye."""
        if self.siguiendo is not None:
            logro(self.juego, "cara_a_cara", self.siguiendo)    # (lo tenía al lado)
        if self.disfrazado:
            logro(self.juego, "no_me_enganas")
        if self.siguiendo is not None:
            logro(self.juego, "lobo_con_piel_de_oveja", self.siguiendo)
            self.siguiendo = None
        super().aturdir(ms)
        self.disfrazado = False
        self.rafaga_ms = 0
        self.objetivo = None
        self.huir_al_despertar = True

    def confundir(self, ms):
        """Lo expusieron en NEXUS: aturdido y sin poder disfrazarse un rato."""
        self.aturdir(ms)
        self.confundido = True
        self.expuesto_ms = EXPUESTO_MS

    def rendirse(self):
        """La presa se calmó en el minijuego: la deja en paz un buen rato y se
        va a esconder. (Antes volvía enseguida y la encerraba en un bucle de
        minijuegos.)"""
        super().rendirse()
        self.revisando = None
        self.presa = None
        self.rafaga_ms = 0
        self.calma_ms = self._calma_tras_cazar()
        if not self.disfrazado:
            self._empezar_huida()

    def entrar_al_escondite(self):
        """Ganó el minijuego: abre el casillero (el juego atrapa al de adentro)."""
        super().entrar_al_escondite()
        self.capturas += 1
        self._olvidar(self.presa, 1.0)
        self.revisando = None
        self.presa = None
        self.rafaga_ms = 0
        self.huir_al_despertar = True
        self.calma_ms = self._calma_tras_cazar()

    def enterarse(self, jugador):
        """Alguien delató dónde está ese jugador (foto con ubicación, un
        prisionero rojo, una acusación falsa): si no tiene presa, la escoge."""
        if self.presa is None and jugador is not None and jugador.cazable:
            self.presa = jugador
            self.punto_presa = jugador.hitbox.center
            self.calma_ms = 0

    def oir(self, punto):
        """Una distracción no le gana a su presa; sin presa, va a ver."""
        if self.presa is not None or self.descanso_ms > 0:
            return False
        self.punto_presa = (int(punto[0]), int(punto[1]))
        return False

    # -- Dibujo ------------------------------------------------------------------------------

    def dibujar_vision(self, screen, offset):
        return      # no tiene cono

    def dibujar_senal(self, screen, offset):
        if self.disfrazado:
            return
        super().dibujar_senal(screen, offset)

    def dibujar(self, screen, offset):
        if self.disfrazado and self.apariencia is not None:
            usuario = self.apariencia.usuario
            if self.glitch_ms < 0:
                usuario = "".join(c if self.rng.random() < 0.55 else self.rng.choice(GLITCH)
                                  for c in usuario)
            color = (170, 172, 185)
            self.apariencia.dibujar(screen, self.hitbox.center, offset, usuario, color,
                                    self.burbuja if self.burbuja_ms > 0 else None)
            return
        # Transformándose: parpadea entre el prisionero y el monstruo.
        if (self.transformando_ms > 0 and self.apariencia is not None
                and int(self.transformando_ms / 90) % 2):
            self.apariencia.dibujar(screen, self.hitbox.center, offset)
            return
        imagen, _ = self._frame_sprite()
        if imagen is not None:
            super().dibujar(screen, offset)       # el sprite de Joseph
        else:
            self._dibujar_monstruo(screen, offset)

    def _dibujar_monstruo(self, screen, offset):
        """Si falta el sprite (Imagenes/Aliens/Alien_Cambiaformas): una
        silueta alta y deforme dibujada con formas."""
        x = self.hitbox.centerx - offset[0]
        pies = self.hitbox.bottom - offset[1]
        t = self.tiempo_ms / 1000
        alto = 112
        sombra = pygame.Rect(0, 0, 60, 14)
        sombra.center = (x, pies)
        pygame.draw.ellipse(screen, (10, 0, 14), sombra)
        # Tentáculos que se mueven.
        for i in range(6):
            base = (x + (i - 2.5) * 8, pies - 30)
            fase = t * 3 + i
            punta = (base[0] + math.sin(fase) * 22 + (i - 2.5) * 6, pies - 4 + math.cos(fase) * 4)
            pygame.draw.line(screen, (40, 6, 50), base, punta, 6)
        cuerpo = pygame.Rect(0, 0, 54, alto - 30)
        cuerpo.midbottom = (x, pies - 18)
        pygame.draw.ellipse(screen, (28, 8, 38), cuerpo)
        cabeza = pygame.Rect(0, 0, 44 + 4 * math.sin(t * 5), 46)
        cabeza.midbottom = (x, cuerpo.y + 18)
        pygame.draw.ellipse(screen, (40, 10, 52), cabeza)
        # Brazos largos.
        for lado in (-1, 1):
            hombro = (x + lado * 22, cuerpo.y + 24)
            mano = (x + lado * (40 + 6 * math.sin(t * 4)), cuerpo.bottom - 6)
            pygame.draw.line(screen, (36, 8, 46), hombro, mano, 7)
        # Ojos y boca.
        for lado in (-1, 1):
            ojo = (int(x + lado * 10), int(cabeza.centery - 2))
            pygame.draw.circle(screen, (255, 40, 40), ojo, 5)
            pygame.draw.circle(screen, (255, 220, 220), ojo, 2)
        boca = [(x - 14, cabeza.bottom - 12)]
        for i in range(1, 8):
            boca.append((x - 14 + i * 4, cabeza.bottom - 12 + (5 if i % 2 else 0)))
        pygame.draw.lines(screen, (230, 230, 230), False, boca, 2)
