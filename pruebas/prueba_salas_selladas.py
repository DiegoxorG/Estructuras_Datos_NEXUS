"""Prueba de las salas selladas (juego/salas_selladas.py).

    python pruebas/prueba_salas_selladas.py

En MapaE2 (6 salas: Laboratorio, Prisión, General, Control, Residencial y
Biosfera) con 2 jugadores no se sella nada. Para probar el sello se baja la
meta (SALAS_POR_JUGADORES):

1. Meta 5: se sella justo una sala. Nunca Residencial (dejaría a Biosfera
   aislada), ni Control/Prisión/General (siempre van) ni Laboratorio (tiene
   la cápsula): siempre Biosfera.
2. Meta 4: Residencial y Biosfera. El pasillo que las une queda aislado y se
   sella también.
3. Lo de adentro se quita (la consola, la caja de fusibles y las pruebas de
   Biosfera...), queda lo mínimo para la misión, las rutas de los aliens
   pierden los puntos sellados, y no se puede entrar caminando.
4. La partida corre y se dibuja (captura), y en la ronda siguiente con la
   meta normal el mapa vuelve a estar completo.
5. El grafo de salas: nodos = rectángulos, aristas = se tocan.
"""

import os, sys, random
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)
import pygame; pygame.init()
OUT = os.path.join(RAIZ, "pruebas", "capturas")
os.makedirs(OUT, exist_ok=True)

from juego import app as App
from juego import objetos_mapa, salas_selladas as SS, navegacion
from juego import salas as salas_mapa
objetos_mapa.mapa_activo = lambda: "MapaE2"
DT = 1000 // 60
META = dict(SS.SALAS_POR_JUGADORES)


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
    g._activar_opcion_menu("jugar"); avanzar(); g._manejar_tecla(pygame.K_RETURN); avanzar()
    g._manejar_tecla(pygame.K_RETURN); avanzar()
    g.seleccion_roles[0]["cursor"] = 0; g._manejar_tecla(pygame.K_e)
    g.seleccion_roles[1]["cursor"] = 1; g._manejar_tecla(pygame.K_RETURN); avanzar()
    return g


# ---------- Sin sellar: 6 salas y 2 jugadores ----------
g = nueva_partida()
assert len(g.jugadores) == 2 and not g.sellado and g.mundo.paredes_base == g.mundo.paredes_archivo
completo = objetos_mapa.cargar("MapaE2")
assert len(g.objetos["piezas"]) == len(completo["piezas"])
print("MapaE2 (6 salas) con 2 jugadores: no se sella nada")

# ---------- El grafo de salas ----------
grafo = SS.grafo_de_salas(g.salas)
assert len(grafo) == len(g.salas)
nombre = {i: n for i, (n, _) in enumerate(g.salas)}
def vecinas(sala):
    return {SS.clave(nombre[v]) for i in nombre if nombre[i] == sala for v in grafo.vecinos(i)}
assert "pasillo" in vecinas("General") and "pasillo" in vecinas("Biosfera")
assert len(grafo.componentes()) == 1, "todo el mapa está conectado"
print(f"grafo de salas: {len(grafo)} nodos, {grafo.aristas() // 2} conexiones, una componente")

# ---------- Apagado (así se juega): aunque sobren salas, no se sella nada ----------
assert SS.ACTIVO is False
SS.SALAS_POR_JUGADORES[2] = 4
g = nueva_partida()
assert not g.sellado and g.mundo.paredes_base == g.mundo.paredes_archivo
print("apagado: con la meta en 4 tampoco se sella nada (siempre el mapa entero)")
SS.ACTIVO = True        # lo de abajo prueba el mecanismo, por si se vuelve a prender

# ---------- Meta 5: siempre Biosfera ----------
SS.SALAS_POR_JUGADORES[2] = 5
vistas = set()
for semilla in range(12):
    objetos = objetos_mapa.cargar("MapaE2")
    s = SS.aplicar(objetos, g.mundo, salas_mapa.preparar(objetos, g.mundo), 2, random.Random(semilla))
    vistas.add(tuple(s.cerradas))
assert vistas == {("biosfera",)}, vistas
print("meta 5: siempre se sella Biosfera (Residencial dejaría a Biosfera aislada)")

