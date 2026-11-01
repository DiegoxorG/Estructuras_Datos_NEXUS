"""Prueba de NEXUS: el grafo, los rumores, el celular y las barras de confianza.

    python pruebas/prueba_nexus.py
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
from Estructuras.grafo import Grafo
from redes.nexus import VERDE, ROJO, GRIS
from data.nexus import UMBRAL_PLANOS, TICK_PROPAGACION_MS, CUENTAS
objetos_mapa.mapa_activo = lambda: "Nave"
DT = 1000 // 60


class Teclas(dict):
    def __getitem__(self, k):
        return self.get(k, False)


pygame.key.get_pressed = lambda: Teclas()

# ================= El grafo solo =================
g = Grafo()
for a, b in [("a", "b"), ("b", "c"), ("c", "a"), ("c", "d"), ("x", "y")]:
    g.agregar_arista(a, b)
assert g.bfs_niveles("a") == [["a"], ["b"], ["c"], ["d"]], g.bfs_niveles("a")
assert g.bfs_niveles("a", max_niveles=1) == [["a"], ["b"]]
assert g.camino_mas_corto("a", "d") == ["a", "b", "c", "d"]
assert g.camino_mas_corto("d", "a") is None, "las aristas tienen dirección"
assert sorted(map(sorted, g.componentes())) == [["a", "b", "c", "d"], ["x", "y"]]
assert g.seguidos_por("a") == ["c"]
# Un nodo que no "puede pasar" recibe pero no reenvía.
assert g.bfs_niveles("a", puede_pasar=lambda n: n != "b") == [["a"], ["b"]]
g.eliminar_nodo("c")
assert "c" not in g and g.camino_mas_corto("a", "d") is None
assert len(g.componentes()) == 3, "al borrar c, d queda aislado"
print("grafo: BFS por niveles, camino más corto, borrar nodo y componentes")


# ================= Partida =================
def nueva_partida():
    juego = App.Game()
    def avanzar():
        for _ in range(80):
            if juego.transitions.is_idle(): break
            juego.transitions.update(juego, 33)
    juego._activar_opcion_menu("jugar"); avanzar(); juego.current_screen = "cantidad"
    juego._manejar_tecla(pygame.K_RETURN); avanzar(); juego.current_screen = "roles"
    juego._manejar_tecla(pygame.K_e); juego._manejar_tecla(pygame.K_RETURN)
    avanzar(); juego.current_screen = "partida"
    juego.saltar_tutorial()
    juego.mision.abrir_puerta()
    juego.quitar_cambiaformas()      # aquí solo NEXUS; el Cambiaformas en su prueba
    for a in juego.aliens:
        a.hitbox.topleft = (5, 5)
        a.descanso_ms = 10 ** 9
    return juego


def frames(juego, n):
    for _ in range(n):
        juego._actualizar_partida(DT)


def poner(j, punto):
    j.personaje.hitbox.center = (int(punto[0]), int(punto[1]))
    j.personaje.sync_sprite_from_hitbox()


def cap(juego, nombre):
    juego._dibujar()
    pygame.image.save(juego.screen, os.path.join(OUT, nombre))


juego = nueva_partida()
red = juego.nexus
j1, j2 = juego.jugadores
assert red is not None and len(red.bots()) == 3
assert len(red._presos()) == len(CUENTAS)
assert red.barras() == (0.0, 0.0), "todos empiezan grises"
assert red.color(red.nodo_de(j1)) == VERDE
for nodo in red.grafo.nodos():
    assert red.grafo.grado_salida(nodo) >= 1, nodo
print(f"red: {len(red.grafo)} cuentas, {red.grafo.aristas()} conexiones, "
      f"{len(red.grafo.componentes())} componente(s)")

# El rumor llega por el grafo: nivel por nivel.
rng = random.Random(3)
red.rng = rng
red.reloj_rumor_ms = 10 ** 9; red.reloj_normal_ms = 10 ** 9
rumor = red.lanzar_rumor(next(r for r in __import__("data.nexus", fromlist=["RUMORES"]).RUMORES
                              if r["lugar"] == "capsula"))
assert rumor is not None and rumor.lugar == juego.mision.capsula.center
assert rumor.alcanzados == set()
frames(juego, int(TICK_PROPAGACION_MS / DT) + 2)
assert rumor.alcanzados, "en un tick ya les llegó a los seguidores del bot"
assert all(red.grafo.datos[n]["tipo"] == "preso" or n.startswith("jugador")
           for n in rumor.alcanzados)
# Hasta que llegue a algún jugador (si no, se le hace llegar por un camino).
for _ in range(15):
    if red.nodo_de(j1) in rumor.alcanzados:
        break
    frames(juego, int(TICK_PROPAGACION_MS / DT) + 1)
if red.nodo_de(j1) not in rumor.alcanzados:
    rumor.alcanzados.add(red.nodo_de(j1))
    rumor.via[red.nodo_de(j1)] = rumor.autor
verde, rojo = red.barras()
print(f"rumor: llegó a {len(rumor.alcanzados)} cuentas; barras verde {verde:.0%} / rojo {rojo:.0%}")
assert verde == 0.0

# El celular: TAB lo abre, el feed muestra el rumor; con el celular abierto no camina.
assert red.sin_leer(j1) >= 1
juego._tecla_en_partida(pygame.K_TAB)
assert j1.panel["tipo"] == "celular" and j1.panel["vista"] == "feed"
assert j1.ocupado and juego.logros.tiene("conectado")
indice = next(i for i, (t, d) in enumerate(j1.panel["opciones"]) if d is rumor)
j1.cursor = indice
cap(juego, "nexus_a_feed.png")
juego._tecla_en_partida(pygame.K_e)
assert j1.panel["vista"] == "post" and j1.panel["pub"] is rumor
acciones = [a for _, a in j1.panel["opciones"]]
assert acciones[0] == "investigar" and "rastrear" in acciones and "compartir" in acciones
cap(juego, "nexus_b_post.png")

# ¿De dónde salió? El camino más corto empieza en el bot.
j1.cursor = acciones.index("rastrear"); juego._tecla_en_partida(pygame.K_e)
assert j1.panel["vista"] == "origen"
camino = j1.panel["camino"]
assert camino[0] == rumor.autor and camino[-1] == red.nodo_de(j1), camino
assert red.es_bot(camino[0])
cap(juego, "nexus_c_origen.png")
juego._tecla_en_partida(pygame.K_TAB)          # atrás: al feed
assert j1.panel["vista"] == "feed"
print(f"celular: feed, publicación y origen ({' > '.join(red.usuario(n) for n in camino)})")

# Investigar: flecha al lugar; al llegar se saca la foto sola.
j1.cursor = next(i for i, (t, d) in enumerate(j1.panel["opciones"]) if d is rumor)
juego._tecla_en_partida(pygame.K_e)
juego._tecla_en_partida(pygame.K_e)            # "Ir a verificarlo"
assert red.investigando[j1] is rumor
juego._tecla_en_partida(pygame.K_TAB); juego._tecla_en_partida(pygame.K_TAB)
assert j1.panel is None
cap(juego, "nexus_d_flecha.png")
poner(j1, (rumor.lugar[0], rumor.lugar[1] + 40))
frames(juego, 2)
assert rumor in red.evidencias[j1] and j1 not in red.investigando
print("investigar: flecha al lugar y la foto se saca sola al llegar")

# Desmentir recortada: no avisa a ningún alien.
for a in juego.aliens:
    a.descanso_ms = 0
    a.hitbox.center = (j1.hitbox.centerx + 300, j1.hitbox.centery)
    a.punto_ruido = None
juego._tecla_en_partida(pygame.K_TAB)
assert j1.panel["pestana"] == "misiones" and j1.panel["opciones"][0] == ("post", rumor)
juego._tecla_en_partida(pygame.K_e)
assert j1.panel["estado"] == "foto" and j1.panel["opciones"][0][1] == "desmentir"
juego._tecla_en_partida(pygame.K_e)                # "Publicar mi foto y desmentirlo"
assert j1.panel["vista"] == "ubicacion"
cap(juego, "nexus_e_ubicacion.png")
j1.cursor = 1; juego._tecla_en_partida(pygame.K_e)  # recortada
assert j1.panel["vista"] == "mensaje" and rumor.desmentida
assert all(a.punto_ruido is None for a in juego.aliens), "recortada no delata"
assert juego.logros.tiene("fact_checker") and juego.logros.tiene("perfil_bajo")
for _ in range(8):
    frames(juego, int(TICK_PROPAGACION_MS / DT) + 1)
verde, rojo = red.barras()
desmentido = next(p for p in reversed(red.publicaciones) if p.tipo == "desmentido")
assert desmentido.desmiente is rumor and desmentido.alcanzados, "el desmentido corrió por la red"
print(f"desmentido: llegó a {len(desmentido.alcanzados)} cuentas; verde {verde:.0%} / rojo {rojo:.0%}")
juego._tecla_en_partida(pygame.K_TAB)
juego._tecla_en_partida(pygame.K_TAB)
assert j1.panel is None

# Desmentir tal cual: el alien más cercano va por él.
otro = red.lanzar_rumor()
assert otro is not None
red.evidencias[j1].append(otro)
for a in juego.aliens:
    a.descanso_ms = 0; a.accion = "PATRULLAR"; a.punto_ruido = None
cercano = min(juego.aliens, key=lambda a: math.dist(a.centro, j1.hitbox.center))
texto, _ = red.desmentir(j1, otro, con_ubicacion=True)
assert cercano.punto_ruido == j1.hitbox.center, "la foto con ubicación lo delató"
assert "viene por ti" in texto
print("foto tal cual:", cercano.nombre, "va hacia", cercano.punto_ruido)
for a in juego.aliens:
    a.descanso_ms = 10 ** 9; a.punto_ruido = None

# Compartir un rumor: sus seguidores se ponen rojos.
tercero = red.lanzar_rumor()
seguidores = [n for n in red.grafo.vecinos(red.nodo_de(j2)) if red.grafo.datos[n]["tipo"] == "preso"]
texto, puntos = red.compartir(j2, tercero)
assert puntos < 0 and all(red.color(n) == ROJO for n in seguidores)
assert red.stats[j2]["compartidos_falsos"] == 1
print("compartir sin verificar: los seguidores de", j2.rol, "se ponen rojos")

# Reportar: a un prisionero no sirve; a un bot lo borra del grafo.
preso = red._presos()[0]
texto, puntos = red.reportar(j2, preso)
assert puntos < 0 and preso in red.grafo
bot = red.bots()[0]
texto, puntos = red.reportar(j2, bot)
assert puntos > 0 and bot not in red.grafo and juego.logros.tiene("cazador_de_bots")
print("reportar: el prisionero sigue, el bot se borra del grafo")

# Rojo ganando: los aliens se potencian.
alien = next(a for a in juego.aliens if a.datos["alcance_vision"] > 0)  # el Ciego no ve
vision_antes = alien.alcance_vision
for n in red._presos():
    red.grafo.datos[n]["color"] = ROJO
for n in red._presos()[:2]:
    red.grafo.datos[n]["color"] = GRIS
frames(juego, 1)
assert red.potencia_aliens() == 1.0 and alien.potencia_nexus == 1.0
assert alien.alcance_vision > vision_antes
print(f"rojo ganando: potencia {red.potencia_aliens():.0%}, visión {vision_antes:.0f} -> {alien.alcance_vision:.0f}")

# Planos: sin ellos la cápsula no se repara.
juego.mision.fase = "capsula"; juego.mision.piezas_entregadas = 3
forj = next(j for j in juego.jugadores if j.rol == "Forjador")
poner(forj, juego.mision.capsula.center)
assert not red.planos
juego.mision.mantener(forj, 500)
assert juego.mision.reparacion == 0, "sin planos no repara"
assert "planos" in juego.mision.objetivo()
for n in red._presos():
    red.grafo.datos[n]["color"] = VERDE
frames(juego, 1)
assert red.planos and juego.logros.tiene("planos") and alien.potencia_nexus == 0
juego.mision.mantener(forj, 500)
assert juego.mision.reparacion > 0
print("planos: con", f"{UMBRAL_PLANOS:.0%}", "de verdes se desbloquean y ya se puede reparar")

# Resultados con el resumen de NEXUS.
juego.terminar_ronda()
for _ in range(80):
    if juego.transitions.is_idle(): break
    juego.transitions.update(juego, 33)
juego.current_screen = "resultados"
cap(juego, "nexus_f_resultados.png")
r = red.resumen()
assert r["desmentidos"] == 2 and r["compartidos_falsos"] == 1 and r["bots_reportados"] == 1
print("resultados:", r["consejo"])

# Aunque gane el rojo (todos les creen a los aliens), no se pierde por eso.
juego2 = nueva_partida()
for n in juego2.nexus._presos():
    juego2.nexus.grafo.datos[n]["color"] = ROJO
frames(juego2, 2)
assert juego2.nexus.barras()[1] >= 0.99 and juego2.mision.resultado is None
print("rojo al 100%: no se pierde (solo los aliens más rápidos)")

# El mando abre el celular con RB.
juego3 = nueva_partida()
from juego.mandos import tecla_virtual
j3 = juego3.jugadores[0]
j3.teclas = dict(j3.teclas)
j3.teclas["celular"] = tuple(j3.teclas["celular"]) + (tecla_virtual(2, "celular"),)
juego3._tecla_en_partida(tecla_virtual(2, "celular"))
assert j3.panel is not None and j3.panel["tipo"] == "celular"
print("mando: RB abre el celular")

# El celular separa por pestañas y nadie tiene más de 3 cosas por ir a verificar
# (el límite es POR JUGADOR: lo que le llega a uno que ya tiene 3 se pierde).
from redes import celular as logica
from data.nexus import MAX_POR_VERIFICAR
juego4 = nueva_partida()
red4, j4 = juego4.nexus, juego4.jugadores[0]
n = len([j for j in juego4.jugadores if j in red4.vistas])
nodo4 = red4.nodo_de(j4)
for nodo in red4._presos():                 # todos se lo creen: el rumor llega a todos
    red4.grafo.datos[nodo]["color"] = ROJO
lanzados = []
for _ in range(12):
    lanzados.append(red4.lanzar_rumor())
    for _ in range(12):
        for prop in list(red4.propagaciones):
            if not prop.terminada:
                red4._avanzar(prop)
for j in juego4.jugadores:
    if j in red4.vistas:
        assert len(red4.por_verificar_de(j)) <= MAX_POR_VERIFICAR, len(red4.por_verificar_de(j))
assert len(red4.por_verificar_de(j4)) == MAX_POR_VERIFICAR
assert len(red4.por_verificar()) <= MAX_POR_VERIFICAR * n
assert None in lanzados                       # llegó un punto en que no cabía más
perdido = next((p for p in red4.rumores_activos() if nodo4 not in p.alcanzados), None)
if perdido is not None:
    print("  un rumor que llegó con J1 lleno no le aparece:", perdido.rumor["lugar"])
assert len([p for p in logica.misiones(red4, j4) if logica.es_mision_activa(red4, p)]) == MAX_POR_VERIFICAR
assert all(p.tipo not in ("rumor", "trampa") for p in logica.contenido(red4, j4, "red"))
logica.abrir(juego4, j4)
assert logica.pestana_de(red4, j4) == "misiones"
logica.cambiar_pestana(juego4, j4, 1)
assert logica.pestana_de(red4, j4) == "equipo"
logica.cambiar_pestana(juego4, j4, -2)
assert logica.pestana_de(red4, j4) == "red"          # da la vuelta
print(f"celular: pestañas Misiones/Equipo/Red y máximo {MAX_POR_VERIFICAR} por verificar por jugador ({n} jugador(es))")

print("\nTODO OK")
