"""Prueba del Cambiaformas y de los prisioneros que caminan por la nave.

    python pruebas/prueba_cambiaformas.py
"""

import os, sys, math, random
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
from Estructuras.arbol_comportamiento import ArbolComportamiento
from data.comportamiento_cambiaformas import ARBOL_CAMBIAFORMAS
from data.npcs import NPCS_POR_PARTIDA, TRANSFORMARSE_MS, EXPUESTO_MS
from redes.nexus import VERDE, ROJO
objetos_mapa.mapa_activo = lambda: "Nave"
DT = 1000 // 60


class Teclas(dict):
    def __getitem__(self, k):
        return self.get(k, False)


pygame.key.get_pressed = lambda: Teclas()

# ================= El árbol =================
arbol = ArbolComportamiento(ARBOL_CAMBIAFORMAS)
hojas = {h.accion for h in arbol.hojas()}
assert hojas == {"DESCANSAR", "HUIR", "SEGUIR", "ATRAPAR", "PERSEGUIR", "REVISAR_ESCONDITE",
                 "REVELARSE", "ESTUDIAR", "RONDAR", "ALEJARSE", "ESPERAR_EN_CEBO",
                 "MERODEAR"}, hojas
base = {c: False for c in arbol.condiciones()}
casos = {
    "DESCANSAR": {"recuperandose": True},
    "HUIR": {"huyendo": True},
    "SEGUIR": {"lo_escoltan": True},
    "ATRAPAR": {"revelado": True, "presa_al_alcance": True},
    "PERSEGUIR": {"revelado": True},
    "REVISAR_ESCONDITE": {"presa_escondida": True, "tiene_presa": True},
    "REVELARSE": {"presa_cerca": True, "tiene_presa": True},
    "ALEJARSE": {"tiene_presa": True, "se_aburrio": True},
    "ESTUDIAR": {"tiene_presa": True, "toca_estudiar": True},
    "RONDAR": {"tiene_presa": True},
    "ESPERAR_EN_CEBO": {"hay_cebo": True},
    "MERODEAR": {},
}
for accion, extra in casos.items():
    assert arbol.decidir({**base, **extra})[0] == accion, accion
print(f"árbol del Cambiaformas: {arbol.contar()} nodos, altura {arbol.altura()}, "
      f"cada hoja se alcanza")


# ================= Partida =================
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
        if a is not g.cambiaformas:
            a.hitbox.topleft = (5, 5)
            a.descanso_ms = 10 ** 9
    g.nexus.reloj_rumor_ms = 10 ** 9
    return g


def frames(g, n):
    for _ in range(n):
        g._actualizar_partida(DT)


def poner(cosa, punto):
    if hasattr(cosa, "personaje"):
        cosa.personaje.hitbox.center = (int(punto[0]), int(punto[1]))
        cosa.personaje.sync_sprite_from_hitbox()
    else:
        cosa.hitbox.center = (int(punto[0]), int(punto[1]))


def cap(g, nombre):
    g._dibujar()
    pygame.image.save(g.screen, os.path.join(OUT, nombre))


g = nueva_partida()
cf, red = g.cambiaformas, g.nexus
j1, j2 = g.jugadores
assert cf is not None and cf in g.aliens and cf.tipo == "cambiaformas"
assert len(g.npcs.npcs) == NPCS_POR_PARTIDA - 1, "el que falta ES el Cambiaformas"
usuarios = [n.usuario for n in g.npcs.npcs]
assert cf.identidad not in usuarios and cf.disfrazado and cf.apariencia.usuario == cf.identidad
assert all(n.nodo in red.grafo for n in g.npcs.npcs), "cada prisionero es una cuenta de NEXUS"
nombre_culpable = g.infiltrado.infiltrado["nombre"]
assert red.grafo.datos[next(n for n in red._presos()
                            if red.grafo.datos[n]["usuario"] == cf.identidad)]["nombre"] == nombre_culpable
assert all(s["nombre"] in [red.grafo.datos[n.nodo]["nombre"] for n in g.npcs.npcs] + [nombre_culpable]
           for s in g.infiltrado.sospechosos), "los sospechosos del caso son prisioneros que caminan"
