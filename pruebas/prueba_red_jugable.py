"""El modo en red de punta a punta, con sockets de verdad y el cliente real.

    python pruebas/prueba_red_jugable.py

1. Dos jugadores en UNA ventana (cliente_servidor.cliente.Sesion, la misma
   que usa el menú "Jugar en red"): se conectan, el espejo arma la partida,
   caminan a la derecha y el dibujo del espejo funciona (sin caer al dibujo
   sencillo). Las posiciones del espejo siguen a las del servidor.
2. Reconexión: se corta el socket de J2 sin avisar; vuelve solo con su token
   y sigue siendo J2.
3. Cierre del servidor (Ctrl+C): los clientes reciben `fin` y la sesión
   termina con motivo "fin" (en el juego: aviso y vuelta al menú).
4. Cuatro jugadores en dos "laptops" (dos sesiones: una con teclado y otra
   con los mandos) en la fase final (--fase-final): la partida se gana, las
   dos ven el resultado y la pantalla de resultados del modo local.

Las capturas van a la carpeta temporal (o NEXUS_CAPTURAS). Tarda ~30 s.
"""

import os
import signal
import subprocess
import sys
import tempfile
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

import pygame

from cliente_servidor import cliente

CARPETA = os.environ.get("NEXUS_CAPTURAS") or os.path.join(tempfile.gettempdir(), "nexus_capturas")
os.makedirs(CARPETA, exist_ok=True)
INICIO = time.time()


def arrancar_servidor(*extra):
    proceso = subprocess.Popen(
        [sys.executable, "-u", "-m", "cliente_servidor.servidor", "--puerto", "0", "--mapa", "Nave",
         "--sin-presentaciones", "--aliens-quietos", "--segundos", "50", *extra],
        cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    limite = time.time() + 20
    while time.time() < limite:
        linea = proceso.stdout.readline()
        if not linea:
            break
        if "escuchando en" in linea:
            return proceso, int(linea.split("escuchando en ")[1].split()[0].rsplit(":", 1)[1])
    proceso.kill()
    raise AssertionError("el servidor no dijo en qué puerto escucha")


def nuevo_juego():
    from juego.app import Game
    return Game()


def sesion(puerto, esquemas, mantener):
    """Una "laptop": un Game espejo y una sesión con sus jugadores locales.
    `mantener` es la lista de acciones mantenidas de cada uno (la cambia la prueba)."""
    s = cliente.Sesion(nuevo_juego(), "127.0.0.1", puerto, esquemas, avisar=lambda t: None)
    s.conectar()
    s.entrada.sacar = lambda: [(set(m), []) for m in mantener]
    return s


def correr(sesiones, pantallas, segundos, hasta=None):
    fin = time.time() + segundos
    while time.time() < fin:
        for s, p in zip(sesiones, pantallas):
            s.paso(p, eventos=[])
        if hasta is not None and hasta():
            return True
        time.sleep(1 / 60)
    return False


def x_servidor(s, i):
    e = s.conexiones[0].ultimo_estado()
    return e[f"j{i}"]["x"] if e else None


pygame.init()

# -- 1 y 2: dos jugadores en una ventana, reconexión ------------------------------------
proceso, puerto = arrancar_servidor("--jugadores", "2")
try:
    mantener = [[], []]
    a = sesion(puerto, cliente.esquemas_para(2), mantener)
    assert [c.jugador for c in a.conexiones] == [0, 1]
    a.preparar_espejo()
    assert a.espejo.listo, a.espejo.error
    pantalla = pygame.Surface((1280, 720))
    assert correr([a], [pantalla], 8, hasta=lambda: x_servidor(a, 0) is not None)
    correr([a], [pantalla], 0.5)
    x0 = x_servidor(a, 0)
    mantener[0][:] = ["derecha"]
    mantener[1][:] = ["derecha"]
    correr([a], [pantalla], 1.2)
    x1 = x_servidor(a, 0)
    assert x1 > x0 + 40, f"J1 camina a la derecha ({x0} -> {x1})"
    assert a.error_dibujo is None, f"el espejo dibujó sin errores: {a.error_dibujo!r}"
    # El espejo está donde dice el servidor (con la interpolación, un poco atrás).
    mantener[0][:] = []
    mantener[1][:] = []
    correr([a], [pantalla], 0.6)
    assert abs(a.espejo.g.jugadores[0].personaje.x - x_servidor(a, 0)) < 2, "quieto, el espejo alcanza al servidor"
    pygame.image.save(pantalla, os.path.join(CARPETA, "red_dos_jugadores.png"))
    print("1. dos jugadores en una ventana: OK")

    j2 = a.conexiones[1]
    j2.cortar()
    assert correr([a], [pantalla], 6, hasta=lambda: j2.reconexiones >= 1 and j2.situacion == "jugando")
    assert j2.jugador == 1, "al volver sigue siendo J2"
    mantener[1][:] = ["izquierda"]
    xa = x_servidor(a, 1)
    correr([a], [pantalla], 1.0)
    assert x_servidor(a, 1) < xa - 20, "después de reconectar J2 se sigue moviendo"
    mantener[1][:] = []
    print("2. reconexión con token: OK")

    proceso.send_signal(signal.SIGINT)        # como Ctrl+C en la terminal del servidor
    assert correr([a], [pantalla], 6, hasta=lambda: a.motivo is not None), "la sesión terminó sola"
    assert a.motivo == "fin", a.motivo
    a.cerrar()
    print("3. cierre del servidor: los clientes se enteran: OK")
finally:
    if proceso.poll() is None:
        proceso.kill()
    proceso.wait(5)

# -- 4: cuatro jugadores en dos "laptops", hasta el final -----------------------------------
proceso, puerto = arrancar_servidor("--jugadores", "4", "--fase-final", "--espera", "1")
try:
    quietos = [[], []]
    teclado = sesion(puerto, cliente.esquemas_para(2), quietos)
    mandos = sesion(puerto, cliente.esquemas_para(2, mandos=True), quietos)
    assert [c.jugador for c in mandos.conexiones] == [2, 3]
    assert mandos.entrada.esquemas == [2, 3], "la segunda laptop juega con los dos mandos"
    for s in (teclado, mandos):
        s.preparar_espejo()
    pantallas = [pygame.Surface((1280, 720)), pygame.Surface((1280, 720))]

    def ganaron():
        return all((s.conexiones[0].ultimo_estado() or {}).get("g", {}).get("resultado") == "victoria"
                   for s in (teclado, mandos))
    assert correr([teclado, mandos], pantallas, 12, hasta=ganaron), "la partida se gana"
    correr([teclado, mandos], pantallas, 0.3)
    assert teclado.error_dibujo is None and mandos.error_dibujo is None
    pygame.image.save(pantallas[0], os.path.join(CARPETA, "red_resultados_laptop1.png"))
    pygame.image.save(pantallas[1], os.path.join(CARPETA, "red_resultados_laptop2.png"))
    # Enter vuelve al menú.
    enter = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r", mod=0, scancode=0)
    teclado.paso(pantallas[0], eventos=[enter])
    assert teclado.motivo == "terminada"
    for s in (teclado, mandos):
        s.cerrar()
    proceso.wait(15)
    salida = proceso.stdout.read()
    assert "partida terminada: victoria" in salida, salida
    for linea in salida.splitlines():
        if "instantáneas:" in linea:
            print("   ", linea.strip())
    print("4. cuatro jugadores en dos laptops hasta la victoria: OK")
finally:
    if proceso.poll() is None:
        proceso.kill()

print(f"OK prueba_red_jugable en {time.time() - INICIO:.1f} s (capturas en {CARPETA})")
