"""La misión de escape: tres fases cortas, celdas y puntos de equipo.

    1. Puerta      encontrar el código en las notas y abrir la puerta (si el
                   mapa tiene una: en la Nave es la de la prisión, en MapaE2
                   la salida de Control). El código va en una de sus notas de
                   código que se alcance ANTES de la puerta
                   (notas_antes_de_la_puerta, sortear_candidatas).
                   Puede haber más puertas con código (cada una de un color,
                   con su código y sus notas): la primera es la de la fase 1
                   y las demás se abren cuando sea (la flecha lleva a ellas si
                   detrás queda algo de la misión).
    2. Sabotaje    apagar las consolas de navegación (mantener la tecla).
    3. Cápsula     llevar 3 piezas a la cápsula y repararla (mantener la tecla).
                   Para repararla hacen falta los planos, que se ganan con la
                   confianza de la tripulación en NEXUS (nexus.py). Eso corre
                   en paralelo con todo lo anterior.
    4. Huida       los aliens entran en alerta; todos tienen que llegar a la
                   cápsula. Si llegan todos, ganan.

Si atrapan a alguien, va a una **celda** y un compañero tiene que ir a
sacarlo. Si están todos en celdas o se quedan sin vidas, pierden. No hay
límite de tiempo.

Para que se pueda jugar con 2 o 3 personas:
- sin Tecnomante, aparecen **decodificadores** para las consolas (no se gastan:
  antes eran de un solo uso y con 2 consolas y 1 decodificador en el mapa la
  misión quedaba imposible);
- sin Forjador, aparece un **kit de herramientas** para reparar, y quien lo
  lleve ve y recoge las piezas (`ve_piezas`; antes las veía cualquiera).
El que tiene el rol lo hace más rápido que el que usa el consumible.

Todo lo de la misión se pone en el mapa con el editor (Editores/editor_mapa.py).
Un mapa sin cápsula no tiene misión: se juega como antes, por tiempo.
"""

import math
import random

import pygame

from data.notas import NOTAS, NOTA_CODIGO, NOTAS_CODIGO_VACIAS
from misiones.logros import logro


PIEZAS_NECESARIAS = 3
SABOTAJE_ROL_S, SABOTAJE_OTROS_S = 3.0, 6.0          # segundos manteniendo la tecla
REPARACION_ROL_S, REPARACION_OTROS_S = 4.0, 8.0
RADIO_RESCATE = 140

PUNTOS_PUERTA = 20
PUNTOS_CONSOLA = 15
PUNTOS_PIEZA = 5
PUNTOS_REPARACION = 20
PUNTOS_ESCAPE = 50
PUNTOS_RESCATE = 10

TAMANO_CONSOLA = (70, 50)
TAMANO_CAPSULA = (210, 130)
TAMANO_NOTA = (30, 30)
TAMANO_CONSUMIBLE = (34, 34)

COLOR_BIEN = (96, 200, 120)
COLOR_MAL = (245, 130, 120)
COLOR_AVISO = (255, 214, 64)

NOMBRE_CONSUMIBLE = {"decodificador": "Decodificador", "kit": "Kit de herramientas",
                     # El Guardia de la Bahía (misiones/guardia.py).
                     "fruta": "Fruta", "abono": "Abono"}

# Cortos a propósito: van en una sola línea del HUD, y con cuatro jugadores a
# 1280 px cada mitad tiene ~520 px para el texto (unos 50 caracteres).
TEXTO_FASE = {
    "prision": "Busquen el código en las notas y abran la puerta.",
    "sabotaje": "Apaguen las consolas de navegación ({hechas}/{total}).",
    "capsula": "Lleven {faltan} pieza(s) a la cápsula y repárenla.",
    "reparar": "Reparen la cápsula: mantengan la tecla.",
    "planos": "Faltan los planos: ganen la confianza en NEXUS.",
    "huida": "¡Alerta! Todos a la cápsula.",
}


# Cada puerta con código tiene un color: sus notas llevan una tachuela de ese color.
COLORES_PUERTA = [("roja", (225, 70, 70)), ("azul", (80, 150, 255)), ("verde", (90, 205, 110)),
                  ("amarilla", (240, 205, 60)), ("morada", (185, 115, 245)), ("naranja", (255, 150, 60)),
                  ("celeste", (110, 225, 235)), ("rosada", (245, 130, 200))]


def color_puerta(i):
    return COLORES_PUERTA[i % len(COLORES_PUERTA)]


class Equipo:
    """Puntos de todo el equipo: se ganan juntos y se gastan en habilidades."""

    def __init__(self):
        self.puntos = 0      # disponibles para desbloquear habilidades
        self.total = 0       # todo lo que ganaron en la partida

    def sumar(self, cantidad):
        if cantidad > 0:
            self.puntos += cantidad
            self.total += cantidad

    def gastar(self, cantidad):
        self.puntos = max(0, self.puntos - cantidad)


def notas_antes_de_la_puerta(mundo, desde, notas, tapan):
    """Índices de las notas (rects) a las que se llega caminando desde `desde`
    con la puerta del código y las puertas para dos cerradas (`tapan`): entre
    ellas se sortea la del código, para que siempre se pueda leer antes de
    abrir. La usa también el editor de mapa, para mostrar cuáles sirven."""
    def choca(rect):
        return mundo.colisiona(rect) or rect.collidelist(tapan) != -1
    celdas = mundo.area_alcanzable(desde, colisiona=choca)
    return [i for i, nota in enumerate(notas)
            if any(pygame.Rect(c[0], c[1], 48, 19).colliderect(nota.inflate(40, 40)) for c in celdas)]


