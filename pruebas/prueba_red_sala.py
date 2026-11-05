"""La sala de Jugar en red: cada jugador elige su rol desde su laptop.

    python pruebas/prueba_red_sala.py

Servidor con --elegir-roles (lo pone el menú del juego) y dos clientes, uno
por jugador:

1. La bienvenida llega sin nave (todavía no hay roles) y el estado de la
   selección viaja en la `sala`.
2. Mover el cursor y confirmar como en el modo local; un rol ya confirmado
   por el otro no se puede tomar; volver a confirmar lo suelta.
3. Cuando los dos eligieron, el servidor arma la nave CON ESOS ROLES, la
   sala trae los datos de la partida y el espejo de cada uno los usa.
4. Capturas: la elección de rol, la pantalla de carga y la partida.
5. El que creó la partida se va en plena sala (cerrar_partida): el otro
   recibe `fin` enseguida (antes esperaba 20 s reconectando).
"""

import os
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

OUT = os.path.join(RAIZ, "pruebas", "capturas")
os.makedirs(OUT, exist_ok=True)
INICIO = time.time()


def arrancar():
    proceso = subprocess.Popen([sys.executable, "-u", "-m", "cliente_servidor.servidor", "--puerto", "0",
                                "--jugadores", "2", "--elegir-roles", "--sin-presentaciones",
                                "--aliens-quietos", "--segundos", "90", "--mapa", "Nave"],
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


def tecla(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0)


pygame.init()
from juego.app import Game

proceso, puerto, salida = arrancar()
try:
    a = cliente.Sesion(Game(), "127.0.0.1", puerto, [0], avisar=lambda t: None)    # WASD
    a.conectar()
    b = cliente.Sesion(Game(), "127.0.0.1", puerto, [1], avisar=lambda t: None)    # flechas
    b.conectar()
    assert a.con_sala and b.con_sala, "la bienvenida debía llegar sin nave (sala)"
    assert "roles" not in a.conexiones[0].bienvenida
    pantalla = pygame.Surface((1280, 720))

    def cuadro(sesion, *teclas):
        sesion.sala(pantalla, eventos=lambda: [tecla(k) for k in teclas])

    def sala_de(sesion):
        with sesion.conexiones[0].candado:
            return sesion.conexiones[0].sala

    def esperar(condicion, segundos=10, que=""):
        fin = time.time() + segundos
        while time.time() < fin:
            for s in (a, b):
                cuadro(s)
            if condicion():
                return
            time.sleep(0.03)
        raise AssertionError("no pasó: " + que + "\n" + "".join(salida[-15:]))

    esperar(lambda: sala_de(a) and sala_de(a)["fase"] == "roles" and all(sala_de(a)["conectados"]),
            que="la sala con los dos conectados")
    print("1. bienvenida sin nave; la sala dice que están los dos: OK")
    pygame.image.save(pantalla, os.path.join(OUT, "red_sala_roles_inicio.png"))

    # J1 (WASD) baja a Forjador y confirma.
    cuadro(a, pygame.K_s)
    esperar(lambda: sala_de(a)["roles"][0]["cursor"] == 1, que="J1 movió el cursor")
    cuadro(a, pygame.K_e)
    esperar(lambda: sala_de(b)["roles"][0]["listo"], que="J1 confirmó")
    assert sala_de(b)["roles"][0]["rol"] == "Forjador"
    # J2 (flechas) empieza en Forjador: no lo puede tomar.
    assert sala_de(b)["roles"][1]["cursor"] == 1
    cuadro(b, pygame.K_RETURN)
    time.sleep(0.4)
    esperar(lambda: True)
    assert not sala_de(b)["roles"][1]["listo"], "tomó un rol que ya era del otro"
    b._dibujar_sala(pantalla)
    pygame.image.save(pantalla, os.path.join(OUT, "red_sala_roles.png"))
    # J1 lo suelta y lo vuelve a tomar (como en el modo local).
    cuadro(a, pygame.K_e)
    esperar(lambda: not sala_de(a)["roles"][0]["listo"], que="J1 soltó su rol")
    cuadro(a, pygame.K_e)
    esperar(lambda: sala_de(a)["roles"][0]["listo"], que="J1 volvió a confirmar")
    # J2 baja a Biomante y confirma.
    cuadro(b, pygame.K_DOWN)
    esperar(lambda: sala_de(b)["roles"][1]["cursor"] == 2, que="J2 movió el cursor")
    cuadro(b, pygame.K_RETURN)
    print("2. mover, confirmar, rol tomado y soltar: OK")

    esperar(lambda: sala_de(a)["fase"] != "roles", que="la sala pasa a armar la nave")
    a._dibujar_sala(pantalla)
    pygame.image.save(pantalla, os.path.join(OUT, "red_sala_carga.png"))
    esperar(lambda: "roles" in a.conexiones[0].bienvenida and "roles" in b.conexiones[0].bienvenida,
            segundos=60, que="los datos de la partida")
    assert a.conexiones[0].bienvenida["roles"] == ["Forjador", "Biomante"], a.conexiones[0].bienvenida["roles"]
    for s in (a, b):
        s.crear_espejo()
        s.preparar_espejo()
    pantallas = [pygame.Surface((1280, 720)) for _ in (a, b)]
    fin = time.time() + 20
    while time.time() < fin:
        for s, p in zip((a, b), pantallas):
            assert s.paso(p, eventos=[]), s.motivo
        if all(s.conexiones[0].ultimo_estado() is not None and s.espejo.listo for s in (a, b)):
            break
        time.sleep(0.02)
    for s, p in zip((a, b), pantallas):
        assert [j.rol for j in s.espejo.g.jugadores] == ["Forjador", "Biomante"]
        for _ in range(5):
            s.paso(p, eventos=[])
    pygame.image.save(pantallas[0], os.path.join(OUT, "red_sala_partida.png"))
    assert any("roles elegidos: ['Forjador', 'Biomante']" in l for l in salida), "".join(salida[-10:])
    print("3. la nave se arma con los roles elegidos y el espejo los usa: OK")
    for s in (a, b):
        s.cerrar()
finally:
    if proceso.poll() is None:
        proceso.kill()
    proceso.wait()

# -- 5. El anfitrión se va en plena sala --------------------------------------------
proceso, puerto, salida = arrancar()
try:
    a = cliente.Sesion(Game(), "127.0.0.1", puerto, [0], avisar=lambda t: None)
    a.anfitrion = True
    a.conectar()
    b = cliente.Sesion(Game(), "127.0.0.1", puerto, [1], avisar=lambda t: None)
    b.conectar()
    time.sleep(0.5)
    t = time.time()
    a.cerrar()
    fin = time.time() + 6
    while time.time() < fin and b.conexiones[0].situacion != "fin":
        time.sleep(0.05)
    assert b.conexiones[0].situacion == "fin", b.conexiones[0].situacion
    try:
        cuadro(b)
        raise AssertionError("la sala siguió como si nada")
    except cliente.Cancelado as cancelado:
        assert cancelado.motivo == "fin", cancelado.motivo
    print(f"5. el anfitrión se va en la sala: el otro recibe `fin` en {time.time() - t:.1f} s: OK")
    b.cerrar()
    proceso.wait(6)
finally:
    if proceso.poll() is None:
        proceso.kill()

print(f"OK prueba_red_sala en {time.time() - INICIO:.1f} s")
