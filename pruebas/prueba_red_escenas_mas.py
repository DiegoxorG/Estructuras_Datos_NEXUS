"""Más escenas del modo en red comparadas con el modo local (2, 3 y 4 jugadores).

    python pruebas/prueba_red_escenas_mas.py            (las tres partidas)
    python pruebas/prueba_red_escenas_mas.py 3          (solo la de 3 jugadores)

Igual que pruebas/prueba_red_escenas.py: un servidor de verdad (otro proceso,
este archivo con --servidor N) va pasando por escenas y en cada una guarda lo
que dibujaría el modo local para los jugadores de cada laptop; dos clientes
(dos Sesion, como dos laptops) guardan lo que dibujan ellos. Con 2 jugadores
cada laptop tiene uno; con 3 y 4, la primera tiene a J1 y la segunda al resto
(pantalla dividida en el cliente).

Las escenas: el susto de cada alien al atraparte (cazador, vigía, ciego, el de
siempre, el Cambiaformas al atrapar y al revelarse, la Sombra), la Sombra y sus
ojos en el apagón (y esfumada), la caja de fusibles buena, el Cambiaformas
disfrazado y revelado, las puertas para dos (uno solo y los dos), una
compuerta, el panel de código, código malo, la puerta abierta (y lo que se ve
por ella), el kit, el decodificador, recoger una pieza, entregar piezas en la
cápsula, repararla, un prisionero que te sigue y el rescate, la planta, el
Guardia distraído y comiendo, el celular completo (investigar, la flecha,
la foto, desmentir con ubicación, compartir, rastrear y reportar, la red),
el caso del infiltrado en la Terminal NEXUS, un logro, la IA de la nave, el
pulso alto, la cuenta regresiva, vidas que bajan, eliminado, derrota y
victoria.

Por escena se pide: que el espejo no falle (Sesion.errores_vistos), que se
vea casi igual que el local (`LIMITE` % de píxeles distintos) y que el estado
clave haya llegado al espejo (`ver`, por ejemplo susto_tipo o
alien.disfrazado). También que lleguen los sonidos de la escena.

Los sustos duran menos de un segundo: en esas escenas el servidor deja el
susto "a la mitad" (susto_ms fijo) para que la captura del local y la del
cliente sean del mismo momento.

Tarda ~4 minutos. Las capturas van a la carpeta temporal (o NEXUS_CAPTURAS),
una subcarpeta por cantidad de jugadores.
"""

import math
import os
import subprocess
import sys
import tempfile
import threading
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

import pygame

PASO = 150             # cuadros del servidor por escena
CAPTURA = 110          # en qué cuadro de la escena se guarda la imagen (par: va con una instantánea)
VER_DESDE = 12         # desde qué cuadro de la escena se mira el espejo (lo que tarda en llegar)
TAM = (1280, 720)
LIMITE = 6.0           # % de píxeles distintos que se aguanta (relojes, interpolación)
CARPETA = os.environ.get("NEXUS_CAPTURAS") or os.path.join(tempfile.gettempdir(), "nexus_red_escenas_mas")

# Cantidad de jugadores -> (roles, dificultad, jugadores locales de cada laptop).
PARTIDAS = {
    2: (["Biomante", "Resonante"], "facil", (1, 1)),
    3: (["Tecnomante", "Forjador", "Biomante"], "normal", (1, 2)),
    4: (["Tecnomante", "Forjador", "Biomante", "Resonante"], "dificil", (1, 3)),
}


# -- Escenas (las arma el servidor y el cliente, con el mismo orden) -----------------------

class Escena:
    def __init__(self, nombre, hacer=None, cada=None, ver=None, sonidos=(), mantener=None,
                 resultado=False):
        self.nombre = nombre
        self.hacer = hacer          # fn(): una vez, al empezar (servidor)
        self.cada = cada            # fn(): antes de cada instantánea (servidor)
        self.ver = ver              # fn(espejo) -> True si llegó lo que importa (cliente)
        self.sonidos = sonidos      # sonidos que el cliente tiene que recibir en la escena
        self.mantener = mantener    # {índice de jugador: {acciones mantenidas}} (servidor)
        self.resultado = resultado  # la partida terminó: se compara la pantalla de resultados


