"""Eventos aleatorios de la nave: el "componente aleatorio" del juego.

Cada cierto tiempo (al azar entre INTERVALO_MIN_S e INTERVALO_MAX_S) la nave
hace algo que cambia la ronda, y la IA de la nave lo anuncia:

    apagon     se va la luz y NO vuelve sola: todo queda a oscuras (solo
               alumbran las linternas) hasta que alguien encuentre la caja de
               fusibles que quedó activa y la encienda manteniendo la tecla.
               Mientras dure un apagón no puede empezar otro.
    alarma     14 s: todos los aliens en alerta (más rápidos, ven más lejos).
    compuerta  20 s: se baja una de las compuertas del mapa: hay que dar la
               vuelta o esperar a que suba.

El apagón va aparte de los otros dos: puede sonar una alarma en plena
oscuridad. Es el más molesto, así que sale menos (PESO_EVENTO) y no antes de
PRIMER_APAGON_S de partida ni hasta ENTRE_APAGONES_S después de que volvió la
luz. Qué evento sale, cuándo, qué compuerta se cierra y cuál de las
cajas de fusibles es la buena lo decide `random`, así que ninguna partida es
igual a otra. No hay eventos nuevos durante el tutorial ni en la huida final.

Las cajas de fusibles se ponen con el editor de mapa. Un mapa sin cajas no
tiene apagones (si no, la oscuridad sería para siempre). Solo puede fallar una
caja a la que se llegue caminando desde el inicio con lo que está cerrado en
ese momento (la de la prisión, con su puerta cerrada, no); si no hay ninguna,
no se va la luz. Cuál falla (`elegir_caja`): según la dificultad y cuánto
llevan de misión, de las cercanas a los jugadores a las lejanas
(data/dificultad.py: fusible_lejania y fusible_avance).
"""

import math
import random

import pygame

from juego.fuentes import fuente_de_tamano
from screens.flechas import flecha_alrededor, cerca_del_borde


INTERVALO_MIN_S, INTERVALO_MAX_S = 50, 80
PRIMERO_MIN_S, PRIMERO_MAX_S = 35, 55     # después del tutorial
# Qué tan seguido sale cada uno cuando toca un evento (antes, los tres igual:
# se iba la luz cada ~3 min). Con estos pesos, ~1 de cada 5 eventos.
PESO_EVENTO = {"apagon": 1, "alarma": 2, "compuerta": 2}
PRIMER_APAGON_S = 150          # el primero, no antes de esto
ENTRE_APAGONES_S = 180         # entre que vuelve la luz y el siguiente apagón

EVENTOS = {
    "apagon": {"nombre": "APAGÓN", "color": (150, 160, 255)},
    "alarma": {"nombre": "ALARMA", "duracion_s": 14, "color": (255, 90, 70)},
    "compuerta": {"nombre": "CIERRE DE EMERGENCIA", "duracion_s": 20, "color": (255, 170, 60)},
}

# Caja de fusibles: cuánto hay que mantener la tecla (el Tecnomante sabe más
# de circuitos) y desde qué distancia se puede usar.
TIEMPO_FUSIBLES_S = 3.0
TIEMPO_FUSIBLES_TECNOMANTE_S = 1.5
RADIO_CAJA = 60
TAMANO_CAJA = (40, 46)
PUNTOS_FUSIBLES = 15
DISTANCIA_BRILLO_CAJA = 1300   # hasta dónde se ve su luz en la oscuridad

# Qué tan "pegada" a la lejanía que toca es la elección de la caja: más chico,
# más predecible (ver elegir_caja).
ANCHO_PREFERENCIA = 0.18

COLOR_BIEN = (96, 200, 120)
COLOR_AVISO = (255, 214, 64)
COLOR_FLECHA_CAJA = (255, 76, 64)   # la flecha roja del apagón (en toda dificultad)


def crear_cajas(objetos, mundo):
    cajas = []
    for rx, ry in objetos.get("fusibles", []):
        rect = pygame.Rect(0, 0, *TAMANO_CAJA)
        rect.center = (int(rx * mundo.ancho), int(ry * mundo.alto))
        cajas.append({"rect": rect, "progreso": 0.0})
    return cajas


