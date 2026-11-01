"""NEXUS: la red social de la nave, en el celular de cada jugador.

Por debajo es un grafo (Estructuras/grafo.py): cada cuenta es un nodo y lo
que publica una cuenta les llega a sus seguidores. Hay tres tipos de cuenta:

- **prisioneros** (data/nexus.py: CUENTAS): son los que cuentan para las
  barras. Cada uno está gris (no decide), verde (confía en los jugadores) o
  rojo (le cree a los aliens).
- **bots** del Cambiaformas: parecen prisioneros, pero publican rumores falsos.
- **los jugadores**: reciben en su feed lo que les llega por el grafo.

Las barras de confianza no son números sueltos: son el % de prisioneros
verdes y rojos.

Cómo se juega:
- Un bot publica un rumor (que habla de un lugar de la nave) y se propaga por
  BFS, un nivel por tick. A cada gris que le llega se lo cree o no (al azar,
  PROB_CREER_RUMOR); el que se lo cree se pone rojo y lo reenvía. Los verdes
  no se lo creen: la confianza hace de cortafuegos.
- El jugador lo ve en el feed y puede **investigar** (una flecha lo lleva al
  lugar), **compartir**, **reportar** o **rastrear de dónde vino** (camino
  más corto desde el bot hasta él).
- En el lugar saca una foto sola. Con la foto **desmiente** desde el celular:
  el desmentido se propaga en verde (lo reenvía quien queda convencido).
  Puede publicarla tal cual (se ve dónde está: convence a más gente, pero el
  alien más cercano va por él) o recortarla.
- Compartir un rumor sin verificar lo riega más y tus seguidores dejan de
  confiar en ti. Reportar un bot lo borra del grafo; reportar a un prisionero
  que solo se creyó el rumor no ayuda.
- Con UMBRAL_PLANOS de verdes se desbloquean los planos de la cápsula (sin
  ellos no se puede reparar, mision.py). Si el rojo le va ganando al verde,
  los aliens se vuelven más rápidos y ven más. (Antes, con mucho rojo los
  aliens tomaban NEXUS y se perdía; se quitó: perder es solo por vidas o por
  quedar todos encerrados.)

El celular se dibuja en screens/celular.py; juego/app.py lo abre con la tecla de
celular de cada jugador y le pasa las teclas.
"""

from juego import dificultad
import math
import random

from Estructuras.grafo import Grafo
from misiones.logros import logro
from data.nexus import (
    CUENTAS, BOTS, RUMORES, NORMALES,
    SEGUIDORES_PRISIONERO, SEGUIDORES_BOT, SEGUIDORES_JUGADOR, SIGUE_CADA_JUGADOR,
    BOTS_AL_EMPEZAR, TICK_PROPAGACION_MS, PRIMER_RUMOR_S, RUMOR_CADA_S, NORMAL_CADA_S,
    NUEVO_BOT_CADA_S, MAX_POR_VERIFICAR, NIVELES_DESMENTIDO, NOMBRE_LUGAR, PROB_CONVENCER_UBICACION,
    NIVELES_COMPARTIR_CIERTO, UMBRAL_PLANOS, DIFERENCIA_POTENCIA_MAX,
    RADIO_FOTO, PUNTOS_DESMENTIR,
    PUNTOS_REPORTAR_BOT, PUNTOS_PLANOS, PROB_CREER_RUMOR, PROB_CONVENCER,
    PUNTOS_SUPLANTACION,
)

GRIS, VERDE, ROJO = "gris", "verde", "rojo"
COLOR_BIEN = (120, 230, 150)
COLOR_MAL = (245, 130, 120)
COLOR_NEXUS = (120, 190, 255)
MAX_FEED = 25


