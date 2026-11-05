"""El modo en red en las situaciones que lo rompían, comparado con el local.

    python pruebas/prueba_red_escenas.py

Un servidor de verdad (otro proceso, este mismo archivo con --servidor) va
pasando por escenas: celular (inicio, otra pestaña, una publicación, de dónde
salió), árbol de habilidades, Terminal NEXUS, Emisión, escondite con un alien
revisándolo, prisión, apagón, alarma, la ventana que presenta un alien,
eliminado y victoria. En cada una guarda lo que dibujaría el modo local para
J1 y J2, y dos clientes (uno por jugador, como dos laptops) guardan lo que
dibujan ellos. La prueba pide:

- que el espejo no falle en ninguna (antes: la presentación de un alien
  -> KeyError 'jugador' y todo pasaba al dibujo sencillo, "el alien era un
  punto rojo"; una publicación del celular -> llegaba como None);
- que los dos se vean casi igual al modo local (menos de 6 % de píxeles
  distintos: hay animaciones con el reloj y la interpolación va 50 ms atrás);
- que nadie se desconecte;
- que el minijuego del escondite le aparezca al cliente y que los prisioneros
  (NPC) caminen con su animación.

Tarda ~1 minuto. Las capturas van a la carpeta temporal (o NEXUS_CAPTURAS).
"""

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
CAPTURA = 110          # en qué cuadro de la escena se guarda la imagen
TAM = (1280, 720)
CARPETA = os.environ.get("NEXUS_CAPTURAS") or os.path.join(tempfile.gettempdir(), "nexus_red_escenas")
os.makedirs(CARPETA, exist_ok=True)


def escenas(g, forzar_fase_final):
    from redes import celular
    from entidades import acciones_rol
    j1, j2 = g.jugadores[0], g.jugadores[1]

    def limpiar():
        for j in g.jugadores:
            if j.preso is not None:
                g.mision.liberar(j.preso, j1 if j is not j1 else j2)
            if j.escondido:
                j.salir_del_escondite()
            j.cerrar_panel()

    def celular_inicio():
        limpiar()
        celular.abrir(g, j1)

    def celular_pestana():
        celular_inicio()
        celular.cambiar_pestana(g, j1, 1)

    def celular_publicacion():
        celular_inicio()
        pubs = [p for p in g.nexus.publicaciones] or [None]
        if pubs[0] is not None:
            j1.abrir_panel(celular._post(g, j1, pubs[-1]))

    def celular_origen():
        celular_inicio()
        rumores = [p for p in g.nexus.publicaciones if p.tipo == "rumor"]
        if rumores:
            j1.abrir_panel(celular._post(g, j1, rumores[0]))
            i = next((k for k, o in enumerate(j1.panel["opciones"]) if o[1] == "rastrear"), None)
            if i is not None:
                j1.cursor = i
                celular.confirmar(g, j1)

    def escondite():
        limpiar()
        e = g.escondites[0]
        j1.personaje.hitbox.center = e["rect"].center
        j1.personaje.sync_sprite_from_hitbox()
        j1.esconderse(e)
        alien = g.aliens[0]
        alien.escondite_objetivo = e           # (si no, el minijuego se corta: "se fue")
        alien.hitbox.center = (e["rect"].centerx + 60, e["rect"].centery)
        g._alien_revisa(j1, alien, e)

    def presentacion():
        limpiar()
        if g.presentacion is not None:
            a = next((a for a in g.aliens if a.tipo not in g.presentacion.presentados), g.aliens[0])
            g.presentacion.abrir(j1, a)

    def eliminado():
        limpiar()
        j2.vidas, j2.eliminado, j2.puede_moverse = 0, True, False

    return [
        ("celular_inicio", celular_inicio), ("celular_pestana", celular_pestana),
        ("celular_publicacion", celular_publicacion), ("celular_origen", celular_origen),
        ("habilidades", lambda: (limpiar(), g.alternar_habilidades(j2))),
        ("terminal", lambda: (limpiar(), j1.abrir_panel(celular.panel_ayuda(g, j1, None)))),
        ("emision", lambda: (limpiar(), acciones_rol.abrir_emision(g, j2))),
        ("escondite", escondite),
        ("prision", lambda: (limpiar(), g._atrapar(j2, g.aliens[1]))),
        ("apagon", lambda: (limpiar(), g.eventos.lanzar("apagon"))),
        ("alarma", lambda: g.eventos.lanzar("alarma")),
        ("presentacion", presentacion),
        ("eliminado", eliminado),
        ("victoria", lambda: forzar_fase_final(g)),
    ]


def servidor():
    """El lado del servidor (otro proceso): recorre las escenas y guarda el dibujo local."""
    from cliente_servidor import servidor as S

    class Escenas(S.Servidor):
        def bucle(self):
            g = self.juego
            lista = escenas(g, S.forzar_fase_final)
            actualizar = g._actualizar_partida

            base = []

            def con_escenas(dt):
                actualizar(dt)
                if not base:
                    # Las escenas empiezan cuando los dos clientes ya dibujan
                    # (ya mandaron su primera intención): armar el espejo tarda.
                    if all(b.ultimo_n >= 0 for b in self.buzones):
                        base.append(self.cuadro)
                        with open(os.path.join(CARPETA, "base.txt"), "w") as f:
                            f.write(str(self.cuadro))
                    return
                k, resto = divmod(self.cuadro - base[0], PASO)
                if not 1 <= k <= len(lista):
                    return
                nombre, hacer = lista[k - 1]
                if resto == 0:
                    hacer()
                    print(f"[escena] {nombre}", flush=True)
                elif resto == CAPTURA:
                    for i in (0, 1):
                        sup = pygame.Surface(TAM)
                        g._dibujar_partida_en(sup, [g.jugadores[i]], g._extras_dibujo())
                        pygame.image.save(sup, os.path.join(CARPETA, f"local_{k:02d}_{nombre}_J{i + 1}.png"))
            g._actualizar_partida = con_escenas
            super().bucle()

    segundos = 180          # (de sobra: se apaga solo cuando los clientes se van)
    Escenas(2, "127.0.0.1", 0, ["Biomante", "Resonante"], "facil", None, segundos,
            aliens_quietos=True, semilla=11, espera_s=5).correr()


