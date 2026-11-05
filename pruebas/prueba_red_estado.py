"""Lo que viaja en las instantáneas y cómo se copia encima del espejo.

    python pruebas/prueba_red_estado.py

Sin sockets, en el mismo proceso (como pruebas/prueba_red_capturas.py): un
servidor arma la partida, se pasan sus instantáneas (completa y delta) por
JSON y el Reconstructor del cliente, y se copian encima de un espejo. Revisa
los casos que dejaban al espejo con estado viejo o roto:

1. El Reconstructor no cambia la instantánea que ya entregó (el hilo lector
   la armaba encima mientras el principal la dibujaba: "dictionary changed
   size during iteration" y el cuadro iba con el dibujo sencillo).
2. Una clave que se borró en el servidor se borra en el espejo (un efecto
   que se acabó, como el mapa del Tecnomante, se quedaba para siempre).
3. Dos atributos que en el espejo son el MISMO dict (el infiltrado es uno de
   los sospechosos) no se pisan: la lista de sospechosos salía con uno
   repetido y otro perdido.
4. Un objeto que en el servidor pasa a None llega a None por delta.
5. Las pistas de controles del espejo son las de ESTA laptop (WASD si juega
   con WASD aquí), no las del puesto en el servidor.
6. Basura por la red: líneas que no son JSON, JSON muy anidado, intenciones
   con tipos raros: se corta esa conexión y nada más.
"""

import json
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

import pygame

from cliente_servidor import estado as E
from cliente_servidor.servidor import Servidor, Teclas
from cliente_servidor.espejo import Espejo
from cliente_servidor.protocolo import Reconstructor, comprimir, LectorLineas, ConexionCerrada


class Red:
    """Lo que hace el servidor al mandar (completa o delta) y el cliente al
    recibir, sin sockets: por JSON, como de verdad."""

    def __init__(self, servidor):
        self.s = servidor
        self.r = Reconstructor()
        self.anterior = None
        self.cuadro = 0

    def mandar(self, completa=False):
        ahora = self.s.instantanea()
        self.cuadro += 2
        if completa or self.anterior is None:
            m = {"tipo": "estado", "c": self.cuadro, "base": None, "z": comprimir(ahora)}
        else:
            cambios = {}
            for seccion, datos in ahora.items():
                d = E.diferencias(self.anterior.get(seccion, {}), datos)
                if d:
                    cambios[seccion] = d
            for seccion in self.anterior:
                if seccion not in ahora:
                    cambios[seccion] = None
            m = {"tipo": "estado", "c": self.cuadro, "base": self.cuadro - 2, "s": cambios}
        self.anterior = ahora
        secciones = self.r.aplicar(json.loads(json.dumps(m)))
        assert secciones is not None
        return secciones


def caminar(s, cuadros, direcciones):
    g = s.juego
    for _ in range(cuadros):
        teclas = Teclas()
        for j, d in zip(g.jugadores, direcciones):
            for t in j.personaje.controles.get(d, ()):
                teclas[t] = True
        s.teclas = teclas
        g._actualizar_partida(16)


pygame.init()
s = Servidor(2, avisar=lambda t: None, semilla=11, presentaciones=False, aliens_quietos=True)
s.preparar_partida()
s.lista.set()
for p in s.puestos:
    p.ocupado = True
caminar(s, 30, ["derecha", "abajo"])
g = s.juego

from juego.app import Game
espejo = Espejo(Game(), s.bienvenida(s.puestos[0]))
espejo.preparar()
red = Red(s)
m = espejo.g

# -- 1. La instantánea entregada no cambia después -----------------------------
primera = red.mandar(completa=True)
copia = json.loads(json.dumps(primera))
g.jugadores[0].efectos["prueba_nueva"] = 1234      # una clave nueva en j0
caminar(s, 4, ["derecha", None])
segunda = red.mandar()
assert "prueba_nueva" in segunda["j0"]["a.efectos"]
assert json.loads(json.dumps(primera)) == copia, \
    "el Reconstructor cambió una instantánea que ya había entregado (carrera con el dibujo)"
assert segunda is not primera
print("1. el Reconstructor no toca lo que ya entregó: OK")

# -- 2. Lo que se borra en el servidor se borra en el espejo --------------------
j0 = g.jugadores[0]
j0.efectos.pop("prueba_nueva", None)
j0.efectos["mapa"] = 4000
espejo.aplicar(red.mandar())
assert "mapa" in m.jugadores[0].efectos
j0.efectos.pop("mapa")
espejo.aplicar(red.mandar())
assert "mapa" not in m.jugadores[0].efectos, \
    f"un efecto que se acabó en el servidor sigue en el espejo: {m.jugadores[0].efectos}"
