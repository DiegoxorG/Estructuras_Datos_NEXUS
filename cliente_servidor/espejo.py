"""El "espejo": un Game de verdad en el cliente que solo sirve para dibujar.

En vez de reescribir el dibujo para el modo en red, el cliente arma la misma
partida que el servidor (mismo mapa, roles, dificultad y semilla) con el
`Game` de juego/app.py, NUNCA la actualiza (no corre `_actualizar_partida`:
el que manda es el servidor) y en cada cuadro le copia encima lo que dice la
instantánea: posiciones, vidas, paneles, misión, eventos, linterna... Después
llama las MISMAS funciones de dibujo del modo local (`_dibujar_partida_en`,
que usa screens/partida.py, paneles.py, celular.py, oscuridad.py...). Así se
ve igual que el local: vistas divididas, HUD, oscuridad y visión, sustos,
paneles, celular.

Lo que no viaja (referencias entre objetos, imágenes, árboles de
comportamiento) se queda como lo armó el espejo; ver cliente_servidor/estado.py.
"""

import random

import pygame

from cliente_servidor import estado as E
from cliente_servidor.protocolo import lista as a_lista


class _Preso(dict):
    """En el servidor `jugador.preso` es la celda (un dict); en el espejo
    basta con algo que diga "sí" y aguante un .get()."""

    def __bool__(self):
        return True


