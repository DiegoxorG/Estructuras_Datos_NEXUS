"""Campo de visión: los jugadores no ven a través de las paredes.

Como en Among Us, cada jugador solo ve bien lo que tiene en línea recta sin
paredes de por medio y dentro de un radio. Lo demás del mapa se sigue viendo,
pero oscurecido, y los aliens que estén fuera de esa zona no se dibujan.

Cómo se calcula el "polígono de visión" (Campo): desde el centro del jugador se
lanzan rayos en todas las direcciones y cada uno se corta en la primera pared
que toca (o en el radio, si no toca ninguna). Unir las puntas de los rayos da
el polígono. Además de unos rayos repartidos parejo, se lanza un par de rayos
rozando cada esquina de las paredes cercanas: así las sombras de las esquinas
quedan con borde recto y no "serruchado".

El choque rayo-rectángulo es la prueba de "las losas" (slab test): para cada
eje se ve en qué tramo del rayo está dentro del rectángulo, y si los tramos de
los dos ejes se cruzan, el rayo entra al rectángulo donde empieza el cruce.
Las paredes son pocas (unos 20 rectángulos), así que esto va en Python puro.

Obstáculos: las paredes del mapa (incluida la puerta de la prisión, que la
partida agrega a mundo.paredes), las puertas para dos cerradas y las
compuertas bajadas.
"""

import math


RADIO_VISION = 640           # hasta dónde ve un jugador, en píxeles del mundo
RAYOS = 90                   # rayos repartidos parejo (más las esquinas)
PASO_ORIGEN = 6              # el origen se redondea a esta rejilla: caminando, el
                             # campo se recalcula cada 2 cuadros y no en cada uno
ROCE_ESQUINA = 0.0008        # cuánto se desvía el rayo que roza una esquina
# Las paredes se ven "de frente" (vista 3/4): el dibujo de la pared sobresale
# hacia arriba de su hitbox. Para que la cara de la pared no quede negra, el
# rayo se mete un poco en ella, más cuando mira hacia arriba.
ENTRA_EN_PARED = 18
ENTRA_EN_PARED_ARRIBA = 70


_obstaculos = {"firma": None, "rects": None, "clave": None}


def obstaculos(mundo, puertas_dobles=(), compuertas=()):
    """Las paredes que tapan la vista ahora (mapa, puerta del código cerrada,
    puertas para dos y compuertas cerradas). Se guarda la última lista y su
    clave para `campo_de`: antes se armaban de nuevo en cada llamada (4 por
    cuadro con 4 jugadores) y la clave eran ~190 tuplas cada vez. Nadie debe
    modificar la lista que devuelve."""
    firma = (id(mundo), id(mundo.paredes), len(mundo.paredes),
             tuple(not p["abierta"] for p in puertas_dobles), tuple(c["cerrada"] for c in compuertas))
    if _obstaculos["firma"] != firma:
        rects = list(mundo.paredes)
        rects += [p["rect"] for p in puertas_dobles if not p["abierta"]]
        rects += [c["rect"] for c in compuertas if c["cerrada"]]
        _obstaculos.update(firma=firma, rects=rects, clave=tuple(tuple(r) for r in rects))
    return _obstaculos["rects"]


def _choque(cajas, c, s):
    """Distancia a la que el rayo (c, s) entra a la primera caja, o infinito.

    Las cajas van relativas al origen del rayo: (x0, y0, x1, y1) con el
    origen en (0, 0). Si el origen queda dentro de una caja, esa se ignora.
    """
    mejor = math.inf
    ic = 1 / c if abs(c) > 1e-9 else None
    is_ = 1 / s if abs(s) > 1e-9 else None
    for x0, y0, x1, y1 in cajas:
        if ic is None:
            if not x0 <= 0 <= x1:
                continue
            entra, sale = -math.inf, math.inf
        else:
            a, b = x0 * ic, x1 * ic
            entra, sale = (a, b) if a < b else (b, a)
        if is_ is None:
            if not y0 <= 0 <= y1:
                continue
        else:
            a, b = y0 * is_, y1 * is_
            if a > b:
                a, b = b, a
            if a > entra:
                entra = a
            if b < sale:
                sale = b
        if 0 < entra <= sale and entra < mejor:
            mejor = entra
    return mejor


def _info_caja(caja):
    """Para descartar rápido una caja: su distancia más corta al origen y el
    abanico de ángulos que ocupa vista desde ahí (centro y mitad del ancho)."""
    x0, y0, x1, y1 = caja
    dx = max(x0, 0, -x1)
    dy = max(y0, 0, -y1)
    cerca = math.hypot(dx, dy)
    angulos = [math.atan2(y, x) for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))]
    centro = math.atan2((y0 + y1) / 2, (x0 + x1) / 2)
    mitad = max(abs((a - centro + math.pi) % (2 * math.pi) - math.pi) for a in angulos)
    return cerca, centro, mitad


