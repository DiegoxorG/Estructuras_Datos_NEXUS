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

Con --elegir-roles (lo pone el menú del juego) hay una SALA antes de armar
la nave: el servidor da la bienvenida apenas llega cada uno, cada jugador
elige su rol desde su laptop (mensajes `rol`) y el estado de la elección
viaja en mensajes `sala` (dos veces por segundo y cada vez que alguien
cambia algo). Cuando todos están y eligieron, se arma la nave con esos roles
y la `sala` trae los datos de la partida (`partida`) para armar el espejo.

Reconexión: la bienvenida trae un `token` por jugador. Si la conexión se
cae, el cliente vuelve a saludar con ese token y recupera su puesto (el
jugador se queda quieto mientras tanto). El servidor se apaga cuando no queda
nadie conectado durante `--espera` segundos (o con Ctrl+C, o con --segundos).
"""

import argparse
import faulthandler
from collections import deque
import os
import random
import secrets
import signal
import socket
import sys
import threading
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)


def _sin_ventana():
    """El servidor nunca abre ventana ni suena: eso es del cliente.

    Antes esto se hacía al IMPORTAR el módulo, y el espejo del cliente lo
    importa (OBJETOS, LISTAS): después de una partida en red, el juego de la
    laptop quedaba con SDL_VIDEODRIVER=dummy en su entorno y el modo local se
    portaba como en las pruebas (sin pantalla de carga y sin guardar el
    historial de logros: juego/app.py y juego/historial_logros.py lo miran).
    Ahora solo lo hace el proceso del servidor (main) o un Servidor de prueba
    al armar la partida."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    # SDL se queda con SIGTERM (y con SIGINT si nadie lo tenía) para
    # convertirlos en un evento QUIT... que el servidor nunca lee: un
    # `terminate()` no lo apagaba y quedaba huérfano con el puerto tomado.
    os.environ.setdefault("SDL_NO_SIGNAL_HANDLERS", "1")

from cliente_servidor.protocolo import (VERSION, HOST, PUERTO, HZ_JUEGO, CUADROS_POR_INSTANTANEA,
                                        MANTENER, PULSAR, LectorLineas, ConexionCerrada,
                                        enviar, a_bytes, sin_nagle, CADA_COMPLETA, comprimir,
                                        comprimir_bytes)
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
# Lo que puede guardar el sistema para mandarle a un jugador. Por defecto
# Windows y Linux guardan cientos de KB: con el wifi trabado se llenaba de
# instantáneas viejas y, al volver, el cliente las recibía todas, atrasado
# (se sentía "lageado" un rato). Con 64 KB (~1 s de instantáneas) lo que no
# cabe se queda en la cola de arriba, que tira lo viejo y manda una completa.
BUFER_ENVIO = 64 * 1024
# El cliente manda su intención cada 100 ms y un `latido` si no tiene nada
# que mandar (cliente.Conexion._escribir). Sin noticias de un jugador:
SUELTA_TECLAS_S = 0.75        # ... en este tiempo se le sueltan las teclas: si
                              # no, con el wifi cortado seguía caminando con
                              # la última tecla hasta chocar con una pared
SILENCIO_S = 5.0              # ... en este, se da por caído y se le cierra el
                              # socket (antes seguía "conectado" para siempre
                              # si el wifi se iba sin cerrar la conexión)
INFORME_CADA_S = 60.0         # cada cuánto escribe en la consola cómo va (rendimiento)

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
# `puede_moverse` SÍ se manda: en el espejo J3 y J4 se arman "sin mando"
# (quietos) y el dibujo no les ponía el anillo de ruido; y al eliminar a
# alguien pasa a False. Lo que tiene cerca (zona, escondite, estación) va como
# índice ("zc", "ecc", "stc"): el dibujo pregunta `zona_cerca is zona` y una
# copia del dict nunca era la zona del espejo (no se resaltaba la Terminal
# NEXUS, el casillero ni la terminal de al lado). `escondite` ya iba como índice.
# `teclas` y `tipo_mando` tampoco: son los de la laptop de cada quien (los
# pone Espejo.controles); el servidor los tiene por puesto (J1 = WASD) y
# pisaban las pistas: J1 con flechas veía "[Q] escoge tu habilidad".
JUGADOR_NO = {"puesto", "esquema", "con_mando", "controles_nombre", "spawn", "teclas", "tipo_mando",
              "velocidad_base", "nombre_personaje",
              "zona_cerca", "escondite_cerca", "estacion_cerca", "escondite"}
# `oculta` de la Sombra es una propiedad (oculta_ms > 0) y `distraido` del
# Guardia también (distraido_ms > 0): sin sus ms el espejo dibujaba a la Sombra
# esfumada y al Guardia distraído como si nada. `ajuste_vision` lo pone el
# director de la dificultad y cambia el largo del cono.
ALIEN_SI = ("accion", "alerta", "aturdido", "confundido", "cansado", "moviendose", "oculta",
            "potencia_nexus", "descanso_ms", "comiendo", "disfrazado", "transformando_ms",
            "oculta_ms", "distraido_ms", "ajuste_vision")


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
        self.vista = None         # (ancho, alto) de su vista en su laptop
        self.ultimo_rx = 0.0      # perf_counter del último mensaje (cualquiera)
        self.ultima_intencion = 0.0   # ... y de la última intención

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
        self.escritor = None      # el hilo de escritura de la conexión actual
        self.ip = None            # de dónde se conectó la última vez


