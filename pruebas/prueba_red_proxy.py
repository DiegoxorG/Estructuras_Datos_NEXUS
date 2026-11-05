"""El modo en red con una red mala: latencia, pérdida y cortes (con un proxy).

    python pruebas/prueba_red_proxy.py

Entre el cliente y el servidor se pone un proxy TCP (en esta prueba) que:
- retrasa 80 ms cada mensaje del servidor al cliente,
- descarta el 15 % de las instantáneas (`estado`). Con TCP nada se pierde
  solo; así se modela la pérdida: al cliente le falta una delta, se da
  cuenta (la `base` no coincide), pide una completa y sigue,
- y al final corta la conexión: el cliente vuelve solo con su token.

Comprueba que los jugadores se siguen moviendo, que la respuesta medida
refleja el retraso y que la interpolación tiene con qué trabajar.
"""

import json
import os
import random
import socket
import subprocess
import sys
import threading
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

import pygame

from cliente_servidor import cliente

RETRASO_S = 0.08
PERDIDA = 0.15


class Proxy:
    """Un proxy TCP que entiende las líneas del protocolo."""

    def __init__(self, puerto_servidor):
        self.destino = puerto_servidor
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.puerto = self.sock.getsockname()[1]
        self.pares = []
        self.descartadas = 0
        self.azar = random.Random(3)
        threading.Thread(target=self._aceptar, daemon=True).start()

    def _aceptar(self):
        while True:
            try:
                c, _ = self.sock.accept()
            except OSError:
                return
            s = socket.create_connection(("127.0.0.1", self.destino))
            self.pares.append((c, s))
            threading.Thread(target=self._subir, args=(c, s), daemon=True).start()
            threading.Thread(target=self._bajar, args=(s, c), daemon=True).start()

    @staticmethod
    def _subir(c, s):
        try:
            while True:
                datos = c.recv(65536)
                if not datos:
                    break
                s.sendall(datos)
        except OSError:
            pass
        for x in (c, s):
            try:
                x.close()
            except OSError:
                pass

    def _bajar(self, s, c):
        """Del servidor al cliente: línea por línea, con retraso y pérdida."""
        bufer = b""
        try:
            while True:
                datos = s.recv(65536)
                if not datos:
                    break
                bufer += datos
                while b"\n" in bufer:
                    linea, bufer = bufer.split(b"\n", 1)
                    if b'"tipo":"estado"' in linea[:40] and self.azar.random() < PERDIDA:
                        self.descartadas += 1
                        continue
                    threading.Timer(RETRASO_S, self._entregar, args=(c, linea + b"\n")).start()
        except OSError:
            pass

    @staticmethod
    def _entregar(c, linea):
        try:
            c.sendall(linea)
        except OSError:
            pass

    def cortar_todo(self):
        for c, s in self.pares:
            for x in (c, s):
                try:
                    x.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        self.pares = []


proceso = subprocess.Popen(
    [sys.executable, "-u", "-m", "cliente_servidor.servidor", "--puerto", "0", "--mapa", "Nave",
     "--jugadores", "2", "--sin-presentaciones", "--aliens-quietos", "--segundos", "40", "--espera", "5"],
    cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
try:
    puerto = None
    while puerto is None:
        linea = proceso.stdout.readline()
        assert linea, "el servidor no arrancó"
        if "escuchando en" in linea:
            puerto = int(linea.split("escuchando en ")[1].split()[0].rsplit(":", 1)[1])
    proxy = Proxy(puerto)

    pygame.init()
    from juego.app import Game
    mantener = [[], []]
    s = cliente.Sesion(Game(), "127.0.0.1", proxy.puerto, cliente.esquemas_para(2), avisar=lambda t: None)
    s.conectar()
    s.entrada.sacar = lambda: [(set(m), []) for m in mantener]
    s.preparar_espejo()
    pantalla = pygame.Surface((960, 540))

    def correr(segundos, hasta=None):
        fin = time.time() + segundos
        while time.time() < fin:
            s.paso(pantalla, eventos=[])
            if hasta is not None and hasta():
                return True
            time.sleep(1 / 60)
        return False

    def x(i):
        e = s.conexiones[0].ultimo_estado()
        return e[f"j{i}"]["x"] if e else None

    assert correr(8, hasta=lambda: x(0) is not None)
    x0 = x(0)
    mantener[0][:] = ["derecha"]
    correr(2.0)
    assert x(0) > x0 + 40, f"con pérdida y retraso J1 camina igual ({x0} -> {x(0)})"
    assert proxy.descartadas > 5, "el proxy descartó instantáneas"
    c = s.conexiones[0]
    assert c.respuesta_ms is not None and c.respuesta_ms > RETRASO_S * 1000, c.respuesta_ms
    assert len(c.interpolador.bufer) >= 3, "la interpolación tiene instantáneas guardadas"
    assert s.error_dibujo is None, s.error_dibujo
    print(f"pérdida: {proxy.descartadas} instantáneas descartadas, respuesta {c.respuesta_ms:.0f} ms: OK")

    proxy.cortar_todo()
    assert correr(8, hasta=lambda: all(k.reconexiones >= 1 and k.situacion == "jugando"
                                        for k in s.conexiones)), "los dos vuelven por el proxy"
    mantener[0][:] = ["izquierda"]
    correr(0.5)
    xa = x(0)
    correr(1.0)
    assert x(0) < xa - 20, f"después del corte siguen jugando ({xa} -> {x(0)})"
    print("corte en el proxy y reconexión: OK")
    s.cerrar()
    print("OK prueba_red_proxy")
finally:
    if proceso.poll() is None:
        proceso.kill()