def cliente():
    from cliente_servidor import cliente as C
    from juego.app import Game
    proceso = subprocess.Popen([sys.executable, "-u", os.path.abspath(__file__), "--servidor"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    salida = []
    limite = time.time() + 30
    puerto = None
    while time.time() < limite:
        linea = proceso.stdout.readline()
        if not linea:
            break
        if "escuchando en" in linea:
            puerto = int(linea.split("escuchando en ")[1].split()[0].rsplit(":", 1)[1])
            break
    assert puerto, "el servidor no arrancó"
    threading.Thread(target=lambda: [salida.append(l.rstrip()) for l in proceso.stdout], daemon=True).start()
    try:
        sesiones = []
        for _ in range(2):
            s = C.Sesion(Game(), "127.0.0.1", puerto, C.esquemas_para(1), avisar=lambda t: None)
            s.conectar()
            s.entrada.sacar = lambda: [(set(), [])]
            sesiones.append(s)
        for s in sesiones:
            s.preparar_espejo()
            assert s.espejo.listo, s.espejo.error
        pantallas = [pygame.Surface(TAM) for _ in sesiones]
        n = 14
        guardadas = set()
        fin = time.time() + PASO * (n + 2) / 60 + 20
        base = None
        vio_minijuego = npc_camina = False
        relojes_npc = set()
        while time.time() < fin and len(guardadas) < 2 * n:
            if base is None and os.path.exists(os.path.join(CARPETA, "base.txt")):
                with open(os.path.join(CARPETA, "base.txt")) as f:
                    texto = f.read().strip()
                base = int(texto) if texto else None
            for i, s in enumerate(sesiones):
                assert s.paso(pantallas[i], eventos=[]), f"la sesión {i} terminó: {s.motivo}"
                if base is None:
                    continue
                k, resto = divmod((s.conexiones[0].cuadro or 0) - base, PASO)
                espejo = s.espejo.g
                if getattr(espejo.jugadores[0], "minijuego", None) is not None:
                    vio_minijuego = True
                for npc in getattr(espejo.npcs, "npcs", [])[:3]:
                    npc_camina = npc_camina or npc.apariencia.moviendose
                    relojes_npc.add(int(npc.apariencia.reloj_ms) // 100)
                if 1 <= k <= n and resto >= CAPTURA + 3 and (k, i) not in guardadas:
                    guardadas.add((k, i))
                    pygame.image.save(pantallas[i], os.path.join(CARPETA, f"red_{k:02d}_J{i + 1}.png"))
            time.sleep(1 / 60)
        # El minijuego del escondite le llega al cliente (antes el objeto no
        # viajaba) y los prisioneros se animan (antes caminaban "congelados").
        assert vio_minijuego, "el cliente nunca vio el minijuego del escondite"
        assert npc_camina and len(relojes_npc) > 5, "los prisioneros del cliente no se animan"
        for i, s in enumerate(sesiones):
            assert not s.errores_vistos, f"el espejo de J{i + 1} falló: {s.errores_vistos}"
            assert all(c.reconexiones == 0 and c.situacion == "jugando" for c in s.conexiones), \
                f"J{i + 1} se desconectó: {[(c.situacion, c.reconexiones) for c in s.conexiones]}"
        for s in sesiones:
            s.cerrar()
    finally:
        proceso.kill()              # (SDL se queda con SIGTERM: no lo apagaría)
        proceso.wait(5)
    print("\n".join(l for l in salida if "Traceback" in l or "Error" in l))
    comparar()


def comparar():
    import numpy as np
    peor = 0.0
    locales = sorted(f for f in os.listdir(CARPETA) if f.startswith("local_"))
    assert len(locales) == 28, f"faltan capturas del servidor ({len(locales)})"
    for nombre in locales:
        k, jug = nombre.split("_")[1], nombre.rsplit("_", 1)[1]
        red = os.path.join(CARPETA, f"red_{k}_{jug}")
        assert os.path.exists(red), f"falta la captura del cliente {red}"
        a = pygame.surfarray.array3d(pygame.image.load(os.path.join(CARPETA, nombre))).astype(int)
        b = pygame.surfarray.array3d(pygame.image.load(red)).astype(int)
        distinto = float((np.abs(a - b).max(axis=2) > 40).mean() * 100)
        peor = max(peor, distinto)
        print(f"  {nombre[9:-4]:28s} {distinto:5.1f} % distinto")
        assert distinto < 6, f"{nombre}: el cliente se ve distinto al modo local ({distinto:.1f} %)"
    print(f"escenas en red iguales al modo local (peor {peor:.1f} %): OK")


if __name__ == "__main__":
    if "--servidor" in sys.argv:
        servidor()
    else:
        for viejo in os.listdir(CARPETA):
            if viejo.endswith((".png", ".txt")):
                os.remove(os.path.join(CARPETA, viejo))
        pygame.init()
        cliente()
        print("OK prueba_red_escenas")