class Servidor:
    def __init__(self, jugadores=2, host=HOST, puerto=PUERTO, roles=None,
                 dificultad="normal", mapa=None, segundos=None, avisar=print,
                 presentaciones=True, aliens_quietos=False, espera_s=30.0, semilla=None,
                 fase_final=False, tutorial=False, elegir_roles=False):
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
        self.tutorial = tutorial
        # La sala de antes de armar la nave (ver el docstring del módulo).
        # Con --roles (las pruebas) no hay nada que elegir.
        self.elegir_roles = elegir_roles and not roles
        self.fase_sala = "roles" if self.elegir_roles else "lista"
        self.seleccion = []                 # [{cursor, listo, rol}] por puesto
        self.candado_sala = threading.Lock()
        self.en_bucle_desde = None          # cuándo empezó el juego (fin de la sala)
        self.sock = None
        self.juego = None
        self.puestos = [Puesto(i) for i in range(jugadores)]
        self.buzones = [p.buzon for p in self.puestos]
        self.candado = threading.Lock()     # para buscar puesto (varios saludos a la vez)
        self.lista = threading.Event()      # la partida ya está armada
        self.teclas = Teclas()
        self.activo = True
        # Ya se mandó `fin`: los hilos de escritura vacían su cola, cierran
        # su lado (SHUT_WR) y terminan; no se aceptan saludos nuevos.
        self.terminando = False
        # Alguien pidió apagar desde otro hilo (el padre cerró la entrada:
        # ver vigilar_padre). El hilo principal lo mira en cada cuadro.
        self.parar = threading.Event()
        self._cerrado = False
        self.cuadro = 0
        self.anterior = None      # la última instantánea completa (para las delta)
        self.sonidos = []         # lo que sonó desde la última instantánea
        self.tamanos = []         # bytes de cada instantánea mandada (para medir)
        self.cierre = self.parar            # (el mismo aviso: lanzador, SIGTERM, el padre)
        # Para saber si el servidor anda bien en la feria: cuadros por segundo
        # de verdad, el peor cuadro y lo que tarda la instantánea.
        self.medidas = {"inicio": None, "cuadros": 0, "peor_ms": 0.0, "inst_ms": 0.0, "inst_n": 0,
                        "tarde": 0}

    # -- Arranque -----------------------------------------------------------------

    con_padre = False

    def escuchar(self):
        """Abre el puerto. Con puerto 0 el sistema da uno libre (las pruebas)."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if os.name != "nt":
            # Para poder volver a abrir el servidor enseguida en Linux/Mac. En
            # Windows esta opción deja que DOS servidores tomen el mismo puerto.
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        elif hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            # En Windows, sin esto otro programa (u otro servidor en
            # 127.0.0.1) puede tomar el MISMO puerto encima del nuestro y
            # quedarse con las conexiones de esta laptop.
            try:
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            except OSError:
                pass
        self.sock.bind((self.host, self.puerto))
        self.sock.listen(8)
        self.puerto = self.sock.getsockname()[1]
        # Esta línea la buscan las pruebas y el lanzador para saber el puerto.
        self.avisar(f"escuchando en {self.host}:{self.puerto} (esperando {self.n} jugadores)")

    def preparar_partida(self):
        """El mismo Game del modo local, pero saltándose los menús: la
        cantidad, la dificultad y los roles vienen de los argumentos."""
        _sin_ventana()
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
        with todos_se_mueven():
            g._preparar_partida()
        g.current_screen = "partida"
        # El tutorial del principio (juego/tutorial.py) también en red: cada
        # quien pasa sus pasos con su tecla de habilidad y la nave arranca
        # cuando todos terminaron. Con tutorial=False (las pruebas) se salta.
        if not self.tutorial:
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
        # Las vistas de cada jugador son las de SU laptop (las manda su
        # cliente con cada intención): con eso decide la partida si un alien ya
        # entró en su pantalla (la ventana que lo presenta). Antes usaba la
        # pantalla falsa del servidor, partida entre todos: un alien se veía
        # en la laptop un buen rato antes de que saliera su ventana.
        vista_local = g.vista_de

        def vista_de(jugador):
            i = g.jugadores.index(jugador) if jugador in g.jugadores else -1
            tam = self.buzones[i].vista if 0 <= i < len(self.buzones) else None
            if tam is None:
                return vista_local(jugador)
            import pygame
            return pygame.Rect(0, 0, *tam)
        g.vista_de = vista_de
        # Los sonidos se oyen en los clientes: se anotan y viajan en la instantánea.
        sonar = g.ambiente.sonar

        def anotar(nombre, volumen=1.0, *resto, **otros):
            self.sonidos.append([nombre, round(float(volumen), 2)])
            return sonar(nombre, volumen, *resto, **otros)
        g.ambiente.sonar = anotar
        self.juego = g
        self.avisar(f"partida lista: mapa {g.mundo.nombre_mapa}, roles {roles}")

    def bienvenida(self, puesto):
        """Su número y su token; con la nave ya armada, también lo que el
        cliente necesita para armar su espejo (datos_partida). En la sala
        todavía no hay nave: eso llega después en la `sala`."""
        mensaje = {"tipo": "bienvenida", "jugador": puesto.numero, "jugadores": self.n,
                   "token": puesto.token, "dificultad": self.clave_dificultad}
        if self.lista.is_set():
            mensaje.update(self.datos_partida())
        else:
            mensaje["sala"] = True
        return mensaje

    def datos_partida(self):
        g = self.juego
        return {"roles": [j.rol for j in g.jugadores],
                "dificultad": g.dificultad.clave if g.dificultad is not None else None,
                "semilla": self.semilla, "presentaciones": self.presentaciones,
                "mapa": g.mundo.nombre_mapa, "ancho": g.mundo.ancho,
                "alto": g.mundo.alto, "escala": g.mundo.escala,
                "hz": HZ_JUEGO // CUADROS_POR_INSTANTANEA}

    # -- La sala: cada uno elige su rol ----------------------------------------------

    def estado_sala(self):
        with self.candado_sala:
            seleccion = [dict(e) for e in self.seleccion]
        mensaje = {"tipo": "sala", "fase": self.fase_sala, "roles": seleccion,
                   "conectados": [bool(p.buzon.conectado) for p in self.puestos]}
        if self.lista.is_set():
            mensaje["partida"] = self.datos_partida()
        return mensaje

    def _mandar_sala(self):
        self._a_todos(self.estado_sala())

    def _rol(self, puesto, mensaje):
        """Un `rol` de un cliente: {"mover": -1/1} o {"ok": true} (confirmar,
        o soltar si ya había confirmado). Como en la selección del modo
        local: dos no pueden tener el mismo rol."""
        from data.roles import ROLES
        nombres = [r["nombre"] for r in ROLES]
        if self.fase_sala != "roles":
            return
        with self.candado_sala:
            if not 0 <= puesto.numero < len(self.seleccion):
                return
            estado = self.seleccion[puesto.numero]
            mover = mensaje.get("mover")
            if mensaje.get("ok") is True:
                if estado["listo"]:
                    estado["listo"], estado["rol"] = False, None
                else:
                    elegido = nombres[estado["cursor"] % len(nombres)]
                    if any(otro["listo"] and otro["rol"] == elegido
                           for i, otro in enumerate(self.seleccion) if i != puesto.numero):
                        return              # ese ya lo tomaron
                    estado["listo"], estado["rol"] = True, elegido
            elif mover in (-1, 1) and not isinstance(mover, bool):
                if not estado["listo"]:
                    estado["cursor"] = (estado["cursor"] + mover) % len(nombres)
            else:
                return
        self._mandar_sala()

    def _sala(self):
        """Hasta que todos estén conectados y hayan elegido rol."""
        from data.roles import ROLES
        with self.candado_sala:
            self.seleccion = [{"cursor": i % len(ROLES), "listo": False, "rol": None}
                              for i in range(self.n)]
        self.fase_sala = "roles"
        listos_desde = None
        while self.activo and not self.parar.is_set():
            self._vigilar_silencios()
            presentes = all(p.ocupado and p.buzon.conectado for p in self.puestos)
            with self.candado_sala:
                listos = all(e["listo"] for e in self.seleccion)
            if presentes and listos:
                # Un momentito con "Todos listos" en pantalla (y por si
                # alguien quería cambiar a último momento).
                listos_desde = listos_desde or time.perf_counter()
                if time.perf_counter() - listos_desde > 0.8:
                    break
            else:
                listos_desde = None
            time.sleep(0.05)
        with self.candado_sala:
            self.roles = [e["rol"] for e in self.seleccion]
        if not self.activo or self.parar.is_set():
            return
        self.fase_sala = "armando"
        self._mandar_sala()
        self.avisar(f"roles elegidos: {self.roles}")

    def _latir_sala(self):
        """Mientras dura la sala y se arma la nave (el hilo principal está
        ocupado y no manda nada), la `sala` dos veces por segundo: así el
        cliente no da la conexión por caída y el que se reconecta se entera
        de todo. Sigue unos segundos ya empezado el juego por si a alguien
        le faltó la última (la que trae los datos de la partida)."""
        while self.activo and not self.parar.is_set() and not self.terminando:
            if self.en_bucle_desde is not None and time.perf_counter() - self.en_bucle_desde > 5:
                return
            self._mandar_sala()
            time.sleep(0.5)

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
        puesto = generacion = None
        try:
            hola = lector.siguiente()
            if hola.get("tipo") != "hola" or hola.get("version") != VERSION:
                self._echar(s, f"se esperaba hola versión {VERSION}")
                return
            # La bienvenida necesita la partida armada (los roles, el mapa),
            # salvo con sala: ahí se arma después de que todos eligen.
            while not self.elegir_roles and not self.lista.wait(0.5):
                if not self.activo:
                    s.close()
                    return
            if self.terminando:
                self._echar(s, "el servidor se está cerrando")
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
                    # No hay puestos libres, pero alguien se fue y no volvió
                    # (su cliente dejó de reintentar, o cerró el juego y lo
                    # abrió otra vez: ya no tiene el token). Antes ese jugador
                    # no podía volver nunca: "la partida ya tiene sus N
                    # jugadores". Ahora el que llega sin token toma ese puesto,
                    # primero uno de su misma IP (su misma laptop).
                    caidos = [p for p in self.puestos if not p.buzon.conectado]
                    puesto = next((p for p in caidos if p.ip == direccion[0]),
                                  caidos[0] if caidos else None)
                    if puesto is not None:
                        # El token viejo deja de servir: si el cliente de antes
                        # aparece, se le dice que no (y no le quita el puesto).
                        puesto.token = secrets.token_hex(8)
                if puesto is None:
                    self._echar(s, f"la partida ya tiene sus {self.n} jugadores")
                    return
                vuelve = puesto.ocupado
                puesto.ocupado = True
                puesto.ip = direccion[0]
                viejo, puesto.sock = puesto.sock, None
                # La generación se cambia AQUÍ, con el candado: antes se
                # cambiaba después de mandar la bienvenida, y dos saludos con el
                # mismo token a la vez (un reintento del cliente mientras el
                # primero seguía) podían quedar con el socket de uno y la
                # generación del otro: el que se quedaba con `puesto.sock` no
                # tenía hilo de escritura y no le llegaba nada. Así, el que
                # pierde se entera abajo y se cierra.
                with puesto.buzon.candado:
                    puesto.generacion += 1
                    generacion = puesto.generacion
            if viejo is not None:             # (la conexión vieja todavía no se había caído)
                _cerrar(viejo)
            enviar(s, self.bienvenida(puesto))
            # Con timeout el hilo lector puede despertar a ver si se apagó el
            # servidor, y un cliente que no lee no traba al juego para siempre.
            s.settimeout(1.0)
            with puesto.hay:
                puesto.cola.clear()           # (lo de la conexión anterior ya no sirve)
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUFER_ENVIO)
            except OSError:
                pass
            with puesto.buzon.candado:
                if puesto.generacion != generacion:
                    s.close()                 # (otro saludo con el mismo token ganó)
                    return
                puesto.buzon.conectado = True
                puesto.buzon.quiere_completa = True
                puesto.buzon.mantener = set()
                puesto.buzon.ultimo_rx = puesto.buzon.ultima_intencion = time.perf_counter()
                puesto.sock = s
            threading.Thread(target=self._leer, args=(lector, puesto, generacion), daemon=True,
                             name=f"lector-J{puesto.numero + 1}").start()
            puesto.escritor = threading.Thread(target=self._escribir, args=(s, puesto, generacion),
                                               daemon=True, name=f"escritor-J{puesto.numero + 1}")
            puesto.escritor.start()
            self.avisar(f"J{puesto.numero + 1} {'reconectado' if vuelve else 'conectado'} desde "
                        f"{direccion[0]}:{direccion[1]} ({str(hola.get('nombre', ''))[:40]})")
        except (OSError, ConexionCerrada):
            s.close()
            if puesto is not None:
                # Se cayó a mitad de la bienvenida y ya había cerrado la
                # conexión vieja: si nadie más tomó el puesto, queda libre
                # para que vuelva (si no, seguía "conectado" sin socket).
                with puesto.buzon.candado:
                    if puesto.generacion == generacion and puesto.sock is None:
                        puesto.buzon.conectado = False

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
                ahora = time.perf_counter()
                buzon.ultimo_rx = ahora          # (un `latido` también cuenta)
                if tipo == "intencion":
                    # Lo que manda el cliente no se cree: "mantener": 5 o null
                    # tumbaba este hilo con TypeError sin pasar por la limpieza
                    # de abajo, y el jugador se quedaba "conectado" y
                    # caminando para siempre con lo último que pidió.
                    mantener = {a for a in _lista(mensaje.get("mantener")) if a in MANTENER}
                    pulsar = [a for a in _lista(mensaje.get("pulsar")) if a in PULSAR]
                    with buzon.candado:
                        buzon.ultima_intencion = ahora
                        buzon.mantener = mantener
                        vista = mensaje.get("vista")
                        if (isinstance(vista, list) and len(vista) == 2
                                and all(isinstance(v, int) and 100 <= v <= 8000 for v in vista)):
                            buzon.vista = (vista[0], vista[1])
                        if "interactuar" in pulsar and isinstance(mensaje.get("aguja"), (int, float)):
                            buzon.aguja = max(0.0, min(1.0, float(mensaje["aguja"])))
                        buzon.pulsar.extend(pulsar[:16])
                        del buzon.pulsar[:-32]      # que nadie llene la cola
                        if isinstance(mensaje.get("n"), int) and not isinstance(mensaje["n"], bool):
                            buzon.ultimo_n = mensaje["n"]
                elif tipo == "completa":
                    # Al cliente le faltó una instantánea (o llegó tarde): la
                    # siguiente se le manda entera.
                    with buzon.candado:
                        buzon.quiere_completa = True
                elif tipo == "rol":
                    self._rol(puesto, mensaje)
                elif tipo == "cerrar_partida":
                    # El juego que creó la partida se va (Esc, volver al
                    # menú): solo vale desde esta misma laptop. Avisa `fin`
                    # a los demás ya, también en la sala (ahí el servidor
                    # todavía no vigila al juego que lo levantó).
                    if str(puesto.ip or "").startswith("127."):
                        self.avisar("el que creó la partida la cerró")
                        self.parar.set()
                        break
                elif tipo == "adios":
                    break
        except (OSError, ConexionCerrada):
            pass
        except Exception as error:          # (algo que no se esperaba: se corta y ya)
            self.avisar(f"J{puesto.numero + 1}: mensaje raro, se corta la conexión ({error!r})")
        with buzon.candado:
            if puesto.generacion == generacion:
                buzon.conectado = False
                buzon.mantener = set()
        # Se cierra también para mandar: antes, si el lector se caía (algo que
        # no era JSON, un `adios`), el socket quedaba abierto y el cliente
        # seguía "jugando" sin recibir nada hasta su timeout.
        if getattr(lector, "sock", None) is not None:
            _cerrar(lector.sock)

    def _vigilar_silencios(self):
        """Lo llama el hilo del juego en cada cuadro: el que no manda nada hace
        rato se queda quieto (SUELTA_TECLAS_S) y después se da por caído
        (SILENCIO_S): se le cierra el socket y su cliente vuelve con el token."""
        ahora = time.perf_counter()
        for puesto in self.puestos:
            buzon = puesto.buzon
            if not buzon.conectado:
                continue
            if ahora - buzon.ultimo_rx > SILENCIO_S:
                with buzon.candado:
                    # (otra vez con el candado: si justo volvió, _saludar ya
                    # puso ultimo_rx nuevo y no hay que cerrarle nada)
                    if not buzon.conectado or ahora - buzon.ultimo_rx <= SILENCIO_S:
                        continue
                    buzon.conectado = False
                    buzon.mantener = set()
                    sock = puesto.sock
                self.avisar(f"J{puesto.numero + 1}: no manda nada hace {ahora - buzon.ultimo_rx:.1f} s; "
                            "se cierra para que reconecte")
                if sock is not None:
                    _cerrar(sock)
            elif buzon.mantener and ahora - buzon.ultima_intencion > SUELTA_TECLAS_S:
                with buzon.candado:
                    buzon.mantener = set()

    def _anunciar(self):
        """Grita por UDP a toda la red local "aquí hay una partida de NEXUS",
        cada segundo mientras falte alguien (lanzador.Buscador la escucha y
        la pone en la lista de "Unirse": nadie tiene que escribir IP ni
        código). Si la red no deja (wifi de la U, firewall), no pasa nada: el
        código de la partida sigue sirviendo."""
        import json
        from cliente_servidor.protocolo import PUERTO_ANUNCIO
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except OSError:
            return
        nombre = (socket.gethostname() or "NEXUS")[:24]
        while self.activo and not self.parar.is_set():
            conectados = sum(1 for p in self.puestos if p.buzon.conectado)
            if conectados < self.n:
                datos = json.dumps({"nexus": VERSION, "puerto": self.puerto, "jugadores": self.n,
                                    "conectados": conectados, "nombre": nombre,
                                    "dificultad": self.clave_dificultad}).encode("utf-8")
                for destino in _difusiones():
                    try:
                        s.sendto(datos, (destino, PUERTO_ANUNCIO))
                    except OSError:
                        pass
            time.sleep(1.0)
        s.close()

    def _escribir(self, s, puesto, generacion):
        """El hilo que le manda a UN jugador lo que hay en su cola. Si no se le
        puede escribir en ENVIO_MAX_S, se le cierra el socket: su cliente se da
        cuenta y vuelve con su token (reconexión)."""
        while True:
            with puesto.hay:
                while (not puesto.cola and puesto.generacion == generacion and self.activo
                       and not self.terminando):
                    puesto.hay.wait(0.5)
                if puesto.generacion != generacion:
                    return
                if not puesto.cola:
                    if self.terminando or not self.activo:
                        # Ya salió lo último (el `fin`): se cierra el lado de
                        # escritura AQUÍ, después del último byte. Antes el
                        # hilo principal cerraba el socket apenas la cola se
                        # veía vacía, con el `fin` todavía a medio mandar
                        # (el cliente lo perdía y tardaba 13 s en enterarse).
                        try:
                            s.shutdown(socket.SHUT_WR)
                        except OSError:
                            pass
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
        while (self.activo and not self.parar.is_set()
               and not all(p.ocupado and p.buzon.conectado for p in self.puestos)):
            # (uno que se fue mientras esperaba no cuenta como presente)
            self._vigilar_silencios()
            conectados = sum(p.buzon.conectado for p in self.puestos)
            self._a_todos({"tipo": "espera", "conectados": conectados, "faltan": self.n - conectados})
            time.sleep(0.25)

    # -- El juego ---------------------------------------------------------------------

    def bucle(self):
        """60 cuadros por segundo con paso fijo; instantánea cada 2."""
        self.en_bucle_desde = time.perf_counter()
        paso = 1.0 / HZ_JUEGO
        siguiente = time.perf_counter()
        inicio = siguiente
        fin_avisado = False
        solo_desde = None         # desde cuándo no hay nadie conectado
        medidas = self.medidas
        medidas["inicio"] = inicio
        proximo_informe = inicio + INFORME_CADA_S
        while self.activo and not self.parar.is_set():
            if self.cierre.is_set():
                self.avisar("me pidieron cerrar")
                break
            t0 = time.perf_counter()
            self._vigilar_silencios()
            acks = self._aplicar_entradas()
            g = self.juego
            if g.mision.resultado is None and g.current_screen == "partida":
                g._actualizar_partida(DT_MS)
            elif not fin_avisado:
                fin_avisado = True
                self.avisar(f"partida terminada: {g.mision.resultado}")
            self.cuadro += 1
            if self.cuadro % CUADROS_POR_INSTANTANEA == 0:
                t1 = time.perf_counter()
                self._mandar_instantanea(acks)
                medidas["inst_ms"] += (time.perf_counter() - t1) * 1000
                medidas["inst_n"] += 1
            medidas["cuadros"] += 1
            medidas["peor_ms"] = max(medidas["peor_ms"], (time.perf_counter() - t0) * 1000)
            if time.perf_counter() > proximo_informe:
                proximo_informe += INFORME_CADA_S
                self.avisar(self.rendimiento())
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
                medidas["tarde"] += 1

    def rendimiento(self):
        """Una línea para la consola: ¿el servidor alcanza los 60 cuadros?"""
        m = self.medidas
        if not m["inicio"] or not m["cuadros"]:
            return "rendimiento: sin cuadros todavía"
        segundos = max(1e-6, time.perf_counter() - m["inicio"])
        return (f"rendimiento: {m['cuadros'] / segundos:.1f} cuadros/s (de {HZ_JUEGO}), peor cuadro "
                f"{m['peor_ms']:.0f} ms, instantánea media {m['inst_ms'] / max(1, m['inst_n']):.1f} ms, "
                f"{m['tarde']} veces atrasado más de 250 ms")

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
            "tut_estado": _tutorial(g),
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
        if g.logros is not None and secciones.get("lg"):
            # El árbol de logros no viaja (es grande y el espejo tiene el
            # mismo): solo cuáles salieron y de quién. Sin esto el cliente
            # mostraba 0 logros en los resultados.
            secciones["lg"]["obtenidos"] = {n.clave: [n.quien, n.por_camino]
                                            for n in g.logros.arbol.preorden() if n.obtenido}
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
            "escondite": _indice(self.juego.escondites, j.escondite),
            "zc": _indice(self.juego.zonas, j.zona_cerca),
            "ecc": _indice(self.juego.escondites, j.escondite_cerca),
            "stc": (["t", _indice(self.juego.terminales, j.estacion_cerca)]
                    if _indice(self.juego.terminales, j.estacion_cerca) is not None else
                    ["p", _indice(self.juego.paneles, j.estacion_cerca)]
                    if _indice(self.juego.paneles, j.estacion_cerca) is not None else None),
        }
        for clave, v in E.atributos(j, JUGADOR_NO).items():
            datos["a." + clave] = v
        arbol = getattr(j, "arbol", None)
        if arbol is not None and hasattr(arbol, "__dict__"):
            for clave, v in E.atributos(arbol).items():
                datos["h." + clave] = v
            # Las habilidades que escogió: los nodos del árbol no viajan
            # (`actual` es un NodoHabilidad, que extraer no sabe mandar) y en
            # el cliente nadie desbloqueaba nada: el HUD seguía con "[Q]
            # escoge tu habilidad", el panel con todo por escoger y lo que
            # depende de `arbol.tiene(...)` (la Sintonía...) no se dibujaba.
            if hasattr(arbol, "por_niveles"):
                datos["hab"] = [[n.clave for n in arbol.desbloqueadas()],
                                [n.clave for n, _ in arbol.por_niveles() if n.descartada]]
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
        # Se arma SOLO si alguien la necesita: antes se comprimía en cada
        # instantánea (30 veces por segundo) aunque casi nunca se mandara, y
        # era ~un tercio de lo que tardaba el servidor en mandar.
        completa = []

        def bytes_completa():
            if not completa:
                completa.append(a_bytes(dict(cabeza, base=None, z=comprimir(ahora))))
            return completa[0]

        if self.anterior is None or self.cuadro % CADA_COMPLETA == 0:
            bytes_delta = None            # (todos reciben la completa)
        else:
            cambios = {}
            for seccion, datos in ahora.items():
                d = E.diferencias(self.anterior.get(seccion, {}), datos)
                if d:
                    cambios[seccion] = d
            # El JSON de los cambios se arma una vez: antes se armaba para
            # medirlo, otra vez para comprimirlo y otra para mandarlo.
            crudo = a_bytes(cambios)
            if len(crudo) > COMPRIMIR_DESDE:
                # (con muchos NPC caminando la delta pasa de 4 KB; comprimida, ~1,5)
                bytes_delta = a_bytes(dict(cabeza, base=self.cuadro_anterior,
                                           z=comprimir_bytes(crudo[:-1])))
            else:
                bytes_delta = a_bytes(dict(cabeza, base=self.cuadro_anterior, s=cambios))
        self.anterior, self.cuadro_anterior = ahora, self.cuadro
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
            entera = entera or bytes_delta is None
            datos = bytes_completa() if entera else bytes_delta
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
            if not self.host.startswith("127."):
                threading.Thread(target=self._anunciar, daemon=True, name="anunciar").start()
            # Si armar la nave se traba (pasó en Windows), cada 30 s se escribe
            # dónde está cada hilo: sale en la terminal y en el registro del
            # lanzador (Guardado/nexus_servidor.log).
            try:
                faulthandler.dump_traceback_later(30, repeat=True, file=sys.stderr)
            except (AttributeError, ValueError, OSError, RuntimeError):
                pass
            if self.elegir_roles:
                threading.Thread(target=self._latir_sala, daemon=True, name="sala").start()
                self._sala()
                if not self.activo or self.parar.is_set():
                    return
            self.preparar_partida()
            self.lista.set()
            self.fase_sala = "lista"
            if self.elegir_roles:
                self._mandar_sala()         # (con los datos de la partida)
            try:
                faulthandler.cancel_dump_traceback_later()
            except (AttributeError, ValueError, OSError, RuntimeError):
                pass
            if self.con_padre:
                # Recién ahora: en Windows, un hilo trabado leyendo la entrada
                # (un tubo) traba también a cualquier otro que toque ese mismo
                # archivo, y armar la nave (pygame.init y compañía) lo tocaba:
                # el servidor se quedaba "Armando la nave..." para siempre.
                vigilar_padre(self)
            self._esperar_jugadores()
            if self.activo and not self.parar.is_set():
                self.avisar("empieza la partida")
                self.bucle()
        except KeyboardInterrupt:
            self.avisar("Ctrl+C")
        finally:
            self.cerrar()

    def vigilar_padre(self, entrada=None):
        """Con --con-padre (lo pone el lanzador): el servidor lee su entrada
        estándar, que es un tubo desde el juego que lo levantó. Cuando el
        juego escribe "salir" o se cierra el tubo (el juego salió, se cayó o
        lo cerraron con la X o el Administrador de tareas), el servidor avisa
        `fin` a todos y se apaga. Antes quedaba huérfano: en Windows
        `terminate()` lo mataba sin avisar a la otra laptop, y si el juego se
        caía seguía corriendo con el puerto 5050 tomado (la próxima "Crear
        partida" fallaba)."""
        entrada = entrada or sys.stdin

        def leer():
            try:
                for linea in entrada:
                    if linea.strip() == "salir":
                        break
            except (OSError, ValueError):
                pass
            self.cierre.set()
        threading.Thread(target=leer, daemon=True, name="padre").start()

    def cerrar(self, texto="El servidor se cerró."):
        """Avisa a todos (`fin`) y cierra: los clientes vuelven al menú."""
        if self._cerrado:
            return
        self._cerrado = True
        self.parar.set()          # (si lo llaman desde otro hilo, que pare el bucle)
        if self.medidas["cuadros"]:
            self.avisar(self.rendimiento())
        if self.tamanos:
            delta = [b for b, entera in self.tamanos if not entera] or [0]
            entera = [b for b, e in self.tamanos if e] or [0]
            self.avisar(f"instantáneas: delta media {sum(delta) / len(delta):.0f} B, máx {max(delta)} B; "
                        f"completa media {sum(entera) / len(entera):.0f} B, máx {max(entera)} B")
        self._a_todos({"tipo": "fin", "texto": texto})
        # Que alcance a salir el `fin`: cada hilo de escritura vacía su cola y
        # cierra su lado; después se espera un poco a que cada cliente cierre
        # el suyo (los lectores siguen leyendo mientras tanto). Cerrar un
        # socket con datos sin leer (las intenciones que siguen llegando)
        # manda un RST, y con el RST el cliente (en Windows seguro) tira lo
        # que no había leído: el `fin` incluido.
        self.terminando = True
        for puesto in self.puestos:
            with puesto.hay:
                puesto.hay.notify_all()
        limite = time.time() + 1.5
        for puesto in self.puestos:
            escritor = puesto.escritor
            if escritor is not None and escritor is not threading.current_thread():
                escritor.join(max(0.0, limite - time.time()))
        while time.time() < limite and any(p.buzon.conectado for p in self.puestos):
            time.sleep(0.02)
        # Primero solo "ya no mando más" (FIN detrás del `fin`) y un momento
        # para que llegue: cerrar de una con intenciones sin leer en el socket
        # manda un RST, y el cliente a veces perdía el `fin` y creía que era
        # un corte del wifi (reintentaba 10 s antes de volver al menú).
        time.sleep(0.05)
        for puesto in self.puestos:
            if puesto.sock is not None:
                try:
                    puesto.sock.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
        time.sleep(0.2)
        self.activo = False
        for puesto in self.puestos:
            with puesto.hay:
                puesto.hay.notify_all()
        for puesto in self.puestos:
            if puesto.sock is not None:
                _cerrar(puesto.sock)
        if self.sock is not None:
            self.sock.close()


def _difusiones():
    """A dónde mandar el anuncio: la difusión general y la de cada red de esta
    laptop (x.y.z.255; en Windows la general sale por una sola tarjeta)."""
    destinos = ["255.255.255.255"]
    ips = set()
    try:
        prueba = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        prueba.connect(("10.255.255.255", 1))
        ips.add(prueba.getsockname()[0])
        prueba.close()
    except OSError:
        pass
    try:
        ips.update(i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET))
    except OSError:
        pass
    for ip in ips:
        if not ip.startswith(("127.", "169.254.")):
            destinos.append(ip.rsplit(".", 1)[0] + ".255")
    return destinos


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


