"""Prueba del editor de mapa y de que el juego use lo que se guarda, sin ventana.

    python pruebas/prueba_editor_mapa.py

Abre el editor sobre la nave con un archivo de prueba vacío, pone, mueve y
borra cosas con "clics" simulados, revisa que avise lo que choca con paredes,
guarda y arranca una partida con ese archivo para ver que el juego lo use.
No toca Hitboxes/Nave_objetos.json ni el mapa activo.

Guarda una captura en pruebas/capturas/editor_mapa.png.
"""

import os, sys, math, copy
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "Editores"))
os.chdir(RAIZ)
import pygame; pygame.init()
pygame.display.set_mode((1366, 768))
OUT = os.path.join(RAIZ, "pruebas", "capturas")
os.makedirs(OUT, exist_ok=True)
import tempfile
TEMP = os.path.join(tempfile.gettempdir(), "_objetos_prueba_editor.json")
if os.path.exists(TEMP):
    os.remove(TEMP)

from juego import objetos_mapa
from editor_mapa import EditorMapa, HERRAMIENTAS

real = objetos_mapa.ruta_archivo("Nave")
with open(real, "rb") as fh:
    real_antes = fh.read()
activo_antes = objetos_mapa.mapa_activo()

ed = EditorMapa("Nave", ruta_salida=TEMP)
fabrica = objetos_mapa.normalizar(objetos_mapa.por_defecto())
for parte in ("escondites", "terminales", "paneles", "piezas", "rutas_aliens", "nexus"):
    assert ed.datos[parte] == [], parte
print("con un archivo nuevo arranca vacío")
assert not ed.problemas, ed.problemas


# Las coordenadas de abajo se escribieron para un cuarto abierto: P() las
# lleva a la prisión de la nave, que es amplia y sin paredes en medio.
def P(x, y):
    return (x - 768 + 2250, y - 640 + 1250)

def usar(nombre):
    ed.herramienta = [h["clave"] for h in HERRAMIENTAS].index(nombre)

def en_pantalla(p):
    return ed.a_pantalla(p)

def clic(p):
    ed.clic_izquierdo(en_pantalla(p)); ed.soltar()

# Poner un escondite en un lugar libre, moverlo y borrarlo.
usar("escondites")
libre = P(768, 560)
clic(libre)
assert len(ed.datos["escondites"]) == 1
nuevo = ed.datos["escondites"][-1]
assert nuevo["clave"] and nuevo["nombre"] == "Casillero"
print("\nescondite puesto con clic:", nuevo["clave"], "| problemas:", len(ed.problemas))
ed.clic_izquierdo(en_pantalla(libre)); ed.arrastrar(en_pantalla(P(800, 600))); ed.soltar()
movido = ed.datos["escondites"][-1]
assert abs(movido["rx"] * ed.mundo.ancho - P(800, 600)[0]) < 4 and abs(movido["ry"] * ed.mundo.alto - P(800, 600)[1]) < 4
print("arrastrado a", (round(movido["rx"], 3), round(movido["ry"], 3)))

# Uno encima de una pared: el editor lo marca.
pared = ed.mundo.paredes[0].center
clic(pared)
assert any("pared" in p for p in ed.problemas), ed.problemas
print("en una pared ->", [p for p in ed.problemas if "pared" in p])
ed.clic_derecho(en_pantalla(pared))
assert not any("pared" in p for p in ed.problemas)
print("clic derecho lo borra")

# Deshacer y rehacer.
antes = len(ed.datos["escondites"])
ed.deshacer_uno()
assert len(ed.datos["escondites"]) == antes + 1
ed.rehacer_uno()
assert len(ed.datos["escondites"]) == antes
print("deshacer / rehacer funcionan")

# Ruta nueva: tres puntos libres y uno que cruza una pared.
usar("rutas_aliens")
ed.nueva_ruta()
for p in [P(600, 640), P(930, 640), P(930, 900)]:
    clic(p)