print(f"prisioneros: {usuarios}; el Cambiaformas es {cf.identidad} ({nombre_culpable})")

# Los prisioneros caminan.
antes = [n.centro for n in g.npcs.npcs]
frames(g, 60 * 8)
assert sum(a != n.centro for a, n in zip(antes, g.npcs.npcs)) >= len(antes) // 2
print("los prisioneros caminan por la nave")

# Al empezar se toma su tiempo: merodea sin presa.
assert cf.calma_ms > 0 and cf.presa is None and cf.accion in ("MERODEAR", "ESPERAR_EN_CEBO")

# Disfrazado no sube el pulso ni suena como alien.
assert cf not in g._aliens_a_la_vista()

# ================= Caza =================
from redes import celular
from data.npcs import ABURRIRSE_MS


def preparar_caza(g):
    cf = g.cambiaformas
    j1, j2 = g.jugadores
    cf.calma_ms = 0
    puntos = g.npcs.puntos
    lejos = max(puntos, key=lambda p: math.dist(p, puntos[0]))
    poner(j2, lejos)
    poner(j1, puntos[0])
    cf.hitbox.center = (j1.hitbox.centerx + 260, j1.hitbox.centery)
    if g.mundo.colisiona(cf.hitbox) or not g.mundo.linea_libre(cf.centro, j1.hitbox.center):
        cf.hitbox.center = (j1.hitbox.centerx, j1.hitbox.centery + 230)
    cf.presa = j1
    return cf, j1, j2


# No es impulsivo: aunque la presa esté sola y con el celular abierto, primero
# la estudia (pasa cerca, se va, ronda, vuelve).
cf, j1, j2 = preparar_caza(g)
celular.abrir(g, j1)
acciones = []
for f in range(60 * 10):
    g._actualizar_partida(DT)
    if cf.accion not in acciones:
        acciones.append(cf.accion)
    assert cf.accion != "REVELARSE", "no ataca sin conocerla"
assert "ESTUDIAR" in acciones and "RONDAR" in acciones, acciones
assert cf.conocimiento.get(j1, 0) > 0, "la estuvo mirando de cerca"
print(f"no es impulsivo: {' > '.join(acciones)}; la estudió {cf.conocimiento[j1] / 1000:.1f} s "
      f"de {cf._necesario(j1) / 1000:.1f} s")

# Ya la conoce y está desprevenida (celular abierto): ahí ataca.
cf.conocimiento[j1] = cf._necesario(j1)
acciones = []
revelo_en = None
for f in range(60 * 40):
    g._actualizar_partida(DT)
    if cf.accion not in acciones:
        acciones.append(cf.accion)
    if cf.accion == "REVELARSE" and revelo_en is None:
        revelo_en = f
        pos_revelo = cf.centro
        assert not cf.disfrazado and j1.susto_ms > 0, "se revela con susto"
        cap(g, "cambiaformas_b_revelado.png")
    if revelo_en is not None and f == revelo_en + int(TRANSFORMARSE_MS / DT) - 5:
        assert math.dist(cf.centro, pos_revelo) < 4, "al transformarse no se mueve (tiempo para huir)"
    if j1.veces_atrapado:
        break
assert "REVELARSE" in acciones and j1.veces_atrapado == 1, acciones
print("caza:", " > ".join(acciones), f"(atrapó a {j1.rol})")
assert cf.calma_ms > 0, "después de atrapar descansa de cazar"
assert cf.conocimiento.get(j1, 0) == 0, "después de atraparla tiene que volver a estudiarla"

# La conoce, pero la presa lo está mirando de frente: espera. De espaldas: ataca.
g = nueva_partida()
cf, j1, j2 = preparar_caza(g)
cf.conocimiento[j1] = cf._necesario(j1)
j1.personaje.direccion = "east" if cf.centro[0] > j1.hitbox.centerx + 100 else "south"
for _ in range(60 * 4):
    g._actualizar_partida(DT)
    assert cf.accion != "REVELARSE", "lo están mirando: no se arriesga"
assert cf.disfrazado and j1.veces_atrapado == 0
j1.personaje.direccion = "west" if j1.personaje.direccion == "east" else "north"
revelo = False
for _ in range(60 * 20):
    g._actualizar_partida(DT)
    if cf.accion == "REVELARSE":
        revelo = True
        break
