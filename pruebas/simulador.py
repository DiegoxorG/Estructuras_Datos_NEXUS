"""Simulador: bots que juegan la misión de la nave de punta a punta, sin ventana.

    python pruebas/simulador.py              (10 partidas, roles variados)
    python pruebas/simulador.py 30           (30 partidas)
    python pruebas/simulador.py 5 Biomante Resonante
    python pruebas/simulador.py 3 --desde 10   (partidas 10, 11 y 12)
    python pruebas/simulador.py 6 --dificultad facil   (facil, normal, dificil, inteligente)

Sirve para dos cosas:
- **Encontrar bugs**: si algo revienta, si un bot se queda trabado (no puede
  llegar a donde tiene que ir), si un alien se queda pegado a una pared...
- **Medir el balance**: cuánto tarda cada fase, cuántas veces atrapan a los
  jugadores y qué tipo de alien, cuántas partidas se ganan.

Los bots juegan "bien pero sin pensar": van directo a lo que toca con el
camino más corto (BFS sobre una cuadrícula del mapa), caminan en sigilo si
hay un alien cerca, rescatan al compañero y encienden la caja de fusibles en
los apagones. No se esconden ni usan habilidades. Un jugador real lo hace
mejor en sigilo y peor en orientarse, así que los números son una guía.
"""

import os, sys, math, random, time, traceback
from collections import deque, Counter, defaultdict
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)
import pygame; pygame.init()

from juego import app as App
from juego import objetos_mapa
from misiones.mision import RADIO_RESCATE, PIEZAS_NECESARIAS
objetos_mapa.mapa_activo = lambda: "Nave"
App.Narrador.decir = lambda self, *a, **k: True   # sin banners (más rápido)
DT = 1000 // 60
PASO = 16
RADIO_EVITAR = 170


class Teclas(dict):
    def __getitem__(self, k):
        return self.get(k, False)


TECLAS = Teclas()
pygame.key.get_pressed = lambda: TECLAS

MOVER = [
    {"arriba": pygame.K_w, "abajo": pygame.K_s, "izquierda": pygame.K_a, "derecha": pygame.K_d},
    {"arriba": pygame.K_UP, "abajo": pygame.K_DOWN, "izquierda": pygame.K_LEFT, "derecha": pygame.K_RIGHT},
]


DIFICULTAD = None     # --dificultad facil|normal|... (sin eso: como Difícil)


def nueva_partida(roles):
    g = App.Game()
    if DIFICULTAD:
        from juego.dificultad import Dificultad
        g.dificultad = Dificultad(DIFICULTAD)
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
    # El tutorial ya no se acaba solo a los 30 s: los bots lo saltan, como si
    # cada uno pasara sus pasos con la tecla de habilidad.
    if g.tutorial is not None:
        for j in g.jugadores:
            while g.en_tutorial and not g.tutorial.esta_listo(j):
                g.tutorial.siguiente(j)
        if not g.en_tutorial:
            g._terminar_tutorial()
    # Los bots no usan el celular: sin NEXUS la cápsula no pide los planos y
    # los aliens no se potencian. Así el simulador mide la misión de siempre.
    g.nexus = None
    return g


