"""Los aliens: patrullan, ven, oyen latidos y persiguen.

Cada alien hace dos cosas por frame:

1. `percibir()` traduce lo que pasa a su alrededor en respuestas de sí o no
   ("¿ve a un jugador?", "¿oyó un latido?"...).
2. Con esas respuestas recorre el árbol de comportamiento
   (Estructuras/arbol_comportamiento.py) de la raíz a una hoja, y la hoja dice
   qué acción ejecutar en ese frame.

El árbol es el mismo para todos los aliens (es contenido, vive en
data/comportamiento_alien.py); lo que cambia es la ruta de cada uno y lo que
percibe. Cada alien guarda el último camino que recorrió en el árbol para que
la vista del árbol (Pausa > Opciones) lo resalte en vivo.

Para volver a su ruta después de perseguir a alguien, el alien deja un
**rastro**: una pila de puntos por donde pasó desde que salió de la ruta. Al
volver los va sacando de la pila (el último en entrar es el primero en salir),
así que deshace su camino exacto y nunca intenta atravesar una pared para
regresar.

Hay varios **tipos** de alien (data/tipos_alien.py): todos usan el mismo
árbol, pero cada tipo ve, oye y corre distinto. El Ciego, por ejemplo, nunca
responde "sí" a "¿ve a un jugador?" salvo que lo tenga casi encima.

Los sprites de los aliens (de Anny; el del Cambiaformas, de Joseph) están en
Imagenes/Aliens/<carpeta>/ con el mismo formato que los personajes (8
direcciones, idle/breathing/walking; running sirve de walking).
Si falta la carpeta de un tipo, se dibuja con formas (respaldo).
"""

import os

# La raíz del proyecto (este archivo está en una subcarpeta).
_RAIZ_PROYECTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import math

import pygame

from juego.fuentes import fuente_de_tamano
from data.tipos_alien import datos_tipo, TIPO_POR_DEFECTO
from data.nexus import POTENCIA_VELOCIDAD, POTENCIA_VISION


# Velocidad, visión y oído de cada tipo de alien: data/tipos_alien.py.

DISTANCIA_ATRAPAR = 46
DISTANCIA_REVISAR = 80           # a esta distancia del escondite se pone a revisarlo
ENFRIAMIENTO_ESCONDITE_MS = 7000 # tras rendirse, cuánto ignora ese escondite
DURACION_BUSQUEDA_MS = 3000      # cuánto busca después de perder el rastro
DURACION_DESCANSO_MS = 2500      # cuánto se queda quieto tras atrapar a alguien
SEPARACION_RASTRO = 36           # cada cuánto deja un punto en el rastro
TIEMPO_ATASCADO_MS = 900         # sin avanzar este tiempo = se rinde
# Patrulla con un sello o una puerta cortándole la ruta: un punto al que solo
# llega dando un rodeo mucho más largo que su recorrido normal cuenta como
# inalcanzable (antes daba la vuelta a media nave para llegar al otro lado).
DESVIO_MAX = 1.6                 # el rodeo puede ser hasta esto × lo normal...
DESVIO_EXTRA_PX = 350            # ...más esto

ANCHO_HITBOX, ALTO_HITBOX = 34, 20

# Color del cono según lo que está haciendo.
COLOR_CONO = {
    "PATRULLAR": (200, 230, 255),
    "VOLVER": (200, 230, 255),
    "INVESTIGAR": (255, 214, 64),
    "BUSCAR": (255, 214, 64),
    "PERSEGUIR": (240, 70, 60),
    "ATRAPAR": (240, 70, 60),
    "DESCANSAR": (150, 150, 170),
    "REVISAR_ESCONDITE": (240, 70, 60),
}

# Sprites por tipo: carpeta en Imagenes/Aliens/ y escala (los cuadros vienen
# de 96 px; el Ciego de 80 px y es bajito porque va a cuatro patas). El
# Cambiaformas viene en cuadros de 80 px y se agranda más: revelado tiene que
# verse más alto que los demás (~120 px).
SPRITES_ALIEN = {
    "ciego": ("Alien_Ciego", 2.0),
    "cazador": ("Alien_Rapido", 1.8),
    "vigia": ("Alien_Vision", 1.9),
    "cambiaformas": ("Alien_Cambiaformas", 2.3),
}
FPS_ANIMACION = 8
# Ángulo -> dirección del sprite (0 = este, va en sentido horario en pantalla).
_DIRECCIONES_ANGULO = ("east", "south-east", "south", "south-west",
                       "west", "north-west", "north", "north-east")
_cache_sprites = {}