assert revelo, "de espaldas, cuando menos se lo espera, ataca"
print("de frente no ataca; de espaldas, sí")

# Si el grupo no se separa, se aburre: se va lejos y vuelve a cazar después.
g = nueva_partida()
cf = g.cambiaformas
j1, j2 = g.jugadores
cf.calma_ms = 0
p = g.npcs.puntos[0]
poner(j1, p); poner(j2, (p[0] + 60, p[1]))
if g.mundo.colisiona(j2.hitbox):
    poner(j2, (p[0], p[1] + 50))
cf.hitbox.center = (p[0] + 140, p[1] + 10)
cf.presa = j1
cf.conocimiento[j1] = cf._necesario(j1)        # aunque ya la conozca
celular.abrir(g, j1)
se_fue = False
for _ in range(int((ABURRIRSE_MS + 6000) / DT)):
    g._actualizar_partida(DT)
    assert cf.accion != "REVELARSE"
    if cf.accion == "ALEJARSE":
        se_fue = True
assert se_fue and cf.calma_ms > 0, (cf.accion, cf.acompanada_ms)
assert cf.disfrazado and j1.veces_atrapado == 0 and j2.veces_atrapado == 0
print(f"en grupo no se revela; a los {ABURRIRSE_MS // 1000} s se aburre y se va "
      f"(vuelve en {cf.calma_ms / 1000:.0f} s)")

# Hackeo: lo aturde, le quita el disfraz y al despertar huye y se vuelve a disfrazar.
cf.aturdir(1500)
assert not cf.disfrazado and cf.descanso_ms > 0
poner(j1, (5, 5)); poner(j2, (5, 5))
for a in g.aliens:
    pass
frames(g, int(1600 / DT))
assert cf.accion == "HUIR" or cf.disfrazado, cf.accion
frames(g, 60 * 15)
assert cf.disfrazado, "nadie lo ve: se vuelve a disfrazar"
print("hackeo: aturdido y sin disfraz; después huye y se disfraza de", cf.apariencia.usuario)

# Expuesto en NEXUS: no se puede disfrazar.
cf.confundir(500)
frames(g, 60 * 6)
assert not cf.disfrazado and cf.expuesto_ms > 0
cf.expuesto_ms = 0
print(f"expuesto: {EXPUESTO_MS // 1000} s sin poder disfrazarse")

# Revisa el escondite donde vio meterse a su presa.
g = nueva_partida()
cf = g.cambiaformas
j1 = g.jugadores[0]
esc = g.escondites[0]
poner(j1, esc["rect"].center)
cf.calma_ms = 0
cf.hitbox.center = (esc["rect"].centerx, esc["rect"].centery + 200)
if g.mundo.colisiona(cf.hitbox):
    cf.hitbox.center = (esc["rect"].centerx + 200, esc["rect"].centery)
cf.presa = j1
frames(g, 2)
j1.esconderse(esc)
for _ in range(60 * 12):
    g._actualizar_partida(DT)
    if j1.minijuego is not None:
        break
assert j1.minijuego is not None and j1.minijuego.alien is cf, cf.accion
cap(g, "cambiaformas_c_escondite.png")
print("vio esconderse a su presa: fue a revisar el casillero (minijuego)")

# Mientras dura el minijuego se queda quieto frente al casillero (antes se iba
# y volvía, y el minijuego se repetía sin fin).
donde = cf.centro
j1.minijuego.amenaza = 40           # que no termine solo en esta parte
for _ in range(60 * 3):
    g._actualizar_partida(DT)
    assert j1.minijuego is not None, "el minijuego no se corta"
    assert math.dist(cf.centro, donde) < 3, (cf.accion, cf.centro, donde)
    j1.minijuego.amenaza = 40
assert cf.accion == "REVISAR_ESCONDITE" and not cf.disfrazado
# El jugador se calma: el Cambiaformas lo deja en paz y no vuelve enseguida.
j1.minijuego.resultado = "calmado"
g._actualizar_partida(DT)
assert j1.minijuego is None and cf.presa is None and cf.calma_ms > 0
for _ in range(60 * 15):
    g._actualizar_partida(DT)
    assert j1.minijuego is None, "no vuelve a revisar el mismo casillero (bucle)"
