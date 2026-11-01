"""Prueba de oscuridad, tipos de alien, sigilo, eventos, puertas para dos y
tutorial, sin ventana.

    python pruebas/prueba_sorpresas.py

Juega en la nave (Hitboxes/Nave_objetos.json). Guarda capturas en
pruebas/capturas/sorpresas_*.png.
"""

import os, sys, math, time, random
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
from misiones import puertas
from juego import tutorial as T
objetos_mapa.mapa_activo = lambda: "Nave"
DT = 1000 // 60


class Teclas(dict):
    def __getitem__(self, k):
        return self.get(k, False)


TECLAS = Teclas()
pygame.key.get_pressed = lambda: TECLAS


def nueva_partida(roles=("Tecnomante", "Forjador")):
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
    g.quitar_cambiaformas()      # lo prueba pruebas/prueba_cambiaformas.py
    return g


def poner(cosa, punto):
    if hasattr(cosa, "personaje"):
        cosa.personaje.hitbox.center = (int(punto[0]), int(punto[1]))
        cosa.personaje.sync_sprite_from_hitbox()
    else:
        cosa.hitbox.center = (int(punto[0]), int(punto[1]))


def frames(g, n):
    for _ in range(n):
        g._actualizar_partida(DT)


def cap(g, nombre):
    g._dibujar()
    pygame.image.save(g.screen, os.path.join(OUT, nombre))


def libre_cerca(g, punto):
    return g.mundo.punto_libre(punto, 48, 19)


# ================= Tutorial =================
g = nueva_partida()
j1, j2 = g.jugadores
assert g.en_tutorial and g.narrador.dichas[0][0] == "tutorial"
posiciones = [a.centro for a in g.aliens]
tiempo = g.tiempo_jugado_ms
frames(g, 60)
assert [a.centro for a in g.aliens] == posiciones, "los aliens no se mueven en el tutorial"
assert g.tiempo_jugado_ms == tiempo, "el cronómetro no corre en el tutorial"
print("tutorial: aliens dormidos y reloj quieto | paso de J1:", g.tutorial.texto(j1)[2])
cap(g, "sorpresas_a_tutorial.png")

# J1 camina: pasa al paso del sigilo.
TECLAS[pygame.K_d] = True
frames(g, 5)
assert g.tutorial.texto(j1)[0] == 2, g.tutorial.texto(j1)
TECLAS[pygame.K_LSHIFT] = True
frames(g, 60)
TECLAS.clear()
assert g.tutorial.texto(j1)[0] == 3, "caminar en sigilo completa el paso 2"
print("tutorial: moverse y sigilo se completan haciéndolos")

# Sin tiempo: aunque pase un minuto entero, sigue el tutorial.
frames(g, int(60 * 1000 / DT))
assert g.en_tutorial and g.tiempo_jugado_ms == tiempo
print("tutorial: no tiene tiempo, espera a los jugadores")

# La puerta de la prisión no abre mientras alguien no haya terminado.
j1.personaje.hitbox.center = g.mision.puerta.center
j1.personaje.sync_sprite_from_hitbox()
assert "tutorial" in g.mision.pista(j1)
assert g.mision.interactuar(j1) and j1.panel is None
print("tutorial: la puerta con código no abre todavía")

# J1 pasa sus pasos con la tecla de habilidad (F), a su ritmo.
while not g.tutorial.esta_listo(j1):
    g._tecla_en_partida(pygame.K_f)
assert g.en_tutorial and "Esperando" in g.tutorial.texto(j1)[2]
assert "1/2" in g.tutorial.texto(j1)[2]
cap(g, "sorpresas_a_tutorial_esperando.png")
# Ya listo, F vuelve a ser su habilidad y no cambia nada del tutorial.
g._tecla_en_partida(pygame.K_f)
assert g.en_tutorial
# J2 también ("-"): ahí sí despiertan los aliens.
for _ in range(len(T.PASOS)):
    g._tecla_en_partida(pygame.K_MINUS)
