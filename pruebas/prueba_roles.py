"""Prueba de los cuatro roles y sus habilidades, sin ventana.

    python pruebas/prueba_roles.py

Recorre cada habilidad de la lámina de Anny y comprueba que hace lo que dice
data/habilidades.py: terminales, hackeo y escaneo (Tecnomante); piezas,
reparación y señuelo (Forjador); vínculo, regeneración e impulso (Biomante);
sintonía, interceptación y señal falsa (Resonante). También que el árbol manda:
la rama que no se escogió no funciona.

Guarda capturas en pruebas/capturas/ (roles_*.png).
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
objetos_mapa.mapa_activo = lambda: "Nave"   # el único mapa del juego
from entidades import acciones_rol
from data.habilidades import ARBOLES_POR_ROL
from data.roles import ROLES
from Estructuras.arbol_habilidades import construir_arbol

DT = 1000 // 60

# ---------- 1. Los árboles ----------
assert [r["nombre"] for r in ROLES] == list(ARBOLES_POR_ROL)
for rol, datos in ARBOLES_POR_ROL.items():
    arbol = construir_arbol(rol, datos)
    assert arbol.altura() == 2 and len(arbol.por_niveles()) == 3, rol
    for nodo, _ in arbol.por_niveles():
        assert nodo.uso in ("pasiva", "estacion", "activa"), (rol, nodo.clave)
        if nodo.uso == "activa":
            assert nodo.recarga_s > 0, (rol, nodo.clave)
    print(f"{rol}: {[n.clave for n, _ in arbol.por_niveles()]}")
print("cada rol: una base y dos hijas, todas con su forma de uso")

# ---------- 2. Partida ----------
g = App.Game()
def avanzar():
    for _ in range(80):
        if g.transitions.is_idle(): break
        g.transitions.update(g, 33)
g._activar_opcion_menu("jugar"); avanzar(); g.current_screen = "cantidad"
g._manejar_tecla(pygame.K_RETURN); avanzar(); g.current_screen = "roles"
g.seleccion_roles[0]["cursor"] = 0; g._manejar_tecla(pygame.K_e)
g.seleccion_roles[1]["cursor"] = 1; g._manejar_tecla(pygame.K_RETURN)
avanzar(); g.current_screen = "partida"
g.saltar_tutorial()
g.mision.abrir_puerta()      # para recorrer la nave entera
j1, j2 = g.jugadores
print("\njugadores:", [j.rol for j in g.jugadores])
# Las coordenadas de abajo se escribieron para un cuarto abierto: P() las
# lleva a la prisión de la nave, que es amplia y sin paredes en medio.
def P(x, y):
    return (x - 768 + 2250, y - 640 + 1250)
LEJOS = g.mundo.punto_libre((int(g.mundo.ancho * 0.12), int(g.mundo.alto * 0.12)), 34, 20)

def cap(nombre):
    g._dibujar(); pygame.display.flip()
    pygame.image.save(g.screen, os.path.join(OUT, nombre))

def frames(n, hasta=None):
    for _ in range(n):
        g._actualizar_partida(DT)
        if hasta and hasta():
            return True
    return False

def poner(jugador, punto):
    jugador.personaje.hitbox.center = (int(punto[0]), int(punto[1]))
    jugador.personaje.sync_sprite_from_hitbox()

def rol(jugador, nombre, hija=None):
    jugador.asignar_rol(nombre)
    jugador.recarga_ms = 0; jugador.efectos.clear(); jugador.piezas = 0
    if hija:
        ok, _, _ = jugador.arbol.desbloquear(hija, 999)
        assert ok, hija

def aliens_lejos():
    for a in g.aliens:
        a.hitbox.topleft = LEJOS; a.descanso_ms = 0; a.punto_ruido = None
        a.rastro.clear(); a.escondite_objetivo = None; a.busqueda_ms = 0

for j in g.jugadores:
    j.invulnerable_ms = 10 ** 9      # que no los atrapen mientras se prueba

# Estaciones bien puestas.
alcanzable = g.mundo.area_alcanzable(j1.spawn)
ocupado = [z["rect"] for z in g.zonas] + [e["rect"] for e in g.escondites]
cosas = g.terminales + g.paneles + g.piezas
for cosa in cosas:
    r = cosa["rect"]
    assert not g.mundo.colisiona(r), f"{cosa.get('clave', 'pieza')} choca con una pared"
    assert any(pygame.Rect(c[0], c[1], 48, 19).colliderect(r) for c in alcanzable), \
        f"{cosa.get('clave', 'pieza')} no se alcanza"
    assert not any(o.colliderect(r) for o in ocupado), f"{cosa.get('clave', 'pieza')} pisa algo"
for i, a in enumerate(cosas):
    for b in cosas[i + 1:]:
        assert not a["rect"].colliderect(b["rect"])
print(f"{len(g.terminales)} terminales, {len(g.paneles)} paneles, {len(g.piezas)} piezas: bien puestos")

terminal = g.terminales[0]
a1, a2 = g.aliens[:2]
for a in g.aliens[2:]:
    a.descanso_ms = 10 ** 9          # el tercero no estorba

# ---------- 3. Tecnomante ----------
aliens_lejos()
rol(j1, "Tecnomante")
poner(j1, terminal["rect"].center); g._actualizar_partida(DT)
assert j1.estacion_cerca is terminal
g._tecla_en_partida(pygame.K_e)
assert "mapa" in j1.efectos and "escaneo" not in j1.efectos
print("\nConexión digital: la terminal muestra el mapa de la nave")
cap("roles_a_mapa_terminal.png")

rol(j1, "Tecnomante", "HACKEO"); terminal["recarga_ms"] = 0
a1.hitbox.center = (terminal["rect"].centerx + 200, terminal["rect"].centery)
puntos = j1.puntos
g._tecla_en_partida(pygame.K_e)
assert a1.descanso_ms > 0 and a1.aturdido and j1.puntos == puntos + acciones_rol.PUNTOS_HACKEO
g._actualizar_partida(DT)
assert a1.accion == "DESCANSAR", a1.accion
print("Hackeo básico: apaga al alien cercano ->", [n.texto for n in a1.camino])
cap("roles_b_hackeo.png")
terminal["recarga_ms"] = 0

rol(j1, "Tecnomante", "ESCANEO")
g._tecla_en_partida(pygame.K_f)
assert "escaneo" in j1.efectos and j1.recarga_ms > 0
recarga = j1.recarga_ms
g._tecla_en_partida(pygame.K_f)
assert j1.recarga_ms == recarga, "no debería poder usarla en recarga"
print("Escaneo de sistemas: mapa con conos, y respeta la recarga")
cap("roles_c_escaneo.png")
# El árbol manda: con ESCANEO, la terminal ya no hackea.
terminal["recarga_ms"] = 0; aliens_lejos()
a1.hitbox.center = (terminal["rect"].centerx + 200, terminal["rect"].centery)
poner(j1, terminal["rect"].center); g._actualizar_partida(DT)
g._tecla_en_partida(pygame.K_e)
assert a1.descanso_ms == 0, "HACKEO quedó descartado y aun así hackeó"
print("con ESCANEO escogido, la terminal no hackea (la rama HACKEO quedó cerrada)")

# ---------- 4. Forjador ----------
aliens_lejos()
rol(j2, "Forjador")
pieza = g.piezas[0]
poner(j2, pieza["rect"].center); g._actualizar_partida(DT)
assert pieza["recogida"] and j2.piezas == 1
print("\nIngenio mecánico: recoge la pieza al pasar ->", j2.piezas)
rol(j1, "Tecnomante")
poner(j1, g.piezas[1]["rect"].center); g._actualizar_partida(DT)
assert not g.piezas[1]["recogida"], "solo el Forjador recoge piezas"
cap("roles_d_piezas.png")

panel = g.paneles[0]
poner(j2, panel["rect"].center); g._actualizar_partida(DT)
j2.piezas = 1
g._tecla_en_partida(pygame.K_RETURN)
assert not panel["reparado"], "sin REPARACION no debería reparar"
rol(j2, "Forjador", "REPARACION"); j2.piezas = 1
puntos = j2.puntos
g._actualizar_partida(DT)
g._tecla_en_partida(pygame.K_RETURN)
assert panel["reparado"] and j2.piezas == 0 and j2.puntos == puntos + acciones_rol.PUNTOS_REPARACION
print("Reparación básica: repara el panel con una pieza")
cap("roles_e_panel.png")

rol(j2, "Forjador", "FABRICACION"); j2.piezas = 1
poner(j2, P(768, 900)); aliens_lejos()
a2.hitbox.center = P(1000, 640)
g._tecla_en_partida(pygame.K_MINUS)
assert len(g.senuelos) == 1 and j2.piezas == 0
g._actualizar_partida(DT)
assert a2.punto_ruido == g.senuelos[0]["pos"], (a2.punto_ruido, a2.accion)
assert a2.accion == "INVESTIGAR"
print("Fabricación improvisada: el señuelo atrae al alien ->", a2.accion)
cap("roles_f_senuelo.png")
g.senuelos.clear()

# ---------- 5. Biomante ----------
aliens_lejos()
rol(j1, "Biomante", "REGENERACION")
poner(j1, P(768, 640)); poner(j2, P(820, 640))
j2.pulso = 90
g._tecla_en_partida(pygame.K_f)
assert j2.pulso <= 90 - acciones_rol.CALMA_REGENERACION + 1, j2.pulso
print("\nRegeneración dirigida: el pulso del compañero baja a", round(j2.pulso))
cap("roles_g_vinculo.png")

rol(j1, "Biomante", "IMPULSO")
j2.recarga_ms = 12000
for t in g.terminales:
    t["recarga_ms"] = 9000
g._tecla_en_partida(pygame.K_f)
assert j2.recarga_ms == 0 and all(t["recarga_ms"] == 0 for t in g.terminales)
print("Impulso energético: la habilidad del compañero y las terminales quedan listas")
j1.recarga_ms = 0
for t in g.terminales:
    t["recarga_ms"] = 0
g._tecla_en_partida(pygame.K_f)
assert j1.recarga_ms == 0, "si nada necesita energía no gasta la recarga"

# Reparación tiene recarga, y el Impulso la llena.
rol(j2, "Forjador", "REPARACION"); j2.piezas = 2
for p in g.paneles:
    p["reparado"] = False
p1, p2 = g.paneles[0], g.paneles[1]
poner(j2, p1["rect"].center); acciones_rol.usar_estacion(g, j2, p1)
assert p1["reparado"] and j2.recarga_ms > 0
poner(j2, p2["rect"].center); acciones_rol.usar_estacion(g, j2, p2)
assert not p2["reparado"], "en recarga no repara otro panel"
poner(j1, j2.hitbox.center); j1.recarga_ms = 0
g._tecla_en_partida(pygame.K_f)
acciones_rol.usar_estacion(g, j2, p2)
assert p2["reparado"], "después del Impulso sí"
print("Reparación: tiene recarga; el Impulso de la Biomante la deja lista")

# Regeneración ayudando a alguien escondido que está en el minijuego.
from entidades.minijuego_latidos import MinijuegoLatidos
rol(j1, "Biomante", "REGENERACION")
# El escondite más cerca de la terminal: más abajo se hackea desde ella.
escondite = min(g.escondites, key=lambda e: math.dist(e["rect"].center, terminal["rect"].center))
poner(j2, escondite["rect"].center); j2.esconderse(escondite)
j2.minijuego = MinijuegoLatidos(80, a1, escondite)
a1.escondite_objetivo = escondite; escondite["revisado_por"] = a1
j2.minijuego.amenaza = 70
poner(j1, (escondite["rect"].centerx + 90, escondite["rect"].centery))
g._tecla_en_partida(pygame.K_f)
assert j2.minijuego.amenaza <= 70 - acciones_rol.AMENAZA_REGENERACION + 0.01
print("Regeneración también le baja la amenaza a quien está escondido:", round(j2.minijuego.amenaza))

# Hackear al alien que revisa el escondite termina el minijuego sin captura.
rol(j1, "Tecnomante", "HACKEO"); terminal["recarga_ms"] = 0
a1.hitbox.center = (escondite["rect"].centerx + 60, escondite["rect"].centery)
poner(j1, terminal["rect"].center)
assert math.hypot(a1.centro[0] - terminal["rect"].centerx,
                  a1.centro[1] - terminal["rect"].centery) <= acciones_rol.RADIO_HACKEO
g._actualizar_partida(DT)
g._tecla_en_partida(pygame.K_e)
g._actualizar_partida(DT)
assert j2.minijuego is None and j2.escondido and j2.veces_atrapado == 0
print("hackear al alien que revisa un escondite salva al de adentro")
j2.salir_del_escondite()

# ---------- 6. Resonante ----------
aliens_lejos()
rol(j2, "Resonante")
poner(j2, P(768, 640))
a1.hitbox.topleft = LEJOS          # fuera de su pantalla
cap("roles_h_sintonia.png")
print("\nSintonía de señales: flechas hacia los aliens fuera de pantalla (ver captura)")

# Y los que tiene cerca (en su pantalla) pero no ve: sus pasos, en rosado.
from screens import roles as dibujo_roles
def rosados(superficie):
    return sum(1 for x in range(0, superficie.get_width(), 2) for y in range(0, superficie.get_height(), 2)
               if (lambda c: c[0] > 200 and 80 < c[1] < 170 and c[2] > 150)(superficie.get_at((x, y))))
def caminar_y_dibujar(jugador, alien, visibles, oscuro=False):
    lienzo = pygame.Surface((800, 600)); lienzo.fill((0, 0, 0))
    camara = pygame.Rect(0, 0, 800, 600); camara.center = jugador.hitbox.center
    offset = (camara.x, camara.y)
    inicio = (jugador.hitbox.centerx + 150, jugador.hitbox.centery - 120)
    t = pygame.time.get_ticks()
    for k in range(8):
        alien.hitbox.center = (inicio[0] + k * 20, inicio[1])
        dibujo_roles.dibujar_pasos(lienzo, offset, camara, jugador, [alien], visibles, oscuro, t + k * 120)
    return lienzo
a1.hitbox.topleft = LEJOS
dibujo_roles._pasos.clear()
assert rosados(caminar_y_dibujar(j2, a1, [])) > 10, "el Resonante oye los pasos del que no ve"
dibujo_roles._pasos.clear()
assert rosados(caminar_y_dibujar(j2, a1, [a1])) == 0, "al que ve no le hacen falta"
dibujo_roles._pasos.clear()
assert rosados(caminar_y_dibujar(j2, a1, [a1], oscuro=True)) > 10, "a oscuras, aunque esté en su campo"
dibujo_roles._pasos.clear()
assert rosados(caminar_y_dibujar(j1, a1, [])) == 0, "los demás roles no los oyen"
class Sombra:        # (la Sombra no hace ruido al caminar)
    pass
assert not dibujo_roles._oye_pasos_de(Sombra())
pygame.image.save(caminar_y_dibujar(j2, a1, []), os.path.join(OUT, "roles_h2_pasos.png"))
# En la partida: un alien detrás de una pared, cerca del Resonante.
cerca = None
for dx in range(-420, 421, 30):
    for dy in range(-260, 261, 30):
        q = g.mundo.punto_libre((j2.hitbox.centerx + dx, j2.hitbox.centery + dy), 40, 40)
        if math.dist(q, j2.hitbox.center) < 450 and not g.mundo.linea_libre(j2.hitbox.center, q):
            cerca = q; break
    if cerca: break
if cerca:
    dibujo_roles._pasos.clear()
    for k in range(8):
        a1.hitbox.center = g.mundo.punto_libre((cerca[0] + k * 14, cerca[1]), *a1.hitbox.size)
        g._dibujar()
    cap("roles_h3_pasos_partida.png")
print("Sintonía: pasos rosados de los aliens cercanos que no ve (detrás de una pared o a oscuras)")

rol(j2, "Resonante", "INTERCEPCION")
g._tecla_en_partida(pygame.K_MINUS)
assert "intercepcion" in j2.efectos
a1.hitbox.center = P(700, 560)
cap("roles_i_intercepcion.png")
print("Interceptación básica: rutas y decisiones de los aliens")

rol(j2, "Resonante", "EMISION")
aliens_lejos()
a1.hitbox.center = P(1000, 640); a1.angulo = 0
j2.personaje.direccion = "west"
g._tecla_en_partida(pygame.K_MINUS)
assert j2.panel and j2.panel["tipo"] == "emision" and not g.senales and j2.recarga_ms == 0
cap("roles_j_emision_mapa.png")
# Cancelar con la misma tecla no gasta nada.
g._tecla_en_partida(pygame.K_MINUS)
assert j2.panel is None and j2.recarga_ms == 0
# Otra vez, y ahora se escoge el punto con el mouse sobre el mapa.
g._tecla_en_partida(pygame.K_MINUS)
g._dibujar()
rect, escala = j2.panel["rect_mapa"], j2.panel["escala_mapa"]
destino = P(900, 640)
g._manejar_click((int(rect.x + destino[0] * escala), int(rect.y + destino[1] * escala)))
assert j2.panel is None and g.senales and j2.recarga_ms > 0
assert math.dist(g.senales[0]["pos"], destino) < 40, g.senales[0]["pos"]
assert a1.punto_ruido == g.senales[0]["pos"]
g._actualizar_partida(DT)
assert a1.accion == "INVESTIGAR"
print(f"Emisión modulada: mapa, clic en {g.senales[0]['pos']} y el alien va a revisarla")
# Con teclado: el cursor se mueve con las teclas de moverse y se confirma.
j2.recarga_ms = 0; g.senales.clear()
g._tecla_en_partida(pygame.K_MINUS)
antes = list(j2.panel["cursor_mapa"])
acciones_rol.mover_cursor_emision(g, j2, 1, 0)
assert j2.panel["cursor_mapa"][0] > antes[0]
g._tecla_en_partida(pygame.K_RETURN)
assert j2.panel is None and g.senales
print("Emisión modulada: también con teclas (mover cursor + interactuar)")
cap("roles_j_emision.png")

# ---------- 7. El HUD dice qué tecla usar ----------
print("\nHUD:", acciones_rol.linea_de_estado(j1), "|", acciones_rol.linea_de_estado(j2))
rol(j1, "Forjador")
assert "escoge" in acciones_rol.linea_de_estado(j1)

print("\nTODO OK")