assert math.dist(cf.centro, donde) > 150 or cf.disfrazado, "se fue a esconder"
print("minijuego: se queda quieto; si te calmas, se va y no vuelve en un buen rato")

# Si pierde el minijuego, lo atrapa una sola vez (sin bucle).
g = nueva_partida()
cf = g.cambiaformas
j1 = g.jugadores[0]
esc = g.escondites[0]
poner(j1, esc["rect"].center)
cf.calma_ms = 0
cf.hitbox.center = (esc["rect"].centerx, esc["rect"].centery + 150)
if g.mundo.colisiona(cf.hitbox):
    cf.hitbox.center = (esc["rect"].centerx + 150, esc["rect"].centery)
cf.presa = j1
frames(g, 2)
j1.esconderse(esc)
for _ in range(60 * 12):
    g._actualizar_partida(DT)
    if j1.minijuego is not None:
        break
assert j1.minijuego is not None
j1.minijuego.resultado = "atrapado"
g._actualizar_partida(DT)
assert j1.veces_atrapado == 1 and cf.presa is None and cf.calma_ms > 0
print("minijuego perdido: lo atrapa una vez y descansa de cazar")

# Si sale del casillero en su cara, lo ataca.
g = nueva_partida()
cf = g.cambiaformas
j1 = g.jugadores[0]
esc = g.escondites[0]
poner(j1, esc["rect"].center)
cf.calma_ms = 0
cf.hitbox.center = (esc["rect"].centerx, esc["rect"].centery + 150)
if g.mundo.colisiona(cf.hitbox):
    cf.hitbox.center = (esc["rect"].centerx + 150, esc["rect"].centery)
cf.presa = j1
frames(g, 2)
j1.esconderse(esc)
for _ in range(60 * 12):
    g._actualizar_partida(DT)
    if j1.minijuego is not None:
        break
j1.minijuego = None
esc["revisado_por"] = None
j1.salir_del_escondite()
g._actualizar_partida(DT)
assert cf.rafaga_ms > 0 or cf.accion in ("PERSEGUIR", "ATRAPAR"), cf.accion
print("salir del casillero frente a él: te persigue")

# ================= Prisioneros y NEXUS =================
g = nueva_partida()
red = g.nexus
npc = g.npcs.npcs[0]
j1 = g.jugadores[0]
for n in g.npcs.npcs[1:]:
    n.hitbox.center = (5, 5)
red.grafo.datos[npc.nodo]["color"] = VERDE
npc.espera_ms = 10 ** 9; npc.charla_ms = 0
poner(j1, (npc.centro[0] + 60, npc.centro[1]))
if g.mundo.colisiona(j1.hitbox):
    poner(j1, (npc.centro[0], npc.centro[1] + 50))
frames(g, 2)
assert npc.burbuja and npc.usuario in j1.mensaje, "un verde te da una pista"
from data.npcs import FRASE_PIDE_RESCATE
assert npc.burbuja == FRASE_PIDE_RESCATE and "[" in j1.mensaje, "la primera vez te pide que lo rescates"
npc.charla_ms = 0
frames(g, 2)
assert npc.burbuja != FRASE_PIDE_RESCATE, "solo la primera vez"
print("verde:", npc.burbuja)
cap(g, "cambiaformas_a_prisioneros.png")
red.grafo.datos[npc.nodo]["color"] = ROJO
npc.charla_ms = 0
g.npcs.rng = random.Random(1)
g.cambiaformas.presa = None
from entidades import npcs as modulo_npcs
modulo_npcs.FRASES_ROJO = ["¡Aquí está {usuario}! ¡Aliens, aquí!"]
modulo_npcs.PROB_DELATAR = 1.0
frames(g, 2)
assert g.cambiaformas.presa is j1, "un rojo te delata y el Cambiaformas se entera"
print("rojo:", npc.burbuja)

