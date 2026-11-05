"""Reconexión: un corte a mitad del saludo no es un "no" del servidor.

    python pruebas/prueba_red_saludo_cortado.py

Antes, si al volver con el token la conexión se cerraba antes de la
bienvenida (wifi que va y viene, el servidor que todavía no soltó la conexión
vieja), el cliente lo tomaba como un rechazo y se rendía para siempre
(situación "perdida" sin haber reintentado). Solo un `error` del servidor
debe cortar los reintentos.

Se prueba `Conexion._reconectar` sin sockets: el saludo falla primero con un
corte (ConexionCerrada) y después responde bien.
"""

import os
import sys
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

from cliente_servidor import cliente
from cliente_servidor.protocolo import ConexionCerrada


class SockFalso:
    def close(self):
        pass


def conexion_falsa(respuestas):
    """Una Conexion sin hilo ni socket, con un `_saludar` que va dando
    `respuestas` (una excepción o un resultado) en orden."""
    c = cliente.Conexion.__new__(cliente.Conexion)
    c.sock = SockFalso()
    c.cerrando = False
    c.reconexiones = 0
    c.situacion = "jugando"
    c.fin_texto = ""
    c.intentos = 0

    def saludar(esperar_s, saludo_s):
        r = respuestas[min(c.intentos, len(respuestas) - 1)]
        c.intentos += 1
        if isinstance(r, Exception):
            raise r
        return r

    c._saludar = saludar
    return c


cliente.time.sleep = lambda s: None        # sin esperas entre reintentos

# 1. Corte a mitad del saludo y después bien: vuelve.
c = conexion_falsa([ConexionCerrada("el otro lado cerró"), (SockFalso(), None, {"tipo": "bienvenida"})])
inicio = time.time()
assert c._reconectar(), "un corte en el saludo debe reintentarse"
assert c.intentos == 2 and c.reconexiones == 1 and c.situacion == "jugando", (c.intentos, c.situacion)
print("corte a mitad del saludo -> reintenta y vuelve: OK")

# 2. El servidor dice que no: no se reintenta.
c = conexion_falsa([cliente.Rechazado("ese token no es de esta partida")])
assert not c._reconectar()
assert c.intentos == 1 and "token" in c.fin_texto
print("rechazo del servidor -> no reintenta: OK")

# 3. Un `error` en vez de bienvenida se convierte en Rechazado.
assert issubclass(cliente.Rechazado, ConexionCerrada)
print("OK prueba_red_saludo_cortado")
