"""Prueba de la misión secundaria del infiltrado (infiltrado.py), sin ventana.

    python pruebas/prueba_infiltrado.py
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
from data.infiltrado import PRUEBAS, CONFUSION_MS
objetos_mapa.mapa_activo = lambda: "Nave"
DT = 1000 // 60


class Teclas(dict):
    def __getitem__(self, k):
        return self.get(k, False)


pygame.key.get_pressed = lambda: Teclas()


def nueva_partida():
    g = App.Game()
    def avanzar():
        for _ in range(80):
            if g.transitions.is_idle(): break
            g.transitions.update(g, 33)
    g._activar_opcion_menu("jugar"); avanzar(); g.current_screen = "cantidad"
    g._manejar_tecla(pygame.K_RETURN); avanzar(); g.current_screen = "roles"
    g._manejar_tecla(pygame.K_e); g._manejar_tecla(pygame.K_RETURN)
    avanzar(); g.current_screen = "partida"
    g.saltar_tutorial()
    g.mision.abrir_puerta()
    for a in g.aliens:
        a.hitbox.topleft = (5, 5)
        a.descanso_ms = 10 ** 9
    return g


def poner(j, punto):
    j.personaje.hitbox.center = punto
    j.personaje.sync_sprite_from_hitbox()


def a_la_terminal(g, j):
    zona = next(z for z in g.zonas if z["clave"].startswith("nexus"))
    poner(j, zona["rect"].center)
    g._actualizar_partida(DT)
    assert j.zona_cerca is zona
    return zona


def elegir(g, j, texto):
    """Mueve el cursor a la opción que empieza con `texto` y confirma."""
    opciones = [o["texto"] for o in j.panel["opciones"]]
    j.cursor = next(i for i, o in enumerate(opciones) if o.startswith(texto))
    g.confirmar(j)


# ---------- Montaje ----------
g = nueva_partida()
caso = g.infiltrado
j1, j2 = g.jugadores
assert caso is not None and caso.activo and len(caso.pruebas) == 3
assert {p["tipo"] for p in caso.pruebas} == set(PRUEBAS)
assert len(caso.sospechosos) == 5 and caso.infiltrado in caso.sospechosos
combos = {tuple(s["rasgos"].values()) for s in caso.sospechosos}
assert len(combos) == 5, "cada sospechoso tiene una combinación distinta"
print("caso armado: 3 pruebas en el mapa, 5 sospechosos, infiltrado:", caso.infiltrado["nombre"])

# Sin pruebas encontradas, la terminal ya muestra el caso (sin subir ni acusar).
a_la_terminal(g, j1)
g._tecla_en_partida(pygame.K_e)
assert j1.panel["accion"] == "ayuda_menu", "la terminal es la central de ayuda"
elegir(g, j1, "El caso del Cambiaformas")
assert j1.panel["accion"] == "infiltrado_menu"
assert [o["texto"] for o in j1.panel["opciones"]] == ["Salir"]
j1.cerrar_panel()
print("antes de encontrar pruebas: la terminal muestra los sospechosos")

# ---------- Recoger ----------
audio = next(p for p in caso.pruebas if p["tipo"] == "prueba_audio")
poner(j1, audio["rect"].center); g._actualizar_partida(DT)
assert j1.pista_mision and "audio" in j1.pista_mision, j1.pista_mision
g._tecla_en_partida(pygame.K_e)
assert "prueba_audio" in j1.objetos and audio["tomada"] and caso.iniciado
assert caso.valor("prueba_audio") in j1.panel["cuerpo"][0]
assert "Cambiaformas" in j2.mensaje
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "infiltrado_a_prueba.png"))
j1.cerrar_panel()
print("recoger el audio: va al inventario y dice el sector del infiltrado")

# ---------- Subir ----------
a_la_terminal(g, j1)
g._tecla_en_partida(pygame.K_e); elegir(g, j1, "El caso del Cambiaformas")
assert j1.panel["accion"] == "infiltrado_menu"
assert any(o["texto"].startswith("Subir") for o in j1.panel["opciones"])
assert not any(o["texto"].startswith("Acusar") for o in j1.panel["opciones"])
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "infiltrado_b_terminal.png"))
puntos = j1.puntos
elegir(g, j1, "Subir")
assert caso.subidas == ["prueba_audio"] and "prueba_audio" not in j1.objetos
assert j1.puntos > puntos
restantes = caso.restantes()
assert caso.infiltrado in restantes and len(restantes) < 5
print(f"subir el audio: quedan {len(restantes)} sospechosos")
j1.cerrar_panel()


# ---------- Acusar mal: caso cerrado y los aliens oyen al que acusó ----------
inocente = next((s for s in restantes if s is not caso.infiltrado), None)
if inocente is None:   # el audio solo ya lo dejó solo: se sube otra para probar
    inocente = next(s for s in caso.sospechosos if s is not caso.infiltrado)
g._tecla_en_partida(pygame.K_e); elegir(g, j1, "El caso del Cambiaformas")
elegir(g, j1, "Acusar")
assert j1.panel["accion"] == "infiltrado_acusar"
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "infiltrado_c_acusar.png"))
for a in g.aliens:
    a.descanso_ms = 0
puntos = j1.puntos
if inocente in j1.panel["candidatos"]:
    elegir(g, j1, inocente["nombre"])
else:
    caso.acusar(j1, inocente)
assert caso.estado == "fallido" and not caso.activo and j1.puntos < puntos
assert all(a.punto_ruido is not None for a in g.aliens if a is not g.cambiaformas), \
    "la nave delata al que acusó"
assert g.cambiaformas.presa is j1, "y el Cambiaformas se entera: lo escoge de presa"
assert "inocente" in caso.resumen() or "acusaron" in caso.resumen()
j1.cerrar_panel()
# Con el caso cerrado la terminal solo cuenta cómo terminó.
g._tecla_en_partida(pygame.K_e); elegir(g, j1, "El caso del Cambiaformas")
assert j1.panel["tipo"] == "aviso" and "inocente" in j1.panel["cuerpo"][0]
j1.cerrar_panel()
print("acusar a un inocente: el caso se cierra ->", caso.resumen())

# ---------- Partida nueva: las 3 pruebas exponen al infiltrado ----------
g = nueva_partida()
caso = g.infiltrado
j1, j2 = g.jugadores
for prueba in caso.pruebas:
    quien = j1 if prueba["tipo"] != "prueba_captura" else j2
    poner(quien, prueba["rect"].center); g._actualizar_partida(DT)
    g._tecla_en_partida(pygame.K_e if quien is j1 else pygame.K_RETURN)
    quien.cerrar_panel()
assert sum(1 for t in PRUEBAS if t in j1.objetos) == 2 and "prueba_captura" in j2.objetos
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "infiltrado_d_inventario.png"))
a_la_terminal(g, j1)
g._tecla_en_partida(pygame.K_e); elegir(g, j1, "El caso del Cambiaformas")
elegir(g, j1, "Subir prueba")       # sube las 2 de una
assert len(caso.subidas) == 2 and caso.activo
j1.cerrar_panel()
for a in g.aliens:
    a.descanso_ms = 0
a_la_terminal(g, j2)
g._tecla_en_partida(pygame.K_RETURN); elegir(g, j2, "El caso del Cambiaformas")
elegir(g, j2, "Subir")
assert caso.estado == "expuesto" and len(caso.restantes()) == 1
assert all(a.confundido and a.descanso_ms >= CONFUSION_MS - 100 for a in g.aliens)
assert g.cambiaformas.expuesto_ms > 0 and not g.cambiaformas.disfrazado, "expuesto: sin disfraz"
g._actualizar_partida(DT)
assert all(a.accion == "DESCANSAR" for a in g.aliens)
print("las 3 pruebas arriba: expuesto ->", caso.resumen(), "| aliens confundidos")
j2.cerrar_panel()
a = g.aliens[0]
a.hitbox.center = (j1.hitbox.centerx + 90, j1.hitbox.centery + 10)
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "infiltrado_e_confundidos.png"))

# ---------- Acusar bien con 1 prueba ----------
g = nueva_partida()
caso = g.infiltrado
j1 = g.jugadores[0]
p = caso.pruebas[0]
poner(j1, p["rect"].center); g._actualizar_partida(DT); g._tecla_en_partida(pygame.K_e); j1.cerrar_panel()
a_la_terminal(g, j1)
g._tecla_en_partida(pygame.K_e); elegir(g, j1, "El caso del Cambiaformas")
elegir(g, j1, "Subir"); j1.cerrar_panel()
g._tecla_en_partida(pygame.K_e); elegir(g, j1, "El caso del Cambiaformas")
elegir(g, j1, "Acusar")
elegir(g, j1, caso.infiltrado["nombre"])
assert caso.estado == "expuesto"
print("acusar bien con 1 prueba también lo expone")

# ---------- Eliminado con pruebas: caen al piso ----------
g = nueva_partida()
caso = g.infiltrado
j1 = g.jugadores[0]
p = caso.pruebas[0]
poner(j1, p["rect"].center); g._actualizar_partida(DT); g._tecla_en_partida(pygame.K_e); j1.cerrar_panel()
j1.vidas = 1
g._atrapar(j1, g.aliens[0])
assert j1.eliminado and p["tipo"] not in j1.objetos
assert any(not q["tomada"] and q["tipo"] == p["tipo"] for q in caso.pruebas)
print("si eliminan al que lleva una prueba, la suelta donde lo atraparon")

# Resultados muestran el caso.
g.current_screen = "resultados"
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "infiltrado_f_resultados.png"))
print("\nTODO OK")