def sprites_de(tipo):
    """Animaciones del tipo de alien, o None si no tiene sprites (o no hay
    pantalla todavía). Se cargan una sola vez por tipo."""
    if tipo in _cache_sprites:
        return _cache_sprites[tipo]
    datos = SPRITES_ALIEN.get(tipo)
    resultado = None
    if datos is not None and pygame.display.get_surface() is not None:
        carpeta, escala = datos
        ruta = os.path.join(_RAIZ_PROYECTO, "Imagenes", "Aliens", carpeta)
        if os.path.isdir(ruta):
            from Movimiento.Personaje import cargar_animaciones
            animaciones = cargar_animaciones(ruta, escala=escala, ancho_ratio=1.0)
            muestra = (animaciones.get("idle", {}).get("south") or [None])[0]
            if muestra is not None:
                contenido = muestra.get_bounding_rect()
                _alinear_pies(animaciones, contenido.bottom)
                # Cuánto aire transparente hay debajo de los pies, y la caja de
                # lo que se ve (para poner encima el "!" y los ojos).
                resultado = {"animaciones": animaciones,
                             "pie": muestra.get_height() - contenido.bottom,
                             "contenido": contenido}
    _cache_sprites[tipo] = resultado
    return resultado


def _alinear_pies(animaciones, base):
    """Corre cada dirección para que los pies queden a la misma altura.

    Las hojas no vienen todas alineadas: en la del Vigía caminando al oeste
    el monstruo está ~7 px (sin escalar) más arriba que en la del suroeste o
    el noroeste, así que al caminar a la izquierda, cada vez que cambiaba
    entre esas direcciones parecía que saltaba. Los pies de una dirección son
    lo más bajo de sus cuadros (el pie que pisa); todas se llevan a `base`
    (la de quieto de frente, con la que se calcula dónde se dibuja)."""
    for por_direccion in animaciones.values():
        for direccion, cuadros in list(por_direccion.items()):
            cajas = [c.get_bounding_rect() for c in cuadros]
            pies = [caja.bottom for caja in cajas if caja.height]
            if not pies:
                continue
            dy = base - max(pies)
            if dy:
                corridos = []
                for cuadro in cuadros:
                    nuevo = pygame.Surface(cuadro.get_size(), pygame.SRCALPHA)
                    nuevo.blit(cuadro, (0, dy))
                    corridos.append(nuevo)
                por_direccion[direccion] = corridos


