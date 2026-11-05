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
                                        ConexionCerrada, enviar, sin_nagle, Reconstructor, legible)
from cliente_servidor.interpolacion import Interpolador

# Cada cuánto se repite la intención aunque no cambie (por si se perdió algo).
REPETIR_INTENCION_S = 0.1
# Sin noticias del servidor en este tiempo, la conexión se da por caída
# (el servidor manda algo cada 33 ms, o cada 250 ms mientras espera).
SILENCIO_S = 3.0
# Cuánto se intenta volver después de un corte.
RECONECTAR_S = 10.0


class Rechazado(ConexionCerrada):
    """El servidor contestó `error` al saludo (partida llena, token de otra
    partida, otra versión): no vale la pena reintentar."""


class Conexion:
    """El socket de UN jugador local, más el hilo que lee sus instantáneas."""

    def __init__(self, host, puerto, nombre, esperar_s=15.0, saludo_s=60.0):
        self.host, self.puerto, self.nombre = host, puerto, nombre
        self.candado = threading.Lock()
        self.reconstructor = Reconstructor()
        self.interpolador = Interpolador()
        self.estado = None            # la última instantánea completa (secciones)
        self.cuadro = None
        self.espera = None            # el último aviso de "faltan jugadores"
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
        self.jugador = self.bienvenida["jugador"]
        self.token = self.bienvenida.get("token")
        self.situacion = "jugando"
        threading.Thread(target=self._leer, daemon=True,
                         name=f"lector-J{self.jugador + 1}").start()

    @property
    def viva(self):
        return self.situacion in ("jugando", "reconectando")

    def _saludar(self, esperar_s, saludo_s):
        sock = _conectar(self.host, self.puerto, esperar_s)
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
            sock.close()
            if bienvenida.get("tipo") == "error":
                raise Rechazado(bienvenida.get("texto", "el servidor no lo dejó entrar"))
            raise ConexionCerrada("el servidor no dio la bienvenida")
        sock.settimeout(SILENCIO_S)
        return sock, lector, bienvenida

    def _leer(self):
        while not self.cerrando:
            try:
                while True:
                    mensaje = self.lector.siguiente()
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
        elif tipo == "fin":
            self.fin_texto = mensaje.get("texto", "")
            self.situacion = "fin"
            return True
        return False

    def _reconectar(self):
        """Vuelve con el token: el servidor le devuelve su mismo jugador."""
        self.situacion = "reconectando"
        try:
            self.sock.close()
        except OSError:
            pass
        limite = time.time() + RECONECTAR_S
        while time.time() < limite and not self.cerrando:
            try:
                self.sock, self.lector, _ = self._saludar(1.0, 5.0)
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
        try:
            enviar(self.sock, mensaje)
        except OSError:
            pass                       # el lector se da cuenta y reconecta

    def mandar(self, mantener, pulsar):
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
        self._enviar({"tipo": "intencion", "n": self.n, "mantener": mantener, "pulsar": pulsar})

    def cortar(self):
        """Corta el socket sin avisar (para probar la reconexión)."""
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def cerrar(self):
        self.cerrando = True
        self._enviar({"tipo": "adios"})
        try:
            self.sock.close()
        except OSError:
            pass