def _lista(valor):
    """Una lista que mandó el cliente, o () si mandó otra cosa (un número,
    null, un texto suelto): solo se miran sus textos."""
    if not isinstance(valor, (list, tuple)):
        return ()
    return [v for v in valor if isinstance(v, str)]


def _cerrar(s):
    try:
        s.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    s.close()


def _indice(lista, objeto):
    """La posición de `objeto` en `lista` (por identidad), o None."""
    if objeto is None:
        return None
    return next((i for i, o in enumerate(lista or ()) if o is objeto), None)


class todos_se_mueven:
    """Mientras se arma la partida, ningún puesto queda "sin mando".

    En el modo local J3 y J4 sin mando se arman quietos (PUESTOS_SIN_MOVIMIENTO)
    y la misión cuenta solo los roles que se mueven. En red todos se mueven (su
    entrada viene del socket), pero `puede_moverse = True` se ponía DESPUÉS de
    armar la misión: con 3 jugadores la Biomante (J3) contaba como ausente y
    salía un abono que no hacía falta (y si J3 era el Tecnomante, un
    decodificador). Lo usan el servidor y el espejo, para que armen lo mismo."""

    def __enter__(self):
        from entidades import jugador
        self._antes, jugador.PUESTOS_SIN_MOVIMIENTO = jugador.PUESTOS_SIN_MOVIMIENTO, ()
        return self

    def __exit__(self, *_):
        from entidades import jugador
        jugador.PUESTOS_SIN_MOVIMIENTO = self._antes
        return False


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


