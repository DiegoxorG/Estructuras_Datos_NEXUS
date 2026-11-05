"""El mundo de juego: el mapa, sus colisiones y las cámaras de cada jugador.

Carga un fondo de Imagenes/Fondos/ junto con las hitboxes que se hayan
dibujado para él en Hitboxes/<nombre>_hitboxes.json (ver CLAUDE.md).
Las coordenadas del archivo son proporciones de 0 a 1, así que aquí se
desnormalizan contra el tamaño al que se dibuja el mundo.
"""

import json
import os

# La raíz del proyecto (este archivo está en una subcarpeta).
_RAIZ_PROYECTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from collections import deque

import pygame


CARPETA_FONDOS = os.path.join(_RAIZ_PROYECTO, "Imagenes", "Fondos")
CARPETA_HITBOXES = os.path.join(_RAIZ_PROYECTO, "Hitboxes")

# El mapa se dibuja más grande que su archivo original para que el personaje
# no ocupe media pantalla. Se escala con nearest neighbor para no emborronar
# el pixel art.
ESCALA_MAPA = 3


def paredes_extra(mundo):
    """Las paredes de ahora que no son del mapa fijo (`paredes_base`): las
    puertas con código que siguen cerradas, básicamente.

    Antes cada quien lo sacaba con `[p for p in mundo.paredes if p not in
    mundo.paredes_base]`: buscar en una lista es recorrerla, así que eran
    ~180 x 180 comparaciones de Rect por llamada. La flecha del objetivo lo
    preguntaba 3 veces por jugador y por cuadro (Mision._llega) y en el PC de
    Diego eso solo eran ~6 ms por cuadro desde que se abre la primera puerta.
    Ahora el mapa fijo se guarda como un set de tuplas (se rehace si
    `paredes_base` cambia, p. ej. al sellar salas)."""
    base = mundo.paredes_base
    guardado = mundo.__dict__.get("_base_como_set")
    if guardado is None or guardado[0] is not base or guardado[1] != len(base):
        guardado = (base, len(base), {tuple(r) for r in base})
        mundo.__dict__["_base_como_set"] = guardado
    fijas = guardado[2]
    return [p for p in mundo.paredes if tuple(p) not in fijas]