espejo.aplicar(red.mandar(completa=True))
assert "mapa" not in m.jugadores[0].efectos
# ...pero lo que no viaja (claves que no son texto, objetos) se queda.
# (ni las listas y sets: muy adentro el servidor no los manda por la
# profundidad, como el `leida_por` de las notas de una puerta)
d = {"x": 1, 5: "int", "obj": m, "leida_por": set(), "pos": [1, 2]}
E._mezclar(d, {"y": 2})
assert d == {"y": 2, 5: "int", "obj": m, "leida_por": set(), "pos": [1, 2]}, d
print("2. las claves borradas se borran (y lo que no viaja se queda): OK")

# -- 3. Dos atributos que en el espejo son el mismo dict ------------------------
inf_s, inf_m = g.infiltrado, m.infiltrado
if inf_s is not None and inf_m is not None:
    # En cada lado el infiltrado ES uno de los sospechosos (el mismo dict); en
    # el espejo, otro distinto (cada lado sortea con su propio random).
    k = inf_s.sospechosos.index(inf_s.infiltrado)
    otro = (k + 1) % len(inf_m.sospechosos)
    inf_m.infiltrado = inf_m.sospechosos[otro]
    espejo.aplicar(red.mandar(completa=True))
    nombres_s = [x["nombre"] for x in inf_s.sospechosos]
    nombres_m = [x["nombre"] for x in inf_m.sospechosos]
    assert nombres_m == nombres_s, f"los sospechosos del espejo no son los del servidor: {nombres_m} vs {nombres_s}"
    assert inf_m.infiltrado["nombre"] == inf_s.infiltrado["nombre"]
    print("3. el infiltrado y los sospechosos no se pisan: OK")
else:
    print("3. (este mapa no tiene caso del infiltrado)")

# -- 4. Un objeto que pasa a None ----------------------------------------------
espejo.aplicar(red.mandar())
assert m.cambiaformas is not None
g.quitar_cambiaformas()
espejo.aplicar(red.mandar())
assert not red.r.secciones["cf"].get("ok")
from cliente_servidor.servidor import OBJETOS
assert m.cambiaformas is None or getattr(m.cambiaformas, "nombre", None) is not None, \
    "el Cambiaformas del espejo quedó con todos sus atributos en None"
print("4. un objeto que desaparece no deja al espejo con atributos en None: OK")

# -- 5. Las pistas de controles son las de esta laptop --------------------------
from entidades.jugador import WASD, FLECHAS, MANDO_1
espejo.controles({1: WASD})            # J2 juega con WASD en esta laptop
assert m.jugadores[1].nombre_tecla("interactuar") == "E", m.jugadores[1].nombre_tecla("interactuar")
espejo.controles({0: MANDO_1, 1: FLECHAS})
assert m.jugadores[1].nombre_tecla("interactuar") == "ENTER"
assert m.jugadores[0].esquema == MANDO_1
espejo.aplicar(red.mandar(completa=True))
assert m.jugadores[0].esquema == MANDO_1, "la instantánea no pisa los controles de esta laptop"
print("5. las pistas de controles son las de esta laptop: OK")


# -- 6. Basura por la red ----------------------------------------------------------
class SockFalso:
    def __init__(self, datos):
        self.datos = [datos]

    def recv(self, n):
        return self.datos.pop(0) if self.datos else b""


for basura in (b"no es json\n", b"[1,2]\n", b"[" * 200000 + b"]" * 200000 + b"\n",
               b"\xff\xfe\n", b'{"a": ' * 100000 + b"1" + b"}" * 100000 + b"\n"):
    try:
        LectorLineas(SockFalso(basura)).siguiente()
        raise AssertionError(f"aceptó basura: {basura[:20]!r}")
    except ConexionCerrada:
        pass
print("6a. el lector corta la basura (también el JSON muy anidado): OK")

from cliente_servidor import servidor as S
p = S.Puesto(0)
p.generacion = 1
p.buzon.conectado = True
mensajes = [{"tipo": "intencion", "n": 1, "mantener": ["derecha"]},
            {"tipo": "intencion", "n": 2, "mantener": 5, "pulsar": None},
            {"tipo": "intencion", "n": 3, "mantener": None, "pulsar": {"x": 1}, "aguja": "a"},
            {"tipo": "intencion", "n": [1], "mantener": [["derecha"]], "pulsar": [{}]},
            {"tipo": 7}, {"tipo": "adios"}]


class LectorFalso:
    def siguiente(self):
        if not mensajes:
            raise ConexionCerrada("fin")
        return mensajes.pop(0)


srv = Servidor.__new__(Servidor)
srv.activo = True
srv._leer(LectorFalso(), p, 1)
assert not mensajes, f"el lector se cayó con una intención rara (quedaron {mensajes})"
assert p.buzon.mantener == set() and not p.buzon.conectado
print("6b. intenciones con tipos raros no tumban al lector: OK")

print("OK prueba_red_estado")