# El Cambiaformas disfrazado no habla y su nombre falla de vez en cuando.
cf = g.cambiaformas
cf.disfrazado = True
cf.hitbox.center = (j1.hitbox.centerx - 110, j1.hitbox.centery + 30)
cf.glitch_ms = -10
cap(g, "cambiaformas_d_disfrazado.png")

# ================= Suplantación en NEXUS =================
g = nueva_partida()
cf, red = g.cambiaformas, g.nexus
j1, j2 = g.jugadores
cf.calma_ms = 0
cf.disfrazado = True
cf.presa = None
pub = cf.suplantar()
assert pub is not None and pub.tipo == "trampa" and pub.suplantada
assert red.usuario(pub.autor) == cf.apariencia.usuario, "publica con la cuenta que imita"
assert red.trampa_activa() is pub and cf.suplantar() is None, "una trampa a la vez"
print("suplantación:", red.usuario(pub.autor), "->", pub.texto)
# Va a esperar al lugar de la trampa.
assert cf._cebo() == pub.lugar
# Alguien que llega al lugar se vuelve su presa.
poner(j2, (5, 5))
poner(j1, pub.lugar)
cf.visible_para = lambda j: True     # ya está esperando ahí y lo ve llegar
g._actualizar_partida(DT)
del cf.visible_para
assert cf.presa is j1, "el que cae en la trampa es su presa"
# Reportar la suplantación: lo desenmascara.
cf.presa = None
g.logros.conseguir("conectado", j1)      # (para reportar abrió el celular)
texto, puntos = red.reportar(j1, pub.autor)
assert puntos > 0 and pub.reportada and not cf.disfrazado and cf.expuesto_ms > 0, texto
assert red.trampa_activa() is None and g.logros.tiene("perfil_robado")
assert red.stats[j1]["suplantaciones"] == 1
frames(g, 60 * 3)
assert not cf.disfrazado, "desenmascarado no se puede disfrazar enseguida"
print("reportar la suplantación:", texto)

# El celular ofrece reportarla desde "¿De dónde salió esto?".
g = nueva_partida()
cf, red = g.cambiaformas, g.nexus
j1 = g.jugadores[0]
cf.disfrazado, cf.presa = True, None
pub = cf.suplantar()
for _ in range(60 * 8):
    g._actualizar_partida(DT)
assert any(p is pub for p in red.feed(j1)), "la trampa le llega a los jugadores"
print("la trampa llega al feed de", j1.rol)

# ================= Escoltar al Cambiaformas =================
# Solo con él: lo traiciona ahí mismo.
g = nueva_partida()
cf = g.cambiaformas
j1, j2 = g.jugadores
cf.calma_ms = 0
cf.disfrazado, cf.presa = True, None
cf.trampa_ms = 10 ** 9
p = g.npcs.puntos[0]
poner(j2, (5, 5))
poner(j1, p)
cf.hitbox.center = (p[0] + 40, p[1])
if g.mundo.colisiona(cf.hitbox):
    cf.hitbox.center = (p[0], p[1] + 40)
for n in g.npcs.npcs:
    n.hitbox.center = (5, 5)
assert g.npcs.cerca(j1) is cf
assert g.npcs.escoltado(j1) is None
assert g.npcs.hablar(j1) and cf.siguiendo is j1 and cf.burbuja == "...", "acepta callado"
assert "espere" in (g.npcs.pista(j1) or ""), "junto al que te sigue: que te espere"
# "Espérame aquí": también se le puede decir al Cambiaformas (callado, otra pista).
assert g.npcs.hablar(j1) and cf.siguiendo is None and cf.disfrazado and cf.burbuja == "..."
assert g.npcs.hablar(j1) and cf.siguiendo is j1, "y vuelve a venir si se lo piden"
for f in range(60 * 6):
    g._actualizar_partida(DT)
    if not cf.disfrazado:
        break
assert not cf.disfrazado and cf.siguiendo is None and cf.presa is j1, cf.accion
assert f * DT >= 3000, f"esperó unos segundos a solas ({f * DT} ms)"
print(f"escolta a solas: se reveló a los {f * DT / 1000:.1f} s")

