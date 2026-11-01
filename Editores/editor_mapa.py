"""Editor de mapa: pon con el mouse todo lo que va en el mapa, sin tocar código.

    python Editores/editor_mapa.py            (elige el fondo en una lista)
    python Editores/editor_mapa.py Nave       (abre ese fondo directo)

Qué se pone aquí (las paredes siguen en Editores/hitbox_editor.py):

    1  Inicio de los jugadores     dónde aparecen al empezar
    2  Rutas de aliens             por dónde patrulla cada alien
    3  Escondites                  casilleros, armarios...
    4  Celdas                      a dónde van los que atrapan
    5  Puertas con código          se abren con un código (la 1.ª: fase 1). Después
                                   de poner una, los clics ponen sus notas de
                                   código (una trae el código); X termina. Cada
                                   puerta tiene su color, su código y sus notas
    6  Notas                       las normales, de historia
    7  Consolas de navegación      las que hay que apagar (fase 2)
    8  Cápsula de escape           fases 3 y 4; sin cápsula no hay misión
    9  Piezas                      las recoge el Forjador
    0  Terminales NEXUS            el caso del infiltrado
    ,  y  .  para las demás: compuertas (las cierra un evento), puertas para
             dos (con sus dos paneles), cajas de fusibles (para los apagones),
             terminales del Tecnomante, paneles del
             Forjador, consumibles (decodificador / kit), pruebas del infiltrado
             y salas (el nombre que sale en el HUD: Laboratorio, Pasillo...).
    En las rutas, T cambia el tipo de alien (Vigía, Ciego, Cazador).
    También se puede hacer clic en la lista de la derecha.

Mouse: clic izquierdo pone o arrastra, clic derecho borra, rueda hace zoom y
el clic del medio (o ESPACIO + arrastrar) mueve la vista.

Guarda en Hitboxes/<mapa>_objetos.json, que es lo que lee el juego
(objetos_mapa.py). Con M ese mapa pasa a ser el que usa el juego, y con F5 se
guarda y se abre el juego para probarlo.

Mientras editas, cada cosa se pinta según si está bien:
    verde     bien
    rojo      choca con una pared
    naranja   no se puede llegar caminando desde el inicio
    amarillo  está encima de otra cosa
y los tramos de una ruta que atraviesan una pared salen en rojo.
"""

import copy
import math
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

import pygame

from juego import objetos_mapa
from juego.mundo import Mundo, CARPETA_FONDOS
from data.tipos_alien import TIPOS_ALIEN, ORDEN_TIPOS, TIPO_POR_DEFECTO
from misiones.mision import notas_antes_de_la_puerta, sortear_candidatas, color_puerta


# -- Herramientas ------------------------------------------------------------------------

HERRAMIENTAS = [
    {"clave": "spawn", "nombre": "Inicio de los jugadores", "color": (255, 255, 255)},
    {"clave": "rutas_aliens", "nombre": "Rutas de aliens", "color": (236, 70, 60)},
    {"clave": "escondites", "nombre": "Escondites", "color": (130, 160, 210)},
    {"clave": "celdas", "nombre": "Celdas", "color": (190, 190, 205)},
    {"clave": "puertas_codigo", "nombre": "Puertas con código", "color": (200, 80, 90)},
    {"clave": "notas", "nombre": "Notas", "color": (240, 226, 170)},
    {"clave": "consolas", "nombre": "Consolas de navegación", "color": (180, 110, 255)},
    {"clave": "capsula", "nombre": "Cápsula de escape", "color": (90, 220, 230)},
    {"clave": "guardia", "nombre": "Guardia (frente a la cápsula)", "color": (156, 162, 138)},
    {"clave": "planta", "nombre": "Planta (fruta para el Guardia)", "color": (110, 200, 90)},
    {"clave": "piezas", "nombre": "Piezas", "color": (255, 170, 50)},
    {"clave": "nexus", "nombre": "Terminales NEXUS", "color": (90, 200, 255)},
    {"clave": "compuertas", "nombre": "Compuertas (evento)", "color": (255, 120, 60)},
    {"clave": "puertas_dobles", "nombre": "Puertas para dos", "color": (255, 214, 64)},
    {"clave": "fusibles", "nombre": "Cajas de fusibles", "color": (255, 240, 120)},
    {"clave": "pruebas", "nombre": "Pruebas del infiltrado", "color": (233, 120, 200)},
    {"clave": "terminales", "nombre": "Terminales (Tecnomante)", "color": (150, 120, 255)},
    {"clave": "paneles", "nombre": "Paneles y sellos (Forjador)", "color": (255, 120, 80)},
    {"clave": "consumibles", "nombre": "Consumibles (si falta un rol)", "color": (120, 200, 160)},
    {"clave": "salas", "nombre": "Salas (nombre en el HUD)", "color": (150, 205, 255)},
]
TECLAS_HERRAMIENTA = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5,
                      pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9, pygame.K_0]

# Cómo se guarda cada parte: lista de puntos [rx, ry], lista de diccionarios
# con nombre, un solo punto, o la puerta (punto con tamaño).
LISTAS = ("piezas", "celdas", "notas", "consolas", "consumibles", "nexus", "fusibles", "pruebas")
CON_NOMBRE = ("escondites", "terminales", "paneles")
UNICOS = ("spawn", "capsula", "guardia", "planta")
# Las notas de código de una puerta: normales (todas las dificultades) y
# "solo Difícil" (Difícil e Inteligente). Cosa del editor -> lista del archivo.
TIPO_NOTA_PUERTA = {"nota_codigo": "notas", "nota_dificil": "notas_dificil"}
# Rectángulos con tamaño, como la puerta, pero varios.
RECTS = ("compuertas", "puertas_dobles")
TAMANO_PANEL = (30, 30)
NOMBRE_SINGULAR = {
    "escondites": "Escondite", "terminales": "Terminal", "paneles": "Panel", "piezas": "Pieza",
    "celdas": "Celda", "notas": "Nota", "consolas": "Consola", "consumibles": "Consumible",
    "nexus": "NEXUS", "fusibles": "Fusibles", "pruebas": "Prueba",
}

# Tamaño en el juego (píxeles del mundo) de lo que ocupa cada cosa. Con esto se
# revisa si choca con paredes o se monta sobre otra.
TAMANOS = {
    "spawn": (48, 19),
    "escondites": (70, 40),
    "terminales": (60, 40),
    "paneles": (60, 40),
    "piezas": (34, 34),
    "celdas": (40, 40),
    "notas": (30, 30),
    "notas_codigo": (30, 30),
    "consolas": (70, 50),
    "capsula": (210, 130),
    "guardia": (150, 60),
    "planta": (56, 56),
    "consumibles": (34, 34),
    "nexus": (60, 60),
    "fusibles": (40, 46),
    "pruebas": (30, 30),
}
TAMANO_ALIEN = (34, 20)
NOMBRES_ESCONDITE = ["Casillero", "Armario", "Contenedor", "Ducto"]
# Los cuartos del modelo de la nave; T los recorre y Y escribe uno nuevo.
NOMBRES_SALA = ["Control", "General", "Laboratorio", "Prisión", "Residencial", "Biosfera",
                "Bahía", "Motores", "Comando", "Gestación", "Pasillo"]
TAMANO_MIN_SALA = 24      # píxeles del mundo: menos que esto es un clic suelto

AYUDA_HERRAMIENTA = {
    "spawn": ["Clic: los jugadores aparecen aquí.",
              "Clic derecho: volver al centro del mapa."],
    "rutas_aliens": ["T: cambia el tipo de alien de la ruta.",
                     "Clic: agrega un punto a la ruta elegida.",
                     "Clic en un punto: elegir esa ruta / arrastrarlo.",
                     "Clic derecho: borra un punto.",
                     "N: ruta nueva (= un alien nuevo).",
                     "TAB: siguiente ruta.  SUPR: borra la ruta.",
                     "Un solo punto = guardia quieto.",
                     "Ámbar: pasa por una puerta. Cerrada, el",
                     "alien patrulla su lado; abierta, toda."],
    "escondites": ["Clic: pone uno.  Arrastrar: lo mueve.",
                   "Clic derecho: lo borra.",
                   "T sobre uno: cambia el nombre."],
    "terminales": ["Clic: pone una.  Arrastrar: la mueve.",
                   "Clic derecho: la borra."],
    "paneles": ["Clic: pone un panel; el clic siguiente",
                "pone su sello (la barrera que levanta",
                "al repararlo: frena solo a los aliens).",
                "+ / - y [ / ]: tamaño del sello (mouse).",
                "Clic derecho: borra el panel o su sello."],
    "piezas": ["Clic: pone una.  Arrastrar: la mueve.",
               "Clic derecho: la borra."],
    "celdas": ["Clic: pone una celda (puede ir detrás",
               "de los barrotes, en la pared).",
               "Tiene que quedar cerca del piso: desde",
               "ahí la liberan. Clic derecho: borra."],
    "puertas_codigo": ["1) Clic: pone una puerta (la 1.ª es la de",
               "   la prisión: fase 1). Cada una, su color.",
               "2) Después, cada clic pone una NOTA DE",
               "   CÓDIGO de esa puerta: en una de ellas (se",
               "   sortea, de las de antes de la puerta)",
               "   sale su código. X: terminar.",
               "3) Con X apagada, otro clic pone otra",
               "   puerta. Clic en una puerta: la elige",
               "   (y sus notas siguen con los clics).",
               "F: las próximas notas son SOLO DIFÍCIL",
               "   (para poner afuera el código de una",
               "   puerta que en Fácil/Normal está adentro",
               "   de la prisión). F otra vez: normales.",
               "Arrastrar: mueve. Clic derecho: borra la",
               "nota; en una puerta, la quita con sus notas.",
               "+ / - y [ / ]: tamaño de la elegida."],
    "notas": ["Clic: pone una nota.  Arrastrar: mueve.",
              "Son las normales, de historia: el texto",
              "sale de data/notas.py, en orden. El",
              "código va en las notas de código (las",
              "pone la herramienta Puerta)."],
    "consolas": ["Clic: pone una consola.",
                 "Hay que apagarlas todas (fase 2)."],
    "guardia": ["Clic: el puesto del Guardia (uno solo), frente a la cápsula.",
                "No sale de la sala donde lo pongas (la Bahía).",
                "Clic derecho lo quita."],
    "planta": ["Clic: la planta (una sola) que da la fruta para el Guardia.",
               "La hace crecer el Biomante (o alguien con abono).",
               "Clic derecho la quita."],
    "capsula": ["Clic: pone la cápsula (una sola).",
                "Sin cápsula, el mapa no tiene misión.",
                "Clic derecho: la quita."],
    "consumibles": ["Clic: pone un punto.",
                    "Ahí aparece un decodificador o un kit",
                    "solo si falta el Tecnomante o el Forjador."],
    "nexus": ["Clic: pone una terminal NEXUS.",
              "Abre el caso del infiltrado (infiltrado.py)."],
    "compuertas": ["Clic: pone una compuerta en un pasillo.",
                   "Un evento al azar la baja 20 s.",
                   "+ / -: más alta o más baja (bajo el mouse).",
                   "[ / ]: más angosta o más ancha.",
                   "Tiene que tapar el pasillo de pared a pared."],
    "pruebas": ["Clic: pone un lugar posible para una prueba",
                "del infiltrado (audio, expediente, captura).",
                "Cada partida se usan 3 al azar: pongan más",
                "de 3 y fuera de la prisión. Con menos, no hay caso."],
    "fusibles": ["Clic: pone una caja de fusibles.",
                 "En un apagón se sortea cuál es la buena:",
                 "hay que encontrarla y encenderla.",
                 "Sin cajas, el mapa no tiene apagones."],
    "salas": ["Arrastra en un lugar vacío: dibuja una",
              "sala. Arrastra una: la mueve; su esquina",
              "de abajo a la derecha: la agranda.",
              "T sobre una: siguiente nombre de la lista.",
              "Y sobre una: escribir el nombre (ENTER).",
              "Varias con el mismo nombre = una sala.",
              "Clic derecho: la borra. G: piso sin sala."],
    "puertas_dobles": ["Clic: pone la puerta; los dos clics",
                       "siguientes ponen sus dos paneles.",
                       "Se abre con dos jugadores, uno en cada",
                       "panel. Solo frena a los jugadores.",
                       "+ / - y [ / ]: tamaño (bajo el mouse).",
                       "Clic derecho: borra la puerta o el panel."],
}