def _poner(g, j, punto):
    """Al jugador `j` en un lugar libre junto a `punto`."""
    w, h = j.personaje.hitbox_w, j.personaje.hitbox_h
    x, y = g.mundo.punto_libre((int(punto[0]) - w // 2, int(punto[1]) - h // 2), w, h)
    j.personaje.hitbox.topleft = (int(x), int(y))
    j.personaje.sync_sprite_from_hitbox()


def _alien(g, tipo):
    return next((a for a in g.aliens if a.tipo == tipo), None)


def escenas(g, n):
    """Las escenas de la partida de `n` jugadores. `g` es el Game del servidor
    (en el cliente no se usa: solo importan los nombres y los `ver`)."""
    st = {}           # lo que una escena deja para la siguiente

    def J(i):
        return g.jugadores[i]

    def limpiar(apagon=True):
        m = g.mision
        for celda in m.celdas:
            if celda["preso"] is not None:
                preso = celda["preso"]
                celda["preso"], celda["fuga_ms"] = None, None
                m._sacar_de_celda(preso, celda)
        for j in g.jugadores:
            if j.escondido:
                j.salir_del_escondite()
            j.cerrar_panel()
            j.minijuego = None
            j.susto_ms = 0
            j.sin_linterna_ms = 0
            j.invulnerable_ms = 10 ** 6       # que ningún alien lo atrape solo
            j.pulso = 30.0
        if apagon and g.eventos is not None and g.eventos.apagon:
            g.eventos.restaurar_luz()
        if g.presentacion is not None and g.presentacion.abierta:
            g.presentacion.cerrar()
        g.tiempo_restante_ms = None

    def mitad_del_susto(*indices):
        def cada():
            for i in indices:
                j = J(i)
                if j.susto_total_ms:
                    j.susto_ms = j.susto_total_ms // 2
        return cada

    def susto(i, tipo, nombre_alien=None):
        def hacer():
            limpiar()
            alien = (next(a for a in g.aliens if a.nombre == nombre_alien) if nombre_alien
                     else _alien(g, tipo))
            J(i).invulnerable_ms = 0
            g._atrapar(J(i), alien)
        return hacer

    def ve_susto(i, tipo):
        return lambda e: e.jugadores[i].susto_tipo == tipo and e.jugadores[i].susto_ms > 0

    # -- La Sombra y el apagón --
    def apagon_caja():
        limpiar()
        g.eventos.lanzar("apagon")
        caja = g.eventos.caja
        _poner(g, J(0), (caja["rect"].centerx, caja["rect"].bottom + 70))
        caja["progreso"] = 0.4

    def sombra_aparece():
        limpiar(apagon=False)
        if not g.eventos.apagon:
            g.eventos.lanzar("apagon")
        sombra = g.sombra
        c = J(0).hitbox.center
        punto = (c[0] + 230, c[1] - 40)
        if g.mundo.colisiona_alien(pygame.Rect(punto[0] - 20, punto[1] - 20, 40, 40)):
            punto = (c[0] - 230, c[1] - 40)
        st["sombra"] = punto
        sombra.aparecer(punto)
        if sombra not in g.aliens:
            g.aliens.append(sombra)
        J(0).linterna.angulo = math.pi / 2          # mira para abajo: no la alumbra

    def sombra_quieta():
        sombra = g.sombra
        if sombra is not None and "sombra" in st:
            sombra.hitbox.center = st["sombra"]
            sombra.descanso_ms = 10 ** 6
            sombra.luz_ms = 0
        J(0).linterna.angulo = math.pi / 2

    def sombra_esfumada():
        sombra_quieta()
        g.sombra.esfumarse(4000)

    def susto_sombra():
        sombra_quieta()
        J(0).susto_ms = 0
        g._sombra_alcanza(J(0), g.sombra)

    # -- El Cambiaformas --
    def cf_disfrazado():
        limpiar()
        cf = g.cambiaformas
        _poner(g, J(0), cf.centro)
        _poner(g, J(0), (J(0).hitbox.centerx + 120, J(0).hitbox.centery))
        cf.burbuja, cf.burbuja_ms = "¿Me sacas de aquí?", 10 ** 6
        st["cf"] = cf.centro

    def cf_quieto():
        cf = g.cambiaformas
        if "cf" in st:
            cf.hitbox.center = st["cf"]
        cf.glitch_ms = 10 ** 6         # (el glitch del nombre es al azar)

    def cf_revela():
        cf_quieto()
        cf = g.cambiaformas
        cf.presa = J(0)
        cf._revelarse()
        cf.transformando_ms = 10 ** 6      # que siga parpadeando entre los dos

    def cf_revela_cada():
        cf_quieto()
        mitad_del_susto(0)()
        g.cambiaformas.transformando_ms = 450   # (en un cuadro "monstruo": 450 / 90 = 5, impar = prisionero)

    def cf_monstruo():
        limpiar()
        cf = g.cambiaformas
        cf.transformando_ms = 0
        cf.disfrazado = False

    # -- Puertas --
    def puerta_doble(uno_solo):
        def hacer():
            limpiar()
            p = g.puertas_dobles[0]
            p["abierta"], p["progreso"] = False, 0.0
            if p["rect"] not in g.mundo.puertas_alien:
                g.mundo.puertas_alien.append(p["rect"])
            _poner(g, J(0), p["paneles"][0].center)
            if not uno_solo:
                _poner(g, J(1), p["paneles"][1].center)
            else:
                _poner(g, J(1), (p["paneles"][0].centerx + 90, p["paneles"][0].centery))
        return hacer

    def compuerta():
        limpiar()
        g.eventos.lanzar("compuerta")
        c = g.eventos.compuerta
        if c is not None:
            r = c["rect"]
            _poner(g, J(0), (r.centerx + (130 if r.height > r.width else 0),
                             r.centery + (130 if r.width >= r.height else 0)))

    def junto_a_puerta_codigo():
        limpiar()
        p = g.mision.puertas[0]
        _poner(g, J(0), (p["rect"].left - 50, p["rect"].centery))
        J(0).personaje.direccion = "east"
        J(0).linterna.angulo = 0.0

    def panel_codigo():
        junto_a_puerta_codigo()
        g.mision._panel_codigo(J(0), 0)

    def codigo_malo():
        panel_codigo()
        panel = J(0).panel
        malo = next(i for i, c in enumerate(panel["codigos"]) if c != g.mision.puertas[0]["codigo"])
        J(0).cursor = malo
        g.confirmar(J(0))

    def puerta_abierta():
        junto_a_puerta_codigo()
        g.mision.abrir_puerta(J(0), 0)

    # -- Misión: consumibles, piezas, cápsula --
    def consumible(i, tipo):
        def hacer():
            limpiar()
            c = next((c for c in g.mision.consumibles if c["tipo"] == tipo), None)
            if c is None:
                return
            c["tomado"] = False
            _poner(g, J(i), c["rect"].center)
            g.mision.interactuar(J(i))
        return hacer

    def recoger_pieza():
        limpiar()
        if "Forjador" not in [j.rol for j in g.jugadores]:
            J(0).objetos.add("kit")
        quien = next((j for j in g.jugadores if j.rol == "Forjador"), J(0))
        st["forjador"] = g.jugadores.index(quien)
        pieza = next(p for p in g.piezas if not p["recogida"])
        _poner(g, quien, pieza["rect"].center)

    def capsula_entregar():
        limpiar()
        m = g.mision
        m.fase = "capsula"
        quien = g.jugadores[st.get("forjador", 0)]
        quien.piezas = max(quien.piezas, 2)
        _poner(g, quien, (m.capsula.centerx, m.capsula.bottom + 8))
        m.interactuar(quien)

    def capsula_reparar():
        limpiar()
        m = g.mision
        m.fase = "capsula"
        m.piezas_entregadas = 3
        g.nexus.planos = True
        quien = g.jugadores[st.get("forjador", 0)]
        if quien.rol != "Forjador":
            quien.objetos.add("kit")
        _poner(g, quien, (m.capsula.centerx, m.capsula.bottom + 8))

    def capsula_reparar_cada():
        if g.mision.reparacion > 0.5:
            g.mision.reparacion = 0.5          # que no termine (sería la huida)

    # -- Prisioneros --
    def npc_sigue():
        limpiar()
        npc = g.npcs.npcs[0]
        st["npc"] = npc.nodo
        g.nexus.grafo.datos[npc.nodo]["color"] = "verde"
        _poner(g, J(0), (npc.centro[0] + 40, npc.centro[1]))
        g.npcs.hablar(J(0))

    def npc_rescate():
        limpiar()
        m = g.mision
        npc = next((x for x in g.npcs.npcs if x.nodo == st.get("npc")), None)
        if npc is None:
            return
        _poner(g, J(0), (m.capsula.centerx + 160, m.capsula.bottom + 40))
        npc.hitbox.center = (m.capsula.centerx + 120, m.capsula.bottom + 40)

    # -- La Biosfera --
    def planta():
        limpiar()
        quien = next((j for j in g.jugadores if j.rol == "Biomante"), J(0))
        st["biomante"] = g.jugadores.index(quien)
        p = g.guardia_planta.planta
        p["progreso"], p["crecida"] = 0.0, False
        _poner(g, quien, (p["rect"].centerx, p["rect"].bottom + 30))

    def planta_cada():
        p = g.guardia_planta.planta
        if p["progreso"] > 0.6:
            p["progreso"] = 0.6

    def guardia_distraido():
        limpiar()
        guardia = g.guardia_planta.guardia
        guardia.comiendo, guardia.distraido_ms = False, 0
        quien = next((j for j in g.jugadores if j.rol == "Resonante"), None)
        if quien is None:
            guardia.distraer(10 ** 6, J(0))
            _poner(g, J(0), (guardia.centro[0], guardia.centro[1] + 200))
            return
        g.guardia_planta.recarga_ms.clear()
        _poner(g, quien, (guardia.centro[0], guardia.centro[1] + 200))
        g.guardia_planta.interactuar(quien)

    def guardia_come():
        limpiar()
        guardia = g.guardia_planta.guardia
        guardia.distraido_ms = 0
        J(0).objetos.add("fruta")
        _poner(g, J(0), (guardia.centro[0], guardia.centro[1] + 90))
        g.guardia_planta.interactuar(J(0))

    # -- El celular --
    def rumor():
        red = g.nexus
        r = next((p for p in red.rumores_activos() if p.lugar is not None), None)
        if r is None:
            r = red.lanzar_rumor()
        if r is None:
            r = next((p for p in red.rumores_activos()), None)
        st["rumor"] = r
        nodo = red.nodo_de(J(0))
        r.alcanzados.add(nodo)
        return r

    def celular_investigar():
        from redes import celular
        limpiar()
        r = rumor()
        celular.abrir(g, J(0))
        J(0).abrir_panel(celular._post(g, J(0), r))
        i = next(k for k, o in enumerate(J(0).panel["opciones"]) if o[1] == "investigar")
        J(0).cursor = i
        celular.confirmar(g, J(0))

    def celular_flecha():
        limpiar()
        r = st["rumor"]
        g.nexus.investigando[J(0)] = r
        lugar = r.lugar
        _poner(g, J(0), (lugar[0] - 700, lugar[1]))

    def celular_foto():
        limpiar()
        r = st["rumor"]
        _poner(g, J(0), r.lugar)

    def celular_ubicacion():
        from redes import celular
        limpiar()
        r = st["rumor"]
        if r not in g.nexus.evidencias[J(0)]:
            g.nexus.evidencias[J(0)].append(r)
        celular.abrir(g, J(0))
        J(0).abrir_panel(celular._post(g, J(0), r))
        i = next(k for k, o in enumerate(J(0).panel["opciones"]) if o[1] == "desmentir")
        J(0).cursor = i
        celular.confirmar(g, J(0))

    def celular_desmentido():
        from redes import celular
        J(0).cursor = 0                 # "Publicar la foto tal cual"
        celular.confirmar(g, J(0))

    def celular_feed_despues():
        from redes import celular
        J(0).cerrar_panel()
        celular.abrir(g, J(0))

    def celular_compartir():
        from redes import celular
        limpiar()
        red = g.nexus
        pub = next((p for p in red.publicaciones if p.autor != red.nodo_de(J(1))), None)
        if pub is None:
            red.publicar_normal()
            pub = red.publicaciones[-1]
        celular.abrir(g, J(1))
        J(1).abrir_panel(celular._post(g, J(1), pub))
        i = next((k for k, o in enumerate(J(1).panel["opciones"]) if o[1] == "compartir"), None)
        if i is not None:
            J(1).cursor = i
            celular.confirmar(g, J(1))

    def celular_rastrear():
        from redes import celular
        limpiar()
        red = g.nexus
        r = red.lanzar_rumor()
        if r is None:
            r = st["rumor"]
        r.alcanzados.add(red.nodo_de(J(1)))
        st["rumor2"] = r
        celular.abrir(g, J(1))
        J(1).abrir_panel(celular._post(g, J(1), r))
        i = next(k for k, o in enumerate(J(1).panel["opciones"]) if o[1] == "rastrear")
        J(1).cursor = i
        celular.confirmar(g, J(1))

    def celular_reportar():
        from redes import celular
        p = J(1).panel
        if p is None or p.get("vista") != "origen":
            return
        i = next((k for k, o in enumerate(p["opciones"]) if o[1] in ("reportar_origen", "reportar_suplantacion")), None)
        if i is not None:
            J(1).cursor = i
            celular.confirmar(g, J(1))

    def celular_red():
        from redes import celular
        J(1).cerrar_panel()
        celular.abrir(g, J(1))
        celular.cambiar_pestana(g, J(1), 2)

    # -- La Terminal NEXUS y el caso del infiltrado --
    def terminal_infiltrado():
        limpiar()
        zona = g.zonas[0]
        _poner(g, J(0), zona["rect"].center)
        g._abrir_nexus(J(0), zona)
        i = next(k for k, a in enumerate(J(0).panel["acciones"]) if a[0] == "infiltrado")
        J(0).cursor = i
        g.confirmar(J(0))

    def terminal_acusar():
        caso = g.infiltrado
        for tipo in ("prueba_audio", "prueba_expediente"):
            J(0).objetos.add(tipo)
        caso.subir(J(0))
        zona = g.zonas[0]
        J(0).abrir_panel(caso.panel_acusar(J(0)))
        J(0).panel["zona"] = zona

    # -- Habilidades --
    def habilidad(i, clave, usar=True):
        def hacer():
            from entidades import acciones_rol
            limpiar()
            j = J(i)
            if not j.arbol.tiene(clave):
                j.arbol.desbloquear(clave, 10 ** 6)
            j.recarga_ms = 0
            if clave == "FABRICACION":
                j.piezas = max(j.piezas, 1)
            if clave == "REGENERACION":
                otro = J((i + 1) % n)
                otro.pulso = 90.0
                _poner(g, j, (otro.hitbox.centerx + 60, otro.hitbox.centery))
            if usar:
                acciones_rol.usar_habilidad(g, j)
        return hacer

    def ve_habilidad(i, clave):
        return lambda e: e.jugadores[i].arbol.tiene(clave)

    # -- Avisos --
    def logro():
        limpiar()
        g.logros.avisos.clear()
        g.logros.conseguir("fantasma", J(0), esperar=False)

    def narrador():
        limpiar()
        g.decir("huida", forzar=True)

    def pulso_alto():
        limpiar()
        alien = _alien(g, "vigia")
        _poner(g, J(0), (alien.centro[0] + 160, alien.centro[1]))

    def pulso_cada():
        J(0).pulso = 96.0

    def cuenta_regresiva():
        limpiar()
        g.tiempo_restante_ms = 25000

    def vidas_bajan():
        limpiar()
        j = J(1)
        j.invulnerable_ms = 0
        g._atrapar(j, _alien(g, "vigia"))
        g._atrapar(j, _alien(g, "ciego"))      # (en la celda no lo atrapan: se llama directo)

    def eliminado():
        limpiar()
        j = J(n - 1)
        j.vidas = 1
        j.invulnerable_ms = 0
        g._atrapar(j, _alien(g, "cazador"))

    def derrota():
        limpiar()
        g.mision.resultado = "derrota"
        g.terminar_ronda()

    def victoria():
        from cliente_servidor.servidor import forzar_fase_final
        limpiar()
        for j in g.jugadores:
            if j.eliminado:
                j.eliminado, j.puede_moverse, j.vidas = False, True, 1
        forzar_fase_final(g)

    sustos = [
        Escena("susto_cazador", susto(0, "cazador"), mitad_del_susto(0), ve_susto(0, "cazador"),
               ("captura_cazador",)),
        Escena("susto_vigia", susto(1, "vigia"), mitad_del_susto(1), ve_susto(1, "vigia"),
               ("captura_vigia",)),
        Escena("susto_ciego", susto(0, "ciego"), mitad_del_susto(0), ve_susto(0, "ciego"),
               ("captura_ciego",)),
        Escena("susto_guardia", susto(1, "guardia"), mitad_del_susto(1), ve_susto(1, "alien"),
               ("captura",)),
        Escena("susto_cf_captura", susto(0, "cambiaformas"), mitad_del_susto(0),
               ve_susto(0, "cf_captura"), ("cf_captura",)),
    ]
    sombra = [
        Escena("apagon_caja", apagon_caja, None,
               lambda e: e.eventos.apagon and e.eventos.caja is not None
               and e.eventos.caja in e.eventos.cajas, ("apagon",)),
        Escena("sombra_ojos", sombra_aparece, sombra_quieta,
               lambda e: e.sombra in e.aliens),
        Escena("sombra_esfumada", None, sombra_esfumada,
               lambda e: e.sombra.oculta),
        Escena("susto_sombra", susto_sombra, lambda: (sombra_quieta(), mitad_del_susto(0)()),
               lambda e: ve_susto(0, "sombra")(e) and e.jugadores[0].sin_linterna_ms > 0,
               ("captura_sombra",)),
    ]
    cambiaformas = [
        Escena("cf_disfrazado", cf_disfrazado, cf_quieto,
               lambda e: e.cambiaformas.disfrazado and e.cambiaformas.burbuja_ms > 0),
        Escena("cf_revela", cf_revela, cf_revela_cada,
               lambda e: ve_susto(0, "cf_revela")(e) and not e.cambiaformas.disfrazado
               and e.jugadores[0].susto_disfraz is not None, ("cf_revela",)),
        Escena("cf_monstruo", cf_monstruo, cf_quieto,
               lambda e: not e.cambiaformas.disfrazado and e.cambiaformas.transformando_ms == 0),
    ]
    puertas = [
        Escena("puerta_doble_uno", puerta_doble(True), None,
               lambda e: e.puertas_dobles[0]["en_panel"][0] is e.jugadores[0], (),
               {0: {"interactuar"}}),
        Escena("puerta_doble_dos", puerta_doble(False), None,
               lambda e: e.puertas_dobles[0]["abierta"], ("puerta",),
               {0: {"interactuar"}, 1: {"interactuar"}}),
        Escena("compuerta", compuerta, None,
               lambda e: any(c["cerrada"] for c in e.compuertas), ("compuerta",)),
        Escena("panel_codigo", panel_codigo, None,
               lambda e: (e.jugadores[0].panel or {}).get("accion") == "codigo"),
        Escena("codigo_malo", codigo_malo, None,
               lambda e: "equivocado" in e.jugadores[0].mensaje, ("alarma",)),
        Escena("puerta_abierta", puerta_abierta, None,
               lambda e: e.mision.puertas[0]["abierta"]
               and e.mision.puertas[0]["rect"] not in e.mundo.paredes, ("puerta",)),
    ]
    mision = [
        Escena("kit", consumible(0, "kit"), None, lambda e: "kit" in e.jugadores[0].objetos,
               ("recoger",)),
        Escena("decodificador", consumible(1, "decodificador"), None,
               lambda e: "decodificador" in e.jugadores[1].objetos, ("recoger",)),
        Escena("abono", consumible(0, "abono"), None, lambda e: "abono" in e.jugadores[0].objetos,
               ("recoger",)),
        Escena("pieza", recoger_pieza, None,
               lambda e: any(j.piezas > 0 for j in e.jugadores), ("recoger",)),
        Escena("capsula_entregar", capsula_entregar, None,
               lambda e: e.mision.piezas_entregadas > 0, ("encajar",)),
        Escena("capsula_reparar", capsula_reparar, capsula_reparar_cada,
               lambda e: any(j.progreso for j in e.jugadores),
               (), {0: {"interactuar"}}),
    ]
    prisioneros = [
        Escena("npc_sigue", npc_sigue, None,
               lambda e: any(x.siguiendo is e.jugadores[0] for x in e.npcs.npcs)),
        Escena("npc_rescate", npc_rescate, None,
               lambda e: bool(e.npcs.rescatados), ("acierto",)),
    ]
    biosfera = [
        Escena("planta", planta, planta_cada,
               lambda e: e.guardia_planta.planta["progreso"] > 0, (),
               None),
        Escena("guardia_distraido", guardia_distraido, None,
               lambda e: e.guardia_planta.guardia.distraido),
        Escena("guardia_come", guardia_come, None,
               lambda e: e.guardia_planta.guardia.comiendo, ("encajar",)),
    ]
    celu = [
        Escena("cel_investigar", celular_investigar, None,
               lambda e: e.nexus.investigando.get(e.jugadores[0]) is not None),
        Escena("cel_flecha", celular_flecha, None,
               lambda e: e.nexus.investigando.get(e.jugadores[0]) is not None),
        Escena("cel_foto", celular_foto, None,
               lambda e: len(e.nexus.evidencias.get(e.jugadores[0], ())) > 0),
        Escena("cel_ubicacion", celular_ubicacion, None,
               lambda e: (e.jugadores[0].panel or {}).get("vista") == "ubicacion"),
        Escena("cel_desmentido", None, None,
               lambda e: (e.jugadores[0].panel or {}).get("vista") == "mensaje"),
        Escena("cel_feed_despues", celular_feed_despues, None,
               lambda e: len(e.nexus.evidencias.get(e.jugadores[0], ())) == 0),
        Escena("cel_compartir", celular_compartir, None,
               lambda e: (e.jugadores[1].panel or {}).get("vista") == "mensaje"),
        Escena("cel_rastrear", celular_rastrear, None,
               lambda e: (e.jugadores[1].panel or {}).get("vista") == "origen"),
        Escena("cel_reportar", celular_reportar, None,
               lambda e: (e.jugadores[1].panel or {}).get("vista") in ("mensaje", "origen")),
        Escena("cel_red", celular_red, None,
               lambda e: (e.jugadores[1].panel or {}).get("tipo") == "celular"),
    ]
    # (desmentir: el "tal cual" se confirma al empezar la escena siguiente a la del panel)
    celu[4].hacer = celular_desmentido
    terminal = [
        Escena("terminal_infiltrado", terminal_infiltrado, None,
               lambda e: (e.jugadores[0].panel or {}).get("accion") == "infiltrado_menu"),
        Escena("terminal_acusar", terminal_acusar, None,
               lambda e: (e.jugadores[0].panel or {}).get("accion") == "infiltrado_acusar"),
    ]
    avisos = [
        Escena("logro", logro, None,
               lambda e: bool(e.logros.avisos) and hasattr(e.logros.avisos[0][0], "nombre"),
               ("logro",)),
        Escena("narrador", narrador, None, lambda e: e.narrador.hablando, ("ia_voz",)),
        Escena("pulso_alto", pulso_alto, pulso_cada, lambda e: e.jugadores[0].pulso > 90),
        Escena("cuenta_regresiva", cuenta_regresiva, None,
               lambda e: e.tiempo_restante_ms is not None),
    ]
    habilidades = [
        Escena("hab_regeneracion", habilidad(0, "REGENERACION"), None, ve_habilidad(0, "REGENERACION")),
        Escena("hab_escaneo", habilidad(0, "ESCANEO"), None,
               lambda e: ve_habilidad(0, "ESCANEO")(e) and "escaneo" in e.jugadores[0].efectos),
        Escena("hab_senuelo", habilidad(1, "FABRICACION"), None,
               lambda e: ve_habilidad(1, "FABRICACION")(e) and len(e.senuelos) > 0, ("senal",)),
        Escena("hab_regeneracion", habilidad(2, "REGENERACION"), None, ve_habilidad(2, "REGENERACION")),
        Escena("hab_intercepcion", habilidad(3, "INTERCEPCION"), None,
               lambda e: ve_habilidad(3, "INTERCEPCION")(e) and "intercepcion" in e.jugadores[3].efectos),
    ]
    if n == 2:
        # La planta en 2 jugadores la hace crecer la Biomante (J1) manteniendo.
        biosfera[0].mantener = {0: {"interactuar"}}
        lista = (sustos + sombra + cambiaformas + puertas + [mision[0], mision[1]] + mision[3:]
                 + prisioneros + biosfera + celu + terminal + avisos + habilidades[:1]
                 + [Escena("victoria", victoria, None, lambda e: e.mision.resultado == "victoria",
                           ("victoria",), resultado=True)])
    elif n == 3:
        biosfera[0].mantener = {2: {"interactuar"}}
        lista = ([sustos[0], sustos[1]] + [sombra[0], sombra[1]] + [puertas[0], puertas[3]]
                 + [mision[3], mision[4], mision[5]] + biosfera[:1] + celu[:3] + avisos[:1]
                 + [Escena("vidas_bajan", vidas_bajan, None,
                           lambda e: e.jugadores[1].vidas < e.jugadores[1].vidas_max),
                    Escena("eliminado", eliminado, None, lambda e: e.jugadores[n - 1].eliminado,
                           ("eliminado",)),
                    Escena("derrota", derrota, None, lambda e: e.mision.resultado == "derrota",
                           ("derrota",), resultado=True)])
    else:
        lista = ([sustos[2], sustos[3]] + sombra[:2] + cambiaformas[:2] + [puertas[1]]
                 + [mision[3]] + prisioneros[:1] + biosfera[1:2] + celu[:1] + avisos[1:3]
                 + habilidades[1:]
                 + [Escena("eliminado", eliminado, None, lambda e: e.jugadores[n - 1].eliminado),
                    Escena("victoria", victoria, None, lambda e: e.mision.resultado == "victoria",
                           ("victoria",), resultado=True)])
    # La reparación: la mantiene el que tiene las piezas (el Forjador o J1 con el kit).
    forjador = next((i for i, r in enumerate(PARTIDAS[n][0]) if r == "Forjador"), 0)
    for e in lista:
        if e.nombre == "capsula_reparar":
            e.mantener = {forjador: {"interactuar"}}
    return lista


def congelar_relojes_del_susto():
    """Los sustos sacan su temblor y sus líneas de velocidad de
    pygame.time.get_ticks() (el reloj de CADA proceso): el sprite del Cazador
    saltaba ±12 px distinto en el servidor y en el cliente y la comparación
    daba 12 %. Para comparar, los dos dibujan el susto con el mismo reloj
    (en los dos procesos)."""
    from screens import partida
    from juego import ambiente
    original = ambiente.dibujar_susto

    def dibujar_susto(screen, vista, jugador):
        ticks = pygame.time.get_ticks
        pygame.time.get_ticks = lambda: 1000
        try:
            original(screen, vista, jugador)
        finally:
            pygame.time.get_ticks = ticks
    partida.dibujar_susto = dibujar_susto
    partida.temblor = lambda jugador, _tiempo_ms: ambiente.temblor(jugador, 1000)


# -- El servidor (otro proceso) ------------------------------------------------------------

def captura_local(g, dueños, resultado):
    """Lo que dibujaría el modo local (Game._dibujar) para esos jugadores."""
    sup = pygame.Surface(TAM)
    if resultado:
        from screens.resultados import render_resultados
        render_resultados(sup, g.jugadores, g.font, g.small_font, g.mision, g.equipo,
                          g.infiltrado, g.logros, getattr(g, "resultados_sel", 0), g.nexus,
                          g.cambiaformas, g.npcs, g.dificultad, g.tiempo_jugado_ms)
        return sup
    g._dibujar_partida_en(sup, dueños, g._extras_dibujo())
    if g.presentacion is None or not g.presentacion.abierta:
        from screens.logros import render_aviso_logro
        render_aviso_logro(sup, g.logros)
    return sup


def servidor(n):
    from cliente_servidor import servidor as S
    congelar_relojes_del_susto()
    roles, dificultad, laptops = PARTIDAS[n]
    carpeta = os.path.join(CARPETA, str(n))

    class Escenas(S.Servidor):
        base = None
        escenas = None
        hecho = -1
        capturado = -1

        def _escena(self):
            if self.base is None:
                return None, None, None
            k, resto = divmod(self.cuadro - self.base, PASO)
            if not 1 <= k <= len(self.escenas):
                return None, None, None
            return k, resto, self.escenas[k - 1]

        def _aplicar_entradas(self):
            g = self.juego
            if self.escenas is None:
                self.escenas = escenas(g, n)
            if self.base is None and all(b.ultimo_n >= 0 for b in self.buzones):
                # Las escenas empiezan cuando los clientes ya dibujan.
                self.base = self.cuadro
                with open(os.path.join(carpeta, "base.txt"), "w") as f:
                    f.write(str(self.cuadro))
            k, resto, escena = self._escena()
            if escena is not None:
                if k != self.hecho:
                    self.hecho = k
                    if escena.hacer is not None:
                        try:
                            escena.hacer()
                        except Exception:
                            import traceback
                            traceback.print_exc()
                    print(f"[escena] {k} {escena.nombre}", flush=True)
                for i, acciones in (escena.mantener or {}).items():
                    if i < len(self.buzones):
                        with self.buzones[i].candado:
                            self.buzones[i].mantener = set(self.buzones[i].mantener) | set(acciones)
            return super()._aplicar_entradas()

        def _mandar_instantanea(self, acks):
            k, resto, escena = self._escena()
            g = self.juego
            if escena is not None:
                if escena.cada is not None:
                    try:
                        escena.cada()
                    except Exception:
                        import traceback
                        traceback.print_exc()
                if resto >= CAPTURA and self.capturado != k:
                    self.capturado = k
                    desde = 0
                    for i, cuantos in enumerate(laptops):
                        dueños = g.jugadores[desde:desde + cuantos]
                        desde += cuantos
                        sup = captura_local(g, dueños, escena.resultado)
                        pygame.image.save(sup, os.path.join(
                            carpeta, f"local_{k:02d}_{escena.nombre}_L{i + 1}.png"))
            return super()._mandar_instantanea(acks)

    Escenas(n, "127.0.0.1", 0, roles, dificultad, None, 400, presentaciones=False,
            aliens_quietos=True, semilla=11, espera_s=5).correr()


# -- Los clientes (este proceso) -----------------------------------------------------------

def cliente(n):
    from cliente_servidor import cliente as C
    from juego.app import Game
    roles, dificultad, laptops = PARTIDAS[n]
    congelar_relojes_del_susto()
    carpeta = os.path.join(CARPETA, str(n))
    os.makedirs(carpeta, exist_ok=True)
    for viejo in os.listdir(carpeta):
        if viejo.endswith((".png", ".txt")):
            os.remove(os.path.join(carpeta, viejo))
    lista = escenas(None, n)
    proceso = subprocess.Popen([sys.executable, "-u", os.path.abspath(__file__), "--servidor", str(n)],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    salida = []
    limite = time.time() + 40
    puerto = None
    while time.time() < limite:
        linea = proceso.stdout.readline()
        if not linea:
            break
        salida.append(linea.rstrip())
        if "escuchando en" in linea:
            puerto = int(linea.split("escuchando en ")[1].split()[0].rsplit(":", 1)[1])
            break
    assert puerto, "el servidor no arrancó:\n" + "\n".join(salida)
    threading.Thread(target=lambda: [salida.append(l.rstrip()) for l in proceso.stdout], daemon=True).start()
    problemas = []
    try:
        sesiones = []
        for cuantos in laptops:
            s = C.Sesion(Game(), "127.0.0.1", puerto, C.esquemas_para(cuantos), avisar=lambda t: None)
            s.conectar()
            s.entrada.sacar = (lambda c=cuantos: [(set(), [])] * c)
            sesiones.append(s)
        for s in sesiones:
            s.preparar_espejo()
            assert s.espejo.listo, s.espejo.error
        # Los sonidos que le llegan a cada espejo, por escena.
        oidos = {}
        for i, s in enumerate(sesiones):
            sonar = s.espejo.sonar

            def anotar(sonidos, i=i, sonar=sonar, s=s):
                k = getattr(s, "_escena_k", None)
                for nombre, _vol in sonidos or ():
                    oidos.setdefault(k, set()).add(nombre)
                return sonar(sonidos)
            s.espejo.sonar = anotar
        pantallas = [pygame.Surface(TAM) for _ in sesiones]
        total = len(lista)
        guardadas = set()
        vistos = set()
        errores = {}                 # escena -> errores nuevos del espejo
        fin = time.time() + PASO * (total + 2) / 60 + 40
        base = None
        while time.time() < fin and len(guardadas) < len(sesiones) * total:
            if base is None and os.path.exists(os.path.join(carpeta, "base.txt")):
                with open(os.path.join(carpeta, "base.txt")) as f:
                    texto = f.read().strip()
                base = int(texto) if texto else None
            for i, s in enumerate(sesiones):
                antes = dict(s.errores_vistos)
                if base is not None:
                    # (los sonidos se sacan al dibujar: van con la escena de
                    # la última instantánea que llegó)
                    ultimo = max((c.cuadro or 0) for c in s.conexiones)
                    s._escena_k = (ultimo - base) // PASO
                if not s.paso(pantallas[i], eventos=[]):
                    time.sleep(1.5)
                    print("\n".join(salida[-80:]))
                    raise AssertionError(f"la laptop {i + 1} terminó: {s.motivo}")
                if base is None:
                    continue
                k, resto = divmod((s.conexiones[0].cuadro or 0) - base, PASO)
                if s.errores_vistos != antes:
                    nuevos = {f for f in s.errores_vistos if f not in antes}
                    errores.setdefault(k, set()).update(nuevos)
                if not 1 <= k <= total:
                    continue
                escena = lista[k - 1]
                if escena.ver is not None and resto >= VER_DESDE and k not in vistos:
                    try:
                        if escena.ver(s.espejo.g):
                            vistos.add(k)
                    except Exception as error:
                        errores.setdefault(k, set()).add(f"ver: {error!r}")
                if resto >= CAPTURA + 3 and (k, i) not in guardadas:
                    guardadas.add((k, i))
                    pygame.image.save(pantallas[i], os.path.join(carpeta, f"red_{k:02d}_L{i + 1}.png"))
            time.sleep(1 / 60)
        for k, escena in enumerate(lista, start=1):
            if escena.ver is not None and k not in vistos:
                problemas.append(f"{escena.nombre}: el estado no le llegó al espejo")
            faltan = [s for s in escena.sonidos if s not in oidos.get(k, set())]
            if faltan:
                problemas.append(f"{escena.nombre}: no llegaron los sonidos {faltan}")
            if errores.get(k):
                problemas.append(f"{escena.nombre}: el espejo falló {sorted(errores[k])}")
        for i, s in enumerate(sesiones):
            if not all(c.reconexiones == 0 and c.situacion == "jugando" for c in s.conexiones):
                problemas.append(f"laptop {i + 1} se desconectó: "
                                 f"{[(c.situacion, c.reconexiones) for c in s.conexiones]}")
        for s in sesiones:
            s.cerrar()
    finally:
        proceso.kill()
        proceso.wait(5)
    rotas = [l for l in salida if "Traceback" in l or "Error" in l]
    if rotas:
        print("\n".join(salida[-60:]))
        problemas.append("el servidor tuvo errores (arriba)")
    problemas += comparar(n, lista, len(sesiones))
    return problemas


def comparar(n, lista, laptops):
    import numpy as np
    carpeta = os.path.join(CARPETA, str(n))
    problemas = []
    peor = 0.0
    for k, escena in enumerate(lista, start=1):
        for i in range(laptops):
            local = os.path.join(carpeta, f"local_{k:02d}_{escena.nombre}_L{i + 1}.png")
            red = os.path.join(carpeta, f"red_{k:02d}_L{i + 1}.png")
            if not os.path.exists(local) or not os.path.exists(red):
                problemas.append(f"{escena.nombre} L{i + 1}: falta una captura")
                continue
            a = pygame.surfarray.array3d(pygame.image.load(local)).astype(int)
            b = pygame.surfarray.array3d(pygame.image.load(red)).astype(int)
            if escena.resultado:
                # El cliente pone arriba "Partida en red terminada: Enter..."
                # (en local no hay red): esa franja no cuenta.
                a[:, :50], b[:, :50] = 0, 0
            distinto = float((np.abs(a - b).max(axis=2) > 40).mean() * 100)
            peor = max(peor, distinto)
            marca = "  <-- MIRAR" if distinto > 2 else ""
            print(f"  [{n}J] {k:02d} {escena.nombre + ' L' + str(i + 1):26s} {distinto:5.1f} % distinto{marca}")
            if distinto >= LIMITE:
                problemas.append(f"{escena.nombre} L{i + 1}: {distinto:.1f} % distinto del local")
    print(f"[{n} jugadores] peor {peor:.1f} %")
    return problemas


if __name__ == "__main__":
    if "--servidor" in sys.argv:
        servidor(int(sys.argv[sys.argv.index("--servidor") + 1]))
    else:
        pygame.init()
        cantidades = [int(a) for a in sys.argv[1:] if a.isdigit()] or [2, 3, 4]
        todos = []
        for n in cantidades:
            todos += [f"[{n}J] {p}" for p in cliente(n)]
        if todos:
            print("PROBLEMAS:\n  " + "\n  ".join(todos))
            sys.exit(1)
        print("OK prueba_red_escenas_mas")