class Espejo:
    def __init__(self, juego, bienvenida):
        self.g = juego
        self.b = bienvenida
        self.aliens = {}           # nombre -> objeto Alien del espejo
        self.pubs = {}             # id -> Publicacion del espejo (ver _publicaciones)
        self._pasos_npc = {}       # id del NPC -> (posición, cuándo cambió, último paso)
        self._agujas = {}          # id del jugador -> ((aguja, sentido) del servidor, cuándo llegó)
        self._reloj_ms = None      # para avanzar las animaciones con el tiempo real
        self._dt_ms = 0
        self.listo = False
        self.error = None

    def preparar(self):
        """Arma la partida igual que el servidor (tarda unos segundos: se
        puede llamar desde otro hilo, como la pantalla de carga del juego)."""
        from juego import app as App
        from juego.dificultad import Dificultad
        g, b = self.g, self.b
        if b.get("dificultad"):
            g.dificultad = Dificultad(b["dificultad"])
        g.cantidad_jugadores = b["jugadores"]
        g.abrir_seleccion_roles(ir=False)
        for estado, rol in zip(g.seleccion_roles, b["roles"]):
            estado["rol"], estado["listo"] = rol, True
        from juego import objetos_mapa
        mapa_activo = objetos_mapa.mapa_activo
        objetos_mapa.mapa_activo = lambda: b["mapa"]
        try:
            random.seed(b.get("semilla"))
            g._preparar_partida()
        finally:
            objetos_mapa.mapa_activo = mapa_activo
        g.saltar_tutorial()
        if not b.get("presentaciones", True):
            g.presentacion = None
        for alien in list(g.aliens) + [getattr(g, "sombra", None), getattr(g, "cambiaformas", None)]:
            if alien is not None and hasattr(alien, "nombre"):
                self.aliens[alien.nombre] = alien
        self.listo = True

    # -- Copiar la instantánea encima ----------------------------------------------

    def aplicar(self, secciones, interpolado=None):
        g = self.g
        interpolado = interpolado or {}
        ahora = pygame.time.get_ticks()
        self._dt_ms = 0 if self._reloj_ms is None else max(0, min(100, ahora - self._reloj_ms))
        self._reloj_ms = ahora
        # Las referencias ({"P": id}, {"J": 1}, {"A": "Vigía 3"}) se cambian por
        # los objetos de ESTE espejo (con dos sesiones en un proceso, como en las
        # pruebas, cada una pone el suyo antes de aplicar).
        E.RESOLVER = self._resolver
        self._publicaciones(secciones.get("pubs"))
        glob = secciones.get("g", {})
        for clave, v in glob.items():
            if clave.startswith("G."):
                try:
                    setattr(g, clave[2:], E.a_python(v))
                except (AttributeError, TypeError):
                    pass
        for i, jugador in enumerate(g.jugadores):
            datos = secciones.get(f"j{i}")
            if datos is not None:
                self._jugador(jugador, datos, interpolado.get(f"j{i}"))
        self._aliens(secciones.get("al", {}), interpolado)
        from cliente_servidor.servidor import OBJETOS, LISTAS
        for clave, nombre in OBJETOS.items():
            datos = secciones.get(clave)
            objeto = getattr(g, nombre, None)
            if datos is None:
                continue
            if not datos:
                if nombre in ("presentacion", "tutorial"):
                    setattr(g, nombre, None)       # (en el servidor ya no está)
                continue
            if objeto is not None:
                cuerpo = {k: v for k, v in datos.items() if k != "ok"}
                if nombre == "npcs" and isinstance(cuerpo.get("npcs"), list):
                    self._npcs(objeto, cuerpo.pop("npcs"))
                E.aplicar(objeto, cuerpo)
        for clave, nombre in LISTAS.items():
            datos = secciones.get(clave)
            lista = getattr(g, nombre, None)
            if datos is None or not isinstance(lista, list):
                continue
            nuevos = a_lista(datos)
            for k, d in enumerate(nuevos):
                if d is None:
                    continue
                if k < len(lista):
                    if hasattr(lista[k], "__dict__"):
                        E.aplicar(lista[k], d)
                    else:
                        lista[k] = E._mezclar(lista[k], d)
                elif isinstance(d, dict) and (not lista or isinstance(lista[0], dict)):
                    lista.append(E.a_python(d))
            if len(lista) > len(nuevos):
                del lista[len(nuevos):]
        self._presentacion(glob.get("presentacion"))
        self._animar_npcs()
        orden = (secciones.get("pubs") or {}).get("orden")
        red = getattr(g, "nexus", None)
        if red is not None and orden is not None:
            red.publicaciones = [self._pub(i) for i in orden]

    def _npcs(self, gestor, lista):
        """Los prisioneros que caminan, por su cuenta (`nodo`): así uno que se
        fue (rescatado) no se queda parado en el espejo y uno nuevo aparece.
        Antes se copiaban por posición en la lista y, si cambiaba el largo, se
        dejaba la lista vieja."""
        from entidades.npcs import NPC
        actuales = {getattr(n, "nodo", None): n for n in gestor.npcs}
        nuevos = []
        for datos in lista:
            if not isinstance(datos, dict):
                continue
            npc = actuales.get(datos.get("nodo"))
            if npc is None:
                npc = NPC.__new__(NPC)
                npc.__dict__.update({"hitbox": pygame.Rect(0, 0, 24, 20), "ruta": [], "burbuja": None,
                                     "burbuja_ms": 0, "siguiendo": None, "juego": self.g,
                                     "apariencia": None, "nodo": None, "usuario": ""})
            E.aplicar(npc, datos)
            if getattr(npc, "apariencia", None) is not None:
                nuevos.append(npc)
        gestor.npcs = nuevos

    def _animar_npcs(self):
        """Los prisioneros caminan con la animación del cliente: en el modo
        local la avanza su `actualizar`, que el espejo no corre. Se mira cuánto
        se movió cada uno (las posiciones llegan 30 veces por segundo, así que
        "se está moviendo" dura un poco después de cada cambio)."""
        import time
        ahora = time.perf_counter()
        quienes = list(getattr(getattr(self.g, "npcs", None), "npcs", None) or [])
        cf = getattr(self.g, "cambiaformas", None)
        if cf is not None and getattr(cf, "apariencia", None) is not None and hasattr(cf, "hitbox"):
            quienes.append(cf)
        vistos = set()
        for quien in quienes:
            ap = getattr(quien, "apariencia", None)
            if ap is None or not hasattr(ap, "animar"):
                continue
            clave = id(quien)
            vistos.add(clave)
            centro = quien.hitbox.center
            antes = self._pasos_npc.get(clave)
            if antes is None or antes[0] != centro:
                d = (centro[0] - antes[0][0], centro[1] - antes[0][1]) if antes else (0, 0)
                antes = (centro, ahora, d if d != (0, 0) else (antes[2] if antes else (0, 0)))
                self._pasos_npc[clave] = antes
            camina = ahora - antes[1] < 0.15 and antes[2] != (0, 0)
            try:
                ap.animar(*(antes[2] if camina else (0, 0)), self._dt_ms)
            except Exception:
                pass
        for clave in [c for c in self._pasos_npc if c not in vistos]:
            del self._pasos_npc[clave]

    def _resolver(self, marca, identidad):
        if marca == "P":
            return self._pub(identidad)
        if marca == "J":
            jugadores = self.g.jugadores
            return jugadores[identidad] if isinstance(identidad, int) and 0 <= identidad < len(jugadores) else None
        if marca == "A":
            return self.aliens.get(identidad)
        return None

    def _pub(self, identidad):
        """La publicación `identidad` del espejo (se crea vacía si no estaba)."""
        pub = self.pubs.get(identidad)
        if pub is None:
            from redes.nexus import Publicacion
            pub = Publicacion.__new__(Publicacion)
            pub.__dict__.update({"autor": None, "tipo": "normal", "texto": "", "falsa": False,
                                 "rumor": None, "lugar": None, "desmentida": False, "foto": None,
                                 "con_ubicacion": False, "desmiente": None, "suplantada": False,
                                 "reportada": False, "via": {}, "alcanzados": set(), "edad_ms": 0})
            pub.id = identidad
            self.pubs[identidad] = pub
        return pub

    def _publicaciones(self, datos):
        if not datos:
            return
        for clave, d in datos.items():
            if clave == "orden" or not isinstance(d, dict):
                continue
            identidad = int(clave) if clave.lstrip("-").isdigit() else clave
            E.aplicar(self._pub(identidad), d)

    def _presentacion(self, datos):
        """La ventana que presenta un alien. En el servidor `actual` tiene al
        jugador y al alien (objetos), que no viajan: el dict llegaba sin ellos
        y el dibujo se caía con KeyError 'jugador'. Aquí se arma con los del
        espejo."""
        p = getattr(self.g, "presentacion", None)
        if p is None:
            return
        if not datos:
            p.actual = None
            return
        indice = datos.get("jugador", 0)
        jugador = self.g.jugadores[indice] if 0 <= indice < len(self.g.jugadores) else None
        alien = self.aliens.get(datos.get("alien"))
        if alien is None:       # (no está entre los vistos: uno del mismo tipo, o uno de mentira)
            alien = next((a for a in self.aliens.values() if a.tipo == datos.get("tipo")), None)
        if jugador is None or alien is None or not datos.get("tipo"):
            p.actual = None
            return
        if datos.get("x") is not None and alien not in self.g.aliens:
            alien.hitbox.center = (round(datos["x"]), round(datos["y"]))
        p.actual = {"tipo": datos["tipo"], "alien": alien, "jugador": jugador, "ms": datos.get("ms", 0)}

    def _jugador(self, j, datos, pos):
        p = j.personaje
        x, y = (pos[0], pos[1]) if pos else (datos["x"], datos["y"])
        p.x, p.y = x, y
        p.sync_hitbox_from_sprite()
        p.direccion = datos["dir"]
        p.moviendose = datos["mov"]
        # La animación es del cliente (no vale la pena mandar el cuadro).
        nuevo = "walking" if datos["mov"] else (
            "breathing" if p.animaciones.get("breathing", {}).get(p.direccion) else "idle")
        if nuevo != p.estado:
            p.estado, p.frame_actual, p.contador_animacion = nuevo, 0, 0
        # En el modo local la animación avanza en Personaje.actualizar, que el
        # espejo nunca llama: sin esto caminaban "deslizándose" en el cuadro 0.
        # (Personaje cuenta cuadros de 60 por segundo: se avanza según el
        # tiempo real, para que vaya igual aunque el cliente dibuje a 30.)
        self._avance_j = getattr(self, "_avance_j", {})
        pendiente = self._avance_j.get(id(p), 0.0) + self._dt_ms * 60 / 1000
        while pendiente >= 1:
            p._avanzar_animacion()
            pendiente -= 1
        self._avance_j[id(p)] = pendiente
        atributos = {k[2:]: v for k, v in datos.items() if k.startswith("a.")}
        panel = atributos.pop("panel", None)
        objetos = atributos.pop("objetos", None)
        E.aplicar(j, atributos)
        # El panel: si cambió de tipo se arma de nuevo; si no, se mezcla (así
        # no se pierden los objetos que el espejo le había puesto).
        if panel is None:
            j.panel = None
        elif not isinstance(j.panel, dict) or j.panel.get("tipo") != panel.get("tipo"):
            j.panel = E.a_python(panel)
        else:
            E._mezclar(j.panel, panel)
            for clave in [k for k in j.panel if k not in panel and not hasattr(j.panel[k], "__dict__")]:
                del j.panel[clave]
        if objetos is not None:
            j.objetos.clear()
            j.objetos.update(objetos)
        j.preso = _Preso() if datos.get("preso") else None
        indice = datos.get("escondite")
        j.escondite = (self.g.escondites[indice] if indice is not None
                       and indice < len(self.g.escondites) else None)
        j.linterna.angulo = pos[2] if pos else datos.get("lin", j.linterna.angulo)
        self._aguja(j)
        arbol = getattr(j, "arbol", None)
        if arbol is not None:
            E.aplicar(arbol, {k[2:]: v for k, v in datos.items() if k.startswith("h.")})

    def _aguja(self, j):
        """La aguja del minijuego del escondite: llega 30 veces por segundo y
        va rápido, así que entre instantánea e instantánea el cliente la sigue
        moviendo él (rebotando igual que en minijuego_latidos.py). Lo que ve el
        jugador es lo que se manda al servidor cuando presiona (cliente.py)."""
        import time
        mj = getattr(j, "minijuego", None)
        if mj is None or not hasattr(mj, "aguja") or getattr(mj, "resultado", None) is not None:
            self._agujas.pop(id(j), None)
            return
        servidor = (mj.aguja, mj.sentido)
        visto = self._agujas.get(id(j))
        ahora = time.perf_counter()
        if visto is None or visto[0] != servidor:
            visto = self._agujas[id(j)] = (servidor, ahora)
        aguja = mj.aguja + mj.sentido * getattr(mj, "velocidad", 0.0) * min(0.12, ahora - visto[1])
        if aguja >= 1:
            mj.aguja, mj.sentido = 2 - aguja, -1
        elif aguja <= 0:
            mj.aguja, mj.sentido = -aguja, 1
        else:
            mj.aguja = aguja

    def _aliens(self, datos, interpolado):
        vistos = []
        for i in range(datos.get("n", 0)):
            pos, resto = datos.get(str(i)), datos.get(f"{i}d")
            if pos is None or resto is None:
                continue
            nombre, _alcance, _medio, otros = resto
            alien = self.aliens.get(nombre)
            if alien is None:
                continue
            x, y, ang = interpolado.get(f"a{i}", pos)
            antes = alien.hitbox.center
            alien.hitbox.center = (round(x), round(y))
            # Su animación va con su reloj propio (tiempo_ms) y `moviendose`,
            # que en el modo local pone alien.actualizar: aquí los pone el espejo.
            alien.tiempo_ms = getattr(alien, "tiempo_ms", 0) + self._dt_ms
            alien.moviendose = alien.hitbox.center != antes
            alien.angulo = ang
            for clave, v in otros.items():
                if clave != "tipo":
                    try:
                        setattr(alien, clave, v)
                    except AttributeError:
                        pass
            vistos.append(alien)
        self.g.aliens = vistos

    def sonar(self, sonidos):
        for nombre, volumen in sonidos or ():
            try:
                self.g.ambiente.sonar(nombre, volumen)
            except Exception:
                pass

    # -- Dibujar ---------------------------------------------------------------------

    def dibujar(self, pantalla, locales):
        """Las vistas de los jugadores `locales` (números de jugador) con el
        dibujo del modo local."""
        g = self.g
        dueños = [g.jugadores[i] for i in locales if i < len(g.jugadores)]
        extras = g._extras_dibujo()
        pantalla_original = g.screen
        g.screen = pantalla
        try:
            g._dibujar_partida_en(pantalla, dueños, extras)
            if g.presentacion is None or not g.presentacion.abierta:
                from screens.logros import render_aviso_logro
                try:
                    render_aviso_logro(pantalla, g.logros)
                except (AttributeError, TypeError, KeyError):
                    pass        # (el aviso de logro es un adorno: que no tumbe el dibujo)
        finally:
            g.screen = pantalla_original

    def dibujar_resultados(self, pantalla):
        """La pantalla de resultados del modo local, con los datos del espejo."""
        from screens.resultados import render_resultados
        g = self.g
        render_resultados(pantalla, g.jugadores, g.font, g.small_font, g.mision, g.equipo,
                          g.infiltrado, g.logros, 0, g.nexus, g.cambiaformas, g.npcs,
                          g.dificultad, g.tiempo_jugado_ms)


def captura_local(juego, locales):
    """Lo que dibuja el modo local para `locales`, sin pasar por la red (para
    comparar en pruebas/prueba_red_capturas.py)."""
    pantalla = pygame.Surface(juego.screen.get_size())
    dueños = [juego.jugadores[i] for i in locales]
    juego._dibujar_partida_en(pantalla, dueños, juego._extras_dibujo())
    return pantalla