AYUDA_GENERAL = [
    "1-9, 0, ',' '.' herramienta   Rueda zoom",
    "WASD/flechas o clic medio: mover vista",
    "Ctrl+Z / Ctrl+Y deshacer / rehacer",
    "Ctrl+S o ENTER guardar",
    "M: usar este mapa en el juego",
    "F5: guardar y probar en el juego",
    "V paredes   G zona caminable",
    "R dos veces: vacía lo de esta herramienta",
    "ESC salir",
]

COLOR_FONDO = (18, 19, 30)
COLOR_PANEL = (26, 28, 44)
COLOR_TEXTO = (235, 238, 250)
COLOR_TENUE = (150, 156, 190)
COLOR_TITULO = (255, 214, 64)
COLOR_OK = (96, 210, 120)
COLOR_PARED = (236, 70, 60)
COLOR_LEJOS = (255, 150, 40)
COLOR_ENCIMA = (255, 214, 64)
COLOR_MURO = (90, 180, 255)

ANCHO_PANEL = 330
ZOOMS = [0.3, 0.4, 0.5, 0.65, 0.8, 1.0, 1.25, 1.6, 2.0]
RADIO_TOQUE = 22          # en píxeles de pantalla: qué tan cerca hay que hacer clic


def _fuente(px):
    try:
        from juego.fuentes import fuente_de_tamano
        return fuente_de_tamano(px)
    except Exception:
        return pygame.font.SysFont("consolas", px)


