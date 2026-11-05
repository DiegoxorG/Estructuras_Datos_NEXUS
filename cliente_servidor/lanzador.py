"""Menú > Jugar en red: crear una partida en esta laptop o unirse a otra.

Es una pantalla aparte con su propio bucle (no toca el flujo del modo local):

- Inicio: dos tarjetas grandes, "Crear partida" y "Unirse a una partida".
- Crear: cuántos juegan en total y cuántos en esta laptop (con un dibujito
  de quién va en cada laptop), controles y dificultad. Levanta el servidor en
  OTRO proceso (`python -m cliente_servidor.servidor --host 0.0.0.0`) y
  muestra el CÓDIGO de la partida en grande mientras espera.
- Unirse: la lista de partidas que se anuncian en este wifi (el servidor las
  grita por UDP: servidor._anunciar) para entrar sin escribir nada, o el
  código de 4-6 letras que sale en la pantalla de la otra laptop.

El código es la IP de la laptop que creó la partida (y el puerto) escrita en
pocas letras (`codigo_de` / `direccion_de_codigo`): 192.168.43.17 -> "AB3K".
Se puede escribir también la IP de siempre.

Se maneja con teclado (flechas, Enter, Esc, escribir), mouse o mando.
"""

import collections
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time

import pygame

from cliente_servidor.protocolo import PUERTO
from cliente_servidor import cliente

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIFICULTADES = ["facil", "normal", "dificil"]
EXTRA_SERVIDOR = ()     # opciones de más para el servidor (las pruebas: --mapa Nave...)
NOMBRE_DIFICULTAD = {"facil": "Fácil", "normal": "Normal", "dificil": "Difícil"}


