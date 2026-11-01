"""Prueba de "que se sienta": latido, pasos, susto y la IA de la nave, sin ventana.

    python pruebas/prueba_ambiente.py

No se puede oír nada sin parlantes, así que se revisa QUÉ sonaría y con qué
volumen (Ambiente.ultimos). Guarda capturas del susto y de la IA hablando.
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

for nombre in ("latido", "paso_alien", "captura", "alarma", "puerta", "consola", "nota",
               "acierto", "fallo", "ia_voz"):
    assert os.path.exists(os.path.join("Audio", "SFX", nombre + ".wav")), f"falta {nombre}.wav"
print("los 10 sonidos están en Audio/SFX")

g = App.Game()
def avanzar():
    for _ in range(80):
        if g.transitions.is_idle(): break
        g.transitions.update(g, 33)
g._activar_opcion_menu("jugar"); avanzar(); g.current_screen = "cantidad"
g._manejar_tecla(pygame.K_RETURN); avanzar(); g.current_screen = "roles"
g.seleccion_roles[0]["cursor"] = 0; g._manejar_tecla(pygame.K_e)
g.seleccion_roles[1]["cursor"] = 1; g._manejar_tecla(pygame.K_RETURN)
avanzar(); g.current_screen = "partida"
j1, j2 = g.jugadores

assert g.narrador.dichas and g.narrador.dichas[0][0] in ("inicio", "tutorial")
print("la IA saluda al empezar:", g.narrador.dichas[0][1])
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "ambiente_a_ia.png"))

def latidos(segundos):
    g.ambiente.ultimos.clear()
    for _ in range(int(segundos * 1000 / DT)):
        g.ambiente.actualizar(DT, g.jugadores, [])
    return [v for n, v in g.ambiente.ultimos if n == "latido"]

for j in g.jugadores:
    j.pulso = 20
tranquilos = latidos(10)
for j in g.jugadores:
    j.pulso = 95
nerviosos = latidos(10)
print(f"latidos en 10 s: tranquilo {len(tranquilos)} (vol {tranquilos[0]}), "
      f"en pánico {len(nerviosos)} (vol {nerviosos[0]})")
assert len(nerviosos) > len(tranquilos) and nerviosos[0] > tranquilos[0]

# Pasos: más fuertes cerca.
alien = g.aliens[0]
alien.accion = "PATRULLAR"
def pasos(distancia):
    g.ambiente.ultimos.clear(); g.ambiente.pasos_ms.clear()
    alien.hitbox.center = (j1.hitbox.centerx + distancia, j1.hitbox.centery)
    j2.personaje.hitbox.center = (5000, 5000)
    for _ in range(60):
        g.ambiente.actualizar(DT, g.jugadores, [alien])
    return [v for n, v in g.ambiente.ultimos if n == "paso_alien"]
cerca, lejos, nada = pasos(80), pasos(500), pasos(900)
print(f"pasos del alien: a 80 px vol {cerca[0]}, a 500 px vol {lejos[0]}, a 900 px {len(nada)} pasos")
assert cerca[0] > lejos[0] and not nada

# Susto al ser atrapado.
g.ambiente.ultimos.clear()
g._atrapar(j1, alien)
# Cada tipo de alien tiene su susto (y su sonido).
esperado = {"ciego": "captura_ciego", "cazador": "captura_cazador", "vigia": "captura_vigia"}.get(alien.tipo, "captura")
assert j1.susto_ms > 0 and j1.susto_tipo in (alien.tipo, "alien") and (esperado, 1.0) in g.ambiente.ultimos
assert g.narrador.dichas[-1][0] == "atrapado"
from juego.ambiente import temblor
assert temblor(j1, 1234) != (0, 0)
g.narrador.restante_ms = 0
for _ in range(6):
    g.ambiente.actualizar(DT, g.jugadores, [])
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "ambiente_b_susto.png"))
for _ in range(60):
    g.ambiente.actualizar(DT, g.jugadores, [])
assert j1.susto_ms == 0 and temblor(j1, 1234) == (0, 0)
print("susto: suena, la pantalla tiembla y se pasa solo; la IA dice:", g.narrador.dichas[-1][1])

# La IA no habla encima de sí misma, salvo lo importante.
g.narrador.enfriamiento_ms = 5000
assert not g.decir("consola", "Tecnomante")
assert g.decir("huida", forzar=True)
print("enfriamiento de la IA: respeta la pausa y lo forzado pasa igual")

print("\nTODO OK")