class Publicacion:
    _siguiente = 0

    def __init__(self, autor, tipo, texto, falsa=False, rumor=None):
        Publicacion._siguiente += 1
        self.id = Publicacion._siguiente
        self.autor = autor          # nodo que la publicó
        self.tipo = tipo            # "rumor", "normal", "desmentido", "compartido",
                                    # "trampa" (suplantación) o "testimonio" (rescatado)
        self.texto = texto
        self.falsa = falsa
        self.rumor = rumor          # dict de RUMORES (solo los rumores)
        self.lugar = None           # (x, y) donde se verifica (solo los rumores)
        self.desmentida = False
        self.foto = None            # texto de la foto (desmentidos)
        self.con_ubicacion = False
        self.desmiente = None       # la Publicacion que desmiente
        self.suplantada = False     # la escribió el Cambiaformas haciéndose pasar por `autor`
        self.reportada = False
        self.via = {}               # nodo -> de quién le llegó
        self.alcanzados = set()     # nodos a los que les llegó
        self.edad_ms = 0


class Propagacion:
    """Una publicación avanzando por el grafo, un nivel (BFS) por tick."""

    def __init__(self, pub, origen, color, max_niveles=None, prob=1.0):
        self.pub = pub
        self.prob = prob            # a cuántos convence (las verdes)
        self.color = color          # ROJO pinta a los grises; VERDE a todos
        self.frontera = [origen]
        self.visitados = {origen}
        self.niveles = 0
        self.max_niveles = max_niveles
        self.reloj_ms = 0

    @property
    def terminada(self):
        return not self.frontera or (self.max_niveles is not None
                                     and self.niveles >= self.max_niveles)


