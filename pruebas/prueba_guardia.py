"""Prueba del Guardia de la Bahía y la planta de la Biosfera
(entidades/guardia.py, misiones/guardia.py).

    python pruebas/prueba_guardia.py

1. En MapaFinal hay un Guardia (en self.aliens) frente a la cápsula y una
   planta en la Biosfera. Es sólido: un jugador no lo atraviesa.
2. A quien entra a la Bahía lo persigue y lo atrapa; nunca sale de la Bahía.
   No le hacen nada el hackeo ni el señuelo.
3. Resonante: con la tecla de interactuar cerca, el Guardia se distrae (se
   va a su rincón y no ve a nadie) un rato; después vuelve. Hay recarga.
4. Biomante: manteniendo la tecla en la planta, crece y suelta una fruta.
   Otro la recoge y se la da al Guardia: se va a su rincón a comer, para
   siempre, y la Bahía queda libre.
5. Sin Biomante aparece abono, y con él cualquiera hace crecer la planta. Si
   eliminan al Biomante, suelta abono.
6. Capturas: pruebas/capturas/guardia_*.png.
"""

import os, sys, math
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
from entidades.guardia import Guardia, DISTRACCION_MS, ALCANCE_BRAZOS
from misiones.guardia import RECARGA_SINTONIA_MS, CRECER_BIOMANTE_MS, CRECER_ABONO_MS
objetos_mapa.mapa_activo = lambda: "MapaFinal"
# Si el mapa guardado todavía no los tiene (un editor viejo abierto los borra
# al guardar), se ponen aquí: lo que se prueba es el Guardia, no el archivo.
_cargar = objetos_mapa.cargar
def _con_guardia(*a, **k):
    datos = _cargar(*a, **k)
    datos["guardia"] = datos.get("guardia") or [0.5888, 0.1231]
    datos["planta"] = datos.get("planta") or [0.8408, 0.7803]
    return datos
objetos_mapa.cargar = _con_guardia
DT = 1000 // 60
NOMBRES = [r["nombre"] for r in App.ROLES]


class Teclas(dict):
    def __getitem__(self, k):
        return self.get(k, False)


TECLAS = Teclas()
pygame.key.get_pressed = lambda: TECLAS


def nueva_partida(roles, dificultad="normal"):
    g = App.Game()
    def avanzar():
        for _ in range(80):
            if g.transitions.is_idle(): break
            g.transitions.update(g, 33)
    g._activar_opcion_menu("jugar"); avanzar()
    from screens.seleccion import OPCIONES
    g.cantidad_seleccionada = OPCIONES.index(len(roles)); g._manejar_tecla(pygame.K_RETURN); avanzar()
    g.dificultad_seleccionada = [d["clave"] for d in DIFICULTADES].index(dificultad)
    g._manejar_tecla(pygame.K_RETURN); avanzar()
    for i, rol in enumerate(roles):
        g.seleccion_roles[i]["cursor"] = NOMBRES.index(rol)
        g._confirmar_rol(i, g.seleccion_roles[i])
    avanzar()
    g.current_screen = "partida"
    g.saltar_tutorial()
    g.presentacion = None   # la ventana de alien nuevo pausaría la prueba
    g.mision.abrir_puerta(g.jugadores[0])
    for i in range(1, len(g.mision.puertas)):     # las demás puertas con código del mapa
        g.mision.abrir_puerta(None, i)
    g.quitar_cambiaformas()
    for a in g.aliens:
        if not isinstance(a, Guardia):
            a.hitbox.topleft = (5, 5)
            a.descanso_ms = 10 ** 9
    g.eventos.proximo_ms = 10 ** 9
    return g


