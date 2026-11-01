"""El caso del Cambiaformas (antes "El Infiltrado", idea de Joseph). Es opcional.

Los sospechosos son prisioneros que caminan por la nave (npcs.py); el culpable
es la identidad que usa el Cambiaformas (cambiaformas.py). Exponerlo lo deja
sin poder disfrazarse un rato. (El nombre del archivo quedó de antes.)


Es todo lo que hay en NEXUS, la red social de la nave: las Terminales NEXUS
abren este caso (sospechosos, subir pruebas y acusar).

Uno de los que escriben en NEXUS es un alien cambiaformas haciéndose pasar por
un prisionero. Por la nave hay tres pruebas (audio, expediente y captura de
cámara). Cada una revela un rasgo del infiltrado; al subirla a NEXUS desde una
terminal, la red descarta a los sospechosos que no lo tienen. Con las tres
arriba queda expuesto ante todos y los aliens se quedan confundidos un rato.

Se puede acusar antes, con una o dos pruebas subidas, pero si se equivocan el
caso se cierra para siempre y la nave delata al que acusó: los aliens van por él.

Los datos (cuentas, rasgos, textos y puntos) están en data/infiltrado.py; el
dibujo de las pruebas en el mapa, en screens/infiltrado_dibujo.py.
"""

import itertools
import math
import random

import pygame

from misiones.logros import logro
from data.infiltrado import (CUENTAS, RASGOS, PRUEBAS, SOSPECHOSOS_POR_PARTIDA,
                             PUNTOS_SUBIR_PRUEBA, PUNTOS_EXPONER, PUNTOS_ACUSACION_FALSA,
                             CONFUSION_MS)

TAMANO_PRUEBA = (30, 30)
DISTANCIA_RECOGER = 22
COLOR_BIEN = (120, 230, 150)
COLOR_MAL = (245, 130, 120)
COLOR_CASO = (233, 120, 200)


def nombre_prueba(tipo, plural=False):
    return PRUEBAS[tipo]["nombre"][1 if plural else 0]