class EditorMapa:
    def __init__(self, mapa, ruta_salida=None, tamano=(1366, 768)):
        self.mapa = mapa
        self.ruta_salida = ruta_salida
        if pygame.display.get_surface() is None:
            pygame.display.set_mode(tamano, pygame.RESIZABLE)
        self.screen = pygame.display.get_surface()
        pygame.display.set_caption(f"Editor de mapa - {mapa}")

        self.mundo = Mundo(mapa)
        ruta_lectura = ruta_salida if ruta_salida and os.path.isfile(ruta_salida) else None
        if ruta_salida and ruta_lectura is None:
            self.datos = objetos_mapa.normalizar(objetos_mapa.por_defecto())
        else:
            self.datos = objetos_mapa.normalizar(objetos_mapa.cargar(mapa, ruta=ruta_lectura))

        self.herramienta = 1
        self.notas_de_puerta = False   # herramienta Puertas: los clics ponen notas de código
        self.puerta_elegida = None     # a qué puerta van esas notas (índice)
        self.notas_solo_dificil = False  # F: las notas que se ponen van a "notas_dificil"
        self.ruta_elegida = 0
        self.arrastre = None          # lo que se está arrastrando
        self.antes = None             # copia de los datos al empezar un clic
        self.paneando = False
        self.deshacer, self.rehacer = [], []
        self.sucio = False
        self.confirmar = None         # acción que espera un segundo toque (R, ESC)
        self.nombre_sala = "Pasillo"  # el nombre que lleva la próxima sala que se dibuje
        self.escribiendo = None       # [índice de la sala, texto] mientras se escribe un nombre

        self.mostrar_paredes = True
        self.mostrar_caminable = False
        self.mensaje, self.mensaje_ms = "", 0

        self.f = _fuente(15)
        self.f_chica = _fuente(13)
        self.f_titulo = _fuente(19)

        self._escalados = {}
        self._caminable = None
        self._caminable_desde = None
        self.estado = {}
        self.problemas = []

        self.zoom_i = 2
        self._ajustar_zoom_inicial()
        self.validar()

    # -- Vista -----------------------------------------------------------------------------

    @property
    def zoom(self):
        """El zoom de verdad: el del mapa escalado (su ancho es entero), para
        que lo que se dibuja encima caiga en los mismos píxeles que el mapa."""
        return int(self.mundo.ancho * ZOOMS[self.zoom_i]) / self.mundo.ancho

    def _cam(self):
        """La cámara en píxeles enteros (la misma para el mapa y lo de encima)."""
        return math.floor(self.cam[0]), math.floor(self.cam[1])

    @property
    def area_mapa(self):
        ancho, alto = self.screen.get_size()
        return pygame.Rect(0, 0, ancho - ANCHO_PANEL, alto)

    def _ajustar_zoom_inicial(self):
        area = self.area_mapa
        cabe = min(area.width / self.mundo.ancho, area.height / self.mundo.alto)
        self.zoom_i = max(i for i, z in enumerate(ZOOMS) if z <= max(cabe, ZOOMS[0]))
        self.cam = [(self.mundo.ancho * self.zoom - area.width) / 2,
                    (self.mundo.alto * self.zoom - area.height) / 2]

    def a_mundo(self, pos):
        cx, cy = self._cam()
        return ((pos[0] + cx) / self.zoom, (pos[1] + cy) / self.zoom)

    def a_pantalla(self, p):
        # El mapa se escala por vecino más cercano: el píxel x del mundo
        # empieza en la columna ceil(x * zoom). Así el borde de una pared
        # coincide con el borde del dibujo.
        cx, cy = self._cam()
        z = self.zoom
        return (math.ceil(p[0] * z - 1e-9) - cx, math.ceil(p[1] * z - 1e-9) - cy)

    def rect_a_pantalla(self, rect, minimo=1):
        x0, y0 = self.a_pantalla(rect.topleft)
        x1, y1 = self.a_pantalla(rect.bottomright)
        return pygame.Rect(x0, y0, max(minimo, x1 - x0), max(minimo, y1 - y0))

    def norm(self, p):
        return [p[0] / self.mundo.ancho, p[1] / self.mundo.alto]

    def px(self, rx, ry):
        return (rx * self.mundo.ancho, ry * self.mundo.alto)

    def cambiar_zoom(self, delta, alrededor=None):
        nuevo = max(0, min(len(ZOOMS) - 1, self.zoom_i + delta))
        if nuevo == self.zoom_i:
            return
        alrededor = alrededor or self.area_mapa.center
        punto = self.a_mundo(alrededor)
        self.zoom_i = nuevo
        self.cam = [punto[0] * self.zoom - alrededor[0], punto[1] * self.zoom - alrededor[1]]

    def _mapa_escalado(self):
        if self.zoom not in self._escalados:
            tam = (round(self.mundo.ancho * self.zoom), round(self.mundo.alto * self.zoom))
            self._escalados[self.zoom] = pygame.transform.scale(self.mundo.imagen, tam)
        return self._escalados[self.zoom]

    # -- Acceso a los objetos -----------------------------------------------------------

    @property
    def clave(self):
        return HERRAMIENTAS[self.herramienta]["clave"]

    def posicion(self, clave, obj):
        """Punto del mundo (píxeles) de un objeto de esa parte."""
        if clave in LISTAS or clave in UNICOS or clave == "notas_codigo":
            return self.px(*obj)
        return self.px(obj["rx"], obj["ry"])

    def puertas(self):
        return self.datos.get("puertas_codigo") or []

    def rects_puertas(self):
        return [self.rect_puerta(i) for i in range(len(self.puertas()))]

    def rect_puerta(self, i=0):
        puertas = self.puertas()
        puerta = puertas[i] if i < len(puertas) else None
        if not puerta:
            return None
        rect = pygame.Rect(0, 0, max(8, int(puerta["ancho"] * self.mundo.ancho)),
                           max(8, int(puerta["alto"] * self.mundo.alto)))
        rect.center = tuple(map(int, self.px(puerta["rx"], puerta["ry"])))
        return rect

    def rect_dict(self, obj):
        """Rect del mundo de una compuerta o puerta para dos."""
        rect = pygame.Rect(0, 0, max(8, int(obj["ancho"] * self.mundo.ancho)),
                           max(8, int(obj["alto"] * self.mundo.alto)))
        rect.center = tuple(map(int, self.px(obj["rx"], obj["ry"])))
        return rect

    def rect_de(self, clave, punto):
        ancho, alto = TAMANOS.get(clave, (30, 30))
        rect = pygame.Rect(0, 0, ancho, alto)
        rect.center = (int(punto[0]), int(punto[1]))
        return rect

    def buscar(self, clave, pos_pantalla):
        """Lo que hay bajo el mouse en esa parte, o None."""
        p = self.a_mundo(pos_pantalla)
        radio = RADIO_TOQUE / self.zoom
        mejor, mejor_d = None, radio
        if clave in UNICOS:
            punto = self.datos.get(clave)
            if punto:
                rect = self.rect_de(clave, self.px(*punto))
                if math.dist(p, rect.center) <= radio or rect.collidepoint(p):
                    return ("unico", clave)
            return None
        if clave == "puertas_codigo":
            for i, puerta in enumerate(self.puertas()):
                for cosa, lista in TIPO_NOTA_PUERTA.items():
                    for k, punto in enumerate(puerta.get(lista, [])):
                        rect = self.rect_de("notas_codigo", self.px(*punto))
                        d = math.dist(p, rect.center)
                        if rect.inflate(radio, radio).collidepoint(p) and (mejor is None or d < mejor_d):
                            mejor, mejor_d = (cosa, i, k), d
            if mejor is not None:
                return mejor
            for i in range(len(self.puertas())):
                if self.rect_puerta(i).inflate(radio, radio).collidepoint(p):
                    return ("puerta", i)
            return None
        if clave == "paneles":
            for i, obj in enumerate(self.datos["paneles"]):
                if obj.get("sello") and self.rect_dict(obj["sello"]).inflate(radio, radio).collidepoint(p):
                    return ("sello", i)
        if clave in RECTS:
            for i, obj in enumerate(self.datos[clave]):
                for k, panel in enumerate(obj.get("paneles", [])):
                    d = math.dist(p, self.px(*panel))
                    if d <= mejor_d + 10:
                        mejor, mejor_d = ("panel", i, k), d
            if mejor is not None:
                return mejor
            for i, obj in enumerate(self.datos[clave]):
                if self.rect_dict(obj).inflate(radio, radio).collidepoint(p):
                    return ("rect", i)
            return None
        if clave == "salas":
            # Primero las esquinas (agrandar), después la más chica que tenga el punto.
            for i, obj in enumerate(self.datos["salas"]):
                if math.dist(p, self.rect_dict(obj).bottomright) <= radio:
                    return ("esquina", i)
            for i, obj in enumerate(self.datos["salas"]):
                rect = self.rect_dict(obj)
                if rect.collidepoint(p) and (mejor is None or rect.width * rect.height < mejor_d):
                    mejor, mejor_d = ("sala", i), rect.width * rect.height
            return mejor
        if clave == "rutas_aliens":
            for i, ruta in enumerate(self.datos["rutas_aliens"]):
                for j, punto in enumerate(ruta):
                    d = math.dist(p, self.px(*punto))
                    if d <= mejor_d:
                        mejor, mejor_d = ("punto", i, j), d
            return mejor
        for i, obj in enumerate(self.datos[clave]):
            rect = self.rect_de(clave, self.posicion(clave, obj))
            d = math.dist(p, rect.center)
            if rect.inflate(radio, radio).collidepoint(p) and (mejor is None or d < mejor_d):
                mejor, mejor_d = ("obj", i), d
        return mejor

    def _poner_sala(self, i, x0, y0, x1, y1):
        x0, x1 = sorted((max(0, min(self.mundo.ancho, x0)), max(0, min(self.mundo.ancho, x1))))
        y0, y1 = sorted((max(0, min(self.mundo.alto, y0)), max(0, min(self.mundo.alto, y1))))
        sala = self.datos["salas"][i]
        sala["rx"], sala["ry"] = self.norm(((x0 + x1) / 2, (y0 + y1) / 2))
        sala["ancho"] = max(0.002, (x1 - x0) / self.mundo.ancho)
        sala["alto"] = max(0.002, (y1 - y0) / self.mundo.alto)

    def mover_a(self, cosa, p):
        if cosa[0] == "sala_nueva":
            self._poner_sala(cosa[1], cosa[2][0], cosa[2][1], p[0], p[1])
            return
        if cosa[0] == "esquina":
            rect = self.rect_dict(self.datos["salas"][cosa[1]])
            self._poner_sala(cosa[1], rect.left, rect.top,
                             max(p[0], rect.left + TAMANO_MIN_SALA), max(p[1], rect.top + TAMANO_MIN_SALA))
            return
        if cosa[0] == "sala":
            rect = self.rect_dict(self.datos["salas"][cosa[1]])
            cx, cy = p[0] + cosa[2], p[1] + cosa[3]
            self._poner_sala(cosa[1], cx - rect.width / 2, cy - rect.height / 2,
                             cx + rect.width / 2, cy + rect.height / 2)
            return
        rx, ry = self.norm(p)
        rx, ry = min(1, max(0, rx)), min(1, max(0, ry))
        if cosa[0] == "unico":
            self.datos[cosa[1]] = [rx, ry]
        elif cosa[0] == "puerta":
            puerta = self.datos["puertas_codigo"][cosa[1]]
            puerta["rx"], puerta["ry"] = rx, ry
        elif cosa[0] in TIPO_NOTA_PUERTA:
            self.datos["puertas_codigo"][cosa[1]][TIPO_NOTA_PUERTA[cosa[0]]][cosa[2]] = [rx, ry]
        elif cosa[0] == "punto":
            self.datos["rutas_aliens"][cosa[1]][cosa[2]] = [rx, ry]
        elif cosa[0] == "rect":
            obj = self.datos[self.clave][cosa[1]]
            obj["rx"], obj["ry"] = rx, ry
        elif cosa[0] == "panel":
            self.datos[self.clave][cosa[1]]["paneles"][cosa[2]] = [rx, ry]
        elif cosa[0] == "sello":
            sello = self.datos["paneles"][cosa[1]]["sello"]
            sello["rx"], sello["ry"] = rx, ry
        elif cosa[0] == "obj":
            obj = self.datos[self.clave][cosa[1]]
            if self.clave in LISTAS:
                obj[0], obj[1] = rx, ry
            else:
                obj["rx"], obj["ry"] = rx, ry

    # -- Edición ---------------------------------------------------------------------------

    def _empezar_cambio(self):
        self.antes = copy.deepcopy(self.datos)

    def _terminar_cambio(self):
        if self.antes is not None and self.antes != self.datos:
            self.deshacer.append(self.antes)
            self.rehacer.clear()
            self.sucio = True
            self.validar()
        self.antes = None

    def clic_izquierdo(self, pos):
        if not self.area_mapa.collidepoint(pos):
            return
        self._empezar_cambio()
        clave = self.clave
        cosa = self.buscar(clave, pos)
        p = self.a_mundo(pos)
        if clave == "salas":
            if cosa is not None and cosa[0] == "sala":
                centro = self.rect_dict(self.datos["salas"][cosa[1]]).center
                self.nombre_sala = self.datos["salas"][cosa[1]]["nombre"]
                self.arrastre = ("sala", cosa[1], centro[0] - p[0], centro[1] - p[1])
            elif cosa is not None:
                self.arrastre = cosa
            elif 0 <= p[0] <= self.mundo.ancho and 0 <= p[1] <= self.mundo.alto:
                rx, ry = self.norm(p)
                self.datos["salas"].append({"nombre": self.nombre_sala, "rx": rx, "ry": ry,
                                            "ancho": 0.002, "alto": 0.002})
                self.arrastre = ("sala_nueva", len(self.datos["salas"]) - 1, p)
            return
        if cosa is not None:
            if cosa[0] == "punto":
                self.ruta_elegida = cosa[1]
            if cosa[0] in ("puerta",) + tuple(TIPO_NOTA_PUERTA):
                cambio = self.puerta_elegida != cosa[1] or not self.notas_de_puerta
                self.puerta_elegida, self.notas_de_puerta = cosa[1], True
                if cosa[0] == "puerta" and cambio:
                    nombre = color_puerta(cosa[1])[0]
                    self.avisar(f"Puerta {nombre} elegida: los clics ponen sus notas de código "
                                "(X termina).")
            self.arrastre = cosa
            return
        rx, ry = self.norm(p)
        if not (0 <= rx <= 1 and 0 <= ry <= 1):
            return
        if clave in UNICOS:
            self.datos[clave] = [rx, ry]
            self.arrastre = ("unico", clave)
        elif (clave == "puertas_codigo" and self.notas_de_puerta and self.puerta_elegida is not None
              and self.puerta_elegida < len(self.puertas())):
            i = self.puerta_elegida
            tipo = "nota_dificil" if self.notas_solo_dificil else "nota_codigo"
            notas = self.datos["puertas_codigo"][i].setdefault(TIPO_NOTA_PUERTA[tipo], [])
            notas.append([rx, ry])
            self.arrastre = (tipo, i, len(notas) - 1)
            cual = "solo Difícil " if self.notas_solo_dificil else ""
            self.avisar(f"Puerta {color_puerta(i)[0]}: nota de código {cual}{len(notas)}. "
                        "Otro clic pone otra; X termina; F cambia normal/solo Difícil.")
        elif clave == "puertas_codigo":
            puertas = self.datos.setdefault("puertas_codigo", [])
            puertas.append({"rx": rx, "ry": ry, "ancho": 0.02, "alto": 0.07, "notas": [],
                            "notas_dificil": []})
            i = len(puertas) - 1
            self.arrastre = ("puerta", i)
            self.puerta_elegida, self.notas_de_puerta = i, True
            que = " (la de la prisión: fase 1)" if i == 0 else ""
            self.avisar(f"Puerta {color_puerta(i)[0]}{que} puesta. Ahora haz clic donde pueden estar "
                        "las notas con su código (X para terminar).")
        elif clave == "rutas_aliens":
            rutas = self.datos["rutas_aliens"]
            if not rutas:
                rutas.append([])
                self.ruta_elegida = 0
            self.ruta_elegida = min(self.ruta_elegida, len(rutas) - 1)
            rutas[self.ruta_elegida].append([rx, ry])
            self.arrastre = ("punto", self.ruta_elegida, len(rutas[self.ruta_elegida]) - 1)
        elif clave == "paneles" and self.datos["paneles"] and not self.datos["paneles"][-1].get("sello"):
            self.datos["paneles"][-1]["sello"] = {"rx": rx, "ry": ry, "ancho": 0.05, "alto": 0.02}
            self.arrastre = ("sello", len(self.datos["paneles"]) - 1)
            self.avisar("Sello puesto. El próximo clic pone otro panel.")
        elif clave == "compuertas":
            self.datos[clave].append({"rx": rx, "ry": ry, "ancho": 0.012, "alto": 0.08})
            self.arrastre = ("rect", len(self.datos[clave]) - 1)
        elif clave == "puertas_dobles":
            dobles = self.datos[clave]
            if dobles and len(dobles[-1].get("paneles", [])) < 2:
                dobles[-1].setdefault("paneles", []).append([rx, ry])
                k = len(dobles[-1]["paneles"]) - 1
                self.arrastre = ("panel", len(dobles) - 1, k)
                if k == 0:
                    self.avisar("Panel 1 listo. Clic para el panel 2.")
                else:
                    self.avisar("Puerta para dos completa.")
            else:
                dobles.append({"rx": rx, "ry": ry, "ancho": 0.05, "alto": 0.02, "paneles": []})
                self.arrastre = ("rect", len(dobles) - 1)
                self.avisar("Ahora haz clic donde van sus dos paneles.")
        elif clave in LISTAS:
            self.datos[clave].append([rx, ry])
            self.arrastre = ("obj", len(self.datos[clave]) - 1)
        else:
            nombre = {"escondites": "Casillero", "terminales": "Terminal",
                      "paneles": "Panel dañado"}[clave]
            self.datos[clave].append({"clave": "", "nombre": nombre, "rx": rx, "ry": ry})
            self.arrastre = ("obj", len(self.datos[clave]) - 1)

    def arrastrar(self, pos):
        if self.arrastre is not None:
            self.mover_a(self.arrastre, self.a_mundo(pos))

    def soltar(self):
        if self.arrastre is not None and self.arrastre[0] == "sala_nueva":
            rect = self.rect_dict(self.datos["salas"][self.arrastre[1]])
            if rect.width < TAMANO_MIN_SALA or rect.height < TAMANO_MIN_SALA:
                del self.datos["salas"][self.arrastre[1]]
            else:
                self.avisar(f"Sala \"{self.nombre_sala}\". T cambia el nombre, Y lo escribe.")
        self.arrastre = None
        if self.antes is not None:
            objetos_mapa.normalizar(self.datos)
        self._terminar_cambio()

    def clic_derecho(self, pos):
        if not self.area_mapa.collidepoint(pos):
            return
        self._empezar_cambio()
        clave = self.clave
        cosa = self.buscar(clave, pos)
        if clave == "spawn":
            self.datos["spawn"] = None
            self.avisar("Inicio de vuelta al centro del mapa.")
        elif clave == "puertas_codigo":
            if cosa is not None and cosa[0] in TIPO_NOTA_PUERTA:
                del self.datos["puertas_codigo"][cosa[1]][TIPO_NOTA_PUERTA[cosa[0]]][cosa[2]]
            elif cosa is not None and cosa[0] == "puerta":
                i = cosa[1]
                quitada = self.datos["puertas_codigo"].pop(i)
                nombre = color_puerta(i)[0]
                cuantas = len(quitada["notas"]) + len(quitada.get("notas_dificil", []))
                self.avisar(f"Puerta {nombre} quitada" + (f", con sus {cuantas} notas de código."
                                                         if cuantas else ".")
                            + (" Las que siguen cambian de color." if i < len(self.puertas()) else ""))
                if self.puerta_elegida == i:
                    self.puerta_elegida, self.notas_de_puerta = None, False
                elif self.puerta_elegida is not None and self.puerta_elegida > i:
                    self.puerta_elegida -= 1
        elif clave in UNICOS:
            if cosa is not None:
                self.datos[clave] = None
        elif cosa is None:
            pass
        elif cosa[0] in ("sala", "esquina"):
            del self.datos["salas"][cosa[1]]
        elif cosa[0] == "sello":
            del self.datos["paneles"][cosa[1]]["sello"]
        elif cosa[0] == "rect":
            del self.datos[clave][cosa[1]]
        elif cosa[0] == "panel":
            del self.datos[clave][cosa[1]]["paneles"][cosa[2]]
        elif cosa[0] == "punto":
            ruta = self.datos["rutas_aliens"][cosa[1]]
            del ruta[cosa[2]]
            if not ruta:
                del self.datos["rutas_aliens"][cosa[1]]
                if cosa[1] < len(self.datos["tipos_aliens"]):
                    del self.datos["tipos_aliens"][cosa[1]]
                self.ruta_elegida = max(0, min(self.ruta_elegida, len(self.datos["rutas_aliens"]) - 1))
        elif cosa[0] == "obj":
            del self.datos[clave][cosa[1]]
        self._terminar_cambio()

    def nueva_ruta(self):
        self._empezar_cambio()
        self.datos["rutas_aliens"].append([])
        tipos = self.datos.setdefault("tipos_aliens", [])
        tipos[:] = (tipos + [TIPO_POR_DEFECTO] * len(self.datos["rutas_aliens"]))[:len(self.datos["rutas_aliens"]) - 1]
        tipos.append(TIPO_POR_DEFECTO)
        self.ruta_elegida = len(self.datos["rutas_aliens"]) - 1
        self.avisar(f"Ruta {self.ruta_elegida + 1}: haz clic para poner sus puntos.")
        self._terminar_cambio()

    def borrar_ruta(self):
        rutas = self.datos["rutas_aliens"]
        if not rutas:
            return
        self._empezar_cambio()
        i = min(self.ruta_elegida, len(rutas) - 1)
        del rutas[i]
        if i < len(self.datos.get("tipos_aliens", [])):
            del self.datos["tipos_aliens"][i]
        self.ruta_elegida = max(0, min(self.ruta_elegida, len(rutas) - 1))
        self._terminar_cambio()

    def _sala_bajo(self, pos):
        cosa = self.buscar("salas", pos)
        return cosa[1] if cosa is not None else None

    def nombre_siguiente_sala(self, pos):
        i = self._sala_bajo(pos)
        if i is None:
            # Sin sala bajo el mouse: cambia el nombre de la próxima que se dibuje.
            k = NOMBRES_SALA.index(self.nombre_sala) if self.nombre_sala in NOMBRES_SALA else -1
            self.nombre_sala = NOMBRES_SALA[(k + 1) % len(NOMBRES_SALA)]
            self.avisar(f"La próxima sala se llamará \"{self.nombre_sala}\".")
            return
        self._empezar_cambio()
        sala = self.datos["salas"][i]
        k = NOMBRES_SALA.index(sala["nombre"]) if sala["nombre"] in NOMBRES_SALA else -1
        sala["nombre"] = self.nombre_sala = NOMBRES_SALA[(k + 1) % len(NOMBRES_SALA)]
        self._terminar_cambio()

    def empezar_a_escribir(self, pos):
        i = self._sala_bajo(pos)
        if i is None:
            self.avisar("Pon el mouse sobre una sala y aprieta Y para escribir su nombre.")
            return
        self.escribiendo = [i, ""]
        pygame.key.start_text_input()

    def _tecla_escribiendo(self, ev):
        i, texto = self.escribiendo
        if ev.type == pygame.TEXTINPUT:
            self.escribiendo[1] = (texto + ev.text)[:24]
        elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_BACKSPACE:
            self.escribiendo[1] = texto[:-1]
        elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.escribiendo = None
        elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.escribiendo = None
            if texto.strip() and i < len(self.datos["salas"]):
                self._empezar_cambio()
                self.datos["salas"][i]["nombre"] = self.nombre_sala = texto.strip()
                self._terminar_cambio()

    def cambiar_nombre(self, pos):
        cosa = self.buscar("escondites", pos)
        if self.clave != "escondites" or cosa is None:
            return
        self._empezar_cambio()
        obj = self.datos["escondites"][cosa[1]]
        i = NOMBRES_ESCONDITE.index(obj["nombre"]) if obj["nombre"] in NOMBRES_ESCONDITE else -1
        obj["nombre"] = NOMBRES_ESCONDITE[(i + 1) % len(NOMBRES_ESCONDITE)]
        self._terminar_cambio()

    def tipo_de_ruta(self, i):
        tipos = self.datos.get("tipos_aliens") or []
        return tipos[i] if i < len(tipos) else TIPO_POR_DEFECTO

    def cambiar_tipo(self):
        """T en la herramienta de rutas: el alien de la ruta elegida cambia de tipo."""
        rutas = self.datos["rutas_aliens"]
        if not rutas:
            return
        self._empezar_cambio()
        i = min(self.ruta_elegida, len(rutas) - 1)
        tipos = self.datos.setdefault("tipos_aliens", [])
        tipos[:] = (tipos + [TIPO_POR_DEFECTO] * len(rutas))[:len(rutas)]
        actual = tipos[i] if tipos[i] in ORDEN_TIPOS else TIPO_POR_DEFECTO
        tipos[i] = ORDEN_TIPOS[(ORDEN_TIPOS.index(actual) + 1) % len(ORDEN_TIPOS)]
        datos = TIPOS_ALIEN[tipos[i]]
        self.avisar(f"Alien {i + 1}: {datos['nombre']} ({datos['descripcion']})")
        self._terminar_cambio()

    def cambiar_puerta(self, d_ancho, d_alto):
        if self.clave == "paneles":
            con_sello = [o for o in self.datos["paneles"] if o.get("sello")]
            cosa = self.buscar("paneles", pygame.mouse.get_pos())
            if not con_sello:
                return
            obj = self.datos["paneles"][cosa[1]] if cosa and cosa[0] == "sello" else con_sello[-1]
            self._empezar_cambio()
            sello = obj["sello"]
            sello["ancho"] = round(min(0.3, max(0.005, sello["ancho"] + d_ancho)), 4)
            sello["alto"] = round(min(0.3, max(0.005, sello["alto"] + d_alto)), 4)
            self._terminar_cambio()
            return
        if self.clave in RECTS:
            lista = self.datos[self.clave]
            cosa = self.buscar(self.clave, pygame.mouse.get_pos())
            if not lista:
                return
            obj = lista[cosa[1]] if cosa is not None else lista[-1]
            self._empezar_cambio()
            obj["ancho"] = round(min(0.3, max(0.005, obj["ancho"] + d_ancho)), 4)
            obj["alto"] = round(min(0.3, max(0.005, obj["alto"] + d_alto)), 4)
            self._terminar_cambio()
            return
        if self.clave != "puertas_codigo" or not self.puertas():
            return
        cosa = self.buscar("puertas_codigo", pygame.mouse.get_pos())
        if cosa is not None and cosa[0] == "puerta":
            i = cosa[1]
        elif self.puerta_elegida is not None and self.puerta_elegida < len(self.puertas()):
            i = self.puerta_elegida
        else:
            i = len(self.puertas()) - 1
        self._empezar_cambio()
        puerta = self.datos["puertas_codigo"][i]
        puerta["ancho"] = round(min(0.3, max(0.005, puerta["ancho"] + d_ancho)), 4)
        puerta["alto"] = round(min(0.3, max(0.005, puerta["alto"] + d_alto)), 4)
        self._terminar_cambio()

    def cambiar_radio(self, pos, delta):
        if self.clave in ("puertas_codigo", "paneles") or self.clave in RECTS:
            self.cambiar_puerta(0, delta)

    def alternar_notas_de_puerta(self):
        """X con la herramienta Puertas: deja de poner notas de código (el
        próximo clic pone otra puerta) o vuelve a ponerlas en la elegida."""
        if not self.puertas():
            self.avisar("Primero pon una puerta (clic).")
            return
        if self.puerta_elegida is None or self.puerta_elegida >= len(self.puertas()):
            self.puerta_elegida = len(self.puertas()) - 1
        nombre = color_puerta(self.puerta_elegida)[0]
        n = len(self.puertas()[self.puerta_elegida]["notas"])
        self.notas_de_puerta = not self.notas_de_puerta
        if self.notas_de_puerta:
            self.avisar(f"Puerta {nombre}: clic pone más notas de código (van {n}). X termina.")
        else:
            self.avisar(f"Puerta {nombre} lista ({n} notas). El próximo clic pone otra puerta; "
                        "clic en una puerta la elige.")

    def alternar_solo_dificil(self):
        """F con la herramienta Puertas: las próximas notas de código son
        "solo Difícil" (o vuelven a ser normales)."""
        self.notas_solo_dificil = not self.notas_solo_dificil
        if self.puertas() and not self.notas_de_puerta:
            if self.puerta_elegida is None or self.puerta_elegida >= len(self.puertas()):
                self.puerta_elegida = len(self.puertas()) - 1
            self.notas_de_puerta = True
        if self.notas_solo_dificil:
            self.avisar("Notas SOLO DIFÍCIL: solo salen en Difícil (e Inteligente), donde nadie "
                        "se escapa solo de la celda. Ponlas afuera de la prisión. F: normales.")
        else:
            self.avisar("Notas normales (salen en todas las dificultades).")

    def restaurar_herramienta(self):
        self._empezar_cambio()
        fabrica = objetos_mapa.normalizar(objetos_mapa.por_defecto())
        self.datos[self.clave] = copy.deepcopy(fabrica[self.clave])
        if self.clave == "puertas_codigo":       # las notas de código se van con sus puertas
            self.notas_de_puerta, self.puerta_elegida = False, None
        self.ruta_elegida = 0
        self._terminar_cambio()
        self.avisar(f"{HERRAMIENTAS[self.herramienta]['nombre']}: vaciada.")

    def deshacer_uno(self):
        if self.deshacer:
            self.rehacer.append(copy.deepcopy(self.datos))
            self.datos = self.deshacer.pop()
            self.sucio = True
            self.validar()

    def rehacer_uno(self):
        if self.rehacer:
            self.deshacer.append(copy.deepcopy(self.datos))
            self.datos = self.rehacer.pop()
            self.sucio = True
            self.validar()

    def guardar(self):
        ruta = objetos_mapa.guardar(self.mapa, self.datos, self.ruta_salida)
        self.sucio = False
        if self.problemas:
            self.avisar(f"Guardado, pero con {len(self.problemas)} problema(s): revisa la lista.")
        else:
            self.avisar(f"Guardado en {os.path.relpath(ruta, RAIZ)}")
        return ruta

    def usar_en_juego(self):
        objetos_mapa.fijar_mapa_activo(self.mapa)
        self.avisar(f"El juego ahora usa el mapa {self.mapa}.")

    def probar(self):
        self.guardar()
        self.usar_en_juego()
        subprocess.Popen([sys.executable, os.path.join(RAIZ, "main.py")], cwd=RAIZ)
        self.avisar("Abriendo el juego con este mapa...")

    def avisar(self, texto, ms=3500):
        self.mensaje, self.mensaje_ms = texto, ms

    # -- Validación -----------------------------------------------------------------------

    def _celdas_caminables(self):
        spawn = self.datos.get("spawn")
        desde = self.px(*spawn) if spawn else (self.mundo.ancho / 2, self.mundo.alto / 2)
        if self._caminable_desde != desde:
            inicio = self.mundo.punto_libre((int(desde[0]), int(desde[1])), 48, 19)
            self._caminable = self.mundo.area_alcanzable(inicio)
            self._caminable_desde = desde
        return self._caminable

    def _alcanzable(self, rect):
        celdas = self._celdas_caminables()
        for cx in range(rect.left // 16 * 16 - 48, rect.right + 16, 16):
            for cy in range(rect.top // 16 * 16 - 32, rect.bottom + 16, 16):
                if (cx, cy) in celdas and pygame.Rect(cx, cy, 48, 19).colliderect(rect):
                    return True
        return False

    def validar(self):
        """Revisa todo y deja en self.estado el color de cada cosa."""
        self.estado, self.problemas = {}, []
        nombres = NOMBRE_SINGULAR
        ocupados = []   # (rect, id) de todo lo que ocupa espacio

        for clave in CON_NOMBRE + LISTAS:
            for i, obj in enumerate(self.datos.get(clave, [])):
                rect = self.rect_de(clave, self.posicion(clave, obj))
                ocupados.append((rect, (clave, i)))
        # Las notas de código de cada puerta: ("nota_codigo", puerta, nota).
        nombres_nota = {}
        for i, puerta in enumerate(self.puertas()):
            for cosa, lista in TIPO_NOTA_PUERTA.items():
                for k, punto in enumerate(puerta.get(lista, [])):
                    ocupados.append((self.rect_de("notas_codigo", self.px(*punto)), (cosa, i, k)))
                    nombres_nota[(cosa, i, k)] = (f"Puerta {color_puerta(i)[0]}, nota "
                                                  f"{'D' if cosa == 'nota_dificil' else ''}{k + 1}")
        for unico in ("capsula", "guardia", "planta"):
            if self.datos.get(unico):
                ocupados.append((self.rect_de(unico, self.px(*self.datos[unico])), (unico, 0)))

        for rect, ident in ocupados:
            clave, i = ident[0], ident[1]
            nombre = nombres.get(clave, {"guardia": "Guardia", "planta": "Planta"}.get(clave, "Cápsula"))
            quien = nombres_nota.get(ident) or f"{nombre} {i + 1}"
            if clave == "celdas":
                # Las celdas van detrás de los barrotes, o sea, en la pared: lo
                # que importa es que quien libera llegue lo bastante cerca.
                if not self._alcanzable(rect.inflate(200, 200)):
                    self.estado[ident] = "lejos"
                    self.problemas.append(f"Celda {i + 1}: muy lejos del piso para liberarla")
                continue
            if self.mundo.colisiona(rect):
                self.estado[ident] = "pared"
                self.problemas.append(f"{quien}: choca con una pared")
            elif not self._alcanzable(rect):
                self.estado[ident] = "lejos"
                self.problemas.append(f"{quien}: no se llega caminando")
            elif any(r2.colliderect(rect) for r2, otro in ocupados if otro != ident):
                self.estado[ident] = "encima"
                self.problemas.append(f"{quien}: está encima de otra cosa")

        if self.datos.get("spawn"):
            rect = self.rect_de("spawn", self.px(*self.datos["spawn"]))
            if self.mundo.colisiona(rect):
                self.estado[("unico", "spawn")] = "pared"
                self.problemas.append("Inicio: choca con una pared")

        # La misión: si hay cápsula, revisar que lo demás tenga sentido.
        if self.datos.get("capsula"):
            if not self.datos["celdas"]:
                self.problemas.append("Misión: no hay celdas (si atrapan a alguien vuelve al inicio)")
            if bool(self.datos.get("guardia")) != bool(self.datos.get("planta")):
                self.problemas.append("Guardia: van juntos el Guardia y la planta (si no, no hay cómo quitarlo)")

        # Dónde puede ir el código de cada puerta (igual que el juego,
        # sortear_candidatas): sus notas de código que se alcanzan desde el
        # inicio con ella cerrada (y las demás también, salvo las que ya se
        # pueden abrir antes); si no tiene, una nota normal.
        self.pueden_tener_codigo = set()
        if self.puertas() and self.datos.get("capsula"):
            spawn = self.datos.get("spawn")
            desde = self.px(*spawn) if spawn else (self.mundo.ancho / 2, self.mundo.alto / 2)
            desde = self.mundo.punto_libre((int(desde[0]), int(desde[1])), 48, 19)
            normales = [self.rect_de("notas", self.posicion("notas", n)) for n in self.datos["notas"]]
            dobles = [self.rect_dict(d) for d in self.datos.get("puertas_dobles", [])]
            # Donde queda el que sale de una celda (el código puede ir adentro
            # de la prisión: lo lee el que encierran y abre desde adentro).
            adentro = [self.mundo.punto_libre((int(c[0]), int(c[1]) + 90), 48, 19)
                       for c in (self.px(*p) for p in self.datos["celdas"])]

            def rects(puntos):
                return [self.rect_de("notas_codigo", self.px(*n)) for n in puntos]

            # Fácil y Normal: solo las notas normales de cada puerta.
            sorteo = sortear_candidatas(self.mundo, desde, self.rects_puertas(),
                                        [rects(p["notas"]) for p in self.puertas()], normales,
                                        dobles, adentro)
            # Difícil (e Inteligente): también las "solo Difícil", y sin escapar
            # solo de la celda no sirve que el código esté adentro.
            sorteo_dificil = sortear_candidatas(
                self.mundo, desde, self.rects_puertas(),
                [rects(p["notas"] + p.get("notas_dificil", [])) for p in self.puertas()], normales,
                dobles, adentro)
            for i, (puerta, resultado, dificil) in enumerate(zip(self.puertas(), sorteo, sorteo_dificil)):
                nombre = f"Puerta {color_puerta(i)[0]}"
                n_normales = len(puerta["notas"])
                if resultado is not None and resultado[0] in ("codigo", "adentro"):
                    self.pueden_tener_codigo |= {("nota_codigo", i, k) for k in resultado[1]}
                elif resultado is not None:
                    self.pueden_tener_codigo |= {("notas", k) for k in resultado[1]}
                if dificil is not None and dificil[0] in ("codigo", "adentro"):
                    self.pueden_tener_codigo |= {("nota_dificil", i, k - n_normales)
                                                 for k in dificil[1] if k >= n_normales}
                if not puerta["notas"]:
                    self.problemas.append(f"{nombre}: no tiene notas de código (elígela con un clic "
                                          "y pon sus notas); su código iría en una nota normal")
                elif resultado is None or resultado[0] == "normal":
                    self.problemas.append(f"{nombre}: ninguna de sus notas de código se alcanza antes "
                                          "de abrirla")
                if resultado is None:
                    self.problemas.append(f"{nombre}: su código no se puede leer antes de abrirla "
                                          "(el juego la dejaría abierta)")
                if dificil is not None and dificil[0] == "adentro":
                    self.problemas.append(f"{nombre}: en Difícil su código queda adentro de la prisión "
                                          "y nadie sale solo de la celda: ponle notas SOLO DIFÍCIL "
                                          "afuera (tecla F)")
                for cosa, lista, res in (("nota_codigo", "notas", resultado),
                                         ("nota_dificil", "notas_dificil", dificil)):
                    for k in range(len(puerta.get(lista, []))):
                        ident = (cosa, i, k)
                        if ident not in self.pueden_tener_codigo:
                            self.estado.setdefault(ident, "lejos")
                            if res is not None and res[0] in ("codigo", "adentro"):
                                self.problemas.append(
                                    f"{nombre}, nota {'D' if cosa == 'nota_dificil' else ''}{k + 1}: "
                                    "queda detrás de una puerta (nunca tendrá el código)")
        if (self.puertas() or self.datos["consolas"]) and not self.datos.get("capsula"):
            self.problemas.append("Misión: falta la cápsula; sin ella no hay misión")

        if 0 < len(self.datos.get("pruebas", [])) < 3:
            self.problemas.append("Infiltrado: hacen falta al menos 3 lugares para pruebas")

        for i, doble in enumerate(self.datos.get("puertas_dobles", [])):
            if len(doble.get("paneles", [])) < 2:
                self.problemas.append(f"Puerta para dos {i + 1}: le faltan paneles (necesita 2)")
            for k, panel in enumerate(doble.get("paneles", [])):
                rect = pygame.Rect(0, 0, *TAMANO_PANEL)
                rect.center = tuple(map(int, self.px(*panel)))
                if self.mundo.colisiona(rect):
                    self.estado[("panel", i, k)] = "pared"
                    self.problemas.append(f"Puerta para dos {i + 1}, panel {k + 1}: en una pared")
                elif not self._alcanzable(rect.inflate(60, 60)):
                    self.estado[("panel", i, k)] = "lejos"
                    self.problemas.append(f"Puerta para dos {i + 1}, panel {k + 1}: no se llega")

        # Salas: que todo el piso tenga nombre (si el mapa ya usa salas).
        self.sin_sala = set()
        if self.datos.get("salas"):
            rects = [self.rect_dict(s) for s in self.datos["salas"]]
            self.sin_sala = {c for c in self._celdas_caminables()
                             if not any(r.collidepoint(c[0] + 24, c[1] + 10) for r in rects)}
            if self.sin_sala:
                self.problemas.append(f"Salas: hay piso sin sala ({len(self.sin_sala)} puntos; G los muestra)")

        self.tramos_malos = {}
        self.tramos_puerta = {}
        for i, ruta in enumerate(self.datos["rutas_aliens"]):
            puntos = [self.px(*p) for p in ruta]
            if not puntos:
                self.problemas.append(f"Ruta {i + 1}: no tiene puntos")
                continue
            for j, p in enumerate(puntos):
                rect = pygame.Rect(0, 0, *TAMANO_ALIEN)
                rect.center = (int(p[0]), int(p[1]))
                if self.mundo.colisiona(rect):
                    self.estado[("punto", i, j)] = "pared"
                    self.problemas.append(f"Ruta {i + 1}, punto {j + 1}: en una pared")
            malos = self.mundo.tramos_bloqueados(puntos, *TAMANO_ALIEN) if len(puntos) > 1 else []
            self.tramos_malos[i] = set(malos)
            for a, b in malos:
                self.problemas.append(f"Ruta {i + 1}: el tramo {a + 1}-{b + 1} cruza una pared")
            # Los tramos que pasan por una puerta (la del código o una para dos)
            # no son un error: mientras está cerrada el alien patrulla solo su
            # lado, y cuando la abren usa la ruta entera. Se pintan en ámbar.
            puertas = self.rects_puertas()
            puertas += [self.rect_dict(d) for d in self.datos.get("puertas_dobles", [])]
            n = len(puntos)
            tramos = [(j, (j + 1) % n) for j in range(n)] if n > 2 else ([(0, 1)] if n == 2 else [])
            self.tramos_puerta[i] = {(a, b) for a, b in tramos if (a, b) not in self.tramos_malos[i]
                                     and any(r.inflate(*TAMANO_ALIEN).clipline(puntos[a], puntos[b])
                                             for r in puertas)}
        return self.problemas

    # -- Entrada ---------------------------------------------------------------------------

    def tecla(self, key, mods=0):
        ctrl = mods & pygame.KMOD_CTRL
        confirmar, self.confirmar = self.confirmar, None
        if key in TECLAS_HERRAMIENTA:
            self.herramienta = TECLAS_HERRAMIENTA.index(key)
            self.arrastre = None
            self.notas_de_puerta = False
        elif key == pygame.K_x and self.clave == "puertas_codigo":
            self.alternar_notas_de_puerta()
        elif key == pygame.K_f and self.clave == "puertas_codigo":
            self.alternar_solo_dificil()
        elif ctrl and key == pygame.K_z:
            self.deshacer_uno()
        elif ctrl and key == pygame.K_y:
            self.rehacer_uno()
        elif (ctrl and key == pygame.K_s) or key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.guardar()
        elif key == pygame.K_m:
            self.usar_en_juego()
        elif key == pygame.K_F5:
            self.probar()
        elif key == pygame.K_v:
            self.mostrar_paredes = not self.mostrar_paredes
        elif key == pygame.K_g:
            self.mostrar_caminable = not self.mostrar_caminable
        elif key == pygame.K_n and self.clave == "rutas_aliens":
            self.nueva_ruta()
        elif key == pygame.K_TAB and self.datos["rutas_aliens"]:
            self.ruta_elegida = (self.ruta_elegida + 1) % len(self.datos["rutas_aliens"])
        elif key == pygame.K_DELETE and self.clave == "rutas_aliens":
            self.borrar_ruta()
        elif key == pygame.K_t and self.clave == "rutas_aliens":
            self.cambiar_tipo()
        elif key == pygame.K_t and self.clave == "salas":
            self.nombre_siguiente_sala(pygame.mouse.get_pos())
        elif key == pygame.K_y and self.clave == "salas":
            self.empezar_a_escribir(pygame.mouse.get_pos())
        elif key == pygame.K_t:
            self.cambiar_nombre(pygame.mouse.get_pos())
        elif key in (pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_EQUALS):
            self.cambiar_radio(pygame.mouse.get_pos(), 0.005)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.cambiar_radio(pygame.mouse.get_pos(), -0.005)
        elif key == pygame.K_LEFTBRACKET:
            self.cambiar_puerta(-0.003, 0)
        elif key == pygame.K_RIGHTBRACKET:
            self.cambiar_puerta(0.003, 0)
        elif key in (pygame.K_COMMA, pygame.K_PERIOD):
            paso = -1 if key == pygame.K_COMMA else 1
            self.herramienta = (self.herramienta + paso) % len(HERRAMIENTAS)
            self.arrastre = None
            self.notas_de_puerta = False
        elif key == pygame.K_r:
            if confirmar == "r":
                self.restaurar_herramienta()
            else:
                self.confirmar = "r"
                self.avisar("R otra vez para vaciar lo de esta herramienta.")
        elif key == pygame.K_ESCAPE:
            if not self.sucio or confirmar == "esc":
                return "salir"
            self.confirmar = "esc"
            self.avisar("Hay cambios sin guardar: ESC otra vez para salir igual.")
        return None

    def actualizar(self, dt):
        self.mensaje_ms = max(0, self.mensaje_ms - dt)
        if self.escribiendo is not None:
            return          # WASD escriben, no mueven la vista
        teclas = pygame.key.get_pressed()
        paso = 900 * dt / 1000
        if teclas[pygame.K_a] or teclas[pygame.K_LEFT]:
            self.cam[0] -= paso
        if teclas[pygame.K_d] or teclas[pygame.K_RIGHT]:
            self.cam[0] += paso
        if teclas[pygame.K_w] or teclas[pygame.K_UP]:
            self.cam[1] -= paso
        if teclas[pygame.K_s] or teclas[pygame.K_DOWN]:
            if not (pygame.key.get_mods() & pygame.KMOD_CTRL):
                self.cam[1] += paso

    def evento(self, ev):
        if self.escribiendo is not None and ev.type in (pygame.KEYDOWN, pygame.TEXTINPUT):
            self._tecla_escribiendo(ev)
            if self.escribiendo is None:
                pygame.key.stop_text_input()
            return None
        if ev.type == pygame.MOUSEBUTTONDOWN:
            espacio = pygame.key.get_pressed()[pygame.K_SPACE]
            if ev.button == 2 or (ev.button == 1 and espacio):
                self.paneando = True
            elif ev.button == 1 and not self.area_mapa.collidepoint(ev.pos):
                for rect, i in getattr(self, "_filas_panel", []):
                    if rect.collidepoint(ev.pos):
                        self.herramienta = i
                        self.arrastre = None
            elif ev.button == 1:
                self.clic_izquierdo(ev.pos)
            elif ev.button == 3:
                self.clic_derecho(ev.pos)
            elif ev.button == 4:
                self.cambiar_zoom(+1, ev.pos)
            elif ev.button == 5:
                self.cambiar_zoom(-1, ev.pos)
        elif ev.type == pygame.MOUSEBUTTONUP:
            if ev.button in (1, 2):
                if self.paneando:
                    self.paneando = False
                else:
                    self.soltar()
        elif ev.type == pygame.MOUSEMOTION:
            if self.paneando:
                self.cam[0] -= ev.rel[0]
                self.cam[1] -= ev.rel[1]
            else:
                self.arrastrar(ev.pos)
        elif ev.type == pygame.MOUSEWHEEL:
            self.cambiar_zoom(1 if ev.y > 0 else -1, pygame.mouse.get_pos())
        elif ev.type == pygame.KEYDOWN:
            return self.tecla(ev.key, ev.mod)
        return None

    # -- Dibujo ------------------------------------------------------------------------------

    def _color(self, ident, base):
        return {"pared": COLOR_PARED, "lejos": COLOR_LEJOS,
                "encima": COLOR_ENCIMA}.get(self.estado.get(ident), base)

    def _etiqueta(self, texto, centro, color, arriba=True):
        img = self.f_chica.render(texto, True, color)
        sombra = self.f_chica.render(texto, True, (0, 0, 0))
        x = centro[0] - img.get_width() // 2
        y = centro[1] - img.get_height() - 4 if arriba else centro[1] + 4
        self.screen.blit(sombra, (x + 1, y + 1))
        self.screen.blit(img, (x, y))

    def dibujar(self):
        s = self.screen
        s.fill(COLOR_FONDO)
        area = self.area_mapa
        s.set_clip(area)
        cx, cy = self._cam()
        s.blit(self._mapa_escalado(), (-cx, -cy))

        if self.mostrar_paredes:
            capa = pygame.Surface(area.size, pygame.SRCALPHA)
            for pared in self.mundo.paredes:
                r = self.rect_a_pantalla(pared)
                pygame.draw.rect(capa, (*COLOR_MURO, 50), r)
                pygame.draw.rect(capa, (*COLOR_MURO, 160), r, 1)
            s.blit(capa, (0, 0))
        if self.mostrar_caminable:
            sin_sala = getattr(self, "sin_sala", set())
            for cx, cy in self._celdas_caminables():
                color = COLOR_PARED if (cx, cy) in sin_sala else (120, 255, 140)
                pygame.draw.circle(s, color, self.a_pantalla((cx + 24, cy + 10)), 3 if (cx, cy) in sin_sala else 2)

        actual = self.clave
        apagado = lambda clave: clave != actual

        # Todo lo que es un punto o una lista de puntos.
        colores = {h["clave"]: h for h in HERRAMIENTAS}
        for clave in CON_NOMBRE + LISTAS + ("capsula", "guardia", "planta"):
            herr = colores[clave]
            objetos = self.datos.get(clave)
            if clave in UNICOS:
                objetos = [objetos] if objetos else []
            for i, obj in enumerate(objetos):
                ident = ("unico", clave) if clave in UNICOS else (clave, i)
                rect = self.rect_de(clave, self.posicion(clave, obj))
                x, y = self.a_pantalla(rect.topleft)
                r = self.rect_a_pantalla(rect, 4)
                estado = self.estado.get(ident) or self.estado.get((clave, i))
                color = self._color(ident if ident in self.estado else (clave, i), herr["color"])
                relleno = pygame.Surface(r.size, pygame.SRCALPHA)
                relleno.fill((*herr["color"], 110 if not apagado(clave) else 50))
                s.blit(relleno, r.topleft)
                pygame.draw.rect(s, color if estado else herr["color"], r,
                                 3 if estado else (2 if not apagado(clave) else 1))
                if not apagado(clave) and clave != "spawn":
                    if isinstance(obj, dict):
                        texto = f"{obj['nombre']} {i + 1}"
                    elif clave in UNICOS:
                        texto = herr["nombre"]
                    else:
                        texto = f"{NOMBRE_SINGULAR[clave]} {i + 1}"
                        if (clave, i) in getattr(self, "pueden_tener_codigo", ()):
                            texto += " (código)"
                    self._etiqueta(texto, r.midtop, color)

        # Puertas con código, cada una de su color, con sus notas de código
        # (con su herramienta se ven fuertes y unidas a su puerta).
        activa = not apagado("puertas_codigo")
        for i, puerta in enumerate(self.puertas()):
            nombre, color_p = color_puerta(i)
            rect_p = self.rect_puerta(i)
            r_p = self.rect_a_pantalla(rect_p, 3)
            elegida = activa and i == self.puerta_elegida
            notas = [("nota_codigo", k, punto) for k, punto in enumerate(puerta["notas"])]
            notas += [("nota_dificil", k, punto) for k, punto in enumerate(puerta.get("notas_dificil", []))]
            for cosa, k, punto in notas:
                ident = (cosa, i, k)
                solo_dificil = cosa == "nota_dificil"
                rect = self.rect_de("notas_codigo", self.px(*punto))
                r = self.rect_a_pantalla(rect, 4)
                if activa:
                    pygame.draw.line(s, color_p, r.center, r_p.center, 2 if elegida else 1)
                relleno = pygame.Surface(r.size, pygame.SRCALPHA)
                relleno.fill((*((70, 40, 40) if solo_dificil else colores["notas"]["color"]),
                              130 if activa else 50))
                s.blit(relleno, r.topleft)
                estado = self.estado.get(ident)
                color = self._color(ident, color_p)
                pygame.draw.rect(s, color if estado else color_p, r, 3 if estado else (2 if activa else 1))
                if solo_dificil:       # borde rojo punteado: solo en Difícil
                    for x in range(r.x, r.right, 6):
                        pygame.draw.line(s, (245, 90, 80), (x, r.bottom + 2), (min(x + 3, r.right), r.bottom + 2), 2)
                pygame.draw.circle(s, color_p, (r.centerx, r.y), max(2, r.width // 5))
                if activa or not apagado("notas"):
                    marca = "D" if solo_dificil else ""
                    self._etiqueta(f"{nombre[:3].capitalize()} {marca}{k + 1}", r.midtop, color)
            pygame.draw.rect(s, color_p, r_p, 0 if activa else 2)
            if elegida:
                pygame.draw.rect(s, (255, 255, 255), r_p.inflate(6, 6), 2)
            if activa:
                que = " (fase 1)" if i == 0 else ""
                self._etiqueta(f"Puerta {nombre}{que}", r_p.midtop, color_p)

        # Sellos de los paneles del Forjador.
        for i, obj in enumerate(self.datos.get("paneles", [])):
            if not obj.get("sello"):
                continue
            rect = self.rect_dict(obj["sello"])
            x, y = self.a_pantalla(rect.topleft)
            r = self.rect_a_pantalla(rect, 3)
            color = (90, 200, 255)
            pygame.draw.rect(s, color, r, 0 if not apagado("paneles") else 2)
            pygame.draw.line(s, color, self.a_pantalla(self.px(obj["rx"], obj["ry"])), r.center, 1)
            if not apagado("paneles"):
                self._etiqueta(f"Sello {i + 1}", r.midtop, color)

        # Compuertas y puertas para dos.
        for clave in RECTS:
            color_base = colores[clave]["color"]
            for i, obj in enumerate(self.datos.get(clave, [])):
                rect = self.rect_dict(obj)
                x, y = self.a_pantalla(rect.topleft)
                r = self.rect_a_pantalla(rect, 3)
                pygame.draw.rect(s, color_base, r, 0 if not apagado(clave) else 2)
                nombre = "Compuerta" if clave == "compuertas" else "Puerta x2"
                if not apagado(clave):
                    self._etiqueta(f"{nombre} {i + 1}", r.midtop, color_base)
                for k, panel in enumerate(obj.get("paneles", [])):
                    centro = self.a_pantalla(self.px(*panel))
                    color = self._color(("panel", i, k), color_base)
                    pygame.draw.line(s, color_base, centro, r.center, 1)
                    lado = max(6, int(TAMANO_PANEL[0] * self.zoom))
                    caja = pygame.Rect(0, 0, lado, lado)
                    caja.center = centro
                    pygame.draw.rect(s, (40, 40, 60), caja)
                    pygame.draw.rect(s, color, caja, 2 if not apagado(clave) else 1)
                    if not apagado(clave):
                        self._etiqueta(f"P{k + 1}", caja.midtop, color)

        # Salas (solo con su herramienta: si no, tapan todo).
        if actual == "salas":
            capa = pygame.Surface(area.size, pygame.SRCALPHA)
            for i, obj in enumerate(self.datos["salas"]):
                rect = self.rect_dict(obj)
                x, y = self.a_pantalla(rect.topleft)
                r = self.rect_a_pantalla(rect, 3)
                tono = (sum(map(ord, obj["nombre"])) * 47) % 360
                color = pygame.Color(0); color.hsva = (tono, 55, 100, 100)
                pygame.draw.rect(capa, (color.r, color.g, color.b, 55), r)
                pygame.draw.rect(capa, (color.r, color.g, color.b, 220), r, 2)
                pygame.draw.rect(capa, (255, 255, 255, 230), (r.right - 7, r.bottom - 7, 7, 7))
            s.blit(capa, (0, 0))
            for i, obj in enumerate(self.datos["salas"]):
                rect = self.rect_dict(obj)
                texto = obj["nombre"]
                if self.escribiendo is not None and self.escribiendo[0] == i:
                    texto = self.escribiendo[1] + ("_" if (pygame.time.get_ticks() // 400) % 2 else " ")
                self._etiqueta(texto, self.a_pantalla(rect.center), COLOR_TEXTO, arriba=False)

        # Rutas de los aliens.
        for i, ruta in enumerate(self.datos["rutas_aliens"]):
            elegida = (i == self.ruta_elegida and actual == "rutas_aliens")
            puntos = [self.a_pantalla(self.px(*p)) for p in ruta]
            base = HERRAMIENTAS[1]["color"] if (elegida or actual != "rutas_aliens") else (150, 90, 90)
            n = len(puntos)
            tramos = [(j, (j + 1) % n) for j in range(n)] if n > 2 else ([(0, 1)] if n == 2 else [])
            for a, b in tramos:
                malo = (a, b) in self.tramos_malos.get(i, set()) or (b, a) in self.tramos_malos.get(i, set())
                por_puerta = (a, b) in getattr(self, "tramos_puerta", {}).get(i, set())
                color = COLOR_PARED if malo else (COLOR_LEJOS if por_puerta else base)
                pygame.draw.line(s, color, puntos[a], puntos[b], 4 if (elegida or malo or por_puerta) else 2)
            for j, p in enumerate(puntos):
                color = self._color(("punto", i, j), base)
                pygame.draw.circle(s, color, p, 9 if elegida else 6)
                pygame.draw.circle(s, (20, 10, 10), p, 9 if elegida else 6, 2)
                if elegida or j == 0:
                    nombre_tipo = TIPOS_ALIEN.get(self.tipo_de_ruta(i), {}).get("nombre", "")
                    self._etiqueta(f"A{i + 1} {nombre_tipo}" if j == 0 else str(j + 1), p, color)

        # Inicio de los jugadores.
        spawn = self.datos.get("spawn")
        if spawn:
            p = self.a_pantalla(self.px(*spawn))
            color = self._color(("unico", "spawn"), (255, 255, 255))
            pygame.draw.circle(s, color, p, 12, 3)
            pygame.draw.circle(s, color, p, 4)
            self._etiqueta("Inicio", (p[0], p[1] - 12), color)

        # Lo que hay bajo el mouse.
        cosa = self.buscar(actual, pygame.mouse.get_pos()) if area.collidepoint(pygame.mouse.get_pos()) else None
        if cosa is not None:
            pygame.draw.circle(s, (255, 255, 255), pygame.mouse.get_pos(), RADIO_TOQUE, 1)

        s.set_clip(None)
        self._dibujar_panel()

    def _dibujar_panel(self):
        s = self.screen
        ancho, alto = s.get_size()
        panel = pygame.Rect(ancho - ANCHO_PANEL, 0, ANCHO_PANEL, alto)
        pygame.draw.rect(s, COLOR_PANEL, panel)
        x, y = panel.x + 14, 12

        def linea(texto, color=COLOR_TEXTO, f=None, extra=4):
            nonlocal y
            f = f or self.f
            s.blit(f.render(texto, True, color), (x, y))
            y += f.get_linesize() + extra

        linea(f"Editor de mapa · {self.mapa}", COLOR_TITULO, self.f_titulo)
        activo = objetos_mapa.mapa_activo() == self.mapa
        linea("Es el mapa del juego" if activo else "No es el mapa del juego (M)",
              COLOR_OK if activo else COLOR_LEJOS, self.f_chica)
        linea("Sin guardar" if self.sucio else "Guardado", COLOR_LEJOS if self.sucio else COLOR_OK,
              self.f_chica, 10)

        self._filas_panel = []
        for i, herr in enumerate(HERRAMIENTAS):
            clave = herr["clave"]
            if clave == "spawn":
                cuenta = "puesto" if self.datos.get("spawn") else "centro"
            elif clave == "puertas_codigo":
                cuenta = (f"{len(self.puertas())}, {sum(len(p['notas']) for p in self.puertas())} notas"
                          + (f" + {sum(len(p.get('notas_dificil', [])) for p in self.puertas())} D"
                             if any(p.get("notas_dificil") for p in self.puertas()) else ""))
            elif clave in UNICOS:
                cuenta = "puesta" if self.datos.get(clave) else "no"
            elif clave in RECTS:
                cuenta = str(len(self.datos.get(clave, [])))
            else:
                cuenta = str(len(self.datos[clave]))
            elegida = i == self.herramienta
            if elegida:
                pygame.draw.rect(s, (52, 57, 92), (panel.x + 6, y - 2, ANCHO_PANEL - 12,
                                                  self.f.get_linesize() + 4))
            pygame.draw.rect(s, herr["color"], (x, y + 4, 10, 10))
            tecla = str((i + 1) % 10) if i < 10 else "·"
            texto = f"{tecla}  {herr['nombre']}  ({cuenta})"
            s.blit(self.f_chica.render(texto, True, COLOR_TITULO if elegida else COLOR_TEXTO), (x + 16, y))
            self._filas_panel.append((pygame.Rect(panel.x, y - 2, ANCHO_PANEL, self.f.get_linesize() + 4), i))
            y += self.f.get_linesize() + 2
        y += 6

        if self.clave == "rutas_aliens" and self.datos["rutas_aliens"]:
            linea(f"Ruta elegida: {self.ruta_elegida + 1} de {len(self.datos['rutas_aliens'])}",
                  COLOR_TITULO, self.f_chica)
            tipo = TIPOS_ALIEN[self.tipo_de_ruta(self.ruta_elegida)]
            linea(f"Tipo: {tipo['nombre']} - {tipo['descripcion']}", COLOR_TITULO, self.f_chica)
        if self.clave == "puertas_codigo":
            if self.notas_de_puerta and self.puerta_elegida is not None and self.puerta_elegida < len(self.puertas()):
                nombre = color_puerta(self.puerta_elegida)[0].upper()
                cual = "SOLO DIFÍCIL " if self.notas_solo_dificil else ""
                linea(f"Clic: NOTAS {cual}PUERTA {nombre} (X fin, F)",
                      color_puerta(self.puerta_elegida)[1], self.f_chica)
            else:
                linea("Clic: pone otra puerta (clic en una: la elige)", COLOR_TITULO, self.f_chica)
        if self.clave == "salas":
            linea(f"Próxima sala: {self.nombre_sala}", COLOR_TITULO, self.f_chica)
            if self.escribiendo is not None:
                linea("Escribiendo: ENTER guarda, ESC cancela", COLOR_TITULO, self.f_chica)
        for texto in AYUDA_HERRAMIENTA[self.clave]:
            linea(texto, COLOR_TENUE, self.f_chica, 2)
        y += 8

        linea(f"Problemas ({len(self.problemas)})", COLOR_PARED if self.problemas else COLOR_OK, self.f)
        for texto in self.problemas[:8]:
            linea("· " + texto, COLOR_LEJOS, self.f_chica, 1)
        if len(self.problemas) > 8:
            linea(f"  y {len(self.problemas) - 8} más", COLOR_LEJOS, self.f_chica, 1)
        y += 8

        y = max(y, alto - len(AYUDA_GENERAL) * (self.f_chica.get_linesize() + 2) - 16)
        for texto in AYUDA_GENERAL:
            linea(texto, COLOR_TENUE, self.f_chica, 2)

        if self.mensaje_ms > 0:
            img = self.f.render(self.mensaje, True, COLOR_TITULO)
            caja = img.get_rect(midbottom=(self.area_mapa.centerx, alto - 16)).inflate(20, 12)
            pygame.draw.rect(s, (14, 15, 28), caja)
            pygame.draw.rect(s, COLOR_TITULO, caja, 2)
            s.blit(img, img.get_rect(center=caja.center))


# -- Programa -------------------------------------------------------------------------------

def elegir_mapa():
    if len(sys.argv) > 1:
        nombre = os.path.splitext(os.path.basename(sys.argv[1]))[0]
        return nombre
    sys.path.insert(0, os.path.join(RAIZ, "Editores"))
    from hitbox_editor import choose_image_gui
    ruta = choose_image_gui(CARPETA_FONDOS, "Elegir mapa - Editor de mapa  (doble clic o Enter)")
    if ruta is None:
        return None
    return os.path.splitext(os.path.basename(ruta))[0]


def main():
    pygame.init()
    info = pygame.display.Info()
    tam = (min(1600, info.current_w - 60), min(950, info.current_h - 80))
    pygame.display.set_mode(tam, pygame.RESIZABLE)
    mapa = elegir_mapa()
    if not mapa:
        pygame.quit()
        return
    pygame.display.set_mode(tam, pygame.RESIZABLE)
    editor = EditorMapa(mapa)
    reloj = pygame.time.Clock()
    while True:
        dt = reloj.tick(60)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                # Cerrar la ventana es como ESC: si hay cambios, pide confirmar.
                ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0)
            if ev.type == pygame.VIDEORESIZE:
                editor.screen = pygame.display.get_surface()
            if editor.evento(ev) == "salir":
                pygame.quit()
                return
        editor.actualizar(dt)
        editor.dibujar()
        pygame.display.flip()


if __name__ == "__main__":
    main()
