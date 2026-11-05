"""La primera vez que se ve cada tipo de alien, se explica.

Cuando un tipo de alien que todavía no se presentó entra en la pantalla de un
jugador (dentro de su cámara y de su campo de visión, como se dibuja en
screens/partida.py), el juego se pausa y en la vista de ese jugador sale una
ventana que señala al alien y cuenta qué es y cómo funciona
(data/presentacion_aliens.py). Se cierra con interactuar, habilidad, Enter,
Espacio o Esc (o A en el mando) de cualquiera. Cada tipo se presenta una sola
vez por partida.

El Cambiaformas se presenta cuando ya se reveló y terminó su susto (nunca
disfrazado: eso arruinaría la sorpresa). Mientras alguien tiene un susto en
pantalla no se abre ninguna, para que no se tapen.

En todas las dificultades (`activa_en`, data/dificultad.PRESENTAR_ALIENS; sin dificultad, en las pruebas, no). La pausa la aplica
`Game._actualizar_partida`: mientras hay una ventana abierta no se mueve nada.
"""

import math

from juego import vision
from data.presentacion_aliens import PRESENTACION

MIN_ABIERTA_MS = 700        # antes no se cierra (por si alguien venía apretando una tecla)
ALCANCE_A_OSCURAS = 260     # en un apagón solo se ve lo que alumbra la linterna


def activa_en(dificultad):
    return dificultad is not None and getattr(dificultad, "presenta_aliens", False)


class PresentacionAliens:
    def __init__(self, juego):
        self.juego = juego
        self.presentados = set()     # tipos ya explicados
        self.actual = None           # {"tipo", "alien", "jugador", "ms"} con la ventana abierta

    @property
    def abierta(self):
        return self.actual is not None

    # -- Buscar a quién presentar -------------------------------------------------------

    def revisar(self):
        """Después de mover todo: ¿alguien tiene en pantalla un tipo nuevo?"""
        juego = self.juego
        if self.actual is not None or getattr(juego, "en_tutorial", False):
            return
        if any(getattr(j, "susto_ms", 0) > 0 for j in juego.jugadores):
            return
        candidatos = [a for a in getattr(juego, "aliens", ())
                      if a.tipo not in self.presentados and a.tipo in PRESENTACION
                      and self._se_puede_mostrar(a)]
        if not candidatos:
            return
        for jugador in juego.jugadores:
            # Escondido también lo ve (por la rendija), salvo en pleno minijuego:
            # ahí pausar le cortaría el ritmo.
            if (jugador.preso is not None or getattr(jugador, "eliminado", False)
                    or getattr(jugador, "minijuego", None) is not None
                    or not getattr(jugador, "puede_moverse", True)):
                continue
            for alien in candidatos:
                if self.ve_en_pantalla(jugador, alien):
                    self.abrir(jugador, alien)
                    return

    @staticmethod
    def _se_puede_mostrar(alien):
        if getattr(alien, "oculta", False):
            return False
        if alien.tipo == "cambiaformas":
            return (not getattr(alien, "disfrazado", False)
                    and getattr(alien, "transformando_ms", 0) <= 0)
        return True

    def ve_en_pantalla(self, jugador, alien):
        """Lo mismo que decide si el alien se dibuja en la vista del jugador:
        dentro de su cámara y de su campo de visión (y, en un apagón, cerca)."""
        juego = self.juego
        vista = self._vista_de(jugador)
        if vista is None:
            return False
        camara = juego.mundo.camara(jugador.hitbox.center, vista.width, vista.height)
        if not camara.colliderect(alien.hitbox):
            return False
        eventos = getattr(juego, "eventos", None)
        if eventos is not None and eventos.apagon and alien.tipo != "sombra":   # (de ella se ven los ojos)
            if math.dist(jugador.hitbox.center, alien.hitbox.center) > ALCANCE_A_OSCURAS:
                return False
        if getattr(juego, "oscuridad", True):
            campo = vision.campo_de(jugador.hitbox.center, vision.obstaculos(
                juego.mundo, getattr(juego, "puertas_dobles", ()), getattr(juego, "compuertas", ())))
            return campo.ve_a(alien.hitbox)
        return True

    def _vista_de(self, jugador):
        juego = self.juego
        if hasattr(juego, "vista_de"):        # (sabe del modo dos pantallas)
            return juego.vista_de(jugador)
        from screens.partida import calcular_viewports
        vistas = calcular_viewports(juego.ancho, juego.alto, len(juego.jugadores))
        indice = juego.jugadores.index(jugador) if jugador in juego.jugadores else -1
        return vistas[indice] if 0 <= indice < len(vistas) else None

    # -- La ventana -------------------------------------------------------------------

    def abrir(self, jugador, alien):
        self.presentados.add(alien.tipo)
        self.actual = {"tipo": alien.tipo, "alien": alien, "jugador": jugador, "ms": 0}
        if hasattr(self.juego, "sonar"):
            self.juego.sonar("nota", 0.7)

    def actualizar(self, dt):
        if self.actual is not None:
            self.actual["ms"] += dt

    def puede_cerrar(self):
        return self.actual is not None and self.actual["ms"] >= MIN_ABIERTA_MS

    def cerrar(self):
        if not self.puede_cerrar():
            return False
        self.actual = None
        if hasattr(self.juego, "sonar"):
            self.juego.sonar("menu_ok", 0.5)
        return True

    def textos(self):
        """(título, líneas ya con las teclas del jugador) de la ventana abierta."""
        if self.actual is None:
            return None
        datos = PRESENTACION[self.actual["tipo"]]
        jugador = self.actual["jugador"]
        teclas = {accion: jugador.nombre_tecla(accion) for accion in ("sigilo", "interactuar", "habilidad")}
        return datos["titulo"], [linea.format(**teclas) for linea in datos["lineas"]]
