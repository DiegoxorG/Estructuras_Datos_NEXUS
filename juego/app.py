"""NEXUS: el juego. Mundo, personajes y estructuras de datos, juntos.

Se corre con `python main.py`.

Aquí se unieron los dos prototipos que antes iban por separado. En una misma
partida conviven:

- el **mapa** con sus colisiones y una cámara por jugador (mundo.py,
  screens/partida.py),
- la **misión** de la nave (mision.py) con su tutorial, eventos y puertas,
- el **árbol de comportamiento** de los aliens (Estructuras/arbol_comportamiento.py),
- la red social **NEXUS** y su misión del infiltrado (infiltrado.py),
- el **árbol de logros** de la partida (logros.py),
- y el **árbol binario de habilidades** de cada rol
  (Estructuras/arbol_habilidades.py), que es lo que hace que subir de nivel
  cambie las opciones que el jugador ve, no solo un número.

La ronda dura unos minutos y termina en una pantalla de resultados. Cada
jugador juega en su mitad de la pantalla con sus propias teclas, incluidas las
de navegar paneles: la partida es local y los dos comparten teclado.
"""

import gc
import math
import os
import sys

import time

import pygame

from juego.config import DEFAULT_FPS
from juego.diagnostico import Diagnostico
from juego.transition_manager import TransitionManager

from juego.fuentes import construir_fuentes
from juego.ui_components import construir_botones

from juego.mundo import Mundo
from juego import salas as salas_mapa
from juego import salas_selladas
from entidades.jugador import Jugador, TECLAS_POR_PUESTO, NOMBRE_CONTROLES, NOMBRE_ESQUEMA
from Movimiento.Personaje import Personaje, CONTROLES_WASD, CONTROLES_FLECHAS

from Estructuras.arbol_comportamiento import ArbolComportamiento

from entidades.alien import Alien
from entidades import acciones_rol
from entidades.minijuego_latidos import MinijuegoLatidos
from misiones.mision import Mision, Equipo
from juego.ambiente import Ambiente
from misiones.ia_nave import Narrador
from juego.mandos import Mandos, tecla_virtual, PUESTOS_CON_MANDO
from juego.tutorial import Tutorial
from juego.pausa import MenuPausa, mover_en_logros
from juego.audio_manager import audio_manager
from misiones.infiltrado import CasoInfiltrado
from redes.nexus import RedNexus
from redes import celular
from entidades.npcs import GestorNPCs, Apariencia, sprites_prisionero
from juego import dificultad
from juego import navegacion
from juego import vision
from entidades.alien import sprites_de, ANCHO_HITBOX as ANCHO_HITBOX_ALIEN, ALTO_HITBOX as ALTO_HITBOX_ALIEN
from juego import presentacion_aliens
from juego import historial_logros
from data.tipos_alien import TIPO_POR_DEFECTO
from Estructuras.arbol_logros import ArbolLogros
from data.logros import ARBOL_LOGROS
from juego.presentacion_aliens import PresentacionAliens
from screens.presentacion_aliens import render_presentacion
from juego.dificultad import Dificultad
from entidades.cambiaformas import Cambiaformas
from entidades.sombra import Sombra
from data.npcs import NPCS_POR_PARTIDA
from misiones.logros import GestorLogros
from misiones.guardia import GuardiaYPlanta
from misiones.eventos import GestorEventos, crear_cajas
from misiones import puertas
from data.roles import ROLES, MINIMO_JUGADORES
from data.comportamiento_alien import ARBOL_ALIEN
from data.escondites import ANCHO_ENTRADA, ALTO_ENTRADA
from juego import objetos_mapa
from screens.menu import render_menu, OPCIONES_MENU
from screens.partida import (render_partida, calcular_viewports, render_terminales_encima, alto_evento,
                             pantalla_secundaria)
from juego import segunda_pantalla
from screens.seleccion import render_cantidad, render_roles, render_dificultad, render_controles, OPCIONES
from data.dificultad import DIFICULTADES, POR_DEFECTO as DIFICULTAD_POR_DEFECTO
from screens.arbol_alien import render_arbol_alien
from screens.grafo_vista import render_grafo_nexus, render_grafo_nave
from screens.panel_habilidades import precargar_iconos
from screens.resultados import render_resultados, opciones_resultados
from screens.ayuda import render_ayuda
from screens.creditos import render_creditos, reiniciar_scroll
from screens.pausa import render_pausa
from screens.logros import render_aviso_logro, render_arbol_logros
from screens import celular as dibujo_celular


ANCHO_VENTANA, ALTO_VENTANA = 960, 600

# El mapa ya no se fija aquí: lo dice Hitboxes/mapa_activo.json, que se cambia
# desde el editor de mapa (Editores/editor_mapa.py, tecla M).
DURACION_RONDA_S = 300  # cinco minutos, como pide el diseño

# Tutorial de 30 s al empezar (tutorial.py), en todas las dificultades. Solo en mapas con misión.
TUTORIAL_ACTIVO = True

# Teclas que suenan en los menús (menú, cantidad, roles y pausa).
TECLAS_MOVER_MENU = {pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_w, pygame.K_s}
TECLAS_OK_MENU = {pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_e}

# Lo que cuesta que te atrape un alien.
PUNTOS_POR_SER_ATRAPADO = 10

# Controles de movimiento de cada puesto. Los puestos 3 y 4 van sin controles a
# propósito: se dibujan en el mapa y se animan, pero no caminan, porque les toca
# mando y eso todavía no está hecho.
def _controles_mando(puesto):
    return {d: (tecla_virtual(puesto, d),) for d in ("arriba", "abajo", "izquierda", "derecha")}


CONTROLES_POR_PUESTO = [CONTROLES_WASD, CONTROLES_FLECHAS,
                        _controles_mando(2), _controles_mando(3)]


def botones_menu(ancho, alto):
    """Los botones del menú van a la derecha, debajo del título NEXUS del
    fondo, para no tapar a los cuatro personajes ni el planeta."""
    return construir_botones(OPCIONES_MENU, ancho, alto,
                             centro_x=ancho * 0.765, centro_y=alto * 0.56,
                             ancho=min(380, int(ancho * 0.26)), alto=46, separacion=12)


def _nombre(tecla):
    """Nombre corto de una tecla, para las pistas de la selección de rol."""
    nombres = {
        pygame.K_w: "W", pygame.K_s: "S", pygame.K_e: "E",
        pygame.K_UP: "ARRIBA", pygame.K_DOWN: "ABAJO", pygame.K_RETURN: "ENTER",
        pygame.K_i: "I", pygame.K_k: "K", pygame.K_o: "O",
        pygame.K_t: "T", pygame.K_g: "G", pygame.K_y: "Y",
    }
    return nombres.get(tecla, "?")


def mover_en_mosaico(filas, cursor, dfila, dcol):
    """Mueve el cursor en un mosaico (`filas`: listas de índices de opciones,
    cada fila puede tener distinta cantidad). Izquierda/derecha dan la vuelta
    en la fila; arriba/abajo pasan a la fila de al lado, a la columna más
    parecida (en proporción), y también dan la vuelta."""
    for f, fila in enumerate(filas):
        if cursor in fila:
            c = fila.index(cursor)
            break
    else:
        return filas[0][0] if filas and filas[0] else 0
    if dcol:
        return fila[(c + dcol) % len(fila)]
    nueva = filas[(f + dfila) % len(filas)]
    relativo = (c + 0.5) / len(fila)
    return nueva[min(len(nueva) - 1, int(relativo * len(nueva)))]



def _ordenar_memoria():
    """Recoge la basura de una vez y "congela" lo que queda (mapa, sprites,
    árboles, sonidos...) para que el recolector de Python no lo vuelva a
    revisar durante la partida.

    El recolector de ciclos, cada tanto, revisa TODOS los objetos vivos (~74
    mil al empezar una partida). Esa revisión completa frenaba un cuadro
    entero (~30 ms en la nube, más en una laptop): un tirón cada minuto o
    dos sin nada en pantalla que lo explicara. Congelados, revisa solo lo
    nuevo (~1-2 ms). Se descongela primero para que lo de la partida
    anterior sí se pueda recoger. Se llama al terminar de cargar (todavía en
    la pantalla de carga, donde una pausa no se nota).
    """
    gc.unfreeze()
    gc.collect()
    gc.freeze()