def poner(j, punto):
    x, y = j.personaje.hitbox.size
    j.personaje.hitbox.topleft = g.mundo.punto_libre((int(punto[0]) - x // 2, int(punto[1]) - y // 2), x, y)
    j.personaje.sync_sprite_from_hitbox()


def frames(n):
    for _ in range(n):
        g._actualizar_partida(DT)


def interactuar(j):
    g._manejar_tecla(j.teclas["interactuar"][0])


def mantener(j, ms):
    TECLAS[j.teclas["interactuar"][0]] = True
    frames(int(ms / DT) + 2)
    TECLAS.clear()


def lejos(j):
    poner(j, g.npcs.puntos[0] if g.npcs and g.npcs.puntos else (300, 300))
    j.invulnerable_ms = 0


# ---------- 1. Está y es sólido ----------
g = nueva_partida(["Resonante", "Biomante"])
bahia = g.guardia_planta
G = bahia.guardia
assert G is not None and G in g.aliens and bahia.planta is not None
res, bio = g.jugadores
assert G.en_area(G.centro) and G.en_area(g.mision.capsula.midbottom)
print(f"Guardia en {G.centro} (Bahía), planta en {bahia.planta['rect'].center}")
# Sólido: caminando hacia él, no lo atraviesa.
for j in (res, bio):
    lejos(j)
poner(bio, (G.cuerpo.centerx, G.cuerpo.bottom + 70))
G.descanso_ms = 10 ** 9       # quieto para la prueba
TECLAS[bio.teclas["arriba"][0]] = True
frames(60)
TECLAS.clear()
assert not bio.hitbox.colliderect(G.cuerpo.inflate(-6, -6)), "atravesó al Guardia"
print("es sólido: no se le puede atravesar")

# ---------- 2. Persigue, atrapa y no sale de la Bahía ----------
G.descanso_ms = 0
lejos(bio)
poner(res, (G.centro[0], G.centro[1] + 160))
res.invulnerable_ms = 0
vidas = res.vidas
salio = False
for _ in range(400):
    g._actualizar_partida(DT)
    salio = salio or not G.en_area(G.centro)
    if res.preso is not None or res.vidas < vidas:
        break
assert res.vidas < vidas or res.preso is not None, "el Guardia no atrapó al intruso"
assert not salio
print("atrapa a quien entra a la Bahía y nunca sale de ella")
g.mision.liberar(next(c for c in g.mision.celdas if c["preso"] is res), bio)
# Hackeo y señuelo: nada.
G.aturdir(5000); assert G.descanso_ms < 5000 or not G.aturdido
assert G.oir(G.centro) is False
print("el hackeo y el señuelo no le hacen nada")

# ---------- 3. Resonante lo distrae ----------
frames(200)
lejos(bio)
poner(res, (G.centro[0], G.centro[1] + 260))
res.invulnerable_ms = 10 ** 9
assert bahia.pista(res) == "Distraer al Guardia (Sintonía)", bahia.pista(res)
interactuar(res)
assert G.distraido and g.logros.tiene("canto_de_sirena")
res.invulnerable_ms = 0
frames(int(3000 / DT))
assert G.accion == "ESCUCHAR" and G.presa is None
lejos(res)
frames(int(4000 / DT))
pygame.display.set_mode((1280, 720)); g.screen = pygame.display.get_surface()
poner(res, (G.centro[0] + 100, G.centro[1] + 80))
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "guardia_distraido.png"))
# Mientras dura, alguien en la cápsula no corre peligro.
poner(bio, g.mision.capsula.midbottom); bio.invulnerable_ms = 0
frames(60)
assert bio.preso is None and bio.vidas == bio.vidas_max
interactuar(res)                     # sigue distraído: no gasta nada
lejos(res); lejos(bio)
frames(int(DISTRACCION_MS / DT))
assert not G.distraido
frames(int(9000 / DT))
assert math.dist(G.centro, G.puesto) < 40, "volvió a su puesto"
poner(res, (G.centro[0], G.centro[1] + 300))
assert "recargando" in bahia.pista(res)
print(f"Resonante: distrae al Guardia {DISTRACCION_MS // 1000} s; después vuelve a su puesto; "
      f"recarga {RECARGA_SINTONIA_MS // 1000} s")
lejos(res)

