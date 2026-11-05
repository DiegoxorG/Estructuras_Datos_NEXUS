"""F3 (segundo toque): además del FPS, caza los tirones.

F3 una vez muestra solo el FPS (lo que de verdad va el juego); otra vez,
además se perfila cada cuadro con cProfile (de que empieza el cuadro
hasta el flip, eventos incluidos). Si uno tarda más de UMBRAL_MS, se anota en
Guardado/tirones.txt qué funciones se comieron el tiempo y qué estaba pasando
en ese momento: fase de la misión, quién está preso, qué puertas están
abiertas, los últimos sonidos, el cartel de la IA, el evento, cuántos aliens
hay cerca de cada jugador...

Sirve para encontrar tirones que en otro computador no salen: el perfil dice
la causa en el PC donde pasa. Perfilar hace todo un poco más lento (las
funciones de Python ~1.5 veces), así que es solo para buscar el problema:
para ver los FPS reales, el primer toque. Apagado no cuesta nada.
"""

import cProfile
import io
import math
import os
import pstats
import statistics
import time
from collections import deque


UMBRAL_MS = 40
# Un tirón es un cuadro que se sale de lo normal: más de UMBRAL_MS Y más de
# VECES_LO_NORMAL la mediana de los últimos cuadros. Si el juego va
# parejo a 45 ms (4 vistas y dos pantallas en un PC lento), eso es carga, no
# tirones: antes cada uno se anotaba (80 en un minuto) y escondía los de
# verdad. La carga se ve en "cuadro típico" (F3) y en el resumen del archivo.
VECES_LO_NORMAL = 1.6
ARCHIVO = os.path.join("Guardado", "tirones.txt")
FUNCIONES = 18          # cuántas funciones se anotan por tirón
CERCA_PX = 900          # "alien cerca" de un jugador, para el contexto


class Diagnostico:
    def __init__(self):
        self.perfil = None
        self.inicio = 0.0
        self.tirones = 0
        self.lentos = 0             # cuadros > UMBRAL_MS pero parejos con los demás (carga)
        self.recientes = deque(maxlen=120)
        self._encabezado = False

    @property
    def tipico(self):
        """Mediana de los últimos cuadros (ms), o 0 si todavía no hay."""
        return statistics.median(self.recientes) if self.recientes else 0.0

    def empezar(self):
        """Al principio del cuadro (solo con F3 prendido)."""
        self.perfil = cProfile.Profile()
        self.inicio = time.perf_counter()
        self.perfil.enable()

    def terminar(self, juego, partes):
        """Después del flip. `partes`: ms de eventos, actualizar, dibujar y flip."""
        if self.perfil is None:
            return
        self.perfil.disable()
        perfil, self.perfil = self.perfil, None
        total = (time.perf_counter() - self.inicio) * 1000
        tipico = self.tipico
        self.recientes.append(total)
        if total < UMBRAL_MS:
            return
        if len(self.recientes) >= 30 and total < tipico * VECES_LO_NORMAL:
            self.lentos += 1
            return
        self.tirones += 1
        resumen = "  ".join(f"{k} {v:.0f}" for k, v in partes.items())
        texto = io.StringIO()
        pstats.Stats(perfil, stream=texto).sort_stats("tottime").print_stats(FUNCIONES)
        funciones = _limpiar(texto.getvalue())
        contexto = _contexto(juego)
        print(f"[TIRÓN] {total:.0f} ms ({resumen})  {contexto[0] if contexto else ''}")
        try:
            os.makedirs(os.path.dirname(ARCHIVO), exist_ok=True)
            with open(ARCHIVO, "a", encoding="utf-8") as f:
                if not self._encabezado:
                    import pygame
                    segunda = getattr(juego, "segunda", None)
                    otra = f", otra pantalla {segunda.ancho}x{segunda.alto}" if segunda is not None else ""
                    sabor = "pygame-ce" if getattr(pygame, "IS_CE", False) else "pygame"
                    f.write(f"\n##### Sesión {time.strftime('%Y-%m-%d %H:%M:%S')} "
                            f"({juego.ancho}x{juego.alto}{otra}, {len(getattr(juego, 'jugadores', []))} jugadores, "
                            f"{sabor} {pygame.version.ver})\n")
                    self._encabezado = True
                f.write(f"\n=== Tirón #{self.tirones}: {total:.0f} ms, lo normal {tipico:.0f} ms  ({resumen})  "
                        f"pantalla {juego.current_screen}\n")
                for linea in contexto:
                    f.write(f"  {linea}\n")
                f.write(funciones)
        except OSError:
            pass


def _limpiar(texto):
    """Solo la tabla de funciones, con las rutas cortas."""
    lineas = []
    tabla = False
    for linea in texto.splitlines():
        if "ncalls" in linea:
            tabla = True
        if tabla and linea.strip():
            lineas.append("    " + linea.replace(os.getcwd() + os.sep, "").replace(os.getcwd() + "/", ""))
    return "\n".join(lineas) + "\n"


def _contexto(juego):
    """Lo que estaba pasando: una línea por cosa."""
    lineas = []
    try:
        mision = getattr(juego, "mision", None)
        jugadores = getattr(juego, "jugadores", [])
        if mision is not None:
            presos = [j.rol for j in jugadores if getattr(j, "preso", None) is not None]
            abiertas = [p["nombre"] for p in getattr(mision, "puertas", ()) if p.get("abierta")]
            lineas.append(f"fase {mision.fase}  ·  presos {presos or '-'}  ·  puertas abiertas {abiertas or '-'}")
        aliens = getattr(juego, "aliens", [])
        cerca = []
        for j in jugadores:
            cx, cy = j.hitbox.center
            n = sum(1 for a in aliens if math.hypot(a.centro[0] - cx, a.centro[1] - cy) < CERCA_PX)
            cerca.append(f"{j.rol} {n}")
        if aliens:
            acciones = {}
            for a in aliens:
                acciones[a.accion] = acciones.get(a.accion, 0) + 1
            lineas.append(f"aliens {len(aliens)} {acciones}  ·  cerca de cada uno: {', '.join(cerca)}")
        sonidos = getattr(getattr(juego, "ambiente", None), "ultimos", [])
        if sonidos:
            lineas.append(f"últimos sonidos: {[n for n, _ in sonidos[-6:]]}")
        narrador = getattr(juego, "narrador", None)
        if narrador is not None and getattr(narrador, "hablando", False):
            lineas.append(f"IA: {narrador.texto[:70]}")
        eventos = getattr(juego, "eventos", None)
        if eventos is not None and eventos.texto():
            lineas.append(f"evento: {eventos.texto()}")
        otros = []
        if getattr(juego, "pausa", None) is not None:
            otros.append("pausa")
        presentacion = getattr(juego, "presentacion", None)
        if presentacion is not None and getattr(presentacion, "abierta", False):
            otros.append("presentación de alien")
        if any(getattr(j, "susto_tipo", None) and getattr(j, "susto_ms", 0) > 0 for j in jugadores):
            otros.append("susto")
        if any(j.panel is not None for j in jugadores):
            otros.append("panel abierto: " + ", ".join(str(j.panel.get("tipo")) for j in jugadores
                                                         if j.panel is not None))
        if otros:
            lineas.append("  ·  ".join(otros))
    except Exception as error:      # el diagnóstico nunca debe tumbar el juego
        lineas.append(f"(no se pudo leer el contexto: {error})")
    return lineas