def _tutorial(g):
    """En qué paso del tutorial va cada jugador, por número de jugador. En el
    Tutorial es un dict por id() del jugador, y los id() no son los mismos en
    el espejo: así no viajaba y el cliente se quedaba en el paso 1."""
    tut = getattr(g, "tutorial", None)
    if tut is None or not getattr(tut, "activo", False):
        return None
    return [dict(tut.estado.get(id(j), {"paso": 0, "sigilo_ms": 0, "listo": False}))
            for j in g.jugadores]


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


def vigilar_padre(servidor):
    """Con --con-padre (lo usa el lanzador): el servidor se apaga cuando se
    cierra su entrada estándar. El juego que lo levantó la cierra al salir de
    la partida, y si ese juego se cuelga o lo matan, el sistema la cierra
    solo. Antes, en Windows no había cómo pedirle que avisara `fin` (terminate
    lo mata en seco) y si el juego se caía el servidor quedaba huérfano
    esperando jugadores para siempre, con el puerto 5050 tomado: el siguiente
    "Crear partida" fallaba con "¿el puerto ya está ocupado?"."""
    def leer():
        try:
            while sys.stdin.buffer.read(1024):
                pass
        except (OSError, ValueError, AttributeError):
            pass
        servidor.avisar("el juego que lo levantó se cerró")
        servidor.parar.set()
    threading.Thread(target=leer, daemon=True, name="padre").start()


