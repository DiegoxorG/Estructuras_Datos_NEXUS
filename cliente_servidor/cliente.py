"""El cliente de NEXUS: UNA ventana, una conexión por jugador local.

    python -m cliente_servidor.cliente --jugadores 2
    python -m cliente_servidor.cliente --jugadores 2 --host 192.168.1.20     (otra laptop)
    python -m cliente_servidor.cliente --jugadores 2 --mandos               (J1 y J2 con mando)
    python -m cliente_servidor.cliente --jugadores 1 --puerto 6000 --ventana 1600x900

Lo normal es no usar esto a mano: el menú del juego tiene "Jugar en red"
(cliente_servidor/lanzador.py), que levanta el servidor y llama `jugar`.

El cliente abre una conexión TCP por cada jugador que juega en esta ventana:
el servidor ve cada socket como un jugador distinto, igual que si cada uno
estuviera en su laptop. Una sola ventana para todos porque el teclado solo le
llega a la ventana que tiene el foco (los mandos sí llegan a cualquiera).

Controles, los mismos del modo local (entidades/jugador.py): el jugador local
1 usa WASD, el 2 flechas, el 3 y el 4 mando. Con `mandos=True` los primeros
juegan con mando y después el teclado. Esc sale al menú.

Hilos: el principal es el de pygame (eventos, entrada y dibujo); hay uno
lector por conexión que arma las instantáneas y, si la conexión se cae,
intenta volver con el token de la bienvenida.

El dibujo: el espejo (cliente_servidor/espejo.py) arma la misma partida con
el `Game` del juego y dibuja con las funciones del modo local. Las posiciones
van interpoladas (cliente_servidor/interpolacion.py).
"""

import argparse
import os
import socket
import sys
import threading
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(RAIZ)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

import pygame

from cliente_servidor.protocolo import (VERSION, HOST, PUERTO, MANTENER, PULSAR, LectorLineas,
                                        ConexionCerrada, enviar, sin_nagle, Reconstructor, legible,
                                        a_bytes)
from cliente_servidor.interpolacion import Interpolador
from juego.mandos import EVENTOS_MANDO

# Cada cuánto se repite la intención aunque no cambie (por si se perdió algo).
REPETIR_INTENCION_S = 0.1
# Sin noticias del servidor en este tiempo, la conexión se da por caída
# (el servidor manda algo cada 33 ms, o cada 250 ms mientras espera).
SILENCIO_S = 3.0
# Cuánto se intenta volver después de un corte. Eran 10 s: con el hotspot de
# un celular que se va 10-15 s (alguien lo bloqueó, se fue a otra sala) el
# jugador se rendía y ya no podía volver (ahora además el servidor le guarda
# el puesto: ver servidor._saludar).
RECONECTAR_S = 20.0
# Sin nada que mandar en este tiempo, el hilo escritor manda un `latido`: el
# servidor da por caído al que no manda nada en 5 s (servidor.SILENCIO_S), y
# mientras se arma la nave o la ventana está trabada (Windows la congela
# mientras se arrastra) la Sesion no manda intenciones.
LATIDO_S = 0.5


class Cancelado(Exception):
    """El jugador pulsó Esc mientras se conectaba."""


class Cancelacion(threading.Event):
    """Un Event que además corta el saludo en curso: si el Esc llega mientras
    se espera la bienvenida (el servidor arma la partida), cerrar el socket
    despierta al hilo que la espera en vez de dejarlo colgado hasta 60 s con
    un puesto tomado."""
    intento = None

    def set(self):
        super().set()
        sock = self.intento
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


class Rechazado(ConexionCerrada):
    """El servidor contestó `error` al saludo (partida llena, token de otra
    partida, otra versión): no vale la pena reintentar."""