class Mundo:
    def __init__(self, nombre_mapa="Nave", escala=ESCALA_MAPA):
        self.nombre_mapa = nombre_mapa
        self.escala = escala
        self.imagen = self._cargar_mapa()
        self.ancho, self.alto = self.imagen.get_size()
        self.paredes, self.interactuables = self._cargar_hitboxes()
        # Las paredes del archivo, sin lo que agrega la partida (la puerta de
        # la prisión). Al empezar otra ronda en el mismo mapa se vuelve a esto.
        self.paredes_base = list(self.paredes)
        self.paredes_archivo = list(self.paredes)
        # Las salas que se sellan en esta ronda (juego/salas_selladas.py).
        self.sellado = None
        # Barreras que solo frenan a los aliens: los sellos que activa el
        # Forjador al reparar un panel (acciones_rol.py).
        self.bloqueos_alien = []
        # Puertas para dos todavía cerradas: a los aliens también los frenan
        # (a los jugadores, Game._colisiona_jugador). Aparte de los sellos
        # porque esa lista se rehace en cada cuadro y da el logro "Por aquí no".
        self.puertas_alien = []

    def sellar(self, rects):
        """Las paredes de las salas selladas de esta ronda (salas_selladas.py)
        pasan a ser parte del mapa fijo. Si cambian, la navegación se vuelve a
        armar (las celdas libres salen de `paredes_base`)."""
        nuevas = self.paredes_archivo + list(rects)
        if nuevas != self.paredes_base:
            self.paredes_base = nuevas
            self.__dict__.pop("_navegaciones", None)
        self.reiniciar_paredes()

    def reiniciar_paredes(self):
        self.paredes = list(self.paredes_base)
        self.bloqueos_alien = []
        self.puertas_alien = []

    # -- Carga -------------------------------------------------------------------

    def _cargar_mapa(self):
        for extension in (".png", ".jpg", ".jpeg"):
            ruta = os.path.join(CARPETA_FONDOS, self.nombre_mapa + extension)
            if os.path.isfile(ruta):
                original = pygame.image.load(ruta).convert()
                ancho, alto = original.get_size()
                return pygame.transform.scale(
                    original, (ancho * self.escala, alto * self.escala)
                )
        # Sin mapa: un fondo liso para que el juego siga corriendo.
        respaldo = pygame.Surface((960 * 2, 600 * 2))
        respaldo.fill((46, 62, 54))
        return respaldo

    def _cargar_hitboxes(self):
        """Devuelve (paredes, interactuables) como listas de Rect del mundo."""
        ruta = os.path.join(CARPETA_HITBOXES, f"{self.nombre_mapa}_hitboxes.json")
        paredes, interactuables = [], []
        try:
            with open(ruta, "r", encoding="utf-8") as fh:
                datos = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return paredes, interactuables

        for h in datos.get("hitboxes", []):
            if h.get("type") != "rect":
                continue  # por ahora solo rectángulos
            try:
                rect = pygame.Rect(
                    int(h["rx"] * self.ancho),
                    int(h["ry"] * self.alto),
                    max(1, int(h["rw"] * self.ancho)),
                    max(1, int(h["rh"] * self.alto)),
                )
            except (KeyError, TypeError):
                continue
            if h.get("role") == "interactable":
                interactuables.append(rect)
            else:
                paredes.append(rect)
        return paredes, interactuables

    # -- Consultas ----------------------------------------------------------------

    def colisiona(self, rect):
        """True si el rect choca con una pared o se sale del mapa."""
        if rect.left < 0 or rect.top < 0 or rect.right > self.ancho or rect.bottom > self.alto:
            return True
        return rect.collidelist(self.paredes) != -1

    def colisiona_alien(self, rect):
        """Para los aliens: las paredes, los sellos activos y las puertas para
        dos cerradas."""
        return (self.colisiona(rect) or rect.collidelist(self.bloqueos_alien) != -1
                or rect.collidelist(self.puertas_alien) != -1)

    def colisiona_npc(self, rect):
        """Para los prisioneros que caminan: las paredes (con la puerta del
        código cerrada) y las puertas para dos cerradas. Los sellos del
        Forjador no: esos solo frenan a los aliens."""
        return self.colisiona(rect) or rect.collidelist(self.puertas_alien) != -1

    def linea_libre(self, desde, hasta, ancho=4, alto=4, paso=10, colisiona=None):
        """True si se puede ir en línea recta de `desde` a `hasta` sin paredes.

        Se avanza por la línea en pasitos de `paso` píxeles y en cada uno se
        prueba un rect de `ancho` x `alto`. Con el rect chiquito por defecto
        sirve como línea de vista (¿el alien ve al jugador?); con el tamaño de
        la hitbox de un personaje sirve para saber si puede caminar por ahí
        (¿la ruta de patrulla atraviesa una pared?).
        """
        dx, dy = hasta[0] - desde[0], hasta[1] - desde[1]
        pasos = max(1, int(max(abs(dx), abs(dy)) // paso))
        for i in range(pasos + 1):
            x = desde[0] + dx * i / pasos
            y = desde[1] + dy * i / pasos
            rect = pygame.Rect(0, 0, ancho, alto)
            rect.center = (int(x), int(y))
            if (colisiona or self.colisiona)(rect):
                return False
        return True

    def tramos_bloqueados(self, ruta, ancho, alto):
        """Tramos de una ruta cerrada que atraviesan una pared.

        Devuelve una lista de (i, j): el tramo que va del punto i al j. Se llama
        al empezar la partida, igual que zonas_inalcanzables, para que una ruta
        mal puesta se avise en consola en vez de dejar a un alien pegado.
        """
        malos = []
        for i, punto in enumerate(ruta):
            siguiente = ruta[(i + 1) % len(ruta)]
            if not self.linea_libre(punto, siguiente, ancho, alto, paso=6):
                malos.append((i, (i + 1) % len(ruta)))
        return malos

    def punto_libre(self, preferido, ancho=40, alto=24):
        """Busca una posición sin paredes cerca de `preferido` (x, y del mundo)."""
        px, py = preferido
        for radio in range(0, max(self.ancho, self.alto), 16):
            for dx, dy in ((0, 0), (radio, 0), (-radio, 0), (0, radio), (0, -radio),
                           (radio, radio), (-radio, -radio), (radio, -radio), (-radio, radio)):
                candidato = pygame.Rect(px + dx, py + dy, ancho, alto)
                if not self.colisiona(candidato):
                    return candidato.x, candidato.y
        return px, py

    def area_alcanzable(self, desde, ancho=48, alto=19, paso=16, colisiona=None):
        """Celdas del mapa a las que se puede llegar caminando desde `desde`.

        Un rectángulo puede no chocar con ninguna pared y aun así ser
        inalcanzable, porque está dentro de un cuarto cerrado. La única forma
        de saberlo es recorrer el mapa como lo haría el jugador: se avanza de
        celda en celda en las cuatro direcciones (BFS con una cola) y se
        devuelve todo lo que se pudo tocar.
        """
        inicio = (int(desde[0]) // paso * paso, int(desde[1]) // paso * paso)
        vistos = {inicio}
        cola = deque([inicio])
        while cola:
            cx, cy = cola.popleft()
            for dx, dy in ((paso, 0), (-paso, 0), (0, paso), (0, -paso)):
                vecino = (cx + dx, cy + dy)
                if vecino in vistos:
                    continue
                if not (0 <= vecino[0] <= self.ancho - ancho
                        and 0 <= vecino[1] <= self.alto - alto):
                    continue
                if (colisiona or self.colisiona)(pygame.Rect(vecino[0], vecino[1], ancho, alto)):
                    continue
                vistos.add(vecino)
                cola.append(vecino)
        return vistos

    def zonas_inalcanzables(self, zonas, desde, ancho=48, alto=19, paso=16):
        """Zonas que el jugador no podría alcanzar desde `desde`.

        Se llama al empezar la partida. Si devuelve algo, es que alguien puso
        una Terminal NEXUS dentro de un cuarto cerrado y hay que moverla con el
        editor de mapa. Vale el costo: encontrar esto jugando es mucho más caro
        que un recorrido al arrancar.
        """
        alcanzable = self.area_alcanzable(desde, ancho, alto, paso)
        malas = []
        for zona in zonas:
            rect = zona["rect"]
            if not any(pygame.Rect(c[0], c[1], ancho, alto).colliderect(rect)
                       for c in alcanzable):
                malas.append(zona)
        return malas

    def camara(self, centro, ancho_vista, alto_vista):
        """Rect de cámara centrado en `centro`, recortado a los bordes del mapa."""
        cx, cy = centro
        x = int(cx - ancho_vista / 2)
        y = int(cy - alto_vista / 2)
        x = max(0, min(x, max(0, self.ancho - ancho_vista)))
        y = max(0, min(y, max(0, self.alto - alto_vista)))
        return pygame.Rect(x, y, ancho_vista, alto_vista)
