"""Navegación de los aliens: caminos que rodean las paredes.

Antes, cuando un alien iba a revisar un ruido (la alarma del código malo, una
señal de la Resonante, un señuelo...) caminaba en línea recta hacia el punto, y
si había una pared en medio se quedaba mirándola. Ahora:

1. Si hay línea libre (con el ancho del alien) va directo.
2. Si no, busca un camino con **BFS** sobre una cuadrícula del mapa: cada
   celda es un lugar donde cabe el alien, vecinas en 8 direcciones. Es el mismo
   recorrido por niveles que se usa para dibujar los árboles, pero sobre un
   grafo implícito (las celdas son los nodos; las celdas vecinas libres, las
   aristas).
3. El camino se "estira": se salta los puntos intermedios a los que ya se
   puede llegar en línea recta, para que no camine en zigzag.

Lo que cambia durante la partida (la puerta de la prisión, los sellos del
Forjador) no está en la cuadrícula fija: se revisa al buscar cada camino.
"""

import heapq
import time
from collections import deque

import pygame


PASO = 16
MAX_NODOS = 40000        # tope del BFS, por si el destino no se alcanza
PESO_ESTIMADO = 1.6      # A* "con prisa": revisa muchas menos celdas y el camino
                         # sale casi igual (después se estira en línea recta)
PRESUPUESTO_CUADRO = 1500  # celdas por cuadro de un camino "por partes" (prisioneros)
PRESUPUESTO_ALIEN = 4000   # lo mismo para los aliens (tienen más prisa)
# Además del tope de celdas, un tope de TIEMPO para todas las búsquedas "por
# partes" de un cuadro juntas: 4000 celdas eran ~4 ms en la nube pero 15-35 ms
# en el PC de Diego (el tirón de cuando un alien sale a buscar lejos, p. ej.
# al cebo de una publicación falsa). Medido en ms reales, en un PC lento se
# reparte en más cuadros en vez de frenar uno. Cada búsqueda avanza al menos
# MINIMO_CELDAS por cuadro para no quedarse quieta si hay varias.
LIMITE_MS_CUADRO = 3.0
MINIMO_CELDAS = 200
_gasto_cuadro = {"cuadro": None, "ms": 0.0}


def _gastado(ms=0.0):
    """Los ms que ya usaron este cuadro las búsquedas por partes (sumando `ms`)."""
    if _gasto_cuadro["cuadro"] != Navegacion.cuadro:
        _gasto_cuadro["cuadro"], _gasto_cuadro["ms"] = Navegacion.cuadro, 0.0
    _gasto_cuadro["ms"] += ms
    return _gasto_cuadro["ms"]