class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("NEXUS")
        self.pantalla_completa = True
        self.screen = self._crear_ventana()
        self.ancho, self.alto = self.screen.get_size()
        # Modo dos pantallas (juego/segunda_pantalla.py): si hay otra pantalla
        # conectada (Windows en "Extender"), J3 y J4 juegan en ella. F9 lo
        # apaga y lo prende.
        self.segunda = None
        self.dos_pantallas = True
        self._abrir_segunda()
        self.clock = pygame.time.Clock()

        self.fuentes = construir_fuentes()
        self.font = self.fuentes["subtitle"]
        self.small_font = self.fuentes["small"]

        self.transitions = TransitionManager()
        self.current_screen = "menu"
        self.menu_buttons = botones_menu(self.ancho, self.alto)
        self.menu_selected = 0
        self.pantalla_anterior = "partida"

        self.mundo = None
        self.jugadores = []
        # Pasos previos a la partida.
        self.cantidad_jugadores = MINIMO_JUGADORES
        self.cantidad_seleccionada = 0   # índice en screens.seleccion.OPCIONES
        self.dificultad_seleccionada = 0  # índice en data/dificultad.DIFICULTADES
        self.seleccion_roles = []
        self.esquemas = []          # el control de cada jugador (abrir_controles)
        self.zonas = []          # zonas del mapa ya convertidas a píxeles
        self.mostrar_hitboxes = False
        # F3: FPS y cuánto tarda cada cuadro (para encontrar tirones).
        self.mostrar_fps = False
        self._tiempos_cuadro = [0.0, 0.0]     # actualizar, dibujar (ms, suavizado)
        # Con F3 además se perfila cada cuadro y los tirones se anotan en
        # Guardado/tirones.txt con su causa (juego/diagnostico.py).
        self.diagnostico = Diagnostico()
        self.cazar_tirones = False   # el segundo toque de F3
        self.aliens = []
        self.escondites = []
        self.objetos = None   # lo que está puesto en el mapa (objetos_mapa.py)
        self.mision = None    # fases, celdas y consumibles (mision.py)
        self.tutorial = None  # los primeros 30 s (tutorial.py)
        self.carga = None     # mientras se arma la partida (empezar_carga)
        # La carga ya terminada, mientras se ve el fundido a la partida: sin
        # esto, esos últimos cuadros se dibujaban sin los personajes elegidos
        # (salía el Tecnomante, el de por defecto).
        self.carga_final = None
        self.eventos = None   # apagón, alarma, compuertas (eventos.py)
        self.infiltrado = None  # misión secundaria del infiltrado de NEXUS (infiltrado.py)
        self.nexus = None       # la red social del celular (nexus.py)
        self.npcs = None        # los prisioneros que caminan (npcs.py)
        self.dificultad = None  # dificultad.Dificultad; None = números base (pruebas)
        self.tiempo_jugado_ms = 0  # cronómetro de la partida (no hay límite)
        self.cambiaformas = None  # el alien que se disfraza de ellos (cambiaformas.py)
        self.guardia_planta = None  # el Guardia de la Bahía y la planta (misiones/guardia.py)
        self.sombra = None        # el alien de los apagones (sombra.py); en self.aliens solo a oscuras
        self._apagon_ms = 0
        self.logros = None      # árbol de logros de la partida (logros.py)
        # Fácil: la ventana que presenta a cada tipo de alien la primera vez
        # que se ve (presentacion_aliens.py). None en las demás dificultades.
        self.presentacion = None
        # Menú > Logros (abrir_catalogo_logros).
        self.catalogo_logros, self.catalogo_nodo, self.catalogo_veces = None, None, {}
        self.catalogo_rects = {}
        self.puertas_dobles, self.compuertas = [], []   # puertas.py
        self.pausa = None     # MenuPausa mientras está abierto (Esc en la partida)
        self._reiniciar_resultados()
        self.oscuridad = True # Pausa > Opciones la apaga (para probar o para quien la necesite)
        self.mandos = Mandos()  # controles de Xbox para los jugadores 3 y 4
        self.equipo = Equipo()
        self._nuevo_ambiente()
        # Lo de las habilidades de los roles (acciones_rol.py).
        self.terminales, self.paneles, self.piezas = [], [], []
        self.senuelos, self.senales = [], []
        self.arbol_alien = None
        self.mostrar_arbol_alien = False
        self.vista_grafo = None      # None, "nexus" o "nave" (screens/grafo_vista.py)
        self.alien_en_vista = 0      # cuál alien muestra la vista del árbol
        self.credit_scroll = reiniciar_scroll()

        # Cuenta regresiva: solo en un mapa sin misión (el modo viejo, por
        # tiempo). Con misión es None: no se pierde por tiempo.
        self.tiempo_restante_ms = None

        self.running = True

    # -- Ventana ---------------------------------------------------------------

    @staticmethod
    def _tamano_escritorio():
        try:
            tamanos = pygame.display.get_desktop_sizes()
            if tamanos:
                return tamanos[0]
        except (AttributeError, pygame.error):
            pass
        info = pygame.display.Info()
        return info.current_w, info.current_h

    def _crear_ventana(self):
        """Pantalla completa sin bordes, o ventana normal si se alterna con F11.

        Se usa NOFRAME y no pygame.FULLSCREEN a propósito: la pantalla completa
        exclusiva cambia el modo de video del monitor y Windows reacomoda las
        ventanas de las demás aplicaciones, dejándolas descolocadas al salir.
        """
        if self.pantalla_completa:
            return pygame.display.set_mode(self._tamano_escritorio(), pygame.NOFRAME)
        return pygame.display.set_mode((ANCHO_VENTANA, ALTO_VENTANA))

    # -- Segunda pantalla -------------------------------------------------------

    def _abrir_segunda(self):
        if self.segunda is not None or not self.dos_pantallas:
            return
        if len(segunda_pantalla.pantallas()) < 2:
            return
        try:
            self.segunda = segunda_pantalla.SegundaPantalla(1)
            print(f"[PANTALLAS] segunda pantalla de {self.segunda.ancho}x{self.segunda.alto}")
        except Exception as error:         # (pygame sin ventanas extra, etc.)
            print(f"[PANTALLAS] no se pudo abrir la segunda pantalla: {error}")
            self.segunda = None

    def _cerrar_segunda(self):
        if self.segunda is not None:
            self.segunda.cerrar()
            self.segunda = None

    def alternar_dos_pantallas(self):
        """F9: J3 y J4 en la otra pantalla, o todos en esta."""
        self.dos_pantallas = not self.dos_pantallas
        if self.dos_pantallas:
            self._abrir_segunda()
            if self.segunda is None:
                self.dos_pantallas = False
        else:
            self._cerrar_segunda()
        print(f"[PANTALLAS] dos pantallas: {'sí' if self.segunda is not None else 'no'}")

    def _reparto_pantallas(self):
        """(vistas de la pantalla principal, vistas de la segunda). Con 3 o 4
        jugadores y otra pantalla, J1 y J2 aquí y el resto allá; si no, todos
        aquí."""
        if self.segunda is not None and len(self.jugadores) >= 3:
            return list(self.jugadores[:2]), list(self.jugadores[2:])
        return list(self.jugadores), []

    def vista_de(self, jugador):
        """El rect de la vista de `jugador`, en la pantalla donde esté."""
        principal, segunda = self._reparto_pantallas()
        if jugador in principal:
            return calcular_viewports(self.ancho, self.alto, len(principal))[principal.index(jugador)]
        if jugador in segunda:
            with pantalla_secundaria():
                return calcular_viewports(self.segunda.ancho, self.segunda.alto,
                                          len(segunda))[segunda.index(jugador)]
        return None

    def _dibujar_partida_en(self, screen, dueños, extras):
        """Las vistas de `dueños` en `screen`, con su barra, cartel de la IA,
        terminales NEXUS y la presentación de aliens."""
        render_partida(screen, self.mundo, self.jugadores, self.zonas,
                       None if self.tiempo_restante_ms is None else self.tiempo_restante_ms / 1000.0,
                       self.mostrar_hitboxes,
                       [a for a in self.aliens if not getattr(a, "oculta", False)],
                       self.escondites, extras, dueños=dueños)
        # El cartel de la IA va con lo global: debajo de la barra de
        # confianza y del aviso del evento (o en el panel del equipo).
        centro_x, arriba, ancho_max = dibujo_celular.columna_avisos(screen, len(dueños), self.nexus)
        arriba += alto_evento(self.eventos, ancho_max)
        self.narrador.dibujar(screen, centro_x, arriba, ancho_max)
        render_terminales_encima(screen, self.jugadores, dueños)
        if self.pausa is None and self.presentacion is not None and self.presentacion.abierta:
            render_presentacion(screen, self, dueños)

    def _dibujar_segunda(self):
        """La otra pantalla: en partida, las vistas de J3 (y J4); si no (menús,
        resultados, o jugando de a 2), lo mismo que la principal."""
        if self.segunda is None:
            return
        principal, segunda = self._reparto_pantallas()
        tela = self.segunda.surface
        if self.current_screen == "partida" and segunda and self.mundo is not None:
            with pantalla_secundaria():
                self._dibujar_partida_en(tela, segunda, self._extras_segunda)
            if self.pausa is not None:
                velo = pygame.Surface(tela.get_size(), pygame.SRCALPHA)
                velo.fill((8, 8, 16, 170))
                tela.blit(velo, (0, 0))
                texto = self.font.render("PAUSA", True, (240, 242, 252))
                tela.blit(texto, texto.get_rect(center=tela.get_rect().center))
            self.transitions.draw(tela)
        else:
            self.segunda.espejo(self.screen)

    def _aplicar_tamano(self):
        self.ancho, self.alto = self.screen.get_size()
        self.menu_buttons = botones_menu(self.ancho, self.alto)
        self.menu_selected = min(self.menu_selected, len(self.menu_buttons) - 1)

    def alternar_pantalla_completa(self):
        self.pantalla_completa = not self.pantalla_completa
        self.screen = self._crear_ventana()
        self._aplicar_tamano()

    # -- Estructuras de datos ---------------------------------------------------

    # -- Partida ----------------------------------------------------------------

    # -- Paso 1: cuántos juegan --------------------------------------------------

    def abrir_cantidad(self):
        self.cantidad_seleccionada = 0
        self.transitions.request(self, "cantidad")

    def confirmar_cantidad(self):
        self.cantidad_jugadores = OPCIONES[self.cantidad_seleccionada]
        self.abrir_seleccion_roles(ir=False)
        self.abrir_dificultad()

    # -- Paso 1.5: la dificultad (dificultad.py) -----------------------------------

    def abrir_dificultad(self):
        claves = [d["clave"] for d in DIFICULTADES]
        actual = self.dificultad.clave if self.dificultad is not None else DIFICULTAD_POR_DEFECTO
        self.dificultad_seleccionada = claves.index(actual)
        self.transitions.request(self, "dificultad")

    def confirmar_dificultad(self):
        self.dificultad = Dificultad(DIFICULTADES[self.dificultad_seleccionada]["clave"])
        self.abrir_controles()

    # -- Paso 1.7: con qué control juega cada uno ------------------------------------

    def abrir_controles(self):
        """Cada jugador escoge su control (WASD, flechas, mando 1 o 2)
        presionando su botón de aceptar: el primero que lo presiona es el
        jugador 1, el siguiente el 2... Dos no pueden tener el mismo (un
        control ya tomado no hace nada). Si no hay mandos conectados no hay
        nada que escoger: cada uno juega con el de su puesto, como siempre."""
        n = self.cantidad_jugadores
        self.esquemas = list(range(n))
        if not self.mandos.por_puesto:
            self.abrir_seleccion_roles()
            return
        self.esquemas = [None] * n
        self.transitions.request(self, "controles")

    def esquemas_libres(self):
        """Los esquemas que se pueden escoger: WASD, flechas y los mandos conectados."""
        return [e for e in range(len(NOMBRE_ESQUEMA))
                if e not in PUESTOS_CON_MANDO or self.mandos.hay_mando(e)]

    def tomar_esquema(self, esquema):
        """Alguien presionó aceptar en `esquema`: si ya era de alguien, lo
        suelta (por si se equivocó); si no, se lo da al primer jugador sin
        control. Con todos listos, a escoger rol."""
        if self.transitions.active or esquema not in self.esquemas_libres():
            return
        if esquema in self.esquemas:
            self.esquemas[self.esquemas.index(esquema)] = None
            self.sonar("menu_mover", 0.5)
            return
        if None not in self.esquemas:
            return
        self.esquemas[self.esquemas.index(None)] = esquema
        self.sonar("menu_ok", 0.6)
        if None not in self.esquemas:
            self.abrir_seleccion_roles()

    def _tecla_en_controles(self, key):
        if key == pygame.K_ESCAPE:
            self.abrir_dificultad()
            return
        for esquema in (0, 1):
            if key in TECLAS_POR_PUESTO[esquema]["interactuar"]:
                self.tomar_esquema(esquema)
                return

    # -- Paso 2: qué rol juega cada uno ------------------------------------------

    def abrir_seleccion_roles(self, ir=True):
        """Prepara el estado de la selección, uno por jugador (y, si `ir`, pasa
        a esa pantalla)."""
        self.seleccion_roles = []
        esquemas = getattr(self, "esquemas", None)
        if not esquemas or len(esquemas) != self.cantidad_jugadores or None in esquemas:
            self.esquemas = esquemas = list(range(self.cantidad_jugadores))
        for puesto in range(self.cantidad_jugadores):
            esquema = esquemas[puesto]
            teclas = TECLAS_POR_PUESTO[esquema]
            self.seleccion_roles.append({
                "cursor": puesto % len(ROLES),
                "listo": False,
                "rol": None,
                "esquema": esquema,
                "controles": (f"Mando {esquema - 1}" if self.mandos.hay_mando(esquema)
                              else NOMBRE_CONTROLES[esquema]),
                # "Flechas" en vez de "ARRIBA/ABAJO": más corto y es como la
                # gente llama a esas teclas.
                "tecla_mover": ("Stick" if self.mandos.hay_mando(esquema)
                                else "Flechas" if pygame.K_UP in teclas["arriba"]
                                else f"{_nombre(teclas['arriba'][0])}/{_nombre(teclas['abajo'][0])}"),
                "tecla_ok": "A" if self.mandos.hay_mando(esquema) else _nombre(teclas["interactuar"][0]),
            })
        if ir:
            self.transitions.request(self, "roles")

    def _tecla_en_seleccion(self, key):
        """Reparte la tecla entre los jugadores que están escogiendo rol."""
        for puesto, estado in enumerate(self.seleccion_roles):
            teclas = TECLAS_POR_PUESTO[estado.get("esquema", puesto)]
            if key in teclas["interactuar"]:
                self._confirmar_rol(puesto, estado)
                return
            if estado["listo"]:
                continue
            if key in teclas["arriba"]:
                estado["cursor"] = (estado["cursor"] - 1) % len(ROLES)
                return
            if key in teclas["abajo"]:
                estado["cursor"] = (estado["cursor"] + 1) % len(ROLES)
                return

    def _confirmar_rol(self, puesto, estado):
        if estado["listo"]:
            # Volver a pulsar deshace la elección, por si se equivocó.
            estado["listo"] = False
            estado["rol"] = None
            return
        elegido = ROLES[estado["cursor"]]["nombre"]
        if any(otro["listo"] and otro["rol"] == elegido
               for i, otro in enumerate(self.seleccion_roles) if i != puesto):
            return  # ese rol ya lo tomaron
        estado["listo"] = True
        estado["rol"] = elegido
        if all(e["listo"] for e in self.seleccion_roles):
            self.empezar_carga()

    # -- Paso 3: la partida ------------------------------------------------------

    # -- La pantalla de carga (screens/carga.py) ----------------------------------

    MIN_CARGA_MS = 2000     # aunque cargue antes, la animación dura al menos esto

    def empezar_carga(self):
        """Pasa a la pantalla de carga y arma la partida en otro hilo, para que
        la animación siga corriendo mientras tanto (antes la pantalla se
        quedaba congelada ~1 s). Sin ventana (las pruebas) carga de una."""
        if os.environ.get("SDL_VIDEODRIVER") == "dummy":
            self.iniciar_partida()
            return
        if self.carga is not None:
            return
        import random
        import threading
        from data.consejos_carga import CONSEJOS
        from screens import carga as pantalla_carga
        roles = [e["rol"] for e in self.seleccion_roles[:self.cantidad_jugadores] if e.get("rol")]
        pantalla_carga.precargar(self.alto, roles)
        self.carga = {"ms": 0, "listo": False, "error": None,
                      "consejo": random.choice(CONSEJOS), "roles": roles}

        def cargar():
            try:
                self._preparar_partida()
            except Exception as error:          # se relanza en el hilo principal
                self.carga["error"] = error
            self.carga["listo"] = True

        self.transitions.request(self, "cargando")
        threading.Thread(target=cargar, daemon=True).start()

    def _actualizar_carga(self, dt):
        carga = self.carga
        if carga is None and self.carga_final is not None and self.current_screen == "cargando":
            self.carga_final["ms"] += dt         # que la animación siga durante el fundido
        if carga is None or self.current_screen != "cargando":
            return
        carga["ms"] += dt
        if carga["error"] is not None:
            self.carga = None
            raise carga["error"]
        if carga["listo"] and carga["ms"] >= self.MIN_CARGA_MS and self.transitions.is_idle():
            self.carga, self.carga_final = None, carga
            self.transitions.request(self, "partida")

    def _progreso_carga(self):
        """La barra va por tiempo (la carga no avisa cuánto le falta): llega
        al 90 % a los MIN_CARGA_MS y se completa cuando de verdad terminó."""
        carga = self.carga
        if carga is None:
            return 1.0
        por_tiempo = 0.9 * min(1.0, carga["ms"] / self.MIN_CARGA_MS)
        return 1.0 if carga["listo"] and carga["ms"] >= self.MIN_CARGA_MS else por_tiempo

    def iniciar_partida(self):
        """Arma la partida de una (sin pantalla de carga) y pasa a jugar."""
        self._preparar_partida()
        self.transitions.request(self, "partida")

    def _preparar_partida(self):
        """Carga el mapa, arma los árboles y crea a los jugadores."""
        self.pausa = None
        if self.dificultad is not None:
            self.dificultad = Dificultad(self.dificultad.clave)    # el director arranca de cero
        nombre_mapa = objetos_mapa.mapa_activo()
        if self.mundo is None or self.mundo.nombre_mapa != nombre_mapa:
            self.mundo = Mundo(nombre_mapa)
        # Si se reutiliza el mundo de la ronda anterior, se quita lo que esa
        # ronda le agregó (la puerta de la prisión): si no, quedaba una puerta
        # invisible que no se abría con el código.
        self.mundo.reiniciar_paredes()
        # Dónde va cada cosa del mapa: lo que se puso con el editor de mapa, y
        # lo que no, de data/ (ver objetos_mapa.py).
        self.objetos = objetos_mapa.cargar(nombre_mapa)
        self.salas = salas_mapa.preparar(self.objetos, self.mundo)
        # Menos jugadores, menos salas: las que sobran se sellan y lo que había
        # adentro se quita de self.objetos antes de armar nada (salas_selladas.py).
        self.sellado = salas_selladas.aplicar(self.objetos, self.mundo, self.salas,
                                              len(self.seleccion_roles))
        self._preparar_zonas()

        self.tiempo_restante_ms = DURACION_RONDA_S * 1000

        self.jugadores = []
        centro = (self.mundo.ancho // 2, self.mundo.alto // 2)
        if self.objetos.get("spawn"):
            centro = (int(self.objetos["spawn"][0] * self.mundo.ancho),
                      int(self.objetos["spawn"][1] * self.mundo.alto))
        for puesto, estado in enumerate(self.seleccion_roles):
            nombre_personaje = estado["rol"]     # sprites en Imagenes/Personajes/<Rol>/
            ruta = os.path.join("Imagenes", "Personajes", nombre_personaje)
            esquema = estado.get("esquema", puesto)
            personaje = Personaje(0, 0, ruta, velocidad=4,
                                  controles=CONTROLES_POR_PUESTO[esquema])
            personaje.rol = estado["rol"]

            # Se reparten alrededor del centro para que no salgan encimados.
            angulo = puesto * 2 * math.pi / max(1, len(self.seleccion_roles))
            preferido = (centro[0] + math.cos(angulo) * 130,
                         centro[1] + math.sin(angulo) * 90)
            x, y = self.mundo.punto_libre(preferido, personaje.hitbox_w, personaje.hitbox_h)
            personaje.hitbox.topleft = (int(x), int(y))
            personaje.sync_sprite_from_hitbox()

            jugador = Jugador(personaje, estado["rol"], puesto,
                              con_mando=self.mandos.hay_mando(esquema), esquema=esquema)
            jugador.spawn = personaje.hitbox.topleft
            jugador.nombre_personaje = nombre_personaje
            personaje.controles_nombre = jugador.controles_nombre
            self.jugadores.append(jugador)

        # Los iconos de las habilidades se dejan listos aquí, mientras el
        # jugador todavía está viendo cargar, y no la primera vez que abre el
        # panel a mitad de la ronda.
        precargar_iconos([j.rol for j in self.jugadores])

        self._preparar_escondites()
        self.terminales, self.paneles, self.piezas = acciones_rol.preparar_estaciones(self.mundo, self.objetos)
        self.senuelos, self.senales = [], []
        self._crear_aliens()
        # Las hojas de sprites de los aliens se cargan aquí, mientras carga el
        # mapa: antes se cargaban la primera vez que uno salía en pantalla y
        # el juego se congelaba ~0.3 s a mitad de partida.
        for alien in self.aliens:
            sprites_de(alien.tipo)
        audio_manager.precargar()

        self.equipo = Equipo()
        for jugador in self.jugadores:
            jugador.equipo = self.equipo
        self.mision = Mision(self, self.objetos)
        self.puertas_dobles = puertas.crear_puertas_dobles(self.objetos, self.mundo)
        # Mientras estén cerradas, los aliens tampoco pasan (mundo.colisiona_alien).
        self.mundo.puertas_alien = [p["rect"] for p in self.puertas_dobles if not p["abierta"]]
        self.compuertas = puertas.crear_compuertas(self.objetos, self.mundo)
        # El Guardia de la cápsula (entra a self.aliens) y la planta de la Biosfera.
        self.guardia_planta = GuardiaYPlanta(self, self.objetos)
        self._nuevo_ambiente()
        self.tutorial, self.eventos = None, None
        self.nexus = RedNexus(self) if self.mision.activa else None
        self._crear_prisioneros()
        # La Sombra: existe desde el principio pero solo entra a self.aliens
        # en los apagones (_actualizar_sombra).
        self.sombra = Sombra(self, len(self.aliens) + 1) if self.mision.activa else None
        self._apagon_ms = 0
        self._sombra_alcanzo = False
        self.sombra_al_volver_la_luz = None
        self.logros = GestorLogros(self)     # uno nuevo cada partida: se reinician solos
        self.presentacion = (PresentacionAliens(self) if presentacion_aliens.activa_en(self.dificultad)
                             else None)
        if self.mision.activa:
            self.tiempo_restante_ms = None      # sin límite: se pierde sin vidas o todos presos
        self.tiempo_jugado_ms = 0
        # La dificultad (dificultad.py): más vidas en los fáciles.
        if self.dificultad is not None:
            for jugador in self.jugadores:
                jugador.vidas = jugador.vidas_max = self.dificultad.vidas
                jugador.vidas_infinitas = self.dificultad.vidas_infinitas
            if self.nexus is not None:
                self.nexus.umbral_planos = self.dificultad.umbral_planos
        if self.mision.activa:
            self.eventos = GestorEventos(self, cajas=crear_cajas(self.objetos, self.mundo))
            # Los pasos del principio salen en todas las dificultades.
            if TUTORIAL_ACTIVO:
                self.tutorial = Tutorial(self.jugadores)
                for alien in self.aliens:
                    alien.accion, alien.aturdido = "DESCANSAR", True
                self.decir("tutorial", forzar=True)
            else:
                self.decir("inicio", forzar=True)
        self._avisar_zonas_inalcanzables()
        _ordenar_memoria()

    def _crear_aliens(self):
        """Un alien por ruta del mapa (las que se trazan en el editor de mapa).

        Una ruta de un solo punto es un guardia: se queda ahí, mirando.

        Todos comparten el mismo árbol de comportamiento: es contenido
        (data/comportamiento_alien.py). Lo que cambia entre aliens es la ruta
        y su tipo (data/tipos_alien.py: velocidad, vista y oído).
        """
        self.arbol_alien = ArbolComportamiento(ARBOL_ALIEN)
        self.aliens = []
        tipos = self.objetos.get("tipos_aliens") or []
        rutas = [(ruta, tipos[i] if i < len(tipos) else TIPO_POR_DEFECTO)
                 for i, ruta in enumerate(self.objetos["rutas_aliens"]) if len(ruta) >= 1]
        for numero, (ruta, tipo) in enumerate(rutas, start=1):
            puntos = [(int(rx * self.mundo.ancho), int(ry * self.mundo.alto)) for rx, ry in ruta]
            alien = Alien(numero, puntos, self.arbol_alien, tipo)
            for i, j in self.mundo.tramos_bloqueados(puntos, alien.hitbox.width,
                                                     alien.hitbox.height):
                print(f"[AVISO] La ruta del {alien.nombre} choca con una pared entre los "
                      f"puntos {i} y {j}. Muévela con el editor de mapa.")
            self.aliens.append(alien)
        self.alien_en_vista = 0
        self.mostrar_arbol_alien = False

    def _crear_prisioneros(self):
        """Los prisioneros que caminan (cuentas de NEXUS), el caso del
        Cambiaformas y el Cambiaformas, que se hace pasar por uno de ellos.

        Se escogen NPCS_POR_PARTIDA cuentas de NEXUS. Los sospechosos del caso
        salen de ellas; la identidad del culpable no camina por su cuenta: es el
        Cambiaformas disfrazado.
        """
        import random
        self.npcs, self.cambiaformas = None, None
        if self.nexus is None:
            self.infiltrado = CasoInfiltrado(self, self.objetos) if self.mision.activa else None
            return
        presos = self.nexus._presos()
        elegidos = random.sample(presos, min(NPCS_POR_PARTIDA, len(presos)))
        cuentas = [(n, self.nexus.grafo.datos[n]) for n in elegidos]
        self.infiltrado = CasoInfiltrado(self, self.objetos,
                                         cuentas=[d["nombre"] for _, d in cuentas])
        culpable = self.infiltrado.infiltrado["nombre"]
        self.npcs = GestorNPCs(self, cuentas)
        apariencias = {n.usuario: Apariencia(n.apariencia.estilo, n.usuario, n.apariencia.numero,
                                             n.apariencia.sprite)
                       for n in self.npcs.npcs}
        identidad = next(d["usuario"] for _, d in cuentas if d["nombre"] == culpable)
        doble = next(n for n in self.npcs.npcs if n.usuario == identidad)
        self.npcs.npcs.remove(doble)      # esa persona ES el Cambiaformas
        self.cambiaformas = Cambiaformas(self, len(self.aliens) + 1, apariencias, identidad,
                                         self._inicio_cambiaformas(doble.centro))
        self.aliens.append(self.cambiaformas)
        # Sus hojas se cargan ya, como las de los demás aliens (si no, el
        # juego se congela un instante la primera vez que aparecen).
        sprites_de(self.cambiaformas.tipo)
        for apariencia in apariencias.values():
            sprites_prisionero(apariencia.sprite)

    def _inicio_cambiaformas(self, punto):
        """Aparece donde habría aparecido el prisionero que imita, salvo que
        ese lugar quede detrás de una puerta cerrada (con la cápsula detrás de
        una puerta para dos, podía quedar encerrado en el Laboratorio casi toda
        la partida): entonces, donde pasea la mayoría de los prisioneros."""
        puntos = self.npcs.puntos if self.npcs is not None else []
        if len(puntos) < 2:
            return punto
        nav = navegacion.de_mundo(self.mundo, ANCHO_HITBOX_ALIEN, ALTO_HITBOX_ALIEN)
        def juntos(p):
            return sum(1 for q in puntos if nav.conectados(p, q))
        if juntos(punto) * 2 >= len(puntos):
            return punto
        mejor = max(puntos, key=juntos)
        return mejor

    # -- La Sombra (sombra.py) ---------------------------------------------------------

    RETRASO_SOMBRA_MS = 3000     # aparece este rato después de que se va la luz
    SIN_LINTERNA_HASTA_LA_LUZ = 10 ** 9   # (Pesadilla) no se acaba solo: lo corta la luz

    def _actualizar_sombra(self, dt):
        """Aparece en los apagones y se disuelve al volver la luz."""
        for jugador in self.jugadores:
            jugador.sin_linterna_ms = max(0, getattr(jugador, "sin_linterna_ms", 0) - dt)
        sombra = self.sombra
        if sombra is None:
            return
        apagon = self.eventos is not None and self.eventos.apagon and not self.en_tutorial
        if not apagon:
            self._apagon_ms = 0
            if sombra in self.aliens:
                self.aliens.remove(sombra)
                self._logros_sombra_al_volver_la_luz(sombra)
            for jugador in self.jugadores:
                jugador.sin_linterna_ms = 0          # con luz, la linterna da igual
            return
        self._apagon_ms += dt
        if sombra not in self.aliens and self._apagon_ms >= self.RETRASO_SOMBRA_MS:
            punto = self._punto_para_sombra()
            if punto is not None:
                sombra.aparecer(punto)
                self.aliens.append(sombra)
                self._sombra_alcanzo = False
                self.decir("sombra", forzar=True)

    def _punto_para_sombra(self):
        """Dónde aparece la Sombra: un lugar caminable, a oscuras (fuera del
        campo de visión de todos), ni muy cerca ni muy lejos del jugador libre
        más cercano y conectado con él. None si no hay."""
        import random
        libres = [j for j in self.jugadores if j.puede_moverse and j.preso is None
                  and not getattr(j, "eliminado", False)]
        if not libres:
            return None
        candidatos = list(self.npcs.puntos) if self.npcs is not None else []
        candidatos += [p for a in self.aliens if a is not self.sombra for p in a.ruta]
        candidatos += [e["rect"].midbottom for e in self.escondites]
        nav = navegacion.de_mundo(self.mundo, ANCHO_HITBOX_ALIEN, ALTO_HITBOX_ALIEN)
        obstaculos = vision.obstaculos(self.mundo, self.puertas_dobles, self.compuertas)
        campos = [vision.campo_de(j.hitbox.center, obstaculos) for j in libres]
        # Revueltos y solo hasta tener unos cuantos buenos: en un mapa con
        # muchas rutas y escondites revisarlos todos trababa un cuadro.
        random.shuffle(candidatos)
        buenos = []
        for punto in candidatos:
            if len(buenos) >= 6:
                break
            rect = pygame.Rect(0, 0, ANCHO_HITBOX_ALIEN, ALTO_HITBOX_ALIEN)
            rect.center = (int(punto[0]), int(punto[1]))
            if self.mundo.colisiona_alien(rect):
                continue
            cerca = min(math.dist(punto, j.hitbox.center) for j in libres)
            if not 650 <= cerca <= 1700 or any(c.ve_a(rect) for c in campos):
                continue
            if any(nav.conectados(punto, j.hitbox.center) for j in libres):
                buenos.append(rect.center)
        return random.choice(buenos) if buenos else None

    def _logros_sombra_al_volver_la_luz(self, sombra):
        """Anota cómo estaba la Sombra cuando volvió la luz, para los logros
        "Luz salvadora" (quien prendió la caja la tenía cerca) y "Sin miedo a
        la oscuridad" (no alcanzó a nadie): los da logros.py, después de
        "Hágase la luz"."""
        quien = getattr(self.eventos, "restauro", None) if self.eventos is not None else None
        self.sombra_al_volver_la_luz = {
            "cerca": (quien is not None and not sombra.oculta
                      and math.dist(quien.hitbox.center, sombra.centro) <= self.DISTANCIA_LUZ_SALVADORA),
            "alcanzo": getattr(self, "_sombra_alcanzo", False),
        }

    DISTANCIA_LUZ_SALVADORA = 500

    def _sombra_alcanza(self, jugador, sombra):
        """La Sombra alcanzó a alguien: susto y le apaga la linterna. Nunca lo
        atrapa. En Pesadilla (Inteligente) la linterna no vuelve hasta que alguien prenda la
        caja de fusibles; si no, solo un rato (data/dificultad.py:
        sombra_hasta_luz, sombra_apaga_ms). Al volver la luz,
        _actualizar_sombra se la devuelve a todos."""
        self._sombra_alcanzo = True
        self.ambiente.susto(jugador, "sombra")
        jugador.pulso = max(jugador.pulso, 85.0)
        if dificultad.valor(self, "sombra_hasta_luz", 1) >= 0.5:
            jugador.sin_linterna_ms = self.SIN_LINTERNA_HASTA_LA_LUZ
            jugador.avisar("¡La Sombra te apagó la linterna hasta que vuelva la luz!", (176, 150, 236))
        else:
            jugador.sin_linterna_ms = int(dificultad.valor(self, "sombra_apaga_ms", 10000))
            jugador.avisar("¡La Sombra te apagó la linterna!", (176, 150, 236))
        self.decir("sombra_linterna", jugador.rol, forzar=True)

    def quitar_sombra(self):
        """Saca a la Sombra de la partida (pruebas que miden otra cosa)."""
        if self.sombra in self.aliens:
            self.aliens.remove(self.sombra)
        self.sombra = None

    def quitar_cambiaformas(self):
        """Saca al Cambiaformas de la partida. Para las pruebas que miden otra
        cosa (los aliens de ruta, la misión...): él va por su cuenta."""
        if self.cambiaformas in self.aliens:
            self.aliens.remove(self.cambiaformas)
        self.cambiaformas = None

    def _preparar_escondites(self):
        """Pasa los escondites de data/escondites.py a rects en píxeles."""
        self.escondites = []
        for datos in self.objetos["escondites"]:
            escondite = dict(datos)
            escondite["rect"] = pygame.Rect(0, 0, ANCHO_ENTRADA, ALTO_ENTRADA)
            escondite["rect"].center = (int(datos["rx"] * self.mundo.ancho),
                                        int(datos["ry"] * self.mundo.alto))
            escondite["ocupante"] = None       # el jugador que está adentro
            escondite["revisado_por"] = None   # el alien que lo está revisando
            escondite["enfriamiento_ms"] = 0   # tiempo en que los aliens lo ignoran
            self.escondites.append(escondite)

    def escondite_bajo(self, jugador):
        """Escondite libre frente al que está parado el jugador, o None."""
        for escondite in self.escondites:
            if escondite["ocupante"] is None and escondite["rect"].colliderect(jugador.hitbox):
                return escondite
        return None

    # -- Que se sienta: sonido, susto y la IA de la nave -------------------------

    def _nuevo_ambiente(self):
        self.ambiente = Ambiente()
        self.narrador = Narrador(al_hablar=lambda: self.ambiente.sonar("ia_voz", 0.7))
        self._aviso_pulso_ms = 0

    def sonar(self, nombre, volumen=1.0):
        self.ambiente.sonar(nombre, volumen)

    def decir(self, evento, rol=None, forzar=False):
        return self.narrador.decir(evento, rol, forzar)

    def _actualizar_ambiente(self, dt):
        # Durante el tutorial los aliens duermen: no se oyen sus pasos.
        self.ambiente.actualizar(dt, self.jugadores,
                                 [] if self.en_tutorial else self._aliens_a_la_vista())
        self.narrador.actualizar(dt)
        self._aviso_pulso_ms = max(0, self._aviso_pulso_ms - dt)
        asustados = [j for j in self.jugadores if j.pulso > 85 and j.preso is None]
        if asustados and self._aviso_pulso_ms == 0:
            if self.decir("pulso_alto", asustados[0].rol):
                self._aviso_pulso_ms = 25000

    @property
    def sin_luz(self):
        """Hay un apagón: no funciona nada eléctrico (terminales, NEXUS,
        teclado de la prisión, consolas, sellos, puertas para dos, escaneo)."""
        return self.eventos is not None and self.eventos.apagon

    @property
    def en_tutorial(self):
        return self.tutorial is not None and self.tutorial.activo

    def saltar_tutorial(self):
        """Termina los pasos del principio de una (si los hay)."""
        if self.tutorial is not None and self.tutorial.activo:
            self.tutorial.activo = False
            self._terminar_tutorial()

    def _terminar_tutorial(self):
        """Los aliens despiertan y empieza a correr el reloj."""
        for alien in self.aliens:
            alien.aturdido = False
            alien.descanso_ms = 0
            alien.accion = "PATRULLAR"
        self.sonar("susto", 0.6)
        self.decir("despertar", forzar=True)

    def _colisiona_jugador(self, rect):
        """Las paredes, y además lo que solo frena a los jugadores (puertas.py)."""
        return (self.mundo.colisiona(rect)
                or puertas.bloquea(self.puertas_dobles, self.compuertas, rect))

    def _colisiona_para(self, jugador):
        """Lo de arriba, más el cuerpo del Guardia (guardia.py), que es sólido.
        Si el Guardia se le vino encima, no lo bloquea: así puede salir."""
        guardia = self.guardia_planta.guardia if self.guardia_planta is not None else None
        if guardia is None:
            return self._colisiona_jugador
        cuerpo = guardia.cuerpo
        if jugador.hitbox.colliderect(cuerpo):
            return self._colisiona_jugador
        return lambda rect: self._colisiona_jugador(rect) or rect.colliderect(cuerpo)

    def _puerta_doble_abierta(self, puerta):
        if puerta["rect"] in self.mundo.puertas_alien:
            self.mundo.puertas_alien.remove(puerta["rect"])
        if self.logros is not None:
            self.logros.conseguir("trabajo_en_equipo")
        self.sonar("puerta")
        self.decir("puerta_doble")

    def _alien_revisa(self, jugador, alien, escondite):
        """Un alien llegó a revisar un escondite: arranca el minijuego."""
        if jugador is None:
            return
        jugador.minijuego = MinijuegoLatidos(jugador.pulso, alien, escondite)
        self.decir("escondite_revisado", jugador.rol)
        jugador.avisar(f"¡El {alien.nombre} revisa tu escondite!", (236, 70, 60))

    def _actualizar_minijuegos(self, dt):
        for jugador in self.jugadores:
            juego = jugador.minijuego
            if juego is None:
                continue
            alien = juego.alien
            if alien.escondite_objetivo is not juego.escondite:
                # El alien dejó de revisar (lo hackearon): se acabó el peligro.
                jugador.minijuego = None
                jugador.avisar("El alien se fue de tu escondite.", (96, 200, 120))
                continue
            juego.actualizar(dt, jugador)
            if not juego.terminado:
                continue
            if juego.resultado == "calmado":
                jugador.minijuego = None
                alien.rendirse()
                self.decir("escondite_calmado", jugador.rol)
                if self.logros is not None:
                    self.logros.conseguir("fantasma", jugador)
                jugador.sumar_puntos(5)
                jugador.avisar("Te calmaste. El alien se fue. +5", (96, 200, 120))
            else:
                alien.entrar_al_escondite()
                self._atrapar(jugador, alien)

    def _atrapar(self, jugador, alien):
        """Lo llama un alien cuando su árbol llega a la hoja ATRAPAR."""
        if jugador is None:
            return
        donde = jugador.hitbox.center
        if self.logros is not None:
            self.logros.al_atrapar(jugador)
        if self.dificultad is not None:
            self.dificultad.al_atrapar()
        jugador.atrapado()
        # Cada tipo de alien tiene su propio susto (ambiente.py).
        tipo = getattr(alien, "tipo", "")
        self.ambiente.susto(jugador, "cf_captura" if tipo == "cambiaformas" else tipo)
        if jugador.vidas <= 0:
            # Última vida: queda fuera de la partida, y suelta lo que llevaba
            # (y las herramientas de su rol) donde lo atraparon.
            jugador.eliminar()
            # Primero las pruebas del infiltrado: soltar_al_morir vacía el inventario.
            if self.infiltrado is not None:
                self.infiltrado.soltar(jugador, donde)
            if self.mision is not None:
                self.mision.soltar_al_morir(jugador, donde)
            self.decir("eliminado", jugador.rol, forzar=True)
            self.sonar("eliminado", 0.8)
            veces = jugador.vidas_max
            jugador.avisar(f"Te atraparon {veces} {'vez' if veces == 1 else 'veces'}. Estás fuera.",
                           (236, 70, 60))
            for otro in self.jugadores:
                if otro is not jugador:
                    otro.avisar(f"¡Perdimos al {jugador.rol}!", (236, 70, 60))
            return
        self.decir("atrapado", jugador.rol, forzar=True)
        if self.mision is not None and self.mision.encarcelar(jugador):
            vidas = jugador.vidas
            if jugador.vidas_infinitas:
                jugador.avisar("¡Te encerraron! En Fácil no pierdes vidas.", (236, 70, 60))
            else:
                jugador.avisar(f"¡Te encerraron! Te queda{'n' if vidas > 1 else ''} {vidas} "
                               f"vida{'s' if vidas > 1 else ''}.", (236, 70, 60))
            return
        jugador.sumar_puntos(-PUNTOS_POR_SER_ATRAPADO)
        jugador.avisar(f"¡Te atrapó el {alien.nombre}! -{PUNTOS_POR_SER_ATRAPADO}",
                       (236, 70, 60))

    def _avisar_zonas_inalcanzables(self):
        """Avisa por consola si alguna zona quedó encerrada tras una pared.

        Una terminal metida en un cuarto cerrado se dibuja en el mapa pero no
        hay forma de llegar. Es el tipo de error que solo se nota jugando, así
        que mejor que el juego lo diga al arrancar.
        """
        if not self.jugadores or self.mundo is None:
            return
        referencia = self.jugadores[0]
        # Con las puertas con código cerradas casi nada se alcanza: se revisa
        # como si estuvieran abiertas, que es como se juega después.
        puertas = [p["rect"] for p in getattr(self.mision, "puertas", ())
                   if p["rect"] in self.mundo.paredes]
        for puerta in puertas:
            self.mundo.paredes.remove(puerta)
        try:
            malas = self.mundo.zonas_inalcanzables(
                self.zonas, referencia.hitbox.topleft,
                referencia.personaje.hitbox_w, referencia.personaje.hitbox_h)
        finally:
            self.mundo.paredes.extend(puertas)
        for zona in malas:
            print(f"[AVISO] La zona '{zona['clave']}' ({zona['nombre']}) no se puede "
                  f"alcanzar caminando. Muévela con el editor de mapa.")

    def _preparar_zonas(self):
        """Las zonas donde se interactúa con algo del mapa: las Terminales
        NEXUS (centrales de ayuda, celular.panel_ayuda)."""
        self.zonas = []
        for i, (rx, ry) in enumerate(self.objetos.get("nexus", []), start=1):
            radio = int(0.02 * self.mundo.ancho)
            self.zonas.append({
                "clave": f"nexus_{i}", "nombre": "Terminal NEXUS",
                "pista": "Central de ayuda de NEXUS.", "tipo": "nexus",
                "roles": [], "color": (90, 220, 230),
                "rect": pygame.Rect(int(rx * self.mundo.ancho) - radio,
                                    int(ry * self.mundo.alto) - radio, radio * 2, radio * 2),
            })

    def zona_bajo(self, jugador):
        """Zona utilizable por ese jugador sobre la que está parado, o None."""
        for zona in self.zonas:
            if zona["roles"] and jugador.rol not in zona["roles"]:
                continue
            if zona["rect"].colliderect(jugador.hitbox):
                return zona
        return None

    def _actualizar_partida(self, dt=0):
        if not self.jugadores or self.mundo is None:
            return
        if self.presentacion is not None and self.presentacion.abierta:
            # Fácil: la ventana que presenta a un alien nuevo pausa todo.
            self.presentacion.actualizar(dt)
            return
        teclas = self.mandos.envolver(pygame.key.get_pressed())
        en_tutorial = self.en_tutorial
        if en_tutorial:
            self.tutorial.actualizar(dt)
            if not self.tutorial.activo:
                self._terminar_tutorial()
        for jugador in self.jugadores:
            if jugador.panel is not None and jugador.panel.get("tipo") == "emision":
                # Sus teclas de moverse mueven el cursor del mapa de la Emisión.
                dx, dy = jugador.personaje.leer_movimiento(teclas)
                acciones_rol.mover_cursor_emision(self, jugador, dx, dy, dt or 16)
            jugador.actualizar(teclas, colisiona=self._colisiona_para(jugador))
            jugador.zona_cerca = self.zona_bajo(jugador)
            jugador.actualizar_mensaje(dt)
            jugador.info = acciones_rol.linea_de_estado(jugador)

        # Tecla de interactuar mantenida: apagar consolas, reparar la cápsula
        # y los paneles de las puertas para dos.
        sosteniendo = []
        for jugador in self.jugadores:
            mantiene = any(teclas[k] for k in jugador.teclas.get("interactuar", ()))
            jugador.progreso = None
            if mantiene and not jugador.ocupado and not jugador.escondido and not jugador.preso:
                sosteniendo.append(jugador)
                if self.mision is not None:
                    self.mision.mantener(jugador, dt)
                if self.eventos is not None:
                    self.eventos.mantener(jugador, dt)
                if self.guardia_planta is not None:
                    self.guardia_planta.mantener(jugador, dt)
            if self.mision is not None and self.mision.activa:
                jugador.objetivo = self.mision.objetivo()
                jugador.pista_mision = self.mision.pista(jugador)
            if self.guardia_planta is not None and not jugador.preso:
                pista_guardia = self.guardia_planta.pista(jugador)
                if pista_guardia:
                    jugador.pista_mision = pista_guardia
            if self.infiltrado is not None and not jugador.pista_mision:
                jugador.pista_mision = self.infiltrado.pista(jugador)
            if self.npcs is not None and not jugador.pista_mision and not jugador.preso:
                jugador.pista_mision = self.npcs.pista(jugador)
            pista_puerta = puertas.pista(self.puertas_dobles, jugador)
            if pista_puerta and not jugador.preso:
                jugador.pista_mision = "Puerta sin energía" if self.sin_luz else pista_puerta
            pista_caja = self.eventos.pista(jugador) if self.eventos is not None else None
            if pista_caja and not jugador.preso:
                jugador.pista_mision = pista_caja
        # Las puertas para dos son eléctricas: en un apagón no abren.
        puertas.actualizar(self.puertas_dobles, [] if self.sin_luz else sosteniendo, dt,
                           self._puerta_doble_abierta)

        acciones_rol.actualizar(self, dt)
        if self.guardia_planta is not None:
            self.guardia_planta.actualizar(dt)
        if self.sin_luz:
            for jugador in self.jugadores:
                if jugador.pista_mision or jugador.preso:
                    continue
                estacion = getattr(jugador, "estacion_cerca", None)
                if jugador.zona_cerca is not None and jugador.zona_cerca["tipo"] == "nexus":
                    jugador.pista_mision = "Terminal NEXUS sin energía"
                elif estacion is not None and estacion["tipo"] == "terminal":
                    jugador.pista_mision = "Terminal sin energía"
        for jugador in self.jugadores:
            jugador.escondite_cerca = (None if jugador.escondido or jugador.zona_cerca
                                       or jugador.estacion_cerca
                                       else self.escondite_bajo(jugador))
        for escondite in self.escondites:
            escondite["enfriamiento_ms"] = max(0, escondite["enfriamiento_ms"] - dt)

        navegacion.siguiente_cuadro()
        self._actualizar_sombra(dt)
        if not en_tutorial:
            if self.dificultad is not None:
                self.dificultad.actualizar(dt, self)
            vel = dificultad.valor(self, "vel_aliens", 1.0)
            vision = dificultad.valor(self, "vision_aliens", 1.0)
            oido = dificultad.valor(self, "oido_aliens", 1.0)
            for alien in self.aliens:
                alien.ajuste_vel, alien.ajuste_vision, alien.ajuste_oido = vel, vision, oido
            for alien in self.aliens:
                alien.actualizar(dt, self.mundo, self.jugadores, self._atrapar,
                                 self.escondites, self._alien_revisa)
            if self.eventos is not None:
                self.eventos.actualizar(dt)
        if self.npcs is not None:
            self.npcs.actualizar(dt)
        if self.nexus is not None:
            self.nexus.actualizar(dt)
            for jugador in self.jugadores:
                panel = jugador.panel or {}
                if panel.get("tipo") == "celular" and panel.get("vista") == "feed":
                    # Lo nuevo que llega aparece aunque tenga el celular abierto;
                    # el cursor se queda sobre la misma publicación.
                    antes = panel["opciones"]
                    elegida = antes[jugador.cursor] if jugador.cursor < len(antes) else None
                    panel["opciones"] = celular.opciones_feed(self, jugador)
                    if elegida in panel["opciones"]:
                        jugador.cursor = panel["opciones"].index(elegida)
        self._actualizar_minijuegos(dt)
        self._actualizar_pulsos(dt)
        self._actualizar_salas(dt)
        self._actualizar_ambiente(dt)
        if self.logros is not None:
            self.logros.actualizar(dt)
        if self.presentacion is not None:
            self.presentacion.revisar()

        if self.mision is not None:
            self.mision.actualizar(dt)
            if self.mision.resultado is not None:
                self.terminar_ronda()
                return

        if not en_tutorial:
            self.tiempo_jugado_ms += dt
            if self.tiempo_restante_ms is not None:
                self.tiempo_restante_ms -= dt
        # Solo en un mapa sin misión se acaba la ronda por tiempo.
        if self.tiempo_restante_ms is not None and self.tiempo_restante_ms <= 0:
            self.tiempo_restante_ms = 0
            self.terminar_ronda()

    def _extras_dibujo(self):
        """Lo del mapa que dibujan las habilidades (screens/roles.py)."""
        return {
            "terminales": self.terminales, "paneles": self.paneles, "piezas": self.piezas,
            "senuelos": self.senuelos, "senales": self.senales, "mision": self.mision,
            "puertas_dobles": self.puertas_dobles, "compuertas": self.compuertas,
            "eventos": self.eventos, "tutorial": self.tutorial, "infiltrado": self.infiltrado,
            "guardia_planta": self.guardia_planta,
            # Campo de visión siempre; la oscuridad de la linterna, solo en un apagón.
            "vision": self.oscuridad,
            "oscuridad": self.oscuridad and self.eventos is not None and self.eventos.apagon,
            "sin_luz": self.sin_luz,
            "nexus": self.nexus,
            "npcs": self.npcs.npcs if self.npcs is not None else (),
            "escolta": self.npcs.escoltado if self.npcs is not None else None,
            "dificultad": self.dificultad,
        }

    def _actualizar_pulsos(self, dt):
        """Cada jugador ajusta su pulso según el alien más cercano."""
        for jugador in self.jugadores:
            centro = jugador.hitbox.center
            if self.en_tutorial:
                jugador.actualizar_pulso(dt, None, False)
                continue
            # El Cambiaformas disfrazado no asusta: nadie sabe que es un alien.
            distancia = min((math.hypot(a.centro[0] - centro[0], a.centro[1] - centro[1])
                             for a in self._aliens_a_la_vista()), default=None)
            if not jugador.cazable:
                distancia = None
            visto = any(a.objetivo is jugador for a in self.aliens)
            jugador.actualizar_pulso(dt, distancia, visto)

    def _actualizar_salas(self, dt):
        """En qué sala está cada uno (para el HUD). Entre dos salas, o en un
        hueco sin sala, se queda con la última."""
        for jugador in self.jugadores:
            jugador.sala_cambio_ms = max(0, jugador.sala_cambio_ms - dt)
            nombre = salas_mapa.sala_en(getattr(self, "salas", ()), jugador.hitbox.center)
            if nombre and nombre != jugador.sala:
                # Al entrar a una sala nueva, el nombre se resalta un momento.
                jugador.sala_cambio_ms = 1800 if jugador.sala is not None else 0
                jugador.sala = nombre

    def _aliens_a_la_vista(self):
        """Los aliens que se notan como aliens (sin el Cambiaformas disfrazado
        ni la Sombra cuando se esfumó)."""
        return [a for a in self.aliens
                if not getattr(a, "disfrazado", False) and not getattr(a, "oculta", False)]

    def terminar_ronda(self):
        if self.mision is not None:
            self.mision.terminar_sin_escapar()   # si nadie ganó todavía (Terminar partida)
        if self.logros is not None:
            self.logros.al_terminar()
            # Para Menú > Logros: los que salieron en esta partida.
            historial_logros.agregar(n.clave for n in self.logros.arbol.preorden() if n.obtenido)
        if self.mision is not None and self.mision.activa:
            self.sonar("victoria" if self.mision.resultado == "victoria" else "derrota", 0.8)
        for jugador in self.jugadores:
            jugador.cerrar_panel()
        self._reiniciar_resultados()
        self.transitions.request(self, "resultados")

    # -- Abrir zonas ------------------------------------------------------------

    def interactuar(self, jugador):
        """El jugador presionó su tecla de interacción sobre una zona."""
        zona = self.zona_bajo(jugador)
        if zona is None:
            return
        if zona["tipo"] == "nexus":
            self._abrir_nexus(jugador, zona)

    def _abrir_nexus(self, jugador, zona):
        """Terminal NEXUS: central de ayuda (celular.panel_ayuda). Cómo va la
        confianza, temas de uso sano de NEXUS, repasar el tutorial y, mientras
        exista, el caso del infiltrado (infiltrado.py)."""
        if self.sin_luz:
            jugador.avisar("La terminal NEXUS está apagada: no hay luz.", (245, 130, 120))
            return
        if self.logros is not None:
            self.logros.conseguir("conectado", jugador)
        jugador.abrir_panel(celular.panel_ayuda(self, jugador, zona))

    # -- Resolver la opción elegida ---------------------------------------------

    def confirmar(self, jugador):
        """El jugador confirmó la opción sobre la que tiene el cursor."""
        panel = jugador.panel
        if panel is None:
            return

        tipo = panel.get("tipo")
        if tipo in ("aviso", "resultado"):
            jugador.cerrar_panel()
            return
        if tipo == "habilidades":
            self._confirmar_habilidad(jugador)
            return
        if tipo == "emision":
            acciones_rol.poner_emision(self, jugador)
            return
        if tipo == "celular":
            celular.confirmar(self, jugador)
            return

        accion = panel.get("accion")
        indice = jugador.cursor
        if accion == "soltar":
            tipos = panel.get("tipos", [])
            jugador.cerrar_panel()
            if indice < len(tipos):
                self._soltar_objeto(jugador, tipos[indice])
            return
        if accion == "codigo" and self.mision is not None:
            self.mision.resolver_codigo(jugador, indice)
        elif accion in ("infiltrado_menu", "infiltrado_acusar"):
            self._resolver_infiltrado(jugador, panel, indice)
        elif accion in ("ayuda_menu", "ayuda_tema"):
            celular.confirmar_ayuda(self, jugador)

    # -- Soltar objetos del inventario -------------------------------------------------

    def _inventario(self, jugador):
        """[(tipo, cantidad)] de lo que lleva, en el orden del cuadro de inventario."""
        objetos = [("pieza", jugador.piezas)] if getattr(jugador, "piezas", 0) > 0 else []
        for tipo in ("decodificador", "kit", "fruta", "abono",
                     "prueba_audio", "prueba_expediente", "prueba_captura"):
            if jugador.objetos.get(tipo, 0) > 0:
                objetos.append((tipo, jugador.objetos[tipo]))
        return objetos

    def soltar(self, jugador):
        """Tecla de soltar: si lleva una sola clase de cosa, la suelta; si no,
        un panel para escoger cuál."""
        from screens.paneles import NOMBRE_OBJETO
        objetos = self._inventario(jugador)
        if not objetos:
            jugador.avisar("No llevas nada que soltar.", (210, 210, 220))
            return
        if len(objetos) == 1:
            self._soltar_objeto(jugador, objetos[0][0])
            return
        jugador.abrir_panel({
            "tipo": "opciones", "accion": "soltar", "tipos": [t for t, _ in objetos],
            "titulo": "Soltar",
            "cuerpo": ["¿Qué dejas en el piso? Cualquiera de ustedes lo puede recoger."],
            "opciones": [{"texto": f"{NOMBRE_OBJETO[t][0]}" + (f"  (llevas {n})" if n > 1 else "")}
                         for t, n in objetos],
            "pie": (f"[{jugador.pista_mover()}] elegir   [{jugador.nombre_tecla('interactuar')}] "
                    f"soltar   [{jugador.nombre_tecla('soltar')}] cerrar"),
        })

    def _soltar_objeto(self, jugador, tipo):
        """Deja uno de `tipo` a sus pies: una pieza vuelve a las piezas del mapa
        (la ve el Forjador o quien lleve el kit), un decodificador o kit a los
        consumibles de la misión y una prueba del infiltrado a sus pruebas."""
        from screens.paneles import NOMBRE_OBJETO
        from misiones.mision import TAMANO_CONSUMIBLE
        from misiones.infiltrado import TAMANO_PRUEBA
        tamano = {"pieza": (34, 34)}.get(tipo, TAMANO_PRUEBA if tipo.startswith("prueba") else TAMANO_CONSUMIBLE)
        pie = jugador.hitbox.midbottom
        x, y = self.mundo.punto_libre((pie[0] - tamano[0] // 2, pie[1] - tamano[1] // 2), *tamano)
        rect = pygame.Rect(x, y, *tamano)
        if tipo == "pieza":
            if jugador.piezas <= 0:
                return
            jugador.piezas -= 1
            # `solto`: no la vuelve a recoger hasta que se mueva de encima.
            self.piezas.append({"rect": rect, "recogida": False, "solto": jugador})
        elif tipo.startswith("prueba"):
            if self.infiltrado is None or tipo not in jugador.objetos:
                return
            jugador.objetos.discard(tipo)
            self.infiltrado.pruebas.append({"rect": rect, "tipo": tipo, "tomada": False})
        else:
            if self.mision is None or tipo not in jugador.objetos:
                return
            jugador.objetos.discard(tipo)
            self.mision.consumibles.append({"rect": rect, "tipo": tipo, "tomado": False})
        jugador.avisar(f"Soltaste: {NOMBRE_OBJETO[tipo][0]}", (210, 210, 220))
        self.sonar("recoger", 0.4)

    def _resolver_infiltrado(self, jugador, panel, indice):
        """Menú de la terminal durante el caso del infiltrado (infiltrado.py)."""
        caso = self.infiltrado
        if caso is None:
            jugador.cerrar_panel()
            return
        if panel["accion"] == "infiltrado_acusar":
            candidatos = panel["candidatos"]
            if indice >= len(candidatos) or not caso.activo:
                jugador.cerrar_panel()      # "Mejor no"
                return
            texto, puntos = caso.acusar(jugador, candidatos[indice])
            jugador.tareas_hechas += 1
            self._panel_resultado(jugador, texto, puntos, terminal=True)
            return
        acciones = panel["acciones"]
        if indice >= len(acciones):
            return
        eleccion = acciones[indice]
        if eleccion == "subir" and caso.activo:
            texto, puntos = caso.subir(jugador)
            jugador.tareas_hechas += 1
            self._panel_resultado(jugador, texto, puntos, terminal=True)
        elif eleccion == "acusar" and caso.activo:
            jugador.abrir_panel(caso.panel_acusar(jugador))
        else:
            jugador.cerrar_panel()

    def _panel_resultado(self, jugador, texto, puntos, terminal=False):
        if puntos > 0:
            resumen, color = f"+{puntos} puntos", (120, 230, 150)
        elif puntos < 0:
            resumen, color = f"{puntos} puntos", (245, 130, 120)
        else:
            resumen, color = "sin puntos", (220, 220, 220)
        jugador.avisar(resumen, color)
        jugador.abrir_panel({
            "tipo": "resultado",
            "titulo": resumen,
            "cuerpo": [texto],
            "pie": f"[{jugador.nombre_tecla('interactuar')}] seguir",
            "nexus_terminal": terminal,
        })

    # -- Habilidades -------------------------------------------------------------

    def alternar_habilidades(self, jugador):
        if jugador.panel is not None and jugador.panel.get("tipo") == "habilidades":
            jugador.cerrar_panel()
        elif jugador.panel is None:
            jugador.abrir_panel({"tipo": "habilidades"})

    def _confirmar_habilidad(self, jugador):
        opciones = jugador.arbol.opciones()
        if not opciones:
            jugador.cerrar_panel()
            return
        indice = min(jugador.cursor, len(opciones) - 1)
        # Las habilidades se pagan con los puntos del EQUIPO (ver mision.Equipo).
        ok, mensaje, costo = jugador.arbol.desbloquear(opciones[indice].clave,
                                                       jugador.puntos_para_habilidades)
        if ok:
            if jugador.equipo is not None:
                jugador.equipo.gastar(costo)
            else:
                jugador.sumar_puntos(-costo)
            jugador.avisar(mensaje, (255, 214, 64))
            self.sonar("acierto", 0.7)
            jugador.cursor = 0
        else:
            jugador.avisar(mensaje, (245, 130, 120))

    # -- Entrada ------------------------------------------------------------------

    def _tecla_en_partida(self, key):
        """Reparte la tecla al jugador dueño de esa tecla.

        Cada rama sale con `return` SOLO si la tecla era de ese jugador. Antes,
        la rama del jugador con un panel abierto terminaba en un `return` suelto
        que se ejecutaba siempre, incluso cuando la tecla no era suya: mientras
        el jugador 1 tenía algo abierto se tragaba todas las teclas y el
        jugador 2 no podía abrir nada. Al revés no pasaba, porque el jugador 1
        se revisa primero y su rama sí hacía `continue`.
        """
        for jugador in self.jugadores:
            # Escondido manda sobre todo lo demás: la tecla de interactuar es
            # la del minijuego si un alien lo está revisando, y si no, la de
            # salir. Mientras está metido no abre habilidades ni zonas.
            # Encerrado en una celda: no puede hacer nada hasta que lo saquen.
            if jugador.preso is not None or jugador.eliminado:
                if any(jugador.es_tecla(key, a) for a in jugador.teclas):
                    return
                continue

            if jugador.escondido:
                if jugador.es_tecla(key, "interactuar"):
                    if jugador.minijuego is not None:
                        acierto = jugador.minijuego.presionar(jugador)
                        self.sonar("acierto" if acierto else "fallo", 0.6)
                    else:
                        jugador.salir_del_escondite()
                    return
                if any(jugador.es_tecla(key, a) for a in ("habilidades", "habilidad", "celular")):
                    return
                continue

            # Con el celular en el inicio, izquierda/derecha cambian de pestaña.
            if (jugador.panel is not None and jugador.panel.get("tipo") == "celular"
                    and (jugador.es_tecla(key, "izquierda") or jugador.es_tecla(key, "derecha"))):
                if celular.cambiar_pestana(self, jugador, -1 if jugador.es_tecla(key, "izquierda") else 1):
                    jugador.cursor = 0
                    self.sonar("menu_mover", 0.35)
                return

            # El celular (NEXUS): abre, va atrás o cierra. Con una Terminal NEXUS
            # abierta, la cierra (no abre el celular).
            if jugador.es_tecla(key, "celular"):
                if jugador.panel is not None and jugador.panel.get("nexus_terminal"):
                    jugador.cerrar_panel()
                    self.sonar("menu_mover", 0.4)
                elif jugador.panel is not None and jugador.panel.get("tipo") == "celular":
                    celular.volver(self, jugador)
                elif jugador.panel is None:
                    celular.abrir(self, jugador)
                    self.sonar("menu_mover", 0.4)
                return

            # El mapa de la Emisión abierto: la tecla de habilidad o la del
            # árbol lo cierran sin gastar la habilidad.
            if (jugador.panel is not None and jugador.panel.get("tipo") == "emision"
                    and (jugador.es_tecla(key, "habilidad") or jugador.es_tecla(key, "habilidades"))):
                jugador.cerrar_panel()
                return

            if jugador.es_tecla(key, "habilidades"):
                self.alternar_habilidades(jugador)
                return

            if jugador.es_tecla(key, "soltar"):
                if jugador.panel is not None and jugador.panel.get("accion") == "soltar":
                    jugador.cerrar_panel()
                elif not jugador.ocupado:
                    self.soltar(jugador)
                return

            if jugador.es_tecla(key, "habilidad"):
                if (self.en_tutorial and not jugador.ocupado
                        and not self.tutorial.esta_listo(jugador)):
                    # En el tutorial, la tecla de habilidad pasa de paso.
                    self.tutorial.siguiente(jugador)
                    self.sonar("menu_ok", 0.5)
                    if not self.tutorial.activo:
                        self._terminar_tutorial()
                    return
                if not jugador.ocupado:
                    acciones_rol.usar_habilidad(self, jugador)
                return

            if not jugador.ocupado:
                if jugador.es_tecla(key, "interactuar"):
                    # Lo de la misión (celdas, puerta, notas, cápsula...) va
                    # primero; después zona, estación de su rol y escondite.
                    if self.eventos is not None and self.eventos.caja_cerca(jugador):
                        jugador.avisar("Mantén la tecla para cambiar los fusibles.", (255, 214, 64))
                        return
                    if self.eventos is not None and self.eventos.caja_falsa_cerca(jugador):
                        jugador.avisar("Esta caja está bien. Busquen la que parpadea en rojo.",
                                       (245, 130, 120))
                        return
                    if puertas.panel_cerca(self.puertas_dobles, jugador) is not None:
                        jugador.avisar("Mantén la tecla aquí mientras otro mantiene el otro panel.",
                                       (255, 214, 64))
                        return
                    if self.guardia_planta is not None and self.guardia_planta.interactuar(jugador):
                        return
                    if self.mision is not None and self.mision.interactuar(jugador):
                        return
                    if self.infiltrado is not None and self.infiltrado.interactuar(jugador):
                        return
                    estacion = (None if self.zona_bajo(jugador)
                                else acciones_rol.estacion_bajo(self, jugador))
                    escondite = (None if self.zona_bajo(jugador) or estacion
                                 else self.escondite_bajo(jugador))
                    if estacion is not None:
                        acciones_rol.usar_estacion(self, jugador, estacion)
                    elif escondite is not None:
                        jugador.esconderse(escondite)
                    elif self.zona_bajo(jugador) is None and self.npcs is not None:
                        self.npcs.hablar(jugador)     # "¿vienes conmigo?" (npcs.py)
                    else:
                        self.interactuar(jugador)
                    return
                continue  # no era suya: que la vea el siguiente

            # Un mosaico (la Terminal NEXUS): se recorre en dos dimensiones.
            filas = (jugador.panel or {}).get("filas")
            if filas:
                for nombre, dfila, dcol in (("arriba", -1, 0), ("abajo", 1, 0),
                                            ("izquierda", 0, -1), ("derecha", 0, 1)):
                    if jugador.es_tecla(key, nombre):
                        jugador.cursor = mover_en_mosaico(filas, jugador.cursor, dfila, dcol)
                        self.sonar("menu_mover", 0.35)
                        return
            total = self._total_opciones(jugador)
            if jugador.es_tecla(key, "arriba"):
                jugador.mover_cursor(-1, total)
                self.sonar("menu_mover", 0.35)
                return
            if jugador.es_tecla(key, "abajo"):
                jugador.mover_cursor(1, total)
                self.sonar("menu_mover", 0.35)
                return
            if jugador.es_tecla(key, "interactuar"):
                self.sonar("menu_ok", 0.4)
                self.confirmar(jugador)
                return
            # Tampoco era suya aunque tenga un panel abierto: se sigue buscando.

    def _total_opciones(self, jugador):
        panel = jugador.panel or {}
        if panel.get("tipo") == "habilidades":
            return len(jugador.arbol.opciones())
        return len(panel.get("opciones", []))

    # -- Loop principal -------------------------------------------------------------

    def run(self):
        while self.running:
            dt = self.clock.tick(DEFAULT_FPS)
            if self.mostrar_fps and self.cazar_tirones:
                self.diagnostico.empezar()
            t_eventos = time.perf_counter()
            self._manejar_eventos()
            self._sonido_de_fondo()
            t0 = time.perf_counter()
            if self.current_screen == "partida" and self.transitions.is_idle():
                if self.pausa is not None:
                    self.pausa.actualizar(dt)   # el juego queda congelado
                else:
                    self._actualizar_partida(dt)
            self._actualizar_carga(dt)
            self.transitions.update(self, dt)
            t1 = time.perf_counter()
            self._dibujar()
            t2 = time.perf_counter()
            if self.mostrar_fps:
                self._medir_cuadro(dt, (t1 - t0) * 1000, (t2 - t1) * 1000)
            pygame.display.flip()
            if self.segunda is not None:
                self.segunda.mostrar()
            # (sin F3 no hay perfil y esto no hace nada)
            self.diagnostico.terminar(self, {"eventos": (t0 - t_eventos) * 1000,
                                             "actualizar": (t1 - t0) * 1000,
                                             "dibujar": (t2 - t1) * 1000,
                                             "flip": (time.perf_counter() - t2) * 1000})
        pygame.quit()
        sys.exit()

    def _medir_cuadro(self, dt, ms_actualizar, ms_dibujar):
        """F3: FPS y milisegundos de actualizar/dibujar arriba a la derecha.
        Los tirones (cuadros de más de 40 ms) los anota juego/diagnostico.py
        en la consola y en Guardado/tirones.txt, con lo que los causó."""
        suave = self._tiempos_cuadro
        suave[0] += (ms_actualizar - suave[0]) * 0.1
        suave[1] += (ms_dibujar - suave[1]) * 0.1
        texto = (f"{self.clock.get_fps():.0f} FPS  ·  actualizar {suave[0]:.1f} ms  ·  "
                 f"dibujar {suave[1]:.1f} ms")
        if self.cazar_tirones:
            texto += (f"  ·  tirones: {self.diagnostico.tirones}  ·  cuadro típico "
                      f"{self.diagnostico.tipico:.0f} ms (perfilando)")
        imagen = self.small_font.render(texto, True, (240, 240, 240))
        fondo = pygame.Rect(0, 0, imagen.get_width() + 12, imagen.get_height() + 6)
        fondo.topright = (self.ancho - 6, 6)
        pygame.draw.rect(self.screen, (10, 12, 20), fondo)
        self.screen.blit(imagen, (fondo.x + 6, fondo.y + 3))

    def _sonido_de_fondo(self):
        """El zumbido de la nave suena durante la partida; se calla en los
        apagones (las máquinas se apagan) y baja en la pausa."""
        if self.current_screen == "partida" and self.mundo is not None:
            if self.eventos is not None and self.eventos.apagon:
                volumen = 0.0
            else:
                volumen = 0.12 if self.pausa is not None else 0.35
            audio_manager.bucle("ambiente", volumen)
        elif audio_manager.sonando_bucle:
            audio_manager.parar_bucle()

    def _manejar_eventos(self):
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                self.running = False
            elif self.segunda is not None and evento.type == getattr(pygame, "WINDOWCLOSE", -1):
                # Con dos ventanas, cerrar la principal (Alt+F4) ya no manda
                # QUIT (queda la otra abierta): se sale igual.
                if not self.segunda.es_suyo(evento):
                    self.running = False
            elif (self.segunda is not None and self.segunda.es_suyo(evento)
                  and evento.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION)):
                continue        # el mouse en la otra pantalla no cuenta
            elif self.carga is not None:
                continue        # cargando: no se toca nada mientras el otro hilo arma la partida
            elif evento.type == pygame.KEYDOWN:
                self._manejar_tecla(evento.key)
            elif evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
                self._manejar_click(evento.pos)
            elif evento.type == pygame.MOUSEMOTION and self.current_screen == "partida":
                if self.pausa is not None:
                    self.pausa.mover_mouse(evento.pos)
                else:
                    self._mouse_en_mapa(evento.pos)
            elif evento.type in (pygame.JOYBUTTONDOWN, pygame.JOYHATMOTION,
                                 pygame.JOYAXISMOTION, pygame.JOYDEVICEADDED,
                                 pygame.JOYDEVICEREMOVED):
                for puesto, accion in self.mandos.evento(evento):
                    self._tecla_mando(puesto, accion)
                if evento.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                    self._sincronizar_mandos()

    def _tecla_mando(self, puesto, accion):
        """Un botón del mando: en partida y en la selección de rol es la tecla
        virtual de ese jugador; en los menús hace de flechas, Enter y Esc."""
        if self.current_screen == "controles":
            # Aquí el mando es suyo: A lo toma (o lo suelta), B vuelve.
            if accion in ("interactuar", "pausa"):
                self.tomar_esquema(puesto)
            elif accion == "volver":
                if puesto in self.esquemas:
                    self.tomar_esquema(puesto)
                elif not self.transitions.active:
                    self.abrir_dificultad()
            return
        if (self.current_screen == "partida" and self.pausa is None and self.presentacion is not None
                and self.presentacion.abierta):
            if accion in ("interactuar", "habilidad", "volver", "pausa"):
                self.presentacion.cerrar()
            return
        if (self.current_screen == "partida" and (self.pausa is not None or accion == "pausa")
                or self.current_screen == "resultados"):
            # START abre la pausa; con la pausa abierta el mando la maneja
            # como en los menús (cruceta, A para aceptar, B o START para volver).
            tecla = {"arriba": pygame.K_UP, "abajo": pygame.K_DOWN,
                     "izquierda": pygame.K_LEFT, "derecha": pygame.K_RIGHT,
                     "interactuar": pygame.K_RETURN, "volver": pygame.K_ESCAPE,
                     "pausa": pygame.K_ESCAPE}.get(accion)
            if tecla is not None:
                self._manejar_tecla(tecla)
            return
        if accion in ("izquierda", "derecha"):
            # Fuera del árbol de logros solo sirven para las pestañas del celular.
            jugador = next((j for j in self.jugadores if j.esquema == puesto), None)
            if (self.current_screen == "partida" and jugador is not None and jugador.panel
                    and jugador.panel.get("tipo") == "celular"):
                if celular.cambiar_pestana(self, jugador, -1 if accion == "izquierda" else 1):
                    jugador.cursor = 0
                    self.sonar("menu_mover", 0.35)
            return
        if accion == "pausa":
            accion = "volver" if self.current_screen == "roles" else "interactuar"
        if self.current_screen in ("partida", "roles"):
            if accion == "volver":
                jugador = next((j for j in self.jugadores if j.esquema == puesto), None)
                if self.current_screen == "partida" and jugador is not None and jugador.ocupado:
                    if jugador.panel is not None and jugador.panel.get("tipo") == "celular":
                        celular.volver(self, jugador)      # B en el celular: atrás
                    else:
                        jugador.cerrar_panel()
                elif self.current_screen == "partida" and jugador is not None:
                    # Caminando, B suelta algo del inventario.
                    self._manejar_tecla(tecla_virtual(puesto, "soltar"))
                return
            self._manejar_tecla(tecla_virtual(puesto, accion))
            return
        tecla = {"arriba": pygame.K_UP, "abajo": pygame.K_DOWN,
                 "interactuar": pygame.K_RETURN}.get(accion)
        if accion == "volver" and self.current_screen != "menu":
            tecla = pygame.K_ESCAPE   # en el menú, Esc cierra el juego: ahí B no hace nada
        if tecla is not None:
            self._manejar_tecla(tecla)

    def _sincronizar_mandos(self):
        """Se conectó o desconectó un mando con la partida andando."""
        for jugador in self.jugadores:
            if jugador.esquema in PUESTOS_CON_MANDO:
                jugador.con_mando = self.mandos.hay_mando(jugador.esquema)
                jugador.puede_moverse = jugador.con_mando and not jugador.eliminado
                jugador.controles_nombre = (f"Mando {jugador.esquema - 1}" if jugador.con_mando
                                            else NOMBRE_CONTROLES[jugador.esquema])

    def _manejar_tecla(self, key):
        if key == pygame.K_F11:
            self.alternar_pantalla_completa()
            return
        if key == pygame.K_F9:
            self.alternar_dos_pantallas()
            return
        if key == pygame.K_F3:
            # Tres pasos: FPS solo (lo que de verdad va el juego) -> FPS y
            # cazador de tirones (perfila cada cuadro: todo va un poco más
            # lento) -> apagado.
            if not self.mostrar_fps:
                self.mostrar_fps, self.cazar_tirones = True, False
            elif not self.cazar_tirones:
                self.cazar_tirones = True
            else:
                self.mostrar_fps = self.cazar_tirones = False
            return
        if self.transitions.active:
            return
        if self.current_screen in ("menu", "cantidad", "dificultad", "roles", "resultados") or (
                self.current_screen == "partida" and self.pausa is not None):
            if key in TECLAS_MOVER_MENU:
                self.sonar("menu_mover", 0.5)
            elif key in TECLAS_OK_MENU:
                self.sonar("menu_ok", 0.6)

        if self.current_screen == "menu":
            if key in (pygame.K_UP, pygame.K_w):
                self.menu_selected = (self.menu_selected - 1) % len(self.menu_buttons)
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.menu_selected = (self.menu_selected + 1) % len(self.menu_buttons)
            elif key == pygame.K_RETURN:
                self._activar_opcion_menu(self.menu_buttons[self.menu_selected].action)
            elif key == pygame.K_ESCAPE:
                self.running = False

        elif self.current_screen == "cantidad":
            if key in (pygame.K_UP, pygame.K_w):
                self.cantidad_seleccionada = (self.cantidad_seleccionada - 1) % len(OPCIONES)
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.cantidad_seleccionada = (self.cantidad_seleccionada + 1) % len(OPCIONES)
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.confirmar_cantidad()
            elif key == pygame.K_ESCAPE:
                self.transitions.request(self, "menu")

        elif self.current_screen == "dificultad":
            if key in (pygame.K_UP, pygame.K_w):
                self.dificultad_seleccionada = (self.dificultad_seleccionada - 1) % len(DIFICULTADES)
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.dificultad_seleccionada = (self.dificultad_seleccionada + 1) % len(DIFICULTADES)
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.confirmar_dificultad()
            elif key == pygame.K_ESCAPE:
                self.transitions.request(self, "cantidad")

        elif self.current_screen == "controles":
            self._tecla_en_controles(key)

        elif self.current_screen == "roles":
            if key == pygame.K_ESCAPE:
                # Con mandos, atrás es escoger controles; sin mandos, la dificultad.
                if self.mandos.por_puesto:
                    self.abrir_controles()
                else:
                    self.abrir_dificultad()
            else:
                self._tecla_en_seleccion(key)

        elif self.current_screen == "partida" and self.pausa is not None:
            self._accion_pausa(self.pausa.tecla(key))

        elif self.current_screen == "partida" and self.presentacion is not None and self.presentacion.abierta:
            # La ventana del alien nuevo (Fácil): la cierra cualquiera.
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_ESCAPE) or any(
                    j.es_tecla(key, accion) for j in self.jugadores for accion in ("interactuar", "habilidad")):
                self.presentacion.cerrar()

        elif self.current_screen == "partida":
            # Hitboxes, árbol del alien y campo de visión van en Pausa > Opciones.
            if key == pygame.K_ESCAPE:
                self.pausa = MenuPausa(self)
                self.sonar("pausa", 0.6)
            else:
                self._tecla_en_partida(key)

        elif self.current_screen == "resultados":
            self._tecla_resultados(key)

        elif self.current_screen == "logros":
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_BACKSPACE, pygame.K_ESCAPE):
                self.transitions.request(self, "menu")
            elif self.catalogo_logros is not None:
                self.catalogo_nodo = mover_en_logros(self.catalogo_logros, self.catalogo_nodo, key)

        elif self.current_screen in ("ayuda", "creditos"):
            if key in (pygame.K_RETURN, pygame.K_BACKSPACE, pygame.K_ESCAPE):
                self.transitions.request(self, self.pantalla_anterior)

    # -- Pantalla de resultados ------------------------------------------------------

    def _reiniciar_resultados(self):
        self.resultados_vista = "resumen"     # o "logros": el árbol completo
        self.resultados_sel = 0
        self.resultados_nodo = None
        self.resultados_rects = []
        self.resultados_rects_logros = {}

    def _tecla_resultados(self, key):
        if self.resultados_vista == "logros":
            if key in (pygame.K_ESCAPE, pygame.K_BACKSPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                self.resultados_vista = "resumen"
            else:
                self.resultados_nodo = mover_en_logros(self.logros.arbol, self.resultados_nodo, key)
            return
        opciones = opciones_resultados(self.logros)
        if key in (pygame.K_LEFT, pygame.K_UP, pygame.K_a, pygame.K_w):
            self.resultados_sel = (self.resultados_sel - 1) % len(opciones)
        elif key in (pygame.K_RIGHT, pygame.K_DOWN, pygame.K_d, pygame.K_s):
            self.resultados_sel = (self.resultados_sel + 1) % len(opciones)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._activar_resultados(opciones[self.resultados_sel % len(opciones)][1])
        elif key == pygame.K_ESCAPE:
            self._activar_resultados("menu")

    def _activar_resultados(self, accion):
        if accion == "logros" and self.logros is not None:
            self.resultados_vista = "logros"
            self.resultados_nodo = self.logros.arbol.raiz
        elif accion == "menu":
            self.transitions.request(self, "menu")

    def _click_resultados(self, pos):
        if self.resultados_vista == "logros":
            for nodo, rect in self.resultados_rects_logros.items():
                if rect.collidepoint(pos):
                    self.resultados_nodo = nodo
            return
        for i, rect in enumerate(self.resultados_rects):
            if rect.collidepoint(pos):
                self.resultados_sel = i
                self._activar_resultados(opciones_resultados(self.logros)[i][1])
                return

    def _accion_pausa(self, accion):
        """Lo que pidió el menú de pausa (pausa.py)."""
        if accion == "continuar":
            self.pausa = None
        elif accion == "terminar":
            self.pausa = None
            for jugador in self.jugadores:
                jugador.cerrar_panel()
            self.transitions.request(self, "menu")
        elif accion == "pantalla_completa":
            self.alternar_pantalla_completa()

    def _jugador_con_mapa_en(self, pos):
        """(jugador, punto del mundo) si `pos` cae en el mapa de la Emisión de
        alguien, o (None, None)."""
        for jugador in self.jugadores:
            panel = jugador.panel
            if panel is None or panel.get("tipo") != "emision" or "rect_mapa" not in panel:
                continue
            rect, escala = panel["rect_mapa"], panel["escala_mapa"]
            if rect.collidepoint(pos):
                return jugador, ((pos[0] - rect.x) / escala, (pos[1] - rect.y) / escala)
        return None, None

    def _mouse_en_mapa(self, pos):
        jugador, punto = self._jugador_con_mapa_en(pos)
        if jugador is not None:
            jugador.panel["cursor_mapa"] = [punto[0], punto[1]]

    def _manejar_click(self, pos):
        if self.current_screen == "partida":
            if self.pausa is not None:
                if not self.transitions.active:
                    self._accion_pausa(self.pausa.click(pos))
                return
            jugador, punto = self._jugador_con_mapa_en(pos)
            if jugador is not None:
                acciones_rol.poner_emision(self, jugador, punto)
            return
        if self.current_screen == "resultados" and not self.transitions.active:
            self._click_resultados(pos)
            return
        # Cuántos juegan y la dificultad también se escogen con el mouse.
        if self.current_screen in ("cantidad", "dificultad") and not self.transitions.active:
            for i, rect in enumerate(getattr(self, "rects_opciones", ())):
                if rect.collidepoint(pos):
                    self.sonar("menu_ok", 0.6)
                    if self.current_screen == "cantidad":
                        self.cantidad_seleccionada = i
                        self.confirmar_cantidad()
                    else:
                        self.dificultad_seleccionada = i
                        self.confirmar_dificultad()
                    return
            return
        if self.current_screen == "logros" and not self.transitions.active:
            for nodo, rect in self.catalogo_rects.items():
                if rect.collidepoint(pos):
                    self.catalogo_nodo = nodo
            return
        if self.current_screen != "menu" or self.transitions.active:
            return
        for i, boton in enumerate(self.menu_buttons):
            if boton.contains(pos):
                self.menu_selected = i
                self._activar_opcion_menu(boton.action)
                return

    def abrir_catalogo_logros(self):
        """Menú > Logros: el árbol completo, con los que salieron alguna vez
        en este computador (juego/historial_logros.py)."""
        self.catalogo_veces = historial_logros.cargar()
        self.catalogo_logros = ArbolLogros(ARBOL_LOGROS)
        for nodo in self.catalogo_logros.preorden():
            nodo.obtenido = self.catalogo_veces.get(nodo.clave, 0) > 0
        self.catalogo_nodo = self.catalogo_logros.raiz
        self.catalogo_rects = {}
        self.pantalla_anterior = "menu"
        self.transitions.request(self, "logros")

    def _activar_opcion_menu(self, accion):
        if accion == "jugar":
            self.pantalla_anterior = "partida"
            self.abrir_cantidad()
        elif accion == "salir":
            self.running = False
        elif accion == "red":
            # Menú > Jugar en red (cliente_servidor/lanzador.py): tiene su
            # propio bucle y vuelve aquí, al menú, cuando se acaba.
            from cliente_servidor import lanzador
            lanzador.abrir(self)
        elif accion == "logros":
            self.abrir_catalogo_logros()
        else:
            # Los créditos siempre arrancan desde el principio: si no, entrar y
            # salir varias veces los retomaba a mitad de camino.
            if accion == "creditos":
                self.credit_scroll = reiniciar_scroll()
            self.pantalla_anterior = "menu"
            self.transitions.request(self, accion)

    # -- Dibujo -----------------------------------------------------------------

    def _dibujar(self):
        if self.current_screen == "cargando":
            from screens.carga import render_carga
            carga = self.carga or self.carga_final or {}
            render_carga(self.screen, carga.get("ms", self.MIN_CARGA_MS), self._progreso_carga(),
                         carga.get("consejo", ""), carga.get("roles"))
        elif self.current_screen == "menu":
            render_menu(self.screen, self.menu_buttons, self.menu_selected)
        elif self.current_screen == "cantidad":
            self.rects_opciones = render_cantidad(self.screen, self.cantidad_seleccionada)
        elif self.current_screen == "dificultad":
            self.rects_opciones = render_dificultad(self.screen, self.dificultad_seleccionada)
        elif self.current_screen == "controles":
            render_controles(self.screen, self.esquemas, NOMBRE_ESQUEMA, self.esquemas_libres(),
                             [self.mandos.hay_mando(e) for e in range(len(NOMBRE_ESQUEMA))])
        elif self.current_screen == "roles":
            viewports = calcular_viewports(self.ancho, self.alto, self.cantidad_jugadores)
            render_roles(self.screen, viewports, self.seleccion_roles)
        elif self.current_screen == "partida":
            principal, _ = self._reparto_pantallas()
            extras = self._extras_dibujo()
            self._extras_segunda = extras         # (la otra pantalla usa los mismos)
            self._dibujar_partida_en(self.screen, principal, extras)
            if self.mostrar_arbol_alien and self.aliens:
                # (la Sombra entra y sale de la lista: que el índice no se pase)
                self.alien_en_vista = min(self.alien_en_vista, len(self.aliens) - 1)
                alien = self.aliens[self.alien_en_vista]
                render_arbol_alien(self.screen, alien, alien.arbol,
                                   self.alien_en_vista + 1, len(self.aliens))
            if self.vista_grafo == "nexus":
                render_grafo_nexus(self.screen, self.nexus)
            elif self.vista_grafo == "nave":
                render_grafo_nave(self.screen, self.mundo, self.aliens,
                                  self.npcs.npcs if self.npcs is not None else (), self.jugadores)
            if self.pausa is None:
                if self.presentacion is None or not self.presentacion.abierta:
                    render_aviso_logro(self.screen, self.logros)   # (con la presentación, espera)
            else:
                render_pausa(self.screen, self.pausa)
        elif self.current_screen == "resultados":
            if self.resultados_vista == "logros" and self.logros is not None:
                self.resultados_rects_logros = render_arbol_logros(
                    self.screen, self.logros.arbol, self.resultados_nodo)
            else:
                self.resultados_rects = render_resultados(
                    self.screen, self.jugadores, self.font, self.small_font, self.mision,
                    self.equipo, self.infiltrado, self.logros, self.resultados_sel,
                    self.nexus, self.cambiaformas, self.npcs, self.dificultad,
                    self.tiempo_jugado_ms)
        elif self.current_screen == "logros" and self.catalogo_logros is not None:
            self.catalogo_rects = render_arbol_logros(self.screen, self.catalogo_logros,
                                                      self.catalogo_nodo, self.catalogo_veces)
        elif self.current_screen == "ayuda":
            render_ayuda(self.screen, self.small_font)
        elif self.current_screen == "creditos":
            self.credit_scroll = render_creditos(self.screen, self.small_font, self.credit_scroll)

        self.transitions.draw(self.screen)
        self._dibujar_segunda()


if __name__ == "__main__":
    Game().run()
