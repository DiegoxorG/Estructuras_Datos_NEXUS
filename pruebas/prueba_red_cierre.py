"""Cómo se apaga el servidor, y lo que pasa con una IP mal escrita o basura.

    python pruebas/prueba_red_cierre.py

1. La IP del menú: "192.168..1" tumbaba el juego (UnicodeError, que no es
   OSError) y "1.2.3.4.5" congelaba la ventana ~15 s reintentando.
2. El servidor levantado por el menú (--con-padre) se apaga solo, avisando
   `fin`, cuando el juego le cierra la entrada (en Windows no hay Ctrl+C
   para otro proceso) o cuando el juego se muere (antes quedaba huérfano con
   el puerto tomado).
3. SIGTERM lo apaga avisando `fin` (antes SDL se quedaba con la señal y el
   servidor seguía vivo).
4. Un cliente que manda basura (intenciones con tipos raros, JSON muy
   anidado) pierde su conexión y nada más: el otro sigue jugando.
"""

import os
import signal
import socket
import subprocess
import sys
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

from cliente_servidor import lanzador, cliente
from cliente_servidor.protocolo import VERSION, LectorLineas, enviar, ConexionCerrada

INICIO = time.time()

# -- 1. La IP del menú ----------------------------------------------------------
assert lanzador.direccion("") == ("127.0.0.1", 5050)
assert lanzador.direccion(" 192.168.1.20 ") == ("192.168.1.20", 5050)
assert lanzador.direccion("192.168.1.20:6000") == ("192.168.1.20", 6000)
for mala in ("192.168..1", "1.2.3.4.5", "999.1.1.1", ".", "192.168.1.", "1:2:3", "::1",
             "10.0.0.1:99999", "10.0.0.1:0", "10.0.0.1:abc"):
    host, texto = lanzador.direccion(mala)
    assert host is None and isinstance(texto, str), (mala, host, texto)
for mala in ("192.168..1", "1.2.3.4.5"):
    t = time.time()
    try:
        cliente._conectar(mala, 5050, 15)
        raise AssertionError("conectó a " + mala)
    except OSError:
        pass
    assert time.time() - t < 3, f"{mala}: se quedó reintentando {time.time() - t:.1f} s"
print("1. IP mal escrita: aviso, sin tumbar ni congelar: OK")


def arrancar(*extra, entrada=None):
    proceso = subprocess.Popen(
        [sys.executable, "-u", "-m", "cliente_servidor.servidor", "--jugadores", "2",
         "--puerto", "0", "--mapa", "Nave", "--sin-presentaciones", "--aliens-quietos",
         "--segundos", "60", *extra],
        cwd=RAIZ, stdin=entrada, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    lineas = []
    for linea in proceso.stdout:
        lineas.append(linea)
        if "escuchando en" in linea:
            return proceso, int(linea.split("escuchando en ")[1].split()[0].rsplit(":", 1)[1])
    raise AssertionError("el servidor no arrancó: " + "".join(lineas))


def entrar(puerto, nombre):
    s = socket.create_connection(("127.0.0.1", puerto), timeout=30)
    lector = LectorLineas(s)
    enviar(s, {"tipo": "hola", "version": VERSION, "nombre": nombre})
    b = lector.siguiente()
    assert b["tipo"] == "bienvenida", b
    return s, lector


def hasta_fin(lector, segundos=8):
    """Lee hasta el `fin` (True) o hasta que se corte sin él (False)."""
    limite = time.time() + segundos
    try:
        while time.time() < limite:
            if lector.siguiente().get("tipo") == "fin":
                return True
    except (OSError, ConexionCerrada):
        return False
    return False


# -- 2. El padre cierra la entrada --------------------------------------------------
proceso, puerto = arrancar("--con-padre", entrada=subprocess.PIPE)
try:
    s, lector = entrar(puerto, "uno")
    lector.siguiente()                       # (un "espera": falta el otro jugador)
    proceso.stdin.close()                    # lo que hace lanzador.cerrar_servidor
    assert hasta_fin(lector), "al cerrarle la entrada no avisó `fin`"
    proceso.wait(6)
    s.close()
finally:
    if proceso.poll() is None:
        proceso.kill()
        raise AssertionError("con la entrada cerrada el servidor siguió vivo")
print("2. el servidor del menú se apaga cuando el juego le cierra la entrada (con `fin`): OK")

# -- 3. SIGTERM (Linux/Mac) ------------------------------------------------------------
if os.name != "nt":
    proceso, puerto = arrancar()
    try:
        a, la = entrar(puerto, "a")
        b, lb = entrar(puerto, "b")
        assert la.siguiente()["tipo"] in ("estado", "espera")   # ya armó la partida (pygame.init)
        proceso.send_signal(signal.SIGTERM)
        assert hasta_fin(la), "con SIGTERM no avisó `fin`"
        proceso.wait(6)
        a.close(); b.close()
    finally:
        if proceso.poll() is None:
            proceso.kill()
            raise AssertionError("con SIGTERM el servidor siguió vivo (SDL se quedó con la señal)")
    print("3. SIGTERM apaga el servidor avisando `fin`: OK")

# (La basura de un cliente se prueba sin sockets en prueba_red_estado.py.)

print(f"OK prueba_red_cierre en {time.time() - INICIO:.1f} s")
