"""Un jugador de la partida: su personaje, su rol, sus puntos y su progresión.

Antes `Game.jugadores` era una lista de `Personaje`. Ahora cada entrada es un
`Jugador`, que envuelve al personaje y le agrega todo lo que es del jugador y
no del muñeco: el rol, los puntos, su árbol de habilidades y el panel que
tenga abierto en su mitad de la pantalla.

Cada jugador tiene su propio juego de teclas, incluidas las de navegar los
paneles, porque la partida es local y los dos juegan en el mismo teclado: si
compartieran las teclas de elegir opción, uno le respondería los diálogos al
otro.
"""

from collections import Counter, defaultdict

import pygame

from Estructuras.arbol_habilidades import construir_arbol
from data.habilidades import ARBOLES_POR_ROL
from data.roles import ROLES_POR_NOMBRE
from juego.oscuridad import Linterna
from juego.mandos import tecla_virtual, es_virtual, nombre_boton, tipo_de


# Teclas de cada PUESTO, no de cada rol: el rol se escoge al empezar la
# partida, así que ya no se puede repartir el teclado por rol. El puesto 1
# juega con WASD, el 2 con las flechas.
#
# Los puestos 3 y 4 juegan con mando (mandos.py): cada botón es una "tecla
# virtual" que va al final de cada tupla. Las letras de teclado que tienen
# delante (I/K/O, T/G/Y...) siguen sirviendo para escoger rol sin mando; sin
# mando, en partida no se mueven.
# "habilidades" abre el panel del árbol; "habilidad" USA la habilidad activa
# que se haya escogido (ver acciones_rol.py). "celular" abre NEXUS (celular.py).
TECLAS_PUESTO_1 = {
    "arriba": (pygame.K_w,),
    "abajo": (pygame.K_s,),
    "interactuar": (pygame.K_e,),
    "habilidades": (pygame.K_q,),
    "habilidad": (pygame.K_f,),
    "sigilo": (pygame.K_LSHIFT,),
    "celular": (pygame.K_TAB,),
    "soltar": (pygame.K_x,),             # soltar algo del inventario al piso
    # Izquierda/derecha solo sirven en menús del jugador (pestañas del celular);
    # para caminar se usan los controles del personaje.
    "izquierda": (pygame.K_a,),
    "derecha": (pygame.K_d,),
}

TECLAS_PUESTO_2 = {
    "arriba": (pygame.K_UP,),
    "abajo": (pygame.K_DOWN,),
    "interactuar": (pygame.K_RETURN, pygame.K_KP_ENTER),
    "habilidades": (pygame.K_RSHIFT,),
    # La tecla "-" (junto al Shift derecho en los teclados en español; en los
    # de inglés es "/"). Ctrl derecho queda de respaldo: no todos los portátiles
    # lo tienen.
    "habilidad": (pygame.K_MINUS, pygame.K_SLASH, pygame.K_RCTRL),
    # AltGr en los teclados en español (SDL lo reporta como RALT o MODE), o
    # el 0 del teclado numérico, que queda junto a las flechas.
    "sigilo": (pygame.K_RALT, pygame.K_MODE, pygame.K_KP0),
    # El punto, junto al "-" de la habilidad (o el del teclado numérico).
    "celular": (pygame.K_PERIOD, pygame.K_KP_PERIOD),
    # La coma, junto al punto del celular.
    "soltar": (pygame.K_COMMA,),
    "izquierda": (pygame.K_LEFT,),
    "derecha": (pygame.K_RIGHT,),
}

def _con_mando(puesto, teclado):
    return {accion: tuple(teclas) + (tecla_virtual(puesto, accion),)
            for accion, teclas in teclado.items()}


TECLAS_PUESTO_3 = _con_mando(2, {
    "arriba": (pygame.K_i,),
    "abajo": (pygame.K_k,),
    "interactuar": (pygame.K_o,),
    "habilidades": (pygame.K_u,),
    "habilidad": (pygame.K_p,),
    "sigilo": (),
    "celular": (pygame.K_j,),
    "soltar": (pygame.K_l,),
    "izquierda": (),
    "derecha": (),
})

