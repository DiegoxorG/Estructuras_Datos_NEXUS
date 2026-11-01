"""Prueba de la Terminal NEXUS como mosaico (redes/celular.panel_ayuda,
screens/paneles.render_mosaico) y de los dibujos del kit y el decodificador.

    python pruebas/prueba_terminal_nexus.py

1. El menú es un mosaico: el caso del Cambiaformas arriba (resaltado y a lo
   ancho), los temas de a tres, Salir abajo. Cada opción tiene su icono.
2. Las flechas lo recorren en dos dimensiones (app.mover_en_mosaico) y la
   tecla de interactuar abre la opción elegida.
3. La tecla del celular cierra la terminal (no abre el celular), también
   dentro de un tema o del caso.
4. Capturas con 2 y 4 jugadores, y del kit y el decodificador (piso e
   inventario): pruebas/capturas/terminal_*.png.
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
from juego.app import mover_en_mosaico
from screens.seleccion import OPCIONES
objetos_mapa.mapa_activo = lambda: "MapaFinal"
NOMBRES = [r["nombre"] for r in App.ROLES]


class Teclas(dict):
    def __getitem__(self, k):
        return self.get(k, False)


pygame.key.get_pressed = lambda: Teclas()


def nueva_partida(roles, tam=(1280, 720)):
    g = App.Game()
    g.screen = pygame.display.set_mode(tam)
    def avanzar():
        for _ in range(80):
            if g.transitions.is_idle(): break
            g.transitions.update(g, 33)
    g._activar_opcion_menu("jugar"); avanzar()
    g.cantidad_seleccionada = OPCIONES.index(len(roles)); g._manejar_tecla(pygame.K_RETURN); avanzar()
    g._manejar_tecla(pygame.K_RETURN); avanzar()
    for i, rol in enumerate(roles):
        g.seleccion_roles[i]["cursor"] = NOMBRES.index(rol)
        g._confirmar_rol(i, g.seleccion_roles[i])
    avanzar()
    g.current_screen = "partida"
    g.saltar_tutorial()
    g.presentacion = None
    for a in g.aliens:
        a.descanso_ms = 10 ** 9
    for j in g.jugadores:
        j.invulnerable_ms = 10 ** 9
    return g


def tecla(g, jugador, nombre):
    g._manejar_tecla(jugador.teclas[nombre][0])


# ---------- 1. El mosaico ----------
g = nueva_partida(["Tecnomante", "Resonante"])
j1 = g.jugadores[0]
terminal = next(z for z in g.zonas if z["tipo"] == "nexus")
g._abrir_nexus(j1, terminal)
panel = j1.panel
assert panel["mosaico"] and panel["nexus_terminal"]
opciones, filas = panel["opciones"], panel["filas"]
assert sorted(i for fila in filas for i in fila) == list(range(len(opciones))), "cada opción en una fila"
assert opciones[filas[0][0]]["destacada"] and opciones[filas[0][0]]["icono"] == "cambiaformas"
assert len(filas[0]) == 1, "el caso del Cambiaformas va solo, a lo ancho"
assert opciones[filas[-1][0]]["icono"] == "salir"
assert all(o.get("icono") for o in opciones)
print("mosaico:", [[opciones[i]["texto"] for i in fila] for fila in filas])

# ---------- 2. Moverse ----------
assert mover_en_mosaico(filas, filas[1][1], 0, 1) == filas[1][2]
assert mover_en_mosaico(filas, filas[1][2], 0, 1) == filas[1][0], "da la vuelta en la fila"
assert mover_en_mosaico(filas, filas[1][1], -1, 0) == filas[0][0], "arriba: el caso"
assert mover_en_mosaico(filas, filas[0][0], 1, 0) == filas[1][1], "abajo: el del medio"
assert mover_en_mosaico(filas, filas[-1][0], 1, 0) == filas[0][0], "da la vuelta abajo"
j1.cursor = filas[0][0]
tecla(g, j1, "abajo"); tecla(g, j1, "derecha")
assert j1.cursor == filas[1][2]
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "terminal_a_mosaico.png"))
j1.cursor = filas[0][0]
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "terminal_b_caso.png"))
tecla(g, j1, "interactuar")
assert j1.panel is not None and j1.panel.get("accion") in ("infiltrado_menu", None) and j1.panel.get("nexus_terminal")
print("el cursor se mueve en dos dimensiones; interactuar abre el caso del Cambiaformas")

# ---------- 3. La tecla del celular la cierra ----------
tecla(g, j1, "celular")
assert j1.panel is None, "cierra la terminal (estando en el caso)"
g._abrir_nexus(j1, terminal)
j1.cursor = filas[1][0]
tecla(g, j1, "interactuar")
assert j1.panel["accion"] == "ayuda_tema"
tecla(g, j1, "celular")
assert j1.panel is None, "cierra la terminal (estando en un tema)"
g._abrir_nexus(j1, terminal)
tecla(g, j1, "celular")
assert j1.panel is None, "cierra el menú, no abre el celular"
tecla(g, j1, "celular")
assert j1.panel is not None and j1.panel["tipo"] == "celular", "sin terminal, abre el celular como siempre"
tecla(g, j1, "celular")
print("la tecla del celular cierra la terminal (sin abrir el celular)")

# ---------- 4. Otras pantallas, kit y decodificador ----------
for tam in ((1920, 1080), (1280, 720)):
    g4 = nueva_partida(["Tecnomante", "Resonante", "Biomante", "Forjador"], tam)
    g4._abrir_nexus(g4.jugadores[1], next(z for z in g4.zonas if z["tipo"] == "nexus"))
    g4.jugadores[1].cursor = g4.jugadores[1].panel["filas"][2][0]
    g4._dibujar(); pygame.image.save(g4.screen, os.path.join(OUT, f"terminal_c_4j_{tam[0]}.png"))

g = nueva_partida(["Resonante", "Biomante"])
j1 = g.jugadores[0]
tipos = {c["tipo"] for c in g.mision.consumibles}
assert {"kit", "decodificador"} <= tipos
for c in g.mision.consumibles:
    if c["tipo"] in ("kit", "decodificador"):
        c["rect"].center = (j1.hitbox.centerx + (90 if c["tipo"] == "kit" else -90), j1.hitbox.centery + 40)
j1.objetos.add("kit"); j1.objetos.add("decodificador")
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "terminal_d_kit_decodificador.png"))
lienzo = pygame.Surface((300, 120)); lienzo.fill((20, 22, 34))
from screens.paneles import _icono_objeto
for k, (tipo, tam) in enumerate((("kit", 80), ("decodificador", 80), ("kit", 34), ("decodificador", 34))):
    _icono_objeto(lienzo, tipo, (50 + k * 70, 60), tam)
pygame.image.save(pygame.transform.scale(lienzo, (600, 240)), os.path.join(OUT, "terminal_e_iconos.png"))
print("kit y decodificador con su dibujo nuevo (piso e inventario)")
# ---------- 5. Puerta con el código ADENTRO de la prisión ----------
# (Si el mapa tiene una: sus notas solo se alcanzan desde donde queda el que
# sale de una celda. El código sale en una de ellas; el que encierran la abre
# desde adentro, y a los de afuera la flecha no los manda allá.)
g = nueva_partida(["Tecnomante", "Resonante"])
m = g.mision
adentro = [p for p in m.puertas if p.get("adentro")]
if adentro:
    puerta = adentro[0]
    assert not puerta["abierta"] and puerta["rect"] in g.mundo.paredes, "no la deja abierta"
    nota = next(n for n in m.notas if puerta["codigo"] in n["texto"])
    assert nota["de_codigo"] and nota in puerta["candidatas"]
    for i in range(len(m.puertas)):
        if m.puertas[i] is not puerta:
            m.abrir_puerta(None, i)
    j1, j2 = g.jugadores
    j2.invulnerable_ms = 0
    g._atrapar(j2, g.aliens[0])
    m.fugarse(j2.preso)
    assert "tachuela" in m.punto_objetivo(j2)[1] and puerta["nombre"] in m.punto_objetivo(j2)[1]
    assert puerta["nombre"] not in (m.punto_objetivo(j1) or (None, ""))[1], "afuera no lo manda adentro"
    j2.personaje.hitbox.center = nota["rect"].center; j2.personaje.sync_sprite_from_hitbox()
    m.interactuar(j2); j2.cerrar_panel()
    assert m.punto_objetivo(j2)[1].startswith(f"Abre la puerta {puerta['nombre']}")
    j2.personaje.hitbox.center = m.punto_objetivo(j2)[0]
    j2.personaje.hitbox.center = g.mundo.punto_libre(j2.hitbox.center, *j2.hitbox.size)
    j2.personaje.sync_sprite_from_hitbox()
    assert m.interactuar(j2) and j2.panel["titulo"] == f"Puerta {puerta['nombre']}"
    m.resolver_codigo(j2, j2.panel["codigos"].index(puerta["codigo"]))
    assert puerta["abierta"] and puerta["rect"] not in g.mundo.paredes
    print(f"puerta {puerta['nombre']}: su código está adentro; el que sale de la celda lo lee y abre")
else:
    print("(el mapa no tiene una puerta con el código adentro de la prisión)")

# ---------- 6. Notas "solo Difícil" ----------
# En Fácil/Normal el código de esa puerta está adentro; en Difícil, como nadie
# sale solo de la celda, va en sus notas "solo Difícil" de afuera (que en
# Fácil/Normal no aparecen).
if adentro:
    i_puerta = g.mision.puertas.index(puerta)
    _cargar = objetos_mapa.cargar
    def _con_nota_dificil(*a, **k):
        datos = _cargar(*a, **k)
        p = datos["puertas_codigo"][i_puerta]
        p["notas_dificil"] = p.get("notas_dificil") or [[d / 6144 for d in (4250, 3330)]]
        return datos
    objetos_mapa.cargar = _con_nota_dificil

    def partida_en(clave):
        g = App.Game()
        g.screen = pygame.display.set_mode((1280, 720))
        def avanzar():
            for _ in range(80):
                if g.transitions.is_idle(): break
                g.transitions.update(g, 33)
        g._activar_opcion_menu("jugar"); avanzar(); g._manejar_tecla(pygame.K_RETURN); avanzar()
        from data.dificultad import DIFICULTADES
        g.dificultad_seleccionada = [d["clave"] for d in DIFICULTADES].index(clave)
        g._manejar_tecla(pygame.K_RETURN); avanzar()
        g.seleccion_roles[0]["cursor"] = 0; g._manejar_tecla(pygame.K_e)
        g.seleccion_roles[1]["cursor"] = 1; g._manejar_tecla(pygame.K_RETURN); avanzar()
        return g

    for clave in ("normal", "dificil"):
        g = partida_en(clave)
        p = g.mision.puertas[i_puerta]
        nota = next(n for n in g.mision.notas if p["codigo"] in n["texto"])
        de_su_puerta = [n for n in g.mision.notas if n.get("puerta") == i_puerta]
        if clave == "normal":
            assert p["adentro"] and len(de_su_puerta) == len(puerta["notas_mapa"]), "en Normal no sale la de Difícil"
        else:
            extra = len(_con_nota_dificil()["puertas_codigo"][i_puerta]["notas_dificil"])
            assert not p["adentro"] and len(de_su_puerta) == len(puerta["notas_mapa"]) + extra
            assert nota in de_su_puerta[-extra:], "en Difícil el código va en una nota de afuera"
        print(f"{clave}: el código de la puerta {p['nombre']} está "
              f"{'adentro de la prisión' if p['adentro'] else 'afuera (nota solo Difícil)'}")
    objetos_mapa.cargar = _cargar
print("\nTODO OK")