def sortear_candidatas(mundo, desde, puertas, notas_puerta, notas_normales, tapan=(), adentro=()):
    """En qué notas puede ir el código de cada puerta (rects de las puertas;
    `notas_puerta[i]`: rects de las notas de código de la puerta i).

    Una nota sirve si se llega a ella con esa puerta cerrada. Las demás puertas
    también están cerradas, salvo las que ya se pueden abrir (su código se lee
    antes): así una puerta puede tener sus notas detrás de otra. Si una puerta
    no tiene notas de código (o no se llega a ninguna), su código va en una
    nota normal alcanzable. `mundo.paredes` no debe tener las puertas.

    `adentro`: puntos donde también aparece gente (donde queda el que sale de
    una celda). Así una puerta puede tener su código ADENTRO de la prisión: lo
    lee el que encierran, al salir de su celda, y abre desde adentro.

    Devuelve, por puerta, ("codigo", [índices en notas_puerta[i]]),
    ("adentro", [índices en notas_puerta[i]]) (solo se leen desde `adentro`),
    ("normal", [índices en notas_normales]) o None (no hay cómo leerlo)."""
    resultado = [None] * len(puertas)
    abiertas = set()
    for normales_tambien in (False, True):
        cambio = True
        while cambio:
            cambio = False
            for i in range(len(puertas)):
                if resultado[i] is not None:
                    continue
                cerradas = [p for j, p in enumerate(puertas) if j not in abiertas] + list(tapan)
                if notas_puerta[i]:
                    alcanzables = notas_antes_de_la_puerta(mundo, desde, notas_puerta[i], cerradas)
                    if alcanzables:
                        resultado[i] = ("codigo", alcanzables)
                    else:
                        for punto in adentro:
                            alcanzables = notas_antes_de_la_puerta(mundo, punto, notas_puerta[i], cerradas)
                            if alcanzables:
                                resultado[i] = ("adentro", alcanzables)
                                break
                if resultado[i] is None and (normales_tambien or not notas_puerta[i]) and notas_normales:
                    alcanzables = notas_antes_de_la_puerta(mundo, desde, notas_normales, cerradas)
                    if alcanzables:
                        resultado[i] = ("normal", alcanzables)
                if resultado[i] is not None:
                    abiertas.add(i)
                    cambio = True
    return resultado


def _rect(centro, tamano):
    rect = pygame.Rect(0, 0, *tamano)
    rect.center = (int(centro[0]), int(centro[1]))
    return rect