# ---------- Meta 4: Residencial y Biosfera ----------
SS.SALAS_POR_JUGADORES[2] = 4
g = nueva_partida()
s = g.sellado
assert s and s.cerradas == ["biosfera", "residencial"], s.cerradas
assert set(s.abiertas) == {"Control", "Prisión", "General", "Laboratorio"}, s.abiertas
assert g.mundo.sellado is s and all(r in g.mundo.paredes_base for r in s.rects)
W, H = g.mundo.ancho, g.mundo.alto
centros = {n: r.center for n, r in g.salas}
bio = next(r for n, r in g.salas if n == "Biosfera")
res = next(r for n, r in g.salas if n == "Residencial")
# El pasillo entre Residencial y Biosfera quedó aislado: también sellado.
pasillo_bio = next(r for n, r in g.salas if n == "Pasillo" and r.inflate(8, 8).colliderect(bio))
assert any(r.colliderect(pasillo_bio) for r in s.rects)
# Lo de adentro se quitó.
def dentro(p, rect):
    return rect.collidepoint(int(p[0] * W), int(p[1] * H))
for parte in ("consolas", "fusibles", "pruebas", "piezas", "notas", "nexus", "terminales"):
    for o in g.objetos[parte]:
        p = (o["rx"], o["ry"]) if isinstance(o, dict) else o
        assert not dentro(p, bio) and not dentro(p, res), (parte, p)
assert len(g.mision.consolas) == 1 and len(g.eventos.cajas) >= 1
assert len(g.objetos["piezas"]) >= SS.PIEZAS_NECESARIAS and len(g.objetos["pruebas"]) >= 3
assert all(not dentro(p, bio) and not dentro(p, res) for ruta in g.objetos["rutas_aliens"] for p in ruta)
assert len(g.objetos["rutas_aliens"]) == len(g.objetos["tipos_aliens"]) == len(
    [a for a in g.aliens if a is not g.cambiaformas])
print(f"lo sellado se quita: quedan {len(g.objetos['piezas'])} piezas, "
      f"{len(g.mision.consolas)} consola, {len(g.eventos.cajas)} cajas de fusibles, "
      f"{len(g.aliens)} aliens (de {len(completo['rutas_aliens'])})")
# No se puede entrar: ni caminando ni con la navegación.
j1 = g.jugadores[0]
r = j1.hitbox.copy(); r.center = bio.center
assert g.mundo.colisiona(r)
g.saltar_tutorial()
g.mision.abrir_puerta(j1)                          # la de la prisión (frente a Control)
for d in g.puertas_dobles:
    d["abierta"] = True
g.mundo.puertas_alien = []
nav = navegacion.de_mundo(g.mundo, 34, 20)
assert not nav.conectados(j1.hitbox.center, bio.center)
for sala in ("Laboratorio", "Prisión", "General"):
    assert nav.conectados(j1.hitbox.center, g.mundo.punto_libre(centros[sala], 34, 20)), sala
print("no se puede entrar a lo sellado; lo demás sigue conectado")

# ---------- Corre y se dibuja ----------
for _ in range(120):
    g._actualizar_partida(DT)
puerta = next(r for n, r in g.salas if n == "Pasillo" and r.inflate(8, 8).colliderect(res)
              and not r.inflate(8, 8).colliderect(bio))
# Uno en la entrada de Residencial y el otro mirando el Laboratorio (abierto).
for jugador, punto in ((j1, (puerta.right - 150, puerta.centery)),
                       (g.jugadores[1], centros["Laboratorio"])):
    jugador.personaje.hitbox.topleft = g.mundo.punto_libre(punto, jugador.personaje.hitbox_w,
                                                           jugador.personaje.hitbox_h)
    jugador.personaje.sync_sprite_from_hitbox()
g._dibujar()
pygame.image.save(g.screen, os.path.join(OUT, "salas_selladas.png"))
print("la partida corre y se dibuja (pruebas/capturas/salas_selladas.png)")

# ---------- Otra ronda con la meta normal: el mapa vuelve completo ----------
SS.SALAS_POR_JUGADORES.update(META)
mundo = g.mundo
g.iniciar_partida()
assert g.mundo is mundo and not g.sellado and mundo.paredes_base == mundo.paredes_archivo
r = pygame.Rect(0, 0, 34, 20); r.center = bio.center
assert not mundo.colisiona(r) and navegacion.de_mundo(mundo, 34, 20)._celda_de(bio.center) in navegacion.de_mundo(mundo, 34, 20).libre
print("la ronda siguiente con la meta normal vuelve a tener todo el mapa")

# ---------- Lo que pidió el equipo ----------
assert META == {1: 6, 2: 6, 3: 8, 4: 10}
assert [SS.clave(n) for n in SS.SIEMPRE] == ["control", "prision", "general", "bahia"]
print("2 jugadores: 6 salas, 3: 8, 4: 10; siempre Control, Prisión, General y Bahía")
print("\nTODO OK")