TECLAS_PUESTO_4 = _con_mando(3, {
    "arriba": (pygame.K_t,),
    "abajo": (pygame.K_g,),
    "interactuar": (pygame.K_y,),
    "habilidades": (pygame.K_r,),
    "habilidad": (pygame.K_v,),
    "sigilo": (),
    "celular": (pygame.K_b,),
    "soltar": (pygame.K_n,),
    "izquierda": (),
    "derecha": (),
})

TECLAS_POR_PUESTO = [TECLAS_PUESTO_1, TECLAS_PUESTO_2, TECLAS_PUESTO_3, TECLAS_PUESTO_4]

# Cómo se llama su esquema de control en pantalla.
NOMBRE_CONTROLES = ["WASD", "Flechas", "Mando 1 (I/K/O)", "Mando 2 (T/G/Y)"]
# Los esquemas de control (el índice en TECLAS_POR_PUESTO): cada jugador
# escoge uno (pantalla "controles", app.py) y dos no pueden tener el mismo.
# Sin escoger, el jugador N usa el esquema N.
WASD, FLECHAS, MANDO_1, MANDO_2 = range(4)
NOMBRE_ESQUEMA = ["WASD", "Flechas", "Mando 1", "Mando 2"]

# Puestos que solo se mueven si tienen un mando conectado.
PUESTOS_SIN_MOVIMIENTO = (2, 3)

# Cuánto dura el mensajito de feedback ("+15 puntos") sobre el personaje.
DURACION_MENSAJE_MS = 2200

# -- Pulso -------------------------------------------------------------------
# El pulso va de 0 a 100 y decide cuánto ruido hace el jugador: un alien que
# esté dentro de `radio_ruido` lo oye aunque no lo vea. Sube cuando hay un
# alien cerca (más entre más cerca) y se dispara si un alien lo está viendo;
# baja cuando está lejos y quieto.
PULSO_REPOSO = 18          # quieto y sin aliens cerca
PULSO_EXTRA_CAMINANDO = 12
PULSO_POR_CERCANIA = 62    # cuánto suma un alien pegado a él
DISTANCIA_QUE_ASUSTA = 400 # a partir de aquí un alien ya no sube el pulso
PULSO_SUBE_POR_S = 34
PULSO_BAJA_POR_S = 11
RADIO_RUIDO_BASE = 40
RADIO_RUIDO_POR_PULSO = 2.6

# Escondido, el latido se oye menos: el radio de ruido se multiplica por esto.
FACTOR_RUIDO_ESCONDIDO = 0.55

# Caminar normal hace ruido de pasos además del latido; en sigilo (tecla
# mantenida) se va a la mitad de velocidad, sin pasos y con el ruido reducido.
RUIDO_PASOS = 45
FACTOR_RUIDO_SIGILO = 0.6
FACTOR_VELOCIDAD_SIGILO = 0.5
PULSO_EXTRA_SIGILO = 3

# Vidas: cada vez que lo atrapan pierde una. Sin vidas queda eliminado: ya no
# vuelve a la partida (ni de la celda). La Biomante puede devolver vidas.
VIDAS_INICIALES = 3

# Después de que lo atrapan, un rato en que los aliens no lo persiguen, para
# que no lo vuelvan a atrapar apenas reaparece.
INVULNERABLE_MS = 2500

# Teclado "todo suelto": se le pasa a Personaje.actualizar cuando el jugador
# tiene un panel abierto, para que siga animándose quieto en vez de caminar
# mientras lee. Es un defaultdict porque Personaje indexa por código de tecla.
SIN_TECLAS = defaultdict(bool)