class Conexion:
    """El socket de UN jugador local, más el hilo que lee sus instantáneas."""

    def __init__(self, host, puerto, nombre, esperar_s=15.0, saludo_s=60.0, cancelado=None):
        self.host, self.puerto, self.nombre = host, puerto, nombre
        # threading.Event: Esc en la pantalla de "Conectando..." (Sesion.conectar)
        self.cancelado = cancelado if cancelado is not None else Cancelacion()
        self.ultimo_rx = time.perf_counter()   # cuándo llegó lo último del servidor
        self.reconectando_desde = None
        self.candado = threading.Lock()
        self.reconstructor = Reconstructor()
        self.interpolador = Interpolador()
        self.estado = None            # la última instantánea completa (secciones)
        self.cuadro = None
        self.espera = None            # el último aviso de "faltan jugadores"
        self.sala = None              # la última `sala` (elegir rol; servidor --elegir-roles)
        self.sonidos = []
        self.situacion = "conectando"  # conectando, jugando, reconectando, perdida, fin
        self.fin_texto = ""
        self.cerrando = False
        self.pidio_completa = False
        self.n = 0                    # número de la última intención mandada
        self.enviadas = {}            # n -> cuándo se mandó (para medir la respuesta)
        self.respuesta_ms = None      # intención -> instantánea que la incluye
        self.ultima = None            # (mantener, cuándo) de la última mandada
        self.reconexiones = 0
        self.token = None
        self.sock, self.lector, self.bienvenida = self._saludar(esperar_s, saludo_s)
        if self.cancelado.is_set():
            # (llegó la bienvenida justo después del Esc: se suelta el puesto)
            self._adios_y_cerrar()
            raise Cancelado()
        self.jugador = self.bienvenida["jugador"]
        self.token = self.bienvenida.get("token")
        self.situacion = "jugando"
        # Lo que se manda va por otro hilo: si el wifi se traba, el que espera
        # es ese hilo y no la ventana del juego (antes el sendall podía
        # congelar el dibujo hasta 3 s).
        self._salida = []
        self._hay_salida = threading.Condition()
        threading.Thread(target=self._leer, daemon=True,
                         name=f"lector-J{self.jugador + 1}").start()
        self._escritor = threading.Thread(target=self._escribir, daemon=True,
                                          name=f"escritor-J{self.jugador + 1}")
        self._escritor.start()

    @property
    def viva(self):
        return self.situacion in ("jugando", "reconectando")

    def _saludar(self, esperar_s, saludo_s):
        sock = _conectar(self.host, self.puerto, esperar_s)
        try:
            sin_nagle(sock)
            lector = LectorLineas(sock)
            hola = {"tipo": "hola", "version": VERSION, "nombre": self.nombre}
            if self.token:
                hola["token"] = self.token
            enviar(sock, hola)
            # El servidor puede estar armando la partida (tarda unos segundos):
            # la bienvenida llega cuando termina.
            sock.settimeout(saludo_s)
            bienvenida = lector.siguiente()
            if bienvenida.get("tipo") != "bienvenida":
                if bienvenida.get("tipo") == "error":
                    raise Rechazado(bienvenida.get("texto", "el servidor no lo dejó entrar"))
                raise ConexionCerrada("el servidor no dio la bienvenida")
        except BaseException:
            # (antes, si se cortaba a mitad del saludo, el socket quedaba
            # abierto: en la reconexión se juntaba uno por intento)
            sock.close()
            raise
        sock.settimeout(SILENCIO_S)
        self.ultimo_rx = time.perf_counter()
        self.cancelado.intento = None
        return sock, lector, bienvenida

    def _leer(self):
        while not self.cerrando:
            try:
                while True:
                    mensaje = self.lector.siguiente()
                    self.ultimo_rx = time.perf_counter()
                    if self._recibir(mensaje):
                        return
            except (OSError, ConexionCerrada):
                # (socket.timeout es un OSError: el servidor se calló)
                pass
            if self.cerrando:
                return
            if not self._reconectar():
                self.situacion = "perdida"
                return

    def _recibir(self, mensaje):
        """True si el servidor dijo que se acabó."""
        tipo = mensaje.get("tipo")
        if tipo == "estado":
            ahora = time.perf_counter()
            secciones = self.reconstructor.aplicar(mensaje)
            if secciones is None:
                # Faltó una instantánea (o llegó otra cosa): pedir una entera.
                if not self.pidio_completa:
                    self.pidio_completa = True
                    self._enviar({"tipo": "completa"})
                return False
            self.pidio_completa = False
            ack = mensaje.get("ack") or []
            with self.candado:
                self.estado, self.cuadro = secciones, mensaje.get("c")
                self.sonidos.extend(mensaje.get("snd") or ())
                del self.sonidos[:-20]
                self.interpolador.agregar(mensaje.get("c", 0), secciones, ahora)
                if self.jugador < len(ack) and ack[self.jugador] in self.enviadas:
                    ms = (ahora - self.enviadas.pop(ack[self.jugador])) * 1000
                    previo = self.respuesta_ms
                    self.respuesta_ms = ms if previo is None else previo * 0.9 + ms * 0.1
        elif tipo == "espera":
            with self.candado:
                self.espera = mensaje
        elif tipo == "sala":
            conectados = [bool(c) for c in _lista_de(mensaje.get("conectados"))]
            with self.candado:
                self.sala = mensaje
                if conectados:
                    self.espera = {"conectados": sum(conectados),
                                   "faltan": len(conectados) - sum(conectados)}
                # Ya se armó la nave: lo que faltaba para armar el espejo.
                if isinstance(mensaje.get("partida"), dict) and "roles" not in self.bienvenida:
                    self.bienvenida.update(mensaje["partida"])
        elif tipo == "fin":
            self.fin_texto = mensaje.get("texto", "")
            self.situacion = "fin"
            return True
        return False

    def _reconectar(self):
        """Vuelve con el token: el servidor le devuelve su mismo jugador."""
        self.situacion = "reconectando"
        self.reconectando_desde = time.time()
        try:
            self.sock.close()
        except OSError:
            pass
        limite = time.time() + RECONECTAR_S
        while time.time() < limite and not self.cerrando:
            try:
                self.sock, self.lector, nueva = self._saludar(1.0, 5.0)
                if "roles" in nueva and "roles" not in self.bienvenida:
                    self.bienvenida.update(nueva)       # (se armó mientras estaba cortado)
            except Rechazado as error:
                self.fin_texto = str(error)
                return False          # el servidor dijo que no (otra partida)
            except (OSError, ConexionCerrada):
                # Se cortó a mitad del saludo (wifi que va y viene, el
                # servidor que todavía no soltó la conexión vieja): eso no es
                # un "no", se vuelve a intentar hasta que se acabe el plazo.
                time.sleep(0.3)
                continue
            self.reconstructor = Reconstructor()     # la siguiente llega entera
            self.reconexiones += 1
            self.ultima = None
            self.reconectando_desde = None
            self.situacion = "jugando"
            return True
        return False

    def ultimo_estado(self):
        with self.candado:
            return self.estado

    def sacar_sonidos(self):
        with self.candado:
            sonidos, self.sonidos = self.sonidos, []
            return sonidos

    def _enviar(self, mensaje):
        """A la cola del hilo escritor (no bloquea)."""
        datos = a_bytes(mensaje)
        cond = getattr(self, "_hay_salida", None)
        if cond is None:                # (todavía saludando)
            try:
                enviar(self.sock, mensaje)
            except OSError:
                pass
            return
        with cond:
            self._salida.append(datos)
            del self._salida[:-64]
            cond.notify()

    def _escribir(self):
        """El ÚNICO que escribe en el socket ya saludado (el `adios` de
        `cerrar` también pasa por aquí: antes lo mandaba el hilo principal a la
        vez que este mandaba intenciones, y dos sendall al mismo tiempo en un
        socket pueden mezclar sus bytes: media línea de cada uno)."""
        ultimo = time.perf_counter()
        latido = a_bytes({"tipo": "latido"})
        while True:
            with self._hay_salida:
                limite = ultimo + LATIDO_S
                while not self._salida and not self.cerrando and time.perf_counter() < limite:
                    self._hay_salida.wait(max(0.01, limite - time.perf_counter()))
                if self.cerrando and not self._salida:
                    return              # (cerrando: el `adios` ya salió, si lo había)
                # Nada que mandar en LATIDO_S: un latido, para que el servidor
                # sepa que esta laptop sigue ahí.
                datos = b"".join(self._salida) or latido
                self._salida = []
            if self.situacion != "jugando" and not self.cerrando:
                continue                # reconectando: las intenciones viejas no sirven
            sock = self.sock
            try:
                sock.sendall(datos)
                ultimo = time.perf_counter()
            except OSError:
                if self.cerrando:
                    return
                # (el lector se da cuenta y reconecta)

    def mandar(self, mantener, pulsar, extra=None):
        """Manda la intención si cambió, si hay algo pulsado o si ya pasó un rato."""
        if self.situacion != "jugando":
            return
        ahora = time.perf_counter()
        mantener = sorted(mantener)
        if (not pulsar and self.ultima is not None and self.ultima[0] == mantener
                and ahora - self.ultima[1] < REPETIR_INTENCION_S):
            return
        self.n += 1
        with self.candado:
            self.enviadas[self.n] = ahora
            if len(self.enviadas) > 200:          # los que nunca volvieron
                for viejo in sorted(self.enviadas)[:100]:
                    del self.enviadas[viejo]
        self.ultima = (mantener, ahora)
        self._enviar({"tipo": "intencion", "n": self.n, "mantener": mantener, "pulsar": pulsar,
                      **(extra or {})})

    def cortar(self):
        """Corta el socket sin avisar (para probar la reconexión)."""
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def _adios_y_cerrar(self):
        try:
            # Poco tiempo: con el wifi trabado esto congelaba la ventana hasta
            # 3 s por jugador al salir al menú.
            self.sock.settimeout(0.2)
            enviar(self.sock, {"tipo": "adios"})
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass

    def cerrar(self):
        if self.cerrando:
            return
        cond = getattr(self, "_hay_salida", None)
        if cond is None:
            self.cerrando = True
            try:
                self.sock.close()
            except OSError:
                pass
            return
        # El `adios` va por el hilo escritor, detrás de lo que faltaba. Se le
        # da un momento y se cierra: antes el sendall era de este hilo (el de
        # la ventana) con el timeout del socket, y con el wifi trabado la
        # ventana se congelaba hasta 3 s al salir.
        with cond:
            self._salida.append(a_bytes({"tipo": "adios"}))
            self.cerrando = True
            cond.notify_all()
        escritor = getattr(self, "_escritor", None)
        if escritor is not None and escritor is not threading.current_thread():
            escritor.join(0.5)
        try:
            self.sock.shutdown(socket.SHUT_RDWR)     # (despierta al lector y al escritor)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


