"""Prueba de humo de una partida, sin abrir ventana.

    python pruebas/prueba_partida.py

Pasa por menú, cantidad y selección de rol con las mismas teclas que un
jugador, abre una Terminal NEXUS, desbloquea una rama del árbol de habilidades,
comprueba que uno puede caminar mientras el otro tiene un panel abierto y
termina la ronda. Guarda capturas en pruebas/capturas/ para revisar a ojo.

Usa el driver "dummy" de SDL, así que corre sin monitor y sirve para
comprobar cambios rápido antes de abrir el juego de verdad.
"""

import os, sys, collections
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
objetos_mapa.mapa_activo = lambda: "Nave"   # el único mapa del juego
from entidades.jugador import Jugador

g = App.Game()


def avanzar():
    for _ in range(80):
        if g.transitions.is_idle(): break
        g.transitions.update(g, 33)


def cap(nombre):
    g._dibujar(); pygame.display.flip()
    pygame.image.save(g.screen, os.path.join(OUT, nombre))


# La partida no arranca sola: hay que pasar por cantidad y selección de rol.
g._activar_opcion_menu("jugar"); avanzar(); g.current_screen = "cantidad"
g._manejar_tecla(pygame.K_RETURN)          # 2 jugadores, la primera opción
avanzar(); g.current_screen = "roles"
g.seleccion_roles[0]["cursor"] = 0         # Tecnomante
g._manejar_tecla(pygame.K_e)
g.seleccion_roles[1]["cursor"] = 1         # Forjador
g._manejar_tecla(pygame.K_RETURN)
avanzar(); g.current_screen = "partida"
tec, forj = g.jugadores
assert (tec.rol, forj.rol) == ("Tecnomante", "Forjador")
assert tec.nombre_personaje == "Tecnomante", "cada rol usa sus propios sprites"
print("jugadores:", [(j.rol, j.controles_nombre) for j in g.jugadores])
print("zonas:", [(z["clave"], z["tipo"]) for z in g.zonas])
g.saltar_tutorial()
for a in g.aliens:
    a.descanso_ms = 10 ** 9


def ir_a(jugador, zona):
    jugador.personaje.hitbox.center = zona["rect"].center
    jugador.personaje.sync_sprite_from_hitbox()
    jugador.zona_cerca = g.zona_bajo(jugador)
    assert jugador.zona_cerca is zona, f"{jugador.rol} no detecta {zona['clave']}"


# ---------- 1. Terminal NEXUS ----------
nexus = next(z for z in g.zonas if z["tipo"] == "nexus")
ir_a(tec, nexus)
g._tecla_en_partida(pygame.K_e)
assert tec.ocupado and tec.panel["accion"] == "ayuda_menu"
print("\nNEXUS:", tec.panel["titulo"], "| opciones:", [o["texto"] for o in tec.panel["opciones"]])
cap("a_nexus.png")

# ---------- 2. El otro sigue caminando mientras uno lee ----------
pos_antes = (forj.personaje.x, forj.personaje.y)
teclas = collections.defaultdict(bool); teclas[pygame.K_RIGHT] = teclas[pygame.K_DOWN] = True
for _ in range(20):
    forj.actualizar(teclas, g.mundo.colisiona)
    tec.actualizar(teclas, g.mundo.colisiona)
assert (forj.personaje.x, forj.personaje.y) != pos_antes, "el Forjador debía moverse"
assert tec.ocupado
print("el Forjador camina mientras el Tecnomante tiene la terminal abierta")
cap("b_split.png")
tec.cursor = len(tec.panel["opciones"]) - 1
g._tecla_en_partida(pygame.K_e)     # "Salir"
assert not tec.ocupado

# ---------- 3. Árbol de habilidades ----------
forj.puntos = 120
g.equipo.sumar(120)   # las habilidades se pagan con los puntos del equipo
g._tecla_en_partida(pygame.K_RSHIFT)
assert forj.panel["tipo"] == "habilidades"
print("\nHABILIDADES opciones:", [n.clave for n in forj.arbol.opciones()])
cap("c_habilidades.png")
g._tecla_en_partida(pygame.K_RETURN)  # desbloquea REPARACION
assert [n.clave for n in forj.arbol.desbloqueadas()] == ["INGENIO", "REPARACION"]
assert forj.arbol.opciones() == [], "FABRICACION debió quedar descartada"
cap("d_habilidades_2.png")
g._tecla_en_partida(pygame.K_RSHIFT)  # cierra
assert not forj.ocupado
print("  rama escogida:", [n.clave for n in forj.arbol.desbloqueadas()])

# ---------- 4. Árbol de la Resonante en el panel ----------
res = Jugador(forj.personaje, "Resonante", puesto=2)
res.puntos = 200
assert not res.arbol.vacio, "el árbol de la Resonante no se construyó"
res.arbol.desbloquear("EMISION", res.puntos)
res.abrir_panel({"tipo": "habilidades"})
g.jugadores = [tec, res]
cap("e_resonante.png")
g.jugadores = [tec, forj]
print("\nRESONANTE camino:", [n.clave for n in res.arbol.desbloqueadas()])

# ---------- 5. Ninguna terminal NEXUS encerrada ----------
puerta = g.mision.puerta
g.mundo.paredes.remove(puerta)
malas = g.mundo.zonas_inalcanzables(g.zonas, tec.hitbox.topleft)
g.mundo.paredes.append(puerta)
assert not malas, f"terminales inalcanzables: {[z['clave'] for z in malas]}"
print("terminales NEXUS: todas alcanzables")

# ---------- 6. Sin límite de tiempo, y resultados ----------
assert g.tiempo_restante_ms is None
g._actualizar_partida(1000)
assert g.current_screen == "partida", "no se pierde por tiempo"
g.terminar_ronda()            # lo que hace Terminar partida en la pausa
avanzar(); g.current_screen = "resultados"
cap("f_resultados.png")
print("\nronda terminó, pantalla:", g.current_screen)
print("TODO OK")
