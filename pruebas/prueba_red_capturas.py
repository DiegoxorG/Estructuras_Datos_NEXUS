"""El cliente en red se ve igual que el modo local (cliente_servidor/espejo.py).

    python pruebas/prueba_red_capturas.py

En el mismo proceso: un servidor (sin sockets) arma una partida y la juega
unos segundos con los jugadores caminando; se toma su instantánea completa,
se pasa por JSON (como por la red) y se copia encima de un juego espejo, como
lo hace el cliente. Después se dibuja la misma pantalla con el modo local
(el Game del servidor) y con el espejo, y se comparan las dos superficies
píxel por píxel: tienen que ser casi iguales (las vistas divididas, el HUD, la
oscuridad, la visión). También se prueba con un apagón (oscuridad y
linterna) y con un panel abierto.

Las capturas quedan en la carpeta temporal (o en NEXUS_CAPTURAS), no en el repo.
"""

import json
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

import pygame

from cliente_servidor.servidor import Servidor, Teclas
from cliente_servidor.espejo import Espejo
from cliente_servidor.protocolo import Reconstructor, comprimir

CARPETA = os.environ.get("NEXUS_CAPTURAS") or os.path.join(tempfile.gettempdir(), "nexus_capturas")
os.makedirs(CARPETA, exist_ok=True)
TAMANO = (1280, 720)
UMBRAL = 0.02          # a lo sumo 2 % de los píxeles distintos


def diferencia(a, b):
    """Fracción de píxeles que cambian más de 24 (en la suma de RGB)."""
    import array
    w, h = a.get_size()
    pa = pygame.image.tobytes(a, "RGB") if hasattr(pygame.image, "tobytes") else pygame.image.tostring(a, "RGB")
    pb = pygame.image.tobytes(b, "RGB") if hasattr(pygame.image, "tobytes") else pygame.image.tostring(b, "RGB")
    distintos = 0
    for i in range(0, len(pa), 3 * 7):         # (uno de cada 7 píxeles: alcanza y es rápido)
        if abs(pa[i] - pb[i]) + abs(pa[i + 1] - pb[i + 1]) + abs(pa[i + 2] - pb[i + 2]) > 24:
            distintos += 1
    return distintos / (len(pa) / (3 * 7))


def caminar(s, cuadros, direcciones):
    g = s.juego
    for _ in range(cuadros):
        teclas = Teclas()
        for j, d in zip(g.jugadores, direcciones):
            for t in j.personaje.controles.get(d, ()):
                teclas[t] = True
        s.teclas = teclas
        g._actualizar_partida(16)


def dibujar(juego, locales):
    sup = pygame.Surface(TAMANO)
    juego._dibujar_partida_en(sup, [juego.jugadores[i] for i in locales], juego._extras_dibujo())
    return sup


def comparar(nombre, s, espejo, locales):
    # Lo que viaja: la instantánea completa, comprimida y en JSON.
    mensaje = json.loads(json.dumps({"tipo": "estado", "c": s.cuadro, "base": None,
                                     "z": comprimir(s.instantanea())}))
    secciones = Reconstructor().aplicar(mensaje)
    espejo.aplicar(secciones)
    local = dibujar(s.juego, locales)
    red = dibujar(espejo.g, locales)
    pygame.image.save(local, os.path.join(CARPETA, f"{nombre}_local.png"))
    pygame.image.save(red, os.path.join(CARPETA, f"{nombre}_red.png"))
    d = diferencia(local, red)
    print(f"{nombre}: {d * 100:.2f} % de píxeles distintos")
    assert d < UMBRAL, f"{nombre}: el cliente no se ve como el local ({d * 100:.1f} %)"


pygame.init()
s = Servidor(2, avisar=lambda t: None, semilla=7, presentaciones=False, aliens_quietos=True)
s.preparar_partida()
s.lista.set()
for p in s.puestos:
    p.ocupado = True
caminar(s, 90, ["derecha", "abajo"])

from juego.app import Game
espejo = Espejo(Game(), s.bienvenida(s.puestos[0]))
espejo.preparar()
s.juego.screen = espejo.g.screen     # (los dos Game comparten la ventana dummy)

comparar("dos_vistas", s, espejo, [0, 1])
comparar("una_vista", s, espejo, [1])

# Con un apagón: oscuridad, linterna y campo de visión.
g = s.juego
if g.eventos is not None:
    g.eventos.apagon = True
    caminar(s, 30, ["izquierda", "arriba"])
    comparar("apagon", s, espejo, [0, 1])
    g.eventos.apagon = False

# Con un panel abierto (el árbol de habilidades de J1).
g.alternar_habilidades(g.jugadores[0])
caminar(s, 2, [None, None])
comparar("panel", s, espejo, [0, 1])

print(f"capturas en {CARPETA}")
print("OK prueba_red_capturas")
