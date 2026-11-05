"""El tutorial del principio también en red (antes el servidor lo saltaba).

    python pruebas/prueba_red_tutorial.py

Servidor con --tutorial y dos clientes (uno por jugador): los dos ven su paso
del tutorial (el cuadro de abajo), cada uno avanza con su tecla de habilidad
(el paso de cada quien viaja: en el Tutorial va por id() del jugador, que en el
espejo es otro), y cuando los dos terminan, el tutorial se acaba en los dos
clientes y los aliens despiertan en el servidor.
"""

import os
import subprocess
import sys
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

import pygame

from cliente_servidor import cliente
from juego.tutorial import PASOS

proceso = subprocess.Popen([sys.executable, "-u", "-m", "cliente_servidor.servidor", "--puerto", "0",
                            "--jugadores", "2", "--tutorial", "--sin-presentaciones", "--segundos", "90",
                            "--dificultad", "facil"],
                           cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
try:
    puerto = None
    while puerto is None:
        linea = proceso.stdout.readline()
        assert linea, "el servidor no arrancó"
        if "escuchando en" in linea:
            puerto = int(linea.split("escuchando en ")[1].split()[0].rsplit(":", 1)[1])
    import threading
    threading.Thread(target=lambda: [None for _ in proceso.stdout], daemon=True).start()
    pygame.init()
    from juego.app import Game
    sesiones, pulsar = [], []
    for k in range(2):
        s = cliente.Sesion(Game(), "127.0.0.1", puerto, cliente.esquemas_para(1), avisar=lambda t: None)
        s.conectar()
        cola = []
        s.entrada.sacar = (lambda cola=cola: [(set(), [cola.pop()] if cola else [])])
        sesiones.append(s)
        pulsar.append(cola)
    for s in sesiones:
        s.preparar_espejo()
    pantallas = [pygame.Surface((1280, 720)) for _ in sesiones]

    def correr(segundos, hasta=None):
        fin = time.time() + segundos
        while time.time() < fin:
            for s, p in zip(sesiones, pantallas):
                assert s.paso(p, eventos=[]), s.motivo
            if hasta is not None and hasta():
                return True
            time.sleep(1 / 60)
        return False

    def paso_de(i):
        g = sesiones[i].espejo.g
        tut = g.tutorial
        if tut is None or not tut.activo:
            return None
        return tut.estado.get(id(g.jugadores[sesiones[i].conexiones[0].jugador]), {}).get("paso")

    assert correr(10, hasta=lambda: paso_de(0) is not None and paso_de(1) is not None), \
        "los clientes no ven el tutorial"
    # J1 avanza tres pasos (los de "leer"), J2 no: cada uno ve el suyo.
    inicio = paso_de(0)
    for _ in range(3):
        pulsar[0].append("habilidad")
        correr(0.4)
    assert correr(3, hasta=lambda: paso_de(0) is not None and paso_de(0) > inicio), \
        f"J1 no avanzó en el tutorial ({inicio} -> {paso_de(0)})"
    assert paso_de(1) == 0, f"J2 no tocó nada y se movió de paso ({paso_de(1)})"
    pygame.image.save(pantallas[0], os.path.join(os.environ.get("TEMP", "/tmp"), "red_tutorial.png"))
    print(f"1. cada cliente ve su paso del tutorial (J1 en {paso_de(0)}, J2 en {paso_de(1)}): OK")
    # Los dos lo terminan: se acaba en los dos clientes.
    for _ in range(len(PASOS) + 2):
        pulsar[0].append("habilidad")
        pulsar[1].append("habilidad")
        correr(0.35)
    assert correr(5, hasta=lambda: paso_de(0) is None and paso_de(1) is None), "el tutorial no terminó"
    print("2. cuando los dos terminan, el tutorial se acaba en los dos: OK")
    for s in sesiones:
        s.cerrar()
finally:
    proceso.kill()
print("OK prueba_red_tutorial")