assert not g.en_tutorial and all(not a.aturdido for a in g.aliens)
assert any(d[0] == "despertar" for d in g.narrador.dichas)
frames(g, 30)
assert g.tiempo_jugado_ms > tiempo
print("tutorial: cuando los dos terminan despiertan los aliens y corre el reloj")

# Y ya se puede usar el teclado de la puerta.
j1.cerrar_panel()
assert g.mision.pista(j1) == "Teclado de la puerta"
g.mision.interactuar(j1)
assert j1.panel is not None and j1.panel.get("accion") == "codigo"
j1.cerrar_panel()
print("tutorial: terminado, la puerta ya abre con el código")

# ================= Sigilo =================
g = nueva_partida(); g.saltar_tutorial()
j1, j2 = g.jugadores
for a in g.aliens:
    a.descanso_ms = 10 ** 9
poner(j1, libre_cerca(g, (int(0.8 * g.mundo.ancho), int(0.75 * g.mundo.alto))))
j1.pulso = 30
TECLAS[pygame.K_d] = True
x0 = j1.hitbox.x; frames(g, 20); normal = j1.hitbox.x - x0; ruido_normal = j1.radio_ruido
TECLAS[pygame.K_LSHIFT] = True
x0 = j1.hitbox.x; frames(g, 20); lento = j1.hitbox.x - x0; ruido_sigilo = j1.radio_ruido
TECLAS.clear()
print(f"sigilo: avanza {lento}px vs {normal}px | ruido {ruido_sigilo:.0f} vs {ruido_normal:.0f}")
assert 0 < lento < normal * 0.7 and ruido_sigilo < ruido_normal * 0.6

# ================= Tipos de alien =================
tipos = {a.tipo: a for a in g.aliens}
assert set(tipos) == {"ciego", "cazador", "vigia"}, tipos
print("aliens en la nave:", ", ".join(a.nombre for a in g.aliens))
ciego, vigia, cazador = tipos["ciego"], tipos["vigia"], tipos["cazador"]


class Falso:
    """Un jugador de mentira para probar la percepción."""
    def __init__(self, punto, ruido=0):
        self.hitbox = pygame.Rect(0, 0, 20, 10); self.hitbox.center = punto
        self.cazable, self.escondido, self.radio_ruido, self.escondite = True, False, ruido, None


def frente(alien, distancia):
    return (int(alien.centro[0] + math.cos(alien.angulo) * distancia),
            int(alien.centro[1] + math.sin(alien.angulo) * distancia))


class MundoAbierto:
    def linea_libre(self, a, b): return True
    def colisiona(self, r): return False


abierto = MundoAbierto()
for a in g.aliens:
    a.descanso_ms = 0
    a.angulo = 0.0
assert not ciego.percibir([Falso(frente(ciego, 200))], abierto)["ve_jugador"]
assert ciego.percibir([Falso(frente(ciego, 60))], abierto)["ve_jugador"]
oye_ciego = ciego.percibir([Falso(frente(ciego, 200), ruido=120)], abierto)["oye_ruido"]
ciego.punto_ruido = None
oye_vigia = vigia.percibir([Falso((vigia.centro[0], vigia.centro[1] - 200), ruido=120)], abierto)["oye_ruido"]
vigia.punto_ruido = None
assert oye_ciego and not oye_vigia
assert vigia.percibir([Falso(frente(vigia, 450))], abierto)["ve_jugador"]
assert not cazador.percibir([Falso(frente(cazador, 450))], abierto)["ve_jugador"]
print("Ciego: no ve a 200 px, siente a 60, oye lo que el Vigía no | Vigía: ve a 450 px")

# El Cazador corre más que un jugador, pero se cansa.
presa = Falso(frente(cazador, 150))
poner(cazador, cazador.centro)
cansado_a = None
for i in range(400):
    presa.hitbox.x += 4
    cazador.actualizar(DT, abierto, [presa])
    if cazador.cansado:
        cansado_a = i * DT
        break
cazador.actualizar(DT, abierto, [presa])
assert cansado_a is not None and cazador.accion == "DESCANSAR", (cansado_a, cazador.accion)
print(f"Cazador: se cansa a los {cansado_a / 1000:.1f} s de perseguir")