def _lista_de(valor):
    return valor if isinstance(valor, list) else []


def _conectar(host, puerto, esperar_s, cancelado=None):
    """Reintenta un rato: así se puede abrir el cliente antes que el servidor."""
    limite = time.time() + esperar_s
    while True:
        if cancelado is not None and cancelado.is_set():
            raise Cancelado()
        try:
            return socket.create_connection((host, puerto), timeout=3)
        except socket.gaierror as error:
            # Una dirección que no existe ("1.2.3.4.5") no va a aparecer
            # reintentando: antes se reintentaba 15 s con la ventana quieta.
            raise OSError(f"la dirección {host} no sirve ({error})") from error
        except (ValueError, OverflowError) as error:
            # "192.168..1": el idna no la entiende y lanza UnicodeError, que
            # NO es OSError: tumbaba el juego entero desde el menú.
            raise OSError(f"la dirección {host}:{puerto} está mal escrita") from error
        except OSError:
            if time.time() > limite:
                raise
            time.sleep(0.3)


# -- Entrada -------------------------------------------------------------------------

def esquemas_para(cantidad, mandos=False):
    """El control de cada jugador local (índices de TECLAS_POR_PUESTO):
    teclado primero (WASD, flechas, mando 1, mando 2) o, con `mandos`, los
    dos mandos primero y después el teclado."""
    from entidades.jugador import WASD, FLECHAS, MANDO_1, MANDO_2
    orden = [MANDO_1, MANDO_2, WASD, FLECHAS] if mandos else [WASD, FLECHAS, MANDO_1, MANDO_2]
    return orden[:cantidad]


class Entrada:
    """Teclado y mandos -> acciones de cada jugador local.

    Reutiliza lo del modo local: las teclas de cada esquema
    (entidades/jugador.TECLAS_POR_PUESTO, que para los mandos son teclas
    virtuales) y juego/mandos.Mandos para los controles."""

    def __init__(self, esquemas, mandos=None):
        from entidades.jugador import TECLAS_POR_PUESTO
        from juego.mandos import Mandos
        self.esquemas = list(esquemas)
        self.teclas = [TECLAS_POR_PUESTO[e] for e in self.esquemas]
        self.mandos = mandos or Mandos()
        self.pulsados = [[] for _ in self.esquemas]

    def evento(self, ev):
        if ev.type == pygame.KEYDOWN:
            for i, teclas in enumerate(self.teclas):
                for accion in PULSAR:
                    if ev.key in teclas.get(accion, ()):
                        self.pulsados[i].append(accion)
        elif ev.type in EVENTOS_MANDO:
            # JOY* y CONTROLLER*: con los mandos que SDL reconoce (Xbox, PS)
            # los botones llegan como CONTROLLER*, y antes aquí se perdían.
            # Mandos.evento devuelve (esquema del mando, acción).
            for esquema, accion in self.mandos.evento(ev):
                if esquema in self.esquemas and accion in PULSAR:
                    self.pulsados[self.esquemas.index(esquema)].append(accion)

    def sacar(self):
        """[(mantener, pulsar)] de cada jugador local en este cuadro."""
        presionadas = self.mandos.envolver(pygame.key.get_pressed())
        salida = []
        for i, teclas in enumerate(self.teclas):
            mantener = {a for a in MANTENER if any(presionadas[k] for k in teclas.get(a, ()))}
            salida.append((mantener, self.pulsados[i]))
            self.pulsados[i] = []
        return salida