class RedNexus:
    def __init__(self, juego, rng=None):
        self.juego = juego
        self.rng = rng or random.Random()
        self.grafo = Grafo()
        self.publicaciones = []
        self.propagaciones = []
        self.planos = False
        self.evidencias = {}        # jugador -> [rumores (Publicacion) con foto]
        self.investigando = {}      # jugador -> rumor (Publicacion) que está investigando
        self.vistas = {}            # jugador -> ids de publicaciones ya vistas
        self.stats = {}             # jugador -> contadores para los resultados
        self.tiempo_celular_ms = {}
        self.reloj_rumor_ms = PRIMER_RUMOR_S * 1000
        self.umbral_planos = UMBRAL_PLANOS     # la dificultad lo cambia (App.iniciar_partida)
        self.reloj_normal_ms = self.rng.uniform(*NORMAL_CADA_S) * 1000
        self.reloj_bot_ms = NUEVO_BOT_CADA_S * 1000
        self._bots_usados = 0
        # Para la vista del grafo (screens/grafo_vista.py, Pausa > Opciones).
        self.tiempo_ms = 0
        self.ultimo_rastreo = None   # (camino, tiempo_ms) del último "¿De dónde salió esto?"
        self.borrados = []           # (nodo, usuario, tiempo_ms) de los bots reportados
        self.pestanas = {}           # jugador -> pestaña del celular que dejó abierta
        self._armar_red()

    # -- La red ---------------------------------------------------------------------

    def nodo_de(self, jugador):
        return f"jugador_{jugador.puesto}"

    def _armar_red(self):
        g = self.grafo
        presos = []
        for i, cuenta in enumerate(CUENTAS):
            nodo = f"preso_{i}"
            g.agregar_nodo(nodo, tipo="preso", color=GRIS, **cuenta)
            presos.append(nodo)
        for nodo in presos:
            for otro in self.rng.sample([p for p in presos if p != nodo],
                                        min(SEGUIDORES_PRISIONERO, len(presos) - 1)):
                g.agregar_arista(nodo, otro)
        for jugador in self.juego.jugadores:
            nodo = self.nodo_de(jugador)
            g.agregar_nodo(nodo, tipo="jugador", color=VERDE, nombre=jugador.rol,
                           usuario="@" + jugador.rol.lower())
            for otro in self.rng.sample(presos, min(SEGUIDORES_JUGADOR, len(presos))):
                g.agregar_arista(nodo, otro)
            for otro in self.rng.sample(presos, min(SIGUE_CADA_JUGADOR, len(presos))):
                g.agregar_arista(otro, nodo)
            self.evidencias[jugador] = []
            self.vistas[jugador] = set()
            self.stats[jugador] = {"desmentidos": 0, "compartidos_falsos": 0,
                                   "compartidos_ciertos": 0, "bots_reportados": 0,
                                   "reportes_injustos": 0, "fotos_ubicacion": 0,
                                   "fotos_recortadas": 0, "rastreos": 0, "suplantaciones": 0}
            self.tiempo_celular_ms[jugador] = 0
        for _ in range(min(BOTS_AL_EMPEZAR, len(BOTS))):
            self._nuevo_bot()

    def _nuevo_bot(self):
        if self._bots_usados >= len(BOTS):
            return None
        cuenta = BOTS[self._bots_usados]
        nodo = f"bot_{self._bots_usados}"
        self._bots_usados += 1
        self.grafo.agregar_nodo(nodo, tipo="bot", color=ROJO, **cuenta)
        presos = self._presos()
        for otro in self.rng.sample(presos, min(SEGUIDORES_BOT, len(presos))):
            self.grafo.agregar_arista(nodo, otro)
        # Para parecer real, el bot también sigue a unos prisioneros.
        for otro in self.rng.sample(presos, min(2, len(presos))):
            self.grafo.agregar_arista(otro, nodo)
        return nodo

    def _presos(self):
        return [n for n in self.grafo.nodos() if self.grafo.datos[n]["tipo"] == "preso"]

    def bots(self):
        return [n for n in self.grafo.nodos() if self.grafo.datos[n]["tipo"] == "bot"]

    def color(self, nodo):
        return self.grafo.datos[nodo]["color"]

    def usuario(self, nodo):
        datos = self.grafo.datos.get(nodo)
        return datos["usuario"] if datos else "@cuenta_borrada"

    def es_bot(self, nodo):
        datos = self.grafo.datos.get(nodo)
        return datos is not None and datos["tipo"] == "bot"

    # -- Barras --------------------------------------------------------------------------

    def barras(self):
        """(fracción de prisioneros verdes, fracción de rojos)."""
        presos = self._presos()
        if not presos:
            return 0.0, 0.0
        verdes = sum(self.color(n) == VERDE for n in presos)
        rojos = sum(self.color(n) == ROJO for n in presos)
        return verdes / len(presos), rojos / len(presos)

    def potencia_aliens(self):
        """0 a 1: qué tanto le va ganando el rojo al verde."""
        verde, rojo = self.barras()
        return max(0.0, min(1.0, (rojo - verde) / DIFERENCIA_POTENCIA_MAX))

    # -- Frame -----------------------------------------------------------------------------

    def actualizar(self, dt):
        juego = self.juego
        self.tiempo_ms += dt
        en_tutorial = getattr(juego, "en_tutorial", False)
        for jugador in juego.jugadores:
            panel = jugador.panel or {}
            if panel.get("tipo") == "celular":
                self.tiempo_celular_ms[jugador] = self.tiempo_celular_ms.get(jugador, 0) + dt

        if not en_tutorial:
            self.reloj_rumor_ms -= dt
            if self.reloj_rumor_ms <= 0:
                self.reloj_rumor_ms = (self.rng.uniform(*RUMOR_CADA_S) * 1000
                                       * dificultad.valor(self.juego, "rumor_cada", 1.0))
                self.lanzar_rumor()
            self.reloj_normal_ms -= dt
            if self.reloj_normal_ms <= 0:
                self.reloj_normal_ms = self.rng.uniform(*NORMAL_CADA_S) * 1000
                self.publicar_normal()
            if len(self.bots()) < BOTS_AL_EMPEZAR:
                self.reloj_bot_ms -= dt
                if self.reloj_bot_ms <= 0:
                    self.reloj_bot_ms = NUEVO_BOT_CADA_S * 1000
                    self._nuevo_bot()

        for pub in self.publicaciones:
            pub.edad_ms += dt
        for prop in list(self.propagaciones):
            prop.reloj_ms += dt
            while prop.reloj_ms >= TICK_PROPAGACION_MS and not prop.terminada:
                prop.reloj_ms -= TICK_PROPAGACION_MS
                self._avanzar(prop)
            if prop.terminada:
                self.propagaciones.remove(prop)

        self._fotos()
        self._revisar_umbrales()
        potencia = self.potencia_aliens()
        for alien in getattr(juego, "aliens", ()):
            alien.potencia_nexus = potencia

    def _avanzar(self, prop):
        """Un tick: la publicación llega al siguiente nivel del BFS."""
        g = self.grafo
        if prop.color == ROJO:
            # Solo reenvía el rumor quien se lo cree (el bot que lo empezó y los
            # rojos). Los verdes y los grises que no se lo creyeron lo dejan ahí.
            def puede_pasar(n):
                return n in g and self.color(n) == ROJO
        elif prop.color == VERDE:
            # Igual con la verdad: la reenvía quien quedó convencido (verde).
            def puede_pasar(n):
                return n in g and self.color(n) == VERDE and g.datos[n]["tipo"] != "bot"
        else:
            # Lo que no cambia opiniones (charla, la trampa del Cambiaformas)
            # lo reenvía cualquier prisionero.
            def puede_pasar(n):
                return n in g and g.datos[n]["tipo"] == "preso"
        frontera = [n for n in prop.frontera if n in g]
        nivel = g.expandir(frontera, prop.visitados, puede_pasar)
        prop.niveles += 1
        prop.frontera = [n for n, _ in nivel]
        for nodo, de_quien in nivel:
            if (prop.pub.tipo in ("rumor", "trampa") and g.datos[nodo]["tipo"] == "jugador"
                    and self._lleno(nodo)):
                continue        # ya tiene MAX_POR_VERIFICAR: a ese jugador no le llega
            prop.pub.alcanzados.add(nodo)
            prop.pub.via.setdefault(nodo, de_quien)
            tipo = g.datos[nodo]["tipo"]
            if tipo == "preso":
                # No todos se creen lo que les llega: cada uno decide (al azar).
                if (prop.color == ROJO and self.color(nodo) == GRIS
                        and self.rng.random() < dificultad.valor(self.juego, "prob_creer", PROB_CREER_RUMOR)):
                    g.datos[nodo]["color"] = ROJO
                elif prop.color == VERDE and self.rng.random() < prop.prob:
                    g.datos[nodo]["color"] = VERDE
            elif tipo == "jugador":
                self._llego_a_jugador(nodo, prop.pub)

    def _lleno(self, nodo):
        jugador = self._jugador_de(nodo)
        return jugador is not None and len(self.por_verificar_de(jugador)) >= MAX_POR_VERIFICAR

    def _llego_a_jugador(self, nodo, pub):
        jugador = self._jugador_de(nodo)
        if jugador is None or pub.tipo == "normal":
            return
        tecla = jugador.nombre_tecla("celular")
        if pub.tipo == "rumor":
            lugar = NOMBRE_LUGAR.get(pub.rumor.get("lugar"), "la nave")
            jugador.avisar(f"NEXUS [{tecla}] · Por verificar: un rumor sobre {lugar}", COLOR_NEXUS)
            self._sonar("senal", 0.25)
        elif pub.tipo == "trampa":
            lugar = getattr(pub, "nombre_lugar", None) or "la nave"
            jugador.avisar(f"NEXUS [{tecla}] · {self.usuario(pub.autor)} pide ayuda en {lugar}",
                           COLOR_NEXUS)
            self._sonar("senal", 0.25)
        elif pub.tipo == "desmentido":
            jugador.avisar(f"NEXUS · Equipo: {self.usuario(pub.autor)} desmintió un rumor", COLOR_BIEN)
        elif pub.tipo == "testimonio":
            jugador.avisar(f"NEXUS · {self.usuario(pub.autor)}: ¡me rescataron!", COLOR_BIEN)

    def _sonar(self, nombre, volumen):
        if hasattr(self.juego, "sonar"):
            self.juego.sonar(nombre, volumen)

    def _decir(self, evento, rol=None):
        if hasattr(self.juego, "decir"):
            self.juego.decir(evento, rol)

    # -- Publicaciones de los demás -------------------------------------------------------

    def _lugares(self, tipo):
        """Puntos del mundo donde se puede verificar un rumor de ese lugar."""
        j = self.juego
        mision = getattr(j, "mision", None)
        if tipo == "capsula":
            return [mision.capsula.center] if mision is not None and mision.capsula else []
        if tipo == "consola":
            return [c["rect"].center for c in (mision.consolas if mision else [])]
        if tipo == "celda":
            return [c["punto"] for c in (mision.celdas if mision else [])]
        if tipo == "fusibles":
            eventos = getattr(j, "eventos", None)
            return [c["rect"].center for c in (eventos.cajas if eventos else [])]
        if tipo == "escondite":
            return [e["rect"].center for e in getattr(j, "escondites", [])]
        if tipo == "terminal":
            return [t["rect"].center for t in getattr(j, "terminales", [])]
        if tipo == "panel":
            return [p["rect"].center for p in getattr(j, "paneles", [])]
        if tipo == "puerta_doble":
            return [p["rect"].center for p in getattr(j, "puertas_dobles", [])]
        return []

    def por_verificar(self):
        """Todo lo que hay que ir a verificar en persona: rumores sin desmentir y
        la trampa del Cambiaformas (de todo el equipo)."""
        trampa = self.trampa_activa()
        return self.rumores_activos() + ([trampa] if trampa is not None else [])

    def por_verificar_de(self, jugador):
        """Lo que tiene ESE jugador por verificar: lo que le llegó (o al que va).
        Nunca más de MAX_POR_VERIFICAR: lo que le llega estando lleno se pierde."""
        nodo = self.nodo_de(jugador)
        yendo = self.investigando.get(jugador)
        return [p for p in self.por_verificar() if nodo in p.alcanzados or p is yendo]

    def _hay_lugar(self):
        """¿Se puede publicar otra cosa por verificar? Si a alguien le cabe, y sin
        pasar de MAX_POR_VERIFICAR por jugador en total (con 1 jugador, 3)."""
        jugadores = [j for j in self.juego.jugadores
                     if j in self.vistas and not getattr(j, "eliminado", False)]
        if not jugadores:
            return False
        if len(self.por_verificar()) >= MAX_POR_VERIFICAR * len(jugadores):
            return False
        return any(len(self.por_verificar_de(j)) < MAX_POR_VERIFICAR for j in jugadores)

    def _jugador_de(self, nodo):
        return next((j for j in self.juego.jugadores if self.nodo_de(j) == nodo), None)

    def rumores_activos(self):
        return [p for p in self.publicaciones if p.tipo == "rumor" and not p.desmentida]

    def lanzar_rumor(self, rumor=None, bot=None):
        """Un bot publica un rumor falso sobre un lugar de la nave."""
        bots = self.bots()
        if not bots or not self._hay_lugar():
            return None
        usados = {p.rumor["lugar"] for p in self.rumores_activos()}
        opciones = [r for r in RUMORES if r["lugar"] not in usados and self._lugares(r["lugar"])]
        if rumor is None:
            if not opciones:
                return None
            rumor = self.rng.choice(opciones)
        lugares = self._lugares(rumor["lugar"])
        if not lugares:
            return None
        bot = bot or self.rng.choice(bots)
        pub = Publicacion(bot, "rumor", rumor["texto"], falsa=True, rumor=rumor)
        pub.lugar = self.rng.choice(lugares)
        self.publicaciones.append(pub)
        self.propagaciones.append(Propagacion(pub, bot, ROJO))
        self._decir("rumor")
        return pub

    def publicar_normal(self):
        presos = self._presos()
        if not presos:
            return None
        autor = self.rng.choice(presos)
        pub = Publicacion(autor, "normal", self.rng.choice(NORMALES))
        self.publicaciones.append(pub)
        self.propagaciones.append(Propagacion(pub, autor, None, max_niveles=2))
        return pub

    # -- Fotos -----------------------------------------------------------------------------

    def _fotos(self):
        """Si un jugador está en el lugar de un rumor que le llegó, saca la foto."""
        for jugador in self.juego.jugadores:
            if jugador.preso or getattr(jugador, "eliminado", False):
                continue
            yendo = self.investigando.get(jugador)
            if (yendo is not None and yendo.tipo == "trampa"
                    and (yendo.reportada or math.dist(jugador.hitbox.center, yendo.lugar) <= RADIO_FOTO)):
                del self.investigando[jugador]
                if not yendo.reportada:
                    jugador.avisar(f"Aquí no hay nada... ¿y {self.usuario(yendo.autor)}?",
                                   COLOR_MAL)
            nodo = self.nodo_de(jugador)
            c = jugador.hitbox.center
            for pub in self.rumores_activos():
                if nodo not in pub.alcanzados and self.investigando.get(jugador) is not pub:
                    continue
                if pub in self.evidencias[jugador]:
                    continue
                if math.dist(c, pub.lugar) <= RADIO_FOTO:
                    self.evidencias[jugador].append(pub)
                    if self.investigando.get(jugador) is pub:
                        del self.investigando[jugador]
                    jugador.avisar("Foto tomada. Abre NEXUS para desmentir el rumor.", COLOR_BIEN)
                    self._sonar("recoger", 0.6)

    # -- Acciones del jugador ---------------------------------------------------------------

    def feed(self, jugador):
        """Lo que le llegó por el grafo y lo que publicó él, lo más nuevo primero."""
        nodo = self.nodo_de(jugador)
        lista = [p for p in self.publicaciones if nodo in p.alcanzados or p.autor == nodo]
        return list(reversed(lista))[:MAX_FEED]

    def nodo_de_usuario(self, usuario):
        return next((n for n, d in self.grafo.datos.items() if d.get("usuario") == usuario), None)

    def trampa_activa(self):
        """La publicación con la que el Cambiaformas está cebando, si hay."""
        return next((p for p in reversed(self.publicaciones)
                     if p.tipo == "trampa" and not p.reportada and p.edad_ms < 70000), None)

    def publicar_trampa(self, usuario, texto, lugar, nombre_lugar=None):
        """El Cambiaformas publica haciéndose pasar por `usuario` (suplantación)."""
        autor = self.nodo_de_usuario(usuario)
        if autor is None or autor not in self.grafo:
            return None
        if not self._hay_lugar():
            return None
        pub = Publicacion(autor, "trampa", texto, falsa=True)
        pub.lugar = lugar
        pub.nombre_lugar = nombre_lugar
        pub.suplantada = True
        self.publicaciones.append(pub)
        self.propagaciones.append(Propagacion(pub, autor, None, max_niveles=5))
        return pub

    def reportar_suplantacion(self, jugador, pub):
        """Alguien notó que esa cuenta no la escribió su dueño: el Cambiaformas
        queda al descubierto un rato."""
        if pub is None or not pub.suplantada or pub.reportada:
            return "Esa publicación ya no está.", 0
        pub.reportada = True
        self.stats[jugador]["suplantaciones"] += 1
        jugador.sumar_puntos(PUNTOS_SUPLANTACION)
        logro(self.juego, "perfil_robado", jugador)
        cf = getattr(self.juego, "cambiaformas", None)
        if cf is not None:
            cf.desenmascarar()
        self._sonar("expuesto", 0.8)
        for otro in self.juego.jugadores:
            otro.avisar(f"¡Alguien se hacía pasar por {self.usuario(pub.autor)}! "
                        "El Cambiaformas quedó al descubierto", COLOR_BIEN)
        return (f"NEXUS confirmó que {self.usuario(pub.autor)} no escribió eso: era el "
                "Cambiaformas usando su nombre. Quedó al descubierto un rato.", PUNTOS_SUPLANTACION)

    def publicar_testimonio(self, nodo, texto):
        """Un prisionero rescatado cuenta en NEXUS que ustedes lo salvaron."""
        if nodo not in self.grafo:
            return None
        self.grafo.datos[nodo]["color"] = VERDE
        pub = Publicacion(nodo, "testimonio", texto)
        self.publicaciones.append(pub)
        self.propagaciones.append(Propagacion(pub, nodo, VERDE, max_niveles=NIVELES_DESMENTIDO,
                                              prob=PROB_CONVENCER))
        return pub

    def sin_leer(self, jugador):
        return sum(1 for p in self.feed(jugador)
                   if p.id not in self.vistas[jugador] and p.tipo != "normal")

    def via(self, jugador, pub):
        """Quién se la pasó (el vecino por el que le llegó)."""
        return pub.via.get(self.nodo_de(jugador), pub.autor)

    def investigar(self, jugador, pub):
        self.investigando[jugador] = pub
        return "Una flecha te lleva al lugar. Al llegar, la foto se saca sola."

    def compartir(self, jugador, pub):
        nodo = self.nodo_de(jugador)
        st = self.stats[jugador]
        if pub.tipo in ("rumor", "trampa"):
            # Riega el rumor desde él, y los que lo siguen dejan de confiar.
            st["compartidos_falsos"] += 1
            for seguidor in self.grafo.vecinos(nodo):
                if self.grafo.datos[seguidor]["tipo"] == "preso":
                    self.grafo.datos[seguidor]["color"] = ROJO
            self.propagaciones.append(Propagacion(pub, nodo, ROJO, max_niveles=2))
            self._sonar("fallo", 0.5)
            return ("Lo compartiste sin verificar. Era falso: tus seguidores se lo "
                    "creyeron y ahora desconfían de ti. Antes de compartir, verifica.", -5)
        st["compartidos_ciertos"] += 1
        copia = Publicacion(nodo, "compartido", pub.texto)
        copia.desmiente = pub.desmiente
        self.publicaciones.append(copia)
        self.propagaciones.append(Propagacion(copia, nodo, VERDE,
                                              max_niveles=NIVELES_COMPARTIR_CIERTO,
                                              prob=PROB_CONVENCER))
        return "Compartiste algo cierto. Tus seguidores confían un poco más en ustedes.", 2

    def rastrear(self, jugador, pub):
        """Camino más corto desde quien la publicó hasta el jugador."""
        self.stats[jugador]["rastreos"] += 1
        camino = self.grafo.camino_mas_corto(pub.autor, self.nodo_de(jugador))
        if camino is None:
            # La cuenta ya no existe o se cortó el camino: se usa el que quedó guardado.
            camino, nodo = [self.nodo_de(jugador)], self.nodo_de(jugador)
            while nodo in pub.via and pub.via[nodo] != nodo and len(camino) < 12:
                nodo = pub.via[nodo]
                camino.append(nodo)
            camino.reverse()
        self.ultimo_rastreo = (camino, self.tiempo_ms)
        return camino

    def reportar(self, jugador, nodo):
        """Reportar una cuenta: si es bot se borra del grafo. Si es la cuenta
        que el Cambiaformas está suplantando, se reporta la suplantación."""
        st = self.stats[jugador]
        trampa = self.trampa_activa()
        if trampa is not None and trampa.autor == nodo:
            return self.reportar_suplantacion(jugador, trampa)
        if self.es_bot(nodo):
            usuario = self.usuario(nodo)
            self.borrados.append((nodo, usuario, self.tiempo_ms))
            self.grafo.eliminar_nodo(nodo)
            st["bots_reportados"] += 1
            jugador.sumar_puntos(PUNTOS_REPORTAR_BOT)
            logro(self.juego, "cazador_de_bots", jugador)
            self._sonar("acierto", 0.6)
            return (f"{usuario} era una cuenta falsa del Cambiaformas. Quedó borrada: "
                    "lo que regaba ya no pasa por ahí.", PUNTOS_REPORTAR_BOT)
        if nodo not in self.grafo:
            return "Esa cuenta ya no existe.", 0
        st["reportes_injustos"] += 1
        usuario = self.usuario(nodo)
        if self.grafo.datos[nodo]["tipo"] == "preso":
            self.grafo.datos[nodo]["color"] = ROJO
        self._sonar("fallo", 0.5)
        return (f"{usuario} es un prisionero de verdad: solo se creyó el rumor. Reportarlo "
                "no lo frena y ahora desconfía de ustedes. Busquen quién lo empezó.", -5)

    def desmentir(self, jugador, rumor, con_ubicacion):
        """Publica la foto del lugar: el desmentido se propaga en verde."""
        if rumor not in self.evidencias.get(jugador, []):
            return "No tienes foto de ese lugar.", 0
        self.evidencias[jugador].remove(rumor)
        nodo = self.nodo_de(jugador)
        st = self.stats[jugador]
        st["desmentidos"] += 1
        pub = Publicacion(nodo, "desmentido", rumor.rumor["desmentido"])
        pub.foto = rumor.rumor["foto"]
        pub.desmiente = rumor
        pub.con_ubicacion = con_ubicacion
        self.publicaciones.append(pub)
        if not rumor.desmentida:
            rumor.desmentida = True
            # El rumor deja de avanzar.
            for prop in self.propagaciones:
                if prop.pub is rumor:
                    prop.frontera = []
        prob = PROB_CONVENCER_UBICACION if con_ubicacion else PROB_CONVENCER
        self.propagaciones.append(Propagacion(pub, nodo, VERDE, max_niveles=NIVELES_DESMENTIDO,
                                              prob=prob))
        jugador.sumar_puntos(PUNTOS_DESMENTIR)
        logro(self.juego, "fact_checker", jugador)
        self._decir("desmentido", jugador.rol)
        self._sonar("senal", 0.6)
        texto = "Desmentiste el rumor. La verdad ya está corriendo por NEXUS."
        if con_ubicacion:
            st["fotos_ubicacion"] += 1
            alien = self._alertar_alien(jugador)
            if alien is not None:
                texto += f" Pero en la foto se ve dónde estás: el {alien.nombre} viene por ti."
                jugador.avisar(f"¡Tu foto te delató! El {alien.nombre} viene", COLOR_MAL)
        else:
            st["fotos_recortadas"] += 1
            logro(self.juego, "perfil_bajo", jugador)
        return texto, PUNTOS_DESMENTIR

    def _alertar_alien(self, jugador):
        """La foto deja ver dónde está: el alien más cercano va para allá."""
        cambiaformas = getattr(self.juego, "cambiaformas", None)
        if cambiaformas is not None:
            cambiaformas.enterarse(jugador)      # él también lee NEXUS
        aliens = [a for a in getattr(self.juego, "aliens", ())
                  if a.descanso_ms <= 0 and a is not cambiaformas]
        if not aliens:
            return None
        c = jugador.hitbox.center
        alien = min(aliens, key=lambda a: math.dist(a.centro, c))
        if alien.oir(c):
            self._sonar("alarma", 0.4)
            return alien
        return None

    # -- Umbrales -------------------------------------------------------------------------

    def _revisar_umbrales(self):
        verde, rojo = self.barras()
        if not self.planos and verde >= self.umbral_planos:
            self.desbloquear_planos()

    def desbloquear_planos(self):
        if self.planos:
            return
        self.planos = True
        for jugador in self.juego.jugadores:
            jugador.avisar("¡La tripulación confía en ustedes! Les pasaron los planos de la cápsula.",
                           COLOR_BIEN)
        equipo = getattr(self.juego, "equipo", None)
        if equipo is not None:
            equipo.sumar(PUNTOS_PLANOS)
        logro(self.juego, "planos")
        self._sonar("logro", 0.8)
        self._decir("planos")

    # -- Resumen para los resultados ----------------------------------------------------------

    def resumen(self):
        """Totales del equipo y un consejo según cómo usaron NEXUS."""
        total = {}
        for st in self.stats.values():
            for clave, valor in st.items():
                total[clave] = total.get(clave, 0) + valor
        minutos = sum(self.tiempo_celular_ms.values()) / 60000
        total["minutos_celular"] = minutos
        if total.get("compartidos_falsos", 0) > total.get("desmentidos", 0):
            consejo = "Compartieron más rumores de los que desmintieron: antes de compartir, verifiquen."
        elif total.get("fotos_ubicacion", 0) > total.get("fotos_recortadas", 0):
            consejo = "Publicar dónde están los puso en peligro: cuiden su ubicación en redes."
        elif total.get("reportes_injustos", 0) > total.get("bots_reportados", 0):
            consejo = "Reportaron a gente que solo se creyó un rumor: busquen la fuente."
        elif total.get("desmentidos", 0) == 0:
            consejo = "Nadie desmintió nada: en redes, el silencio también deja ganar a la mentira."
        else:
            consejo = "Buen uso de NEXUS: verificaron, cuidaron su ubicación y frenaron los rumores."
        total["consejo"] = consejo
        return total
