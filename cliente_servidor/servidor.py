"""El servidor de NEXUS: dueño de la partida, sin ventana.

    python -m cliente_servidor.servidor --jugadores 2
    python -m cliente_servidor.servidor --jugadores 4 --host 0.0.0.0      (para otras laptops)
    python -m cliente_servidor.servidor --jugadores 2 --puerto 6000 --dificultad facil --mapa Nave

Escucha (127.0.0.1 por defecto; 0.0.0.0 para la red local), espera a que se
conecten todos (una conexión por jugador) y corre la partida de verdad: el
mismo `Game` de juego/app.py, sin ventana (SDL_VIDEODRIVER=dummy), como lo
hace pruebas/simulador.py. Lo que mandan los clientes se convierte en las
teclas del puesto de cada jugador. También se arranca solo desde el menú del
juego ("Jugar en red", cliente_servidor/lanzador.py).

Hilos:
- el principal arma la partida, espera a los jugadores y corre el juego a
  60 Hz y manda las instantáneas (30 por segundo). Es el ÚNICO que toca `Game`
  y el único que escribe en los sockets de los jugadores ya sentados.
- uno que acepta conexiones durante TODA la partida (para reconectar) y uno
  por saludo que lee el `hola` y le busca puesto.
- uno por conexión que lee las intenciones y las deja en el `Buzon` de ese
  jugador (con un candado: el principal las saca de ahí cada cuadro).

Reconexión: la bienvenida trae un `token` por jugador. Si la conexión se
cae, el cliente vuelve a saludar con ese token y recupera su puesto (el
jugador se queda quieto mientras tanto). El servidor se apaga cuando no queda
nadie conectado durante `--espera` segundos (o con Ctrl+C, o con --segundos).
"""

import argparse
from collections import deque
import os
import random
import secrets
import socket
import sys
import threading
import time

# El servidor nunca abre ventana ni suena: eso es del cliente.
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(RAIZ)            # las imágenes y mapas se buscan desde aquí (como main.py)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from cliente_servidor.protocolo import (VERSION, HOST, PUERTO, HZ_JUEGO, CUADROS_POR_INSTANTANEA,
                                        MANTENER, PULSAR, LectorLineas, ConexionCerrada,
                                        enviar, a_bytes, sin_nagle, CADA_COMPLETA, comprimir)
from cliente_servidor import estado as E

DT_MS = 1000 // HZ_JUEGO      # 16, lo mismo que usa pruebas/simulador.py
# Lo que se manda a cada jugador va por SU hilo de escritura (_escribir), no
# por el del juego. Antes el hilo del juego hacía sendall con timeout de 1 s:
# un cliente lento o un wifi que se traba congelaba la partida de todos
# hasta 1 s, y si se pasaba, lo daba por desconectado a mitad de un mensaje
# (sin cerrarle el socket: se quedaba "conectado" sin recibir nada).
ENVIO_MAX_S = 6.0             # sin poder escribirle en este tiempo: se le cierra
COLA_MAX = 4                  # más atrasado que esto: se tira y va una completa
COMPRIMIR_DESDE = 1200        # bytes: una delta más grande va con zlib

# Lo del Game que el espejo del cliente necesita para dibujar igual que el
# modo local. sección -> atributo de Game. Los objetos se mandan con
# estado.atributos (solo sus datos), las listas elemento por elemento.
OBJETOS = {"m": "mision", "ev": "eventos", "eq": "equipo", "nx": "nexus", "inf": "infiltrado",
           "gp": "guardia_planta", "tut": "tutorial", "nar": "narrador", "lg": "logros",
           "pr": "presentacion", "npc": "npcs", "cf": "cambiaformas"}
LISTAS = {"pz": "piezas", "te": "terminales", "pa": "paneles", "sn": "senuelos", "sl": "senales",
          "pd": "puertas_dobles", "cp": "compuertas", "es": "escondites"}
DEL_JUEGO = ("tiempo_jugado_ms", "tiempo_restante_ms", "oscuridad", "mostrar_arbol_alien",
             "alien_en_vista", "vista_grafo")
# Atributos del Jugador que no se mandan (son de cada lado o no cambian).
JUGADOR_NO = {"puesto", "esquema", "con_mando", "controles_nombre", "spawn", "puede_moverse",
              "velocidad_base", "nombre_personaje"}