def _choque_rapido(info, a, c, s):
    """Como _choque, pero mirando solo las cajas que el rayo de ángulo `a` puede
    tocar, de la más cercana a la más lejana, y parando cuando ya ninguna puede
    quedar más cerca que el choque encontrado. Da lo mismo que _choque.

    (Lo usan las pruebas y quien no tenga un Campo; el Campo usa sus
    "rebanadas", que es lo mismo pero sin revisar todas las cajas.)"""
    mejor = math.inf
    for cerca, centro, mitad, caja in info:
        if cerca >= mejor:
            break
        if abs((a - centro + math.pi) % (2 * math.pi) - math.pi) > mitad + 0.003:
            continue
        d = _choque((caja,), c, s)
        if d < mejor:
            mejor = d
    return mejor


# El círculo alrededor del jugador se parte en REBANADAS de ángulo, y cada
# rebanada guarda las cajas que caen (aunque sea en parte) en ella, de la más
# cercana a la más lejana. Un rayo solo prueba las de su rebanada. Antes cada
# rayo (~200 por campo) miraba el ángulo de todas las cajas cercanas (~40):
# ~8000 vueltas de Python por campo, lo más caro del dibujo con 4 jugadores
# caminando en el PC de Diego (vision.__init__ ~18 ms de 50 en un tirón).
REBANADAS = 96
_ANCHO_REBANADA = 2 * math.pi / REBANADAS
_MARGEN_ANGULO = 0.003


def _rebanadas(info):
    """Lista por rebanada de (cerca, x0, y0, x1, y1), ordenada por `cerca`."""
    dos_pi = 2 * math.pi
    rebanadas = [[] for _ in range(REBANADAS)]
    for cerca, centro, mitad, caja in info:      # (info ya viene por cercanía)
        entrada = (cerca,) + tuple(caja)
        if mitad + _MARGEN_ANGULO >= math.pi:
            for r in rebanadas:
                r.append(entrada)
            continue
        desde = math.floor(((centro - mitad - _MARGEN_ANGULO) % dos_pi) / _ANCHO_REBANADA)
        cuantas = math.floor((2 * (mitad + _MARGEN_ANGULO)) / _ANCHO_REBANADA) + 2
        for k in range(min(cuantas, REBANADAS)):
            rebanadas[(desde + k) % REBANADAS].append(entrada)
    return rebanadas


def _choque_rebanada(lista, c, s):
    """El primer choque del rayo (c, s) con las cajas de `lista` (ver
    _rebanadas), con la prueba de las losas escrita de corrido (sin llamar a
    _choque por cada caja, que en Python cuesta)."""
    mejor = math.inf
    inf = math.inf
    if abs(c) > 1e-9:
        ic = 1 / c
    else:
        ic = None
    if abs(s) > 1e-9:
        is_ = 1 / s
    else:
        is_ = None
    for cerca, x0, y0, x1, y1 in lista:
        if cerca >= mejor:
            break
        if ic is None:
            if not x0 <= 0 <= x1:
                continue
            entra, sale = -inf, inf
        else:
            entra, sale = x0 * ic, x1 * ic
            if entra > sale:
                entra, sale = sale, entra
        if is_ is None:
            if not y0 <= 0 <= y1:
                continue
        else:
            a, b = y0 * is_, y1 * is_
            if a > b:
                a, b = b, a
            if a > entra:
                entra = a
            if b < sale:
                sale = b
        if 0 < entra <= sale and entra < mejor:
            mejor = entra
    return mejor


def _alcance(dist, s, radio):
    """Dónde termina el rayo: en la pared (metiéndose un poco) o en el radio."""
    if dist >= radio:
        return radio
    return min(radio, dist + ENTRA_EN_PARED + ENTRA_EN_PARED_ARRIBA * max(0.0, -s))