def _distancia(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


class Alien:
    def __init__(self, numero, ruta, arbol, tipo=TIPO_POR_DEFECTO):
        """`ruta` es una lista de puntos (x, y) en píxeles del mundo."""
        self.numero = numero
        self.tipo = tipo
        self.datos = datos_tipo(tipo)
        self.nombre = f"{self.datos['nombre']} {numero}"
        self.ruta = list(ruta)
        self.arbol = arbol
        self.indice_ruta = 1 % len(self.ruta)

        self.hitbox = pygame.Rect(0, 0, ANCHO_HITBOX, ALTO_HITBOX)
        self.hitbox.center = self.ruta[0]
        self.angulo = 0.0                 # hacia dónde mira, en radianes

        self.accion = "PATRULLAR"
        self.camino = []                  # nodos recorridos en el árbol este frame

        self.objetivo = None              # jugador que está viendo
        self.punto_ruido = None           # a dónde va a investigar
        self.escondite_objetivo = None    # escondite de donde salió el latido
        self.rastro = []                  # pila de puntos para volver a la ruta
        self.busqueda_ms = 0
        self.descanso_ms = 0
        self.aturdido = False             # el descanso viene de un hackeo
        self.confundido = False           # ...o de que expusieron al infiltrado
        self.alerta = False               # huida final: más rápido y ve más lejos
        self.potencia_nexus = 0.0         # 0-1: cuánto le va ganando el rojo en NEXUS
        # La dificultad (dificultad.py) multiplica velocidad, visión y oído;
        # el juego los pone cada frame. 1.0 = Pesadilla (los números base).
        self.ajuste_vel = self.ajuste_vision = self.ajuste_oido = 1.0
        self.atascado_ms = 0
        self.tiempo_ms = 0                # reloj propio, para animaciones
        self.persecucion_ms = 0           # cuánto lleva persiguiendo (el Cazador se cansa)
        self.cansado = False
        self.moviendose = False           # para escoger la animación de caminar
        self.ruta_ruido = []              # camino (navegacion.py) hacia el ruido
        self._ruta_parcial = False        # el camino no llega al ruido, solo lo más cerca posible
        self._destino_ruta = None
        self._recalcular_ms = 0
        # Patrulla con puertas cerradas (_elegir_punto_patrulla): a qué punto
        # va, si directo o rodeando, y con qué puertas/sellos se decidió.
        self._patrulla_revisada = None
        self._patrulla_directa = True
        self._patrulla_quieto = False

    # -- Percepción ---------------------------------------------------------------

    @property
    def centro(self):
        return self.hitbox.center

    def puede_ver(self, punto, mundo):
        """True si `punto` está dentro del cono y no hay una pared en medio."""
        dx, dy = punto[0] - self.centro[0], punto[1] - self.centro[1]
        distancia = math.hypot(dx, dy)
        # Tacto: lo que tiene casi encima lo nota aunque no lo vea (el Ciego
        # solo "ve" así).
        # Los sellos del Forjador son opacos para ellos: ni ven a través.
        choca = getattr(mundo, "colisiona_alien", None)
        if distancia <= self.datos["tacto"]:
            return mundo.linea_libre(self.centro, punto, colisiona=choca) if choca \
                else mundo.linea_libre(self.centro, punto)
        if distancia > self.alcance_vision:
            return False
        if distancia > 1:
            diferencia = (math.atan2(dy, dx) - self.angulo + math.pi) % (2 * math.pi) - math.pi
            if abs(diferencia) > self.datos["medio_angulo"]:
                return False
        if choca:
            return mundo.linea_libre(self.centro, punto, colisiona=choca)
        return mundo.linea_libre(self.centro, punto)

    @property
    def alcance_vision(self):
        """Ve más lejos en la huida y mientras el rojo le gana al verde en NEXUS."""
        return (self.datos["alcance_vision"] * (1.3 if self.alerta else 1.0)
                * (1 + POTENCIA_VISION * self.potencia_nexus) * self.ajuste_vision)

    @staticmethod
    def escondite_disponible(escondite, alien=None):
        """Si un alien puede ir a revisar este escondite ahora."""
        if escondite.get("enfriamiento_ms", 0) > 0:
            return False
        dueño = escondite.get("revisado_por")
        return dueño is None or dueño is alien

    def _revisando_ocupado(self):
        esc = self.escondite_objetivo
        return (esc is not None and esc.get("revisado_por") is self
                and esc.get("ocupante") is not None and esc.get("enfriamiento_ms", 0) <= 0)

    def soltar_escondites(self, escondites):
        """Suelta los escondites que marcó como "lo estoy revisando" y ya no
        revisa (se fue, lo cambió por otro, salió el de adentro...). Si no, el
        escondite quedaba en rojo y ningún alien podía volver a revisarlo."""
        for esc in escondites:
            if esc.get("revisado_por") is self and esc is not self.escondite_objetivo:
                esc["revisado_por"] = None

    def percibir(self, jugadores, mundo, escondites=()):
        """Responde las preguntas del árbol con lo que pasa en este frame."""
        visibles = [j for j in jugadores
                    if j.cazable and not j.escondido
                    and self.puede_ver(j.hitbox.center, mundo)]
        self.objetivo = min(visibles, key=lambda j: _distancia(self.centro, j.hitbox.center),
                            default=None)

        if self.objetivo is not None:
            # Lo último que vio: si lo pierde, va a buscar ahí.
            self.punto_ruido = self.objetivo.hitbox.center
        elif self._revisando_ocupado():
            # Ya está revisando un escondite con alguien adentro: no lo cambia
            # por otro que también oiga. (Antes, con dos escondites juntos y
            # alguien en cada uno, saltaba de uno al otro según qué latido
            # sonara más, y se quedaba parado al frente sin que empezara el
            # minijuego de ninguno.)
            self.punto_ruido = self.escondite_objetivo["ocupante"].hitbox.center
        else:
            # Un latido fuerte se oye aunque no haya línea de vista: el pulso de
            # cada jugador decide qué tan lejos llega su ruido. Si ya iba hacia
            # un escondite y todavía oye al de adentro, sigue con ese.
            actual = self.escondite_objetivo
            jugadores = sorted(jugadores, key=lambda j: 0 if (actual is not None and j.escondido
                                                              and j.escondite is actual) else 1)
            for jugador in jugadores:
                if not jugador.cazable:
                    continue
                if _distancia(self.centro, jugador.hitbox.center) > jugador.radio_ruido * self.datos["oido"] * self.ajuste_oido:
                    continue
                if jugador.escondido:
                    if not self.escondite_disponible(jugador.escondite, self):
                        continue
                    self.escondite_objetivo = jugador.escondite
                self.punto_ruido = jugador.hitbox.center
                break

        # Si va hacia un escondite ocupado (porque lo oyó, o porque vio a
        # alguien meterse ahí), lo recuerda para revisarlo al llegar.
        if self.punto_ruido is not None and self.escondite_objetivo is None:
            for escondite in escondites:
                if (escondite.get("ocupante") is not None
                        and self.escondite_disponible(escondite, self)
                        and escondite["rect"].inflate(60, 60).collidepoint(self.punto_ruido)):
                    self.escondite_objetivo = escondite
                    break
        if self.escondite_objetivo is not None and (
                self.escondite_objetivo.get("ocupante") is None
                or not self.escondite_disponible(self.escondite_objetivo, self)):
            self.escondite_objetivo = None

        al_alcance = (self.objetivo is not None and
                      _distancia(self.centro, self.objetivo.hitbox.center) <= DISTANCIA_ATRAPAR)
        return {
            "recuperandose": self.descanso_ms > 0,
            "ve_jugador": self.objetivo is not None,
            "jugador_al_alcance": al_alcance,
            "oye_ruido": self.punto_ruido is not None,
            "en_escondite": (self.escondite_objetivo is not None and
                             _distancia(self.centro, self.escondite_objetivo["rect"].center)
                             <= DISTANCIA_REVISAR),
            "rastro_reciente": self.busqueda_ms > 0,
            "fuera_de_ruta": bool(self.rastro),
        }

    # -- Frame --------------------------------------------------------------------

    def actualizar(self, dt, mundo, jugadores, al_atrapar=None, escondites=(),
                   al_revisar=None):
        """Percibe, decide con el árbol y ejecuta la acción de la hoja.

        `al_atrapar(jugador, alien)` y `al_revisar(jugador, alien, escondite)`
        los pone el juego: lo que pasa al atrapar a alguien o al empezar a
        revisar un escondite no es asunto del alien.
        """
        self.tiempo_ms += dt
        factor = min(3.0, dt / (1000 / 60)) if dt else 1.0
        if self.alerta:
            factor *= 1.25
        factor *= (1 + POTENCIA_VELOCIDAD * self.potencia_nexus) * self.ajuste_vel
        self.descanso_ms = max(0, self.descanso_ms - dt)
        if self.descanso_ms == 0:
            self.aturdido = False
            self.cansado = False
            self.confundido = False

        condiciones = self.percibir(jugadores, mundo, escondites)
        self.accion, self.camino = self.arbol.decidir(condiciones)
        antes = self.hitbox.center
        self._ejecutar(self.accion, dt, factor, mundo, al_atrapar, al_revisar)
        self.soltar_escondites(escondites)
        self.moviendose = self.hitbox.center != antes
        self._cansarse(dt)

    def _cansarse(self, dt):
        """El Cazador corre más que nadie, pero solo un rato."""
        aguante = self.datos["aguante_ms"]
        if not aguante:
            return
        if self.accion == "PERSEGUIR":
            self.persecucion_ms += dt
            if self.persecucion_ms >= aguante:
                self.persecucion_ms = 0
                self.cansado = True
                self.descanso_ms = max(self.descanso_ms, self.datos["cansancio_ms"])
                self.objetivo = None
        else:
            self.persecucion_ms = max(0, self.persecucion_ms - dt / 2)

    # -- Lo que les hacen las habilidades de los jugadores ----------------------------

    def aturdir(self, ms):
        """Hackeo del Tecnomante: queda fuera de combate `ms` milisegundos.

        Si estaba revisando un escondite, lo suelta: el juego ve que ya no lo
        revisa y termina el minijuego de quien estaba adentro.
        """
        if self.escondite_objetivo is not None:
            self.rendirse()
        self.descanso_ms = max(self.descanso_ms, ms)
        self.aturdido = True
        self.punto_ruido = None
        self.busqueda_ms = 0

    def confundir(self, ms):
        """Expusieron al infiltrado de NEXUS (infiltrado.py): se quedan
        quietos `ms` milisegundos, sin ver ni oír, como con un hackeo."""
        self.aturdir(ms)
        self.confundido = True
        self.objetivo = None

    def oir(self, punto):
        """Un ruido que no viene de un latido: señuelo o señal falsa.

        Si está persiguiendo a alguien, revisando un escondite o fuera de
        combate, no le hace caso: una distracción no le gana a lo que tiene
        enfrente.
        """
        if self.descanso_ms > 0 or self.accion in ("PERSEGUIR", "ATRAPAR", "REVISAR_ESCONDITE"):
            return False
        self.punto_ruido = (int(punto[0]), int(punto[1]))
        self.escondite_objetivo = None
        self.ruta_ruido, self._destino_ruta = [], None
        return True

    def rendirse(self):
        """El jugador ganó el minijuego: deja el escondite en paz un rato."""
        escondite = self.escondite_objetivo
        if escondite is not None:
            escondite["revisado_por"] = None
            escondite["enfriamiento_ms"] = ENFRIAMIENTO_ESCONDITE_MS
        self.escondite_objetivo = None
        self.punto_ruido = None
        self.busqueda_ms = DURACION_BUSQUEDA_MS

    def entrar_al_escondite(self):
        """El jugador perdió el minijuego: el alien abre el escondite."""
        escondite = self.escondite_objetivo
        if escondite is not None:
            escondite["revisado_por"] = None
            escondite["enfriamiento_ms"] = ENFRIAMIENTO_ESCONDITE_MS
        self.escondite_objetivo = None
        self.punto_ruido = None
        self.busqueda_ms = 0
        self.descanso_ms = DURACION_DESCANSO_MS

    def _ejecutar(self, accion, dt, factor, mundo, al_atrapar, al_revisar=None):
        if accion in ("PERSEGUIR", "INVESTIGAR", "BUSCAR", "ATRAPAR", "REVISAR_ESCONDITE"):
            self._dejar_rastro()

        if accion == "DESCANSAR":
            return

        if accion == "REVISAR_ESCONDITE":
            # Se queda frente al escondite mirándolo. La primera vez avisa al
            # juego, que arranca el minijuego del que está adentro; el alien
            # espera aquí hasta que el juego llame a rendirse() o a
            # entrar_al_escondite().
            escondite = self.escondite_objetivo
            centro = escondite["rect"].center
            self.angulo = math.atan2(centro[1] - self.centro[1], centro[0] - self.centro[0])
            ocupante = escondite.get("ocupante")
            sin_minijuego = (ocupante is not None and getattr(ocupante, "minijuego", None) is None)
            if escondite.get("revisado_por") is None or sin_minijuego:
                # (Si ya era suyo pero el de adentro no tiene minijuego, se le
                # arranca: que nunca se quede parado al frente sin más.)
                escondite["revisado_por"] = self
                if al_revisar is not None:
                    al_revisar(ocupante, self, escondite)
            return

        if accion == "ATRAPAR":
            if al_atrapar is not None:
                al_atrapar(self.objetivo, self)
            self.descanso_ms = DURACION_DESCANSO_MS
            self.punto_ruido = None
            self.busqueda_ms = 0
            return

        if accion == "PERSEGUIR":
            self.busqueda_ms = DURACION_BUSQUEDA_MS
            self._ir_hacia(self.objetivo.hitbox.center, self.datos["vel_perseguir"] * factor, dt, mundo)
            return

        if accion == "INVESTIGAR":
            llego = self._ir_por_camino(self.punto_ruido, self.datos["vel_investigar"] * factor,
                                        dt, mundo)
            if llego or self.atascado_ms > TIEMPO_ATASCADO_MS:
                # Llegó (o no puede llegar): ahora busca alrededor un rato.
                self.punto_ruido = None
                self.ruta_ruido, self._destino_ruta = [], None
                self.escondite_objetivo = None
                self.busqueda_ms = DURACION_BUSQUEDA_MS
                self.atascado_ms = 0
            return

        if accion == "BUSCAR":
            # Quieto, mirando a un lado y al otro.
            self.busqueda_ms = max(0, self.busqueda_ms - dt)
            self.angulo += math.sin(self.tiempo_ms / 420) * 0.045 * factor
            return

        if accion == "VOLVER":
            # Deshace el camino sacando puntos de la pila. Si un sello le
            # cerró el paso, se salta ese punto.
            if self._ir_hacia(self.rastro[-1], self.datos["vel_investigar"] * factor, dt, mundo, 6) \
                    or self.atascado_ms > TIEMPO_ATASCADO_MS:
                self.rastro.pop()
                self.atascado_ms = 0
            return

        # PATRULLAR. La ruta puede pasar por puertas (la del código, las para
        # dos) o por donde el Forjador levantó un sello: mientras estén
        # cerradas, se salta los puntos a los que no puede llegar (sin ir a
        # chocar contra la puerta) y patrulla solo su lado; cuando se abren,
        # vuelve a revisar y recorre la ruta entera.
        version = (len(mundo.paredes), len(getattr(mundo, "bloqueos_alien", ())),
                   len(getattr(mundo, "puertas_alien", ())))
        if self._patrulla_revisada != (self.indice_ruta, version):
            self._elegir_punto_patrulla(mundo, version)
        if self._patrulla_quieto:
            return                       # encerrado: se queda de guardia
        destino = self.ruta[self.indice_ruta]
        velocidad = self.datos["vel_patrulla"] * factor
        if self._patrulla_directa:
            llego = self._ir_hacia(destino, velocidad, dt, mundo, 6)
        else:
            llego = self._ir_por_camino(destino, velocidad, dt, mundo)
        if llego or self.atascado_ms > TIEMPO_ATASCADO_MS:
            self.indice_ruta = (self.indice_ruta + 1) % len(self.ruta)
            self.atascado_ms = 0
            self.ruta_ruido, self._destino_ruta = [], None

    def _elegir_punto_patrulla(self, mundo, version):
        """Desde el punto que le toca, el primero de su ruta al que puede llegar:
        directo si la línea está libre, o rodeando (navegacion.py) si no. Si a
        ninguno se puede llegar, se queda quieto hasta que algo se abra.

        Con algo cerrado (un sello, una puerta), "poder llegar" es sin un
        rodeo mucho más largo que ir por su ruta (DESVIO_MAX): así patrulla su
        lado en vez de dar la vuelta a media nave."""
        self._patrulla_quieto = False
        self._patrulla_directa = True
        n = len(self.ruta)
        if n > 1 and hasattr(mundo, "paredes_base"):     # (las pruebas usan mundos de mentira)
            from juego import navegacion
            nav = navegacion.de_mundo(mundo, self.hitbox.width, self.hitbox.height)
            from juego.mundo import paredes_extra
            hay_cierres = bool(getattr(mundo, "bloqueos_alien", None)) or bool(paredes_extra(mundo))
            por_ruta = _distancia(self.centro, self.ruta[self.indice_ruta])   # lo normal, siguiendo su ruta
            for k in range(n):
                i = (self.indice_ruta + k) % n
                punto = self.ruta[i]
                if k > 0:
                    por_ruta += _distancia(self.ruta[(i - 1) % n], punto)
                if nav.libre_entre(self.centro, punto):
                    self.indice_ruta, self._patrulla_directa = i, True
                    break
                if nav.conectados(self.centro, punto) and (
                        not hay_cierres or nav.distancia_camino(
                            self.centro, punto, por_ruta * DESVIO_MAX + DESVIO_EXTRA_PX) is not None):
                    self.indice_ruta, self._patrulla_directa = i, False
                    break
            else:
                self._patrulla_quieto = True
            self.ruta_ruido, self._destino_ruta = [], None
        self._patrulla_revisada = (self.indice_ruta, version)

    def _ir_por_camino(self, destino, velocidad, dt, mundo):
        """Como _ir_hacia, pero rodeando paredes (navegacion.py).

        Si hay línea libre va directo; si no, sigue un camino buscado con BFS.
        El camino se recalcula si el destino se mueve bastante (un ruido que
        se desplaza), pero no más de una vez cada 400 ms. Devuelve True al
        llegar, o si no hay forma de llegar (para que deje de intentarlo).
        """
        self._recalcular_ms = max(0, self._recalcular_ms - dt)
        if not hasattr(mundo, "paredes_base"):
            return self._ir_hacia(destino, velocidad, dt, mundo)
        from juego import navegacion
        nav = navegacion.de_mundo(mundo, self.hitbox.width, self.hitbox.height)
        movido = (self._destino_ruta is None or
                  _distancia(self._destino_ruta, destino) > 64)
        if movido and (self._recalcular_ms == 0 or not self.ruta_ruido):
            self._destino_ruta = destino
            self._recalcular_ms = 400
            if nav.libre_entre(self.centro, destino):
                self.ruta_ruido = [destino]
                self._ruta_parcial = False
            else:
                # Un camino largo se busca en varios cuadros (navegacion.py,
                # por_partes; unos pocos cuadros): mientras tanto va directo.
                # Se sigue pidiendo el mismo destino hasta que salga.
                pedido = getattr(self, "_buscando_hacia", None) or destino
                camino = nav.camino(self.centro, pedido, parcial=True,
                                    por_partes=navegacion.PRESUPUESTO_ALIEN, quien=id(self))
                if camino is None and nav.ocupada:
                    self._buscando_hacia = pedido
                    self._destino_ruta, self._recalcular_ms, self.ruta_ruido = None, 0, []
                    self._ir_hacia(destino, velocidad, dt, mundo)
                    return False
                else:
                    self._buscando_hacia = None
                    if not camino:
                        self.ruta_ruido = []
                        return True          # no se puede llegar ni acercarse: que se rinda
                    self.ruta_ruido = camino
                    self._ruta_parcial = nav.ultimo_parcial
        if not self.ruta_ruido:
            return self._ir_hacia(destino, velocidad, dt, mundo)
        # El último punto del camino sigue al ruido aunque se mueva un poco
        # (salvo en un camino parcial: ahí el último es lo más cerca que llega).
        if not self._ruta_parcial:
            self.ruta_ruido[-1] = destino
        # Si ya ve el siguiente punto del camino, se salta el actual.
        while len(self.ruta_ruido) > 1 and nav.libre_entre(self.centro, self.ruta_ruido[1]):
            self.ruta_ruido.pop(0)
        objetivo = self.ruta_ruido[0]
        # Los puntos intermedios se tocan casi exactos: si dobla antes de
        # llegar, se roza con la esquina y se queda pegado.
        if self._ir_hacia(objetivo, velocidad, dt, mundo, 3 if len(self.ruta_ruido) > 1 else 10):
            self.ruta_ruido.pop(0)
            if not self.ruta_ruido:
                self._destino_ruta = None
                return True
        return False

    def _dejar_rastro(self):
        """Apila un punto cada SEPARACION_RASTRO píxeles mientras está fuera."""
        if not self.rastro or _distancia(self.rastro[-1], self.centro) >= SEPARACION_RASTRO:
            self.rastro.append(self.centro)

    def _ir_hacia(self, destino, velocidad, dt, mundo, tolerancia=10):
        """Da un paso hacia `destino`. Devuelve True si ya llegó.

        Se mueve primero en X y luego en Y, como los jugadores, para que pueda
        deslizarse por una pared en vez de quedarse pegado.
        """
        dx, dy = destino[0] - self.centro[0], destino[1] - self.centro[1]
        distancia = math.hypot(dx, dy)
        if distancia <= tolerancia:
            self.atascado_ms = 0
            return True

        objetivo_angulo = math.atan2(dy, dx)
        diferencia = (objetivo_angulo - self.angulo + math.pi) % (2 * math.pi) - math.pi
        self.angulo += diferencia * 0.25   # gira suave, no de golpe

        paso = min(velocidad, distancia)
        antes = self.hitbox.center
        choca = getattr(mundo, "colisiona_alien", mundo.colisiona)
        for eje_x, eje_y in ((dx / distancia * paso, 0), (0, dy / distancia * paso)):
            previo = self.hitbox.copy()
            self._mover(eje_x, eje_y)
            if choca(self.hitbox):
                self.hitbox = previo
        if self.hitbox.center == antes:
            self.atascado_ms += dt
        else:
            self.atascado_ms = 0
        return False

    def _mover(self, dx, dy):
        # Rect solo guarda enteros: se acumula lo fraccionario aparte para que
        # las velocidades como 1.7 no se redondeen a 1.
        self._resto = getattr(self, "_resto", [0.0, 0.0])
        self._resto[0] += dx
        self._resto[1] += dy
        enteros = int(self._resto[0]), int(self._resto[1])
        self._resto[0] -= enteros[0]
        self._resto[1] -= enteros[1]
        self.hitbox.move_ip(*enteros)

    # -- Dibujo -------------------------------------------------------------------

    def dibujar_vision(self, screen, offset):
        """El cono de visión, translúcido, en el piso.

        El Ciego no tiene cono: se dibuja un anillo tenue del alcance de su
        tacto, que late como si escuchara.
        """
        cx, cy = self.centro[0] - offset[0], self.centro[1] - offset[1]
        color = COLOR_CONO.get(self.accion, (255, 255, 255))
        if self.datos["alcance_vision"] <= 0:
            radio = int(self.datos["tacto"] + 6 * math.sin(self.tiempo_ms / 300))
            caja = pygame.Rect(0, 0, radio * 2 + 4, radio * 2 + 4)
            caja.center = (int(cx), int(cy))
            if not caja.colliderect(screen.get_clip()):
                return
            capa = pygame.Surface(caja.size, pygame.SRCALPHA)
            pygame.draw.circle(capa, (*color, 30), (radio + 2, radio + 2), radio)
            pygame.draw.circle(capa, (*color, 90), (radio + 2, radio + 2), radio, 2)
            screen.blit(capa, caja.topleft)
            return
        alcance = self.alcance_vision
        medio = self.datos["medio_angulo"]
        puntos = [(cx, cy)]
        pasos = 12
        for i in range(pasos + 1):
            a = self.angulo - medio + 2 * medio * i / pasos
            puntos.append((cx + math.cos(a) * alcance, cy + math.sin(a) * alcance))
        # La capa se recorta a lo que ocupa el cono, y solo a la parte que cae
        # en pantalla: antes era un cuadrado de 600x600 nuevo por alien, por
        # viewport y por frame, y eso pesaba.
        xs = [p[0] for p in puntos]
        ys = [p[1] for p in puntos]
        caja = pygame.Rect(int(min(xs)) - 2, int(min(ys)) - 2,
                           int(max(xs) - min(xs)) + 5, int(max(ys) - min(ys)) + 5)
        visible = caja.clip(screen.get_clip())
        if visible.width <= 0 or visible.height <= 0:
            return
        capa = pygame.Surface(visible.size, pygame.SRCALPHA)
        locales = [(x - visible.x, y - visible.y) for x, y in puntos]
        pygame.draw.polygon(capa, (*color, 46), locales)
        pygame.draw.polygon(capa, (*color, 110), locales, 2)
        screen.blit(capa, visible.topleft)

    def _cuerpo(self, offset):
        pie_x, pie_y = self.hitbox.centerx - offset[0], self.hitbox.bottom - offset[1]
        flote = math.sin(self.tiempo_ms / 260) * 3
        alto = 74 if self.tipo == "vigia" else 54 if self.tipo == "cazador" else 62
        ancho = 40 if self.tipo == "vigia" else 50 if self.tipo == "cazador" else 46
        cuerpo = pygame.Rect(0, 0, ancho, alto)
        cuerpo.midbottom = (pie_x, pie_y - 4 + flote)
        return cuerpo, pie_x, pie_y

    def _frame_sprite(self):
        """(superficie, datos) del cuadro que toca ahora, o (None, None)."""
        datos = sprites_de(self.tipo)
        if datos is None:
            return None, None
        estado = "walking" if self.moviendose else "breathing"
        indice = self._indice_direccion()
        frames = datos["animaciones"].get(estado, {}).get(_DIRECCIONES_ANGULO[indice]) or []
        if not frames:
            return None, None
        cuadro = int(self.tiempo_ms / (1000 / FPS_ANIMACION)) % len(frames)
        return frames[cuadro], datos

    def _indice_direccion(self):
        """Cuál de las 8 hojas toca según hacia dónde mira, con un margen: si
        camina justo entre dos direcciones (por ejemplo, oeste y suroeste) no
        salta de una hoja a la otra en cada cuadro."""
        exacto = self.angulo / (math.pi / 4)
        previo = getattr(self, "_indice_hoja", None)
        if previo is not None and abs((exacto - previo + 4) % 8 - 4) < 0.7:
            return previo
        self._indice_hoja = round(exacto) % 8
        return self._indice_hoja

    def _posicion_sprite(self, imagen, datos, offset):
        rect = imagen.get_rect()
        rect.midbottom = (self.hitbox.centerx - offset[0],
                          self.hitbox.bottom - offset[1] + datos["pie"])
        return rect

    def _caja_figura(self, offset):
        """Rect en pantalla de lo que se ve del alien (sprite o formas)."""
        imagen, datos = self._frame_sprite()
        if imagen is not None:
            rect = self._posicion_sprite(imagen, datos, offset)
            return datos["contenido"].move(rect.topleft)
        return self._cuerpo(offset)[0]

    def dibujar(self, screen, offset):
        imagen, datos = self._frame_sprite()
        if imagen is not None:
            rect = self._posicion_sprite(imagen, datos, offset)
            sombra = pygame.Rect(0, 0, int(datos["contenido"].width * 0.8), 14)
            sombra.center = (rect.centerx, self.hitbox.bottom - offset[1] - 2)
            pygame.draw.ellipse(screen, (10, 12, 20), sombra)
            screen.blit(imagen, rect)
            return
        self._dibujar_formas(screen, offset)

    def _dibujar_formas(self, screen, offset):
        """Figura provisional, para el tipo que todavía no tiene sprite.

        Cada tipo tiene su silueta para que se reconozca de un vistazo: el
        Vigía es alto y de un solo ojo, el Ciego lleva una venda sin ojos y el
        Cazador es bajo, rojizo y con púas.
        """
        cuerpo, pie_x, pie_y = self._cuerpo(offset)
        color, borde = self.datos["color"], self.datos["borde"]

        pygame.draw.ellipse(screen, (10, 12, 20), (pie_x - 22, pie_y - 8, 44, 14))
        if self.tipo == "cazador":
            for i in range(5):
                a = math.pi * (1.1 + 0.2 * i)
                base = (cuerpo.centerx + math.cos(a) * 20, cuerpo.centery + math.sin(a) * 22)
                punta = (cuerpo.centerx + math.cos(a) * 34, cuerpo.centery + math.sin(a) * 36)
                pygame.draw.line(screen, borde, base, punta, 4)
        pygame.draw.ellipse(screen, color, cuerpo)
        pygame.draw.ellipse(screen, borde, cuerpo, 3)

        mira_x = math.cos(self.angulo) * 4
        mira_y = math.sin(self.angulo) * 3
        if self.tipo == "ciego":
            # Una venda: no tiene ojos.
            venda = pygame.Rect(cuerpo.x + 4, cuerpo.y + 16, cuerpo.width - 8, 12)
            pygame.draw.rect(screen, (60, 50, 50), venda, border_radius=5)
            for i in range(3):
                x = venda.x + 8 + i * (venda.width - 16) // 2
                pygame.draw.line(screen, (120, 100, 95), (x, venda.y + 2), (x, venda.bottom - 3), 1)
        elif self.tipo == "vigia":
            ojo = pygame.Rect(0, 0, 24, 24)
            ojo.center = (cuerpo.centerx + mira_x * 1.5, cuerpo.y + 22 + mira_y)
            pygame.draw.ellipse(screen, (240, 240, 210), ojo)
            pygame.draw.circle(screen, (12, 12, 20), (int(ojo.centerx + mira_x), int(ojo.centery + mira_y)), 6)
        else:
            pupila = (255, 60, 50) if self.tipo == "cazador" else (230, 240, 255)
            for lado in (-1, 1):
                ojo = pygame.Rect(0, 0, 15, 20 if self.tipo != "cazador" else 12)
                ojo.center = (cuerpo.centerx + lado * 10 + mira_x, cuerpo.y + 22 + mira_y)
                pygame.draw.ellipse(screen, (12, 12, 20), ojo)
                pygame.draw.circle(screen, pupila, (ojo.centerx - 3, ojo.y + 5), 3)

        # Antenas (el Ciego las tiene más largas: con eso "oye").
        largo = 24 if self.tipo == "ciego" else 14
        for lado in (-1, 1):
            base = (cuerpo.centerx + lado * 8, cuerpo.y + 4)
            punta = (cuerpo.centerx + lado * (16 + largo // 3),
                     cuerpo.y - largo + math.sin(self.tiempo_ms / 200 + lado) * 2)
            pygame.draw.line(screen, borde, base, punta, 3)
            pygame.draw.circle(screen, (255, 120, 200), (int(punta[0]), int(punta[1])), 5)

    def dibujar_senal(self, screen, offset):
        """"!" si persigue, "?" si investiga o busca, "zZ" si lo hackearon,
        "?!?" si está confundido (expusieron al infiltrado) y "..." si se cansó.
        Se dibuja debajo de la oscuridad: en un apagón queda igual de oscura."""
        cuerpo = self._caja_figura(offset)
        signo = {"PERSEGUIR": "!", "ATRAPAR": "!", "REVISAR_ESCONDITE": "!",
                 "INVESTIGAR": "?", "BUSCAR": "?"}.get(self.accion)
        if self.accion == "DESCANSAR" and self.cansado:
            signo = "..."
        if self.accion == "DESCANSAR" and self.aturdido and self.confundido:
            signo = "?!?"
        elif self.accion == "DESCANSAR" and self.aturdido:
            signo = "zZ"
            # Chispas: lo apagó un hackeo.
            for i in range(3):
                a = self.tiempo_ms / 150 + i * 2.1
                px = cuerpo.centerx + math.cos(a) * 26
                py = cuerpo.y + 10 + math.sin(a) * 12
                pygame.draw.line(screen, (150, 200, 255), (px - 4, py), (px + 4, py), 2)
                pygame.draw.line(screen, (150, 200, 255), (px, py - 4), (px, py + 4), 2)
        if signo:
            color = {"!": (240, 70, 60), "?": (255, 214, 64),
                     "...": (200, 200, 210), "?!?": (233, 120, 200)}.get(signo, (150, 200, 255))
            f = fuente_de_tamano(30)
            texto = f.render(signo, True, color)
            sombra = f.render(signo, True, (12, 11, 23))
            pos = (cuerpo.centerx - texto.get_width() // 2, cuerpo.y - 46)
            screen.blit(sombra, (pos[0] + 2, pos[1] + 2))
            screen.blit(texto, pos)
