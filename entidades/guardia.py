"""El Guardia: un alien enorme, como una roca, que protege la cápsula.

Idea de Diego para darle misión al Resonante y al Biomante. Hay uno solo, en
la sala de la cápsula (la Bahía en MapaFinal), y nunca sale de ella: se pone
con el editor de mapa (herramienta "Guardia", su puesto frente a la cápsula).

- Lo ve todo dentro de su sala (no tiene cono): a quien entre, lo persigue
  despacio, sin salir de la sala, y si lo alcanza con los brazos lo atrapa.
  Es un cuerpo sólido: los jugadores no lo atraviesan.
- No le hacen nada el hackeo, el señuelo ni el infiltrado: es una roca.
- **Distraerlo un rato** (Resonante): `distraer()`. Se va a un rincón de la
  Bahía a escuchar la señal y, mientras dura, no ve a nadie: hay que
  reparar la cápsula rápido y salir. Lo hace la Sintonía (de cerca, tecla de
  interactuar, misiones/guardia.py) o una Emisión que caiga en su sala.
- **Quitarlo para siempre**: `alimentar()` con la fruta de la planta de la
  Biosfera. Se va a su rincón y se queda comiendo; ya no persigue a nadie.

Su comportamiento es un árbol binario de decisión, como el de los demás
(data/comportamiento_guardia.py); aquí se responden sus preguntas (percibir)
y se ejecutan sus hojas (_ejecutar). Se dibuja con formas (`figura_guardia`).
"""

import math

import pygame

from entidades.alien import Alien, _distancia
from Estructuras.arbol_comportamiento import ArbolComportamiento
from data.comportamiento_guardia import ARBOL_GUARDIA
from juego.fuentes import fuente_de_tamano

ALCANCE_BRAZOS = 112           # a esta distancia (centro a centro) atrapa
DISTANCIA_ESPERA = 120         # se para a esto del que le trae la fruta (se la dan a ≤ 170)
CUERPO = (150, 60)             # lo que no se puede atravesar (alrededor de los pies)
DISTRACCION_MS = 18000         # Sintonía del Resonante, de cerca
DISTRACCION_EMISION_MS = 9000  # una Emisión que cae en su sala
DESCANSO_TRAS_ATRAPAR_MS = 3000
MARGEN_RINCON = 110            # qué tan pegado a la pared se va a su rincón


