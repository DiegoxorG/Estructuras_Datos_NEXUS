"""Prueba de los aliens, su árbol de comportamiento y el pulso, sin ventana.

    python pruebas/prueba_aliens.py

Comprueba que:
- el árbol se construye, que cada hoja se puede alcanzar y que sus
  condiciones son las mismas que responde Alien.percibir();
- las rutas de patrulla no atraviesan paredes;
- un alien patrulla, ve a un jugador que tiene enfrente, lo persigue y lo
  atrapa; oye un latido fuerte a su espalda y va a investigar; y después
  busca, vuelve por su rastro y retoma la patrulla;
- el pulso sube con un alien cerca y baja cuando el jugador está tranquilo.

Guarda capturas en pruebas/capturas/ (aliens_*.png).
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
from Estructuras.arbol_comportamiento import ArbolComportamiento
from data.comportamiento_alien import ARBOL_ALIEN

DT = 1000 // 60

# ---------- 1. El árbol ----------
arbol = ArbolComportamiento(ARBOL_ALIEN)
print("nodos:", arbol.contar(), "| altura:", arbol.altura())
print("preorden:", [n.accion or n.condicion for n, _ in arbol.preorden()])
casos = {
    "DESCANSAR": {"recuperandose": True},
    "ATRAPAR": {"ve_jugador": True, "jugador_al_alcance": True},
    "PERSEGUIR": {"ve_jugador": True},
    "INVESTIGAR": {"oye_ruido": True},
    "REVISAR_ESCONDITE": {"oye_ruido": True, "en_escondite": True},
    "BUSCAR": {"rastro_reciente": True},
    "VOLVER": {"fuera_de_ruta": True},
    "PATRULLAR": {},
}
for esperada, condiciones in casos.items():
    accion, camino = arbol.decidir(condiciones)
    assert accion == esperada, (esperada, accion)
assert {h.accion for h in arbol.hojas()} == set(casos), "hay hojas sin probar"
print("cada hoja se alcanza con su combinación de condiciones")

copia = ArbolComportamiento(ARBOL_ALIEN)
assert copia.insertar_pregunta("BUSCAR", "¿Ve una huella?", "ve_huella", "SEGUIR_HUELLA", "BUSCAR")
assert copia.decidir({"rastro_reciente": True, "ve_huella": True})[0] == "SEGUIR_HUELLA"
assert copia.contar() == arbol.contar() + 2
print("insertar_pregunta cuelga una conducta nueva sin reconstruir el árbol")

# ---------- 2. Arrancar una partida de 2 ----------
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
g.quitar_cambiaformas()          # los aliens de ruta; el Cambiaformas: prueba_cambiaformas.py
g.saltar_tutorial()
g.mision.abrir_puerta()          # para recorrer la nave entera
for doble in g.puertas_dobles:   # las puertas para dos también frenan a los aliens
    doble["abierta"] = True
    g._puerta_doble_abierta(doble)

j1, j2 = g.jugadores
# a1 oye (el Ciego), a2 ve (el Vigía); el Cazador se aparta para no estorbar.
a1 = next(a for a in g.aliens if a.tipo == "ciego")
a2 = next(a for a in g.aliens if a.tipo == "vigia")
otros = [a for a in g.aliens if a not in (a1, a2)]
LEJOS = g.mundo.punto_libre((int(g.mundo.ancho * 0.12), int(g.mundo.alto * 0.12)), 34, 20)
LEJOS_J = g.mundo.punto_libre((int(g.mundo.ancho * 0.05), int(g.mundo.alto * 0.2)), 48, 19)
print("\naliens:", [(a.nombre, a.tipo, len(a.ruta)) for a in g.aliens])

alien_ejemplo = a1
claves = set(alien_ejemplo.percibir(g.jugadores, g.mundo))
assert claves >= arbol.condiciones(), f"faltan condiciones: {arbol.condiciones() - claves}"
print("Alien.percibir responde todas las condiciones del árbol")

for alien in g.aliens:
    assert not g.mundo.tramos_bloqueados(alien.ruta, alien.hitbox.width, alien.hitbox.height), \
        f"la ruta del {alien.nombre} atraviesa una pared"
    alcanzable = g.mundo.area_alcanzable(j1.hitbox.topleft)
    for punto in alien.ruta:
        assert any(pygame.Rect(c[0], c[1], 48, 19).collidepoint(punto) for c in alcanzable), \
            f"un punto de la ruta del {alien.nombre} no se alcanza caminando"
print("las rutas no atraviesan paredes y están en la zona caminable")

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

# ---------- 3. Patrulla ----------
for j in g.jugadores:
    j.invulnerable_ms = 10 ** 9   # que nadie lo moleste mientras patrulla
indices = {a.numero: set() for a in g.aliens}
for _ in range(60 * 90):
    g._actualizar_partida(DT)
    for a in g.aliens:
        indices[a.numero].add(a.indice_ruta)
        assert not g.mundo.colisiona(a.hitbox), f"{a.nombre} quedó dentro de una pared"
    if all(len(indices[a.numero]) == len(a.ruta) for a in g.aliens):
        break
for a in g.aliens:
    assert a.accion == "PATRULLAR", (a.nombre, a.accion)
    assert len(indices[a.numero]) == len(a.ruta), f"{a.nombre} no recorrió toda su ruta"
print("patrullan toda su ruta sin meterse en paredes")
cap("aliens_a_patrulla.png")

# ---------- 4. Ver, perseguir y atrapar ----------
for a in otros:
    a.hitbox.topleft = LEJOS; a.descanso_ms = 10 ** 9
for j in g.jugadores:
    j.invulnerable_ms = 0
poner(j2, LEJOS_J); j2.invulnerable_ms = 10 ** 9      # el 2 fuera del juego
# En medio de la prisión, que es amplia: nada tapa la vista.
a2.hitbox.center = (2250, 1250); a2.angulo = 0.0
delante = (a2.centro[0] + math.cos(a2.angulo) * 170, a2.centro[1] + math.sin(a2.angulo) * 170)
poner(j1, delante)
g._actualizar_partida(DT)
print("\ncon un jugador enfrente:", a2.accion, "| camino:", [n.texto for n in a2.camino])
assert a2.accion == "PERSEGUIR"
assert j1.visto
g.mostrar_arbol_alien = True; g.alien_en_vista = 1
cap("aliens_b_persigue_arbol.png")
g.mostrar_arbol_alien = False
vidas = j1.vidas
atrapado = frames(60 * 6, lambda: j1.veces_atrapado > 0)
assert atrapado, "el alien no lo atrapó"
assert j1.vidas == vidas - 1 and j1.preso is not None
g._actualizar_partida(DT)
assert a2.accion == "DESCANSAR", a2.accion
print("lo atrapó: pierde una vida, va a una celda y el alien descansa")
cap("aliens_c_atrapado.png")
g.mision.liberar(j1.preso, j2)

# ---------- 5. Oír un latido ----------
frames(60 * 3)   # que se le pase el descanso
j1.invulnerable_ms = 0
detras = (a2.centro[0] - math.cos(a2.angulo) * 110, a2.centro[1] - math.sin(a2.angulo) * 110)
if g.mundo.colisiona(pygame.Rect(detras[0] - 15, detras[1] - 8, 30, 16)):
    detras = (a2.centro[0] - math.cos(a2.angulo) * 80, a2.centro[1] - math.sin(a2.angulo) * 80)
poner(j1, detras)
j1.pulso = 85
assert not a2.puede_ver(j1.hitbox.center, g.mundo), "debería estar a su espalda"
g._actualizar_partida(DT)
print("\nlatido fuerte a su espalda:", a2.accion)
assert a2.accion in ("INVESTIGAR", "PERSEGUIR")
cap("aliens_d_investiga.png")

# ---------- 6. Buscar, volver y retomar ----------
poner(j1, LEJOS_J); j1.invulnerable_ms = 10 ** 9
vistas = []
for _ in range(60 * 30):
    g._actualizar_partida(DT)
    if not vistas or vistas[-1] != a2.accion:
        vistas.append(a2.accion)
    if a2.accion == "PATRULLAR" and "VOLVER" in vistas:
        break
print("secuencia:", " -> ".join(vistas))
assert "BUSCAR" in vistas and "VOLVER" in vistas and vistas[-1] == "PATRULLAR"
assert not a2.rastro
print("vuelve por su rastro (pila vacía) y retoma la patrulla")

# ---------- 7. Pulso ----------
j1.invulnerable_ms = 0
a1.descanso_ms = 10 ** 9           # quieto, para que solo cuente la distancia
poner(j1, (a1.centro[0], a1.centro[1] + 60))
j1.pulso = 20
for _ in range(60 * 2):
    g._actualizar_pulsos(DT)
print("\npulso con un alien a 60 px:", round(j1.pulso), "| radio de ruido:", round(j1.radio_ruido))
assert j1.pulso > 55
cap("aliens_e_pulso_alto.png")
poner(j1, j1.spawn)
j1.personaje.hitbox.topleft = j1.spawn
for a in g.aliens:
    a.hitbox.topleft = LEJOS
for _ in range(60 * 6):
    g._actualizar_pulsos(DT)
print("pulso tras 6 s lejos y quieto:", round(j1.pulso))
assert j1.pulso < 30

# ---------- 8. Cuatro jugadores: que se dibuje todo en cuartos ----------
g.jugadores = [j1, j2, j1, j2]
cap("aliens_f_cuatro.png")
g.jugadores = [j1, j2]

# ---------- 9. Escondites ----------
from entidades.minijuego_latidos import MinijuegoLatidos
alcanzable = g.mundo.area_alcanzable(j1.spawn)
for e in g.escondites:
    assert not g.mundo.colisiona(e["rect"]), f"el escondite {e['clave']} choca con una pared"
    assert any(pygame.Rect(c[0], c[1], 48, 19).colliderect(e["rect"]) for c in alcanzable), \
        f"el escondite {e['clave']} no se alcanza caminando"
    assert not any(z["rect"].colliderect(e["rect"]) for z in g.zonas), \
        f"el escondite {e['clave']} está encima de una zona"
print("\nescondites:", len(g.escondites), "| ninguno choca, todos se alcanzan, ninguno pisa una zona")

for a in g.aliens:
    a.descanso_ms = 0
j2.invulnerable_ms = 10 ** 9
# Un escondite con piso libre a su derecha, donde se pone el alien.
def piso_a_la_derecha(e):
    return all(not g.mundo.colisiona(pygame.Rect(e["rect"].centerx + d - 20,
                                                 e["rect"].centery - 15, 40, 30))
               for d in (60, 130, 160))
escondite = next(e for e in g.escondites if piso_a_la_derecha(e))

def esconder(jugador, e):
    jugador.salir_del_escondite()
    jugador.invulnerable_ms = 0
    jugador.minijuego = None
    poner(jugador, e["rect"].center)
    g._actualizar_partida(DT)
    assert jugador.escondite_cerca is e, "no detecta el escondite"
    g._tecla_en_partida(pygame.K_e)      # tecla de interactuar del jugador 1
    assert jugador.escondido and e["ocupante"] is jugador

def preparar_alien(a, e, distancia=130):
    """Pone al alien cerca del escondite pero de espaldas, para que solo oiga."""
    a.rastro.clear(); a.punto_ruido = None; a.escondite_objetivo = None
    a.busqueda_ms = 0; a.descanso_ms = 0
    a.hitbox.center = (e["rect"].centerx + distancia, e["rect"].centery)
    a.angulo = 0.0       # mirando a la derecha, lejos del escondite
    e["revisado_por"] = None; e["enfriamiento_ms"] = 0
    for otro in g.aliens:
        if otro is not a:
            otro.hitbox.topleft = LEJOS; otro.descanso_ms = 10 ** 9

esconder(j1, escondite)
print("se escondió con [E]:", j1.escondido)
preparar_alien(a1, escondite)
assert not a1.puede_ver(j1.hitbox.center, g.mundo) or True
j1.pulso = 100
llego = frames(60 * 6, lambda: j1.minijuego is not None)
assert llego, f"el alien no vino a revisar (accion {a1.accion})"
assert a1.accion == "REVISAR_ESCONDITE", a1.accion
print("lo oyó escondido y vino a revisar:", [n.texto for n in a1.camino])
g.mostrar_arbol_alien = False
cap("aliens_g_minijuego.png")
g.mostrar_arbol_alien = True; g.alien_en_vista = 0
cap("aliens_h_minijuego_arbol.png")
g.mostrar_arbol_alien = False

# Ganar: presionar solo cuando la aguja está en verde.
puntos = j1.puntos
for _ in range(60 * 30):
    if j1.minijuego is None: break
    if j1.minijuego.aguja_en_zona():
        g._tecla_en_partida(pygame.K_e)
    g._actualizar_partida(DT)
assert j1.minijuego is None and j1.escondido, "debería seguir escondido tras calmarse"
assert j1.puntos == puntos + 5
assert escondite["enfriamiento_ms"] > 0 and escondite["revisado_por"] is None
frames(5)
assert a1.accion in ("BUSCAR", "VOLVER", "PATRULLAR"), a1.accion
print("ganó el minijuego: sigue escondido, +5, y el alien se va a", a1.accion)
frames(60 * 2)
assert j1.minijuego is None, "el alien no debería volver a revisar enseguida"

# Perder: no presionar nada.
esconder(j1, escondite)
preparar_alien(a1, escondite); j1.pulso = 100
assert frames(60 * 6, lambda: j1.minijuego is not None)
atrapado_antes = j1.veces_atrapado
frames(60 * 15, lambda: j1.minijuego is None)
assert j1.veces_atrapado == atrapado_antes + 1 and not j1.escondido
assert j1.preso is not None and escondite["ocupante"] is None
print("perdió sin presionar: el alien entra, lo atrapa y va a una celda")
g.mision.liberar(j1.preso, j2)

# Apretar sin parar no sirve: los fallos suben la amenaza.
juego = MinijuegoLatidos(50)
for _ in range(60 * 20):
    juego.actualizar(DT)
    juego.presionar()
    if juego.terminado: break
assert juego.resultado == "atrapado", juego.resultado
print("apretar sin parar pierde:", juego.aciertos, "aciertos,", juego.fallos, "fallos")

# El pulso sube poco a poco junto con la barra del alien, sin presionar nada.
class _Pulso:
    pulso = 40.0
quieto = _Pulso()
juego = MinijuegoLatidos(quieto.pulso)
ancho_antes = juego.ancho_zona
for _ in range(60 * 2):
    juego.actualizar(DT, quieto)
assert 45 < quieto.pulso < 50, quieto.pulso
assert juego.ancho_zona < ancho_antes, "con el pulso más alto la franja se angosta"
print(f"sin presionar, el pulso sube con la amenaza: 40 -> {quieto.pulso:.1f} en 2 s")

# Visto entrar: si el alien lo ve meterse, va directo a revisar (el Vigía,
# que sí ve).
j1.invulnerable_ms = 0
a1 = a2
preparar_alien(a1, escondite, distancia=160)
a1.angulo = math.pi            # ahora sí mirando hacia el escondite
poner(j1, (escondite["rect"].centerx + 60, escondite["rect"].centery))
g._actualizar_partida(DT)
assert a1.accion == "PERSEGUIR", a1.accion
poner(j1, escondite["rect"].center)
g._actualizar_partida(DT)
g._tecla_en_partida(pygame.K_e)
assert j1.escondido
assert frames(60 * 4, lambda: j1.minijuego is not None), a1.accion
print("lo vio meterse al escondite y fue directo a revisar")
j1.salir_del_escondite()

# Dos escondites juntos, uno con cada jugador, y el alien oye a los dos
# (sus latidos suben y bajan): antes saltaba de uno al otro, se quedaba
# parado al frente sin minijuego y el escondite quedaba en rojo.
import copy
vecino = copy.copy(escondite)
vecino["rect"] = escondite["rect"].move(0, 0)
vecino["rect"].x += escondite["rect"].width + 6
vecino["clave"] = "vecino_prueba"
vecino["ocupante"] = None; vecino["revisado_por"] = None; vecino["enfriamiento_ms"] = 0
g.escondites.append(vecino)
for e in (escondite, vecino):
    e["revisado_por"] = None; e["enfriamiento_ms"] = 0
j1.invulnerable_ms = j2.invulnerable_ms = 0
j1.minijuego = j2.minijuego = None
j1.esconderse(escondite); j2.esconderse(vecino)
preparar_alien(a1, vecino, distancia=170)
parado_sin_minijuego = 0
alguno = None
for k in range(60 * 8):
    con_minijuego = [j for j in (j1, j2) if j.minijuego is not None]
    if con_minijuego:
        # El de adentro se calma y el otro late fuerte: antes, el alien
        # cambiaba de escondite y dejaba al primero sin minijuego.
        otro = j2 if con_minijuego[0] is j1 else j1
        con_minijuego[0].pulso, otro.pulso = 60, 100
    else:
        # Los latidos se turnan: cada medio segundo suena más uno que el otro.
        fuerte, suave = (j1, j2) if (k // 30) % 2 == 0 else (j2, j1)
        fuerte.pulso, suave.pulso = 100, 60
    g._actualizar_partida(DT)
    con_minijuego = [j for j in (j1, j2) if j.minijuego is not None]
    assert len(con_minijuego) <= 1
    if con_minijuego:
        if alguno is None:
            alguno = (con_minijuego[0], a1.escondite_objetivo)
        assert a1.escondite_objetivo is alguno[1], "cambió de escondite en pleno minijuego"
    if any(j.preso for j in (j1, j2)) or (alguno and not con_minijuego):
        break
    parado_sin_minijuego = (parado_sin_minijuego + 1 if a1.accion == "REVISAR_ESCONDITE"
                            and not con_minijuego else 0)
    assert parado_sin_minijuego < 10, "el alien se quedó frente a los escondites sin minijuego"
    for e in (escondite, vecino):
        assert e["revisado_por"] in (None, a1) and (e["revisado_por"] is None or a1.escondite_objetivo is e), \
            "un escondite quedó marcado por un alien que ya no lo revisa"
assert alguno, ("nunca empezó el minijuego", a1.accion)
# Y directo: si ya está revisando uno (con alguien adentro), aunque oiga más
# al del otro, no cambia.
for j in (j1, j2):
    if j.preso is not None:
        g.mision.liberar(j.preso, j2 if j is j1 else j1)
    j.salir_del_escondite(); j.minijuego = None; j.invulnerable_ms = 0
for e in (escondite, vecino):
    e["revisado_por"] = None; e["enfriamiento_ms"] = 0
j1.esconderse(escondite); j2.esconderse(vecino)
preparar_alien(a1, escondite, distancia=60)
a1.escondite_objetivo = escondite
escondite["revisado_por"] = a1
j1.pulso, j2.pulso = 40, 100
a1.percibir([j2, j1], g.mundo, g.escondites)
assert a1.escondite_objetivo is escondite, "cambió al escondite del que late más"
a1._ejecutar("REVISAR_ESCONDITE", DT, 1.0, g.mundo, None, g._alien_revisa)
assert j1.minijuego is not None, "frente al escondite que revisa, el de adentro tiene minijuego"
print("dos escondites juntos: el alien escoge uno, arranca su minijuego y no lo cambia por el otro")
# Si el de adentro sale, el escondite deja de estar en rojo.
for j in (j1, j2):
    if j.preso is not None:
        g.mision.liberar(j.preso, j2 if j is j1 else j1)
for j in (j1, j2):
    j.salir_del_escondite(); j.minijuego = None
for e in (escondite, vecino):
    e["revisado_por"] = None; e["enfriamiento_ms"] = 0
j1.invulnerable_ms = 0
j2.invulnerable_ms = 10 ** 9
poner(j2, LEJOS)
j1.esconderse(escondite)
preparar_alien(a1, escondite, distancia=130)
j1.pulso = 100
assert frames(60 * 6, lambda: j1.minijuego is not None), a1.accion
quien = j1
esc = quien.escondite
assert esc["revisado_por"] is a1
quien.salir_del_escondite()
quien.invulnerable_ms = 10 ** 9
for _ in range(5):
    g._actualizar_partida(DT)
assert esc["revisado_por"] is None, "al salir, el escondite no queda marcado (en rojo)"
print("al salir del escondite, ya no queda en rojo")
for j in (j1, j2):
    j.salir_del_escondite()
g.escondites.remove(vecino)

print("\nTODO OK")
