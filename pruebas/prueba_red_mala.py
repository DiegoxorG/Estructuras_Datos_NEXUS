"""El modo en red con wifi malo (el hotspot de un celular en la feria).

    python pruebas/prueba_red_mala.py            (~2 minutos)

Un servidor de verdad (otro proceso) y dos clientes:
- A (en esta prueba, J1): una Sesion real que dibuja en una Surface. Pasa
  por el proxy `pa`, al que se le pone latencia con jitter.
- B (otro proceso, J2: este mismo archivo con --cliente): otra Sesion real.
  Pasa por el proxy `pb`, que se corta, y al proceso se le congela con
  SIGSTOP (como una laptop que se traba). Cada 0.1 s escribe cómo está.

El proxy entiende de tiempos, no de mensajes: retrasa cada pedazo en las dos
direcciones (en orden, como TCP), y en un corte deja de leer y de mandar sin
cerrar nada (como un wifi que se cae: los paquetes no llegan, no hay RST) y
las conexiones nuevas se quedan colgadas hasta que vuelve.

Fases:
1. latencia 50, 150 y 300 ms ida y vuelta (con jitter de ±40 %): tecla ->
   se ve moverse en el espejo de A, y la respuesta medida (intención -> ack).
2. ráfagas: cada ~1.5 s el wifi se traba 0.3-0.8 s y suelta todo junto.
3. cortes de 1, 3, 5 y 8 s a B mientras mantiene una tecla.
4. B congelado 3, 6 y 10 s (SIGSTOP; solo Linux/Mac).

Pide:
- que nadie quede "jugando" sin recibir nada (más de SILENCIO_S + 1 s),
- que después de cada corte o congelada B vuelva como J2 y se mueva,
- que el jugador de B se detenga en el servidor poco después de que se corta
  (antes seguía caminando con la última tecla hasta chocar),
- que el servidor siga a ~60 cuadros por segundo para A (y que a A le sigan
  llegando instantáneas sin huecos grandes),
- que la ventana de B siga dibujando mientras está cortado.
Los números van a la salida (y a NEXUS_RED_INFORME si se define).
"""

import json
import os
import random
import signal
import socket
import subprocess
import sys
import threading
import time
from collections import deque

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)


class Proxy:
    """Proxy TCP con latencia (ms de ida en CADA dirección), jitter y cortes."""

    def __init__(self, puerto_destino, semilla=1):
        self.destino = puerto_destino
        self.ida_s = 0.0
        self.jitter = 0.0
        self.parado_hasta = 0.0
        self.azar = random.Random(semilla)
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(16)
        self.puerto = self.sock.getsockname()[1]
        self.conexiones = 0
        threading.Thread(target=self._aceptar, daemon=True).start()

    def latencia(self, ida_y_vuelta_ms, jitter=0.4):
        self.ida_s = ida_y_vuelta_ms / 2000.0
        self.jitter = jitter

    def cortar(self, segundos):
        self.parado_hasta = time.time() + segundos

    def parado(self):
        return time.time() < self.parado_hasta

    def _aceptar(self):
        while True:
            try:
                c, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._par, args=(c,), daemon=True).start()

    def _par(self, c):
        while self.parado():            # (el wifi está caído: el saludo no pasa)
            time.sleep(0.02)
        try:
            s = socket.create_connection(("127.0.0.1", self.destino))
        except OSError:
            c.close()
            return
        for x in (c, s):
            x.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.conexiones += 1
        self._tubo(c, s)
        self._tubo(s, c)

    def _tubo(self, origen, destino):
        cola = deque()
        hay = threading.Condition()

        def leer():
            ultimo = 0.0
            while True:
                while self.parado():
                    time.sleep(0.01)
                try:
                    datos = origen.recv(65536)
                except OSError:
                    datos = b""
                demora = self.ida_s * (1 + self.azar.uniform(-self.jitter, self.jitter))
                ultimo = max(ultimo, time.time() + demora)      # en orden, como TCP
                with hay:
                    cola.append((ultimo, datos))
                    hay.notify()
                if not datos:
                    return

        def mandar():
            while True:
                with hay:
                    while not cola:
                        hay.wait()
                    cuando, datos = cola.popleft()
                while time.time() < cuando or self.parado():
                    time.sleep(0.002)
                if not datos:
                    for x in (origen, destino):
                        try:
                            x.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass
                        x.close()
                    return
                try:
                    destino.sendall(datos)
                except OSError:
                    pass

        threading.Thread(target=leer, daemon=True).start()
        threading.Thread(target=mandar, daemon=True).start()


