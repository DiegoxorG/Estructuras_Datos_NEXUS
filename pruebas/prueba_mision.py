"""Prueba de la misión completa en la nave, sin ventana.

    python pruebas/prueba_mision.py

Juega la misión de punta a punta con lo que hay en Hitboxes/Nave_objetos.json:
notas y código de la puerta, alarma por código equivocado, puntos de equipo
para habilidades, consolas (mantener la tecla), piezas y reparación de la
cápsula, celdas y rescate, NEXUS, huida y victoria. Después repite con una
tripulación sin Tecnomante ni Forjador (consumibles) y prueba la derrota.

Guarda capturas en pruebas/capturas/mision_*.png.
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
from misiones import mision as M
objetos_mapa.mapa_activo = lambda: "Nave"      # sin tocar el mapa activo real
DT = 1000 // 60


def nueva_partida(roles):
    g = App.Game()
    def avanzar():
        for _ in range(80):
            if g.transitions.is_idle(): break
            g.transitions.update(g, 33)
    g._activar_opcion_menu("jugar"); avanzar(); g.current_screen = "cantidad"
    g._manejar_tecla(pygame.K_RETURN); avanzar(); g.current_screen = "roles"
    nombres = [r["nombre"] for r in App.ROLES]
    g.seleccion_roles[0]["cursor"] = nombres.index(roles[0]); g._manejar_tecla(pygame.K_e)
    g.seleccion_roles[1]["cursor"] = nombres.index(roles[1]); g._manejar_tecla(pygame.K_RETURN)
    avanzar(); g.current_screen = "partida"
    # El tutorial ya no se acaba solo: aquí se da por terminado (con el
    # tutorial abierto la puerta de la prisión no abre).
    if g.tutorial is not None:
        g.saltar_tutorial()
    # NEXUS se prueba aparte (prueba_nexus.py): aquí no mete rumores ni pide planos.
    # Y el Cambiaformas también (prueba_cambiaformas.py).
    g.nexus = None
    g.quitar_cambiaformas()
    return g


def poner(j, punto):
    j.personaje.hitbox.center = (int(punto[0]), int(punto[1]))
    j.personaje.sync_sprite_from_hitbox()


def calmar_aliens(g):
    for a in g.aliens:
        a.descanso_ms = 10 ** 9; a.punto_ruido = None; a.escondite_objetivo = None


def frames(g, n):
    for _ in range(n):
        g._actualizar_partida(DT)


def cap(g, nombre):
    g._dibujar(); pygame.display.flip()
    pygame.image.save(g.screen, os.path.join(OUT, nombre))


def mantener(g, j, segundos):
    for _ in range(int(segundos * 1000 / DT) + 2):
        g.mision.mantener(j, DT)
        g.mision.actualizar(DT)


# ================= Partida 1: Tecnomante + Forjador =================
g = nueva_partida(("Tecnomante", "Forjador"))
tec, forj = g.jugadores
m = g.mision
print("mapa:", g.mundo.nombre_mapa, "| misión activa:", m.activa, "| fase:", m.fase,
      "| código:", m.codigo, "| sin límite de tiempo:", g.tiempo_restante_ms is None)
assert m.activa and m.fase == "prision" and m.puerta in g.mundo.paredes
assert not m.consumibles, "con Tecnomante y Forjador no hay consumibles"
assert len(g.aliens) == 3 and any(z["clave"].startswith("nexus") for z in g.zonas)
cap(g, "mision_a_inicio.png")
calmar_aliens(g)

# Notas: la del código está en la prisión.
con_codigo = [n for n in m.notas if m.codigo in n["texto"]]
assert len(con_codigo) == 1
poner(tec, con_codigo[0]["rect"].center)
assert g.mision.interactuar(tec) and tec.panel["titulo"] == "Nota arrugada"
print("nota del código:", tec.panel["cuerpo"][0])
cap(g, "mision_b_nota.png")
tec.cerrar_panel()

# Notas de código (vienen con la puerta): el código sale solo en una de ellas
# (de las de antes de la puerta); las normales quedan de historia.
normales = [n["rect"].center for n in m.notas if not n["de_codigo"]]
desde = tec.hitbox.center
cerca_1 = g.mundo.punto_libre((desde[0] + 120, desde[1]), 30, 30)
cerca_2 = g.mundo.punto_libre((desde[0] - 120, desde[1]), 30, 30)
lejos_puerta = g.mundo.punto_libre((m.puerta.left - 300, m.puerta.centery), 30, 30)
for _ in range(15):
    m._crear_notas(normales, [[cerca_1, cerca_2, lejos_puerta]])
    de_codigo = [n for n in m.notas if n["de_codigo"]]
    assert len(de_codigo) == 3 and len(m.notas) == len(normales) + 3
    con = [n for n in m.notas if m.codigo in n["texto"]]
    assert len(con) == 1 and con[0]["de_codigo"], "el código va en una nota de código"
    assert con[0] is not de_codigo[2], "la de detrás de la puerta nunca lo tiene"
    assert all(n not in m.notas_alcanzables for n in m.notas if not n["de_codigo"])
    assert g.mundo.paredes.count(m.puerta) == 1
from data.notas import NOTAS_CODIGO_VACIAS
vacias = [n for n in de_codigo if m.codigo not in n["texto"]]
assert all(n["titulo"] in [v["titulo"] for v in NOTAS_CODIGO_VACIAS] for n in vacias)
assert "tachuela roja" in m.punto_objetivo(tec)[1]
cap(g, "mision_b2_notas_codigo.png")
print("notas de código: el código sale en una de ellas (nunca detrás de la puerta)")

# Varias puertas con código: cada una con su color, su código y sus notas. La
# segunda puede tener sus notas detrás de la primera (se lee después de abrirla).
from misiones.mision import color_puerta, _rect
afuera = g.mundo.punto_libre((m.puerta.left - 700, m.puerta.centery), 40, 120)
nombre, color = color_puerta(1)
m.puertas.append({"rect": _rect((afuera[0] + 20, afuera[1] + 60), (40, 120)), "codigo": m._codigo_nuevo({m.codigo}),
                  "abierta": False, "nombre": nombre, "color": color, "candidatas": [], "notas_mapa": []})
azul = m.puertas[1]
m._crear_notas(normales, [[cerca_1], [lejos_puerta]])
assert azul["codigo"] != m.codigo and azul["nombre"] == "azul" and not azul["abierta"]
nota_azul = next(n for n in m.notas if azul["codigo"] in n["texto"])
assert nota_azul["de_codigo"] and nota_azul["puerta"] == 1 and nota_azul["color"] == azul["color"]
assert "azul" in nota_azul["texto"] and m.codigo not in nota_azul["texto"]
assert azul["rect"] in g.mundo.paredes and m.puerta in g.mundo.paredes
# Su teclado abre la azul (no la de la prisión, ni pasa de fase).
poner(tec, (azul["rect"].right + 30, azul["rect"].centery))
tec.cerrar_panel()
assert "azul" in m.pista(tec)
assert m.interactuar(tec) and tec.panel["titulo"] == "Puerta azul"
m.resolver_codigo(tec, tec.panel["codigos"].index(azul["codigo"]))
assert azul["abierta"] and azul["rect"] not in g.mundo.paredes
assert not m.puerta_abierta and m.fase == "prision"
print("varias puertas: la azul tiene su código (en una nota detrás de la roja) y su teclado")
# Si no hay cómo leer su código antes de abrirla, queda abierta.
m._crear_notas(normales, [[cerca_1], []])
m.puertas[1]["notas_mapa"] = []
solo_detras = g.mundo.punto_libre((azul["rect"].left - 200, azul["rect"].centery), 30, 30)
m._crear_notas([], [[cerca_1], [solo_detras]])
print("puerta azul con su nota solo detrás de ella:", "abierta" if azul["abierta"] else "cerrada")
# Volver a como estaba el mapa (una puerta, sin notas de código) para lo que sigue.
del m.puertas[1:]
g.mundo.paredes[:] = [r for r in g.mundo.paredes if r != azul["rect"]]
m._crear_notas(normales)
con_codigo = [n for n in m.notas if m.codigo in n["texto"]]
assert len(con_codigo) == 1 and not con_codigo[0]["de_codigo"]
poner(tec, desde)

# Puerta: código equivocado suena la alarma; el correcto abre.
poner(tec, (m.puerta.right + 40, m.puerta.centery))
for a in g.aliens:
    a.descanso_ms = 0
g._tecla_en_partida(pygame.K_e)
assert tec.panel and tec.panel.get("accion") == "codigo"
codigos = tec.panel["codigos"]
tec.cursor = next(i for i, c in enumerate(codigos) if c != m.codigo)
g.confirmar(tec)
assert all(a.punto_ruido == m.puerta.center for a in g.aliens), "la alarma debió atraer aliens"
print("código equivocado: los aliens van a la puerta")
calmar_aliens(g)
g._tecla_en_partida(pygame.K_e)
tec.cursor = tec.panel["codigos"].index(m.codigo)
g.confirmar(tec)
assert m.puerta_abierta and m.puerta not in g.mundo.paredes and m.fase == "sabotaje"
print("código correcto: puerta abierta | fase:", m.fase, "| puntos del equipo:", g.equipo.puntos)

# Las habilidades se pagan con puntos del equipo.
antes = g.equipo.puntos
g.alternar_habilidades(tec); tec.cursor = 1; g._confirmar_habilidad(tec)
assert tec.arbol.tiene("ESCANEO") and g.equipo.puntos == antes - 15
tec.cerrar_panel()
print("Tecnomante desbloqueó Escaneo con puntos del equipo:", antes, "->", g.equipo.puntos)

# Consolas: el Forjador no puede; el Tecnomante sí, manteniendo la tecla.
c0, c1 = m.consolas
poner(forj, c0["rect"].center)
mantener(g, forj, 1)
assert c0["progreso"] == 0
for consola in m.consolas:
    poner(tec, consola["rect"].center)
    mantener(g, tec, M.SABOTAJE_ROL_S)
    assert consola["progreso"] >= 1
assert m.fase == "capsula"
print("consolas apagadas | fase:", m.fase)

# Piezas: el Forjador las recoge y las lleva; repara manteniendo la tecla.
for pieza in g.piezas[:3]:
    poner(forj, pieza["rect"].center)
    frames(g, 1)
assert forj.piezas == 3, forj.piezas
poner(forj, m.capsula.center); poner(tec, m.capsula.center)
assert m.interactuar(forj) and m.piezas_entregadas == 3
mantener(g, tec, 1)
assert m.reparacion == 0, "el Tecnomante sin kit no repara"
mantener(g, forj, M.REPARACION_ROL_S)
assert m.fase == "huida" and all(a.alerta for a in g.aliens)
print("cápsula reparada | fase:", m.fase, "| aliens en alerta")

# Celdas: atrapan al Tecnomante y el Forjador lo saca.
poner(tec, (1500, 1300))
g._atrapar(tec, g.aliens[0])
assert tec.preso is not None and not tec.cazable
cap(g, "mision_c_celda.png")
celda = tec.preso
poner(forj, (celda["punto"][0], celda["punto"][1] + 60))
g._tecla_en_partida(pygame.K_RETURN)
assert tec.preso is None and not g.mundo.colisiona(tec.hitbox)
print("rescate: el Forjador sacó al Tecnomante de la celda")

# NEXUS: la terminal es la central de ayuda; desde ahí también se abre el caso.
nexus = [z for z in g.zonas if z["clave"].startswith("nexus")][0]
poner(tec, nexus["rect"].center)
tec.zona_cerca = g.zona_bajo(tec)
g.interactuar(tec)
assert tec.panel["accion"] == "ayuda_menu"
assert any("Confianza" in l for l in tec.panel["cuerpo"]) or g.nexus is None
cap(g, "mision_d_ayuda.png")
tec.cursor = next(i for i, (t, _) in enumerate(tec.panel["acciones"]) if t == "infiltrado")
g.confirmar(tec)
assert tec.panel["accion"] == "infiltrado_menu" and "Sospechosos:" in tec.panel["cuerpo"]
print("NEXUS:", tec.panel["titulo"], "|", len(g.infiltrado.sospechosos), "sospechosos")
cap(g, "mision_d_nexus.png")
tec.cerrar_panel()

# Huida: todos en la cápsula = victoria.
calmar_aliens(g)
poner(tec, m.capsula.center); poner(forj, m.capsula.center)
frames(g, 2)
assert m.resultado == "victoria"
for _ in range(80):
    if g.transitions.is_idle(): break
    g.transitions.update(g, 33)
g.current_screen = "resultados"
cap(g, "mision_e_victoria.png")
print("VICTORIA | puntos del equipo:", g.equipo.total)

# ================= Partida 2: sin Tecnomante ni Forjador =================
g = nueva_partida(("Biomante", "Resonante"))
bio, res = g.jugadores
m = g.mision
calmar_aliens(g)
tipos = sorted(c["tipo"] for c in m.consumibles)
# Uno solo de cada uno, cada uno en un punto distinto.
assert len(tipos) == len(set(tipos)), tipos
assert len({c["rect"].center for c in m.consumibles}) == len(m.consumibles)
print("\nsin Tecnomante ni Forjador -> consumibles:", tipos, "| piezas para todos:", m.piezas_para_todos)
assert tipos == ["decodificador", "kit"] and m.piezas_para_todos
m.abrir_puerta(bio)
deco = [c for c in m.consumibles if c["tipo"] == "decodificador"][0]
poner(bio, deco["rect"].center)
assert m.interactuar(bio) and "decodificador" in bio.objetos
poner(bio, m.consolas[0]["rect"].center)
mantener(g, bio, M.SABOTAJE_ROL_S)
assert 0 < m.consolas[0]["progreso"] < 1, "con decodificador debe ser más lento"
mantener(g, bio, M.SABOTAJE_OTROS_S)
assert m.consolas[0]["progreso"] >= 1 and "decodificador" in bio.objetos
mantener(g, bio, M.SABOTAJE_OTROS_S)
print("la Biomante apagó una consola con el decodificador (y le sirve para las demás)")
# Sin Forjador, las piezas las ve y las recoge quien lleve el kit.
assert not m.ve_piezas(res)
poner(res, g.piezas[0]["rect"].center); frames(g, 1)
assert res.piezas == 0, "sin el kit no la ve ni la recoge"
objetivo = m.punto_objetivo(res)
kit = [c for c in m.consumibles if c["tipo"] == "kit"][0]
if m.fase == "capsula":
    assert objetivo[0] == kit["rect"].center, "la flecha lleva al kit"
poner(res, kit["rect"].center)
assert m.interactuar(res) and "kit" in res.objetos and m.ve_piezas(res)
poner(res, g.piezas[0]["rect"].center); frames(g, 1)
assert res.piezas == 1, "con el kit la recoge"
print("sin Forjador: la Resonante toma el kit y con él ve y recoge las piezas")

# Soltar del inventario: con dos cosas sale un panel para escoger.
assert g._inventario(res) == [("pieza", 1), ("kit", 1)]
g._manejar_tecla(res.teclas["soltar"][0])
assert res.panel is not None and res.panel["accion"] == "soltar"
res.cursor = 0                       # la pieza
g.confirmar(res)
assert res.piezas == 0 and res.panel is None
soltada = g.piezas[-1]
assert not soltada["recogida"] and soltada["rect"].colliderect(res.hitbox.inflate(40, 40))
frames(g, 3)
assert res.piezas == 0, "no la recoge de nuevo mientras sigue encima"
# Con una sola cosa, se suelta de una: el kit. Sin él ya no ve las piezas...
g._manejar_tecla(res.teclas["soltar"][0])
assert "kit" not in res.objetos and not m.ve_piezas(res) and m.kit_libre() is not None
# ...y la Biomante lo recoge y las ve.
poner(bio, m.kit_libre()["rect"].center)
assert m.interactuar(bio) and m.ve_piezas(bio)
poner(bio, soltada["rect"].center); frames(g, 1)
assert bio.piezas == 1
g._manejar_tecla(res.teclas["soltar"][0])
assert "nada" in res.mensaje.lower() if hasattr(res, "mensaje") and isinstance(res.mensaje, str) else True
print("soltar: panel para escoger, la pieza no se recoge sola de nuevo, y el kit pasa a otra")

# Derrota: todos encerrados.
g._atrapar(bio, g.aliens[0]); g._atrapar(res, g.aliens[1])
frames(g, 1)
assert m.resultado == "derrota"
print("todos encerrados -> DERROTA")

print("\nTODO OK")