ruta = ed.datos["rutas_aliens"][-1]
assert len(ruta) == 3 and ed.ruta_elegida == len(ed.datos["rutas_aliens"]) - 1
print("\nruta nueva con 3 puntos:", ruta)
assert not ed.tramos_malos.get(ed.ruta_elegida), ed.tramos_malos
clic(P(60, 900))        # al otro lado de la pared de la prisión
assert ed.tramos_malos.get(ed.ruta_elegida), "debió detectar el tramo que cruza la pared"
print("el tramo que cruza una pared sale marcado:", ed.tramos_malos[ed.ruta_elegida])
ed.clic_derecho(en_pantalla(P(60, 900)))
assert not ed.tramos_malos.get(ed.ruta_elegida)

# Mover el inicio y poner una Terminal NEXUS.
usar("spawn"); clic(P(768, 700))
usar("nexus"); clic(P(600, 760))
assert len(ed.datos["nexus"]) == 1
print("\ninicio movido y Terminal NEXUS puesta")

# Puertas con código: un clic pone una y los siguientes ponen sus notas de
# código hasta la X; después, otro clic pone otra puerta (de otro color). Clic
# en una puerta la elige. Clic derecho borra una nota; en una puerta, la quita
# con sus notas.
usar("puertas_codigo")
clic(P(768, 520))
assert len(ed.datos["puertas_codigo"]) == 1 and ed.notas_de_puerta and ed.puerta_elegida == 0
clic(P(620, 700)); clic(P(700, 760))
assert len(ed.datos["puertas_codigo"][0]["notas"]) == 2 and len(ed.datos["notas"]) == 0
ed.tecla(pygame.K_x)
assert not ed.notas_de_puerta
clic(P(900, 520))                       # sin notas: otra puerta
assert len(ed.datos["puertas_codigo"]) == 2 and ed.puerta_elegida == 1 and ed.notas_de_puerta
clic(P(560, 640))
assert len(ed.datos["puertas_codigo"][1]["notas"]) == 1 and len(ed.datos["puertas_codigo"][0]["notas"]) == 2
ed.clic_izquierdo(ed.rect_a_pantalla(ed.rect_puerta(0)).center); ed.soltar()     # elige la roja
assert ed.puerta_elegida == 0 and len(ed.datos["puertas_codigo"]) == 2
clic(P(660, 640))
assert len(ed.datos["puertas_codigo"][0]["notas"]) == 3 and len(ed.datos["puertas_codigo"][1]["notas"]) == 1
ed.clic_izquierdo(en_pantalla(P(560, 640))); ed.arrastrar(en_pantalla(P(570, 660))); ed.soltar()
assert sum(len(p["notas"]) for p in ed.datos["puertas_codigo"]) == 4, "arrastrar mueve, no pone otra"
ed.clic_derecho(en_pantalla(P(660, 640)))
assert len(ed.datos["puertas_codigo"][0]["notas"]) == 2
# F: las próximas notas de la puerta elegida son "solo Difícil".
ed.tecla(pygame.K_f)
assert ed.notas_solo_dificil and ed.notas_de_puerta
clic(P(700, 600))
pc = ed.datos["puertas_codigo"]
assert len(pc[ed.puerta_elegida]["notas_dificil"]) == 1
ed.clic_izquierdo(en_pantalla(P(700, 600))); ed.arrastrar(en_pantalla(P(710, 610))); ed.soltar()
assert len(ed.datos["puertas_codigo"][ed.puerta_elegida]["notas_dificil"]) == 1, "arrastrar la mueve"
ed.tecla(pygame.K_f)
assert not ed.notas_solo_dificil
ed.dibujar(); pygame.image.save(ed.screen, os.path.join(OUT, "editor_mapa_notas_codigo.png"))
ed.clic_derecho(en_pantalla(P(710, 610)))
assert not any(p["notas_dificil"] for p in ed.datos["puertas_codigo"]), "clic derecho la borra"
antes = copy.deepcopy(ed.datos["puertas_codigo"])
ed.clic_derecho(ed.rect_a_pantalla(ed.rect_puerta(1)).center)
assert len(ed.datos["puertas_codigo"]) == 1 and len(ed.datos["puertas_codigo"][0]["notas"]) == 2
ed.deshacer_uno()
assert ed.datos["puertas_codigo"] == antes
# Se guardan juntas, cada una con sus notas, y el juego las lee igual.
copia = objetos_mapa.normalizar(copy.deepcopy(ed.datos))
assert copia["puertas_codigo"] == antes and "puerta" not in copia
ed.clic_derecho(ed.rect_a_pantalla(ed.rect_puerta(1)).center)
ed.clic_derecho(ed.rect_a_pantalla(ed.rect_puerta(0)).center)
assert ed.datos["puertas_codigo"] == []
# El formato viejo (una sola "puerta") se lee como la primera.
vieja = objetos_mapa.normalizar({"puerta": {"rx": 0.5, "ry": 0.5, "ancho": 0.02, "alto": 0.07}})
assert vieja["puertas_codigo"] == [{"rx": 0.5, "ry": 0.5, "ancho": 0.02, "alto": 0.07, "notas": [], "notas_dificil": []}]
print("puertas con código: varias, cada una con sus notas (clic pone, X termina, clic elige)")

