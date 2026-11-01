"""Prueba del flujo previo a la partida: cuántos juegan y quién es quién.

    python pruebas/prueba_seleccion.py

Recorre el menú -> cantidad -> selección de rol -> partida con 2, 3 y 4
jugadores, y comprueba lo que es fácil romper sin darse cuenta: que las teclas
de un jugador no muevan el cursor de otro, que dos no puedan quedarse con el
mismo rol, que volver a confirmar deshaga la elección, y que los puestos sin
mando se dibujen pero no caminen. Las capturas quedan en pruebas/capturas/.
"""

import os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)
import pygame; pygame.init()
OUT = os.path.join(RAIZ, "pruebas", "capturas", "seleccion")
os.makedirs(OUT, exist_ok=True)
from juego import app as App
from juego import objetos_mapa
objetos_mapa.mapa_activo = lambda: "Nave"   # el único mapa del juego

CONFIRMAR = [pygame.K_e, pygame.K_RETURN, pygame.K_o, pygame.K_y]
ARRIBA    = [pygame.K_w, pygame.K_UP, pygame.K_i, pygame.K_t]
ABAJO     = [pygame.K_s, pygame.K_DOWN, pygame.K_k, pygame.K_g]

def avanzar(g):
    for _ in range(80):
        if g.transitions.is_idle(): break
        g.transitions.update(g, 33)

for cantidad in (2, 3, 4):
    g = App.Game()
    g._activar_opcion_menu("jugar"); avanzar(g); g.current_screen = "cantidad"
    while g.cantidad_seleccionada != cantidad - 2: g._manejar_tecla(pygame.K_DOWN)
    g._dibujar(); pygame.image.save(g.screen, f"{OUT}/cantidad_{cantidad}.png")
    g._manejar_tecla(pygame.K_RETURN); avanzar(g); g.current_screen = "roles"
    print(f"\n=== {cantidad} JUGADORES ===")
    g._dibujar(); pygame.image.save(g.screen, f"{OUT}/roles_{cantidad}_inicio.png")

    # --- las teclas de un jugador no mueven el cursor de otro ---
    antes = [s["cursor"] for s in g.seleccion_roles]
    g._manejar_tecla(pygame.K_s)            # solo el jugador 1
    despues = [s["cursor"] for s in g.seleccion_roles]
    movidos = [i for i,(a,b) in enumerate(zip(antes,despues)) if a!=b]
    print("  [S] mueve solo al jugador:", movidos, "(debe ser [0])")

    # --- jugador 1 toma el primer rol ---
    g.seleccion_roles[0]["cursor"] = 0
    g._manejar_tecla(CONFIRMAR[0])
    print("  j1 ->", g.seleccion_roles[0]["rol"])

    # --- jugador 2 intenta el MISMO rol ---
    g.seleccion_roles[1]["cursor"] = 0
    g._manejar_tecla(CONFIRMAR[1])
    print("  j2 intenta el mismo rol -> listo:", g.seleccion_roles[1]["listo"], "(debe ser False)")

    # --- cada uno toma uno distinto ---
    for puesto in range(1, cantidad):
        g.seleccion_roles[puesto]["cursor"] = puesto
        g._manejar_tecla(CONFIRMAR[puesto])
    g._dibujar(); pygame.image.save(g.screen, f"{OUT}/roles_{cantidad}_fin.png")
    print("  roles:", [s["rol"] for s in g.seleccion_roles])
    avanzar(g)
    print("  pantalla:", g.current_screen, "| viewports:",
          len(__import__('screens.partida', fromlist=['x']).calcular_viewports(g.ancho, g.alto, cantidad)))
    g.current_screen = "partida"
    for _ in range(5): g._actualizar_partida(16)
    g._dibujar(); pygame.image.save(g.screen, f"{OUT}/partida_{cantidad}.png")
    for j in g.jugadores:
        print(f"    {j.rol:11} {j.nombre_personaje:7} {j.controles_nombre:16} "
              f"{'se mueve' if j.puede_moverse else 'SIN MANDO'}")

    # --- los que no tienen mando no se mueven ---
    import collections
    teclas = collections.defaultdict(bool)
    for k in (pygame.K_d, pygame.K_RIGHT, pygame.K_i, pygame.K_t, pygame.K_l): teclas[k]=True
    pos = [(j.personaje.x, j.personaje.y) for j in g.jugadores]
    for _ in range(20):
        for j in g.jugadores: j.actualizar(teclas, g.mundo.colisiona)
    for i, j in enumerate(g.jugadores):
        movido = (j.personaje.x, j.personaje.y) != pos[i]
        esperado = j.puede_moverse
        estado = "ok" if movido == esperado else "MAL"
        print(f"    {j.rol:11} movido={movido} esperado={esperado} {estado}")

    # --- deshacer ---
    g.current_screen = "roles"
    g._manejar_tecla(CONFIRMAR[0])
    print("  j1 pulsa de nuevo -> listo:", g.seleccion_roles[0]["listo"], "(debe ser False)")
# La pantalla de carga: el Cambiaformas persigue a los personajes elegidos.
from screens.carga import render_carga, precargar
CARGA = os.path.join(RAIZ, "pruebas", "capturas")
for roles in (["Tecnomante"], ["Biomante", "Resonante"], ["Forjador", "Resonante", "Tecnomante"],
              ["Tecnomante", "Resonante", "Biomante", "Forjador"]):
    for tam in ((1280, 720), (1920, 1080)):
        lienzo = pygame.Surface(tam)
        precargar(tam[1], roles)
        for t in (300, 1200):          # 1200: en pleno salto del Cambiaformas
            render_carga(lienzo, t, 0.5, "Consejo de prueba para ver cómo queda.", roles)
            pygame.image.save(lienzo, os.path.join(CARGA, f"carga_{len(roles)}j_{tam[0]}_{t}.png"))
print("pantalla de carga: el Cambiaformas persigue a 1, 2, 3 y 4 personajes (capturas carga_*)")
# Al terminar la carga, durante el fundido a la partida, siguen los mismos
# personajes (antes, esos últimos cuadros salían con el Tecnomante).
import screens.carga as modulo_carga
vistos = []
original = modulo_carga.render_carga
modulo_carga.render_carga = lambda pantalla, t, p, consejo="", roles=None: vistos.append(roles)
g = App.Game()
g.current_screen = "cargando"
g.carga = {"ms": 0, "listo": True, "error": None, "consejo": "", "roles": ["Biomante", "Resonante"]}
g._actualizar_carga(g.MIN_CARGA_MS + 10)
assert g.carga is None, "terminó la carga"
for _ in range(40):
    if g.current_screen != "cargando":
        break
    g._dibujar()
    g._actualizar_carga(33)
    g.transitions.update(g, 33)
modulo_carga.render_carga = original
assert vistos and all(r == ["Biomante", "Resonante"] for r in vistos), vistos
print(f"fin de la carga: {len(vistos)} cuadros del fundido, todos con Biomante y Resonante")
print("\nTODO OK")