def _conectar(host, puerto, esperar_s):
    """Reintenta un rato: así se puede abrir el cliente antes que el servidor."""
    limite = time.time() + esperar_s
    while True:
        try:
            return socket.create_connection((host, puerto), timeout=3)
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
        elif ev.type in (pygame.JOYBUTTONDOWN, pygame.JOYHATMOTION, pygame.JOYAXISMOTION,
                         pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
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
            if ev.type in (pygame.KEYDOWN, pygame.JOYBUTTONDOWN, pygame.QUIT):
                return
        aviso(pantalla, lineas)
        pygame.display.flip()
        time.sleep(1 / 30)


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
        self.error_dibujo = None

    def conectar(self, pantalla=None):
        for i in range(len(self.esquemas)):
            if pantalla is not None:
                aviso(pantalla, [f"Conectando a {self.host}:{self.puerto}...",
                                 f"Jugador local {i + 1} de {len(self.esquemas)}"])
                pygame.display.flip()
                pygame.event.pump()
            try:
                self.conexiones.append(Conexion(self.host, self.puerto, f"local {i + 1}"))
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
        from cliente_servidor.espejo import Espejo
        self.espejo = Espejo(self.g, self.conexiones[0].bienvenida)
        self.avisar("conectado como " + ", ".join(f"J{c.jugador + 1}" for c in self.conexiones))

    def preparar_espejo(self, pantalla=None):
        """Arma la partida espejo en otro hilo mientras se muestra un aviso
        (como la pantalla de carga del modo local)."""
        hilo = threading.Thread(target=self._preparar, daemon=True)
        hilo.start()
        while hilo.is_alive():
            if pantalla is not None:
                pygame.event.pump()
                aviso(pantalla, ["Armando la nave...", self._texto_espera()])
                pygame.display.flip()
            hilo.join(1 / 30)

    def _preparar(self):
        try:
            self.espejo.preparar()
        except Exception as error:          # sin espejo se dibuja lo sencillo
            self.espejo.error = error
            self.avisar(f"el espejo no se pudo armar: {error!r}")

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
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                self.motivo = "menu"
            else:
                self.entrada.evento(ev)
        for conexion, (mantener, pulsar) in zip(self.conexiones, self.entrada.sacar()):
            conexion.mandar(mantener, pulsar)
        vivas = [c for c in self.conexiones if c.viva]
        if not vivas:
            c = self.conexiones[0]
            self.motivo = self.motivo or ("fin" if c.situacion == "fin" else "perdida")
        if self.motivo:
            return False
        conexion = next((c for c in vivas if c.ultimo_estado() is not None), vivas[0])
        secciones = conexion.ultimo_estado()
        if secciones is None or (not self.espejo.listo and self.espejo.error is None):
            # Quien creó la partida ve aquí la IP que tiene que escribir la
            # otra laptop (antes solo salía en el menú de Jugar en red).
            aviso(pantalla, ["Esperando jugadores...", self._texto_espera()],
                  extra=getattr(self, "info_espera", ()))
            return True
        glob = secciones.get("g", {})
        self._dibujar(pantalla, conexion, secciones)
        if any(c.situacion == "reconectando" for c in self.conexiones):
            self._cartel(pantalla, "Se cortó la conexión: reconectando...")
        if glob.get("resultado"):
            self._resultado(pantalla, glob["resultado"], eventos)
        return not self.motivo

    def _dibujar(self, pantalla, conexion, secciones):
        locales = [c.jugador for c in self.conexiones]
        if self.espejo.error is None and self.error_dibujo is None:
            try:
                with conexion.candado:
                    interpolado = conexion.interpolador.ahora()
                self.espejo.aplicar(secciones, interpolado)
                self.espejo.sonar(conexion.sacar_sonidos())
                self.espejo.dibujar(pantalla, locales)
                return
            except Exception as error:
                # Que un panel que el espejo no sabe dibujar no tumbe la
                # partida: se sigue con el dibujo sencillo y se anota.
                import traceback
                traceback.print_exc()
                self.error_dibujo = error
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
            elif ev.type == pygame.JOYBUTTONDOWN:
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
        for c in self.conexiones:
            c.cerrar()


def jugar(juego, host, puerto, esquemas, avisar=print, info_espera=()):
    """Todo junto, en la ventana del juego: conectar, armar el espejo, jugar.
    Devuelve el motivo del final ("menu", "salir", "terminada", "perdida",
    "fin" o "error"). `info_espera`: líneas de más para la pantalla de
    "Esperando jugadores" (la IP de esta laptop, si la partida es de aquí)."""
    pantalla = juego.screen
    sesion = Sesion(juego, host, puerto, esquemas, avisar)
    sesion.info_espera = list(info_espera)
    try:
        sesion.conectar(pantalla)
    except (OSError, ConexionCerrada) as error:
        avisar(f"no se pudo conectar: {error}")
        sesion.cerrar()
        _esperar_tecla(pantalla, ["No se pudo conectar al servidor.", str(error)[:60]])
        return "error"
    sesion.preparar_espejo(pantalla)
    return sesion.jugar(pantalla)


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