# ================= Puertas para dos =================
puerta = g.puertas_dobles[0]
p0, p1 = puerta["paneles"]
centro_puerta = pygame.Rect(0, 0, 20, 10); centro_puerta.center = puerta["rect"].center
assert not puerta["abierta"] and g._colisiona_jugador(centro_puerta)
assert not g.mundo.colisiona(centro_puerta), "a los aliens no los frena"
for a in g.aliens:
    a.descanso_ms = 10 ** 9
poner(j1, libre_cerca(g, p0.center)); poner(j2, libre_cerca(g, p1.center))
TECLAS[pygame.K_e] = True
frames(g, 120)
assert not puerta["abierta"], "uno solo no la abre"
assert j1.pista_mision and "dos" in j1.pista_mision
TECLAS[pygame.K_RETURN] = True
frames(g, int(puertas.TIEMPO_ABRIR_S * 1000 / DT) + 5)
TECLAS.clear()
assert puerta["abierta"] and not g._colisiona_jugador(centro_puerta)
print("puerta para dos: uno solo no puede; los dos a la vez la abren")

# ================= Eventos aleatorios =================
ev = g.eventos
ev.rng = random.Random(3)
poner(j1, libre_cerca(g, (int(0.8 * g.mundo.ancho), int(0.75 * g.mundo.alto))))
poner(j2, libre_cerca(g, (int(0.85 * g.mundo.ancho), int(0.75 * g.mundo.alto))))
assert not g._extras_dibujo()["oscuridad"], "sin apagón todo está iluminado"
cap(g, "sorpresas_b_iluminado.png")
ev.lanzar("alarma")
assert all(a.alerta for a in g.aliens) and ev.texto().startswith("ALARMA")
ev.terminar()
assert not any(a.alerta for a in g.aliens)
ev.lanzar("compuerta")
cerrada = ev.compuerta
assert cerrada["cerrada"] and g._colisiona_jugador(cerrada["rect"])
ev.restante_ms = 1; ev.actualizar(DT)
assert not cerrada["cerrada"] and ev.activo is None
print("alarma y compuerta: empiezan y se acaban solas")

# Apagón: no se acaba solo, no puede haber dos, y se arregla con la caja buena.
assert len(ev.cajas) == 4
ev.lanzar("apagon")
caja = ev.caja
assert ev.apagon and g._extras_dibujo()["oscuridad"]
assert ev.lanzar("apagon") is None and "apagon" not in ev.posibles()
ev.proximo_ms = 10 ** 9
frames(g, int(60 * 1000 / DT))
assert ev.apagon, "el apagón no se arregla solo"
assert ev.lanzar("alarma") == "alarma", "en plena oscuridad sí puede sonar la alarma"
ev.terminar()
for a in g.aliens:
    a.descanso_ms = 10 ** 9; a.alerta = False
cap(g, "sorpresas_c_apagon.png")
# La flecha roja hacia la caja buena sale en cualquier dificultad (también
# en las que no tienen la amarilla) y no se monta con otra flecha.
from misiones.eventos import COLOR_FLECHA_CAJA
from screens import flechas
from juego.dificultad import Dificultad
dif_antes = g.dificultad
for dif in (Dificultad("facil"), Dificultad("dificil"), None):
    g.dificultad = dif
    g._dibujar()
    rojos = sum(1 for x in range(0, g.screen.get_width(), 2) for y in range(0, g.screen.get_height(), 2)
                if g.screen.get_at((x, y))[:3] == COLOR_FLECHA_CAJA)
    assert rojos > 20, ("no se ve la flecha roja del apagón", dif and dif.clave, rojos)
