"""El protocolo entre el servidor y los clientes (ver docs/cliente_servidor.md).

TCP, y cada mensaje es un objeto JSON en UNA línea terminada en "\\n". TCP es
un chorro de bytes, no de mensajes: un `recv` puede traer medio mensaje o tres
pegados. Por eso `LectorLineas` junta lo que llega en un búfer y solo entrega
líneas completas. `json.dumps` escapa los saltos de línea de los textos, así
que un mensaje nunca se parte en dos líneas.

Aquí no hay nada de pygame: lo usan igual el servidor (sin ventana), el
cliente y las pruebas.
"""

import json
import socket


VERSION = 1
HOST = "127.0.0.1"
PUERTO = 5050

# El servidor corre el juego a 60 cuadros por segundo (la velocidad de los
# personajes va por cuadro, así que tiene que ser el mismo ritmo del modo
# local) y manda una instantánea cada 2 cuadros: 30 por segundo.
HZ_JUEGO = 60
CUADROS_POR_INSTANTANEA = 2

# Lo que el cliente puede pedir. Son nombres de acciones, no teclas: cada
# cliente traduce sus teclas o su mando, y el servidor las vuelve a traducir a
# las teclas del puesto de ese jugador (entidades/jugador.py).
MANTENER = ("arriba", "abajo", "izquierda", "derecha", "sigilo", "interactuar")
PULSAR = ("arriba", "abajo", "izquierda", "derecha", "interactuar", "habilidad",
          "habilidades", "celular", "soltar", "volver")

# Una línea más larga que esto es un cliente roto (o alguien mandando basura):
# se corta la conexión en vez de llenar la memoria.
MAXIMO_LINEA = 1 << 20


class ConexionCerrada(Exception):
    """El otro lado cerró el socket (o mandó algo que no se entiende)."""


def a_bytes(mensaje):
    """Un dict -> la línea de bytes que se manda."""
    texto = json.dumps(mensaje, ensure_ascii=False, separators=(",", ":"), default=str)
    return (texto + "\n").encode("utf-8")


def enviar(sock, mensaje):
    sock.sendall(a_bytes(mensaje))


def sin_nagle(sock):
    """Los mensajes son chiquitos y van seguido: sin esto TCP los junta y
    espera (algoritmo de Nagle) y se sienten 40 ms de retraso."""
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError:
        pass


class LectorLineas:
    """Saca mensajes JSON completos de un socket, uno por línea."""

    def __init__(self, sock):
        self.sock = sock
        self.bufer = b""

    def siguiente(self):
        """El siguiente mensaje (bloquea hasta que llegue uno completo).

        Si el socket tiene timeout y no llega nada, sale `socket.timeout` y el
        búfer queda como estaba: se puede volver a llamar."""
        while True:
            corte = self.bufer.find(b"\n")
            if corte >= 0:
                linea, self.bufer = self.bufer[:corte], self.bufer[corte + 1:]
                if not linea.strip():
                    continue
                try:
                    mensaje = json.loads(linea.decode("utf-8"))
                except (UnicodeDecodeError, ValueError):
                    raise ConexionCerrada("mensaje que no es JSON")
                if not isinstance(mensaje, dict):
                    raise ConexionCerrada("mensaje que no es un objeto")
                return mensaje
            if len(self.bufer) > MAXIMO_LINEA:
                raise ConexionCerrada("línea demasiado larga")
            datos = self.sock.recv(65536)
            if not datos:
                raise ConexionCerrada("el otro lado cerró")
            self.bufer += datos