class Campo:
    """Lo que ve un jugador desde `origen`: el polígono y las paredes cercanas.

    `cajas` son las paredes cercanas, relativas al origen (ver _choque).
    """

    def __init__(self, origen, rects, radio=RADIO_VISION):
        self.origen = ox, oy = origen
        self.radio = radio
        self.cajas = []
        angulos = [2 * math.pi * i / RAYOS for i in range(RAYOS)]
        for r in rects:
            # Solo las paredes que pueden estar dentro del radio.
            if (r.right < ox - radio or r.left > ox + radio
                    or r.bottom < oy - radio or r.top > oy + radio):
                continue
            caja = (r.left - ox, r.top - oy, r.right - ox, r.bottom - oy)
            if caja[0] < 0 < caja[2] and caja[1] < 0 < caja[3]:
                continue
            self.cajas.append(caja)
            for ex, ey in ((caja[0], caja[1]), (caja[2], caja[1]),
                           (caja[0], caja[3]), (caja[2], caja[3])):
                if ex * ex + ey * ey > radio * radio:
                    continue
                a = math.atan2(ey, ex)
                angulos += (a - ROCE_ESQUINA, a + ROCE_ESQUINA)
        angulos.sort(key=lambda a: a % (2 * math.pi))
        self.info = sorted((_info_caja(caja) + (caja,) for caja in self.cajas),
                           key=lambda i: i[0])
        self.rebanadas = _rebanadas(self.info)

        self.puntos = []
        rebanadas, ancho, dos_pi = self.rebanadas, _ANCHO_REBANADA, 2 * math.pi
        cos, sin = math.cos, math.sin
        for a in angulos:
            c, s = cos(a), sin(a)
            dist = _choque_rebanada(rebanadas[int((a % dos_pi) / ancho) % REBANADAS], c, s)
            dist = _alcance(dist, s, radio)
            self.puntos.append((ox + c * dist, oy + s * dist))

    def ve_punto(self, p):
        """True si p está dentro del radio y sin pared de por medio.

        Es lo mismo que preguntar si cae en el polígono, pero más barato: se
        lanza un solo rayo hacia p.
        """
        dx, dy = p[0] - self.origen[0], p[1] - self.origen[1]
        d = math.hypot(dx, dy)
        if d > self.radio:
            return False
        if d < 1:
            return True
        c, s = dx / d, dy / d
        rebanada = self.rebanadas[int((math.atan2(dy, dx) % (2 * math.pi)) / _ANCHO_REBANADA) % REBANADAS]
        return d <= _alcance(_choque_rebanada(rebanada, c, s), s, self.radio)

    def ve_a(self, rect):
        """True si algo de `rect` (la hitbox de un personaje) se ve.

        Se prueban los pies, el centro y un punto más arriba (donde va la
        cabeza del sprite), para que no desaparezca alguien que asoma por una
        esquina.
        """
        return any(self.ve_punto(p) for p in
                   (rect.center, rect.midbottom, (rect.centerx, rect.top - 40)))


_recientes = {}
_de_dueño = {}             # id del dueño -> (clave de paredes, su último campo)
ESPERA_MAX_PX = 24         # con `puede_esperar`, hasta cuánto puede quedarse atrás


def campo_de(origen, rects, radio=RADIO_VISION, dueño=None, puede_esperar=False):
    """Campo desde `origen`, reusando el último si nada cambió.

    Un jugador quieto (escondido, preso, leyendo un panel) no vuelve a lanzar
    sus rayos cada cuadro mientras no se muevan él ni las puertas.

    Con `dueño` y `puede_esperar`, si ese dueño ya tiene un campo de este
    mismo mapa a menos de ESPERA_MAX_PX, se le devuelve ese en vez de
    calcular uno nuevo. Lo usa la partida con 3-4 jugadores: cada vista
    recalcula día por medio (screens/partida.py). Con 4 caminando, en el PC de
    Diego los 4 campos por cuadro eran lo más caro del dibujo (~12 ms); así
    son 2, y el borde de la sombra va como mucho un cuadro atrás.
    """
    origen = (round(origen[0] / PASO_ORIGEN) * PASO_ORIGEN,
              round(origen[1] / PASO_ORIGEN) * PASO_ORIGEN)
    paredes = _obstaculos["clave"] if rects is _obstaculos["rects"] else tuple(tuple(r) for r in rects)
    clave = (origen, radio, paredes)
    campo = _recientes.get(clave)
    if campo is None and dueño is not None and puede_esperar:
        anterior = _de_dueño.get(id(dueño))
        if (anterior is not None and anterior[0] is paredes and anterior[1].radio == radio
                and abs(anterior[1].origen[0] - origen[0]) <= ESPERA_MAX_PX
                and abs(anterior[1].origen[1] - origen[1]) <= ESPERA_MAX_PX):
            return anterior[1]
    if campo is None:
        if len(_recientes) > 16:
            _recientes.clear()
        campo = _recientes[clave] = Campo(origen, rects, radio)
    if dueño is not None:
        if len(_de_dueño) > 16:      # dueños de partidas viejas
            _de_dueño.clear()
        _de_dueño[id(dueño)] = (paredes, campo)
    return campo

