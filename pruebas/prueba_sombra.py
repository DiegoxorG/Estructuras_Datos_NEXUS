"""Prueba de La Sombra, el alien de los apagones (entidades/sombra.py).

    python pruebas/prueba_sombra.py

1. Con luz no existe; en un apagón aparece a los RETRASO_SOMBRA_MS, lejos de
   todos y donde nadie la ve. Al volver la luz se disuelve.
2. Como los ángeles llorones: si la linterna la apunta, no se mueve; de
   espaldas, se acerca. Alumbrada mucho rato, se esfuma y reaparece.
3. Si alcanza a alguien: en Normal le apaga la linterna (y la oscuridad no
   dibuja su cono); en Pesadilla (Inteligente) hasta que vuelva la luz.
4. Al que está en un escondite no lo busca.
5. En Fácil se presenta (ventana) cuando se le ven los ojos. Capturas.
"""

import math, os, sys
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
from data.dificultad import DIFICULTADES
from entidades.sombra import LUZ_PARA_ESFUMARSE_MS
objetos_mapa.mapa_activo = lambda: "Nave"
DT = 1000 // 60


class Teclas(dict):
    def __getitem__(self, k):
        return self.get(k, False)


pygame.key.get_pressed = lambda: Teclas()


def nueva_partida(dificultad, presentar=False):
    g = App.Game()
    def avanzar():
        for _ in range(80):
            if g.transitions.is_idle(): break
            g.transitions.update(g, 33)
    g._activar_opcion_menu("jugar"); avanzar(); g._manejar_tecla(pygame.K_RETURN); avanzar()
    g.dificultad_seleccionada = [d["clave"] for d in DIFICULTADES].index(dificultad)
    g._manejar_tecla(pygame.K_RETURN); avanzar()
    g.seleccion_roles[0]["cursor"] = 0; g._manejar_tecla(pygame.K_e)
    g.seleccion_roles[1]["cursor"] = 1; g._manejar_tecla(pygame.K_RETURN); avanzar()
    g.saltar_tutorial()
    if not presentar:
        g.presentacion = None   # la ventana de alien nuevo (en todas) pausaría la prueba
    g.mision.abrir_puerta(g.jugadores[0])
    g.quitar_cambiaformas()
    for a in g.aliens:
        a.hitbox.topleft = (5, 5)
        a.descanso_ms = 10 ** 9
    g.eventos.proximo_ms = 10 ** 9
    return g


def apagon(g):
    g.eventos.lanzar("apagon")
    for _ in range(g.RETRASO_SOMBRA_MS // DT + 30):
        g._actualizar_partida(DT)
        if g.sombra in g.aliens:
            return
    raise AssertionError("la Sombra no apareció")


def frente_a(g, jugador, sombra, distancia=260):
    """Pone a la Sombra a `distancia` del jugador, con línea de vista."""
    for a in range(0, 360, 15):
        r = sombra.hitbox.copy()
        r.center = (jugador.hitbox.centerx + int(distancia * math.cos(math.radians(a))),
                    jugador.hitbox.centery + int(distancia * math.sin(math.radians(a))))
        if not g.mundo.colisiona_alien(r) and g.mundo.linea_libre(r.center, jugador.hitbox.center,
                                                                   34, 20):
            sombra.aparecer(r.center)
            return math.atan2(r.centery - jugador.hitbox.centery, r.centerx - jugador.hitbox.centerx)
    raise AssertionError("no encontré dónde poner a la Sombra")


def apuntar(jugador, angulo):
    jugador.linterna.angulo = angulo


# ---------- 1: solo en los apagones ----------
g = nueva_partida("normal")
S = g.sombra
j1, j2 = g.jugadores
assert S is not None and S not in g.aliens
for _ in range(60):
    g._actualizar_partida(DT)
assert S not in g.aliens, "con luz no existe"
apagon(g)
libres = [j for j in g.jugadores if j.puede_moverse]
assert min(math.dist(S.centro, j.hitbox.center) for j in libres) >= 650, "aparece lejos"
print(f"apagón: la Sombra aparece a los {g.RETRASO_SOMBRA_MS / 1000:.0f} s, lejos y a oscuras")

# ---------- 2: ángel llorón ----------
angulo = frente_a(g, j1, S)
apuntar(j1, angulo)
g._actualizar_partida(DT)
antes = S.centro
for _ in range(40):
    apuntar(j1, angulo); g._actualizar_partida(DT)
assert S.alumbrada and S.accion == "CONGELARSE" and S.centro == antes, "alumbrada no se mueve"
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "sombra_a_alumbrada.png"))
for _ in range(LUZ_PARA_ESFUMARSE_MS // DT + 5):
    apuntar(j1, angulo); g._actualizar_partida(DT)
assert S.oculta, "alumbrada mucho rato se esfuma"
print("alumbrada se congela, y si la alumbran mucho rato se esfuma")

angulo = frente_a(g, j1, S, 300)
lejos = math.dist(S.centro, j1.hitbox.center)
for _ in range(30):
    apuntar(j1, angulo + math.pi); g._actualizar_partida(DT)
assert not S.alumbrada and math.dist(S.centro, j1.hitbox.center) < lejos - 30, "de espaldas se acerca"
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "sombra_b_ojos.png"))
print("de espaldas se acerca (a oscuras solo se le ven los ojos)")

# ---------- 3: alcanzar ----------
# Normal: le apaga la linterna.
frente_a(g, j1, S, 30)
j1.invulnerable_ms = 0
vidas = j1.vidas
for _ in range(5):
    apuntar(j1, angulo + math.pi); g._actualizar_partida(DT)