g.dificultad = dif_antes
flechas.empezar()
lienzo = pygame.Surface((600, 600))
vista, camara = lienzo.get_rect(), pygame.Rect(0, 0, 600, 600)
camara.center = j1.hitbox.center
flechas.flecha_alrededor(lienzo, vista, camara, j1, (j1.hitbox.centerx + 5000, j1.hitbox.centery), (255, 0, 0), "uno")
flechas.flecha_alrededor(lienzo, vista, camara, j1, (j1.hitbox.centerx + 5000, j1.hitbox.centery + 300), (0, 0, 255), "dos")
a1, a2 = flechas._angulos
assert abs(a2 - a1) >= flechas.SEPARACION - 1e-6 and flechas._textos[0].collidelist(flechas._textos[1:]) < 0
print("apagón: flecha roja a la caja de fusibles (con o sin flecha de dificultad)")
otra = next(c for c in ev.cajas if c is not caja)
poner(j1, libre_cerca(g, otra["rect"].center))
assert "no tiene daño" in ev.pista(j1)
poner(j1, libre_cerca(g, caja["rect"].center))
poner(j2, libre_cerca(g, (int(0.85 * g.mundo.ancho), int(0.75 * g.mundo.alto))))
assert ev.caja_cerca(j1) is caja, (j1.hitbox.center, caja["rect"].center)
TECLAS[pygame.K_e] = True
frames(g, int(1000 / DT))
assert ev.apagon and 0 < caja["progreso"] < 1
cap(g, "sorpresas_d_fusibles.png")
frames(g, int(2.5 * 1000 / DT))
TECLAS.clear()
assert not ev.apagon and not g._extras_dibujo()["oscuridad"]
assert any(d[0] == "luz" for d in g.narrador.dichas)
print(f"apagón: dura hasta encender la caja de fusibles ({j1.rol}, "
      f"{'1.5' if j1.rol == 'Tecnomante' else '3'} s manteniendo la tecla)")

# Muchos minutos sin que nadie arregle la luz: nunca hay dos apagones.
ev.rng = random.Random(7)
ev.proximo_ms = 1
apagones_vistos = 0
for _ in range(int(420 * 1000 / DT)):
    antes = ev.apagon
    ev.actualizar(DT)
    if ev.apagon and not antes:
        apagones_vistos += 1
print("eventos en ~7 min sin arreglar la luz:", ev.historial[-12:])
assert apagones_vistos <= 1 and len(set(ev.historial)) >= 2
# Y si la arreglan enseguida: el apagón sale poco (pesos) y nunca dos seguidos
# antes de ENTRE_APAGONES_S.
from misiones.eventos import ENTRE_APAGONES_S
if ev.apagon:
    ev.restaurar_luz()
ev.rng = random.Random(3)
cuando, t = [], 0
for _ in range(int(20 * 60 * 1000 / 100)):
    ev.actualizar(100); t += 100
    if ev.apagon:
        cuando.append(t)
        ev.restaurar_luz()
separaciones = [b - a for a, b in zip(cuando, cuando[1:])]
assert len(cuando) <= 6 and all(d >= ENTRE_APAGONES_S * 1000 for d in separaciones), cuando
print(f"apagones en 20 min arreglándolos al toque: {len(cuando)} (antes salían ~9)")
ev.restaurar_luz()
if ev.activo:
    ev.terminar()
for a in g.aliens:
    a.alerta = False

# ================= Oscuridad: costo de dibujar =================
ev.lanzar("apagon")
pantalla = pygame.Surface((1920, 1080))
g.screen = pantalla
inicio = time.perf_counter()
for _ in range(30):
    g._dibujar()
con = (time.perf_counter() - inicio) / 30 * 1000
g.oscuridad = False
assert not g._extras_dibujo()["oscuridad"], "la opción de la pausa la apaga aunque haya apagón"
inicio = time.perf_counter()
for _ in range(30):
    g._dibujar()
sin = (time.perf_counter() - inicio) / 30 * 1000
print(f"dibujar a 1080p: {con:.1f} ms con oscuridad, {sin:.1f} ms sin ella")
g._manejar_tecla(pygame.K_l)
assert not g.oscuridad, "la L ya no es atajo: va en Pausa > Opciones"
g.oscuridad = True
ev.restaurar_luz()

