"""Prueba de la vista de los grafos (Pausa > Opciones > Grafo).

    python pruebas/prueba_vista_grafo.py

Prende la vista desde la pausa, hace que pase de todo en NEXUS (un rumor
viajando por BFS, un "¿De dónde salió esto?", un bot reportado) y en la nave
(un alien buscando camino con A*) y guarda capturas en pruebas/capturas.
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
from juego.dificultad import Dificultad
from juego.navegacion import Navegacion
objetos_mapa.mapa_activo = lambda: "Nave"
DT = 1000 // 60


class Teclas(dict):
    def __getitem__(self, k):
        return self.get(k, False)


pygame.key.get_pressed = lambda: Teclas()
NOM = [r["nombre"] for r in App.ROLES]


def avanzar(g):
    for _ in range(80):
        if g.transitions.is_idle():
            break
        g.transitions.update(g, 33)


for ancho, alto in [(1366, 768), (1920, 1080)]:
    g = App.Game()
    g.screen = pygame.Surface((ancho, alto)); g.ancho, g.alto = ancho, alto
    g.cantidad_jugadores = 2
    g.abrir_seleccion_roles(ir=False)
    for i, e in enumerate(g.seleccion_roles):
        e["listo"], e["rol"] = True, NOM[i]
    g.dificultad = Dificultad("normal")
    g.iniciar_partida(); avanzar(g); g.current_screen = "partida"
    g.saltar_tutorial()
    g.presentacion = None   # la ventana de alien nuevo pausaría la prueba
    red = g.nexus
    j1 = g.jugadores[0]

    # Desde la pausa: Opciones > Grafo: NEXUS.
    g._manejar_tecla(pygame.K_ESCAPE)
    assert g.pausa is not None
    g.pausa.activar(1)                                   # Opciones
    i = [a for _, a in g.pausa.opciones()].index("grafo")
    g.pausa.seleccion = i
    g._manejar_tecla(pygame.K_RIGHT)
    assert g.vista_grafo == "nexus", g.vista_grafo
    g._manejar_tecla(pygame.K_ESCAPE); g._manejar_tecla(pygame.K_ESCAPE)
    assert g.pausa is None

    # Pasa de todo: un rumor viajando, un rastreo y un bot reportado.
    pub = red.lanzar_rumor()
    for _ in range(int(3000 / DT)):
        g._actualizar_partida(DT)
    # El rumor ya llegó a alguien (si la red es chica puede haber terminado de propagarse).
    assert len(pub.alcanzados) > 0
    camino = red.rastrear(j1, pub)
    assert red.ultimo_rastreo[0] == camino
    bot = red.bots()[0]
    red.reportar(j1, bot)
    assert bot not in red.grafo and red.borrados[-1][0] == bot
    g._actualizar_partida(DT)
    g._dibujar()
    pygame.image.save(g.screen, os.path.join(OUT, f"grafo_nexus_{ancho}.png"))
    print(f"{ancho}x{alto} NEXUS: {len(red.grafo)} nodos, rumor nivel "
          f"{red.propagaciones[0].niveles if red.propagaciones else '-'}, "
          f"camino {len(camino)} saltos, bot borrado")

    # Nave: un alien va a un ruido lejos (busca camino con A*).
    g._manejar_tecla(pygame.K_ESCAPE)
    g.pausa.activar(1)
    g.pausa.seleccion = [a for _, a in g.pausa.opciones()].index("grafo")
    g._manejar_tecla(pygame.K_RIGHT)
    assert g.vista_grafo == "nave"
    g._manejar_tecla(pygame.K_ESCAPE); g._manejar_tecla(pygame.K_ESCAPE)
    alien = next(a for a in g.aliens if a is not g.cambiaformas)
    lejos = max(g.npcs.puntos, key=lambda p: (p[0] - alien.centro[0]) ** 2 + (p[1] - alien.centro[1]) ** 2)
    alien.descanso_ms = 0
    alien.oir(lejos)
    for _ in range(30):
        g._actualizar_partida(DT)
    assert Navegacion.ultima_busqueda is not None
    g._dibujar()
    pygame.image.save(g.screen, os.path.join(OUT, f"grafo_nave_{ancho}.png"))
    print(f"{ancho}x{alto} nave: última búsqueda revisó "
          f"{len(Navegacion.ultima_busqueda['explorados'])} celdas")

    # Prender el árbol del alien apaga el grafo (una vista a la vez).
    g._manejar_tecla(pygame.K_ESCAPE)
    g.pausa.activar(1)
    g.pausa.seleccion = [a for _, a in g.pausa.opciones()].index("arbol")
    g._manejar_tecla(pygame.K_RIGHT)
    assert g.mostrar_arbol_alien and g.vista_grafo is None

print("\nTODO OK")