class GestorEventos:
    def __init__(self, juego, aleatorio=None, cajas=None):
        self.juego = juego
        self.rng = aleatorio or random.Random()
        self.cajas = list(cajas or [])
        self.apagon = False          # la luz está caída
        self.caja = None             # la caja de fusibles que la devuelve
        self.activo = None           # alarma o compuerta en curso
        self.restante_ms = 0
        self.compuerta = None        # la que bajó el evento
        self.alertados = []          # aliens que puso en alerta la alarma
        self.historial = []
        self.proximo_ms = self.rng.randint(PRIMERO_MIN_S, PRIMERO_MAX_S) * 1000
        self.sin_apagon_ms = PRIMER_APAGON_S * 1000    # hasta que pueda irse la luz otra vez

    # -- Qué puede pasar -----------------------------------------------------------

    def posibles(self):
        nombres = []
        if self.cajas and not self.apagon and self._cajas_alcanzables():
            nombres.append("apagon")
        if self.activo is None:
            nombres.append("alarma")
            if self._compuertas_libres():
                nombres.append("compuerta")
        return nombres

    def _cajas_alcanzables(self):
        """Las cajas a las que se llega caminando desde el inicio con lo que
        está cerrado AHORA (puertas con código, puertas para dos, compuertas
        bajadas). Solo esas pueden fallar: antes la buena podía quedar detrás
        de una puerta cerrada (la de la prisión, o una para dos que había que
        abrir a oscuras primero)."""
        juego = self.juego
        mundo = getattr(juego, "mundo", None)
        if mundo is None or not hasattr(mundo, "paredes_base"):
            return list(self.cajas)
        mision = getattr(juego, "mision", None)
        desde = getattr(mision, "_desde", None)
        if desde is not None:
            desde = (desde[0] + 24, desde[1] + 10)
        else:
            libres = [j for j in juego.jugadores if j.puede_moverse and not j.preso]
            if not libres:
                return list(self.cajas)
            desde = libres[0].hitbox.center
        from juego import navegacion
        nav = navegacion.de_mundo(mundo, 34, 20)
        from juego.mundo import paredes_extra
        extra = paredes_extra(mundo)
        extra += [p["rect"] for p in getattr(juego, "puertas_dobles", []) if not p["abierta"]]
        extra += [c["rect"] for c in getattr(juego, "compuertas", []) if c["cerrada"]]
        return [caja for caja in self.cajas
                if nav.conectados(desde, self._pie_de(caja, mundo), extra=extra)]

    @staticmethod
    def _pie_de(caja, mundo):
        """Un punto del piso frente a la caja (la caja en sí va en la pared)."""
        r = caja["rect"]
        return mundo.punto_libre((r.centerx - 17, r.bottom + 10), 34, 20)

    def elegir_caja(self, cajas):
        """Cuál falla: se ordenan por distancia al jugador libre más cercano y
        se sortea con preferencia por las que están a la "lejanía" que toca
        (0 = la más cercana, 1 = la más lejana). La lejanía depende de la
        dificultad (en Fácil, casi siempre la más cercana) y sube a medida
        que avanzan en la misión."""
        if len(cajas) <= 1:
            return cajas[0] if cajas else None
        from juego import dificultad
        juego = self.juego
        jugadores = [j for j in juego.jugadores if not j.preso and not getattr(j, "eliminado", False)] \
            or list(juego.jugadores)
        if not jugadores:
            return self.rng.choice(cajas)
        distancias = [min(math.dist(c["rect"].center, j.hitbox.center) for j in jugadores) for c in cajas]
        cerca, lejos = min(distancias), max(distancias)
        progreso = dificultad.progreso_mision(getattr(juego, "mision", None)) or 0.0
        lejania = (dificultad.valor(juego, "fusible_lejania", 0.5)
                   + dificultad.valor(juego, "fusible_avance", 0.55) * progreso)
        lejania = max(0.0, min(1.0, lejania))
        pesos = []
        for d in distancias:
            x = (d - cerca) / (lejos - cerca) if lejos > cerca else 0.0
            pesos.append(math.exp(-((x - lejania) ** 2) / (2 * ANCHO_PREFERENCIA ** 2)) + 0.003)
        return self.rng.choices(cajas, weights=pesos)[0]

    def _compuertas_libres(self):
        """Compuertas que se pueden bajar sin aplastar a nadie."""
        jugadores = self.juego.jugadores
        return [c for c in getattr(self.juego, "compuertas", [])
                if not c["cerrada"]
                and not any(c["rect"].inflate(20, 20).colliderect(j.hitbox) for j in jugadores)]

    # -- Reloj ---------------------------------------------------------------------

    def actualizar(self, dt):
        if not self.apagon:
            self.sin_apagon_ms = max(0, self.sin_apagon_ms - dt)
        if self.activo is not None:
            self.restante_ms -= dt
            if self.restante_ms <= 0:
                self.terminar()
        mision = getattr(self.juego, "mision", None)
        if mision is not None and mision.fase == "huida":
            return
        self.proximo_ms -= dt
        if self.proximo_ms <= 0:
            self.proximo_ms = self.rng.randint(INTERVALO_MIN_S, INTERVALO_MAX_S) * 1000
            self.lanzar()

    def lanzar(self, nombre=None):
        posibles = self.posibles()
        if nombre is None:
            # Al azar, con pesos, y el apagón solo si ya pasó su espera.
            if self.sin_apagon_ms > 0 and "apagon" in posibles:
                posibles = [p for p in posibles if p != "apagon"]
            if not posibles:
                return None
            nombre = self.rng.choices(posibles, weights=[PESO_EVENTO.get(p, 1) for p in posibles])[0]
        elif nombre not in posibles:
            return None
        if nombre == "apagon":
            alcanzables = self._cajas_alcanzables()
            if not alcanzables:
                return None          # ninguna se puede arreglar ahora: no se va la luz
            self.apagon = True
            self.caja = self.elegir_caja(alcanzables)
            self.caja["progreso"] = 0.0
            self._sonar("apagon", 0.9)
        elif nombre == "compuerta":
            self.compuerta = self.rng.choice(self._compuertas_libres())
            self.compuerta["cerrada"] = True
            self._sonar("compuerta", 0.9)
        elif nombre == "alarma":
            self.alertados = [a for a in self.juego.aliens if not a.alerta]
            for alien in self.alertados:
                alien.alerta = True
            self._sonar("alarma", 0.8)
        if nombre != "apagon":
            self.activo = nombre
            self.restante_ms = EVENTOS[nombre]["duracion_s"] * 1000
        self.historial.append(nombre)
        self._decir(nombre)
        return nombre

    def terminar(self):
        """Termina la alarma o la compuerta (el apagón solo se arregla a mano)."""
        if self.activo == "compuerta" and self.compuerta is not None:
            self.compuerta["cerrada"] = False
            self.compuerta = None
            self._sonar("puerta", 0.5)
        elif self.activo == "alarma":
            mision = getattr(self.juego, "mision", None)
            if mision is None or mision.fase != "huida":
                for alien in self.alertados:
                    alien.alerta = False
            self.alertados = []
        self.activo = None
        self.restante_ms = 0
        if not self.apagon:   # "sistemas normalizados" a oscuras sonaría a mentira
            self._decir("fin_evento")

    # -- La caja de fusibles --------------------------------------------------------

    def caja_cerca(self, jugador):
        if not self.apagon or self.caja is None:
            return None
        if math.dist(jugador.hitbox.center, self.caja["rect"].center) <= RADIO_CAJA:
            return self.caja
        return None

    def caja_falsa_cerca(self, jugador):
        """Una caja que no es la buena: para avisar que hay que buscar otra."""
        if not self.apagon:
            return None
        for caja in self.cajas:
            if caja is not self.caja and math.dist(jugador.hitbox.center,
                                                   caja["rect"].center) <= RADIO_CAJA:
                return caja
        return None

    def mantener(self, jugador, dt):
        """El jugador mantiene la tecla frente a la caja buena."""
        caja = self.caja_cerca(jugador)
        if caja is None:
            return
        duracion = (TIEMPO_FUSIBLES_TECNOMANTE_S if jugador.rol == "Tecnomante"
                    else TIEMPO_FUSIBLES_S)
        caja["progreso"] = min(1.0, caja["progreso"] + dt / 1000 / duracion)
        jugador.progreso = ("Cambiando fusibles", caja["progreso"])
        if caja["progreso"] >= 1:
            self.restaurar_luz(jugador)

    def restaurar_luz(self, jugador=None):
        self.apagon = False
        self.sin_apagon_ms = ENTRE_APAGONES_S * 1000
        self.restauro = jugador          # para el logro (logros.py)
        if self.caja is not None:
            self.caja["progreso"] = 0.0
        self.caja = None
        if jugador is not None:
            jugador.sumar_puntos(PUNTOS_FUSIBLES)
            for j in self.juego.jugadores:
                j.avisar("¡Volvió la luz!" if j is not jugador
                         else f"¡Volvió la luz! +{PUNTOS_FUSIBLES}", COLOR_BIEN)
        self._sonar("luz", 0.9)
        self._decir("luz")

    def pista(self, jugador):
        if self.caja_cerca(jugador) is not None:
            return "Mantener: encender la caja de fusibles"
        if self.caja_falsa_cerca(jugador) is not None:
            return "Esta caja no tiene daño: busquen la que parpadea"
        return None

    # -- Lo que se muestra ------------------------------------------------------------

    def texto(self):
        """Lo que se muestra arriba, p. ej. "APAGÓN · busquen la caja de fusibles"."""
        partes = []
        if self.apagon:
            partes.append(f"{EVENTOS['apagon']['nombre']} · caja de fusibles")
        if self.activo is not None:
            partes.append(f"{EVENTOS[self.activo]['nombre']} · "
                          f"{max(0, self.restante_ms) // 1000 + 1} s")
        return "   |   ".join(partes) or None

    def color(self):
        return EVENTOS[self.activo or "apagon"]["color"]

    def _sonar(self, nombre, volumen=1.0):
        if hasattr(self.juego, "sonar"):
            self.juego.sonar(nombre, volumen)

    def _decir(self, evento):
        if hasattr(self.juego, "decir"):
            self.juego.decir(evento, None, True)