# -- La sesión en la ventana del juego -------------------------------------------------

def aviso(pantalla, lineas, color=(230, 230, 230), extra=(), color_extra=(120, 220, 255)):
    """Una pantalla de texto centrado (conectando, esperando, se cortó...).
    `extra`: líneas más abajo y de otro color (la IP para unirse)."""
    from juego.fuentes import fuente
    pantalla.fill((12, 14, 22))
    letra = fuente("subtitle")
    todas = [(l, color) for l in lineas] + ([("", color)] if extra else []) + [(l, color_extra) for l in extra]
    y = pantalla.get_height() // 2 - 24 * len(todas)
    for linea, c in todas:
        if linea:
            imagen = letra.render(linea, True, c)
            pantalla.blit(imagen, imagen.get_rect(midtop=(pantalla.get_width() // 2, y)))
        y += 48


def _esperar_tecla(pantalla, lineas, segundos=4.0):
    """Muestra un aviso hasta que se pulse algo o pasen `segundos`."""
    fin = time.time() + segundos
    while time.time() < fin:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.event.post(ev)     # (que el menú también se entere y cierre el juego)
                return
            if ev.type in (pygame.KEYDOWN, pygame.JOYBUTTONDOWN):
                return
        aviso(pantalla, lineas)
        pygame.display.flip()
        time.sleep(1 / 30)


class Cancelado(Exception):
    """Esc (o cerrar la ventana) mientras se conectaba."""

    def __init__(self, motivo):
        super().__init__(motivo)
        self.motivo = motivo


def _sin_congelar(pantalla, lineas, trabajo, dibujo=None):
    """Corre `trabajo()` en otro hilo mientras la ventana sigue viva (el
    aviso y los eventos): conectar a una IP que no contesta tarda hasta 15 s
    y antes la ventana se quedaba congelada todo ese rato (Windows la marca
    "no responde"). Esc lo cancela (Cancelado("menu")), cerrar la ventana
    también (Cancelado("salir")). Si el hilo termina después de cancelado,
    lo que armó (una Conexion) se cierra solo."""
    caja = {"listo": False, "cancelado": False, "resultado": None, "error": None}
    candado = threading.Lock()

    def correr():
        try:
            resultado, error = trabajo(), None
        except Exception as e:
            resultado, error = None, e
        with candado:
            caja.update(listo=True, resultado=resultado, error=error)
            tarde = caja["cancelado"]
        if tarde and resultado is not None and hasattr(resultado, "cerrar"):
            resultado.cerrar()

    threading.Thread(target=correr, daemon=True, name="conectar").start()
    while True:
        with candado:
            if caja["listo"]:
                break
        for ev in pygame.event.get():
            motivo = None
            if ev.type == pygame.QUIT:
                motivo = "salir"
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                motivo = "menu"
            if motivo is not None:
                with candado:
                    if not caja["listo"]:
                        caja["cancelado"] = True
                        raise Cancelado(motivo)
        if dibujo is not None:
            dibujo()            # (la pantalla de espera del menú, con el código)
        else:
            aviso(pantalla, list(lineas) + ["(Esc para cancelar)"])
        pygame.display.flip()
        time.sleep(1 / 30)
    if caja["error"] is not None:
        raise caja["error"]
    return caja["resultado"]


class Sesion:
    """Una partida en red vista desde esta ventana. `paso()` hace un cuadro
    (eventos, entrada, dibujo); `jugar()` repite hasta que se acaba. Las
    pruebas llaman `paso()` a mano."""

    def __init__(self, juego, host, puerto, esquemas, avisar=print):
        self.g = juego
        self.host, self.puerto = host, puerto
        self.esquemas = list(esquemas)
        self.avisar = avisar
        self.conexiones = []
        self.espejo = None
        self.entrada = None
        self.simple = None
        self.motivo = None          # por qué terminó (None mientras sigue)
        # fn(pantalla, sesion, título): la pantalla de espera del menú de
        # Jugar en red (lanzador.py, con el código de la partida). Sin ella,
        # un aviso de texto.
        self.dibujar_espera = None
        self.error_dibujo = None    # el último error del espejo (para las pruebas)
        self.anfitrion = False      # esta laptop creó la partida (el servidor es suyo)
        self.con_sala = False       # se eligió rol en la sala (servidor --elegir-roles)
        self.carga = None           # la pantalla de carga: {"inicio", "consejo", "roles"}
        self.errores_vistos = {}    # firma del error -> cuántas veces

    def conectar(self, pantalla=None):
        for i in range(len(self.esquemas)):
            nueva = (lambda k=i: Conexion(self.host, self.puerto, f"local {k + 1}"))
            try:
                if pantalla is not None:
                    dibujo = None
                    if self.dibujar_espera is not None:
                        dibujo = (lambda: self.dibujar_espera(pantalla, self, "Conectando..."))
                    conexion = _sin_congelar(pantalla, [f"Conectando a {self.host}:{self.puerto}...",
                                                        f"Jugador local {i + 1} de {len(self.esquemas)}"],
                                             nueva, dibujo)
                else:
                    conexion = nueva()
                self.conexiones.append(conexion)
            except Rechazado as error:
                # Ya entró al menos uno y la partida se llenó: se juega con
                # los que cupieron (antes se iba todo al suelo con "la partida
                # ya tiene sus N jugadores").
                if not self.conexiones or "ya tiene sus" not in str(error):
                    raise
                self.avisar(f"solo cupieron {len(self.conexiones)} de esta laptop: {error}")
                self.esquemas = self.esquemas[:len(self.conexiones)]
                break
        self.entrada = Entrada(self.esquemas, getattr(self.g, "mandos", None))
        if "roles" not in self.conexiones[0].bienvenida:
            # La sala: cada uno elige su rol y el servidor arma la nave.
            self.con_sala = True
            if pantalla is None:
                return          # (las pruebas llaman sala() y después crear_espejo())
            self.sala(pantalla)
        self.crear_espejo()

    def crear_espejo(self):
        from cliente_servidor.espejo import Espejo
        self.espejo = Espejo(self.g, self.conexiones[0].bienvenida)
        # {número de jugador: esquema de esta laptop}, para las pistas de
        # controles del espejo (Espejo.controles).
        self.controles = {c.jugador: e for c, e in zip(self.conexiones, self.esquemas)}
        self.avisar("conectado como " + ", ".join(f"J{c.jugador + 1}" for c in self.conexiones))

    def _en_otro_hilo(self, pantalla, trabajo, lineas, cancelar=None):
        """Corre `trabajo` en otro hilo mientras la ventana sigue dibujando y
        leyendo eventos. Esc (o cerrar la ventana) llama `cancelar` y sale con
        Cancelado sin esperar al hilo (el trabajo se entera por `cancelar`)."""
        resultado = {}

        def correr():
            try:
                resultado["ok"] = trabajo()
            except BaseException as error:        # (se relanza en este hilo)
                resultado["error"] = error
        hilo = threading.Thread(target=correr, daemon=True)
        hilo.start()
        while hilo.is_alive():
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                    self.motivo = "salir" if ev.type == pygame.QUIT else "menu"
                    if cancelar is not None:
                        cancelar()
                    raise Cancelado()
            aviso(pantalla, list(lineas) + ["", "Esc para cancelar"])
            pygame.display.flip()
            hilo.join(1 / 30)
        if "error" in resultado:
            raise resultado["error"]
        return resultado["ok"]

    # -- La sala: elegir rol y esperar a que se arme la nave ----------------------------

    def sala(self, pantalla, eventos=None):
        """Hasta que el servidor arma la nave (la `sala` trae los datos de la
        partida). Mientras tanto: esperar a los demás (con el código), elegir
        rol como en el modo local y la pantalla de carga del Cambiaformas.
        Esc vuelve al menú (Cancelado). `eventos`: para las pruebas, una
        función que devuelve los eventos de cada cuadro."""
        reloj = pygame.time.Clock()
        while True:
            primera = self.conexiones[0]
            if "roles" in primera.bienvenida:
                for c in self.conexiones[1:]:
                    if "roles" not in c.bienvenida:
                        c.bienvenida.update({k: v for k, v in primera.bienvenida.items()
                                             if k not in ("jugador", "token")})
                return
            if not any(c.viva for c in self.conexiones):
                raise Cancelado("fin" if primera.situacion == "fin" else "perdida")
            for ev in (eventos() if eventos is not None else pygame.event.get()):
                if ev.type == pygame.QUIT:
                    raise Cancelado("salir")
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    raise Cancelado("menu")
                self._evento_sala(ev)
            self._dibujar_sala(pantalla)
            if eventos is None:
                pygame.display.flip()
                reloj.tick(30)
            else:
                return              # (las pruebas llaman un cuadro a la vez)

    def _evento_sala(self, ev):
        """Flechas/WASD/stick mueven el cursor del rol; el botón de aceptar de
        cada uno confirma (o suelta), como en el modo local."""
        from entidades.jugador import TECLAS_POR_PUESTO
        acciones = []
        if ev.type == pygame.KEYDOWN:
            for i, esquema in enumerate(self.esquemas):
                teclas = TECLAS_POR_PUESTO[esquema]
                for accion in ("arriba", "abajo", "interactuar"):
                    if ev.key in teclas.get(accion, ()):
                        acciones.append((i, accion))
        elif ev.type in EVENTOS_MANDO and getattr(self.g, "mandos", None) is not None:
            for esquema, accion in self.g.mandos.evento(ev):
                if esquema in self.esquemas:
                    acciones.append((self.esquemas.index(esquema), accion))
        for i, accion in acciones:
            if i >= len(self.conexiones):
                continue
            if accion in ("arriba", "abajo"):
                self.conexiones[i]._enviar({"tipo": "rol", "mover": -1 if accion == "arriba" else 1})
            elif accion == "interactuar":
                self.conexiones[i]._enviar({"tipo": "rol", "ok": True})

    def _dibujar_sala(self, pantalla):
        primera = self.conexiones[0]
        with primera.candado:
            sala = primera.sala
            espera = primera.espera
        if sala is None or (espera and espera.get("faltan")):
            if self.dibujar_espera is not None:
                self.dibujar_espera(pantalla, self, "Esperando jugadores...")
            else:
                aviso(pantalla, ["Esperando jugadores...", self._texto_espera(), "", "Esc para cancelar"])
            return
        if sala.get("fase") == "roles":
            self._dibujar_roles(pantalla, sala)
        else:
            self._dibujar_carga(pantalla, [e.get("rol") for e in _lista_de(sala.get("roles"))])

    def _dibujar_roles(self, pantalla, sala):
        """La selección de rol del modo local (screens/seleccion.py), con una
        sección por jugador de ESTA laptop; los de la otra salen arriba."""
        from entidades.jugador import TECLAS_POR_PUESTO, NOMBRE_CONTROLES
        from juego.app import _nombre
        from juego.mandos import nombre_boton
        from screens.seleccion import render_roles
        from data.roles import ROLES
        nombres = [r["nombre"] for r in ROLES]
        mandos = getattr(self.g, "mandos", None)
        roles = _lista_de(sala.get("roles"))
        mios = []
        for conexion, esquema in zip(self.conexiones, self.esquemas):
            estado = roles[conexion.jugador] if conexion.jugador < len(roles) else {}
            teclas = TECLAS_POR_PUESTO[esquema]
            con_mando = mandos is not None and mandos.hay_mando(esquema)
            mios.append({
                "cursor": int(estado.get("cursor", 0)) % len(nombres),
                "listo": bool(estado.get("listo")), "rol": estado.get("rol"),
                "esquema": esquema, "numero": conexion.jugador,
                "controles": f"Mando {esquema - 1}" if con_mando else NOMBRE_CONTROLES[esquema],
                "tecla_mover": ("Stick" if con_mando else "Flechas" if pygame.K_UP in teclas["arriba"]
                                else f"{_nombre(teclas['arriba'][0])}/{_nombre(teclas['abajo'][0])}"),
                "tecla_ok": (nombre_boton("interactuar", mandos.tipo(esquema)) if con_mando
                             else _nombre(teclas["interactuar"][0])),
            })
        tomados = {e.get("rol") for e in roles if e.get("listo")}
        aqui = {c.jugador for c in self.conexiones}
        otros = []
        for i, e in enumerate(roles):
            if i not in aqui:
                otros.append(f"J{i + 1}: {e['rol']}" if e.get("listo") else f"J{i + 1}: eligiendo...")
        faltan = sum(1 for e in roles if not e.get("listo"))
        if not faltan:
            mensaje = "Todos listos. Armando la nave..."
        else:
            mensaje = f"Faltan {faltan} por elegir" if faltan > 1 else "Falta uno por elegir"
        if otros:
            mensaje += "   ·   Otra laptop: " + ", ".join(otros)
        ancho, alto = pantalla.get_size()
        from screens.partida import calcular_viewports
        render_roles(pantalla, calcular_viewports(ancho, alto, len(mios)), mios,
                     tomados=tomados, mensaje=mensaje, listo=not faltan)

    def _dibujar_carga(self, pantalla, roles=None):
        """La pantalla de carga del modo local: el Cambiaformas persigue a los
        personajes que eligieron, mientras se arma la nave."""
        from screens import carga as pantalla_carga
        if self.carga is None:
            import random
            from data.consejos_carga import CONSEJOS
            self.carga = {"inicio": time.perf_counter(), "consejo": random.choice(CONSEJOS), "roles": None}
        roles = [r for r in (roles or self.conexiones[0].bienvenida.get("roles") or self.carga["roles"] or [])
                 if r]
        if roles and roles != self.carga["roles"]:
            self.carga["roles"] = roles
            pantalla_carga.precargar(pantalla.get_height(), roles)
        ms = (time.perf_counter() - self.carga["inicio"]) * 1000
        # La barra va por tiempo (nadie sabe cuánto falta): se acerca al 95 %.
        progreso = 0.95 * (1 - 2.718 ** (-ms / 7000))
        pantalla_carga.render_carga(pantalla, ms, progreso, self.carga["consejo"], self.carga["roles"],
                                    titulo="Armando la nave")

    def preparar_espejo(self, pantalla=None):
        """Arma la partida espejo en otro hilo mientras se muestra un aviso
        (como la pantalla de carga del modo local). Esc aquí deja `motivo` en
        "menu": se termina de armar (el hilo está tocando el Game del juego y
        no se puede cortar a la mitad) y se vuelve al menú sin jugar."""
        hilo = threading.Thread(target=self._preparar, daemon=True)
        hilo.start()
        while hilo.is_alive():
            if pantalla is not None:
                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT:
                        self.motivo = "salir"
                    elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                        self.motivo = self.motivo or "menu"
                lineas = (["Cancelando..."] if self.motivo else
                          ["Armando la nave...", self._texto_espera(), "", "Esc para cancelar"])
                if self.con_sala and not self.motivo:
                    self._dibujar_carga(pantalla)
                elif self.dibujar_espera is not None and not self.motivo:
                    # (el menú de Jugar en red dibuja su pantalla: con el código)
                    self.dibujar_espera(pantalla, self, "Armando la nave...")
                else:
                    aviso(pantalla, lineas)
                pygame.display.flip()
            hilo.join(1 / 30)

    def _preparar(self):
        try:
            self.espejo.preparar()
            self._teclas_de_esta_laptop()
        except Exception as error:          # sin espejo se dibuja lo sencillo
            self.espejo.error = error
            self.avisar(f"el espejo no se pudo armar: {error!r}")

    def _teclas_de_esta_laptop(self):
        """Las pistas de la pantalla ("[E] Terminal NEXUS", "[Q] escoge tu
        habilidad") con las teclas que de verdad usa cada jugador AQUÍ. El
        espejo arma a J2 con las flechas (su puesto en el modo local), pero en
        la segunda laptop J2 juega con WASD (esquemas_para): le decía "[SHIFT
        DER]" y "Flechas" a alguien que juega con Q y W/S. Solo cambia lo que
        se dibuja: lo que se manda al servidor son acciones, no teclas."""
        from entidades.jugador import TECLAS_POR_PUESTO, NOMBRE_CONTROLES
        g = self.espejo.g
        mandos = getattr(self.g, "mandos", None)
        for conexion, esquema in zip(self.conexiones, self.esquemas):
            if not 0 <= conexion.jugador < len(g.jugadores):
                continue
            j = g.jugadores[conexion.jugador]
            j.esquema = esquema
            j.teclas = TECLAS_POR_PUESTO[esquema]
            j.con_mando = bool(mandos is not None and mandos.hay_mando(esquema))
            j.controles_nombre = (f"Mando {esquema - 1}" if j.con_mando else NOMBRE_CONTROLES[esquema])
            j.personaje.controles_nombre = j.controles_nombre

    def _texto_espera(self):
        espera = self.conexiones[0].espera or {}
        return (f"Conectado como " + ", ".join(f"J{c.jugador + 1}" for c in self.conexiones)
                + ((f"  ·  falta 1 jugador" if espera["faltan"] == 1 else f"  ·  faltan {espera['faltan']} jugadores")
                   if espera.get("faltan") else ""))

    def paso(self, pantalla, eventos=None):
        """Un cuadro. Devuelve False cuando la sesión terminó (ver `motivo`)."""
        eventos = pygame.event.get() if eventos is None else eventos
        estado_fin = None
        for ev in eventos:
            if ev.type == pygame.QUIT:
                self.motivo = "salir"
            elif (ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_RETURN,
                                                            pygame.K_KP_ENTER, pygame.K_SPACE)
                  and self._presentacion_abierta()):
                # La ventana que presenta un alien se cierra con Esc, Enter o
                # Espacio, como en el modo local. (Antes Esc aquí sacaba a esta
                # laptop de la partida: "el segundo jugador se desconectó".)
                if self.entrada is not None and self.entrada.pulsados:
                    self.entrada.pulsados[0].append("volver")
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                # En red no hay pausa: Esc saca a esta laptop de la partida.
                # Para que no pase sin querer, hay que pulsarlo dos veces...
                # salvo mientras se esperan jugadores: ahí no hay partida que
                # perder y la pantalla dice "Esc cancela" (antes había que
                # pulsarlo dos veces sin que nada lo dijera).
                ahora = time.time()
                if ahora - getattr(self, "_esc", 0) < 2.5 or not self._en_partida():
                    self.motivo = "menu"
                self._esc = ahora
            else:
                self.entrada.evento(ev)
        for conexion, (mantener, pulsar) in zip(self.conexiones, self.entrada.sacar()):
            conexion.mandar(mantener, pulsar, self._extra(conexion, pulsar))
        vivas = [c for c in self.conexiones if c.viva]
        if not vivas:
            c = self.conexiones[0]
            self.motivo = self.motivo or ("fin" if c.situacion == "fin" else "perdida")
        if self.motivo:
            return False
        conexion = next((c for c in vivas if c.ultimo_estado() is not None), vivas[0])
        secciones = conexion.ultimo_estado()
        if secciones is None or (not self.espejo.listo and self.espejo.error is None):
            if self.con_sala and all(c.espera is None or not c.espera.get("faltan") for c in vivas):
                self._dibujar_carga(pantalla)       # (ya están todos: falta la primera)
                return True
            # Quien creó la partida ve aquí la IP que tiene que escribir la
            # otra laptop (antes solo salía en el menú de Jugar en red).
            if self.dibujar_espera is not None:
                self.dibujar_espera(pantalla, self, "Esperando jugadores...")
                if time.time() - getattr(self, "_esc", 0) < 2.5:
                    self._cartel(pantalla, "Pulsa Esc otra vez para cancelar")
                return True
            aviso(pantalla, ["Esperando jugadores...", self._texto_espera()],
                  extra=getattr(self, "info_espera", ()) or ["Esc para cancelar"])
            return True
        glob = secciones.get("g", {})
        self._dibujar(pantalla, conexion, secciones)
        cortadas = [c for c in self.conexiones if c.situacion == "reconectando"]
        if cortadas:
            desde = min(c.reconectando_desde or time.time() for c in cortadas)
            quedan = max(0, int(RECONECTAR_S - (time.time() - desde)))
            self._cartel(pantalla, f"Se cortó la conexión: reconectando... ({quedan} s)  ·  Esc Esc sale")
        if glob.get("resultado"):
            self._resultado(pantalla, glob["resultado"], eventos)
        elif time.time() - getattr(self, "_esc", 0) < 2.5:
            self._cartel(pantalla, "Pulsa Esc otra vez para salir de la partida en red")
        return not self.motivo

    def _en_partida(self):
        return (self.espejo is not None and (self.espejo.listo or self.espejo.error is not None)
                and any(c.ultimo_estado() is not None for c in self.conexiones))

    def _extra(self, conexion, pulsar):
        """Con el minijuego del escondite, dónde VIO la aguja el jugador al
        presionar: el servidor juzga el acierto con eso. Si no, con el retraso
        de la red (y el wifi) apretaba con la aguja en la franja y le contaba
        fallo.

        También el tamaño de la vista de ese jugador EN ESTA LAPTOP: el
        servidor decide con eso si un alien ya "entró en su pantalla" (la
        ventana que lo presenta). Antes usaba el tamaño de su propia pantalla
        falsa, dividida entre todos los jugadores, y la ventana salía tarde."""
        extra = {}
        vista = self._vista_de(conexion)
        if vista is not None:
            extra["vista"] = vista
        if "interactuar" not in pulsar or self.espejo is None or not self.espejo.listo:
            return extra or None
        jugadores = self.espejo.g.jugadores
        if not 0 <= conexion.jugador < len(jugadores):
            return extra or None
        mj = getattr(jugadores[conexion.jugador], "minijuego", None)
        if mj is not None and hasattr(mj, "aguja"):
            extra["aguja"] = round(float(mj.aguja), 3)
        return extra or None

    def _vista_de(self, conexion):
        """[ancho, alto] de la vista de ese jugador en esta ventana (la misma
        cuenta que hace el dibujo: screens/partida.calcular_viewports)."""
        pantalla = pygame.display.get_surface()
        if pantalla is None or conexion not in self.conexiones:
            return None
        from screens.partida import calcular_viewports
        vistas = calcular_viewports(*pantalla.get_size(), len(self.conexiones))
        i = self.conexiones.index(conexion)
        return [vistas[i].width, vistas[i].height] if i < len(vistas) else None

    def _presentacion_abierta(self):
        g = getattr(self.espejo, "g", None) if self.espejo is not None else None
        p = getattr(g, "presentacion", None)
        return bool(p is not None and getattr(p, "abierta", False))

    def _dibujar(self, pantalla, conexion, secciones):
        locales = [c.jugador for c in self.conexiones]
        if self.espejo.error is None:
            try:
                with conexion.candado:
                    interpolado = conexion.interpolador.ahora()
                self.espejo.aplicar(secciones, interpolado)
                self.espejo.controles(getattr(self, "controles", {}))
                self.espejo.sonar(conexion.sacar_sonidos())
                self.espejo.dibujar(pantalla, locales)
                return
            except Exception as error:
                # Que algo que el espejo no sabe dibujar no tumbe la partida:
                # ESTE cuadro va con el dibujo sencillo y el siguiente se
                # vuelve a intentar con el espejo. (Antes se quedaba en el
                # sencillo para siempre: "todo perdió textura y el alien era
                # un punto rojo".) Cada error distinto se anota una vez.
                self.error_dibujo = error
                firma = f"{type(error).__name__}: {str(error)[:80]}"
                veces = self.errores_vistos.get(firma, 0)
                self.errores_vistos[firma] = veces + 1
                if veces == 0:
                    import traceback
                    traceback.print_exc()
                    self.avisar(f"el espejo falló ({firma}); ese cuadro va sencillo")
        if self.simple is None:
            from cliente_servidor.dibujo_simple import Dibujo
            self.simple = Dibujo(conexion.bienvenida)
        estado = legible(secciones)
        from cliente_servidor.dibujo_simple import vistas
        self.simple.animar(estado)
        pantalla.fill((0, 0, 0))
        rects = vistas(*pantalla.get_size(), len(locales))
        for rect, c in zip(rects, self.conexiones):
            self.simple.vista(pantalla, rect, estado, c.jugador, c)
        self.simple.encima(pantalla, estado)

    def _cartel(self, pantalla, texto):
        from juego.fuentes import fuente
        imagen = fuente("small").render(texto, True, (255, 230, 140))
        caja = imagen.get_rect(midtop=(pantalla.get_width() // 2, 12)).inflate(24, 12)
        pygame.draw.rect(pantalla, (16, 20, 34), caja)
        pygame.draw.rect(pantalla, (240, 200, 90), caja, 2)
        pantalla.blit(imagen, imagen.get_rect(center=caja.center))

    def _resultado(self, pantalla, resultado, eventos):
        """La pantalla de resultados del modo local (con el espejo); Enter vuelve al menú."""
        try:
            if self.espejo.error is not None:
                raise RuntimeError("sin espejo")
            self.espejo.dibujar_resultados(pantalla)
        except Exception:
            aviso(pantalla, ["¡ESCAPARON!" if resultado == "victoria" else "DERROTA"])
        self._cartel(pantalla, "Partida en red terminada: Enter para volver al menú")
        for ev in eventos:
            if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.motivo = "terminada"
            elif ev.type in (pygame.JOYBUTTONDOWN, getattr(pygame, "CONTROLLERBUTTONDOWN", -1)):
                self.motivo = "terminada"

    def jugar(self, pantalla):
        reloj = pygame.time.Clock()
        while True:
            reloj.tick(60)
            sigue = self.paso(pantalla)
            pygame.display.flip()
            if not sigue:
                break
        self.cerrar()
        if self.motivo in ("perdida", "fin"):
            c = self.conexiones[0]
            texto = c.fin_texto or "Se perdió la conexión con el servidor."
            _esperar_tecla(pantalla, [texto, "Volviendo al menú..."])
        return self.motivo

    def cerrar(self):
        if self.anfitrion and self.conexiones:
            # El servidor es de esta laptop: que avise `fin` a las otras ya
            # (en la sala todavía no vigila al juego que lo levantó).
            self.conexiones[0]._enviar({"tipo": "cerrar_partida"})
        for c in self.conexiones:
            c.cerrar()
        # Que el estado de la red no se quede apuntando al espejo de esta
        # partida (y con él a toda la partida) cuando se vuelve al menú.
        from cliente_servidor import estado as E
        if self.espejo is not None and getattr(E.RESOLVER, "__self__", None) is self.espejo:
            E.RESOLVER = None
        E.nueva_pasada()


def jugar(juego, host, puerto, esquemas, avisar=print, info_espera=(), dibujar_espera=None,
          anfitrion=False):
    """Todo junto, en la ventana del juego: conectar, armar el espejo, jugar.
    Devuelve el motivo del final ("menu", "salir", "terminada", "perdida",
    "fin" o "error"). `info_espera`: líneas de más para la pantalla de
    "Esperando jugadores" (la IP de esta laptop, si la partida es de aquí)."""
    pantalla = juego.screen
    sesion = Sesion(juego, host, puerto, esquemas, avisar)
    sesion.info_espera = list(info_espera)
    sesion.dibujar_espera = dibujar_espera
    sesion.anfitrion = anfitrion
    try:
        sesion.conectar(pantalla)
    except Cancelado as cancelado:
        sesion.cerrar()
        return cancelado.motivo
    except (OSError, ConexionCerrada) as error:
        avisar(f"no se pudo conectar: {error}")
        sesion.cerrar()
        _esperar_tecla(pantalla, ["No se pudo conectar al servidor.", _explicar(error)])
        return "error"
    sesion.preparar_espejo(pantalla)
    if sesion.motivo:                       # Esc mientras se armaba la nave
        sesion.cerrar()
        return sesion.motivo
    return sesion.jugar(pantalla)


def _explicar(error):
    """El error de conexión en palabras de la feria."""
    if isinstance(error, Rechazado):
        return str(error)[:70]
    if isinstance(error, ConnectionRefusedError):
        return "En esa IP no hay ninguna partida abierta (¿ya la crearon?)."
    if isinstance(error, (socket.timeout, TimeoutError)):
        return "Esa IP no contesta: revisa que estén en el mismo wifi."
    if isinstance(error, socket.gaierror):
        return "Esa IP está mal escrita."
    return str(error)[:70]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Cliente de NEXUS (una ventana, un socket por jugador).")
    ap.add_argument("--jugadores", type=int, default=2, choices=(1, 2, 3, 4),
                    help="cuántos juegan en ESTA ventana")
    ap.add_argument("--host", default=HOST)
    ap.add_argument("--puerto", type=int, default=PUERTO)
    ap.add_argument("--mandos", action="store_true", help="los primeros jugadores con mando")
    ap.add_argument("--ventana", default="1280x720", help="tamaño, p. ej. 1600x900")
    args = ap.parse_args(argv)
    ancho, alto = (int(v) for v in args.ventana.lower().split("x"))

    from juego.app import Game
    g = Game()
    g.pantalla_completa = False
    g.screen = pygame.display.set_mode((ancho, alto))
    g._aplicar_tamano()
    pygame.display.set_caption("NEXUS (red)")
    motivo = jugar(g, args.host, args.puerto, esquemas_para(args.jugadores, args.mandos),
                   avisar=lambda texto: print("[cliente]", texto, flush=True))
    pygame.quit()
    return 0 if motivo in ("menu", "salir", "terminada") else 1


if __name__ == "__main__":
    sys.exit(main())