assert j1.preso is None and j1.vidas == vidas and j1.sin_linterna_ms > 0, "Normal: sin linterna"
assert j1.susto_tipo == "sombra" and S.oculta
from juego import oscuridad
print(f"Normal: te apaga la linterna {j1.sin_linterna_ms / 1000:.0f} s (sin perder vidas)")
# Sin linterna no la congela.
S.aparecer(S.centro)
angulo = frente_a(g, j1, S, 260)
apuntar(j1, angulo)
assert not S.alumbrada_por(j1, g.mundo), "sin linterna no la frena"
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "sombra_c_sin_linterna.png"))
j1.sin_linterna_ms = 0

# Escondido: no lo busca.
esc = min(g.escondites, key=lambda e: math.dist(e["rect"].center, j2.hitbox.center))
j1.personaje.hitbox.midbottom = esc["rect"].midbottom; j1.personaje.sync_sprite_from_hitbox()
j1.esconderse(esc)
j2.personaje.hitbox.topleft = (5, 5); j2.puede_moverse = False
S.aparecer((j1.hitbox.centerx, j1.hitbox.centery + 40))
g._actualizar_partida(DT)
assert S.presa is None and S.accion != "ALCANZAR", "al escondido no lo busca"
j1.salir_del_escondite(); j2.puede_moverse = True
print("al que está en un escondite no lo busca")

# Vuelve la luz: se va.
g.eventos.restaurar_luz(j2)
g._actualizar_partida(DT)
assert S not in g.aliens and j1.sin_linterna_ms == 0
print("al volver la luz se disuelve")

# Pesadilla (lo más alto de Inteligente): no atrapa; la linterna no vuelve
# hasta que prendan los fusibles.
g = nueva_partida("inteligente")
g.dificultad.nivel = 3.0
g.dificultad.actualizar = lambda dt, juego: None     # que el director no lo mueva
S, (j1, j2) = g.sombra, g.jugadores
apagon(g)
angulo = frente_a(g, j1, S, 30)
j1.invulnerable_ms = 0
vidas = j1.vidas
for _ in range(5):
    apuntar(j1, angulo + math.pi); g._actualizar_partida(DT)
assert j1.preso is None and j1.vidas == vidas and j1.susto_tipo == "sombra", "Pesadilla: no atrapa"
assert j1.sin_linterna_ms >= g.SIN_LINTERNA_HASTA_LA_LUZ - 10 ** 6
for _ in range(int(60 * 1000 / DT)):         # un minuto entero: sigue sin linterna
    g._actualizar_partida(DT)
assert j1.sin_linterna_ms > 0 and j1.preso is None
assert S.presa is not j1, "al que ya dejó a oscuras no lo persigue"
g.eventos.restaurar_luz(j2)
g._actualizar_partida(DT)
assert j1.sin_linterna_ms == 0
print("Pesadilla: no atrapa; te deja sin linterna hasta que prendan la caja de fusibles")

# ---------- Logros de la Sombra ----------
g = nueva_partida("normal")
S, (j1, j2) = g.sombra, g.jugadores
L = g.logros
apagon(g)
angulo = frente_a(g, j1, S, 260)
for _ in range(3):
    apuntar(j1, angulo); g._actualizar_partida(DT)
assert L.tiene("ojos_en_la_oscuridad") and L.arbol.buscar("ojos_en_la_oscuridad").quien == j1.rol
for _ in range(LUZ_PARA_ESFUMARSE_MS // DT + 5):
    apuntar(j1, angulo); g._actualizar_partida(DT)
assert L.tiene("no_parpadees") and L.arbol.buscar("no_parpadees").quien == j1.rol
S.aparecer(S.centro)
frente_a(g, j2, S, 200)
g.eventos.restaurar_luz(j2)
g._actualizar_partida(DT)
assert L.tiene("luz_salvadora") and L.tiene("sin_miedo")
print("logros: 'Ojos en la oscuridad', 'No parpadees', 'Luz salvadora' y 'Sin miedo a la oscuridad'")
# Si alcanza a alguien, no hay "Sin miedo".
g = nueva_partida("normal")
S, (j1, j2) = g.sombra, g.jugadores
apagon(g)
angulo = frente_a(g, j1, S, 30)
j1.invulnerable_ms = 0
for _ in range(5):
    apuntar(j1, angulo + math.pi); g._actualizar_partida(DT)
assert j1.sin_linterna_ms > 0
g.eventos.restaurar_luz(j2)
g._actualizar_partida(DT)
assert not g.logros.tiene("sin_miedo")
print("si alcanza a alguien, no hay 'Sin miedo a la oscuridad'")

# ---------- 5: Fácil, presentación ----------
g = nueva_partida("facil", presentar=True)
S, (j1, j2) = g.sombra, g.jugadores
P = g.presentacion
P.presentados |= {a.tipo for a in g.aliens}      # los demás ya presentados
apagon(g)
if P.abierta:
    assert P.actual["tipo"] == "sombra"
else:
    angulo = frente_a(g, j1, S, 180)
    for _ in range(3):
        apuntar(j1, angulo + math.pi); g._actualizar_partida(DT)
    assert P.abierta and P.actual["tipo"] == "sombra", "se presenta cuando se le ven los ojos"
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "sombra_d_presentacion.png"))
print("Fácil: la ventana presenta a la Sombra")
print("\nTODO OK")