# -- Dibujo ------------------------------------------------------------------------

def dibujar_cajas(screen, offset, camara, eventos, tiempo_ms):
    """Las cajas de fusibles, en el piso. La buena parpadea en rojo en un apagón."""
    if eventos is None:
        return
    for caja in eventos.cajas:
        rect = caja["rect"]
        if not rect.inflate(80, 80).colliderect(camara):
            continue
        r = rect.move(-offset[0], -offset[1])
        buena = eventos.apagon and caja is eventos.caja
        pygame.draw.rect(screen, (10, 12, 20), r.move(3, 3), border_radius=4)
        pygame.draw.rect(screen, (96, 104, 120), r, border_radius=4)
        pygame.draw.rect(screen, (40, 44, 58), r, 2, border_radius=4)
        # Rayo pintado en la tapa.
        cx, cy = r.center
        pygame.draw.lines(screen, (255, 214, 64), False,
                          [(cx + 3, cy - 12), (cx - 5, cy + 1), (cx + 4, cy + 1), (cx - 3, cy + 13)], 3)
        if buena:
            luz = (255, 70, 60) if (tiempo_ms // 350) % 2 else (110, 30, 30)
        else:
            luz = (96, 200, 120) if not eventos.apagon else (60, 70, 80)
        pygame.draw.circle(screen, luz, (r.right - 8, r.top + 8), 4)
        if buena and caja["progreso"] > 0:
            barra = pygame.Rect(r.x, r.bottom + 4, int(r.width * caja["progreso"]), 5)
            pygame.draw.rect(screen, COLOR_BIEN, barra)


def dibujar_brillo_caja(screen, offset, dueño, eventos, tiempo_ms):
    """Encima de la oscuridad: la luz roja de la caja buena se ve de lejos."""
    if eventos is None or not eventos.apagon or eventos.caja is None:
        return
    centro = eventos.caja["rect"].center
    if math.dist(centro, dueño.hitbox.center) > DISTANCIA_BRILLO_CAJA:
        return
    if (tiempo_ms // 350) % 2 == 0:
        return
    r = eventos.caja["rect"].move(-offset[0], -offset[1])
    brillo = pygame.Surface((40, 40), pygame.SRCALPHA)
    pygame.draw.circle(brillo, (255, 70, 60, 80), (20, 20), 18)
    pygame.draw.circle(brillo, (255, 90, 70, 255), (20, 20), 4)
    screen.blit(brillo, (r.right - 8 - 20, r.top + 8 - 20))


def dibujar_flecha_caja(screen, vista, camara, dueño, eventos, tiempo_ms):
    """En un apagón, en cualquier dificultad: la flecha roja hacia la caja de
    fusibles que hay que encender (screens/flechas.py). Si la caja ya se ve,
    un aro rojo encima de ella; la flecha solo sale si queda en el borde."""
    if eventos is None or not eventos.apagon or eventos.caja is None:
        return
    if dueño.preso or getattr(dueño, "eliminado", False):
        return
    x, y = eventos.caja["rect"].center
    texto = "Caja de fusibles"
    if camara.collidepoint(x, y):
        centro = (int(x - camara.x + vista.x), int(y - camara.y + vista.y))
        radio = 38 + int(5 * math.sin(tiempo_ms / 180))
        pygame.draw.circle(screen, COLOR_FLECHA_CAJA, centro, radio, 3)
        img = fuente_de_tamano(14).render(texto, True, COLOR_FLECHA_CAJA)
        fondo = pygame.Surface((img.get_width() + 10, img.get_height() + 4), pygame.SRCALPHA)
        fondo.fill((14, 15, 28, 180))
        r = fondo.get_rect(midbottom=(centro[0], centro[1] - radio - 4))
        r.clamp_ip(vista.inflate(-8, -8))
        screen.blit(fondo, r)
        screen.blit(img, img.get_rect(center=r.center))
        if not cerca_del_borde(vista, centro):
            return
    # Si el objetivo ya está en pantalla (en el borde), su letrero ya salió
    # encima del aro: la flecha va sin texto para no repetirlo.
    flecha_alrededor(screen, vista, camara, dueño, (x, y), COLOR_FLECHA_CAJA,
                     None if camara.collidepoint(x, y) else texto, tiempo_ms)