# ---------- 4. Biomante: planta, fruta, a comer ----------
planta = bahia.planta
poner(bio, (planta["rect"].centerx, planta["rect"].bottom + 30))
assert bahia.pista(bio) == "Mantener: hacer crecer la planta"
mantener(bio, CRECER_BIOMANTE_MS // 2)
assert 0.3 < planta["progreso"] < 1
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "guardia_planta.png"))
mantener(bio, CRECER_BIOMANTE_MS)
assert planta["crecida"] and g.logros.tiene("jardinero")
# La fruta va derecho al inventario del que hizo crecer la planta...
assert "fruta" in bio.objetos and ("fruta", 1) in g._inventario(bio)
assert not any(c["tipo"] == "fruta" for c in g.mision.consumibles)
from screens.paneles import render_inventario
render_inventario(g.screen, g.screen.get_rect(), bio)
# ...y la puede soltar para que otro se la lleve.
g._manejar_tecla(bio.teclas["soltar"][0])
assert "fruta" not in bio.objetos
fruta = next(c for c in g.mision.consumibles if c["tipo"] == "fruta" and not c["tomado"])
# (Mientras queden consolas, la flecha de la Resonante va primero al decodificador.)
assert g.mision.punto_objetivo(res)[1].startswith("Toma el decodificador")
for consola in g.mision.consolas:
    consola["progreso"] = 1.0
frames(2)
assert g.mision.punto_objetivo(res)[1] == "Recoge la fruta"
poner(res, fruta["rect"].center)
interactuar(res)
assert "fruta" in res.objetos
assert g.mision.punto_objetivo(res)[1] == "Dale la fruta al Guardia"
# Con la fruta no lo ataca: se le acerca y espera.
G.descanso_ms = 0; G.distraido_ms = 0
lejos(bio)
res.invulnerable_ms = 0
vidas = res.vidas
poner(res, (G.centro[0], G.centro[1] + 260))
assert G.en_area(res.hitbox.center)
antes = math.dist(G.centro, res.hitbox.center)
frames(240)
assert res.preso is None and res.vidas == vidas, "al que trae la fruta no lo ataca"
assert G.accion == "ESPERAR_FRUTA"
assert math.dist(G.centro, res.hitbox.center) < antes, "se le acerca"
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "guardia_espera_fruta.png"))
# Si entra alguien sin fruta, a ese sí lo ataca (y al de la fruta no).
bio.invulnerable_ms = 0
vidas_bio = bio.vidas
poner(bio, (G.centro[0] + 150, G.centro[1] + 60))
atrapado = False
for _ in range(400):
    g._actualizar_partida(DT)
    if bio.preso is not None or bio.vidas < vidas_bio:
        atrapado = True
        break
assert atrapado and res.preso is None and res.vidas == vidas, "ataca al que no trae la fruta"
lejos(bio); bio.invulnerable_ms = 10 ** 9
print("con la fruta: el Guardia se acerca y espera; al que entra sin fruta lo ataca")
poner(res, (G.centro[0], G.centro[1] + 120))
res.invulnerable_ms = 10 ** 9
interactuar(res)
assert G.comiendo and "fruta" not in res.objetos and g.logros.tiene("buen_provecho")
frames(int(6000 / DT))
assert G.accion == "COMER"
res.invulnerable_ms = 0
poner(res, g.mision.capsula.midbottom)
frames(200)
assert res.preso is None, "comiendo ya no atrapa a nadie"
poner(res, (G.centro[0] - 120, G.centro[1] + 40))
g._dibujar(); pygame.image.save(g.screen, os.path.join(OUT, "guardia_comiendo.png"))
print("Biomante: la planta crece y la fruta va a su inventario (se puede soltar); "
      "el Guardia se la come y se queda en su rincón para siempre")

# ---------- 5. Sin Biomante: abono ----------
g = nueva_partida(["Tecnomante", "Forjador"])
bahia = g.guardia_planta
abonos = [c for c in g.mision.consumibles if c["tipo"] == "abono"]
assert len(abonos) == 1, [c["tipo"] for c in g.mision.consumibles]
assert [c["tipo"] for c in g.mision.consumibles] == ["abono"], "solo falta el Biomante: solo abono"
# Uno de cada uno, cada uno en un lugar de consumibles distinto (varias veces, es al azar).
for _ in range(4):
    g2 = nueva_partida(["Resonante", "Biomante"])
    tipos = sorted(c["tipo"] for c in g2.mision.consumibles)
    assert tipos == ["decodificador", "kit"], tipos
    assert len({c["rect"].center for c in g2.mision.consumibles}) == len(tipos)