def arrancar_servidor():
    proceso = subprocess.Popen(
        [sys.executable, "-u", "-m", "cliente_servidor.servidor", "--puerto", "0", "--mapa", "Nave",
         "--jugadores", "2", "--sin-presentaciones", "--aliens-quietos", "--segundos", "400",
         "--espera", "60"],
        cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    while True:
        linea = proceso.stdout.readline()
        assert linea, "el servidor no arrancó"
        if "escuchando en" in linea:
            puerto = int(linea.split("escuchando en ")[1].split()[0].rsplit(":", 1)[1])
            break
    salida = []
    threading.Thread(target=lambda: [salida.append(l) for l in proceso.stdout], daemon=True).start()
    return proceso, puerto, salida


def vigilar(conexion):
    """Anota cuándo llega cada mensaje a `conexion` (y el cuadro `c`)."""
    llegadas = deque(maxlen=20000)
    original = conexion._recibir

    def recibir(mensaje):
        llegadas.append((time.time(), mensaje.get("c")))
        return original(mensaje)
    conexion._recibir = recibir
    saludar = conexion._saludar

    def saludar_y_anotar(*args):
        # La bienvenida de una reconexión también es "recibir algo".
        resultado = saludar(*args)
        llegadas.append((time.time(), None))
        return resultado
    conexion._saludar = saludar_y_anotar
    conexion.llegadas = llegadas
    return llegadas


# -- B: el cliente en otro proceso ------------------------------------------------------

def modo_cliente(puerto):
    import pygame
    from cliente_servidor import cliente
    pygame.init()
    from juego.app import Game
    mantener = []
    s = cliente.Sesion(Game(), "127.0.0.1", puerto, cliente.esquemas_para(1), avisar=lambda t: None)
    s.conectar()
    s.entrada.sacar = lambda: [(set(mantener), [])]
    c = s.conexiones[0]
    llegadas = vigilar(c)

    def ordenes():
        for linea in sys.stdin:
            mantener[:] = [a for a in linea.split() if a != "quieto"]
    threading.Thread(target=ordenes, daemon=True).start()
    s.preparar_espejo()
    pantalla = pygame.Surface((960, 540))
    cuadros, ultimo = 0, time.time()
    while True:
        s.paso(pantalla, eventos=[])
        cuadros += 1
        ahora = time.time()
        if ahora - ultimo >= 0.1:
            e = c.ultimo_estado() or {}
            print(json.dumps({"t": ahora, "sit": c.situacion, "j": c.jugador, "rec": c.reconexiones,
                              "rx": ahora - llegadas[-1][0] if llegadas else None,
                              "fps": cuadros / (ahora - ultimo), "motivo": s.motivo,
                              "x": (e.get("j1") or {}).get("x")}), flush=True)
            cuadros, ultimo = 0, ahora
        if s.motivo:
            return
        time.sleep(1 / 60)


# -- La prueba ---------------------------------------------------------------------------

def main():
    import pygame
    from cliente_servidor import cliente
    from cliente_servidor.cliente import SILENCIO_S
    informe = []

    def anotar(texto):
        print(texto, flush=True)
        informe.append(texto)

    proceso, puerto, salida_servidor = arrancar_servidor()
    pa, pb = Proxy(puerto, 1), Proxy(puerto, 2)
    b = None
    try:
        pygame.init()
        from juego.app import Game
        mantener_a = []
        a = cliente.Sesion(Game(), "127.0.0.1", pa.puerto, cliente.esquemas_para(1), avisar=lambda t: None)
        a.conectar()
        a.entrada.sacar = lambda: [(set(mantener_a), [])]
        ca = a.conexiones[0]
        assert ca.jugador == 0
        llegadas_a = vigilar(ca)
        b = subprocess.Popen([sys.executable, "-u", os.path.abspath(__file__), "--cliente", str(pb.puerto)],
                             cwd=RAIZ, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, text=True)
        estados_b = deque(maxlen=5000)

        def leer_b():
            for linea in b.stdout:
                if linea.startswith("{"):
                    estados_b.append(json.loads(linea))
        threading.Thread(target=leer_b, daemon=True).start()

        def ordenar_b(*acciones):
            b.stdin.write(" ".join(acciones or ("quieto",)) + "\n")
            b.stdin.flush()

        a.preparar_espejo()
        pantalla = pygame.Surface((960, 540))
        violaciones = []     # (quién, cuándo, rx) "jugando" sin recibir nada
        reloj_a = {"cuadros": 0}
        gracia = {"b": 0.0}  # al despertar de SIGSTOP, B todavía no alcanzó a leer

        def paso_a():
            a.paso(pantalla, eventos=[])
            reloj_a["cuadros"] += 1
            ahora = time.time()
            if ca.situacion == "jugando" and llegadas_a and ahora - llegadas_a[-1][0] > SILENCIO_S + 1:
                violaciones.append(("A", ahora, ahora - llegadas_a[-1][0]))
            for e in list(estados_b)[-3:]:
                if (e["sit"] == "jugando" and e["rx"] is not None and e["rx"] > SILENCIO_S + 1
                        and e["t"] > gracia["b"]):
                    violaciones.append(("B", e["t"], e["rx"]))

        def correr(segundos, hasta=None):
            fin = time.time() + segundos
            while time.time() < fin:
                paso_a()
                if hasta is not None and hasta():
                    return True
                time.sleep(1 / 60)
            return False

        def estado():
            return ca.ultimo_estado() or {}

        def x(i):
            return (estado().get(f"j{i}") or {}).get("x")

        def on(i):
            return (estado().get(f"j{i}") or {}).get("on")

        def camina(i):
            # `mov` es "tiene una tecla de caminar apretada" en el servidor
            # (Personaje.moviendose), aunque esté contra una pared.
            return bool((estado().get(f"j{i}") or {}).get("mov"))

        assert correr(30, hasta=lambda: x(0) is not None and x(1) is not None and on(1)), "B no llegó"
        assert correr(15, hasta=lambda: estados_b and estados_b[-1]["x"] is not None), "B no juega"
        correr(0.5)

        # 1. Latencia ------------------------------------------------------------------
        def ida_y_vuelta(direccion):
            """Tecla -> se ve moverse en el espejo de A (s)."""
            mantener_a[:] = []
            correr(0.6)
            x0 = a.espejo.g.jugadores[0].personaje.x
            inicio = time.time()
            mantener_a[:] = [direccion]
            visto = correr(3.0, hasta=lambda: abs(a.espejo.g.jugadores[0].personaje.x - x0) > 0.5)
            ms = (time.time() - inicio) * 1000
            correr(0.25)
            mantener_a[:] = []
            return ms if visto else None

        for rtt in (0, 50, 150, 300):
            pa.latencia(rtt, 0.4 if rtt else 0.0)
            correr(1.0)
            muestras = [ida_y_vuelta(("derecha", "izquierda")[k % 2]) for k in range(6)]
            assert all(m is not None for m in muestras), f"con {rtt} ms A no se movió: {muestras}"
            muestras.sort()
            anotar(f"latencia {rtt:3d} ms ida y vuelta (±40 %): tecla -> se ve moverse mediana "
                   f"{muestras[3]:.0f} ms, máx {muestras[-1]:.0f} ms; intención -> ack {ca.respuesta_ms:.0f} ms")
            assert muestras[3] < rtt * 1.4 + 250, f"con {rtt} ms tarda demasiado en verse: {muestras}"
        assert ca.reconexiones == 0, "con latencia nadie se desconecta"
        pa.latencia(30, 0.5)

        # 2. Ráfagas -------------------------------------------------------------------
        azar = random.Random(5)
        fin = time.time() + 9
        mantener_a[:] = ["derecha"]
        k = 0
        while time.time() < fin:
            pa.cortar(azar.uniform(0.3, 0.8))
            correr(azar.uniform(1.0, 2.0))
            k += 1
            mantener_a[:] = [("izquierda", "derecha")[k % 2]]
        mantener_a[:] = []
        correr(1.0)
        assert ca.reconexiones == 0 and ca.situacion == "jugando", "las ráfagas no desconectan"
        x0 = x(0)
        mantener_a[:] = ["izquierda"]
        assert correr(3, hasta=lambda: abs(x(0) - x0) > 20), "después de las ráfagas A se mueve"
        mantener_a[:] = []
        anotar(f"ráfagas ({k} trabas de 0.3-0.8 s): sin reconexiones, A sigue jugando")
        pa.latencia(0, 0.0)

        # 3 y 4. Cortes y congeladas de B ----------------------------------------------
        def mirar_servidor(desde):
            """Cuadros por segundo del servidor según lo que le llega a A, y el
            hueco más largo entre dos instantáneas."""
            vistas = [(t, c) for t, c in llegadas_a if t >= desde and c is not None]
            if len(vistas) < 2:
                return 0.0, 99.0
            fps = (vistas[-1][1] - vistas[0][1]) / (vistas[-1][0] - vistas[0][0])
            hueco = max(b_[0] - a_[0] for a_, b_ in zip(vistas, vistas[1:]))
            return fps, hueco

        def problema(nombre, segundos, empezar, terminar):
            # B camina con la tecla apretada justo cuando se corta.
            ordenar_b("derecha")
            correr(0.4)
            reconexiones_b = estados_b[-1]["rec"]
            inicio = time.time()
            empezar(segundos)
            posiciones = []          # (t, x de J2 en el servidor, on)
            cuadros_b = []
            while time.time() < inicio + segundos:
                correr(0.05)
                posiciones.append((time.time(), camina(1), on(1)))
                e = estados_b[-1]
                if e["t"] > inicio + 0.3 and nombre == "corte":
                    cuadros_b.append(e["fps"])
            terminar()
            gracia["b"] = time.time() + 1.5
            fps, hueco = mirar_servidor(inicio)
            # Cuándo dejó de moverse J2 en el servidor.
            # (sin los últimos 0.3 s: al volver el wifi llegan juntas las
            # intenciones atrasadas y la tecla vuelve a estar apretada)
            se_detuvo = max([t - inicio for t, mov, _ in posiciones
                             if mov and t < inicio + segundos - 0.3] or [0.0])
            apagado = next((t - inicio for t, _, o in posiciones if o is False), None)
            # Vuelve: B como J2, jugando, y se mueve.
            vuelta = time.time()
            ordenar_b("izquierda")
            ok = correr(25, hasta=lambda: estados_b[-1]["sit"] == "jugando" and estados_b[-1]["rx"] is not None
                        and estados_b[-1]["rx"] < 0.5 and on(1))
            volvio = time.time() - vuelta
            x0_ = x(1)
            se_mueve = correr(5, hasta=lambda: x(1) is not None and x0_ is not None and x(1) < x0_ - 20)
            ordenar_b("quieto")
            correr(0.6)
            e = estados_b[-1]
            texto = (f"{nombre} {segundos:>4.1f} s: servidor {fps:.0f} cuadros/s para A (hueco máx "
                     f"{hueco * 1000:.0f} ms); J2 siguió caminando {se_detuvo:.1f} s; "
                     f"servidor lo marcó desconectado a los {'%.1f s' % apagado if apagado is not None else 'nunca'}; "
                     f"B volvió en {volvio:.1f} s ({e['rec'] - reconexiones_b} reconexiones, J{e['j'] + 1})")
            if cuadros_b:
                texto += f"; B dibujó a {min(cuadros_b):.0f}-{max(cuadros_b):.0f} cuadros/s durante el corte"
            anotar(texto)
            assert ok, f"{nombre} {segundos} s: B no volvió a jugar ({e})"
            assert e["j"] == 1, "B vuelve como J2"
            assert se_mueve, f"{nombre} {segundos} s: B no se mueve después"
            assert fps > 50 and hueco < 0.5, f"el servidor se trabó para A ({fps:.0f} cuadros/s, hueco {hueco:.2f} s)"
            assert se_detuvo < max(2.0, segundos * 0.5) or segundos <= 1.5, \
                f"J2 siguió caminando {se_detuvo:.1f} s con el wifi cortado"
            if cuadros_b:
                assert min(cuadros_b) > 15, f"la ventana de B se trabó durante el corte ({cuadros_b})"

        for segundos in (1, 3, 5, 8):
            problema("corte", segundos, pb.cortar, lambda: None)
        if hasattr(signal, "SIGSTOP"):
            for segundos in (3, 6, 10):
                problema("congelado", segundos, lambda s: os.kill(b.pid, signal.SIGSTOP),
                         lambda: os.kill(b.pid, signal.SIGCONT))
        assert not violaciones, f"alguien quedó 'jugando' sin recibir nada: {violaciones[:5]}"
        anotar("nadie quedó 'jugando' sin recibir nada: OK")
        assert ca.jugador == 0 and ca.situacion == "jugando"
        a.cerrar()
    finally:
        if b is not None and b.poll() is None:
            try:
                os.kill(b.pid, getattr(signal, "SIGCONT", signal.SIGTERM))
            except OSError:
                pass
            b.kill()
        if proceso.poll() is None:
            proceso.kill()
        resumen = [l.strip() for l in salida_servidor if "rendimiento" in l or "instantáneas" in l]
        for l in resumen:
            anotar("  " + l)
        if os.environ.get("NEXUS_RED_INFORME"):
            with open(os.environ["NEXUS_RED_INFORME"], "w", encoding="utf-8") as f:
                f.write("\n".join(informe) + "\n")
    print("OK prueba_red_mala")


if __name__ == "__main__":
    if "--cliente" in sys.argv:
        modo_cliente(int(sys.argv[sys.argv.index("--cliente") + 1]))
    else:
        main()