ALIEN_SI = ("accion", "alerta", "aturdido", "confundido", "cansado", "moviendose", "oculta",
            "potencia_nexus", "descanso_ms", "comiendo", "disfrazado", "transformando_ms")


class Teclas(dict):
    """Lo que el juego cree que es `pygame.key.get_pressed()`: lo que no está
    es una tecla suelta."""

    def __getitem__(self, tecla):
        return self.get(tecla, False)


class Buzon:
    """Lo último que pidió un jugador. Lo escribe su hilo lector y lo lee el
    hilo del juego, por eso todo pasa con `candado`."""

    def __init__(self):
        self.candado = threading.Lock()
        self.mantener = set()     # acciones mantenidas (estado: la última manda)
        self.pulsar = []          # acciones de una vez (eventos: se acumulan)
        self.ultimo_n = -1        # número de la última intención (para el ack)
        self.conectado = False
        self.quiere_completa = True   # la próxima instantánea a este va entera
        self.aguja = None         # dónde vio la aguja del minijuego al presionar

    def sacar(self):
        with self.candado:
            pulsar, self.pulsar = self.pulsar, []
            return set(self.mantener), pulsar, self.ultimo_n


class Puesto:
    """Un jugador de la partida: su token, su conexión actual (si tiene) y la
    cola de lo que falta mandarle (la vacía su hilo de escritura)."""

    def __init__(self, numero):
        self.numero = numero
        self.token = secrets.token_hex(8)
        self.buzon = Buzon()
        self.sock = None
        self.ocupado = False      # alguna vez se sentó alguien aquí
        self.generacion = 0       # cuántas conexiones ha tenido (la vieja se ignora)
        self.cola = deque()       # bytes por mandar (instantáneas, avisos)
        self.hay = threading.Condition()