class Mapa:
    """Cuadrícula de dónde cabe un jugador, para buscar caminos con BFS."""

    def __init__(self, g):
        self.g = g
        j = g.jugadores[0]
        self.w, self.h = j.personaje.hitbox_w, j.personaje.hitbox_h
        m = g.mundo
        base = m.paredes_base
        self.libre = set()
        for x in range(0, m.ancho - self.w, PASO):
            for y in range(0, m.alto - self.h, PASO):
                if pygame.Rect(x, y, self.w, self.h).collidelist(base) == -1:
                    self.libre.add((x, y))

    def bloqueos(self):
        g = self.g
        extra = [p for p in g.mundo.paredes if p not in g.mundo.paredes_base]
        extra += [p["rect"] for p in g.puertas_dobles if not p["abierta"]]
        extra += [c["rect"] for c in g.compuertas if c["cerrada"]]
        return extra

    def celda(self, punto):
        return (int(punto[0] - self.w / 2) // PASO * PASO, int(punto[1] - self.h / 2) // PASO * PASO)

    def camino(self, desde, hasta, cerca=0, evitar=(), arriesgar=True):
        """Lista de celdas de `desde` a cerca de `hasta` (puntos del mundo).

        `evitar` son puntos (aliens) por los que no quiere pasar cerca: un
        jugador con cuidado da la vuelta. Si así no hay camino, se arriesga.
        """
        if evitar:
            prohibidas = set()
            for alien in evitar:
                prohibidas |= self.zona_de(alien)
            ruta = self._camino(desde, hasta, cerca, prohibidas)
            if ruta or not arriesgar:
                return ruta
        return self._camino(desde, hasta, cerca, ())

    def huida(self, desde, peligro, pasos=45):
        """Camino a la celda más lejos de `peligro` a menos de `pasos` celdas."""
        extra = self.bloqueos()
        x0, y0 = desde[0] - self.w / 2, desde[1] - self.h / 2
        inicio = (int(x0) // PASO * PASO, int(y0) // PASO * PASO)
        if inicio not in self.libre:
            return []
        previo, nivel = {inicio: None}, {inicio: 0}
        cola = deque([inicio])
        mejor, mejor_d = inicio, 0
        while cola:
            c = cola.popleft()
            d = math.dist((c[0] + self.w / 2, c[1] + self.h / 2), peligro)
            if d > mejor_d:
                mejor, mejor_d = c, d
            if nivel[c] >= pasos:
                continue
            for dx, dy in ((PASO, 0), (-PASO, 0), (0, PASO), (0, -PASO)):
                v = (c[0] + dx, c[1] + dy)
                if v in previo or v not in self.libre:
                    continue
                if extra and pygame.Rect(v[0], v[1], self.w, self.h).collidelist(extra) != -1:
                    continue
                previo[v], nivel[v] = c, nivel[c] + 1
                cola.append(v)
        ruta = []
        while mejor is not None:
            ruta.append(mejor)
            mejor = previo[mejor]
        return ruta[::-1]

    def zona_de(self, alien):
        """Celdas peligrosas cerca de un alien: alrededor suyo y en su cono."""
        ax, ay = alien.centro
        alcance = max(RADIO_EVITAR, alien.alcance_vision * 0.85)
        medio = alien.datos["medio_angulo"] + 0.15
        r = int(alcance // PASO) + 1
        bx, by = int(ax - self.w / 2) // PASO * PASO, int(ay - self.h / 2) // PASO * PASO
        zona = set()
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                d2 = (dx * dx + dy * dy) * PASO * PASO
                if d2 <= RADIO_EVITAR ** 2:
                    zona.add((bx + dx * PASO, by + dy * PASO))
                elif d2 <= alcance ** 2 and medio > 0.15:
                    dif = (math.atan2(dy, dx) - alien.angulo + math.pi) % (2 * math.pi) - math.pi
                    if abs(dif) <= medio:
                        zona.add((bx + dx * PASO, by + dy * PASO))
        return zona

    def _camino(self, desde, hasta, cerca, evitar):
        extra = self.bloqueos()
        def ok(c):
            if c not in self.libre:
                return False
            if extra and pygame.Rect(c[0], c[1], self.w, self.h).collidelist(extra) != -1:
                return False
            return c not in evitar
        # La celda de partida: la libre más cercana entre las cuatro que
        # rodean la posición real (redondear a ciegas podía caer en una pared).
        x0, y0 = desde[0] - self.w / 2, desde[1] - self.h / 2
        candidatas = [(int(x0) // PASO * PASO + dx, int(y0) // PASO * PASO + dy)
                      for dx in (-PASO, 0, PASO, 2 * PASO) for dy in (-PASO, 0, PASO, 2 * PASO)]
        candidatas = [c for c in candidatas if ok(c)] or [self.celda(desde)]
        inicio = min(candidatas, key=lambda c: math.dist(c, (x0, y0)))
        meta = (hasta[0] - self.w / 2, hasta[1] - self.h / 2)
        radio = max(PASO, cerca)
        previo = {inicio: None}
        cola = deque([inicio])
        mejor = None
        while cola:
            c = cola.popleft()
            if math.dist(c, meta) <= radio:
                mejor = c
                break
            for dx, dy in ((PASO, 0), (-PASO, 0), (0, PASO), (0, -PASO)):
                v = (c[0] + dx, c[1] + dy)
                if v not in previo and ok(v):
                    previo[v] = c
                    cola.append(v)
        if mejor is None:
            return None
        ruta = []
        while mejor is not None:
            ruta.append(mejor)
            mejor = previo[mejor]
        return ruta[::-1]


class Bot:
    def __init__(self, g, jugador, mapa):
        self.g, self.j, self.mapa = g, jugador, mapa
        self.seat = jugador.puesto
        self.meta = None
        self.ruta = []
        self.replan_ms = 0
        self.sabe_codigo = False
        self.quieto_ms = 0
        self.ultimo = jugador.hitbox.topleft
        self.mantener = False
        self.presionar = False
        self.sin_camino = 0
        self.espera_ms = 0
        self.esperando = False
        self.huir_ms = 0

    # -- Qué hacer ---------------------------------------------------------------
    def decidir(self, otro):
        g, j, m = self.g, self.j, self.g.mision
        self.mantener = self.presionar = False
        if j.preso:
            return None, 0
        if j.panel is not None:            # cerrar notas abiertas
            self.presionar = True
            return None, 0
        # 1. Rescatar al compañero.
        if otro.j.preso:
            celda = otro.j.preso["punto"]
            if math.dist(j.hitbox.center, celda) <= RADIO_RESCATE - 15:
                self.presionar = True
                return None, 0
            return celda, RADIO_RESCATE - 30
        # 2. Apagón: a la caja buena (el más cercano, o los dos si el otro está lejos).
        ev = g.eventos
        if ev is not None and ev.apagon and ev.caja is not None:
            caja = ev.caja["rect"].center
            if math.dist(j.hitbox.center, caja) <= 50:
                self.mantener = True
                return None, 0
            return caja, 30
        # 3. La misión.
        if m.fase == "prision":
            nota = next(n for n in m.notas if m.codigo in n["texto"])
            if not self.sabe_codigo:
                if math.dist(j.hitbox.center, nota["rect"].center) <= 50:
                    self.sabe_codigo = True
                else:
                    return nota["rect"].center, 30
            otro.sabe_codigo = otro.sabe_codigo or self.sabe_codigo and self.seat == 0
            if self.seat == 0:
                frente = (m.puerta.right + 40, m.puerta.centery)
                if math.dist(j.hitbox.center, frente) <= 40:
                    self.presionar = "codigo"
                    return None, 0
                return frente, 24
            return (m.puerta.right + 120, m.puerta.centery), 60
        doble = next((p for p in g.puertas_dobles if not p["abierta"]), None)
        necesita_control = (m.fase == "sabotaje") or any(
            not p["recogida"] and p["rect"].centery < g.mundo.alto * 0.4 for p in g.piezas)
        if doble is not None and necesita_control and m.fase in ("sabotaje", "capsula"):
            panel = doble["paneles"][self.seat % 2].center
            if math.dist(j.hitbox.center, panel) <= 36:
                self.mantener = True
                return None, 0
            return panel, 24
        if m.fase == "sabotaje":
            puede = j.rol == "Tecnomante" or "decodificador" in j.objetos
            if not puede and m.falta_tecnomante:
                cons = next((c for c in m.consumibles if not c["tomado"] and c["tipo"] == "decodificador"), None)
                if cons is not None and not any("decodificador" in b.objetos for b in g.jugadores):
                    if math.dist(j.hitbox.center, cons["rect"].center) <= 40:
                        self.presionar = True
                        return None, 0
                    return cons["rect"].center, 24
            if puede:
                consola = next((c for c in m.consolas if c["progreso"] < 1), None)
                if consola is not None:
                    if math.dist(j.hitbox.center, consola["rect"].center) <= 50:
                        self.mantener = True
                        return None, 0
                    return consola["rect"].center, 36
            return self._piezas_o_esperar()
        if m.fase == "capsula":
            faltan = PIEZAS_NECESARIAS - m.piezas_entregadas
            puede = j.rol == "Forjador" or "kit" in j.objetos
            if faltan > 0 and (puede or not m.falta_forjador or m.kit_libre() is None):
                return self._piezas_o_esperar(entregar=True)
            if not puede and m.falta_forjador:
                cons = next((c for c in m.consumibles if not c["tomado"] and c["tipo"] == "kit"), None)
                if cons is not None and not any("kit" in b.objetos for b in g.jugadores):
                    if math.dist(j.hitbox.center, cons["rect"].center) <= 40:
                        self.presionar = True
                        return None, 0
                    return cons["rect"].center, 24
            if puede:
                if m._cerca(j, m.capsula, 5):
                    self.mantener = True
                    return None, 0
                return m.capsula.center, 60
            return m.capsula.center, 140
        if m.fase == "huida":
            return m.capsula.center, 40
        return None, 0

    def _piezas_o_esperar(self, entregar=False):
        g, j, m = self.g, self.j, self.g.mision
        recoge = m.ve_piezas(j)
        faltan = PIEZAS_NECESARIAS - m.piezas_entregadas - sum(b.piezas for b in g.jugadores)
        if recoge and faltan > 0:
            libres = [p for p in g.piezas if not p["recogida"]]
            if libres:
                pieza = min(libres, key=lambda p: math.dist(p["rect"].center, j.hitbox.center))
                return pieza["rect"].center, 0
        if entregar and j.piezas > 0:
            if m._cerca(j, m.capsula, 5):
                self.presionar = True
                return None, 0
            return m.capsula.center, 60
        return m.capsula.center if m.fase == "capsula" else None, 160

    # -- Moverse ------------------------------------------------------------------
    def actualizar(self, dt, otro, teclas, stats):
        j = self.j
        # Si un alien lo persigue, lo primero es huir (el jugador corre más
        # que casi todos).
        perseguidor = next((a for a in self.g.aliens
                            if a.objetivo is j and a.accion == "PERSEGUIR"), None)
        if perseguidor is not None and not j.preso:
            self.huir_ms -= dt
            if self.huir_ms <= 0 or not self.ruta:
                self.ruta = self.mapa.huida(j.hitbox.center, perseguidor.centro)
                self.huir_ms = 500
                self.meta = None
            self.mantener = self.presionar = False
            self._seguir(teclas)
            for k in j.teclas["interactuar"][:1]:
                teclas[k] = False
            self.ultimo = j.hitbox.topleft
            return
        destino, cerca = self.decidir(otro)
        if destino is not None:
            self.espera_ms += dt
            self.replan_ms -= dt
            # Se recalcula si cambió la meta o cada tanto, NO cada frame que no
            # hay camino: un BFS por frame hacía la simulación eterna.
            if destino != self.meta or self.replan_ms <= 0:
                self.meta = destino
                peligro = [a for a in self.g.aliens
                           if a.descanso_ms <= 0 and math.dist(a.centro, destino) > RADIO_EVITAR
                           and math.dist(a.centro, j.hitbox.center) > 60]
                # Si el único camino pasa por donde ve un alien, espera
                # quieto (en sigilo) un rato antes de arriesgarse.
                arriesgar = self.espera_ms > 8000
                self.ruta = self.mapa.camino(j.hitbox.center, destino, cerca, peligro,
                                             arriesgar) or []
                self.esperando = False
                if self.ruta or not peligro:
                    self.espera_ms = 0
                elif not arriesgar:
                    if self.mapa.camino(j.hitbox.center, destino, cerca):
                        self.esperando = True
                self.replan_ms = 400
                if not self.ruta and not self.esperando \
                        and not any(c["cerrada"] for c in self.g.compuertas):
                    self.sin_camino += 1
                    stats["sin_camino"][(self.g.mision.fase, j.rol)] += 1
            self._seguir(teclas)
        # Trabado: con meta y sin moverse.
        if destino is not None and j.hitbox.topleft == self.ultimo and not j.preso \
                and not self.esperando \
                and not any(c["cerrada"] for c in self.g.compuertas) \
                and not self.mantener and j.panel is None:
            self.quieto_ms += dt
            if self.quieto_ms > 4000:
                stats["bots_trabados"].append((self.g.mision.fase, j.rol, j.hitbox.center, destino))
                self.quieto_ms = -10 ** 9   # se reporta una vez
                self.ruta = []
        else:
            self.quieto_ms = max(0, self.quieto_ms) if self.quieto_ms >= 0 else self.quieto_ms
            if j.hitbox.topleft != self.ultimo:
                self.quieto_ms = 0
        self.ultimo = j.hitbox.topleft
        # Sigilo si hay un alien cerca que no lo persigue.
        cerca_alien = self.esperando or any(
            math.dist(a.centro, j.hitbox.center) < 420 and a.objetivo is not j
            for a in self.g.aliens)
        for k in j.teclas["sigilo"][:1]:
            teclas[k] = cerca_alien
        for k in j.teclas["interactuar"][:1]:
            teclas[k] = self.mantener

    def _seguir(self, teclas):
        j = self.j
        while self.ruta and abs(self.ruta[0][0] - j.hitbox.x) <= 3 \
                and abs(self.ruta[0][1] - j.hitbox.y) <= 3:
            self.ruta.pop(0)
        if not self.ruta:
            return
        tx, ty = self.ruta[0]
        x, y = j.hitbox.topleft
        mov = MOVER[self.seat]
        teclas[mov["derecha"]] = tx - x > 2
        teclas[mov["izquierda"]] = x - tx > 2
        teclas[mov["abajo"]] = ty - y > 2
        teclas[mov["arriba"]] = y - ty > 2

    def teclas_sueltas(self):
        """Lo de presionar una vez (KEYDOWN)."""
        g, j = self.g, self.j
        tecla = j.teclas["interactuar"][0]
        if self.presionar == "codigo":
            if j.panel is None:
                g._tecla_en_partida(tecla)
            if j.panel is not None and j.panel.get("accion") == "codigo":
                j.cursor = j.panel["codigos"].index(g.mision.codigo)
                g._tecla_en_partida(tecla)
        elif self.presionar:
            g._tecla_en_partida(tecla)


def jugar(roles, semilla, max_s=520):
    random.seed(semilla)
    stats = {"sin_camino": Counter(), "bots_trabados": [], "fases": {}, "atrapado_por": Counter(),
             "aliens_pegados": Counter(), "error": None, "donde": Counter()}
    g = nueva_partida(roles)
    g.eventos.rng = random.Random(semilla)
    mapa = Mapa(g)
    bots = [Bot(g, j, mapa) for j in g.jugadores[:2]]
    original = g._atrapar
    def atrapar(jugador, alien):
        if jugador is not None:
            stats["atrapado_por"][alien.tipo] += 1
            zona = (round(jugador.hitbox.centerx / g.mundo.ancho, 1),
                    round(jugador.hitbox.centery / g.mundo.alto, 1))
            stats["donde"][zona] += 1
        original(jugador, alien)
    g._atrapar = atrapar

    for a in g.aliens:
        a.actualizar.__func__   # existe
    fase = None
    t = 0
    pegado = defaultdict(int)
    try:
        while t < max_s * 1000 and g.current_screen == "partida":
            TECLAS.clear()
            for i, bot in enumerate(bots):
                bot.actualizar(DT, bots[1 - i], TECLAS, stats)
            for bot in bots:
                bot.teclas_sueltas()
            g._actualizar_partida(DT)
            if g.transitions.active or g.mision.resultado:
                break
            if g.mision.fase != fase:
                fase = g.mision.fase
                stats["fases"][fase] = t / 1000
            for a in g.aliens:
                if a.atascado_ms > 3000 and a.accion in ("PATRULLAR", "VOLVER"):
                    pegado[a.nombre] += 1
                    if pegado[a.nombre] == 1:
                        stats["aliens_pegados"][(a.nombre, a.accion, a.centro)] += 1
                else:
                    pegado[a.nombre] = 0
            t += DT
    except Exception:
        stats["error"] = traceback.format_exc()
    stats["resultado"] = g.mision.resultado or ("sin terminar" if t >= max_s * 1000 else "?")
    stats["duracion_s"] = t / 1000
    stats["eventos"] = list(g.eventos.historial)
    stats["capturas"] = sum(j.veces_atrapado for j in g.jugadores)
    stats["puntos"] = g.equipo.total
    return stats


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--dificultad" in args:
        i = args.index("--dificultad")
        DIFICULTAD = args[i + 1]
        del args[i:i + 2]
    desde = 0
    if "--desde" in args:
        i = args.index("--desde")
        desde = int(args[i + 1])
        del args[i:i + 2]
    n = int(args[0]) if args else 10
    combos = [tuple(args[1:3])] if len(args) > 2 else [
        ("Tecnomante", "Forjador"), ("Biomante", "Resonante"), ("Tecnomante", "Biomante"),
        ("Forjador", "Resonante")]
    resumen = Counter()
    donde = Counter()
    duraciones = defaultdict(list)
    for i in range(desde, desde + n):
        roles = combos[i % len(combos)]
        inicio = time.perf_counter()
        s = jugar(roles, i)
        resumen[s["resultado"]] += 1
        donde.update(s["donde"])
        fases = list(s["fases"].items()) + [("fin", s["duracion_s"])]
        for (f, t0), (_, t1) in zip(fases, fases[1:]):
            duraciones[f].append(t1 - t0)
        print(f"\n#{i} {roles[0]}+{roles[1]}: {s['resultado'].upper()} en {s['duracion_s']:.0f} s "
              f"| capturas {s['capturas']} {dict(s['atrapado_por'])} "
              f"| puntos {s['puntos']} | sim {time.perf_counter() - inicio:.0f} s")
        print("   fases:", {k: round(v) for k, v in s["fases"].items()}, "| eventos:", s["eventos"])
        if s["sin_camino"]:
            print("   SIN CAMINO:", dict(s["sin_camino"]))
        for b in s["bots_trabados"]:
            print("   BOT TRABADO:", b)
        for a in s["aliens_pegados"]:
            print("   ALIEN PEGADO:", a)
        if s["error"]:
            print("   ERROR:\n" + s["error"])
        sys.stdout.flush()
    print("\nRESUMEN:", dict(resumen))
    print("duración media de cada fase (s):",
          {f: round(sum(v) / len(v)) for f, v in duraciones.items()})
    print("dónde los atrapan (x, y del mapa, de 0 a 1):", donde.most_common(6))