def ip_local():
    """La IP de esta laptop en la red local (la que hay que darle a la otra).
    Conectar un socket UDP no manda nada: solo hace que el sistema escoja la
    interfaz de salida."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def ips_locales():
    """Todas las IPv4 de esta laptop que sirven para la red local, la de
    salida primero. Puede haber varias (wifi, cable, adaptadores virtuales de
    VirtualBox o WSL): se muestran todas para que la otra laptop pruebe."""
    ips = []
    principal = ip_local()
    if principal and not principal.startswith("127."):
        ips.append(principal)
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith(("127.", "169.254.")):
                ips.append(ip)
    except OSError:
        pass
    return ips or ["127.0.0.1"]


def leer_direccion(texto):
    """"192.168.43.10" o "192.168.43.10:5051" -> (host, puerto). ValueError
    con lo que hay que decirle al jugador si está mal escrita. Antes se
    probaba cualquier cosa: "192.168.1" (un número de menos) es para el
    sistema 192.168.0.1 y se quedaba 15 s intentando otra máquina."""
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("Escribe la IP de la laptop que creó la partida")
    host, _, puerto = texto.partition(":")
    partes = host.split(".")
    if len(partes) != 4 or not all(p.isdigit() and int(p) <= 255 for p in partes):
        raise ValueError(f"La IP {host!r} está mal escrita: son 4 números del 0 al 255 con punto "
                         f"(p. ej. 192.168.43.10)")
    if not puerto:
        return host, PUERTO
    if not puerto.isdigit() or not 1 <= int(puerto) <= 65535:
        raise ValueError(f"El puerto {puerto!r} está mal escrito (va de 1 a 65535)")
    return host, int(puerto)


def puerto_libre(puerto, host="0.0.0.0"):
    """¿Se puede abrir el servidor en `puerto`? (como lo abre el servidor)"""
    prueba = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name != "nt":
            prueba.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        elif hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            prueba.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        prueba.bind((host, puerto))
        return True
    except OSError:
        return False
    finally:
        prueba.close()


# Si el 5050 está ocupado (otra partida abierta en esta laptop, otro programa)
# se prueba con los que siguen; la pantalla de espera dice cuál quedó.
PUERTOS_DE_MAS = 3


def levantar_servidor(jugadores, dificultad, puerto=PUERTO, host="0.0.0.0", extra=()):
    """El servidor en otro proceso. Devuelve (proceso, puerto) cuando ya
    escucha, o (None, texto del error)."""
    # --con-padre y stdin=PIPE: el servidor se apaga (avisando `fin`) cuando
    # este proceso le cierra la entrada, o cuando este proceso se muere (el
    # sistema la cierra solo). Ver servidor.vigilar_padre y cerrar_servidor.
    # La salida va en UTF-8 de los dos lados: en Windows el texto de un tubo
    # va con la página de códigos del sistema y un nombre raro en el `hola`
    # tumbaba el print del servidor.
    entorno = dict(os.environ, PYTHONIOENCODING="utf-8")
    proceso = subprocess.Popen(
        [sys.executable, "-u", "-m", "cliente_servidor.servidor", "--jugadores", str(jugadores),
         "--host", host, "--puerto", str(puerto), "--dificultad", dificultad, "--con-padre", *extra],
        cwd=RAIZ, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", env=entorno)
    limite = time.time() + 20
    ultimas = []
    while time.time() < limite:
        linea = proceso.stdout.readline()
        if not linea:
            break
        ultimas = (ultimas + [linea.strip()])[-3:]
        if "escuchando en" in linea:
            puerto = int(linea.split("escuchando en ")[1].split()[0].rsplit(":", 1)[1])
            _seguir_salida(proceso, ultimas)
            return proceso, puerto
    proceso.kill()
    proceso.wait()
    if any("Address already in use" in l or "Errno 98" in l or "10048" in l for l in ultimas):
        return None, f"El puerto {puerto} ya está ocupado (¿otra partida abierta en esta laptop?)"
    return None, "el servidor no arrancó (¿el puerto ya está ocupado?)"


# Lo que dice el servidor también queda en este archivo: si algo falla en la
# laptop de alguien, ahí está el error completo aunque no haya terminal.
# (Guardado/ no va a git.)
REGISTRO = os.path.join(RAIZ, "Guardado", "nexus_servidor.log")


def _seguir_salida(proceso, primeras=()):
    """Un hilo lee TODO lo que dice el servidor (si nadie lo lee, el tubo se
    llena y el servidor se queda trabado en un print), lo muestra en la
    terminal, lo guarda en REGISTRO y avisa con `proceso.lista` cuando la
    partida ya está armada. `proceso.salida`: las últimas líneas."""
    proceso.lista = threading.Event()
    proceso.salida = collections.deque(primeras, maxlen=60)
    try:
        os.makedirs(os.path.dirname(REGISTRO), exist_ok=True)
        registro = open(REGISTRO, "w", encoding="utf-8")
        registro.write("\n".join(primeras) + "\n")
    except OSError:
        registro = None

    def leer():
        for linea in proceso.stdout:
            proceso.salida.append(linea.rstrip())
            if "partida lista" in linea:
                proceso.lista.set()
            # (un print que falla, sin terminal o con un carácter que la
            # consola no tiene, no puede matar a este hilo)
            try:
                print(linea, end="", flush=True)
            except Exception:
                pass
            if registro is not None:
                try:
                    registro.write(linea)
                    registro.flush()
                except (OSError, ValueError):
                    pass
        if registro is not None:
            registro.close()
    threading.Thread(target=leer, daemon=True, name="salida-servidor").start()


def _error_del_servidor(proceso):
    """La última línea que explica por qué se cayó el servidor."""
    lineas = []
    for linea in getattr(proceso, "salida", ()):
        if linea.startswith("Fatal Python error"):
            break               # (lo que Python dice al morir, no el error)
        if linea.strip():
            lineas.append(linea.strip())
    for linea in reversed(lineas):
        # (la última línea de un traceback: "NombreError: lo que pasó")
        if re.match(r"^[\w.]+(Error|Exception|Exit)\b", linea):
            return linea[:120]
    return lineas[-1].strip()[:120] if lineas else "sin mensaje"


def cerrar_servidor(proceso):
    """Apaga el servidor que levantó esta laptop, avisando `fin` a los de
    las otras: se le cierra la entrada (servidor.vigilar_padre), que sirve
    igual en Windows, Linux y Mac. Si no responde, Ctrl+C (Linux/Mac) o
    terminate, y al final kill. (Ojo: SIGTERM antes de pygame.init lo mata,
    después lo atrapa SDL; el servidor ahora lo atrapa él mismo.)"""
    try:
        proceso.stdin.close()
    except (OSError, ValueError, AttributeError):
        pass
    try:
        proceso.wait(3)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        if os.name != "nt":
            proceso.send_signal(signal.SIGINT)
        else:
            proceso.terminate()
        proceso.wait(2)
    except (OSError, subprocess.TimeoutExpired):
        proceso.kill()
        try:
            proceso.wait(2)
        except subprocess.TimeoutExpired:
            pass


def direccion(texto):
    """La IP (y el puerto) que escribieron para unirse: (host, puerto) o
    (None, por qué no sirve). Antes una IP con dos puntos seguidos
    ("192.168..1") tumbaba el juego entero (UnicodeError del idna, que no es
    OSError) y una mal escrita ("1.2.3.4.5") dejaba la ventana congelada
    ~15 s reintentando."""
    import ipaddress
    texto = (texto or "").strip() or "127.0.0.1"
    host, _, puerto = texto.partition(":")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return None, f"La IP \"{host}\" está mal escrita (ejemplo: 192.168.1.20)"
    if ip.version != 4:
        return None, "Solo IP de 4 números (ejemplo: 192.168.1.20)"
    if not puerto:
        return str(ip), PUERTO
    if not puerto.isdigit() or not 1 <= int(puerto) <= 65535:
        return None, f"El puerto \"{puerto}\" no sirve (de 1 a 65535)"
    return str(ip), int(puerto)


# -- El código de la partida --------------------------------------------------------

# Base 32 de Crockford: sin I, L, O ni U, para que no se confundan al dictarlo.
ALFABETO = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_PARECIDAS = {"O": "0", "I": "1", "L": "1", "U": "V"}


def codigo_de(ip, puerto=PUERTO):
    """La IP (y el puerto, si es uno de los 4 del juego) en pocas letras.

    Las redes de casa y de los hotspots tienen IPs con prefijos conocidos, así
    que solo se guarda lo que cambia: 192.168.x.y -> 4 letras, 172.16-31.x.y
    (hotspot de iPhone) -> 5, 10.x.y.z -> 6, cualquier otra -> 8. Los 2 bits
    de abajo dicen el prefijo y los 2 siguientes el puerto (5050-5053)."""
    a, b, c, d = (int(x) for x in ip.split("."))
    extra = puerto - PUERTO
    if not 0 <= extra <= 3:
        return None
    if a == 192 and b == 168:
        prefijo, valor, bits = 0, (c << 8) | d, 16
    elif a == 172 and 16 <= b <= 31:
        prefijo, valor, bits = 1, ((b - 16) << 16) | (c << 8) | d, 20
    elif a == 10:
        prefijo, valor, bits = 2, (b << 16) | (c << 8) | d, 24
    else:
        prefijo, valor, bits = 3, (a << 24) | (b << 16) | (c << 8) | d, 32
    numero = (((valor << 2) | extra) << 2) | prefijo
    letras = -(-(bits + 4) // 5)
    texto = ""
    for _ in range(letras):
        texto = ALFABETO[numero & 31] + texto
        numero >>= 5
    return texto


def direccion_de_codigo(texto):
    """Lo inverso: el código (o una IP escrita) -> (host, puerto) o
    (None, por qué no sirve)."""
    texto = (texto or "").strip().upper().replace("-", "").replace(" ", "")
    if not texto:
        return None, "Escribe el código que sale en la pantalla de la otra laptop"
    if "." in texto:
        return direccion(texto)
    numero = 0
    for letra in texto:
        letra = _PARECIDAS.get(letra, letra)
        if letra not in ALFABETO:
            return None, f"El código no lleva \"{letra}\": revisa las letras"
        numero = numero * 32 + ALFABETO.index(letra)
    prefijo, numero = numero & 3, numero >> 2
    extra, valor = numero & 3, numero >> 2
    largo = {0: 4, 1: 5, 2: 6, 3: 8}[prefijo]
    if len(texto) != largo:
        return None, "Ese código está incompleto o le sobran letras"
    if prefijo == 0:
        ip = f"192.168.{valor >> 8 & 255}.{valor & 255}"
    elif prefijo == 1:
        ip = f"172.{16 + (valor >> 16 & 15)}.{valor >> 8 & 255}.{valor & 255}"
    elif prefijo == 2:
        ip = f"10.{valor >> 16 & 255}.{valor >> 8 & 255}.{valor & 255}"
    else:
        ip = f"{valor >> 24 & 255}.{valor >> 16 & 255}.{valor >> 8 & 255}.{valor & 255}"
    return ip, PUERTO + extra


def con_guion(codigo):
    """"AB3KQ7" -> "AB3-KQ7" (más fácil de leer y dictar)."""
    if not codigo or len(codigo) <= 4:
        return codigo or ""
    mitad = (len(codigo) + 1) // 2
    return codigo[:mitad] + "-" + codigo[mitad:]


# -- Buscar partidas en la red ---------------------------------------------------------

class Buscador:
    """Escucha los anuncios de partidas (servidor._anunciar) en otro hilo.
    `partidas()`: las que se oyeron en los últimos segundos."""

    def __init__(self):
        from cliente_servidor.protocolo import PUERTO_ANUNCIO
        self.vistas = {}            # (ip, puerto) -> (datos, cuándo)
        self.candado = threading.Lock()
        self.activo = True
        self.error = None
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("", PUERTO_ANUNCIO))
            self.sock.settimeout(0.5)
        except OSError as error:
            self.sock, self.error = None, error
            return
        threading.Thread(target=self._escuchar, daemon=True, name="buscador").start()

    def _escuchar(self):
        import json
        from cliente_servidor.protocolo import VERSION
        while self.activo:
            try:
                datos, (ip, _) = self.sock.recvfrom(2048)
                anuncio = json.loads(datos.decode("utf-8"))
            except socket.timeout:
                continue
            except (OSError, ValueError):
                if not self.activo:
                    return
                continue
            if not isinstance(anuncio, dict) or anuncio.get("nexus") != VERSION:
                continue
            puerto = anuncio.get("puerto")
            if not isinstance(puerto, int):
                continue
            with self.candado:
                self.vistas[(ip, puerto)] = (anuncio, time.time())

    def partidas(self):
        """[(ip, puerto, anuncio)] de las que se oyeron hace poco."""
        ahora = time.time()
        with self.candado:
            return sorted(((ip, p, a) for (ip, p), (a, t) in self.vistas.items() if ahora - t < 3.5),
                          key=lambda x: (x[2].get("nombre", ""), x[0]))

    def cerrar(self):
        self.activo = False
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass


# -- La pantalla -------------------------------------------------------------------------

AZUL_FONDO = (10, 12, 24)
PANEL = (20, 24, 44)
PANEL_MARCADO = (30, 40, 74)
BORDE = (56, 66, 110)
CIAN = (110, 220, 255)
ROSA = (233, 120, 200)
VERDE = (110, 220, 140)
AMARILLO = (255, 214, 120)
TEXTO = (232, 236, 250)
TENUE = (150, 158, 190)


class MenuRed:
    """Lo que se eligió en las pantallas y en qué pantalla va."""

    def __init__(self):
        self.pantalla = "inicio"          # inicio, crear, unirse
        self.foco = 0
        self.total = 2                    # jugadores en la partida
        # Cuántos juegan en esta laptop. Empieza en 1: con 2 de 2 la partida
        # se llenaba aquí mismo y la otra laptop no podía unirse.
        self.locales = 1
        # (Con qué control juega cada uno ya no se elige aquí: antes de
        # entrar, cada jugador presiona el botón del suyo, _elegir_controles.)
        self.dificultad = "normal"
        self.codigo = ""                  # lo que se escribe para unirse
        self.ip = ""                      # (compatibilidad: una IP escrita)
        self.ip_propia = ip_local()
        self.elegida = None               # (ip, puerto, anuncio) de la lista
        self.buscador = None
        self.rects = []                   # [(rect, índice del elemento)] del último dibujo

    # -- Qué hay en cada pantalla -------------------------------------------------------

    def elementos(self):
        """[(tipo, clave, texto)] de la pantalla actual, en orden de foco."""
        if self.pantalla == "inicio":
            return [("tarjeta", "a_crear", "Crear partida"), ("tarjeta", "a_unirse", "Unirse a una partida"),
                    ("boton", "volver", "Volver al menú")]
        if self.pantalla == "crear":
            return [("opcion", "total", f"{self.total}"),
                    ("opcion", "locales", f"{self.locales}"),
                    ("opcion", "dificultad", NOMBRE_DIFICULTAD[self.dificultad]),
                    ("boton", "crear", "Crear partida"), ("boton", "atras", "Atrás")]
        partidas = self.buscador.partidas() if self.buscador is not None else []
        lista = [("partida", (ip, p, a), "") for ip, p, a in partidas[:4]]
        return lista + [("campo", "codigo", self.codigo),
                        ("opcion", "locales", f"{self.locales}"),
                        ("boton", "unirse", "Unirse con el código"), ("boton", "atras", "Atrás")]

    def ir(self, pantalla):
        self.pantalla, self.foco = pantalla, 0
        if pantalla == "unirse" and self.buscador is None:
            self.buscador = Buscador()
        if pantalla == "unirse":
            # El foco empieza en el código si no hay partidas en la lista.
            tipos = [t for t, _, _ in self.elementos()]
            self.foco = 0 if tipos[0] == "partida" else tipos.index("campo")

    def cerrar(self):
        if self.buscador is not None:
            self.buscador.cerrar()
            self.buscador = None

    def cambiar(self, clave, paso):
        if clave == "total":
            self.total = min(4, max(2, self.total + paso))
            self.locales = min(self.locales, self.total)
        elif clave == "locales":
            tope = self.total if self.pantalla == "crear" else 3
            self.locales = min(tope, max(1, self.locales + paso))
        elif clave == "dificultad":
            i = DIFICULTADES.index(self.dificultad)
            self.dificultad = DIFICULTADES[(i + paso) % len(DIFICULTADES)]

    # -- Entrada ----------------------------------------------------------------------

    def accion(self, que, texto=""):
        """Una acción ("arriba", "abajo", "izquierda", "derecha", "ok",
        "volver", "borrar", "escribir"). Devuelve "crear", ("unirse", host,
        puerto), "salir" o None."""
        elementos = self.elementos()
        self.foco = min(self.foco, len(elementos) - 1)
        tipo, clave, _ = elementos[self.foco]
        if que == "volver":
            if self.pantalla == "inicio":
                return "salir"
            self.ir("inicio")
        elif que == "arriba":
            self.foco = (self.foco - 1) % len(elementos)
        elif que == "abajo":
            self.foco = (self.foco + 1) % len(elementos)
        elif que in ("izquierda", "derecha"):
            if tipo == "opcion":
                self.cambiar(clave, -1 if que == "izquierda" else 1)
            elif self.pantalla == "inicio" and tipo == "tarjeta":
                self.foco = 1 - self.foco if self.foco in (0, 1) else self.foco
        elif que == "borrar" and tipo == "campo":
            self.codigo = self.codigo[:-1]
        elif que == "escribir":
            if self.pantalla == "unirse" and texto and (texto.isalnum() or texto in ".:-"):
                if tipo != "campo":
                    self.foco = [t for t, _, _ in elementos].index("campo")
                self.codigo = (self.codigo + texto.upper())[:21]
        elif que == "ok":
            return self._elegir(tipo, clave)
        return None

    def _elegir(self, tipo, clave):
        if clave == "a_crear":
            self.ir("crear")
        elif clave == "a_unirse":
            self.ir("unirse")
        elif clave == "volver":
            return "salir"
        elif clave == "atras":
            self.ir("inicio")
        elif clave == "crear":
            return "crear"
        elif tipo == "partida":
            ip, puerto, anuncio = clave
            faltan = max(1, anuncio.get("jugadores", 2) - anuncio.get("conectados", 0))
            self.locales = min(self.locales, faltan)
            return ("unirse", ip, puerto)
        elif clave in ("unirse", "codigo"):
            host, puerto = direccion_de_codigo(self.codigo)
            if host is None:
                return ("aviso", puerto)
            return ("unirse", host, puerto)
        elif tipo == "opcion":
            self.cambiar(clave, 1)
        return None

    def tecla(self, ev):
        """Compatibilidad (pruebas viejas): un KEYDOWN -> acción."""
        que, texto = _de_tecla(ev, escribir=self.pantalla == "unirse")
        return self.accion(que, texto) if que else None

    # -- Dibujo ------------------------------------------------------------------------

    def dibujar(self, pantalla, aviso=""):
        from juego.fuentes import fuente, fuente_de_tamano
        ancho, alto = pantalla.get_size()
        _fondo(pantalla)
        escala = min(ancho / 1280, alto / 720)
        titulo = fuente_de_tamano(max(30, int(54 * escala))).render("Jugar en red", True, TEXTO)
        pantalla.blit(titulo, titulo.get_rect(midtop=(ancho // 2, int(alto * 0.05))))
        sub = {"inicio": "Juega con otra laptop en el mismo wifi",
               "crear": "Esta laptop será la anfitriona: las demás se unen con el código",
               "unirse": "Elige una partida de la lista o escribe su código"}[self.pantalla]
        imagen = fuente("small").render(sub, True, TENUE)
        pantalla.blit(imagen, imagen.get_rect(midtop=(ancho // 2, titulo.get_rect(
            midtop=(ancho // 2, int(alto * 0.05))).bottom + 6)))
        self.rects = []
        if self.pantalla == "inicio":
            self._dibujar_inicio(pantalla, escala)
        elif self.pantalla == "crear":
            self._dibujar_crear(pantalla, escala)
        else:
            self._dibujar_unirse(pantalla, escala)
        pistas = "Flechas o mouse para elegir  ·  Enter: aceptar  ·  Esc: atrás"
        if self.pantalla == "unirse":
            pistas = "Escribe el código  ·  Flechas o mouse  ·  Enter: unirse  ·  Esc: atrás"
        imagen = fuente("small").render(pistas, True, TENUE)
        pantalla.blit(imagen, imagen.get_rect(midbottom=(ancho // 2, alto - 14)))
        if aviso:
            imagen = fuente("small").render(aviso, True, AMARILLO)
            caja = imagen.get_rect(midbottom=(ancho // 2, alto - 52)).inflate(28, 14)
            pygame.draw.rect(pantalla, (40, 32, 16), caja, border_radius=8)
            pygame.draw.rect(pantalla, AMARILLO, caja, 2, border_radius=8)
            pantalla.blit(imagen, imagen.get_rect(center=caja.center))

    def _caja(self, pantalla, rect, indice, borde=None):
        marcado = indice == self.foco
        pygame.draw.rect(pantalla, PANEL_MARCADO if marcado else PANEL, rect, border_radius=14)
        pygame.draw.rect(pantalla, borde or (CIAN if marcado else BORDE), rect, 3 if marcado else 2,
                         border_radius=14)
        self.rects.append((rect, indice))
        return marcado

    def _dibujar_inicio(self, pantalla, escala):
        from juego.fuentes import fuente, fuente_de_tamano
        ancho, alto = pantalla.get_size()
        w, h = int(min(460, ancho * 0.38)), int(min(330, alto * 0.5))
        sep = int(40 * escala)
        y = int(alto * 0.24)
        textos = [("Crear partida", "Esta laptop es la anfitriona.", "Te da un código para que", "las demás se unan.", "laptop"),
                  ("Unirse a una partida", "Busca las partidas de este", "wifi o escribe el código", "de la otra laptop.", "wifi")]
        for i, (titulo, *lineas, icono) in enumerate(textos):
            rect = pygame.Rect(0, 0, w, h)
            rect.topleft = (ancho // 2 - w - sep // 2 + i * (w + sep), y)
            marcado = self._caja(pantalla, rect, i, borde=None)
            color = CIAN if i == 0 else ROSA
            _icono(pantalla, icono, (rect.centerx, rect.y + int(h * 0.27)), int(h * 0.18), color)
            img = fuente_de_tamano(max(20, int(32 * escala))).render(titulo, True, color if marcado else TEXTO)
            pantalla.blit(img, img.get_rect(midtop=(rect.centerx, rect.y + int(h * 0.5))))
            for k, linea in enumerate(lineas):
                img = fuente("small").render(linea, True, TENUE)
                pantalla.blit(img, img.get_rect(midtop=(rect.centerx, rect.y + int(h * 0.66) + k * 26)))
        boton = pygame.Rect(0, 0, 260, 50)
        boton.midtop = (ancho // 2, y + h + int(30 * escala))
        self._boton(pantalla, boton, 2, "Volver al menú")

    def _boton(self, pantalla, rect, indice, texto, color=None):
        from juego.fuentes import fuente
        marcado = self._caja(pantalla, rect, indice, borde=color if indice == self.foco else None)
        img = fuente("subtitle").render(texto, True, (color or CIAN) if marcado else TEXTO)
        pantalla.blit(img, img.get_rect(center=rect.center))

    def _fila(self, pantalla, rect, indice, etiqueta, valor, nota=""):
        """Una opción: etiqueta a la izquierda y el valor con flechas a la derecha."""
        from juego.fuentes import fuente
        marcado = self._caja(pantalla, rect, indice)
        img = fuente("subtitle").render(etiqueta, True, TEXTO)
        pantalla.blit(img, img.get_rect(midleft=(rect.x + 22, rect.centery - (9 if nota else 0))))
        if nota:
            img = fuente("small").render(nota, True, TENUE)
            pantalla.blit(img, img.get_rect(midleft=(rect.x + 22, rect.centery + 15)))
        img = fuente("subtitle").render(valor, True, CIAN if marcado else TEXTO)
        caja_valor = pygame.Rect(0, 0, max(200, img.get_width() + 80), rect.height - 18)
        caja_valor.midright = (rect.right - 16, rect.centery)
        pantalla.blit(img, img.get_rect(center=caja_valor.center))
        for lado in (-1, 1):
            cx = caja_valor.centerx + lado * (caja_valor.width // 2 - 10)
            puntos = [(cx + lado * 8, caja_valor.centery), (cx - lado * 6, caja_valor.centery - 10),
                      (cx - lado * 6, caja_valor.centery + 10)]
            pygame.draw.polygon(pantalla, CIAN if marcado else BORDE, puntos)

    def _dibujar_crear(self, pantalla, escala):
        from juego.fuentes import fuente
        ancho, alto = pantalla.get_size()
        w = int(min(700, ancho * 0.56))
        x = ancho // 2 - w // 2
        y = int(alto * 0.18)
        h, sep = 60, 10
        filas = [("Jugadores en total", f"{self.total}", "Entre todas las laptops"),
                 ("Juegan en esta laptop", f"{self.locales}", "Luego eligen su control"),
                 ("Dificultad", NOMBRE_DIFICULTAD[self.dificultad], "")]
        for i, (etiqueta, valor, nota) in enumerate(filas):
            self._fila(pantalla, pygame.Rect(x, y + i * (h + sep), w, h), i, etiqueta, valor, nota)
        # Quién juega dónde: un muñequito por jugador, de su color de laptop.
        y_rep = y + 3 * (h + sep) + 6
        _reparto(pantalla, (ancho // 2, y_rep + 34), self.total, self.locales)
        if self.locales >= self.total:
            nota = "Todos juegan aquí: nadie más se puede unir"
            color = AMARILLO
        else:
            faltan = self.total - self.locales
            nota = f"La otra laptop se une con {faltan} jugador{'es' if faltan > 1 else ''}"
            color = VERDE
        img = fuente("small").render(nota, True, color)
        pantalla.blit(img, img.get_rect(midtop=(ancho // 2, y_rep + 92)))
        botones = pygame.Rect(0, 0, 260, 54)
        botones.midtop = (ancho // 2 + 140, y_rep + 130)
        self._boton(pantalla, botones, 3, "Crear partida", VERDE)
        atras = pygame.Rect(0, 0, 200, 54)
        atras.midtop = (ancho // 2 - 150, y_rep + 130)
        self._boton(pantalla, atras, 4, "Atrás")

    def _dibujar_unirse(self, pantalla, escala):
        from juego.fuentes import fuente, fuente_de_tamano
        ancho, alto = pantalla.get_size()
        w = int(min(760, ancho * 0.6))
        x = ancho // 2 - w // 2
        y = int(alto * 0.19)
        elementos = self.elementos()
        partidas = [e for e in elementos if e[0] == "partida"]
        img = fuente("subtitle").render("Partidas en este wifi", True, ROSA)
        pantalla.blit(img, (x, y))
        y += img.get_height() + 8
        if not partidas:
            caja = pygame.Rect(x, y, w, 70)
            pygame.draw.rect(pantalla, PANEL, caja, border_radius=14)
            pygame.draw.rect(pantalla, BORDE, caja, 2, border_radius=14)
            puntos = "." * (1 + (pygame.time.get_ticks() // 400) % 3)
            texto = ("Buscando" + puntos) if self.buscador is not None and self.buscador.error is None \
                else "No se puede buscar en esta red: usa el código"
            img = fuente("small").render(texto, True, TENUE)
            pantalla.blit(img, img.get_rect(midleft=(caja.x + 20, caja.centery - 10)))
            img = fuente("small").render("Si no aparece, escribe el código de la otra laptop.", True, TENUE)
            pantalla.blit(img, img.get_rect(midleft=(caja.x + 20, caja.centery + 14)))
            y = caja.bottom + 18
        else:
            for i, (_, (ip, puerto, anuncio), _) in enumerate(partidas):
                rect = pygame.Rect(x, y, w, 62)
                marcado = self._caja(pantalla, rect, i)
                _icono(pantalla, "laptop", (rect.x + 38, rect.centery), 20, CIAN)
                nombre = str(anuncio.get("nombre", "Partida"))[:24]
                img = fuente("subtitle").render(f"Partida de {nombre}", True, CIAN if marcado else TEXTO)
                pantalla.blit(img, img.get_rect(midleft=(rect.x + 72, rect.centery - 10)))
                dif = NOMBRE_DIFICULTAD.get(anuncio.get("dificultad"), "")
                faltan = anuncio.get("jugadores", 2) - anuncio.get("conectados", 0)
                img = fuente("small").render(
                    f"{anuncio.get('conectados', 0)} de {anuncio.get('jugadores', 2)} jugadores  ·  {dif}  ·  "
                    f"código {con_guion(codigo_de(ip, puerto) or ip)}", True, TENUE)
                pantalla.blit(img, img.get_rect(midleft=(rect.x + 72, rect.centery + 14)))
                img = fuente("small").render(f"faltan {faltan}", True, VERDE)
                pantalla.blit(img, img.get_rect(midright=(rect.right - 20, rect.centery)))
                y = rect.bottom + 10
            y += 8
        base = len(partidas)
        # El código.
        img = fuente("subtitle").render("Código de la partida", True, ROSA)
        pantalla.blit(img, (x, y))
        y += img.get_height() + 8
        campo = pygame.Rect(x, y, w, 70)
        marcado = self._caja(pantalla, campo, base)
        texto = self.codigo or ("escribe el código, p. ej. AB3K" if not marcado else "")
        grande = fuente_de_tamano(40)
        img = grande.render(self.codigo, True, TEXTO) if self.codigo else fuente("small").render(texto, True, TENUE)
        rect_txt = img.get_rect(midleft=(campo.x + 24, campo.centery))
        pantalla.blit(img, rect_txt)
        if marcado and (pygame.time.get_ticks() // 500) % 2:
            cursor_x = rect_txt.right + 4 if self.codigo else campo.x + 24
            pygame.draw.line(pantalla, CIAN, (cursor_x, campo.centery - 18), (cursor_x, campo.centery + 18), 3)
        y = campo.bottom + 14
        h = 58
        self._fila(pantalla, pygame.Rect(x, y, w, h), base + 1, "Juegan en esta laptop", f"{self.locales}")
        y += h + 20
        boton = pygame.Rect(0, 0, 300, 54)
        boton.midtop = (ancho // 2 + 140, y)
        self._boton(pantalla, boton, base + 2, "Unirse", VERDE)
        atras = pygame.Rect(0, 0, 200, 54)
        atras.midtop = (ancho // 2 - 170, y)
        self._boton(pantalla, atras, base + 3, "Atrás")


def _fondo(pantalla):
    """Fondo oscuro con un degradado y unas estrellas quietas."""
    ancho, alto = pantalla.get_size()
    clave = (ancho, alto)
    if _FONDOS.get("clave") != clave:
        import random as _r
        fondo = pygame.Surface((ancho, alto))
        for y in range(0, alto, 4):
            t = y / max(1, alto)
            color = (int(10 + 10 * t), int(12 + 6 * t), int(24 + 22 * t))
            pygame.draw.rect(fondo, color, (0, y, ancho, 4))
        azar = _r.Random(7)
        for _ in range(140):
            x, y = azar.randrange(ancho), azar.randrange(alto)
            v = azar.randint(70, 170)
            fondo.set_at((x, y), (v, v, min(255, v + 40)))
        _FONDOS.update(clave=clave, imagen=fondo)
    pantalla.blit(_FONDOS["imagen"], (0, 0))


_FONDOS = {}


def _icono(pantalla, tipo, centro, tam, color):
    """Dibujitos hechos con formas: una laptop o las ondas del wifi."""
    cx, cy = centro
    if tipo == "laptop":
        pantalla_r = pygame.Rect(0, 0, int(tam * 2.2), int(tam * 1.4))
        pantalla_r.midbottom = (cx, cy + tam // 3)
        pygame.draw.rect(pantalla, color, pantalla_r, 4, border_radius=6)
        pygame.draw.rect(pantalla, color, (pantalla_r.x - tam // 3, pantalla_r.bottom + 4,
                                           pantalla_r.width + 2 * (tam // 3), max(5, tam // 4)),
                         border_radius=4)
    else:
        for k in range(3):
            r = int(tam * (0.45 + 0.4 * k))
            pygame.draw.arc(pantalla, color, (cx - r, cy - r + tam // 2, 2 * r, 2 * r),
                            0.75, 2.39, 5)
        pygame.draw.circle(pantalla, color, (cx, cy + tam // 2), max(4, tam // 6))


def _reparto(pantalla, centro, total, locales):
    """Quién juega dónde: J1..Jn, los de aquí en cian y los de la otra laptop
    en rosa, con su control debajo."""
    from juego.fuentes import fuente
    cx, cy = centro
    paso = 140
    x0 = cx - (total - 1) * paso // 2
    for i in range(total):
        aqui = i < locales
        color = CIAN if aqui else ROSA
        x = x0 + i * paso
        pygame.draw.circle(pantalla, color, (x, cy - 12), 12)
        pygame.draw.rect(pantalla, color, (x - 14, cy + 2, 28, 22), border_radius=8)
        img = fuente("small").render(f"J{i + 1}", True, AZUL_FONDO)
        pantalla.blit(img, img.get_rect(center=(x, cy + 13)))
        texto = "esta laptop" if aqui else "otra laptop"
        img = fuente("small").render(texto, True, color)
        pantalla.blit(img, img.get_rect(midtop=(x, cy + 28)))


def dibujar_espera(codigo, ip, puerto):
    """La pantalla mientras se espera a los demás (la usa cliente.Sesion):
    el código en grande, cómo se une la otra laptop y quién ya llegó."""
    def dibujar(pantalla, sesion, titulo):
        from juego.fuentes import fuente, fuente_de_tamano
        ancho, alto = pantalla.get_size()
        escala = min(ancho / 1280, alto / 720)
        _fondo(pantalla)
        img = fuente_de_tamano(max(28, int(46 * escala))).render(titulo, True, TEXTO)
        pantalla.blit(img, img.get_rect(midtop=(ancho // 2, int(alto * 0.07))))
        if codigo:
            img = fuente("subtitle").render("Código de la partida", True, ROSA)
            pantalla.blit(img, img.get_rect(midtop=(ancho // 2, int(alto * 0.2))))
            grande = fuente_de_tamano(max(48, int(110 * escala)))
            letras = con_guion(codigo)
            img = grande.render(letras, True, CIAN)
            caja = img.get_rect(midtop=(ancho // 2, int(alto * 0.27))).inflate(70, 30)
            pygame.draw.rect(pantalla, PANEL, caja, border_radius=20)
            pygame.draw.rect(pantalla, CIAN, caja, 3, border_radius=20)
            pantalla.blit(img, img.get_rect(center=caja.center))
            y = caja.bottom + 22
            for linea in ("En la otra laptop:  Jugar en red  >  Unirse a una partida",
                          "y elige esta partida de la lista, o escribe el código."):
                img = fuente("small").render(linea, True, TEXTO)
                pantalla.blit(img, img.get_rect(midtop=(ancho // 2, y)))
                y += 28
            img = fuente("small").render(f"(o la IP: {ip}" + (f":{puerto}" if puerto != PUERTO else "") + ")",
                                         True, TENUE)
            pantalla.blit(img, img.get_rect(midtop=(ancho // 2, y + 4)))
            y += 84
        else:
            y = int(alto * 0.3)
        # Quién ya está.
        espera = (sesion.conexiones[0].espera if sesion.conexiones else None) or {}
        conectados = espera.get("conectados", len(sesion.conexiones))
        total = conectados + espera.get("faltan", 0) if espera else max(2, len(sesion.conexiones))
        paso = 130
        x0 = ancho // 2 - (total - 1) * paso // 2
        mios = {c.jugador for c in sesion.conexiones}
        for i in range(total):
            llego = i < conectados
            color = (CIAN if i in mios else VERDE) if llego else BORDE
            x = x0 + i * paso
            pygame.draw.circle(pantalla, color, (x, y), 26, 0 if llego else 3)
            img = fuente("subtitle").render(f"J{i + 1}", True, AZUL_FONDO if llego else TENUE)
            pantalla.blit(img, img.get_rect(center=(x, y)))
            texto = ("aquí" if i in mios else "llegó") if llego else "esperando"
            img = fuente("small").render(texto, True, color if llego else TENUE)
            pantalla.blit(img, img.get_rect(midtop=(x, y + 32)))
        img = fuente("small").render("Esc para cancelar", True, TENUE)
        pantalla.blit(img, img.get_rect(midbottom=(ancho // 2, alto - 16)))
    return dibujar


# -- El bucle ------------------------------------------------------------------------------

def _de_tecla(ev, escribir=False):
    """Un KEYDOWN -> (acción, texto) para MenuRed.accion. Con `escribir`
    (en la pantalla de unirse) las letras y números se escriben en el código;
    si no, WASD también mueve."""
    if escribir and ev.unicode and (ev.unicode.isalnum() or ev.unicode in ".:-"):
        return "escribir", ev.unicode
    teclas = {pygame.K_UP: "arriba", pygame.K_w: "arriba", pygame.K_DOWN: "abajo", pygame.K_s: "abajo",
              pygame.K_LEFT: "izquierda", pygame.K_a: "izquierda", pygame.K_RIGHT: "derecha",
              pygame.K_d: "derecha", pygame.K_RETURN: "ok", pygame.K_KP_ENTER: "ok",
              pygame.K_SPACE: "ok", pygame.K_e: "ok", pygame.K_ESCAPE: "volver",
              pygame.K_BACKSPACE: "borrar", pygame.K_TAB: "abajo"}
    return teclas.get(ev.key, ""), ""


def abrir(juego):
    """La pantalla de "Jugar en red", con su bucle. Vuelve al menú al salir."""
    from juego.mandos import EVENTOS_MANDO
    menu = MenuRed()
    reloj = pygame.time.Clock()
    aviso, aviso_hasta = "", 0
    try:
        while juego.running:
            reloj.tick(30)
            resultado = None
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    juego.running = False
                elif ev.type == pygame.KEYDOWN:
                    # En la pantalla de unirse las letras se escriben (son del
                    # código); para moverse están las flechas.
                    que, texto = _de_tecla(ev, escribir=menu.pantalla == "unirse")
                    if que:
                        resultado = menu.accion(que, texto) or resultado
                elif ev.type == pygame.MOUSEMOTION:
                    for rect, i in menu.rects:
                        if rect.collidepoint(ev.pos):
                            menu.foco = i
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    for rect, i in menu.rects:
                        if rect.collidepoint(ev.pos):
                            menu.foco = i
                            tipo = menu.elementos()[i][0]
                            if tipo == "opcion":
                                # Clic a la izquierda del valor baja, a la derecha sube.
                                que = "derecha" if ev.pos[0] > rect.right - 115 else "izquierda"
                                resultado = menu.accion(que) or resultado
                            elif tipo != "campo":
                                resultado = menu.accion("ok") or resultado
                elif ev.type in EVENTOS_MANDO and getattr(juego, "mandos", None) is not None:
                    for _puesto, accion in juego.mandos.evento(ev):
                        que = {"interactuar": "ok", "pausa": "ok", "volver": "volver",
                               "arriba": "arriba", "abajo": "abajo", "izquierda": "izquierda",
                               "derecha": "derecha"}.get(accion)
                        if que:
                            resultado = menu.accion(que) or resultado
            if resultado == "salir":
                break
            if isinstance(resultado, tuple) and resultado[0] == "aviso":
                aviso, aviso_hasta = resultado[1], time.time() + 5
            elif resultado == "crear" or (isinstance(resultado, tuple) and resultado[0] == "unirse"):
                aviso = _jugar(juego, menu, resultado) or ""
                aviso_hasta = time.time() + 6
                if not juego.running:
                    break
            if aviso and time.time() > aviso_hasta:
                aviso = ""
            menu.dibujar(juego.screen, aviso)
            pygame.display.flip()
    finally:
        menu.cerrar()
    juego.current_screen = "menu"


def _levantar(menu):
    """El servidor en el 5050, o en el siguiente libre (hasta 5053, los que
    caben en el código)."""
    ultimo = "no se pudo abrir el servidor"
    for puerto in range(PUERTO, PUERTO + 4):
        if not puerto_libre(puerto):
            ultimo = f"El puerto {puerto} ya está ocupado"
            continue
        proceso, puerto_o_error = levantar_servidor(menu.total, menu.dificultad, puerto=puerto,
                                                    extra=("--tutorial", "--elegir-roles", *EXTRA_SERVIDOR))
        if proceso is not None:
            return proceso, puerto_o_error
        ultimo = puerto_o_error
    return None, ultimo


def esquemas_libres(mandos):
    """WASD y flechas siempre; los mandos, si están conectados."""
    from juego.mandos import PUESTOS_CON_MANDO
    from entidades.jugador import NOMBRE_ESQUEMA
    return [e for e in range(len(NOMBRE_ESQUEMA))
            if e not in PUESTOS_CON_MANDO or (mandos is not None and mandos.hay_mando(e))]


def tomar_esquema(esquemas, esquema, libres):
    """Lo mismo que Game.tomar_esquema del modo local: si ese control ya era
    de alguien, lo suelta; si no, se lo da al primero sin control. Devuelve
    True si cambió algo."""
    if esquema not in libres:
        return False
    if esquema in esquemas:
        esquemas[esquemas.index(esquema)] = None
        return True
    if None not in esquemas:
        return False
    esquemas[esquemas.index(None)] = esquema
    return True


def _elegir_controles(juego, cantidad):
    """La pantalla "¿Con qué juega cada uno?" del modo local, para los
    jugadores de esta laptop. Devuelve la lista de esquemas (WASD=0,
    Flechas=1, Mando 1=2, Mando 2=3, en el orden en que se tomaron), None
    con Esc o "salir" si se cierra la ventana."""
    from juego.mandos import EVENTOS_MANDO, PUESTOS_CON_MANDO
    from entidades.jugador import TECLAS_POR_PUESTO, NOMBRE_ESQUEMA
    from screens.seleccion import render_controles
    mandos = getattr(juego, "mandos", None)
    esquemas = [None] * cantidad
    reloj = pygame.time.Clock()
    listo_desde = None
    while True:
        libres = esquemas_libres(mandos)
        # Un mando que alguien tomó y se desconectó queda libre otra vez.
        for i, e in enumerate(esquemas):
            if e is not None and e not in libres:
                esquemas[i] = None
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return "salir"
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return None
                for esquema in (0, 1):
                    if ev.key in TECLAS_POR_PUESTO[esquema]["interactuar"]:
                        tomar_esquema(esquemas, esquema, libres)
            elif ev.type in EVENTOS_MANDO and mandos is not None:
                for puesto, accion in mandos.evento(ev):
                    if puesto not in PUESTOS_CON_MANDO:
                        continue
                    if accion in ("interactuar", "pausa"):
                        tomar_esquema(esquemas, puesto, esquemas_libres(mandos))
                    elif accion == "volver":
                        if puesto in esquemas:
                            tomar_esquema(esquemas, puesto, esquemas_libres(mandos))
                        else:
                            return None
        nombres = [mandos.nombre_esquema(e, n) if mandos is not None else n
                   for e, n in enumerate(NOMBRE_ESQUEMA)]
        conectados = [mandos is not None and mandos.hay_mando(e) for e in range(len(NOMBRE_ESQUEMA))]
        render_controles(juego.screen, esquemas, nombres, esquemas_libres(mandos), conectados,
                         volver="volver al menú de red")
        pygame.display.flip()
        # Todos tienen el suyo: un momentito para que se vea y seguimos.
        if None not in esquemas:
            listo_desde = listo_desde or time.time()
            if time.time() - listo_desde > 0.4:
                return list(esquemas)
        else:
            listo_desde = None
        reloj.tick(30)


def _jugar(juego, menu, resultado):
    """Crea o se une; juega; devuelve un aviso para la pantalla (o "")."""
    # Como en el modo de una sola laptop: cada jugador de aquí presiona el
    # botón de su control (E, Enter o el de su mando) y así queda cuál es J1, J2...
    esquemas = _elegir_controles(juego, menu.locales)
    if esquemas is None:
        return ""
    if esquemas == "salir":
        juego.running = False
        return ""
    proceso = None
    espera = None
    if resultado == "crear":
        _fondo(juego.screen)
        cliente.aviso(juego.screen, ["Preparando la partida..."])
        pygame.display.flip()
        pygame.event.pump()
        proceso, puerto = _levantar(menu)
        if proceso is None:
            return puerto
        host = "127.0.0.1"
        ip = ips_locales()[0]
        espera = dibujar_espera(codigo_de(ip, puerto), ip, puerto)
        # (La nave se arma después, cuando todos eligieron rol: mientras
        # tanto el código está en pantalla y los demás ya pueden unirse.)
    else:
        _, host, puerto = resultado
        espera = dibujar_espera(None, host, puerto)
    if menu.buscador is not None:
        menu.buscador.cerrar()          # (se vuelve a abrir al regresar a "Unirse")
        menu.buscador = None
    try:
        motivo = cliente.jugar(juego, host, puerto, esquemas,
                               avisar=lambda t: print("[red]", t, flush=True), dibujar_espera=espera,
                               anfitrion=proceso is not None)
        if proceso is not None and proceso.poll() is not None and motivo in ("perdida", "error", "fin"):
            # Se cayó el servidor de esta laptop: se dice por qué.
            time.sleep(0.3)
            print("[red] el servidor se cerró. Detalle en", REGISTRO, flush=True)
            return "El servidor se cerró: " + _error_del_servidor(proceso)
    finally:
        if proceso is not None:
            # El servidor alcanza a mandar `fin` a los de otras laptops.
            cerrar_servidor(proceso)
    if menu.pantalla == "unirse":
        menu.buscador = Buscador()
    if motivo == "salir":
        juego.running = False
    return {"error": "No se pudo conectar: revisa el código y que estén en el mismo wifi.",
            "perdida": "Se perdió la conexión con la otra laptop.",
            "fin": "La otra laptop cerró la partida."}.get(motivo, "")
