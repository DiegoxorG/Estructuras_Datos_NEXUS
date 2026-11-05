"""Interpolación en el cliente: que se vea fluido con 30 instantáneas por segundo.

El servidor manda la posición de cada jugador y cada alien 30 veces por
segundo (y por la red pueden llegar a tirones). Si el cliente dibujara
siempre la última, todo avanzaría a saltos de 2 cuadros, más los tirones de
la red. Lo que se hace es dibujar un poquito en el PASADO (RETRASO_MS = 100):
casi siempre hay una instantánea antes y otra después de ese momento, y se
dibuja la mezcla de las dos según cuánto se avanzó entre ellas.

    tiempo del servidor ──●─────────●─────────●────────●──►
                          c=200     c=202     c=204     c=206 (la última)
                                       ▲
                          se dibuja aquí (100 ms antes de la última)

El "tiempo del servidor" sale del número de cuadro (`c`, 60 por segundo):
se estima cuánto le lleva el reloj del cliente al del servidor con la
llegada más rápida que se ha visto (`desfase`), así un mensaje que llega
tarde no mueve la referencia.

Solo se interpolan posiciones y ángulos; lo demás (vidas, paneles, misión)
va con la última instantánea.
"""

import math
import time

from cliente_servidor.protocolo import HZ_JUEGO

RETRASO_MS = 100
GUARDAR = 30            # instantáneas guardadas (un segundo a 30 por segundo)


def posiciones(secciones):
    """{"j0": (x, y, ángulo de linterna), "a3": (x, y, ángulo)} de una instantánea."""
    salida = {}
    i = 0
    while f"j{i}" in secciones:
        j = secciones[f"j{i}"]
        salida[f"j{i}"] = (j["x"], j["y"], j.get("lin", 0.0))
        i += 1
    aliens = secciones.get("al", {})
    for k in range(aliens.get("n", 0)):
        pos = aliens.get(str(k))
        if pos:
            salida[f"a{k}"] = tuple(pos)
    return salida


def _angulo(a, b, t):
    """De a hacia b por el lado más corto (de 179° a -179° son 2°, no 358°)."""
    d = (b - a + math.pi) % (2 * math.pi) - math.pi
    return a + d * t


class Interpolador:
    def __init__(self, retraso_ms=RETRASO_MS, reloj=time.perf_counter):
        self.retraso = retraso_ms / 1000.0
        self.reloj = reloj
        self.bufer = []          # [(cuadro, posiciones)], de la más vieja a la más nueva
        self.desfase = None      # reloj local - tiempo del servidor (el más chico visto)

    def agregar(self, cuadro, secciones, ahora=None):
        ahora = self.reloj() if ahora is None else ahora
        t_servidor = cuadro / HZ_JUEGO
        desfase = ahora - t_servidor
        if self.desfase is None or desfase < self.desfase:
            self.desfase = desfase
        else:
            # Que se adapte despacio si el reloj del servidor se atrasa de verdad.
            self.desfase += (desfase - self.desfase) * 0.002
        if self.bufer and cuadro <= self.bufer[-1][0]:
            self.bufer = [b for b in self.bufer if b[0] < cuadro]   # (empezó otra partida)
        self.bufer.append((cuadro, posiciones(secciones)))
        del self.bufer[:-GUARDAR]

    def ahora(self, ahora=None):
        """{clave: (x, y, ángulo)} para dibujar en este momento."""
        if not self.bufer:
            return {}
        ahora = self.reloj() if ahora is None else ahora
        objetivo = (ahora - self.desfase - self.retraso) * HZ_JUEGO     # en cuadros
        if objetivo >= self.bufer[-1][0]:
            return dict(self.bufer[-1][1])
        if objetivo <= self.bufer[0][0]:
            return dict(self.bufer[0][1])
        for (ca, pa), (cb, pb) in zip(self.bufer, self.bufer[1:]):
            if ca <= objetivo <= cb:
                t = (objetivo - ca) / max(1, cb - ca)
                salida = {}
                for clave, b in pb.items():
                    a = pa.get(clave)
                    if a is None or abs(a[0] - b[0]) + abs(a[1] - b[1]) > 300:
                        salida[clave] = b        # (apareció o se teletransportó)
                        continue
                    salida[clave] = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t,
                                     _angulo(a[2], b[2], t))
                return salida
        return dict(self.bufer[-1][1])