# ================= La puerta de la prisión en la segunda ronda =================
# Antes, si una ronda terminaba con la puerta cerrada, la siguiente ronda
# tenía dos puertas en el mismo sitio: el código quitaba una y la otra,
# invisible, no dejaba pasar.
g3 = nueva_partida()
g3.iniciar_partida(); g3.quitar_cambiaformas()
assert g3.mundo.paredes.count(g3.mision.puerta) == 1
g3.saltar_tutorial()
for a in g3.aliens:
    a.descanso_ms = 10 ** 9
k1 = g3.jugadores[0]
g3.mision.abrir_puerta(k1)
poner(k1, (g3.mision.puerta.right + 60, g3.mision.puerta.centery))
TECLAS[pygame.K_a] = True
x0 = k1.hitbox.centerx
frames(g3, 60)
TECLAS.clear()
assert k1.hitbox.centerx < g3.mision.puerta.left, "debe cruzar la puerta abierta"
print("segunda ronda: la puerta de la prisión se abre y deja pasar")

# ================= Sellos del Forjador =================
from entidades import acciones_rol
g4 = nueva_partida(("Tecnomante", "Forjador"))
g4.saltar_tutorial()
for a in g4.aliens:
    a.descanso_ms = 10 ** 9
forj = g4.jugadores[1]
panel = next(p for p in g4.paneles if p["clave"] == "panel_pasillo")
sello = panel["sello_rect"]
assert sello is not None and not g4.mundo.bloqueos_alien
forj.arbol.desbloquear("REPARACION", 999)
forj.piezas = 1
poner(forj, panel["rect"].center)
acciones_rol.usar_estacion(g4, forj, panel)
assert panel["reparado"] and sello in g4.mundo.bloqueos_alien and forj.piezas == 0
# Un alien no lo cruza, ni ve a través; un jugador sí pasa.
alien = next(a for a in g4.aliens if a.tipo == "cazador")
alien.descanso_ms = 0
arriba = libre_cerca(g4, (sello.centerx, sello.top - 60))
abajo = libre_cerca(g4, (sello.centerx, sello.bottom + 60))
poner(alien, (arriba[0] + 17, arriba[1] + 10))
for _ in range(240):
    alien._ir_hacia((abajo[0] + 17, abajo[1] + 10), 3, DT, g4.mundo)
assert alien.hitbox.bottom <= sello.top + 2, (alien.hitbox, sello)
# Visión: un punto de cada lado con línea libre entre ellos si no hubiera sello.
g4.mundo.bloqueos_alien.remove(sello)
x = next(x for x in range(sello.left + 10, sello.right - 10, 6)
         if g4.mundo.linea_libre((x, sello.top - 30), (x, sello.bottom + 60)))
g4.mundo.bloqueos_alien.append(sello)
poner(alien, (x, sello.top - 30))
detras = (x, sello.bottom + 60)
alien.angulo = math.atan2(detras[1] - alien.centro[1], detras[0] - alien.centro[0])
assert not alien.puede_ver(detras, g4.mundo), "no ve a través del sello"
g4.mundo.bloqueos_alien.remove(sello)
assert alien.puede_ver(detras, g4.mundo), "sin el sello sí lo vería"
g4.mundo.bloqueos_alien.append(sello)
centro = pygame.Rect(0, 0, 20, 10); centro.center = sello.center
assert not g4._colisiona_jugador(centro), "a los jugadores no los frena"
cap(g4, "sorpresas_f_sello.png")
# No se activa con un alien encima del paso.
otro = next(p for p in g4.paneles if p["clave"] == "panel_control")
poner(g4.aliens[2], otro["sello_rect"].center)
forj.piezas = 1
poner(forj, otro["rect"].center)
acciones_rol.usar_estacion(g4, forj, otro)
assert not otro["reparado"] and forj.piezas == 1
# Otra ronda: los sellos se apagan.
g4.iniciar_partida(); g4.quitar_cambiaformas()
assert not g4.mundo.bloqueos_alien
print("sellos: el Forjador repara un panel y levanta una barrera que frena solo a los aliens")