class Inventario(Counter):
    """Los consumibles que lleva un jugador, con cuántos de cada uno.

    Se usa como antes se usaba el set: `"kit" in objetos`, `objetos.add(...)`,
    `objetos.discard(...)`; pero ahora puede llevar varios del mismo.
    """

    def add(self, tipo, cantidad=1):
        self[tipo] += cantidad

    def discard(self, tipo):
        if self[tipo] > 0:
            self[tipo] -= 1
        if self[tipo] <= 0:
            # dict.pop y no `del self[tipo]`: Counter.__delitem__ pregunta
            # `tipo in self`, que aquí (__contains__ de abajo) es False con 0, y
            # entonces no borraba nada: quedaba {"fruta": 0} en el inventario.
            dict.pop(self, tipo, None)

    def __contains__(self, tipo):
        return self.get(tipo, 0) > 0


class Jugador:
    def __init__(self, personaje, rol, puesto=0, con_mando=False, esquema=None):
        self.personaje = personaje
        self.puesto = puesto          # su lugar: su mitad (o cuarto) de la pantalla
        # Con qué juega (WASD, flechas, mando 1 o 2): por defecto, el de su puesto.
        self.esquema = puesto % len(TECLAS_POR_PUESTO) if esquema is None else esquema
        self.teclas = TECLAS_POR_PUESTO[self.esquema]
        self.con_mando = con_mando
        self.controles_nombre = (f"Mando {self.esquema - 1}" if con_mando
                                 else NOMBRE_CONTROLES[self.esquema])
        self.puede_moverse = self.esquema not in PUESTOS_SIN_MOVIMIENTO or con_mando

        self.puntos = 0
        self.tareas_hechas = 0
        self.rol = None
        self.objetivo = ""
        self.arbol = construir_arbol("", None)
        self.asignar_rol(rol)

        # Panel abierto en su viewport (None = está caminando por el mapa).
        self.panel = None
        self.cursor = 0

        # La sala donde está (juego/salas.py), para el HUD.
        self.sala = None
        self.sala_cambio_ms = 0

        # Mensaje corto de feedback y su tiempo restante.
        self.mensaje = ""
        self.mensaje_color = (255, 255, 255)
        self.mensaje_ms = 0

        # Zona del mapa sobre la que está parado, para la pista de "presiona E".
        self.zona_cerca = None

        # Pulso (ver PULSO_* arriba) y la fase de su latido, que solo sirve
        # para animar el corazón del HUD al ritmo del pulso.
        self.sigilo = False          # mantiene la tecla de sigilo
        self.linterna = Linterna()   # hacia dónde alumbra (oscuridad.py)
        self.velocidad_base = personaje.velocidad
        self.pulso = float(PULSO_REPOSO)
        self.fase_latido = 0.0
        self.visto = False
        self.spawn = None            # dónde reaparece si lo atrapan

        # Escondites: en cuál está metido (None = afuera), cuál tiene cerca
        # para la pista de "presiona E", y el minijuego si un alien lo revisa.
        self.escondite = None
        self.escondite_cerca = None
        self.minijuego = None

        # Habilidades del rol (acciones_rol.py): recarga de la activa, efectos
        # con tiempo (nombre -> ms restantes), piezas del Forjador y la
        # estación que tiene enfrente, para la pista de "presiona E".
        self.recarga_ms = 0
        self.efectos = {}
        self.piezas = 0
        self.estacion_cerca = None

        # Misión (mision.py): la celda donde está encerrado (None = libre), los
        # consumibles que lleva ("decodificador", "kit"), lo que está haciendo
        # con la tecla mantenida (texto, 0 a 1) y el equipo con el que suma
        # puntos para las habilidades.
        self.preso = None
        self.objetos = Inventario()
        self.progreso = None
        self.equipo = None
        self.pista_mision = None
        self.susto_ms = 0            # cuánto le queda al susto de ser atrapado
        self.susto_total_ms = 0      # cuánto dura el susto actual (ambiente.py)
        self.susto_tipo = "alien"    # "alien", "ciego", "cazador", "vigia", "cf_revela" o "cf_captura"
        self.susto_disfraz = None    # sprite del prisionero que imitaba el Cambiaformas
        self.sin_linterna_ms = 0     # la Sombra le apagó la linterna (sombra.py)
        self.vidas = VIDAS_INICIALES
        self.vidas_max = VIDAS_INICIALES     # la dificultad lo cambia (dificultad.py)
        self.vidas_infinitas = False         # dificultad Fácil: atrapar no quita vidas
        self.eliminado = False       # sin vidas: fuera de la partida
        self.vida_cambio_ms = 0      # para que el corazón que cambia parpadee
        self.curacion_ms = 0         # recarga de la curación de la Biomante
        self.invulnerable_ms = 0
        self.veces_atrapado = 0

        # Línea extra del HUD, propia de cada rol (acciones_rol.linea_de_estado).
        self.info = ""

    def asignar_rol(self, rol):
        """Le da un rol al jugador y rearma lo que depende de él.

        Se llama al terminar la selección, no en el constructor, porque el
        jugador existe desde antes de que sepa qué va a jugar.
        """
        self.rol = rol
        self.objetivo = ROLES_POR_NOMBRE.get(rol, {}).get("objetivo", "")
        self.arbol = construir_arbol(rol, ARBOLES_POR_ROL.get(rol))

    # -- Estado ----------------------------------------------------------------

    @property
    def ocupado(self):
        """True si tiene un panel abierto: mientras tanto no camina."""
        return self.panel is not None

    def es_tecla(self, key, accion):
        return key in self.teclas.get(accion, ())

    def nombre_tecla(self, accion):
        """Nombre legible de su tecla, para las pistas en pantalla."""
        teclas = self.teclas.get(accion, ())
        if getattr(self, "con_mando", False) and any(es_virtual(t) for t in teclas):
            # El botón de SU mando: A en Xbox, Cruz en PlayStation...
            return nombre_boton(accion, self.tipo_mando)
        teclas = [t for t in teclas if not es_virtual(t)]
        if not teclas:
            return "?"
        nombres = {
            pygame.K_w: "W", pygame.K_s: "S", pygame.K_e: "E", pygame.K_q: "Q",
            pygame.K_UP: "ARRIBA", pygame.K_DOWN: "ABAJO",
            pygame.K_RETURN: "ENTER", pygame.K_KP_ENTER: "ENTER",
            pygame.K_RSHIFT: "SHIFT DER", pygame.K_RCTRL: "CTRL DER",
            pygame.K_f: "F", pygame.K_p: "P", pygame.K_v: "V",
            pygame.K_i: "I", pygame.K_k: "K", pygame.K_o: "O", pygame.K_u: "U",
            pygame.K_t: "T", pygame.K_g: "G", pygame.K_y: "Y", pygame.K_r: "R",
            pygame.K_LSHIFT: "SHIFT IZQ", pygame.K_RALT: "ALT GR",
            pygame.K_MINUS: "-", pygame.K_SLASH: "/",
            pygame.K_TAB: "TAB", pygame.K_PERIOD: ".", pygame.K_KP_PERIOD: ".",
            pygame.K_j: "J", pygame.K_b: "B", pygame.K_a: "A", pygame.K_d: "D",
            pygame.K_LEFT: "IZQ", pygame.K_RIGHT: "DER",
            pygame.K_x: "X", pygame.K_COMMA: ",", pygame.K_l: "L", pygame.K_n: "N",
        }
        return nombres.get(teclas[0], "?")

    @property
    def tipo_mando(self):
        """"xbox", "playstation" u "otro": el mando con el que juega (mandos.py)."""
        return tipo_de(getattr(self, "esquema", self.puesto))

    def pista_pestanas(self):
        """Cómo se nombran en pantalla las teclas para cambiar de pestaña."""
        if getattr(self, "con_mando", False):
            return "Stick"
        if pygame.K_LEFT in self.teclas.get("izquierda", ()):
            return "IZQ/DER"
        return f"{self.nombre_tecla('izquierda')}/{self.nombre_tecla('derecha')}"

    def pista_mover(self):
        """Cómo se nombra en pantalla el par de teclas para mover el cursor.

        Para el puesto de las flechas devuelve "Flechas" en vez de los nombres
        sueltos: la tipografía del juego (Determination Mono) **no trae los
        glifos de flecha** (U+2190-2193), así que escribir "↑/↓" salía como dos
        cuadritos vacíos. Las tildes y la ñ sí están; el problema era solo con
        las flechas.
        """
        if getattr(self, "con_mando", False):
            return "Stick"
        if pygame.K_UP in self.teclas.get("arriba", ()):
            return "Flechas"
        return f"{self.nombre_tecla('arriba')}/{self.nombre_tecla('abajo')}"

    # -- Pulso y aliens ------------------------------------------------------------

    @property
    def radio_ruido(self):
        """Hasta dónde se oye su latido, en píxeles del mundo."""
        radio = RADIO_RUIDO_BASE + self.pulso * RADIO_RUIDO_POR_PULSO
        if self.escondido:
            return radio * FACTOR_RUIDO_ESCONDIDO
        if self.sigilo:
            return radio * FACTOR_RUIDO_SIGILO
        if self.personaje.moviendose:
            radio += RUIDO_PASOS
        return radio

    @property
    def escondido(self):
        return self.escondite is not None

    def esconderse(self, escondite):
        """Se mete al escondite: deja de verse y de moverse."""
        self.escondite = escondite
        escondite["ocupante"] = self
        # Se para en la entrada, para que al salir quede en el mismo sitio.
        self.personaje.hitbox.center = escondite["rect"].center
        self.personaje.sync_sprite_from_hitbox()

    def salir_del_escondite(self):
        if self.escondite is not None:
            self.escondite["ocupante"] = None
        self.escondite = None
        self.minijuego = None

    @property
    def cazable(self):
        """Si los aliens lo pueden ver, oír y atrapar.

        Los puestos sin mando todavía no se mueven: si los aliens los cazaran,
        los atraparían una y otra vez sin que el jugador pudiera hacer nada.
        """
        return (self.puede_moverse and not self.eliminado
                and self.invulnerable_ms <= 0 and self.preso is None)

    @property
    def latidos_por_minuto(self):
        return int(60 + self.pulso * 1.1)

    def actualizar_pulso(self, dt, distancia_alien=None, visto=False):
        """Acerca el pulso a lo que "debería" ser con lo que está pasando.

        No salta de golpe: sube y baja a una velocidad fija, así que pasar
        rápido junto a un alien es menos peligroso que quedarse cerca.

        Mientras dura el minijuego del escondite el pulso lo mueve el
        minijuego (sube con la barra del alien, baja con los aciertos y sube
        con los fallos; ver minijuego_latidos.py): aquí únicamente avanza la
        animación del latido.
        """
        self.visto = visto
        self.invulnerable_ms = max(0, self.invulnerable_ms - dt)
        self.vida_cambio_ms = max(0, self.vida_cambio_ms - dt)
        segundos = dt / 1000
        if self.minijuego is not None:
            self.fase_latido = (self.fase_latido + self.latidos_por_minuto / 60 * segundos) % 1.0
            return

        objetivo = PULSO_REPOSO
        if self.personaje.moviendose:
            objetivo += PULSO_EXTRA_SIGILO if self.sigilo else PULSO_EXTRA_CAMINANDO
        if distancia_alien is not None and distancia_alien < DISTANCIA_QUE_ASUSTA:
            objetivo += PULSO_POR_CERCANIA * (1 - distancia_alien / DISTANCIA_QUE_ASUSTA)
        if visto:
            objetivo = 100

        if self.pulso < objetivo:
            self.pulso = min(objetivo, self.pulso + PULSO_SUBE_POR_S * segundos)
        else:
            self.pulso = max(objetivo, self.pulso - PULSO_BAJA_POR_S * segundos)
        self.pulso = max(0.0, min(100.0, self.pulso))

        self.fase_latido = (self.fase_latido + self.latidos_por_minuto / 60 * segundos) % 1.0

    def atrapado(self):
        """Lo atrapó un alien: pierde una vida y vuelve a su punto de inicio
        (después la misión lo mete en una celda)."""
        self.veces_atrapado += 1
        if not self.vidas_infinitas:
            self.vidas = max(0, self.vidas - 1)
        self.vida_cambio_ms = 1200
        self.invulnerable_ms = INVULNERABLE_MS
        self.pulso = 45.0
        self.cerrar_panel()
        self.salir_del_escondite()
        if self.spawn is not None:
            self.personaje.hitbox.topleft = self.spawn
            self.personaje.sync_sprite_from_hitbox()

    def eliminar(self):
        """Se quedó sin vidas: sale de la partida para siempre."""
        self.eliminado = True
        self.puede_moverse = False
        self.cerrar_panel()
        self.salir_del_escondite()
        self.progreso = None

    def curar(self, cantidad=1):
        """Recupera vidas (la Biomante). Devuelve cuántas recuperó."""
        if self.eliminado:
            return 0
        antes = self.vidas
        self.vidas = min(self.vidas_max, self.vidas + cantidad)
        if self.vidas != antes:
            self.vida_cambio_ms = 1200
        return self.vidas - antes

    # -- Puntos y mensajes ------------------------------------------------------

    def sumar_puntos(self, cantidad):
        self.puntos = max(0, self.puntos + int(cantidad))
        # Lo que gana cada uno también le suma al equipo, que es con lo que se
        # desbloquean las habilidades.
        if self.equipo is not None:
            self.equipo.sumar(int(cantidad))

    @property
    def puntos_para_habilidades(self):
        return self.equipo.puntos if self.equipo is not None else self.puntos

    def avisar(self, texto, color=(255, 255, 255)):
        self.mensaje = texto
        self.mensaje_color = color
        self.mensaje_ms = DURACION_MENSAJE_MS

    def actualizar_mensaje(self, dt):
        if self.mensaje_ms > 0:
            self.mensaje_ms = max(0, self.mensaje_ms - dt)
            if self.mensaje_ms == 0:
                self.mensaje = ""

    # -- Paneles ----------------------------------------------------------------

    def abrir_panel(self, panel):
        self.panel = panel
        self.cursor = 0

    def cerrar_panel(self):
        self.panel = None
        self.cursor = 0

    def mover_cursor(self, delta, total):
        if total <= 0:
            self.cursor = 0
            return
        self.cursor = (self.cursor + delta) % total

    # -- Atajos al personaje -----------------------------------------------------

    @property
    def hitbox(self):
        return self.personaje.hitbox

    def actualizar(self, teclas, colisiona):
        """Mueve al personaje, salvo que tenga un panel abierto, esté escondido
        o no tenga mando."""
        if self.ocupado or self.escondido or self.preso or not self.puede_moverse:
            self.sigilo = False
            self.personaje.actualizar(SIN_TECLAS, colisiona=colisiona)
            return
        self.sigilo = any(teclas[k] for k in self.teclas.get("sigilo", ()))
        self.personaje.velocidad = self.velocidad_base * (
            FACTOR_VELOCIDAD_SIGILO if self.sigilo else 1.0)
        self.personaje.actualizar(teclas, colisiona=colisiona)
        self.linterna.actualizar(self.personaje.direccion)

    def dibujar(self, screen, offset):
        if self.escondido or self.eliminado:
            return   # metido en el escondite (o eliminado): no se ve
        self.personaje.dibujar(screen, offset)