def _al_terminar(_senal, _cuadro):
    raise KeyboardInterrupt


def atrapar_senales():
    """SIGTERM (kill, terminate()) apaga el servidor como Ctrl+C, avisando
    `fin`. Hay que ponerlo ANTES de pygame.init(): SDL se queda con las
    señales que siguen "por defecto" y las convierte en un evento SDL_QUIT
    que aquí nadie lee, así que el servidor no se moría con SIGTERM."""
    import signal
    for nombre in ("SIGTERM", "SIGBREAK"):
        if hasattr(signal, nombre):
            try:
                signal.signal(getattr(signal, nombre), _al_terminar)
            except (OSError, ValueError):
                pass        # (no es el hilo principal)


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
    ap.add_argument("--tutorial", action="store_true",
                    help="con el tutorial del principio (lo pone el menú del juego)")
    ap.add_argument("--elegir-roles", action="store_true",
                    help="cada jugador elige su rol antes de armar la nave (lo pone el menú del juego)")
    ap.add_argument("--con-padre", action="store_true",
                    help="apagarse cuando se cierre la entrada estándar (lo usa el menú del juego)")
    args = ap.parse_args(argv)
    _sin_ventana()
    os.chdir(RAIZ)            # las imágenes y mapas se buscan desde aquí (como main.py)
    roles = [r.strip() for r in args.roles.split(",")] if args.roles else None
    atrapar_senales()
    servidor = Servidor(args.jugadores, args.host, args.puerto, roles, args.dificultad, args.mapa,
                        args.segundos, avisar=lambda texto: print("[servidor]", texto, flush=True),
                        presentaciones=not args.sin_presentaciones, aliens_quietos=args.aliens_quietos,
                        espera_s=args.espera, semilla=args.semilla, fase_final=args.fase_final,
                        tutorial=args.tutorial, elegir_roles=args.elegir_roles)
    servidor.con_padre = args.con_padre      # (vigilar_padre empieza en correr)
    servidor.correr()


if __name__ == "__main__":
    main()