class Servidor:
    def __init__(self, jugadores=2, host=HOST, puerto=PUERTO, roles=None,
                 dificultad="normal", mapa=None, segundos=None, avisar=print,
                 presentaciones=True, aliens_quietos=False, espera_s=30.0, semilla=None,
                 fase_final=False):
        self.n = jugadores
        self.host, self.puerto = host, puerto
        self.roles = roles
        self.clave_dificultad = dificultad
        self.mapa = mapa
        self.segundos = segundos
        self.avisar = avisar
        self.presentaciones = presentaciones
        self.aliens_quietos = aliens_quietos
        self.espera_s = espera_s
        self.semilla = random.randrange(1 << 30) if semilla is None else semilla
        self.fase_final = fase_final
        self.sock = None
        self.juego = None
        self.puestos = [Puesto(i) for i in range(jugadores)]
        self.buzones = [p.buzon for p in self.puestos]
        self.candado = threading.Lock()     # para buscar puesto (varios saludos a la vez)
        self.lista = threading.Event()      # la partida ya está armada
        self.teclas = Teclas()
        self.activo = True
        self.cuadro = 0
        self.anterior = None      # la última instantánea completa (para las delta)
        self.sonidos = []         # lo que sonó desde la última instantánea
        self.tamanos = []         # bytes de cada instantánea mandada (para medir)

    # -- Arranque -----------------------------------------------------------------

    def escuchar(self):
        """Abre el puerto. Con puerto 0 el sistema da uno libre (las pruebas)."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if os.name != "nt":
            # Para poder volver a abrir el servidor enseguida en Linux/Mac. En
            # Windows esta opción deja que DOS servidores tomen el mismo puerto.
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.puerto))
        self.sock.listen(8)
        self.puerto = self.sock.getsockname()[1]
        # Esta línea la buscan las pruebas y el lanzador para saber el puerto.
        self.avisar(f"escuchando en {self.host}:{self.puerto} (esperando {self.n} jugadores)")

    def preparar_partida(self):
        """El mismo Game del modo local, pero saltándose los menús: la
        cantidad, la dificultad y los roles vienen de los argumentos."""
        import pygame
        pygame.init()
        from juego import app as App
        from juego import objetos_mapa
        from juego.dificultad import Dificultad
        if self.mapa:
            objetos_mapa.mapa_activo = lambda: self.mapa
        g = App.Game()
        if self.clave_dificultad:
            g.dificultad = Dificultad(self.clave_dificultad)
        nombres = [r["nombre"] for r in App.ROLES]
        roles = list(self.roles or nombres[:self.n])
        if len(roles) != self.n or any(r not in nombres for r in roles) or len(set(roles)) != len(roles):
            raise SystemExit(f"--roles necesita {self.n} roles distintos de: {', '.join(nombres)}")
        self.roles = roles
        g.cantidad_jugadores = self.n
        g.abrir_seleccion_roles(ir=False)
        for estado, rol in zip(g.seleccion_roles, roles):
            estado["rol"], estado["listo"] = rol, True
        # La misma semilla que usa el espejo del cliente: así los dos arman
        # casi la misma partida (lo que no, lo corrigen las instantáneas).
        random.seed(self.semilla)
        g._preparar_partida()
        g.current_screen = "partida"
        # El tutorial se maneja con los paneles del modo local: en red se
        # salta y los aliens despiertan de una.
        g.saltar_tutorial()
        if not self.presentaciones:
            g.presentacion = None
        if self.aliens_quietos:
            for alien in g.aliens:          # como en pruebas/prueba_partida.py
                alien.descanso_ms = 10 ** 9
        for jugador in g.jugadores:
            # En local los puestos 3 y 4 solo caminan con mando; aquí su
            # entrada viene del socket.
            jugador.puede_moverse = True
        if self.fase_final:
            forzar_fase_final(g)
        # El gancho de la entrada: el juego pregunta las teclas con
        # self.mandos.envolver(pygame.key.get_pressed()). Cambiando `envolver`
        # en ESTA instancia, lo que lee son las teclas que armó el servidor
        # con lo que mandaron los clientes (no hay que tocar app.py).
        g.mandos.envolver = lambda _teclado_real: self.teclas
        # Los sonidos se oyen en los clientes: se anotan y viajan en la instantánea.
        sonar = g.ambiente.sonar

        def anotar(nombre, volumen=1.0, *resto, **otros):
            self.sonidos.append([nombre, round(float(volumen), 2)])
            return sonar(nombre, volumen, *resto, **otros)
        g.ambiente.sonar = anotar
        self.juego = g
        self.avisar(f"partida lista: mapa {g.mundo.nombre_mapa}, roles {roles}")

    def bienvenida(self, puesto):
        g = self.juego
        return {"tipo": "bienvenida", "jugador": puesto.numero, "jugadores": self.n,
                "token": puesto.token, "roles": [j.rol for j in g.jugadores],
                "dificultad": g.dificultad.clave if g.dificultad is not None else None,
                "semilla": self.semilla, "presentaciones": self.presentaciones,
                "mapa": g.mundo.nombre_mapa, "ancho": g.mundo.ancho,
                "alto": g.mundo.alto, "escala": g.mundo.escala,
                "hz": HZ_JUEGO // CUADROS_POR_INSTANTANEA}

    # -- Conexiones (hilos) --------------------------------------------------------

    def _aceptar_siempre(self):
        """Acepta conexiones mientras dure el servidor: las primeras y las que
        vuelven después de un corte."""
        self.sock.settimeout(0.5)
        while self.activo:
            try:
                s, direccion = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            threading.Thread(target=self._saludar, args=(s, direccion), daemon=True).start()

    def _saludar(self, s, direccion):
        """Lee el `hola` y le busca puesto: el suyo si trae token, uno libre si
        no. Si no hay, `error` (partida llena)."""
        sin_nagle(s)
        s.settimeout(5.0)
        lector = LectorLineas(s)
        try:
            hola = lector.siguiente()
            if hola.get("tipo") != "hola" or hola.get("version") != VERSION:
                self._echar(s, f"se esperaba hola versión {VERSION}")
                return
            # La bienvenida necesita la partida armada (los roles, el mapa).
            while not self.lista.wait(0.5):
                if not self.activo:
                    s.close()
                    return
            with self.candado:
                token = hola.get("token")
                puesto = next((p for p in self.puestos if token and p.token == token), None)
                if token and puesto is None:
                    self._echar(s, "ese token no es de esta partida")
                    return
                if puesto is None:
                    puesto = next((p for p in self.puestos if not p.ocupado), None)
                if puesto is None:
                    self._echar(s, f"la partida ya tiene sus {self.n} jugadores")
                    return
                vuelve = puesto.ocupado
                puesto.ocupado = True
                viejo, puesto.sock = puesto.sock, None
            if viejo is not None:             # (la conexión vieja todavía no se había caído)
                _cerrar(viejo)
            enviar(s, self.bienvenida(puesto))
            # Con timeout el hilo lector puede despertar a ver si se apagó el
            # servidor, y un cliente que no lee no traba al juego para siempre.
            s.settimeout(1.0)
            with puesto.buzon.candado:
                puesto.generacion += 1
                generacion = puesto.generacion
                puesto.buzon.conectado = True
                puesto.buzon.quiere_completa = True
                puesto.buzon.mantener = set()
            with puesto.hay:
                puesto.cola.clear()           # (lo de la conexión anterior ya no sirve)
            puesto.sock = s
            threading.Thread(target=self._leer, args=(lector, puesto, generacion), daemon=True,
                             name=f"lector-J{puesto.numero + 1}").start()
            threading.Thread(target=self._escribir, args=(s, puesto, generacion), daemon=True,
                             name=f"escritor-J{puesto.numero + 1}").start()
            self.avisar(f"J{puesto.numero + 1} {'reconectado' if vuelve else 'conectado'} desde "
                        f"{direccion[0]}:{direccion[1]} ({hola.get('nombre', '')})")
        except (OSError, ConexionCerrada):
            s.close()

    @staticmethod
    def _echar(s, texto):
        try:
            enviar(s, {"tipo": "error", "texto": texto})
            s.shutdown(socket.SHUT_WR)
        except OSError:
            pass
        s.close()

    def _leer(self, lector, puesto, generacion):
        buzon = puesto.buzon
        try:
            while self.activo and puesto.generacion == generacion:
                try:
                    mensaje = lector.siguiente()
                except socket.timeout:
                    continue
                tipo = mensaje.get("tipo")
                if tipo == "intencion":
                    mantener = {a for a in mensaje.get("mantener", ()) if a in MANTENER}
                    pulsar = [a for a in mensaje.get("pulsar", ()) if a in PULSAR]
                    with buzon.candado:
                        buzon.mantener = mantener
                        if "interactuar" in pulsar and isinstance(mensaje.get("aguja"), (int, float)):
                            buzon.aguja = max(0.0, min(1.0, float(mensaje["aguja"])))
                        buzon.pulsar.extend(pulsar[:16])
                        del buzon.pulsar[:-32]      # que nadie llene la cola
                        if isinstance(mensaje.get("n"), int):
                            buzon.ultimo_n = mensaje["n"]
                elif tipo == "completa":
                    # Al cliente le faltó una instantánea (o llegó tarde): la
                    # siguiente se le manda entera.
                    with buzon.candado:
                        buzon.quiere_completa = True
                elif tipo == "adios":
                    break
        except (OSError, ConexionCerrada):
            pass
        with buzon.candado:
            if puesto.generacion == generacion:
                buzon.conectado = False
                buzon.mantener = set()

    def _escribir(self, s, puesto, generacion):
        """El hilo que le manda a UN jugador lo que hay en su cola. Si no se le
        puede escribir en ENVIO_MAX_S, se le cierra el socket: su cliente se da
        cuenta y vuelve con su token (reconexión)."""
        while True:
            with puesto.hay:
                while not puesto.cola and puesto.generacion == generacion and self.activo:
                    puesto.hay.wait(0.5)
                if puesto.generacion != generacion or not puesto.cola:
                    return
                datos = puesto.cola.popleft()
            if not _mandar_todo(s, datos, ENVIO_MAX_S):
                with puesto.buzon.candado:
                    if puesto.generacion == generacion:
                        puesto.buzon.conectado = False
                        puesto.buzon.mantener = set()
                self.avisar(f"J{puesto.numero + 1}: no se le pudo mandar nada en "
                            f"{ENVIO_MAX_S:.0f} s; se cierra para que reconecte")
                _cerrar(s)
                return

    def _esperar_jugadores(self):
        while self.activo and not all(p.ocupado and p.buzon.conectado for p in self.puestos):
            conectados = sum(p.buzon.conectado for p in self.puestos)
            self._a_todos({"tipo": "espera", "conectados": conectados, "faltan": self.n - conectados})
            time.sleep(0.25)

    # -- El juego ---------------------------------------------------------------------

    def bucle(self):
        """60 cuadros por segundo con paso fijo; instantánea cada 2."""
        paso = 1.0 / HZ_JUEGO
        siguiente = time.perf_counter()
        inicio = siguiente
        fin_avisado = False
        solo_desde = None         # desde cuándo no hay nadie conectado
        while self.activo:
            acks = self._aplicar_entradas()
            g = self.juego
            if g.mision.resultado is None and g.current_screen == "partida":
                g._actualizar_partida(DT_MS)
            elif not fin_avisado:
                fin_avisado = True
                self.avisar(f"partida terminada: {g.mision.resultado}")
            self.cuadro += 1
            if self.cuadro % CUADROS_POR_INSTANTANEA == 0:
                self._mandar_instantanea(acks)
            if any(b.conectado for b in self.buzones):
                solo_desde = None
            elif solo_desde is None:
                solo_desde = time.perf_counter()
                self.avisar(f"no queda nadie conectado (espero {self.espera_s:.0f} s)")
            elif time.perf_counter() - solo_desde > self.espera_s:
                self.avisar("se desconectaron todos")
                break
            if self.segundos is not None and time.perf_counter() - inicio > self.segundos:
                self.avisar(f"pasaron {self.segundos} s (--segundos)")
                break
            siguiente += paso
            espera = siguiente - time.perf_counter()
            if espera > 0:
                time.sleep(espera)
            elif espera < -0.25:
                siguiente = time.perf_counter()   # se atrasó mucho: no intenta recuperar

    def _aplicar_entradas(self):
        """Lo que mandaron los clientes -> las teclas de cada puesto."""
        g = self.juego
        teclas = Teclas()
        pulsados, acks = [], []
        for jugador, buzon in zip(g.jugadores, self.buzones):
            mantener, pulsar, ultimo_n = buzon.sacar()
            acks.append(ultimo_n)
            for accion in mantener:
                for tecla in jugador.teclas.get(accion, ()):
                    teclas[tecla] = True
                for tecla in jugador.personaje.controles.get(accion, ()):
                    teclas[tecla] = True
            with buzon.candado:
                aguja, buzon.aguja = buzon.aguja, None
            pulsados.append((jugador, pulsar, aguja))
        self.teclas = teclas
        # Lo pulsado va antes de actualizar, como en el modo local (primero
        # los eventos y después _actualizar_partida).
        for jugador, pulsar, aguja in pulsados:
            for accion in pulsar:
                if accion == "interactuar" and aguja is not None and getattr(jugador, "minijuego", None) is not None:
                    # El acierto se juzga con la aguja que vio el jugador (ver
                    # cliente.Sesion._extra), no con la de este cuadro.
                    jugador.minijuego.aguja = aguja
                self._pulsar(jugador, accion)
        return acks

    def _pulsar(self, jugador, accion):
        """Una acción de una vez = el KEYDOWN de la tecla de ese jugador."""
        g = self.juego
        if g.mision.resultado is not None:
            return
        if g.presentacion is not None and g.presentacion.abierta:
            # La ventana que presenta un alien se cierra como con el mando.
            if accion in ("interactuar", "habilidad", "volver"):
                g.presentacion.cerrar()
            return
        if accion == "volver":
            # Lo mismo que el botón B del mando (Game._tecla_mando).
            if jugador.ocupado:
                if jugador.panel.get("tipo") == "celular":
                    from redes import celular
                    celular.volver(g, jugador)
                else:
                    jugador.cerrar_panel()
                return
            accion = "soltar"
        teclas = jugador.teclas.get(accion, ())
        if teclas:
            g._tecla_en_partida(teclas[0])

    # -- Instantáneas -----------------------------------------------------------------

    def instantanea(self, acks=None):
        """La instantánea COMPLETA: {sección: {clave: valor}}. Lo que viaja
        casi siempre es solo lo que cambió (`_mandar_instantanea`)."""
        g = self.juego
        m = g.mision
        secciones = {"g": {
            "t": g.tiempo_jugado_ms, "fase": m.fase, "objetivo": m.objetivo() if m.activa else "",
            "resultado": m.resultado, "entregadas": m.piezas_entregadas,
            "apagon": bool(g.eventos is not None and g.eventos.apagon),
            "capsula": list(m.capsula) if m.capsula is not None else None,
            "piezas": [list(p["rect"].center) for p in g.piezas if not p.get("recogida")],
            "puntos": g.equipo.total, "presentacion": _presentacion(g),
            **{"G." + k: E.extraer(getattr(g, k, None)) for k in DEL_JUEGO},
        }}
        for i, j in enumerate(g.jugadores):
            secciones[f"j{i}"] = self._jugador(i, j)
        # Por alien dos claves: "3" = [x, y, ángulo] (cambia todo el tiempo) y
        # "3d" = lo demás (casi nunca cambia). En la delta va solo lo que cambió.
        secciones["al"] = {}
        for i, a in enumerate(g.aliens):
            secciones["al"][str(i)], secciones["al"][f"{i}d"] = self._alien(a)
        secciones["al"]["n"] = len(g.aliens)
        for clave, nombre in OBJETOS.items():
            objeto = getattr(g, nombre, None)
            secciones[clave] = {} if objeto is None else {"ok": True, **E.atributos(objeto)}
        for clave, nombre in LISTAS.items():
            lista = getattr(g, nombre, None) or []
            secciones[clave] = {str(i): (E.atributos(o) if hasattr(o, "__dict__") else E.extraer(o))
                                for i, o in enumerate(lista)}
            secciones[clave]["n"] = len(lista)
        secciones["pubs"] = _publicaciones(g)
        return secciones

    def _jugador(self, i, j):
        p = j.personaje
        buzon = self.buzones[i] if i < len(self.buzones) else None
        datos = {
            # Lo "legible" (lo usa el dibujo sencillo y las pruebas).
            "n": i, "rol": j.rol,
            "x": round(p.x, 1), "y": round(p.y, 1),            # esquina del sprite
            "hx": j.hitbox.centerx, "hy": j.hitbox.centery,     # centro de la hitbox
            "dir": p.direccion, "mov": bool(p.moviendose),
            "vidas": j.vidas, "vmax": j.vidas_max, "infinitas": j.vidas_infinitas,
            "preso": j.preso is not None, "elim": j.eliminado, "esc": j.escondido,
            "sig": j.sigilo, "pulso": round(j.pulso), "puntos": j.puntos,
            "piezas": j.piezas, "objetos": dict(j.objetos),
            "sala": j.sala or "", "msg": j.mensaje if j.mensaje_ms > 0 else "",
            "pista": j.pista_mision or "",
            "prog": [j.progreso[0], round(j.progreso[1], 2)] if j.progreso else None,
            "panel": _panel(j),
            "on": buzon.conectado if buzon else False,
            # Lo del espejo: los atributos del Jugador, la linterna y el árbol.
            "lin": round(j.linterna.angulo, 2),
            "escondite": (self.juego.escondites.index(j.escondite)
                          if j.escondite in self.juego.escondites else None),
        }
        for clave, v in E.atributos(j, JUGADOR_NO).items():
            datos["a." + clave] = v
        arbol = getattr(j, "arbol", None)
        if arbol is not None and hasattr(arbol, "__dict__"):
            for clave, v in E.atributos(arbol).items():
                datos["h." + clave] = v
        return datos

    @staticmethod
    def _alien(a):
        """Un alien en dos listas cortas: [x, y, ángulo] y [nombre, alcance,
        medio ángulo, {lo demás}]."""
        return ([round(a.centro[0]), round(a.centro[1]), round(a.angulo, 2)],
                [a.nombre, round(a.alcance_vision), round(a.datos.get("medio_angulo", 0), 2),
                 {k: E.extraer(getattr(a, k)) for k in ALIEN_SI if hasattr(a, k)}])

    def _mandar_instantanea(self, acks):
        """La completa al que la necesita (recién llegado, reconectado o que
        perdió una) y a los demás solo lo que cambió desde la anterior."""
        ahora = self.instantanea(acks)
        cabeza = {"tipo": "estado", "c": self.cuadro, "ack": acks or [], "snd": self.sonidos}
        self.sonidos = []
        # La completa pesa ~30 KB (los escondites, las notas...): va comprimida.
        completa = dict(cabeza, base=None, z=comprimir(ahora))
        if self.anterior is None or self.cuadro % CADA_COMPLETA == 0:
            delta = completa
        else:
            cambios = {}
            for seccion, datos in ahora.items():
                d = E.diferencias(self.anterior.get(seccion, {}), datos)
                if d:
                    cambios[seccion] = d
            delta = dict(cabeza, base=self.cuadro_anterior, s=cambios)
            if len(a_bytes(cambios)) > COMPRIMIR_DESDE:
                # (con muchos NPC caminando la delta pasa de 4 KB; comprimida, ~1,5)
                delta = dict(cabeza, base=self.cuadro_anterior, z=comprimir(cambios))
        self.anterior, self.cuadro_anterior = ahora, self.cuadro
        bytes_delta, bytes_completa = a_bytes(delta), None
        for puesto in self.puestos:
            buzon = puesto.buzon
            if not buzon.conectado or puesto.sock is None:
                continue
            with buzon.candado:
                entera, buzon.quiere_completa = buzon.quiere_completa, False
            with puesto.hay:
                if len(puesto.cola) >= COLA_MAX:
                    # Va atrasado (wifi lento): lo viejo ya no sirve, mejor
                    # una completa al día que una fila de deltas.
                    puesto.cola.clear()
                    entera = True
            if entera and bytes_completa is None:
                bytes_completa = a_bytes(completa)
            datos = bytes_completa if entera else bytes_delta
            self.tamanos.append((len(datos), entera))
            del self.tamanos[:-2000]
            self._mandar(puesto, datos)

    def _mandar(self, puesto, datos):
        """A la cola del jugador (no bloquea al juego: ver _escribir)."""
        with puesto.hay:
            puesto.cola.append(datos)
            puesto.hay.notify()

    def _a_todos(self, mensaje):
        datos = a_bytes(mensaje)
        for puesto in self.puestos:
            if puesto.buzon.conectado and puesto.sock is not None:
                self._mandar(puesto, datos)

    # -- Todo junto ---------------------------------------------------------------------

    def correr(self):
        try:
            if self.sock is None:
                self.escuchar()
            # Se escucha ANTES de armar la partida (tarda unos segundos): los
            # clientes que llegan mientras tanto esperan su bienvenida.
            threading.Thread(target=self._aceptar_siempre, daemon=True, name="aceptar").start()
            self.preparar_partida()
            self.lista.set()
            self._esperar_jugadores()
            if self.activo:
                self.avisar("empieza la partida")
                self.bucle()
        except KeyboardInterrupt:
            self.avisar("Ctrl+C")
        finally:
            self.cerrar()

    def cerrar(self, texto="El servidor se cerró."):
        """Avisa a todos (`fin`) y cierra: los clientes vuelven al menú."""
        if self.tamanos:
            delta = [b for b, entera in self.tamanos if not entera] or [0]
            entera = [b for b, e in self.tamanos if e] or [0]
            self.avisar(f"instantáneas: delta media {sum(delta) / len(delta):.0f} B, máx {max(delta)} B; "
                        f"completa media {sum(entera) / len(entera):.0f} B, máx {max(entera)} B")
        self._a_todos({"tipo": "fin", "texto": texto})
        limite = time.time() + 1.0          # que alcance a salir el `fin`
        while time.time() < limite and any(p.cola for p in self.puestos if p.buzon.conectado):
            time.sleep(0.02)
        self.activo = False
        for puesto in self.puestos:
            with puesto.hay:
                puesto.hay.notify_all()
        for puesto in self.puestos:
            if puesto.sock is not None:
                _cerrar(puesto.sock)
        if self.sock is not None:
            self.sock.close()


def _mandar_todo(s, datos, plazo_s):
    """Como sendall, pero sin cortar un mensaje a la mitad por el timeout del
    socket (es de 1 s, para el lector): `send` con timeout no manda nada o
    manda un pedazo, y se sigue desde ahí hasta `plazo_s`. False si no se pudo."""
    vista = memoryview(datos)
    limite = time.time() + plazo_s
    while vista:
        try:
            enviados = s.send(vista)
        except socket.timeout:
            if time.time() > limite:
                return False
            continue
        except OSError:
            return False
        vista = vista[enviados:]
    return True


def _cerrar(s):
    try:
        s.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    s.close()


def forzar_fase_final(g):
    """Un atajo para las pruebas (como pruebas/simulador.py): la misión ya en
    la huida y todos junto a la cápsula, así la partida se gana en el primer
    cuadro y la prueba ve el final completo en pocos segundos."""
    m = g.mision
    if not m.activa or m.capsula is None:
        return
    m.fase = "huida"
    for k, j in enumerate(g.jugadores):
        j.personaje.hitbox.center = (m.capsula.centerx - 20 + 14 * k, m.capsula.bottom + 20)
        j.personaje.sync_sprite_from_hitbox()


def _publicaciones(g):
    """Las publicaciones de NEXUS (el celular), una por clave (su id): en las
    demás secciones viajan como referencia {"P": id} (estado.REFERENCIAS) y el
    espejo las arma con esto. Antes el celular del cliente se quedaba con las
    del principio: lo que se publicaba en la partida no le llegaba. `edad_ms`
    va redondeada al segundo; si no, todas cambiarían en cada instantánea."""
    red = getattr(g, "nexus", None)
    if red is None:
        return {}
    salida = {}
    for pub in red.publicaciones:
        datos = E.atributos(pub)
        if isinstance(datos.get("edad_ms"), (int, float)):
            datos["edad_ms"] = int(datos["edad_ms"]) // 1000 * 1000
        salida[str(pub.id)] = datos
    salida["orden"] = [pub.id for pub in red.publicaciones]
    return salida


def _presentacion(g):
    """La ventana que presenta un alien nuevo (pausa a todos hasta que alguien
    la cierre con interactuar o habilidad)."""
    p = g.presentacion
    if p is None or not p.abierta:
        return None
    titulo, lineas = p.textos()
    alien = p.actual["alien"]
    return {"titulo": titulo, "lineas": lineas, "jugador": g.jugadores.index(p.actual["jugador"]),
            "x": alien.centro[0], "y": alien.centro[1], "tipo": p.actual["tipo"],
            "alien": getattr(alien, "nombre", None), "ms": p.actual.get("ms", 0)}


def _panel(jugador):
    """El panel abierto, en texto: título, cuerpo, opciones y cursor."""
    p = jugador.panel
    if p is None:
        return None

    def texto(x):
        # Las opciones son de varias formas: {"texto": ...}, ("Volver", "volver"),
        # ("post", Publicacion) en el celular...
        if isinstance(x, (tuple, list)):
            con_texto = next((e for e in x if hasattr(e, "texto")), None)
            x = con_texto if con_texto is not None else next((e for e in x if isinstance(e, str)), "")
        if isinstance(x, dict):
            x = x.get("texto") or x.get("titulo") or x.get("nombre") or ""
        elif hasattr(x, "texto"):
            x = x.texto
        return str(x)[:90]

    cuerpo = p.get("cuerpo") or []
    if isinstance(cuerpo, str):
        cuerpo = [cuerpo]
    titulo = p.get("titulo") or (f"NEXUS · {p.get('pestana', '')}" if p.get("tipo") == "celular"
                                 else p.get("tipo") or "")
    return {"tipo": p.get("tipo"), "titulo": texto(titulo),
            "cuerpo": [texto(c) for c in cuerpo if isinstance(c, (str, dict))][:8],
            "opciones": [texto(o) for o in (p.get("opciones") or [])][:12],
            "cursor": jugador.cursor, "pie": texto(p.get("pie") or "")}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Servidor de NEXUS (una conexión por jugador).")
    ap.add_argument("--jugadores", type=int, default=2, choices=(2, 3, 4))
    ap.add_argument("--host", default=HOST, help="127.0.0.1 (por defecto); 0.0.0.0 para la red local")
    ap.add_argument("--puerto", type=int, default=PUERTO, help="0 = uno libre")
    ap.add_argument("--roles", default=None,
                    help="separados por coma, p. ej. Tecnomante,Forjador (por defecto, en orden)")
    ap.add_argument("--dificultad", default="normal",
                    choices=("facil", "normal", "dificil", "inteligente"))
    ap.add_argument("--mapa", default=None, help="por defecto el de Hitboxes/mapa_activo.json")
    ap.add_argument("--segundos", type=float, default=None, help="apagarse solo después de esto")
    ap.add_argument("--sin-presentaciones", action="store_true",
                    help="no pausar la primera vez que se ve cada alien")
    ap.add_argument("--aliens-quietos", action="store_true",
                    help="los aliens no se mueven (para pruebas y para mostrar la red)")
    ap.add_argument("--espera", type=float, default=30.0,
                    help="segundos sin nadie conectado antes de apagarse (para reconectar)")
    ap.add_argument("--semilla", type=int, default=None)
    ap.add_argument("--fase-final", action="store_true",
                    help="empezar en la cápsula con 2 piezas entregadas (pruebas)")
    args = ap.parse_args(argv)
    roles = [r.strip() for r in args.roles.split(",")] if args.roles else None
    Servidor(args.jugadores, args.host, args.puerto, roles, args.dificultad, args.mapa,
             args.segundos, avisar=lambda texto: print("[servidor]", texto, flush=True),
             presentaciones=not args.sin_presentaciones, aliens_quietos=args.aliens_quietos,
             espera_s=args.espera, semilla=args.semilla, fase_final=args.fase_final).correr()


if __name__ == "__main__":
    main()