ed.dibujar(); pygame.image.save(ed.screen, os.path.join(OUT, "editor_mapa.png"))

# Guardar y que el juego lo use.
ed.guardar()
assert os.path.exists(TEMP) and not ed.sucio
leido = objetos_mapa.cargar(ruta=TEMP)
assert leido["rutas_aliens"] == ed.datos["rutas_aliens"]
assert len(leido["escondites"]) == len(ed.datos["escondites"])
print("guardado y leído igual:", TEMP)

from juego import app as App
original = objetos_mapa.cargar
objetos_mapa.cargar = lambda mapa=None, ruta=None: original(ruta=TEMP)
# Los objetos son de la Nave: el juego tiene que usar la Nave (no el mapa activo).
activo_original = objetos_mapa.mapa_activo
objetos_mapa.mapa_activo = lambda: "Nave"
g = App.Game()
def avanzar():
    for _ in range(80):
        if g.transitions.is_idle(): break
        g.transitions.update(g, 33)
g._activar_opcion_menu("jugar"); avanzar(); g.current_screen = "cantidad"
g._manejar_tecla(pygame.K_RETURN); avanzar(); g.current_screen = "roles"
g.seleccion_roles[0]["cursor"] = 0; g._manejar_tecla(pygame.K_e)
g.seleccion_roles[1]["cursor"] = 1; g._manejar_tecla(pygame.K_RETURN)
avanzar()
objetos_mapa.cargar = original
objetos_mapa.mapa_activo = activo_original
assert len(g.aliens) == len(leido["rutas_aliens"])
assert len(g.escondites) == len(leido["escondites"])
inicio = (0.5 * 0 + leido["spawn"][0] * g.mundo.ancho, leido["spawn"][1] * g.mundo.alto)
cerca = min(math.dist(j.hitbox.center, inicio) for j in g.jugadores)
assert cerca < 200, cerca
terminal = [z for z in g.zonas if z["tipo"] == "nexus"][0]
assert abs(terminal["rect"].centerx - leido["nexus"][0][0] * g.mundo.ancho) < 3
print(f"el juego usa el archivo: {len(g.aliens)} aliens, {len(g.escondites)} escondites, "
      f"jugadores junto al inicio, la Terminal NEXUS donde se puso")

os.remove(TEMP)
with open(real, "rb") as fh:
    assert fh.read() == real_antes, "no debía tocar el archivo real de la nave"
assert objetos_mapa.mapa_activo() == activo_antes
print("\nTODO OK")