class Guardia(Alien):
    def __init__(self, juego, numero, puesto, area, capsula=None):
        """`puesto`: donde vigila (px del mundo); `area`: los Rect de su sala
        (no sale de ellos); `capsula`: el Rect de la cápsula (para escoger el
        rincón más lejos de ella)."""
        super().__init__(numero, [puesto], ArbolComportamiento(ARBOL_GUARDIA), "guardia")
        self.juego = juego
        self.nombre = "El Guardia"
        self.puesto = (int(puesto[0]), int(puesto[1]))
        self.area = [r.copy() for r in area] or [pygame.Rect(0, 0, 1400, 1000).move(
            self.puesto[0] - 700, self.puesto[1] - 500)]
        self.capsula = capsula
        self.comiendo = False
        self.distraido_ms = 0
        self.quien_distrajo = None
        self.presa = None
        self.con_fruta = None        # quién le trae la fruta (lo espera, no lo ataca)
        self.angulo = math.pi / 2          # mira hacia abajo (hacia la entrada)
        self.rincon = self._buscar_rincon()

    # -- Su sala ------------------------------------------------------------------

    def en_area(self, punto):
        return any(r.collidepoint(punto) for r in self.area)

    def _buscar_rincon(self):
        """El punto de su sala más lejos de la cápsula (y de su puesto): ahí
        se va a escuchar la señal o a comer."""
        mundo = getattr(self.juego, "mundo", None)
        ref = self.capsula.center if self.capsula is not None else self.puesto
        candidatos = []
        for r in self.area:
            adentro = r.inflate(-2 * MARGEN_RINCON, -2 * MARGEN_RINCON)
            if adentro.width <= 0 or adentro.height <= 0:
                adentro = pygame.Rect(r.center, (1, 1))
            for p in (adentro.topleft, adentro.topright, adentro.bottomleft, adentro.bottomright,
                      adentro.midleft, adentro.midright, adentro.midbottom):
                candidatos.append(p)
        # Lejos de la cápsula, pero no tapando una entrada de la sala.
        salas = getattr(self.juego, "salas", ())
        entradas = [r for n, r in salas if n.lower() == "pasillo"
                    and any(r.inflate(16, 16).colliderect(a) for a in self.area)]

        def tapa_entrada(p):
            return any(_distancia(p, (min(max(p[0], e.left), e.right), min(max(p[1], e.top), e.bottom))) < 280
                       for e in entradas)

        candidatos.sort(key=lambda p: (tapa_entrada(p), -_distancia(p, ref)))
        for p in candidatos:
            if mundo is None:
                return p
            rect = self.hitbox.copy()
            rect.center = p
            if not mundo.colisiona(rect) and self._camino_directo(p, mundo):
                return p
        return self.puesto

    def _camino_directo(self, p, mundo):
        return mundo.linea_libre(self.puesto, p, self.hitbox.width, self.hitbox.height, paso=12)

    @property
    def cuerpo(self):
        """Lo sólido del Guardia: los jugadores no pasan a través."""
        r = pygame.Rect(0, 0, *CUERPO)
        r.midbottom = (self.hitbox.centerx, self.hitbox.bottom + 6)
        return r

    @property
    def distraido(self):
        return self.distraido_ms > 0

    @property
    def inofensivo(self):
        return self.comiendo or self.distraido

    # -- Lo que le hacen los jugadores ----------------------------------------------

    def distraer(self, ms, quien=None):
        """La Sintonía (o una Emisión en su sala) lo distrae `ms` milisegundos."""
        if self.comiendo:
            return False
        self.distraido_ms = max(self.distraido_ms, ms)
        self.quien_distrajo = quien
        self.presa = None
        if quien is not None:
            from misiones.logros import logro
            logro(self.juego, "canto_de_sirena", quien)
        return True

    def alimentar(self, jugador=None):
        """Le dieron la fruta: se va a su rincón a comer, para siempre."""
        if self.comiendo:
            return False
        self.comiendo = True
        self.distraido_ms = 0
        self.presa = None
        if jugador is not None:
            from misiones.logros import logro
            logro(self.juego, "buen_provecho", jugador)
        return True

    def aturdir(self, ms):
        return                   # el hackeo no le hace nada: es una roca

    def confundir(self, ms):
        return

    def oir(self, punto):
        """Ni el señuelo ni los latidos lo mueven de su puesto. (Una Emisión
        que cae en su sala sí lo distrae: acciones_rol.poner_emision llama a
        `distraer`.)"""
        return False

    # -- Percepción ------------------------------------------------------------------

    def percibir(self, jugadores, mundo, escondites=()):
        self.presa = None
        self.con_fruta = None
        if not self.inofensivo:
            choca = getattr(mundo, "colisiona_alien", None)
            intrusos = [j for j in jugadores
                        if j.cazable and not j.escondido and self.en_area(j.hitbox.center)
                        and (mundo.linea_libre(self.centro, j.hitbox.center, colisiona=choca)
                             if choca else True)]
            # Al que trae la fruta no lo ataca: lo espera. A los demás, sí.
            con_fruta = [j for j in intrusos if "fruta" in getattr(j, "objetos", ())]
            sin_fruta = [j for j in intrusos if j not in con_fruta]
            cerca = lambda j: _distancia(self.centro, j.hitbox.center)
            self.presa = min(sin_fruta, key=cerca, default=None)
            self.con_fruta = min(con_fruta, key=cerca, default=None)
        self.objetivo = self.presa
        return {
            "comiendo": self.comiendo,
            "distraido": self.distraido,
            "recuperandose": self.descanso_ms > 0,
            "intruso_al_alcance": (self.presa is not None and
                                   _distancia(self.centro, self.presa.hitbox.center) <= ALCANCE_BRAZOS),
            "hay_intruso": self.presa is not None,
            "le_traen_fruta": self.con_fruta is not None,
            "lejos_del_puesto": _distancia(self.centro, self.puesto) > 24,
        }

    def actualizar(self, dt, mundo, jugadores, al_atrapar=None, escondites=(), al_revisar=None):
        self.distraido_ms = max(0, self.distraido_ms - dt)
        super().actualizar(dt, mundo, jugadores, al_atrapar, escondites, al_revisar)

    # -- Acciones ----------------------------------------------------------------------

    def _ejecutar(self, accion, dt, factor, mundo, al_atrapar, al_revisar=None):
        if accion in ("COMER", "ESCUCHAR"):
            if self._ir_hacia(self.rincon, self.datos["vel_investigar"] * factor, dt, mundo, 14):
                # Llegó: mira hacia el centro de la sala.
                self.angulo = math.atan2(self.puesto[1] - self.centro[1],
                                         self.puesto[0] - self.centro[0])
            return
        if accion == "DESCANSAR":
            return
        if accion == "ATRAPAR":
            presa = self.presa
            if presa is not None and al_atrapar is not None:
                al_atrapar(presa, self)
            self.descanso_ms = DESCANSO_TRAS_ATRAPAR_MS
            self.presa = None
            return
        if accion == "PERSEGUIR":
            destino = self.presa.hitbox.center
            if not self.en_area(destino):
                return
            self._ir_hacia(destino, self.datos["vel_perseguir"] * factor, dt, mundo, 4)
            if not self.en_area(self.centro):     # nunca sale de su sala
                self.hitbox.center = self._ultimo_adentro
            return
        if accion == "ESPERAR_FRUTA":
            # Se le acerca (sin salir de su sala) y se queda esperando, mirándolo.
            quien = self.con_fruta.hitbox.center
            if _distancia(self.centro, quien) > DISTANCIA_ESPERA and self.en_area(quien):
                self._ir_hacia(quien, self.datos["vel_patrulla"] * factor, dt, mundo, DISTANCIA_ESPERA)
                if not self.en_area(self.centro):
                    self.hitbox.center = self._ultimo_adentro
            self.angulo = math.atan2(quien[1] - self.centro[1], quien[0] - self.centro[0])
            return
        if accion == "VOLVER":
            self._ir_hacia(self.puesto, self.datos["vel_patrulla"] * factor, dt, mundo, 8)
            return
        if accion == "VIGILAR":
            # Mira de un lado al otro, despacio.
            self.angulo = math.pi / 2 + math.sin(self.tiempo_ms / 1400) * 0.9

    def _ir_hacia(self, destino, velocidad, dt, mundo, tolerancia=10):
        if self.en_area(self.centro):
            self._ultimo_adentro = self.centro
        return super()._ir_hacia(destino, velocidad, dt, mundo, tolerancia)

    # -- Dibujo -------------------------------------------------------------------------

    def _estado_figura(self):
        if self.comiendo and not self.moviendose:
            return "come"
        if self.distraido and not self.moviendose:
            return "escucha"
        return "camina" if self.moviendose else "quieto"

    def _imagen(self):
        izquierda = math.cos(self.angulo) < 0
        estado = self._estado_figura()
        velocidad = {"camina": 180, "come": 260, "escucha": 420}.get(estado, 600)
        fase = int(self.tiempo_ms / velocidad) % (2 if estado != "camina" else 4)
        return figura_guardia(estado, fase, izquierda)

    def _caja_figura(self, offset):
        imagen = self._imagen()
        return imagen.get_rect(midbottom=(self.hitbox.centerx - offset[0],
                                          self.hitbox.bottom - offset[1] + 12))

    def dibujar(self, screen, offset):
        imagen = self._imagen()
        rect = self._caja_figura(offset)
        sombra = pygame.Rect(0, 0, int(rect.width * 0.8), 28)
        sombra.center = (rect.centerx, self.hitbox.bottom - offset[1] + 2)
        pygame.draw.ellipse(screen, (10, 11, 16), sombra)
        screen.blit(imagen, rect)
        estado = self._estado_figura()
        if estado == "escucha":
            # Notitas que suben: está escuchando la señal del Resonante.
            for i in range(3):
                t = (self.tiempo_ms / 900 + i / 3) % 1
                x = rect.centerx + int(math.sin(t * 6 + i) * 22) + (i - 1) * 18
                y = rect.y - 6 - int(t * 46)
                _nota(screen, (x, y), (150, 200, 255))
        elif self.accion == "ESPERAR_FRUTA" and not self.moviendose:
            # Espera la fruta: una fruta que late sobre su cabeza.
            r = 7 + (1 if (self.tiempo_ms // 300) % 2 else 0)
            centro = (rect.centerx, rect.y - 14)
            pygame.draw.circle(screen, (24, 20, 16), centro, r + 2)
            pygame.draw.circle(screen, FRUTA, centro, r)
            pygame.draw.line(screen, MUSGO, (centro[0], centro[1] - r), (centro[0] + 4, centro[1] - r - 5), 2)
        elif estado == "come" and (self.tiempo_ms // 520) % 3 == 0:
            f = fuente_de_tamano(18)
            img = f.render("ñam", True, (255, 214, 140))
            screen.blit(img, (rect.centerx + 24, rect.y + 6))

    def dibujar_vision(self, screen, offset):
        return          # no tiene cono: ve toda su sala

    def dibujar_senal(self, screen, offset):
        if self.comiendo:
            return
        if self.distraido:
            return       # las notitas ya lo dicen
        super().dibujar_senal(screen, offset)


def _nota(screen, pos, color):
    x, y = pos
    pygame.draw.circle(screen, color, (x, y + 8), 4)
    pygame.draw.line(screen, color, (x + 3, y + 8), (x + 3, y - 4), 2)
    pygame.draw.line(screen, color, (x + 3, y - 4), (x + 9, y - 1), 2)


# -- Su figura (formas, hasta que haya arte) ------------------------------------------

ANCHO_FIGURA, ALTO_FIGURA = 96, 104
ESCALA_FIGURA = 2.4
ROCA = (118, 124, 104)
ROCA_OSCURA = (78, 84, 68)
ROCA_CLARA = (156, 162, 138)
MUSGO = (88, 132, 70)
CONTORNO = (22, 24, 18)
OJO = (255, 186, 70)
FRUTA = (232, 84, 60)
_figuras = {}


def figura_guardia(estado="quieto", fase=0, izquierda=False):
    """El Guardia mirando a la derecha (o a la izquierda): una mole de piedra
    con musgo, cabeza hundida entre los hombros, brazos hasta el piso.
    `estado`: quieto, camina, come (sentado, con la fruta) o escucha."""
    clave = (estado, fase, izquierda)
    if clave in _figuras:
        return _figuras[clave]
    s = pygame.Surface((ANCHO_FIGURA, ALTO_FIGURA), pygame.SRCALPHA)
    sentado = estado == "come"
    respira = 1 if (estado == "quieto" and fase) else 0
    bob = (1 if fase % 2 else 0) if estado == "camina" else 0
    ladeo = (-3 if fase else 3) if estado == "escucha" else 0
    base = ALTO_FIGURA - 2
    alto_cuerpo = 62 if sentado else 70
    top = base - alto_cuerpo - (0 if sentado else 18) + respira + bob

    # Piernas (cortas y gruesas) o, sentado, las rodillas.
    if sentado:
        for x in (30, 58):
            pygame.draw.ellipse(s, ROCA_OSCURA, (x - 4, base - 18, 26, 18))
            pygame.draw.ellipse(s, CONTORNO, (x - 4, base - 18, 26, 18), 2)
    else:
        paso = (3 if fase in (1, 2) else -3) if estado == "camina" else 0
        for i, x in enumerate((30, 54)):
            dx = paso if i == 0 else -paso
            pierna = pygame.Rect(x + dx, base - 24, 18, 24)
            pygame.draw.rect(s, ROCA_OSCURA, pierna, border_radius=5)
            pygame.draw.rect(s, CONTORNO, pierna, 2, border_radius=5)

    # Cuerpo: una roca redonda, más ancha arriba (hombros).
    cuerpo = pygame.Rect(14 + ladeo, top, 70, alto_cuerpo)
    pygame.draw.ellipse(s, ROCA, cuerpo)
    pygame.draw.ellipse(s, ROCA_CLARA, cuerpo.inflate(-26, -30).move(-6, -10))
    pygame.draw.ellipse(s, ROCA, cuerpo.inflate(-16, -16).move(4, 6))
    # Grietas y placas.
    for (x0, y0, x1, y1) in ((30, 18, 40, 34), (40, 34, 36, 48), (60, 22, 52, 40), (52, 40, 58, 54)):
        pygame.draw.line(s, ROCA_OSCURA, (cuerpo.x + x0 - 14, cuerpo.y + y0 - 6),
                         (cuerpo.x + x1 - 14, cuerpo.y + y1 - 6), 2)
    # Musgo en los hombros.
    for (x, y, r) in ((22, 6, 9), (34, 2, 8), (62, 4, 9), (74, 10, 7)):
        pygame.draw.circle(s, MUSGO, (cuerpo.x + x - 14 + 6, cuerpo.y + y + 2), r)
    pygame.draw.ellipse(s, CONTORNO, cuerpo, 2)

    # Cabeza hundida entre los hombros, adelante (a la derecha).
    cabeza = pygame.Rect(0, 0, 30, 24)
    cabeza.center = (cuerpo.centerx + 16, cuerpo.y + 16 + (2 if sentado else 0))
    pygame.draw.ellipse(s, ROCA_OSCURA, cabeza)
    pygame.draw.ellipse(s, CONTORNO, cabeza, 2)
    for dx in (-5, 6):
        pygame.draw.circle(s, OJO, (cabeza.centerx + dx, cabeza.centery - 2), 3)
        pygame.draw.circle(s, (255, 240, 200), (cabeza.centerx + dx, cabeza.centery - 3), 1)
    boca_abierta = sentado and fase == 1
    boca = pygame.Rect(0, 0, 12, 6 if boca_abierta else 3)
    boca.center = (cabeza.centerx + 1, cabeza.bottom - 6)
    pygame.draw.rect(s, (40, 20, 18), boca, border_radius=2)

    # Brazos: largos, con los nudillos casi en el piso (o la fruta en la boca).
    if sentado:
        mano = (cabeza.centerx + 4, cabeza.bottom - 2 + (0 if fase else 6))
        pygame.draw.line(s, ROCA_OSCURA, (cuerpo.right - 10, cuerpo.y + 26), mano, 12)
        pygame.draw.circle(s, FRUTA, (mano[0] + 4, mano[1] - 4), 8 if fase == 0 else 6)
        pygame.draw.line(s, MUSGO, (mano[0] + 4, mano[1] - 12), (mano[0] + 7, mano[1] - 16), 2)
        pygame.draw.circle(s, ROCA, mano, 7)
        pygame.draw.circle(s, CONTORNO, mano, 7, 2)
    else:
        balanceo = (4 if fase in (0, 1) else -4) if estado == "camina" else 0
        for hombro_x, dx in ((cuerpo.x + 8, -balanceo), (cuerpo.right - 8, balanceo)):
            mano = (hombro_x + (6 if hombro_x > cuerpo.centerx else -6) + dx, base - 10)
            pygame.draw.line(s, ROCA_OSCURA, (hombro_x, cuerpo.y + 20), mano, 13)
            pygame.draw.line(s, CONTORNO, (hombro_x, cuerpo.y + 20), mano, 1)
            pygame.draw.circle(s, ROCA, mano, 9)
            pygame.draw.circle(s, CONTORNO, mano, 9, 2)

    if izquierda:
        s = pygame.transform.flip(s, True, False)
    s = pygame.transform.scale(s, (int(ANCHO_FIGURA * ESCALA_FIGURA), int(ALTO_FIGURA * ESCALA_FIGURA)))
    _figuras[clave] = s
    return s