# ================= Hackeo desde la sala de control =================
g5 = nueva_partida(("Tecnomante", "Forjador"))
g5.saltar_tutorial()
tec = g5.jugadores[0]
terminal = next(t for t in g5.terminales if t["clave"] == "terminal_control")
vigia5 = next(a for a in g5.aliens if a.tipo == "vigia")
assert any(math.dist(terminal["rect"].center, c["rect"].center) < 400 for c in g5.mision.consolas)
tec.arbol.desbloquear("HACKEO", 999)
poner(tec, terminal["rect"].center)
acciones_rol.usar_estacion(g5, tec, terminal)
assert vigia5.aturdido, "el hackeo de la terminal de control apaga al Vigía"
print("hackeo: la terminal de la sala de control apaga al Vigía junto a las consolas")

# ================= Los aliens rodean las paredes para llegar a un ruido =================
g6 = nueva_partida(("Tecnomante", "Forjador"))
g6.saltar_tutorial()
for j in g6.jugadores:
    j.invulnerable_ms = 10 ** 9
afuera = (g6.mision.puerta.left - 60, g6.mision.puerta.centery)   # la alarma del código malo
cazador6 = next(a for a in g6.aliens if a.tipo == "cazador")
inicio6 = cazador6.centro
assert not g6.mundo.linea_libre(inicio6, afuera), "tiene que haber paredes en medio"
cazador6.descanso_ms = 0
cazador6.oir(afuera)
llego = None
for f in range(60 * 30):
    cazador6.actualizar(DT, g6.mundo, g6.jugadores, None, g6.escondites)
    if math.dist(cazador6.centro, afuera) < 40:
        llego = f * DT / 1000
        break
assert llego is not None, ("el Cazador no llegó a la alarma", cazador6.centro)
print(f"navegación: el Cazador rodea las paredes y llega a la alarma en {llego:.1f} s")

# ================= Editor: tipos y puertas para dos =================
import tempfile
sys.path.insert(0, os.path.join(RAIZ, "Editores"))
from editor_mapa import EditorMapa, HERRAMIENTAS
TEMP = os.path.join(tempfile.gettempdir(), "_objetos_prueba_sorpresas.json")
pygame.display.set_mode((1366, 768))
ed = EditorMapa("Nave", ruta_salida=TEMP)
ed.datos = objetos_mapa.cargar("Nave", ruta=objetos_mapa.ruta_archivo("Nave"))
ed.herramienta = [h["clave"] for h in HERRAMIENTAS].index("rutas_aliens")
ed.ruta_elegida = 0
antes = ed.tipo_de_ruta(0)
ed.tecla(pygame.K_t)
assert ed.tipo_de_ruta(0) != antes
ed.herramienta = [h["clave"] for h in HERRAMIENTAS].index("puertas_dobles")
n = len(ed.datos["puertas_dobles"])
for pos in ((300, 300), (360, 300), (420, 300)):
    ed.clic_izquierdo(pos); ed.soltar()
assert len(ed.datos["puertas_dobles"]) == n + 1 and len(ed.datos["puertas_dobles"][-1]["paneles"]) == 2
ed.herramienta = [h["clave"] for h in HERRAMIENTAS].index("paneles")
n_paneles = len(ed.datos["paneles"])
ed.clic_izquierdo((600, 300)); ed.soltar()     # panel nuevo (el último ya tenía sello)
ed.clic_izquierdo((640, 300)); ed.soltar()     # su sello
assert len(ed.datos["paneles"]) == n_paneles + 1 and ed.datos["paneles"][-1].get("sello")
ed.herramienta = [h["clave"] for h in HERRAMIENTAS].index("compuertas")
ed.clic_izquierdo((500, 300)); ed.soltar()
ed.guardar()
leido = objetos_mapa.cargar("Nave", ruta=TEMP)
assert leido["tipos_aliens"][0] == ed.tipo_de_ruta(0) and len(leido["compuertas"]) == 3
assert leido["paneles"][-1]["sello"]["ancho"] > 0
ed.dibujar()
pygame.image.save(ed.screen, os.path.join(OUT, "sorpresas_e_editor.png"))
os.remove(TEMP)
print("editor: T cambia el tipo de alien; puerta para dos con sus paneles; compuertas; panel con sello")

print("\nTODO OK")