# Hackearlo mientras lo llevan: "No me engañas" y "Lobo con piel de oveja".
g = nueva_partida()
cf = g.cambiaformas
j1 = g.jugadores[0]
cf.disfrazado = True
cf.pedir_que_siga(j1)
g.logros.conseguir("despertar")          # (como al terminar el tutorial)
cf.aturdir(1000)
assert g.logros.tiene("no_me_enganas") and g.logros.tiene("lobo_con_piel_de_oveja")
assert cf.siguiendo is None
print("hackeado mientras lo escoltan: No me engañas + Lobo con piel de oveja")

# Acompañados hasta la cápsula: sabotea y huye.
g = nueva_partida()
cf, m = g.cambiaformas, g.mision
j1, j2 = g.jugadores
cf.disfrazado, cf.presa = True, None
cf.trampa_ms = 10 ** 9
m.piezas_entregadas = 2
antes = len(g.piezas)
poner(j1, (m.capsula.centerx, m.capsula.bottom + 60))
poner(j2, (m.capsula.centerx + 40, m.capsula.bottom + 60))
cf.hitbox.center = (m.capsula.centerx, m.capsula.bottom + 100)
cf.pedir_que_siga(j1)
frames(g, 3)
assert cf.sabotajes == 1 and m.piezas_entregadas == 1 and len(g.piezas) == antes + 1
pieza = g.piezas[-1]
assert math.dist(pieza["rect"].center, m.capsula.center) > 400, "la tiró lejos"
assert cf.siguiendo is None and not cf.disfrazado
print("escolta hasta la cápsula: saboteó (pieza tirada a",
      int(math.dist(pieza["rect"].center, m.capsula.center)), "px) y huyó")
# Sin piezas entregadas, deshace parte de la reparación.
g2 = nueva_partida()
g2.mision.reparacion = 0.7
g2.cambiaformas.disfrazado = True
g2.cambiaformas.pedir_que_siga(g2.jugadores[0])
g2.cambiaformas.sabotear()
assert abs(g2.mision.reparacion - 0.3) < 1e-6
# Con la cápsula ya reparada (huida): arranca una pieza, daña la reparación y
# ya no se puede escapar hasta volver a traerla y repararla.
from misiones.mision import PIEZAS_NECESARIAS
g3 = nueva_partida()
m3 = g3.mision
m3.fase, m3.piezas_entregadas, m3.reparacion = "capsula", PIEZAS_NECESARIAS, 1.0
m3.empezar_huida()
assert m3.fase == "huida" and all(a.alerta for a in g3.aliens)
g3.cambiaformas.disfrazado = True
g3.cambiaformas.pedir_que_siga(g3.jugadores[0])
g3.cambiaformas.sabotear()
assert m3.fase == "capsula", m3.fase
assert m3.piezas_entregadas == PIEZAS_NECESARIAS - 1 and abs(m3.reparacion - 0.6) < 1e-6
assert not any(a.alerta for a in g3.aliens)
for j in g3.jugadores:                       # todos en la cápsula: igual no ganan
    j.hitbox.center = m3.capsula.center
m3.actualizar(16)
assert m3.resultado is None
print("sabotaje con la cápsula lista: vuelve a fase cápsula (falta 1 pieza, reparación al 60%)")

# ================= Rescatar prisioneros =================
g = nueva_partida()
red, m = g.nexus, g.mision
j1, j2 = g.jugadores
g.cambiaformas.hitbox.center = (5, 5)
g.cambiaformas.trampa_ms = 10 ** 9
npc, otro = g.npcs.npcs[0], g.npcs.npcs[1]
for n in g.npcs.npcs[1:]:
    n.hitbox.center = (5, 5)
poner(j2, (5, 5))
poner(j1, (npc.centro[0] + 40, npc.centro[1]))
npc.espera_ms = 10 ** 9
red.grafo.datos[npc.nodo]["color"] = ROJO
assert g.npcs.hablar(j1) and npc.siguiendo is None, "rojo: no viene"
red.grafo.datos[npc.nodo]["color"] = VERDE
assert g.npcs.hablar(j1) and npc.siguiendo is j1, "verde: te sigue"
assert g.npcs.escoltado(j1) == npc.usuario, "el HUD dice a quién llevas"
# "Espérame aquí": deja de seguirlo y se queda quieto un rato.
from data.npcs import FRASE_ESPERA, ESPERA_SOLTADO_MS
assert "espere" in g.npcs.pista(j1)
assert g.npcs.hablar(j1) and npc.siguiendo is None and npc.burbuja == FRASE_ESPERA
assert npc.espera_ms == ESPERA_SOLTADO_MS and g.npcs.escoltado(j1) is None
quieto = npc.centro
for _ in range(60):
    g._actualizar_partida(DT)