class Navegacion:
    cuadro = 0                # lo sube el juego en cada cuadro (siguiente_cuadro)
    ultimo_cuadro = -1        # en qué cuadro se calculó el último camino nuevo
    ocupada = False
    ultima_busqueda = None    # {"explorados": celdas que revisó el A*, "camino": ...}
    def __init__(self, mundo, ancho, alto, paso=PASO):
        self.mundo = mundo
        self.ancho, self.alto, self.paso = ancho, alto, paso
        self._guardados = {}
        base = mundo.paredes_base
        self.libre = set()
        for x in range(0, mundo.ancho - ancho, paso):
            for y in range(0, mundo.alto - alto, paso):
                if pygame.Rect(x, y, ancho, alto).collidelist(base) == -1:
                    self.libre.add((x, y))

    # -- Lo que cambia en la partida -------------------------------------------------

    def _bloqueos_extra(self, sellos=True):
        """Lo que tapa ahora además del mapa fijo: la puerta del código, las
        puertas para dos cerradas y (si `sellos`) los sellos del Forjador, que
        solo frenan a los aliens: los prisioneros los cruzan (sellos=False)."""
        mundo = self.mundo
        from juego.mundo import paredes_extra
        extra = paredes_extra(mundo)
        if sellos:
            extra += list(getattr(mundo, "bloqueos_alien", []))
        extra += list(getattr(mundo, "puertas_alien", []))
        return extra

    def _celda_de(self, punto):
        x = int(punto[0] - self.ancho / 2) // self.paso * self.paso
        y = int(punto[1] - self.alto / 2) // self.paso * self.paso
        return x, y

    def _mas_cercana(self, punto, ok):
        """La celda libre más cercana a `punto` (busca en un radio chico)."""
        cx, cy = self._celda_de(punto)
        mejor, mejor_d = None, None
        for r in range(0, 6):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    c = (cx + dx * self.paso, cy + dy * self.paso)
                    if ok(c):
                        d = (c[0] + self.ancho / 2 - punto[0]) ** 2 + (c[1] + self.alto / 2 - punto[1]) ** 2
                        if mejor is None or d < mejor_d:
                            mejor, mejor_d = c, d
            if mejor is not None:
                return mejor
        return None

    # -- Buscar un camino --------------------------------------------------------------

    def _componentes(self):
        """A qué pedazo conectado del mapa fijo pertenece cada celda (se arma
        una vez). Sirve para saber al instante que dos puntos no se conectan
        sin recorrer todo el mapa buscando."""
        if getattr(self, "_comp", None) is None:
            p = self.paso
            vecinos = ((p, 0), (-p, 0), (0, p), (0, -p))
            self._comp, self._celdas_comp = {}, []
            for celda in self.libre:
                if celda in self._comp:
                    continue
                n = len(self._celdas_comp)
                grupo = [celda]
                self._comp[celda] = n
                cola = deque([celda])
                while cola:
                    c = cola.popleft()
                    for dx, dy in vecinos:
                        v = (c[0] + dx, c[1] + dy)
                        if v in self.libre and v not in self._comp:
                            self._comp[v] = n
                            grupo.append(v)
                            cola.append(v)
                self._celdas_comp.append(grupo)
        return self._comp

    def _estado(self, sellos=True, extra=None):
        """Lo que está cerrado AHORA (puertas, sellos): qué celdas tapa y en qué
        pedazos queda partido el mapa. Se arma una vez por cada estado de las
        puertas y lo comparten el A* y `conectados` (todos los aliens y
        prisioneros). `extra` reemplaza a los bloqueos de siempre (las cajas
        de fusibles preguntan con lo que frena a los jugadores)."""
        if extra is None:
            extra = self._bloqueos_extra(sellos)
        clave = tuple(tuple(r) for r in extra)
        estados = self.__dict__.setdefault("_estados", {})
        estado = estados.get(clave)
        if estado is None:
            if len(estados) >= 8:
                estados.clear()
            tapadas = self._tapadas(extra)
            mascara = self._mascara_base().copy()
            p = self.paso
            for x, y in tapadas:
                i, j = 2 * (x // p), 2 * (y // p)
                for punto in ((i, j), (i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                    if punto[0] >= 0 and punto[1] >= 0:
                        mascara.set_at(punto, 0)
            estado = {"tapadas": tapadas, "mascara": mascara, "zonas": []}
            estados[clave] = estado
        return estado

    def _mascara_base(self):
        """El mapa fijo como una máscara de pygame para sacar los pedazos
        conectados en C (antes era un BFS en Python: ~25 ms por cada puerta que
        se abría o sello que se levantaba, y el doble en un PC más lento).

        Cada celda libre es un pixel en (2i, 2j); el pixel de en medio entre
        dos vecinas (2i+1, 2j) o (2i, 2j+1) se prende solo si las dos están
        libres. Así lo que "toca" en la máscara (pygame junta también en
        diagonal) es justo lo que se conecta caminando: los pixeles impares en
        las dos coordenadas siempre quedan apagados."""
        if getattr(self, "_mascara", None) is None:
            p, libre = self.paso, self.libre
            mascara = pygame.mask.Mask((2 * (self.mundo.ancho // p) + 4, 2 * (self.mundo.alto // p) + 4))
            poner = mascara.set_at
            for x, y in libre:
                i, j = 2 * (x // p), 2 * (y // p)
                poner((i, j))
                if (x + p, y) in libre:
                    poner((i + 1, j))
                if (x, y + p) in libre:
                    poner((i, j + 1))
            self._mascara = mascara
        return self._mascara

    def _zona(self, estado, celda):
        """Número del pedazo conectado de `celda` con lo cerrado de `estado`
        (`celda` tiene que estar libre y no tapada)."""
        p = self.paso
        punto = (2 * (celda[0] // p), 2 * (celda[1] // p))
        zonas = estado["zonas"]
        for n, zona in enumerate(zonas):
            if zona.get_at(punto):
                return n
        zonas.append(estado["mascara"].connected_component(punto))
        return len(zonas) - 1

    def _mas_cercana_en_zona(self, estado, n, punto):
        """La celda del pedazo `n` más cercana a `punto` (para ir lo más cerca
        posible de algo que quedó del otro lado de una puerta). Busca en
        anillos alrededor de `punto` hasta que ya no puede haber una mejor."""
        zona, p = estado["zonas"][n], self.paso
        w, h = self.ancho, self.alto
        ancho, alto = zona.get_size()
        ci, cj = int(punto[0] - w / 2) // p, int(punto[1] - h / 2) // p
        mejor, mejor_d = None, None
        for r in range(0, max(ancho, alto) // 2 + 1):
            if mejor is not None and (r - 1) * p > mejor_d ** 0.5:
                break
            for i in range(ci - r, ci + r + 1):
                for j in ((cj - r, cj + r) if abs(i - ci) != r else range(cj - r, cj + r + 1)):
                    if 0 <= 2 * i < ancho and 0 <= 2 * j < alto and zona.get_at((2 * i, 2 * j)):
                        c = (i * p, j * p)
                        d = (c[0] + w / 2 - punto[0]) ** 2 + (c[1] + h / 2 - punto[1]) ** 2
                        if mejor is None or d < mejor_d:
                            mejor, mejor_d = c, d
        return mejor

    def conectados(self, a, b, sellos=True, extra=None):
        """¿Se puede ir de `a` a `b` con lo que está cerrado AHORA (puertas,
        sellos)? Sin buscar el camino: con los pedazos conectados de `_estado`
        (antes, preguntarlo con el A* recorría toda la zona cada vez que la
        respuesta era "no")."""
        estado = self._estado(sellos, extra)
        tapadas, libre = estado["tapadas"], self.libre

        def ok(c):
            return c in libre and c not in tapadas

        ca, cb = self._mas_cercana(a, ok), self._mas_cercana(b, ok)
        return ca is not None and cb is not None and self._zona(estado, ca) == self._zona(estado, cb)

    def _vecinos(self):
        """Lista de adyacencia del grafo de la nave (se arma una vez): para
        cada celda libre, sus vecinas libres en 8 direcciones con lo que cuesta
        ir (1 o 1.41) y, en diagonal, las dos celdas de la esquina que tienen
        que estar libres para no cortarla."""
        if getattr(self, "_ady", None) is None:
            p, libre = self.paso, self.libre
            self._ady = {}
            for c in libre:
                lista = []
                for dx, dy in ((p, 0), (-p, 0), (0, p), (0, -p), (p, p), (p, -p), (-p, p), (-p, -p)):
                    v = (c[0] + dx, c[1] + dy)
                    if v not in libre:
                        continue
                    if dx and dy:
                        a, b = (c[0] + dx, c[1]), (c[0], c[1] + dy)
                        if a not in libre or b not in libre:
                            continue
                        lista.append((v, 1.4142, (a, b)))
                    else:
                        lista.append((v, 1.0, None))
                self._ady[c] = lista
        return self._ady

    def _tapadas(self, extra):
        """Celdas libres del mapa fijo que tapa lo que cambia (puerta, sellos)."""
        tapadas = set()
        p, w, h = self.paso, self.ancho, self.alto
        for r in extra:
            x0 = (r.left - w) // p * p
            y0 = (r.top - h) // p * p
            for x in range(x0, r.right + p, p):
                for y in range(y0, r.bottom + p, p):
                    if (x, y) in self.libre and pygame.Rect(x, y, w, h).colliderect(r):
                        tapadas.add((x, y))
        return tapadas

    def camino(self, desde, hasta, parcial=False, puede_esperar=False, sellos=True, por_partes=False,
               quien=None):
        """Lista de puntos (centros) de `desde` a `hasta`, o None si no hay.

        Con `parcial=True`, si no se puede llegar (por ejemplo, el ruido está
        al otro lado de la puerta cerrada de la prisión), devuelve el camino
        hasta la celda alcanzable más cercana al destino: el alien va lo más
        cerca que puede, como haría alguien que oye algo detrás de una puerta.
        En ese caso el último punto NO es `hasta` (ver `self.ultimo_parcial`).

        Busca con A* (un BFS que primero prueba las celdas que van hacia la
        meta): encuentra el mismo tipo de camino que el BFS de antes pero
        revisando muchas menos celdas, así no da tirones cuando varios
        prisioneros y aliens piden camino a la vez.

        Con `por_partes` (True = PRESUPUESTO_CUADRO, o un número de celdas)
        un camino largo se busca de a pedazos, esa cantidad de celdas por
        cuadro, devolviendo None con `ocupada` mientras tanto: un camino de
        punta a punta de MapaE2 (~15.000 celdas) ya no frena un cuadro entero.
        Hay que volver a pedir el MISMO destino para que siga. Con `quien`
        (id de quien lo pide) la búsqueda sigue aunque él se haya movido
        mientras tanto: el camino sale desde donde empezó a buscar.
        """
        self.ultimo_parcial = False
        extra = self._bloqueos_extra(sellos)
        # Los prisioneros van y vienen entre los mismos puntos: el mismo camino
        # se pide muchas veces. Se guarda (mientras no cambie lo que tapa).
        clave = (self._celda_de(desde), self._celda_de(hasta), int(hasta[0]), int(hasta[1]),
                 parcial, tuple(tuple(r) for r in extra))
        guardado = self._guardados.get(clave)
        if guardado is not None:
            self.ultimo_parcial = guardado[1]
            return list(guardado[0]) if guardado[0] is not None else None
        # Los prisioneros no tienen prisa: si en este mismo cuadro ya se
        # calculó otro camino nuevo, esperan su turno (None, con `ocupada`) y
        # lo piden después. Así varios caminos largos no caen en el mismo
        # cuadro (tirón).
        self.ocupada = False
        if puede_esperar and Navegacion.ultimo_cuadro == Navegacion.cuadro:
            self.ocupada = True
            return None
        if por_partes:
            pendientes = self.__dict__.setdefault("_pendientes", {})
            clave_pendiente = clave if quien is None else ("de", quien) + clave[1:]
            busqueda = pendientes.pop(clave_pendiente, None)
            if busqueda is None:
                if len(pendientes) > 30:      # pedidos que nadie volvió a pedir
                    pendientes.clear()
                presupuesto = PRESUPUESTO_CUADRO if por_partes is True else int(por_partes)
                busqueda = self._busqueda(desde, hasta, parcial, extra, presupuesto)
            Navegacion.ultimo_cuadro = Navegacion.cuadro
            try:
                next(busqueda)
            except StopIteration as fin:
                resultado, self.ultimo_parcial, self._explorados = fin.value
            else:
                pendientes[clave_pendiente] = busqueda
                self.ocupada = True
                return None
        else:
            resultado = self._camino(desde, hasta, parcial, extra)
        Navegacion.ultimo_cuadro = Navegacion.cuadro
        # La última búsqueda nueva, para la vista del grafo de la nave.
        Navegacion.ultima_busqueda = {"explorados": self._explorados, "camino": resultado,
                                      "desde": desde, "hasta": hasta, "nav": self}
        if len(self._guardados) > 2000:
            self._guardados.clear()
        self._guardados[clave] = (resultado, self.ultimo_parcial)
        return list(resultado) if resultado is not None else None

    def _camino(self, desde, hasta, parcial, extra):
        busqueda = self._busqueda(desde, hasta, parcial, extra)
        try:
            while True:
                next(busqueda)
        except StopIteration as fin:
            resultado, self.ultimo_parcial, self._explorados = fin.value
        return resultado

    def _busqueda(self, desde, hasta, parcial, extra, presupuesto=None):
        """El A*, como generador: con `presupuesto`, cada `next()` revisa a lo
        más esa cantidad de celdas (así se reparte en varios cuadros). Al
        terminar devuelve (camino o None, si es parcial, celdas exploradas)."""
        estado = self._estado(extra=extra)
        tapadas = estado["tapadas"]
        libre = self.libre
        w, h = self.ancho, self.alto

        def ok(c):
            return c in libre and c not in tapadas

        inicio = self._mas_cercana(desde, ok)
        meta = self._mas_cercana(hasta, ok)
        if inicio is None or meta is None:
            return None, False, set()
        zona = self._zona(estado, inicio)
        if zona != self._zona(estado, meta):
            # No se conectan (una pared, o una puerta cerrada en medio): antes
            # el A* recorría todo su lado buscando hasta rendirse (el tirón de
            # cuando se abría la puerta del Laboratorio). Ahora se sabe de una:
            # sin camino, o hasta lo más cerca posible de su lado.
            if not parcial:
                return None, False, set()
            meta = self._mas_cercana_en_zona(estado, zona, hasta)
            if meta is None:
                return None, False, set()
            hasta = None
        mx, my = meta
        p = self.paso
        diag = 1.4142

        def estimado(c):
            dx, dy = abs(c[0] - mx) / p, abs(c[1] - my) / p
            return (dx + dy) + (diag - 2) * (dx if dx < dy else dy)

        vecinos = self._vecinos()
        previo = {inicio: None}
        costo = {inicio: 0.0}
        abiertos = [(estimado(inicio), 0, inicio)]
        orden = 0
        heappop, heappush = heapq.heappop, heapq.heappush
        cuenta = 0
        cerradas = set()
        costo_de = costo.get
        peso, resta = PESO_ESTIMADO / p, diag - 2
        reloj = time.perf_counter
        desde_ms = reloj()
        while abiertos and len(previo) < MAX_NODOS:
            if presupuesto is not None:
                cuenta += 1
                if cuenta >= presupuesto or (cuenta >= MINIMO_CELDAS and not cuenta & 63 and
                                              _gastado() + (reloj() - desde_ms) * 1000 > LIMITE_MS_CUADRO):
                    _gastado((reloj() - desde_ms) * 1000)
                    cuenta = 0
                    yield
                    desde_ms = reloj()
            _, _, c = heappop(abiertos)
            if c in cerradas:
                continue           # una entrada vieja de la cola: ya se revisó
            if c == meta:
                break
            cerradas.add(c)
            base = costo[c]
            for v, paso, esquinas in vecinos[c]:
                if v in cerradas:
                    continue
                if tapadas and (v in tapadas or (esquinas and (esquinas[0] in tapadas
                                                               or esquinas[1] in tapadas))):
                    continue
                nuevo = base + paso
                if nuevo < costo_de(v, 1e18):
                    costo[v] = nuevo
                    previo[v] = c
                    orden += 1
                    # (el estimado, escrito aquí mismo: es lo que más se repite)
                    ex, ey = abs(v[0] - mx), abs(v[1] - my)
                    heappush(abiertos, (nuevo + peso * ((ex + ey) + resta * (ex if ex < ey else ey)),
                                        orden, v))
        explorados = set(previo)
        llego = meta in previo and hasta is not None
        es_parcial = False
        if meta not in previo or hasta is None:
            if not parcial or len(previo) <= 1:
                return None, False, explorados
            objetivo = hasta if hasta is not None else (mx + w / 2, my + h / 2)
            if meta not in previo:
                meta = min(previo, key=lambda c: (c[0] + w / 2 - objetivo[0]) ** 2
                           + (c[1] + h / 2 - objetivo[1]) ** 2)
            es_parcial = True
        celdas = []
        c = meta
        while c is not None:
            celdas.append(c)
            c = previo[c]
        celdas.reverse()
        puntos = [(cx + w // 2, cy + h // 2) for cx, cy in celdas]
        if llego:
            puntos.append((int(hasta[0]), int(hasta[1])))
        return self.estirar(puntos), es_parcial, explorados

    def distancia_camino(self, desde, hasta, max_px, sellos=True):
        """Lo que mide el camino más corto de `desde` a `hasta` (en px), o None
        si no hay o si es más largo que `max_px`. Un A* con tope: no recorre
        más allá de `max_px`, así preguntar "¿llego sin dar la vuelta a media
        nave?" sale barato aunque la respuesta sea que no."""
        estado = self._estado(sellos)
        tapadas, libre = estado["tapadas"], self.libre

        def ok(c):
            return c in libre and c not in tapadas

        inicio = self._mas_cercana(desde, ok)
        meta = self._mas_cercana(hasta, ok)
        if inicio is None or meta is None or self._zona(estado, inicio) != self._zona(estado, meta):
            return None
        p = self.paso
        tope = max_px / p
        mx, my = meta
        resta = 1.4142 - 2

        def estimado(c):
            ex, ey = abs(c[0] - mx) / p, abs(c[1] - my) / p
            return (ex + ey) + resta * (ex if ex < ey else ey)

        if estimado(inicio) > tope:
            return None
        vecinos = self._vecinos()
        costo = {inicio: 0.0}
        abiertos = [(estimado(inicio), 0, inicio)]
        cerradas, orden = set(), 0
        while abiertos:
            _, _, c = heapq.heappop(abiertos)
            if c in cerradas:
                continue
            if c == meta:
                return costo[c] * p
            cerradas.add(c)
            base = costo[c]
            for v, paso, esquinas in vecinos[c]:
                if v in cerradas:
                    continue
                if tapadas and (v in tapadas or (esquinas and (esquinas[0] in tapadas
                                                               or esquinas[1] in tapadas))):
                    continue
                nuevo = base + paso
                total = nuevo + estimado(v)
                if total <= tope and nuevo < costo.get(v, 1e18):
                    costo[v] = nuevo
                    orden += 1
                    heapq.heappush(abiertos, (total, orden, v))
        return None

    def libre_entre(self, a, b):
        """¿El alien entero cabe por la línea recta de `a` a `b`?

        Lo mismo que `mundo.linea_libre` con `colisiona_alien` (pasitos de 8 px
        con un rect un poco más ancho que el alien, así no roza esquinas al
        doblar), pero probando solo contra las paredes que quedan cerca de la
        línea: se llama cientos de veces por camino."""
        mundo = self.mundo
        w, h = self.ancho + 4, self.alto + 4
        if not hasattr(mundo, "paredes_base"):        # (los mundos de mentira de las pruebas)
            choca = getattr(mundo, "colisiona_alien", mundo.colisiona)
            return mundo.linea_libre(a, b, w, h, paso=8, colisiona=choca)
        dx, dy = b[0] - a[0], b[1] - a[1]
        caja = pygame.Rect(min(a[0], b[0]) - w, min(a[1], b[1]) - h, abs(dx) + 2 * w, abs(dy) + 2 * h)
        todos = mundo.paredes + mundo.bloqueos_alien + mundo.puertas_alien
        cerca = [todos[i] for i in caja.collidelistall(todos)]
        adentro = caja.left >= 0 and caja.top >= 0 and caja.right <= mundo.ancho and caja.bottom <= mundo.alto
        if not cerca and adentro:
            return True
        pasos = max(1, int(max(abs(dx), abs(dy)) // 8))
        rect = pygame.Rect(0, 0, w, h)
        ancho, alto = mundo.ancho, mundo.alto
        for i in range(pasos + 1):
            rect.center = (int(a[0] + dx * i / pasos), int(a[1] + dy * i / pasos))
            if not adentro and (rect.left < 0 or rect.top < 0 or rect.right > ancho or rect.bottom > alto):
                return False
            if rect.collidelist(cerca) != -1:
                return False
        return True

    def estirar(self, puntos):
        """Quita los puntos intermedios que se pueden saltar en línea recta.
        Desde cada punto avanza mientras el siguiente se vea en línea recta
        (antes probaba desde el final hacia atrás: muchas más líneas)."""
        if len(puntos) <= 2:
            return puntos
        # Los puntos del medio de un tramo recto sobran (el camino sale de la
        # cuadrícula: casi todo son celdas en fila). Con menos puntos, muchas
        # menos líneas que probar.
        rectos = [puntos[0]]
        for k in range(1, len(puntos) - 1):
            a, b, c = rectos[-1], puntos[k], puntos[k + 1]
            if (b[0] - a[0]) * (c[1] - b[1]) != (b[1] - a[1]) * (c[0] - b[0]) or \
                    (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1]) < 0:
                rectos.append(b)
        rectos.append(puntos[-1])
        puntos = rectos
        if len(puntos) <= 2:
            return puntos[1:] if len(puntos) == 2 else puntos
        resultado = [puntos[0]]
        i = 0
        n = len(puntos)
        while i < n - 1:
            j = i + 1
            while j + 1 < n and self.libre_entre(puntos[i], puntos[j + 1]):
                j += 1
            resultado.append(puntos[j])
            i = j
        return resultado[1:]


def siguiente_cuadro():
    """Lo llama el juego una vez por cuadro (para repartir los caminos nuevos)."""
    Navegacion.cuadro += 1


def de_mundo(mundo, ancho, alto):
    """Una navegación por mundo y tamaño de alien (se arma la primera vez)."""
    cache = mundo.__dict__.setdefault("_navegaciones", {})
    clave = (ancho, alto)
    if clave not in cache:
        cache[clave] = Navegacion(mundo, ancho, alto)
    return cache[clave]
