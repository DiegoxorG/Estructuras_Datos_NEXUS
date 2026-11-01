"""Capturas del HUD con 2, 3 y 4 jugadores en varias resoluciones, sin ventana.

    python pruebas/prueba_hud.py

Pone a la vez lo que más se pelea por espacio (tutorial, aviso de evento,
cartel de la IA, pista + barra de progreso, mensaje) y guarda
pruebas/capturas/hud_<jugadores>j_<ancho>x<alto>[_apagon].png para revisarlas
a ojo. También revisa solo que ningún texto del HUD se salga de su mitad.
"""

import os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)
import pygame; pygame.init()
OUT = os.path.join(RAIZ, "pruebas", "capturas")
os.makedirs(OUT, exist_ok=True)

from juego import app as App
from juego import objetos_mapa
objetos_mapa.mapa_activo = lambda: "Nave"
DT = 1000 // 60
NOMBRES = [r["nombre"] for r in App.ROLES]


def partida(n):
    g = App.Game()
    g.cantidad_jugadores = n
    g.abrir_seleccion_roles()
    for i, e in enumerate(g.seleccion_roles):
        e["listo"], e["rol"] = True, NOMBRES[i]
    g.iniciar_partida()
    for _ in range(80):
        if g.transitions.is_idle(): break
        g.transitions.update(g, 33)
    g.current_screen = "partida"
    return g


def escena(g, apagon):
    j = g.jugadores
    for a in g.aliens:
        a.descanso_ms = 10 ** 9
    for _ in range(30):
        g._actualizar_partida(DT)
    j[0].avisar("¡Te atrapó el Cazador 2! -10", (236, 70, 60))
    j[0].pista_mision = "Mantener: encender la caja de fusibles"
    j[0].progreso = ("Cambiando fusibles", 0.6)
    if len(j) > 1:
        j[1].avisar("Pieza recogida (2)", (96, 200, 120))
    g.eventos.lanzar("alarma")
    if apagon:
        if g.tutorial is not None: g.tutorial.activo = False
        g.eventos.lanzar("apagon")
    g.decir("apagon", forzar=True)
    for _ in range(90):
        g.narrador.actualizar(DT)
    # Pista y progreso se vuelven a calcular cada frame: se fijan después.
    j[0].pista_mision = "Mantener: encender la caja de fusibles"
    j[0].progreso = ("Cambiando fusibles", 0.6)


for n in (2, 3, 4):
    g = partida(n)
    for tam in ((1280, 720), (1366, 768), (1920, 1080)):
        for apagon in (False, True):
            if apagon and tam != (1366, 768):
                continue
            g.screen = pygame.Surface(tam)
            g.ancho, g.alto = tam
            g2 = g
            escena(g2, apagon)
            g2._dibujar()
            nombre = f"hud_{n}j_{tam[0]}x{tam[1]}{'_apagon' if apagon else ''}.png"
            pygame.image.save(g2.screen, os.path.join(OUT, nombre))
            print("guardada", nombre)
            g2.eventos.terminar()
            if apagon:
                g2.eventos.restaurar_luz()
print("\nlisto: revisar pruebas/capturas/hud_*.png")