assert npc.centro == quieto, "se queda esperando"
assert g.npcs.hablar(j1) and npc.siguiendo is j1, "y si vuelves por él, te sigue otra vez"
print("'espérame aquí': el prisionero (y el Cambiaformas disfrazado) deja de seguirte y espera")
# Lo lleva a la cápsula.
# Ya casi llegan (puntos caminables cerca de la cápsula): el jugador junto a
# ella y el prisionero unos pasos atrás, que camina solo hasta ahí.
from entidades.npcs import distancia_a_rect
def libre(q):
    r = j1.hitbox.copy(); r.center = q
    return not g.mundo.colisiona(r)
destino = next((x, y) for x in range(m.capsula.left - 60, m.capsula.right + 60, 10)
               for y in range(m.capsula.top - 60, m.capsula.bottom + 60, 10)
               if 0 < distancia_a_rect((x, y), m.capsula) <= 30 and libre((x, y)))
npc.hitbox.center = min(g.npcs.puntos, key=lambda q: abs(math.dist(q, destino) - 300))
for _ in range(60 * 40):
    poner(j1, destino)
    g._actualizar_partida(DT)
    if npc not in g.npcs.npcs:
        break
assert npc not in g.npcs.npcs and npc.usuario in g.npcs.rescatados, "llegó a la cápsula"
assert g.logros.tiene("rescate")
assert any(p.tipo == "testimonio" and p.autor == npc.nodo for p in red.publicaciones)
print(f"rescate: {npc.usuario} a salvo en la cápsula, testimonio en NEXUS")

# Un verde advierte si llevas al Cambiaformas.
g = nueva_partida()
red = g.nexus
cf = g.cambiaformas
j1, j2 = g.jugadores
cf.trampa_ms = 10 ** 9
poner(j2, (5, 5))
npc = g.npcs.npcs[0]
for n in g.npcs.npcs[1:]:
    n.hitbox.center = (5, 5)
# Lejos de la cápsula: si el NPC quedaba al lado, el Cambiaformas la saboteaba
# en el primer frame, dejaba de seguir y huía (la prueba fallaba al azar).
capsula = g.mision.capsula
npc.hitbox.center = max(g.npcs.puntos, key=lambda q: math.dist(q, capsula.center))
red.grafo.datos[npc.nodo]["color"] = VERDE
npc.espera_ms = 10 ** 9; npc.charla_ms = 0
poner(j1, (npc.centro[0] + 60, npc.centro[1]))
if g.mundo.colisiona(j1.hitbox):
    poner(j1, (npc.centro[0], npc.centro[1] + 50))
# Disfrazado de verdad: a veces arrancaba huyendo (huida_ms) y en el primer
# frame se quitaba el disfraz (la prueba fallaba al azar).
cf.expuesto_ms = cf.descanso_ms = 0; cf.huir_al_despertar = False
cf._disfrazarse()
cf.hitbox.center = (j1.hitbox.centerx + 20, j1.hitbox.centery)
assert cf.pedir_que_siga(j1)
g.jugadores[1].preso = None
frames(g, 2)
assert npc.burbuja and cf.apariencia.usuario in npc.burbuja, npc.burbuja
print("verde advierte:", npc.burbuja)

# Susurro cerca del Cambiaformas disfrazado.
sonidos = []
g = nueva_partida()
g.sonar = lambda nombre, vol=1.0, *a, **k: sonidos.append(nombre)
cf = g.cambiaformas
cf.disfrazado, cf.presa = True, None
cf.calma_ms = 10 ** 9
poner(g.jugadores[0], cf.centro)
frames(g, 2)
assert "susurro" in sonidos
print("susurro: suena cerca del Cambiaformas disfrazado")

print("\nTODO OK")