class CasoInfiltrado:
    def __init__(self, juego, objetos, rng=None, cuentas=None):
        """`cuentas`: los nombres de los prisioneros que caminan por la nave
        (npcs.py); de ahí salen los sospechosos. Sin eso, los de data/infiltrado.py."""
        self.juego = juego
        self.rng = rng or random.Random()
        self.estado = "abierto"          # "expuesto" o "fallido" cuando se cierra
        self.iniciado = False            # alguien ya encontró una prueba
        self.subidas = []                # tipos de prueba ya subidos a NEXUS
        self.acusado = None              # a quién acusaron (si acusaron)
        self.pruebas = []                # {"rect", "tipo", "tomada"} en el mapa

        cuentas = list(cuentas or CUENTAS)
        cuantos = min(SOSPECHOSOS_POR_PARTIDA, len(cuentas))
        nombres = self.rng.sample(cuentas, cuantos)
        claves = list(RASGOS)
        combinaciones = self.rng.sample(list(itertools.product(range(2), repeat=len(claves))),
                                        cuantos)
        self.sospechosos = [
            {"nombre": nombre,
             "rasgos": {clave: RASGOS[clave][valor] for clave, valor in zip(claves, combo)}}
            for nombre, combo in zip(nombres, combinaciones)
        ]
        self.infiltrado = self.rng.choice(self.sospechosos)
        self._colocar(objetos.get("pruebas") or [])

    # -- Montaje ------------------------------------------------------------------------

    def _colocar(self, puntos):
        """Escoge 3 de los puntos que puso el editor de mapa y les reparte las
        tres pruebas en orden al azar. Con menos de 3 puntos no hay caso."""
        if len(puntos) < len(PRUEBAS):
            return
        mundo = self.juego.mundo
        elegidos = self.rng.sample(list(puntos), len(PRUEBAS))
        tipos = list(PRUEBAS)
        self.rng.shuffle(tipos)
        for (rx, ry), tipo in zip(elegidos, tipos):
            centro = (int(rx * mundo.ancho), int(ry * mundo.alto))
            self.pruebas.append({"rect": _rect(centro), "tipo": tipo, "tomada": False})

    @property
    def activo(self):
        """Hay caso en este mapa y todavía no se cerró."""
        return bool(self.pruebas) and self.estado == "abierto"

    # -- Deducción ----------------------------------------------------------------------

    def valor(self, tipo):
        """El rasgo del infiltrado que revela esa prueba ("Bodega", "de noche"...)."""
        return self.infiltrado["rasgos"][PRUEBAS[tipo]["rasgo"]]

    def texto_prueba(self, tipo):
        return PRUEBAS[tipo]["texto"].format(valor=self.valor(tipo))

    def descartado(self, sospechoso):
        """True si alguna prueba ya subida no le cuadra."""
        return any(sospechoso["rasgos"][PRUEBAS[t]["rasgo"]] != self.valor(t) for t in self.subidas)

    def restantes(self):
        return [s for s in self.sospechosos if not self.descartado(s)]

    def lineas_sospechosos(self):
        lineas = []
        for s in self.sospechosos:
            r = s["rasgos"]
            if self.descartado(s):
                lineas.append(f"  x {s['nombre']}: descartado")
            else:
                lineas.append(f"  - {s['nombre']}: {r['sector']}, {r['turno']}, {r['lentes']}")
        return lineas

    # -- En el mapa ---------------------------------------------------------------------

    def _cerca(self, jugador, prueba):
        return prueba["rect"].inflate(DISTANCIA_RECOGER * 2, DISTANCIA_RECOGER * 2).colliderect(
            jugador.hitbox)

    def prueba_cerca(self, jugador):
        if not self.activo or jugador.preso or jugador.eliminado:
            return None
        return next((p for p in self.pruebas if not p["tomada"] and self._cerca(jugador, p)), None)

    def pista(self, jugador):
        prueba = self.prueba_cerca(jugador)
        return f"Recoger: {nombre_prueba(prueba['tipo']).lower()}" if prueba else None

    def interactuar(self, jugador):
        """Recoge la prueba que tenga cerca. True si se encargó de la tecla."""
        prueba = self.prueba_cerca(jugador)
        if prueba is None:
            return False
        prueba["tomada"] = True
        jugador.objetos.add(prueba["tipo"])
        self._sonar("recoger", 0.7)
        primera = not self.iniciado
        self.iniciado = True
        logro(self.juego, "algo_no_cuadra", jugador)
        jugador.abrir_panel({
            "tipo": "aviso",
            "titulo": f"Prueba: {nombre_prueba(prueba['tipo'])}",
            "cuerpo": [self.texto_prueba(prueba["tipo"]), "",
                       "Uno de los prisioneros no es quien dice ser. Sube esta prueba desde "
                       "una Terminal NEXUS para que la red la vea."],
            "pie": f"[{jugador.nombre_tecla('interactuar')}] guardar",
        })
        if primera:
            for otro in self.juego.jugadores:
                if otro is not jugador:
                    otro.avisar("¡El Cambiaformas anda entre los prisioneros!", COLOR_CASO)
            self._decir("prueba", jugador.rol)
        return True

    # -- En la terminal NEXUS --------------------------------------------------------------

    def pruebas_de(self, jugador):
        return [t for t in PRUEBAS if t in jugador.objetos and t not in self.subidas]

    def panel_terminal(self, jugador, zona):
        """Lo que muestra una Terminal NEXUS: el caso abierto (sospechosos,
        subir pruebas, acusar) o, si ya se cerró, cómo terminó."""
        pie_salir = f"[{jugador.nombre_tecla('interactuar')}] salir"
        if not self.pruebas:
            return {"tipo": "aviso", "titulo": "NEXUS", "nexus_terminal": True,
                    "cuerpo": ["La red está tranquila. Demasiado tranquila."], "pie": pie_salir}
        if not self.activo:
            nombre = self.infiltrado["nombre"]
            cuerpo = ([f"Caso cerrado: {nombre} era el Cambiaformas y ya todos lo saben."]
                      if self.estado == "expuesto" else
                      [f"Acusaron a {self.acusado['nombre']}, que era inocente.",
                       "El Cambiaformas borró su rastro. Ya no se puede hacer nada."])
            return {"tipo": "aviso", "titulo": "NEXUS · El Cambiaformas", "cuerpo": cuerpo,
                    "pie": pie_salir, "nexus_terminal": True}
        mias = self.pruebas_de(jugador)
        opciones = []
        if mias:
            opciones.append((f"Subir prueba{'s' if len(mias) > 1 else ''} ({len(mias)})", "subir"))
        if self.subidas:
            opciones.append(("Acusar a alguien", "acusar"))
        opciones.append(("Salir", "salir"))
        cuerpo = ["Uno de los prisioneros que caminan por la nave es el Cambiaformas "
                  "disfrazado. Busquen las 3 pruebas por la nave y súbanlas aquí: al "
                  "exponerlo, no se podrá disfrazar por un rato.",
                  f"Pruebas subidas: {len(self.subidas)}/{len(PRUEBAS)}", "",
                  "Sospechosos:"] + self.lineas_sospechosos()
        return {
            "tipo": "opciones", "accion": "infiltrado_menu", "zona": zona, "nexus_terminal": True,
            "titulo": "NEXUS · El Cambiaformas",
            "cuerpo": cuerpo,
            "opciones": [{"texto": t} for t, _ in opciones],
            "acciones": [a for _, a in opciones],
            "pie": (f"[{jugador.pista_mover()}] elegir   "
                    f"[{jugador.nombre_tecla('interactuar')}] confirmar"),
        }

    def panel_acusar(self, jugador):
        restantes = self.restantes()
        return {
            "tipo": "opciones", "accion": "infiltrado_acusar", "nexus_terminal": True,
            "titulo": "¿Quién es el Cambiaformas?",
            "cuerpo": ["Si aciertas, queda expuesto. Si te equivocas, el caso se cierra "
                       "y la nave avisa a los aliens dónde estás."],
            "opciones": [{"texto": s["nombre"]} for s in restantes] + [{"texto": "Mejor no"}],
            "candidatos": restantes,
            "pie": (f"[{jugador.pista_mover()}] elegir   "
                    f"[{jugador.nombre_tecla('interactuar')}] confirmar"),
        }

    def subir(self, jugador):
        """Sube todas las pruebas que lleva. Devuelve (texto, puntos)."""
        mias = self.pruebas_de(jugador)
        if not mias:
            return "No llevas pruebas para subir.", 0
        antes = len(self.restantes())
        for tipo in mias:
            jugador.objetos.discard(tipo)
            self.subidas.append(tipo)
        puntos = PUNTOS_SUBIR_PRUEBA * len(mias)
        jugador.sumar_puntos(puntos)
        logro(self.juego, "evidencia", jugador)
        self._sonar("senal", 0.7)
        descartados = antes - len(self.restantes())
        texto = (f"Subiste {len(mias)} prueba{'s' if len(mias) > 1 else ''}. La red descartó a "
                 f"{descartados} sospechoso{'s' if descartados != 1 else ''}.")
        if len(self.subidas) >= len(PRUEBAS):
            self.exponer(jugador)
            texto += f" ¡Ya no hay duda: era {self.infiltrado['nombre']}!"
            puntos += PUNTOS_EXPONER
        else:
            for otro in self.juego.jugadores:
                if otro is not jugador:
                    otro.avisar(f"{jugador.rol} subió pruebas ({len(self.subidas)}/{len(PRUEBAS)})",
                                COLOR_CASO)
        return texto, puntos

    def acusar(self, jugador, sospechoso):
        """Devuelve (texto, puntos)."""
        self.acusado = sospechoso
        if sospechoso is self.infiltrado:
            self.exponer(jugador)
            return (f"¡Acertaste! {sospechoso['nombre']} era el Cambiaformas. "
                    f"Los aliens quedaron confundidos y ya no se puede disfrazar un rato.", PUNTOS_EXPONER)
        self.fallar(jugador, sospechoso)
        return (f"{sospechoso['nombre']} era inocente. El Cambiaformas se escondió y la nave "
                f"te delató: los aliens vienen por ti.", PUNTOS_ACUSACION_FALSA)

    # -- Cierre del caso -----------------------------------------------------------------

    def exponer(self, jugador):
        self.estado = "expuesto"
        logro(self.juego, "caso_cerrado" if len(self.subidas) >= len(PRUEBAS) else "corazonada",
              jugador)
        jugador.sumar_puntos(PUNTOS_EXPONER)
        for alien in getattr(self.juego, "aliens", ()):
            alien.confundir(CONFUSION_MS)
        self._sonar("expuesto", 0.9)
        for otro in self.juego.jugadores:
            otro.avisar(f"¡Cambiaformas expuesto! Aliens confundidos {CONFUSION_MS // 1000} s",
                        COLOR_BIEN)
        self._limpiar()
        self._decir("infiltrado_expuesto", jugador.rol)

    def fallar(self, jugador, sospechoso):
        self.estado = "fallido"
        logro(self.juego, "acusacion_falsa", jugador)
        jugador.sumar_puntos(PUNTOS_ACUSACION_FALSA)
        for alien in getattr(self.juego, "aliens", ()):
            alien.oir(jugador.hitbox.center)
            if hasattr(alien, "enterarse"):
                alien.enterarse(jugador)
        self._sonar("alarma", 0.8)
        for otro in self.juego.jugadores:
            if otro is not jugador:
                otro.avisar(f"{jugador.rol} acusó a un inocente", COLOR_MAL)
        self._limpiar()
        self._decir("acusacion_falsa", jugador.rol)

    def _limpiar(self):
        """Caso cerrado: las pruebas que queden ya no sirven."""
        for jugador in self.juego.jugadores:
            for tipo in PRUEBAS:
                while tipo in jugador.objetos:
                    jugador.objetos.discard(tipo)
        for prueba in self.pruebas:
            prueba["tomada"] = True

    def soltar(self, jugador, punto):
        """Lo eliminaron: las pruebas que llevaba caen donde lo atraparon."""
        tipos = [t for t in PRUEBAS if t in jugador.objetos]
        if not self.activo:
            return []
        mundo = self.juego.mundo
        for i, tipo in enumerate(tipos):
            jugador.objetos.discard(tipo)
            angulo = 2 * math.pi * i / max(1, len(tipos)) + 0.5
            deseado = (punto[0] + math.cos(angulo) * 60 - TAMANO_PRUEBA[0] / 2,
                       punto[1] + math.sin(angulo) * 44 - TAMANO_PRUEBA[1] / 2)
            x, y = mundo.punto_libre(deseado, *TAMANO_PRUEBA)
            centro = (int(x + TAMANO_PRUEBA[0] / 2), int(y + TAMANO_PRUEBA[1] / 2))
            self.pruebas.append({"rect": _rect(centro), "tipo": tipo, "tomada": False})
        return tipos

    def resumen(self):
        """Una línea para la pantalla de resultados, o None si no hubo caso."""
        if not self.pruebas:
            return None
        nombre = self.infiltrado["nombre"]
        if self.estado == "expuesto":
            return f"Cambiaformas: expuesto ({nombre})"
        if self.estado == "fallido":
            return f"Cambiaformas: acusaron a {self.acusado['nombre']}; era {nombre}"
        return f"Cambiaformas: no lo descubrieron (era {nombre}, {len(self.subidas)}/3 pruebas)"

    def _sonar(self, nombre, volumen=1.0):
        if hasattr(self.juego, "sonar"):
            self.juego.sonar(nombre, volumen)

    def _decir(self, evento, rol=None):
        if hasattr(self.juego, "decir"):
            self.juego.decir(evento, rol, forzar=True)


def _rect(centro):
    r = pygame.Rect(0, 0, *TAMANO_PRUEBA)
    r.center = centro
    return r