print("consumibles: uno solo de cada uno y cada uno en un lugar distinto")
tec = g.jugadores[0]
poner(tec, (bahia.planta["rect"].centerx, bahia.planta["rect"].bottom + 30))
assert "Biomante" in bahia.pista(tec)
# Flecha: el Tecnomante hackea; el Forjador (que no puede) va por el abono.
assert g.mision.punto_objetivo(tec)[1] == "Hackea esta consola"
assert g.mision.punto_objetivo(g.jugadores[1])[1] == "Recoge el abono (para la planta)"
poner(tec, abonos[0]["rect"].center)
interactuar(tec)
assert "abono" in tec.objetos
poner(tec, (bahia.planta["rect"].centerx, bahia.planta["rect"].bottom + 30))
mantener(tec, CRECER_ABONO_MS + 200)
assert bahia.planta["crecida"] and "abono" not in tec.objetos
print("sin Biomante: aparece abono y con él cualquiera hace crecer la planta")
# Si eliminan al Biomante, suelta abono.
g = nueva_partida(["Biomante", "Forjador"])
bio = g.jugadores[0]
bio.vidas = 1; bio.invulnerable_ms = 0
antes = sum(1 for c in g.mision.consumibles if c["tipo"] == "abono")
g._atrapar(bio, g.guardia_planta.guardia)
assert bio.eliminado
assert sum(1 for c in g.mision.consumibles if c["tipo"] == "abono") == antes + 1
print("si eliminan al Biomante, suelta abono")

# ---------- 6. La flecha amarilla, según la etapa, el rol y lo que llevan ----------
from misiones.mision import PIEZAS_NECESARIAS
g = nueva_partida(["Tecnomante", "Biomante", "Resonante", "Forjador"])
m, bahia = g.mision, g.guardia_planta
tec, bio, res, forj = g.jugadores
for j in g.jugadores:
    lejos(j); j.invulnerable_ms = 10 ** 9


def flecha(j):
    objetivo = m.punto_objetivo(j)
    return objetivo and objetivo[1]


assert m.fase == "sabotaje"
assert flecha(tec) == "Hackea esta consola"
assert flecha(bio) == "Haz crecer la planta", "mientras otros hackean, adelanta la planta"
assert flecha(res) == flecha(forj) == "Cuida a quien hackea esta consola"
print("consolas:", {j.rol: flecha(j) for j in g.jugadores})
for consola in m.consolas:
    consola["progreso"] = 1.0
frames(2)
assert m.fase == "capsula"
assert flecha(bio) == "Haz crecer la planta", "primero quitar al Guardia para siempre"
assert flecha(forj) == "Recoge esta pieza"
assert flecha(res) != "Distrae al Guardia (Sintonía)", "nadie necesita llegar a la cápsula todavía"
pieza = next(p for p in g.piezas if not p["recogida"])
poner(forj, pieza["rect"].center); frames(1)
assert forj.piezas == 1
assert flecha(forj) == "Lleva la pieza (ojo: el Guardia la cuida)"
assert flecha(res) == "Distrae al Guardia (Sintonía)", "alguien lleva una pieza: a distraerlo"
print("cápsula:", {j.rol: flecha(j) for j in g.jugadores})
poner(bio, (bahia.planta["rect"].centerx, bahia.planta["rect"].bottom + 30))
mantener(bio, CRECER_BIOMANTE_MS + 200)
assert "fruta" in bio.objetos and flecha(bio) == "Dale la fruta al Guardia"
G = bahia.guardia
poner(bio, (G.centro[0], G.centro[1] + 120))
interactuar(bio)
assert not bahia.activo
assert flecha(forj) == "Lleva la pieza a la cápsula" and flecha(res) != "Distrae al Guardia (Sintonía)"
print("Guardia comiendo:", {j.rol: flecha(j) for j in g.jugadores})
# Sin Biomante ni abono que usar: el Resonante es la única salida y lo distrae.
g = nueva_partida(["Resonante", "Forjador"])
m, bahia = g.mision, g.guardia_planta
res, forj = g.jugadores
m.consumibles = [c for c in m.consumibles if c["tipo"] != "abono"]
for consola in m.consolas:
    consola["progreso"] = 1.0
frames(2)
assert m.fase == "capsula" and not bahia.hay_camino_permanente()
assert flecha(res) == "Distrae al Guardia (Sintonía)"
print("sin forma de darle de comer: el Resonante lo distrae")
print("\nTODO OK")