class Mision:
    def __init__(self, juego, objetos, aleatorio=None):
        self.juego = juego
        self.rng = aleatorio or random.Random()
        mundo = juego.mundo
        ancho, alto = mundo.ancho, mundo.alto

        def px(p):
            return (int(p[0] * ancho), int(p[1] * alto))

        self.activa = bool(objetos.get("capsula"))
        # Solo cuentan los que se pueden mover: un puesto de mando sin mando
        # (jugador 3 o 4 sin control) no camina, y si era el Tecnomante o el
        # Forjador no aparecían el decodificador ni el kit: la misión quedaba
        # imposible.
        roles = {j.rol for j in juego.jugadores if getattr(j, "puede_moverse", True)} \
            or {j.rol for j in juego.jugadores}
        self.falta_tecnomante = "Tecnomante" not in roles
        self.falta_forjador = "Forjador" not in roles
        # Sin Biomante, abono para la planta de la Biosfera (misiones/guardia.py).
        self.hay_planta = bool(objetos.get("planta") and objetos.get("guardia"))
        self.falta_biomante = "Biomante" not in roles and self.hay_planta
        # Sin Forjador las piezas no son solo suyas: las ve y las recoge quien
        # lleve el kit de herramientas (ve_piezas). El nombre es de antes,
        # cuando las veía cualquiera.
        self.piezas_para_todos = self.activa and self.falta_forjador
        self.resultado = None            # "victoria" / "derrota"

        # Puertas con código: {"rect", "codigo", "abierta", "nombre", "color",
        # "candidatas"}. La primera es la de la prisión (fase 1).
        self.puertas = []
        self._codigo_suelto = self._codigo_nuevo()
        self.capsula = None
        self.consolas, self.celdas, self.notas, self.consumibles = [], [], [], []
        self.piezas_entregadas = 0
        self.codigos_fallidos = 0        # para el logro "A la primera"
        self.abrio = None                # quién abrió la puerta de la prisión
        self._objetivos = []             # rects de lo de la misión (para ver qué tapan las puertas)
        self._tapado = False             # ¿alguna puerta cerrada tapa algo de la misión?
        self.reparacion = 0.0
        self.fase = None
        if not self.activa:
            return

        # Desde dónde se mide qué se alcanza (dónde empiezan los jugadores).
        self._desde = juego.jugadores[0].hitbox.topleft if juego.jugadores else None
        usados = set()
        # Las notas "solo Difícil" salen donde nadie se escapa solo de la celda
        # (Difícil e Inteligente; también sin dificultad, en las pruebas).
        dif = getattr(juego, "dificultad", None)
        con_dificil = dif is None or getattr(dif, "clave", None) in ("dificil", "inteligente")
        for i, puerta in enumerate(objetos.get("puertas_codigo") or []):
            nombre, color = color_puerta(i)
            codigo = self._codigo_nuevo(evitar=usados)
            usados.add(codigo)
            self.puertas.append({
                "rect": _rect(px((puerta["rx"], puerta["ry"])),
                              (max(8, int(puerta["ancho"] * ancho)), max(8, int(puerta["alto"] * alto)))),
                "codigo": codigo, "abierta": False, "nombre": nombre, "color": color,
                "candidatas": [],
                "notas_mapa": [px(n) for n in (puerta.get("notas") or [])
                               + ((puerta.get("notas_dificil") or []) if con_dificil else [])],
            })

        self.capsula = _rect(px(objetos["capsula"]), TAMANO_CAPSULA)
        self.consolas = [{"rect": _rect(px(c), TAMANO_CONSOLA), "progreso": 0.0}
                         for c in objetos.get("consolas", [])]
        self.celdas = [{"punto": px(c), "preso": None} for c in objetos.get("celdas", [])]
        # Las puertas para dos también tapan al buscar dónde esconder el código.
        self._dobles = [_rect(px((d["rx"], d["ry"])), (max(8, int(d["ancho"] * ancho)), max(8, int(d["alto"] * alto))))
                        for d in objetos.get("puertas_dobles", [])]
        self._crear_notas([px(n) for n in objetos.get("notas", [])],
                          [p["notas_mapa"] for p in self.puertas])
        self._crear_consumibles([px(c) for c in objetos.get("consumibles", [])])
        # Lo que no puede quedar detrás de una puerta cerrada sin que la flecha
        # lleve a abrirla.
        self._objetivos = ([k["rect"] for k in self.consolas] + [self.capsula]
                           + [_rect(px(p), (34, 34)) for p in objetos.get("piezas", [])])
        self._recalcular_acceso()

        if self.puerta is not None:
            self.fase = "prision"
        elif self.consolas:
            self.fase = "sabotaje"
        else:
            self.fase = "capsula"

    # -- Preparación ----------------------------------------------------------------

    # -- Puertas con código ---------------------------------------------------------

    def _codigo_nuevo(self, evitar=()):
        while True:
            codigo = "-".join(str(self.rng.randint(1, 9)) for _ in range(3))
            if codigo not in evitar:
                return codigo

    @property
    def principal(self):
        """La puerta de la prisión (fase 1): la primera, si sigue en el juego."""
        if self.puertas and not self.puertas[0].get("quitada"):
            return self.puertas[0]
        return None

    @property
    def puerta(self):
        p = self.principal
        return p["rect"] if p is not None else None

    @property
    def puerta_abierta(self):
        p = self.principal
        return p is None or p["abierta"]

    @property
    def codigo(self):
        p = self.principal
        return p["codigo"] if p is not None else self._codigo_suelto

    def _de(self, puerta):
        """" roja", " azul"... (vacío si el mapa tiene una sola puerta)."""
        return f" {puerta['nombre']}" if len(self.puertas) > 1 else ""

    def puertas_cerradas(self):
        return [p for p in self.puertas if not p["abierta"]]

    def _crear_notas(self, puntos, notas_por_puerta=()):
        """Las notas normales (historia) y las de código de cada puerta. El
        código de cada puerta va en una de sus notas de código que se alcance
        antes de abrirla (sortear_candidatas); si no tiene, en una normal. Si
        no hay cómo leerlo, la puerta queda abierta."""
        mundo = self.juego.mundo
        rects_puertas = [p["rect"] for p in self.puertas]
        # Para sortear, las puertas no pueden ser paredes del mundo.
        mundo.paredes[:] = [r for r in mundo.paredes if r not in rects_puertas]
        self.notas = [{"rect": _rect(p, TAMANO_NOTA), "titulo": "", "texto": "", "leida_por": set(),
                       "de_codigo": False, "puerta": None} for p in puntos]
        por_puerta = []
        for i, puntos_codigo in enumerate(list(notas_por_puerta) + [[]] * (len(self.puertas) - len(notas_por_puerta))):
            notas = [{"rect": _rect(p, TAMANO_NOTA), "titulo": "", "texto": "", "leida_por": set(),
                      "de_codigo": True, "puerta": i} for p in puntos_codigo]
            por_puerta.append(notas)
            self.notas += notas
        normales = [n for n in self.notas if not n["de_codigo"]]
        if self.puertas:
            desde = getattr(self, "_desde", None) or \
                mundo.punto_libre((mundo.ancho // 2, mundo.alto // 2), 48, 19)
            # Donde queda el que sale de una celda: si las notas de una puerta
            # están adentro de la prisión, las lee él y abre desde adentro.
            adentro = [mundo.punto_libre((c["punto"][0], c["punto"][1] + 90), 48, 19)
                       for c in self.celdas]
            sorteo = sortear_candidatas(mundo, desde, rects_puertas,
                                        [[n["rect"] for n in notas] for notas in por_puerta],
                                        [n["rect"] for n in normales],
                                        getattr(self, "_dobles", []), adentro)
        else:
            sorteo = []
        textos = {id(n): [] for n in self.notas}
        usadas = set()
        for i, puerta in enumerate(self.puertas):
            puerta["abierta"], puerta["quitada"], puerta["candidatas"] = False, False, []
            puerta["adentro"] = False
            if sorteo[i] is None:
                # Antes le ponía el código a cualquier nota, aunque estuviera
                # del otro lado: la partida quedaba imposible. Mejor abierta.
                print(f"[AVISO] El código de la puerta {puerta['nombre']} no se puede leer antes "
                      "de abrirla: se deja abierta (ponle notas antes, con el editor de mapa).")
                puerta["abierta"], puerta["quitada"] = True, True
                continue
            tipo, indices = sorteo[i]
            puerta["adentro"] = tipo == "adentro"
            puerta["candidatas"] = [(normales if tipo == "normal" else por_puerta[i])[k] for k in indices]
            libres = [n for n in puerta["candidatas"] if id(n) not in usadas] or puerta["candidatas"]
            elegida = self.rng.choice(libres)
            usadas.add(id(elegida))
            textos[id(elegida)].append(NOTA_CODIGO["texto"].replace("{codigo}", puerta["codigo"])
                                       .replace("{puerta}", puerta["nombre"]))
            if tipo == "normal" and por_puerta[i]:
                print(f"[AVISO] Ninguna nota de código de la puerta {puerta['nombre']} se alcanza "
                      "antes de abrirla: su código va en una nota normal.")
        for puerta in self.puertas_cerradas():
            mundo.paredes.append(puerta["rect"])
        p = self.principal
        self.notas_alcanzables = p["candidatas"] if p is not None else []   # para la flecha
        if not self.notas:
            return
        lore = list(NOTAS)
        vacias = 0
        for nota in self.notas:
            if textos[id(nota)]:
                nota["titulo"] = NOTA_CODIGO["titulo"]
                nota["texto"] = " ".join(textos[id(nota)])
            elif nota["de_codigo"] and NOTAS_CODIGO_VACIAS:
                datos = NOTAS_CODIGO_VACIAS[vacias % len(NOTAS_CODIGO_VACIAS)]
                vacias += 1
                nota["titulo"], nota["texto"] = datos["titulo"], datos["texto"]
            else:
                datos = lore.pop(0) if lore else {"titulo": "Nota", "texto": "Está en blanco."}
                nota["titulo"], nota["texto"] = datos["titulo"], datos["texto"]
            if nota["de_codigo"]:
                nota["color"] = self.puertas[nota["puerta"]]["color"]

    def _recalcular_acceso(self):
        """¿Queda algo de la misión detrás de una puerta con código cerrada?"""
        self._tapado = False
        cerradas = [p for p in self.puertas_cerradas() if p is not self.principal]
        desde = getattr(self, "_desde", None)
        if not cerradas or desde is None or not self._objetivos:
            return
        mundo = self.juego.mundo
        principal = self.puerta
        if hasattr(mundo, "paredes_base"):
            # Con la navegación (pedazos conectados ya calculados en C), como
            # Mision._llega. Antes era notas_antes_de_la_puerta: un BFS en
            # Python por todo el mapa, celda por celda, que al abrir una puerta
            # congelaba el juego ~0.4 s en el PC de Diego.
            from juego import navegacion
            from juego.mundo import paredes_extra
            nav = navegacion.de_mundo(mundo, 34, 20)
            extra = [p for p in paredes_extra(mundo) if principal is None or p != principal]
            inicio = (desde[0] + 24, desde[1] + 10)
            llega = [r for r in self._objetivos if nav.conectados(inicio, r.center, sellos=False, extra=extra)]
            self._tapado = len(llega) < len(self._objetivos)
            return
        quitar = principal is not None and principal in mundo.paredes
        if quitar:       # como si la de la prisión ya estuviera abierta
            mundo.paredes.remove(principal)
        try:
            alcanzados = notas_antes_de_la_puerta(mundo, desde, self._objetivos, [])
        finally:
            if quitar:
                mundo.paredes.append(principal)
        self._tapado = len(alcanzados) < len(self._objetivos)

    def _crear_consumibles(self, puntos):
        """Solo para los roles que faltan: UNO de cada uno (decodificador sin
        Tecnomante, kit sin Forjador, abono sin Biomante), cada uno en un
        punto de consumibles distinto, al azar. (Ninguno se gasta salvo el
        abono, así que con uno alcanza.)"""
        tipos = []
        if self.falta_tecnomante and self.consolas:
            tipos.append("decodificador")
        if self.falta_forjador:
            tipos.append("kit")
        if self.falta_biomante:
            tipos.append("abono")
        self.consumibles = []
        if not puntos or not tipos:
            return
        libres = list(puntos)
        self.rng.shuffle(libres)
        for k, tipo in enumerate(tipos):
            if k < len(libres):
                centro = libres[k]
            else:
                # Más consumibles que puntos: al lado de uno (sin montarse).
                x, y = libres[k % len(libres)]
                lx, ly = self.juego.mundo.punto_libre((x + 48 * (k // len(libres)) - TAMANO_CONSUMIBLE[0] // 2,
                                                       y - TAMANO_CONSUMIBLE[1] // 2), *TAMANO_CONSUMIBLE)
                centro = (lx + TAMANO_CONSUMIBLE[0] // 2, ly + TAMANO_CONSUMIBLE[1] // 2)
            self.consumibles.append({"rect": _rect(centro, TAMANO_CONSUMIBLE), "tipo": tipo, "tomado": False})

    def hay_consumible(self, tipo):
        """¿Ya hay uno de esos en el piso o en el inventario de alguien?"""
        return (any(c["tipo"] == tipo and not c["tomado"] for c in self.consumibles)
                or any(tipo in getattr(j, "objetos", ()) for j in self.juego.jugadores))

    # -- Consultas ------------------------------------------------------------------

    def objetivo(self):
        if not self.activa:
            return None
        if self.fase == "sabotaje":
            hechas = sum(c["progreso"] >= 1 for c in self.consolas)
            return TEXTO_FASE["sabotaje"].format(hechas=hechas, total=len(self.consolas))
        if self.fase == "capsula":
            faltan = PIEZAS_NECESARIAS - self.piezas_entregadas
            if faltan > 0:
                return TEXTO_FASE["capsula"].format(faltan=faltan)
            return TEXTO_FASE["reparar"] if self.hay_planos() else TEXTO_FASE["planos"]
        return TEXTO_FASE.get(self.fase, "")

    def punto_objetivo(self, jugador):
        """A dónde debería ir ahora este jugador, para la flecha amarilla de
        las dificultades fáciles (dificultad.py). Devuelve (punto, texto) o None.

        El orden (según la fase, el rol y lo que lleva):
          0. Rescatar a un compañero encerrado.
          1. Prisión: leer las notas y abrir la puerta.
          2. Consolas: quien puede (Tecnomante o con decodificador) las
             hackea; si hay un decodificador suelto, ir por él. Los demás
             adelantan lo suyo: la planta (Biomante o con abono), el kit si
             falta el Forjador; si no tienen nada, cuidan al que hackea.
          3. Cápsula: primero quitar al Guardia para siempre (fruta, planta,
             abono); el Resonante lo distrae cuando alguien necesita llegar a
             la cápsula; luego piezas, kit, planos (NEXUS) y reparar.
          4. Huida: a la cápsula (el Resonante, si hace falta, distrae)."""
        if not self.activa or jugador.preso or getattr(jugador, "eliminado", False):
            return None
        c = jugador.hitbox.center

        def cerca(cosas, punto=lambda x: x):
            return min(cosas, key=lambda x: math.dist(punto(x), c), default=None)

        # Primero, sacar a un compañero de su celda.
        celda = cerca([cd for cd in self.celdas if cd["preso"] is not None], lambda cd: cd["punto"])
        if celda is not None and self.fase != "prision":
            return celda["punto"], "Rescata a tu compañero"
        # El Guardia de la Bahía (misiones/guardia.py).
        bahia = getattr(self.juego, "guardia_planta", None)
        if bahia is not None and not bahia.activo:
            bahia = None
        if bahia is not None and "fruta" in jugador.objetos and self.fase != "prision":
            return bahia.punto_objetivo(jugador)          # la fruta, ya: al Guardia
        if self.fase == "huida":
            if bahia is not None:
                distraer = bahia.punto_distraer(jugador)
                if distraer is not None:
                    return distraer
            return self.capsula.center, "¡A la cápsula!"
        if self.fase == "prision" and self.principal is not None:
            return self._guiar_a_puerta(jugador, self.principal, cerca)
        # Otra puerta con código tapa algo de la misión: a abrirla (la más cercana
        # cuyo código ya se puede leer).
        if self._tapado:
            # (Una puerta con el código adentro de la prisión solo le sirve al
            # que está adentro.)
            alcanzables = [p for p in self.puertas_cerradas() if p["candidatas"]
                           and (not p.get("adentro") or any(self._llega(jugador, n["rect"].center)
                                                            for n in p["candidatas"]))]
            # De la más cercana a la más lejana, la primera a la que se puede
            # ir ahora: si la nota que falta leer de una está detrás de OTRA
            # puerta cerrada, la flecha apuntaba a un lugar sin camino (y los
            # jugadores se quedaban dando vueltas) en vez de llevar a la otra.
            c0 = jugador.hitbox.center
            for puerta in sorted(alcanzables, key=lambda p: math.dist(p["rect"].center, c0)):
                guia = self._guiar_a_puerta(jugador, puerta, cerca, solo_alcanzables=True)
                if guia is not None:
                    return guia
        if self.fase == "sabotaje":
            pendientes = [k for k in self.consolas if k["progreso"] < 1]
            consola = cerca(pendientes, lambda k: k["rect"].center)
            puede_hackear = (jugador.rol == "Tecnomante" and not getattr(jugador, "eliminado", False)) \
                or "decodificador" in jugador.objetos
            if consola is not None and puede_hackear:
                return consola["rect"].center, "Hackea esta consola"
            if consola is not None:
                decodificador = cerca([k for k in self.consumibles
                                       if k["tipo"] == "decodificador" and not k["tomado"]],
                                      lambda k: k["rect"].center)
                if decodificador is not None:
                    return decodificador["rect"].center, "Toma el decodificador: con él hackeas consolas"
            # Lo que este jugador puede ir adelantando mientras otros hackean.
            if bahia is not None:
                planta = bahia.punto_objetivo(jugador)
                if planta is not None:
                    return planta
            kit = self.kit_libre() if self.piezas_para_todos else None
            if kit is not None:
                return kit["rect"].center, "Toma el kit: con él verás las piezas"
            if consola is not None:
                return consola["rect"].center, "Cuida a quien hackea esta consola"
        red = getattr(self.juego, "nexus", None)
        if self.fase == "capsula":
            if bahia is not None:
                # Primero, quitar al Guardia para siempre.
                planta = bahia.punto_objetivo(jugador)
                if planta is not None:
                    return planta
                # El Resonante lo distrae cuando alguien tiene que llegar a la
                # cápsula (con una pieza o para repararla), o si ya no hay
                # forma de darle de comer.
                listos = self.piezas_entregadas >= PIEZAS_NECESARIAS and self.hay_planos()
                con_pieza = any(getattr(j, "piezas", 0) > 0 for j in self.juego.jugadores)
                if listos or con_pieza or not bahia.hay_camino_permanente():
                    distraer = bahia.punto_distraer(jugador)
                    if distraer is not None:
                        return distraer
            if getattr(jugador, "piezas", 0) > 0 and self.piezas_entregadas < PIEZAS_NECESARIAS:
                if bahia is not None and not bahia.guardia.distraido:
                    return self.capsula.center, "Lleva la pieza (ojo: el Guardia la cuida)"
                return self.capsula.center, "Lleva la pieza a la cápsula"
            if self.piezas_entregadas < PIEZAS_NECESARIAS and self.ve_piezas(jugador):
                pieza = cerca([p for p in getattr(self.juego, "piezas", []) if not p["recogida"]],
                              lambda p: p["rect"].center)
                if pieza is not None:
                    return pieza["rect"].center, "Recoge esta pieza"
            kit = self.kit_libre() if self.piezas_para_todos else None
            if self.piezas_entregadas < PIEZAS_NECESARIAS and kit is not None:
                return kit["rect"].center, "Toma el kit: con él ves las piezas"
            if not self.hay_planos() and red is not None:
                nodo = red.nodo_de(jugador)
                rumor = cerca([p for p in red.rumores_activos()
                               if p.lugar is not None and nodo in p.alcanzados
                               and p not in red.evidencias.get(jugador, ())],
                              lambda p: p.lugar)
                if rumor is not None:
                    return rumor.lugar, "Desmiente este rumor (foto)"
                # Sin rumores a la mano: la central de ayuda dice cómo va la confianza.
                terminal = cerca([z for z in getattr(self.juego, "zonas", ()) if z.get("tipo") == "nexus"],
                                 lambda z: z["rect"].center)
                if terminal is not None:
                    return terminal["rect"].center, "Faltan los planos: revisa NEXUS aquí"
            if self.piezas_entregadas >= PIEZAS_NECESARIAS and self.hay_planos():
                if bahia is not None and not bahia.guardia.distraido:
                    return self.capsula.center, "Repara la cápsula (ojo: el Guardia)"
                return self.capsula.center, "Repara la cápsula"
            if self.piezas_entregadas < PIEZAS_NECESARIAS:
                return self.capsula.center, "Ayuda con la cápsula"
        return None

    def _llega(self, jugador, punto):
        """¿Puede ir caminando hasta `punto` con lo que está cerrado ahora?"""
        mundo = self.juego.mundo
        if not hasattr(mundo, "paredes_base"):
            return True
        from juego import navegacion
        from juego.mundo import paredes_extra
        nav = navegacion.de_mundo(mundo, 34, 20)
        return nav.conectados(jugador.hitbox.center, punto, extra=paredes_extra(mundo))

    def _guiar_a_puerta(self, jugador, puerta, cerca, solo_alcanzables=False):
        """A dónde ir para abrir `puerta`: la puerta (si ya leyó el código) o
        la nota más cercana sin leer. Con `solo_alcanzables`, solo notas a las
        que se llega con lo que está cerrado ahora; si no queda ninguna,
        None."""
        leyo = any(jugador in n["leida_por"] and puerta["codigo"] in n["texto"] for n in self.notas)
        if leyo or not puerta["candidatas"]:
            return puerta["rect"].center, f"Abre la puerta{self._de(puerta)} con el código"
        sin_leer = [n for n in puerta["candidatas"] if jugador not in n["leida_por"]]
        if solo_alcanzables:
            sin_leer = [n for n in sin_leer if self._llega(jugador, n["rect"].center)]
            if not sin_leer:
                return None
        nota = cerca(sin_leer, lambda n: n["rect"].center)
        if nota is None:
            return puerta["rect"].center, f"Abre la puerta{self._de(puerta)}"
        if nota["de_codigo"]:
            return nota["rect"].center, f"Lee las notas de tachuela {puerta['nombre']}: una tiene el código"
        return nota["rect"].center, f"Lee las notas: una tiene el código de la puerta{self._de(puerta)}"

    def ve_piezas(self, jugador):
        """Quién ve y recoge las piezas sueltas: el Forjador (Ingenio mecánico)
        y, si no hay Forjador (o lo eliminaron), quien lleve el kit de
        herramientas."""
        arbol = getattr(jugador, "arbol", None)
        if arbol is not None and arbol.tiene("INGENIO") and not getattr(jugador, "eliminado", False):
            return True
        if not self.piezas_para_todos:
            return False
        if "kit" in getattr(jugador, "objetos", ()):
            return True
        # Si en el mapa no hay ningún kit (ni lo lleva nadie), como antes: todos.
        hay_kit = (any(c["tipo"] == "kit" and not c["tomado"] for c in self.consumibles)
                   or any("kit" in getattr(j, "objetos", ()) for j in self.juego.jugadores))
        return not hay_kit

    def kit_libre(self):
        """El kit de herramientas que está en el piso, si nadie lo lleva."""
        if any("kit" in getattr(j, "objetos", ()) for j in self.juego.jugadores):
            return None
        return next((c for c in self.consumibles if c["tipo"] == "kit" and not c["tomado"]), None)

    def hay_planos(self):
        """Los planos de la cápsula se ganan en NEXUS. Sin NEXUS no hacen falta."""
        red = getattr(self.juego, "nexus", None)
        return red is None or red.planos

    def _cerca(self, jugador, rect, margen=40):
        return rect.inflate(margen * 2, margen * 2).colliderect(jugador.hitbox)

    def _sonar(self, nombre, volumen=1.0):
        if hasattr(self.juego, "sonar"):
            self.juego.sonar(nombre, volumen)

    def _decir(self, evento, rol=None, forzar=False):
        if hasattr(self.juego, "decir"):
            self.juego.decir(evento, rol, forzar)

    def _avisar_todos(self, texto, color=COLOR_AVISO):
        for j in self.juego.jugadores:
            j.avisar(texto, color)

    def pista(self, jugador):
        """Texto de "presiona E para..." según lo que tenga cerca, o None."""
        if not self.activa:
            return None
        if jugador.preso:
            fuga = jugador.preso.get("fuga_ms")
            if fuga is not None:
                return f"Forzando la reja... sales en {max(1, int(fuga // 1000) + 1)} s"
            return None
        c = jugador.hitbox.center
        for celda in self.celdas:
            if celda["preso"] is not None and math.dist(c, celda["punto"]) <= RADIO_RESCATE:
                return f"Liberar a {celda['preso'].rol}"
        puerta = self._puerta_cerca(jugador)
        if puerta is not None:
            if getattr(self.juego, "en_tutorial", False):
                return "Teclado bloqueado hasta que todos terminen el tutorial"
            if getattr(self.juego, "sin_luz", False):
                return "Teclado sin energía"
            return f"Teclado de la puerta{self._de(puerta)}"
        for cons in self.consumibles:
            if not cons["tomado"] and self._cerca(jugador, cons["rect"], 15):
                return f"Recoger {NOMBRE_CONSUMIBLE[cons['tipo']].lower()}"
        if self.capsula and self.fase == "capsula" and self._cerca(jugador, self.capsula, 10):
            if self.piezas_entregadas < PIEZAS_NECESARIAS:
                return "Dejar piezas en la cápsula" if jugador.piezas else "Cápsula: faltan piezas"
            if not self.hay_planos():
                return "Cápsula: faltan los planos (confianza en NEXUS)"
            return "Mantener: reparar la cápsula"
        for nota in self.notas:
            if self._cerca(jugador, nota["rect"], 20):
                return "Leer nota"
        if self.fase == "sabotaje":
            for consola in self.consolas:
                if consola["progreso"] < 1 and self._cerca(jugador, consola["rect"], 20):
                    if getattr(self.juego, "sin_luz", False):
                        return "Consola sin energía"
                    return "Mantener: apagar consola"
        return None

    # -- Tecla de interactuar --------------------------------------------------------

    def interactuar(self, jugador):
        """Devuelve True si la misión se encargó de la tecla."""
        if not self.activa:
            return False
        if jugador.preso:
            return True
        c = jugador.hitbox.center
        for celda in self.celdas:
            if celda["preso"] is not None and math.dist(c, celda["punto"]) <= RADIO_RESCATE:
                self.liberar(celda, jugador)
                return True
        puerta = self._puerta_cerca(jugador)
        if puerta is not None:
            if getattr(self.juego, "en_tutorial", False):
                # Con los aliens dormidos sería gratis: primero todos terminan el tutorial.
                jugador.avisar("El teclado no responde: terminen todos el tutorial.", COLOR_MAL)
                return True
            if getattr(self.juego, "sin_luz", False):
                jugador.avisar("El teclado está apagado. Sin energía: enciendan la caja de fusibles.", COLOR_MAL)
                return True
            self._panel_codigo(jugador, self.puertas.index(puerta))
            return True
        for cons in self.consumibles:
            if not cons["tomado"] and self._cerca(jugador, cons["rect"], 15):
                cons["tomado"] = True
                jugador.objetos.add(cons["tipo"])
                jugador.avisar(f"Recogiste: {NOMBRE_CONSUMIBLE[cons['tipo']]}", COLOR_BIEN)
                self._sonar("recoger", 0.7)
                return True
        if self.capsula and self.fase == "capsula" and self._cerca(jugador, self.capsula, 10):
            faltan = PIEZAS_NECESARIAS - self.piezas_entregadas
            if faltan > 0 and jugador.piezas > 0:
                dejar = min(faltan, jugador.piezas)
                jugador.piezas -= dejar
                self.piezas_entregadas += dejar
                jugador.sumar_puntos(PUNTOS_PIEZA * dejar)
                self._sonar("encajar", 0.8)
                jugador.avisar(f"Piezas en la cápsula: {self.piezas_entregadas}/{PIEZAS_NECESARIAS}",
                               COLOR_BIEN)
            elif faltan > 0:
                quien = ("Las ve y las recoge quien lleve el kit de herramientas"
                         if self.piezas_para_todos else "El Forjador tiene que recogerlas")
                jugador.avisar(f"Faltan {faltan} pieza(s). {quien}.", COLOR_MAL)
            elif not self.hay_planos():
                jugador.avisar("Sin los planos no saben cómo repararla. Ganen la confianza "
                               "de la tripulación en NEXUS.", COLOR_MAL)
            else:
                jugador.avisar("Mantén la tecla para reparar la cápsula.", COLOR_AVISO)
            return True
        for nota in self.notas:
            if self._cerca(jugador, nota["rect"], 20):
                nota["leida_por"].add(jugador)
                self._sonar("nota", 0.7)
                jugador.abrir_panel({
                    "tipo": "aviso", "titulo": nota["titulo"], "cuerpo": [nota["texto"]],
                    "pie": f"[{jugador.nombre_tecla('interactuar')}] cerrar",
                })
                return True
        if self.fase == "sabotaje":
            for consola in self.consolas:
                if consola["progreso"] < 1 and self._cerca(jugador, consola["rect"], 20):
                    jugador.avisar("Mantén la tecla para apagar la consola.", COLOR_AVISO)
                    return True
        return False

    def _puerta_cerca(self, jugador):
        """La puerta con código cerrada junto a la que está (la más cercana)."""
        cerca = [p for p in self.puertas_cerradas() if self._cerca(jugador, p["rect"], 70)]
        return min(cerca, key=lambda p: math.dist(p["rect"].center, jugador.hitbox.center), default=None)

    def _panel_codigo(self, jugador, i=0):
        puerta = self.puertas[i]
        opciones = {puerta["codigo"]}
        while len(opciones) < 4:
            opciones.add(self._codigo_nuevo())
        opciones = sorted(opciones)
        jugador.abrir_panel({
            "tipo": "opciones", "accion": "codigo", "codigos": opciones, "puerta": i,
            "titulo": f"Puerta {puerta['nombre']}" if len(self.puertas) > 1 else "Puerta con código",
            "cuerpo": ["Un teclado pide un código de tres números.",
                       "Si te equivocas, suena la alarma."],
            "opciones": [{"texto": c} for c in opciones],
            "pie": (f"[{jugador.pista_mover()}] elegir   "
                    f"[{jugador.nombre_tecla('interactuar')}] marcar"),
        })

    def resolver_codigo(self, jugador, indice):
        codigos = jugador.panel.get("codigos", [])
        i = jugador.panel.get("puerta", 0)
        jugador.cerrar_panel()
        if indice >= len(codigos) or i >= len(self.puertas):
            return
        puerta = self.puertas[i]
        if codigos[indice] == puerta["codigo"]:
            self.abrir_puerta(jugador, i)
        else:
            self.codigos_fallidos += 1
            for alien in self.juego.aliens:
                alien.oir(puerta["rect"].center)
            jugador.avisar("¡Código equivocado! Suena la alarma.", COLOR_MAL)
            self._sonar("alarma", 0.8)
            self._decir("codigo_malo", jugador.rol, True)

    def abrir_puerta(self, jugador=None, i=0):
        """Abre la puerta con código i (0: la de la prisión, que pasa de fase)."""
        if not self.puertas:
            if self.fase == "prision":
                self.fase = "sabotaje" if self.consolas else "capsula"
            return
        puerta = self.puertas[i]
        # Todas las copias: si una ronda anterior dejó la suya, también.
        paredes = self.juego.mundo.paredes
        paredes[:] = [p for p in paredes if p != puerta["rect"]]
        ya_estaba = puerta["abierta"]
        puerta["abierta"] = True
        if jugador is not None and not ya_estaba:
            jugador.sumar_puntos(PUNTOS_PUERTA)
        if puerta is self.principal or i == 0:
            self.abrio = jugador
            if self.fase == "prision":
                self.fase = "sabotaje" if self.consolas else "capsula"
        self._recalcular_acceso()
        self._avisar_todos(f"¡La puerta {puerta['nombre']} se abrió!" if len(self.puertas) > 1
                           else "¡La puerta se abrió!", COLOR_BIEN)
        self._sonar("puerta")
        self._decir("puerta_abierta", None, True)

    # -- Mantener la tecla ------------------------------------------------------------

    def mantener(self, jugador, dt):
        """El jugador mantiene la tecla: avanza consolas o la reparación."""
        jugador.progreso = None
        if not self.activa or jugador.preso:
            return
        paso = dt / 1000
        if self.fase == "sabotaje":
            for consola in self.consolas:
                if consola["progreso"] >= 1 or not self._cerca(jugador, consola["rect"], 20):
                    continue
                if getattr(self.juego, "sin_luz", False):
                    # Sin energía no hay sistema que desconectar.
                    jugador.avisar("Sin energía: enciendan la caja de fusibles.", COLOR_MAL)
                    return
                if jugador.rol == "Tecnomante":
                    duracion = SABOTAJE_ROL_S
                elif "decodificador" in jugador.objetos:
                    duracion = SABOTAJE_OTROS_S
                else:
                    jugador.avisar("Necesitas al Tecnomante o un decodificador.", COLOR_MAL)
                    return
                consola["progreso"] = min(1.0, consola["progreso"] + paso / duracion)
                jugador.progreso = ("Apagando consola", consola["progreso"])
                if consola["progreso"] >= 1:
                    jugador.sumar_puntos(PUNTOS_CONSOLA)
                    jugador.avisar("Consola apagada.", COLOR_BIEN)
                    self._sonar("consola", 0.8)
                    self._decir("consola", jugador.rol)
                return
        if (self.fase == "capsula" and self.piezas_entregadas >= PIEZAS_NECESARIAS
                and self._cerca(jugador, self.capsula, 10)):
            if not self.hay_planos():
                jugador.avisar("Faltan los planos: ganen la confianza en NEXUS.", COLOR_MAL)
                return
            if jugador.rol == "Forjador":
                duracion = REPARACION_ROL_S
            elif "kit" in jugador.objetos:
                duracion = REPARACION_OTROS_S
            else:
                jugador.avisar("Necesitas al Forjador o un kit de herramientas.", COLOR_MAL)
                return
            self.reparacion = min(1.0, self.reparacion + paso / duracion)
            jugador.progreso = ("Reparando la cápsula", self.reparacion)
            if self.reparacion >= 1:
                jugador.sumar_puntos(PUNTOS_REPARACION)
                self.empezar_huida()

    # -- Celdas -------------------------------------------------------------------------

    def encarcelar(self, jugador):
        """Lo atraparon: a una celda libre, hasta que alguien lo saque."""
        if not self.celdas:
            return False
        libres = [c for c in self.celdas if c["preso"] is None] or self.celdas
        celda = libres[0]
        anterior = celda["preso"]
        if anterior is not None and anterior is not jugador:
            # Todas las celdas llenas (4 jugadores, 3 celdas): el que estaba sale
            # para hacerle espacio. Antes solo se le quitaba "preso" y se quedaba
            # dentro de la pared de la celda, sin poder moverse.
            self._sacar_de_celda(anterior, celda)
            anterior.avisar(f"Los aliens te sacaron para encerrar al {jugador.rol}. ¡Corre!", COLOR_BIEN)
        celda["preso"] = jugador
        # Dificultades fáciles: sale solo después de un rato (dificultad.py).
        dif = getattr(self.juego, "dificultad", None)
        celda["fuga_ms"] = dif.fuga_ms if dif is not None else None
        jugador.preso = celda
        jugador.personaje.hitbox.center = celda["punto"]
        jugador.personaje.sync_sprite_from_hitbox()
        for otro in self.juego.jugadores:
            if otro is not jugador:
                otro.avisar(f"¡Encerraron al {jugador.rol}! Vayan a sacarlo.", COLOR_MAL)
        return True

    def fugarse(self, celda):
        """Se le acabó la espera (dificultades fáciles): fuerza la reja y sale."""
        preso = celda["preso"]
        if preso is None:
            return
        celda["preso"] = None
        celda["fuga_ms"] = None
        self._sacar_de_celda(preso, celda)
        preso.avisar("Forzaste la reja: ¡estás libre!", COLOR_BIEN)
        self._sonar("puerta", 0.6)

    def _sacar_de_celda(self, preso, celda):
        preso.preso = None
        x, y = celda["punto"]
        libre = self.juego.mundo.punto_libre((x, y + 90), preso.personaje.hitbox_w,
                                             preso.personaje.hitbox_h)
        preso.personaje.hitbox.topleft = (int(libre[0]), int(libre[1]))
        preso.personaje.sync_sprite_from_hitbox()
        preso.invulnerable_ms = 2500

    def liberar(self, celda, rescatador):
        preso = celda["preso"]
        celda["preso"] = None
        celda["fuga_ms"] = None
        if preso is None:
            return
        self._sacar_de_celda(preso, celda)
        rescatador.sumar_puntos(PUNTOS_RESCATE)
        if rescatador.rol == "Biomante":
            preso.pulso = min(preso.pulso, 20.0)
            preso.avisar("La Biomante te sacó y te calmó.", COLOR_BIEN)
        else:
            preso.avisar(f"El {rescatador.rol} te sacó de la celda.", COLOR_BIEN)
        rescatador.avisar(f"Liberaste al {preso.rol}. +{PUNTOS_RESCATE}", COLOR_BIEN)
        logro(self.juego, "nadie_atras", rescatador)
        if preso.vidas == 1:
            logro(self.juego, "segunda_oportunidad", rescatador)
        self._sonar("puerta", 0.6)
        self._decir("rescate", preso.rol)

    # -- Cuando eliminan a alguien ------------------------------------------------------

    def soltar_al_morir(self, jugador, punto):
        """Lo eliminaron (sin vidas): suelta lo que llevaba donde lo atraparon.

        Sin esto, perder al Tecnomante o al Forjador dejaba la misión sin
        forma de terminarse. El Tecnomante deja un decodificador (para las
        consolas) y el Forjador un kit de herramientas (para la cápsula), si no
        hay ya uno en el mapa o en el inventario de alguien; desde
        ese momento quien lo recoja ve y recoge las piezas. Además cae lo que tuviera
        en el inventario: consumibles y piezas.
        """
        if not self.activa:
            return []
        tipos = sorted(t for t in jugador.objetos.elements() if t in NOMBRE_CONSUMIBLE)
        jugador.objetos.clear()
        # Lo de su rol, uno solo (y si ya hay uno por ahí, nada).
        if jugador.rol == "Tecnomante":
            self.falta_tecnomante = True
            if self.consolas and not self.hay_consumible("decodificador") and "decodificador" not in tipos:
                tipos.insert(0, "decodificador")
        if jugador.rol == "Forjador":
            self.falta_forjador = True
            self.piezas_para_todos = True
            if not self.hay_consumible("kit") and "kit" not in tipos:
                tipos.insert(0, "kit")
        bahia = getattr(self.juego, "guardia_planta", None)
        if (jugador.rol == "Biomante" and bahia is not None and bahia.activo
                and bahia.planta is not None and not bahia.planta["crecida"]):
            self.falta_biomante = True
            if not self.hay_consumible("abono") and "abono" not in tipos:
                tipos.insert(0, "abono")
        piezas, jugador.piezas = jugador.piezas, 0

        mundo = self.juego.mundo
        soltados = []
        total = len(tipos) + piezas
        for i in range(total):
            angulo = 2 * math.pi * i / max(1, total)
            deseado = (punto[0] + math.cos(angulo) * 46 - TAMANO_CONSUMIBLE[0] / 2,
                       punto[1] + math.sin(angulo) * 34 - TAMANO_CONSUMIBLE[1] / 2)
            x, y = mundo.punto_libre(deseado, *TAMANO_CONSUMIBLE)
            centro = (int(x + TAMANO_CONSUMIBLE[0] / 2), int(y + TAMANO_CONSUMIBLE[1] / 2))
            if i < len(tipos):
                cons = {"rect": _rect(centro, TAMANO_CONSUMIBLE), "tipo": tipos[i], "tomado": False}
                self.consumibles.append(cons)
                soltados.append(tipos[i])
            else:
                self.juego.piezas.append({"rect": _rect(centro, (34, 34)), "recogida": False})
                soltados.append("pieza")
        if soltados:
            nombres = {"decodificador": ("decodificador", "decodificadores"),
                       "kit": ("kit de herramientas", "kits de herramientas"),
                       "fruta": ("fruta", "frutas"), "abono": ("abono", "abonos"),
                       "pieza": ("pieza", "piezas")}
            cuenta = {}
            for s in soltados:
                cuenta[s] = cuenta.get(s, 0) + 1
            lista = ", ".join(f"{n} {nombres[t][n > 1]}" for t, n in cuenta.items())
            self._avisar_todos(f"El {jugador.rol} dejó caer: {lista}. ¡Recójanlo!", COLOR_AVISO)
        return soltados

    # -- Fases --------------------------------------------------------------------------

    def empezar_huida(self):
        self.fase = "huida"
        for alien in self.juego.aliens:
            alien.alerta = True
        self._avisar_todos("¡Cápsula lista! Los aliens están en alerta: ¡todos a la cápsula!",
                           COLOR_MAL)
        self._sonar("alarma")
        self._decir("huida", None, True)

    def volver_a_reparar(self):
        """El Cambiaformas saboteó la cápsula ya lista: se vuelve a la fase de
        reparar (traer la pieza que arrancó y terminar la reparación)."""
        self.fase = "capsula"
        for alien in self.juego.aliens:
            alien.alerta = False

    def actualizar(self, dt):
        if not self.activa or self.resultado is not None:
            return
        # Los puestos sin mando todavía no se mueven: no cuentan para ganar ni
        # para perder, o con 3 o 4 jugadores nunca se podría escapar.
        # Los eliminados (sin vidas) tampoco: ya no están en la partida.
        jugadores = [j for j in self.juego.jugadores if j.puede_moverse]
        if not jugadores:
            if any(getattr(j, "eliminado", False) for j in self.juego.jugadores):
                self.resultado = "derrota"     # eliminaron a todos (sin vidas)
                return
            jugadores = self.juego.jugadores
        for celda in self.celdas:
            if celda["preso"] is not None and celda.get("fuga_ms") is not None:
                celda["fuga_ms"] -= dt
                if celda["fuga_ms"] <= 0:
                    self.fugarse(celda)
        # Todos encerrados = derrota, salvo que alguien pueda fugarse solo.
        if (jugadores and all(j.preso for j in jugadores)
                and not any(j.preso.get("fuga_ms") is not None for j in jugadores)):
            self.resultado = "derrota"
            return
        if self.fase == "sabotaje" and self.consolas and all(c["progreso"] >= 1 for c in self.consolas):
            self.fase = "capsula"
            self._avisar_todos("Navegación apagada. Ahora, a la cápsula.", COLOR_BIEN)
        if self.fase == "huida":
            zona = self.capsula.inflate(60, 60)
            if all(not j.preso and zona.colliderect(j.hitbox) for j in jugadores):
                self.resultado = "victoria"
                for j in jugadores:
                    j.sumar_puntos(PUNTOS_ESCAPE // max(1, len(jugadores)))

    def terminar_sin_escapar(self):
        """Se acabó la partida sin que escaparan (Terminar partida en la pausa)."""
        if self.activa and self.resultado is None:
            self.resultado = "derrota"
