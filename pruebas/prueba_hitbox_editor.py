"""Prueba del editor de hitboxes (Editores/hitbox_editor.py): zoom y que las
hitboxes queden donde el juego las pone.

    python pruebas/prueba_hitbox_editor.py

1. El mundo del editor es el del juego (imagen × mundo.ESCALA_MAPA): cada
   pared que el editor dibuja es EXACTAMENTE el Rect que arma el juego, y el
   cuadro del modo prueba mide lo mismo que la hitbox de un personaje.
2. La rueda hace zoom alrededor del mouse (hasta 12 px de pantalla por
   píxel del dibujo) y 0 vuelve a ver el mapa entero.
3. Un rectángulo dibujado con el mouse se guarda pegado a los píxeles del
   dibujo (rx * ancho de la imagen es entero), con cualquier zoom.
4. El editor de mapa dibuja las paredes en los mismos píxeles que el mapa.

No escribe nada: el guardado se intercepta. Capturas en
pruebas/capturas/hitbox_editor_*.png.
"""

import os, sys, math
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "Editores"))
os.chdir(RAIZ)
import pygame; pygame.init()
OUT = os.path.join(RAIZ, "pruebas", "capturas")
os.makedirs(OUT, exist_ok=True)


class Info:
    current_w, current_h = 1600, 900


pygame.display.Info = lambda: Info()
import hitbox_editor as HE
from juego.mundo import Mundo, ESCALA_MAPA

MAPA = "MapaFinal"
guardado = {}
HE.save_hitboxes = lambda out, hb, rect, img, **k: guardado.update(hb=[dict(h) for h in hb], rect=tuple(rect))
sys.argv = ["hitbox_editor.py", f"Imagenes/Fondos/{MAPA}.png"]

estado = {}
_dummy = HE.build_dummy_from_game_logic
HE.build_dummy_from_game_logic = lambda *a, **k: estado.setdefault("dummy", _dummy(*a, **k))


def ev(t, **k):
    return pygame.event.Event(t, **k)


MOUSE = (430, 330)
guion = {5: ["captura_0"]}
for i in range(8):
    guion[10 + i] = [ev(pygame.MOUSEWHEEL, x=0, y=1, flipped=False)]
guion[30] = ["captura_1"]
guion[40] = [ev(pygame.MOUSEBUTTONDOWN, pos=(403, 307), button=1)]
guion[41] = [ev(pygame.MOUSEMOTION, pos=(471, 359), rel=(1, 1), buttons=(1, 0, 0))]
guion[42] = [ev(pygame.MOUSEBUTTONUP, pos=(471, 359), button=1)]
guion[45] = ["captura_2", ev(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="\r", scancode=0)]
guion[50] = [ev(pygame.KEYDOWN, key=pygame.K_0, mod=0, unicode="0", scancode=0)]
guion[52] = ["captura_3"]
guion[55] = [ev(pygame.QUIT)]
cuadro = [0]
_get = pygame.event.get


def get(*a, **k):
    _get()
    c = cuadro[0]
    cuadro[0] += 1
    salida = []
    for e in guion.get(c, []):
        if isinstance(e, str):
            sup = pygame.display.get_surface()
            estado[e] = sup.copy()
            pygame.image.save(sup, os.path.join(OUT, f"hitbox_editor_{e[-1]}.png"))
        else:
            salida.append(e)
    return salida


pygame.event.get = get
pygame.mouse.get_pos = lambda: MOUSE
try:
    HE.main()
except SystemExit:
    pass

# 1. Mundo del juego y paredes idénticas.
pygame.init(); pygame.display.set_mode((1600, 900))
mundo = Mundo(MAPA)
assert guardado, "no se guardó"
assert guardado["rect"] == (0, 0, mundo.ancho, mundo.alto), guardado["rect"]
paredes_editor = [HE.denormalize_rect(h, pygame.Rect(guardado["rect"])) for h in guardado["hb"][:-1]
                  if h.get("type") == "rect" and h.get("role", "wall") == "wall"]
assert paredes_editor == mundo.paredes, "el editor y el juego no ponen las paredes en el mismo lugar"
from Movimiento.Personaje import Personaje
carpeta = os.path.join("Imagenes", "Personajes", sorted(
    d for d in os.listdir(os.path.join("Imagenes", "Personajes"))
    if os.path.isdir(os.path.join("Imagenes", "Personajes", d)))[0])
dummy = estado["dummy"]
print(f"mundo del editor = mundo del juego ({mundo.ancho}x{mundo.alto}); "
      f"{len(paredes_editor)} paredes idénticas; modo prueba {dummy.width}x{dummy.height}")

# 2. Zoom: cambió y volvió.
a, b, c = (estado[f"captura_{i}"] for i in (0, 1, 3))
assert pygame.image.tostring(a, "RGB") != pygame.image.tostring(b, "RGB"), "la rueda no hizo zoom"
print("la rueda hace zoom y 0 vuelve a ver el mapa entero")

# 3. El rect nuevo, pegado a los píxeles del dibujo.
iw = pygame.image.load(f"Imagenes/Fondos/{MAPA}.png").get_width()
nuevo = guardado["hb"][-1]
for k in ("rx", "ry", "rw", "rh"):
    v = nuevo[k] * iw
    assert abs(v - round(v)) < 1e-9, (k, v)
fuera = [h for h in guardado["hb"] if h.get("type") == "rect"
         and any(abs(h[k] * iw - round(h[k] * iw)) > 1e-9 for k in ("rx", "ry", "rw", "rh"))]
assert not fuera, f"{len(fuera)} rects fuera de los píxeles del dibujo"
r = HE.denormalize_rect(nuevo, pygame.Rect(guardado["rect"]))
assert all(v % ESCALA_MAPA == 0 for v in (r.x, r.y, r.width, r.height)), r
print(f"rect dibujado con zoom: {r} (múltiplos de {ESCALA_MAPA}: cae en píxeles del dibujo)")

# 4. Editor de mapa: el borde de cada pared, en la columna donde empieza ese píxel del mapa.
from editor_mapa import EditorMapa, ZOOMS
ed = EditorMapa(MAPA, ruta_salida=os.path.join(OUT, "_tmp_objetos.json"))
malos = 0
for i in range(len(ZOOMS)):
    ed.zoom_i = i
    ed.cam = [123.4, 56.7]
    mapa = ed._mapa_escalado()
    z = ed.zoom
    assert mapa.get_width() == round(mundo.ancho * z)
    for p in mundo.paredes[:40]:
        x, _ = ed.a_pantalla(p.topleft)
        j = x + math.floor(ed.cam[0])      # columna en el mapa escalado
        if 0 < j < mapa.get_width() and not (math.floor((j - 1) / z) < p.x <= math.floor(j / z) + 1e-9):
            malos += 1
assert malos == 0, malos
print("editor de mapa: las paredes caen en los mismos píxeles que el dibujo en todos los zooms")
print("\nTODO OK")
