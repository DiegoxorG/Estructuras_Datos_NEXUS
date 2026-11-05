"""Pasar el estado de los objetos del juego por la red, sin pygame en el cable.

El servidor tiene los objetos de verdad (Jugador, Alien, Mision...) y el
cliente tiene otro juego "espejo" con objetos de la misma clase (ver
cliente_servidor/espejo.py). Aquí está lo que copia los DATOS de unos a otros:

- `extraer(valor)`: lo convierte en algo que JSON entiende. Los números, los
  textos, las listas y los diccionarios pasan tal cual; un `pygame.Rect` va
  como {"R": [x, y, w, h]} y un set como {"S": [...]}. Las referencias a otros
  objetos (al alien que lo persigue, al juego...) NO se mandan: cada lado
  tiene los suyos y no tiene sentido copiar un objeto entero por la red.
- `aplicar(destino, datos)`: escribe esos datos encima de un objeto del
  espejo, sin cambiar lo que no vino (las imágenes, los árboles, el sprite).
- `diferencias(antes, ahora)`: solo las claves que cambiaron (las
  instantáneas delta, ver docs/cliente_servidor.md).

Nada de esto importa pygame más que para reconocer los Rect.
"""

NADA = object()          # "esto no se manda" (un objeto, una función...)

# Atributos que nunca se mandan: son de cada lado (las teclas de este puesto,
# el spawn) o son referencias a otros objetos grandes.
SALTAR = {"juego", "mundo", "equipo", "arbol", "personaje", "linterna", "teclas",
          "controles", "animaciones", "rng", "aleatorio", "ruta_config"}


def _es_rect(valor):
    return type(valor).__name__ in ("Rect", "FRect")


# Objetos que viajan como REFERENCIA (nombre de la clase -> (marca, atributo
# que los identifica)): una publicación del celular, un jugador, un alien. Del
# otro lado se cambian por el objeto del espejo que tiene esa identidad
# (RESOLVER, lo pone cliente_servidor/espejo.py). Antes se perdían: una
# opción del celular ("post", publicación) llegaba como ("post", None) y el
# dibujo se caía; un dict con jugadores de clave (red.vistas[jugador]) no
# viajaba. Como clave de un dict van como texto: "@J:1".
REFERENCIAS = {"Publicacion": ("P", "id"), "Jugador": ("J", "puesto"),
               "Alien": ("A", "nombre"), "Sombra": ("A", "nombre"), "Cambiaformas": ("A", "nombre"),
               "Guardia": ("A", "nombre")}
MARCAS = {marca for marca, _ in REFERENCIAS.values()}
RESOLVER = None          # fn(marca, identidad) -> objeto del espejo (o None)


def _referencia(valor):
    """(marca, identidad) si `valor` viaja como referencia, o None."""
    regla = REFERENCIAS.get(type(valor).__name__)
    if regla is None:
        return None
    identidad = getattr(valor, regla[1], None)
    return None if identidad is None else (regla[0], identidad)


def _resolver(marca, identidad):
    return RESOLVER(marca, identidad) if RESOLVER is not None else None


def _clave_texto(clave):
    """La clave de un dict como texto (las referencias como "@J:1"), o None."""
    if isinstance(clave, str):
        return clave
    ref = _referencia(clave)
    if ref is not None:
        return f"@{ref[0]}:{ref[1]}"
    return None


def _clave_python(clave):
    """Lo inverso: "@J:1" -> el jugador del espejo (o la clave tal cual)."""
    if isinstance(clave, str) and clave.startswith("@") and clave[1:2] in MARCAS and clave[2:3] == ":":
        identidad = clave[3:]
        if identidad.lstrip("-").isdigit():
            identidad = int(identidad)
        objeto = _resolver(clave[1], identidad)
        return objeto if objeto is not None else clave
    return clave


def _es_ref(datos):
    return (isinstance(datos, dict) and len(datos) == 1 and next(iter(datos)) in MARCAS)


# Objetos chicos de DATOS que viajan enteros, con su clase: {"O": [clase,
# {atributos}]}. Del otro lado se arma uno de esa clase (o se actualiza el
# que ya había). Sin esto se perdían: el minijuego del escondite no le
# aparecía al cliente, ni el disfraz nuevo del Cambiaformas. clase ->
# (módulo, atributos que viajan; None = todos los de datos).
CLASES = {
    "MinijuegoLatidos": ("entidades.minijuego_latidos", None),
    # De la apariencia solo QUIÉN es: la animación (reloj, dirección, paso)
    # la lleva el cliente (espejo.py), si no tironearía con cada instantánea.
    "Apariencia": ("entidades.npcs", ("estilo", "usuario", "numero", "sprite")),
    # La red social de NEXUS: cambia en la partida (bots nuevos, cuentas que se
    # reportan y se borran, colores). Sin esto la pestaña Red del cliente se
    # quedaba como al principio.
    "Grafo": ("Estructuras.grafo", None),
}


def _objeto(valor, profundidad):
    regla = CLASES.get(type(valor).__name__)
    if regla is None:
        return None
    _, campos = regla
    datos = atributos(valor, profundidad=max(1, profundidad - 1))
    if campos is not None:
        datos = {k: v for k, v in datos.items() if k in campos}
    return {"O": [type(valor).__name__, datos]}


def _es_objeto(datos):
    return (isinstance(datos, dict) and len(datos) == 1 and "O" in datos
            and isinstance(datos["O"], list) and len(datos["O"]) == 2 and datos["O"][0] in CLASES)


def _armar(datos, actual=None):
    """{"O": [clase, atributos]} -> un objeto de esa clase (`actual` si ya lo es)."""
    clase, atribs = datos["O"]
    if actual is None or type(actual).__name__ != clase:
        import importlib
        cls = getattr(importlib.import_module(CLASES[clase][0]), clase)
        actual = cls.__new__(cls)
        if clase == "Apariencia":
            # Lo que su __init__ pone y no viaja (la animación es del cliente).
            from Movimiento.Personaje import DireccionSuave
            actual.__dict__.update({"reloj_ms": 0, "direccion": "south", "fase": 0.0,
                                    "moviendose": False, "_giro": DireccionSuave()})
    # Cada atributo se pone de nuevo (no se mezcla): si en el servidor se
    # borró algo de un dict (un nodo del grafo), aquí también.
    for clave, v in atribs.items():
        try:
            setattr(actual, clave, a_python(v))
        except (AttributeError, TypeError):
            pass
    return actual


def extraer(valor, profundidad=4):
    """`valor` en forma de JSON, o NADA si no se puede (o no vale la pena)."""
    if valor is None or isinstance(valor, (bool, int, str)):
        return valor
    if isinstance(valor, float):
        # Dos decimales alcanzan para dibujar y achican mucho el JSON.
        return round(valor, 2)
    if _es_rect(valor):
        return {"R": [int(valor.x), int(valor.y), int(valor.w), int(valor.h)]}
    ref = _referencia(valor)
    if ref is not None:
        return {ref[0]: ref[1]}
    if profundidad <= 0:
        return NADA
    objeto = _objeto(valor, profundidad)
    if objeto is not None:
        return objeto
    if profundidad <= 0:
        return NADA
    if isinstance(valor, (set, frozenset)):
        elementos = [extraer(v, 0) for v in valor]
        if any(e is NADA for e in elementos):
            return NADA
        return {"S": sorted(elementos, key=str)}
    if isinstance(valor, (list, tuple)):
        if len(valor) > 400:
            return NADA            # (un camino entero, una lista de puntos...)
        # Los objetos dentro de una lista (los NPC, las publicaciones del
        # celular...) van con sus datos, un nivel menos de profundidad.
        return [None if e is NADA else e for e in
                ((atributos(v, profundidad=profundidad - 2) if hasattr(v, "__dict__") and profundidad > 2
                  else extraer(v, profundidad - 1)) for v in valor)]
    if isinstance(valor, dict):
        salida = {}
        for clave, v in valor.items():
            clave = _clave_texto(clave)
            if clave is None or clave in SALTAR:
                continue
            e = extraer(v, profundidad - 1)
            if e is not NADA:
                salida[clave] = e
        # Las claves "R" y "S" (o una marca de referencia) solas se
        # confundirían con un Rect, un set o una referencia.
        if len(salida) == 1 and next(iter(salida)) in ("R", "S", "O", *MARCAS):
            return NADA
        return salida
    return NADA


def atributos(objeto, saltar=(), profundidad=4):
    """Los atributos de un objeto que se pueden mandar (los que empiezan con
    _ son internos y no se dibujan)."""
    salida = {}
    for clave, v in vars(objeto).items():
        if clave.startswith("_") or clave in SALTAR or clave in saltar:
            continue
        e = extraer(v, profundidad)
        if e is not NADA:
            salida[clave] = e
    return salida


def a_python(datos):
    """Lo inverso de extraer (para lo que no existía en el espejo)."""
    if isinstance(datos, dict):
        if len(datos) == 1 and "R" in datos and isinstance(datos["R"], list):
            import pygame
            return pygame.Rect(*datos["R"])
        if len(datos) == 1 and "S" in datos and isinstance(datos["S"], list):
            salida = set()
            for v in datos["S"]:
                try:
                    salida.add(a_python(v))
                except TypeError:          # (algo que no se puede meter en un set)
                    pass
            return salida
        if _es_ref(datos):
            marca, identidad = next(iter(datos.items()))
            return _resolver(marca, identidad)
        if _es_objeto(datos):
            return _armar(datos)
        return {_clave_python(k): a_python(v) for k, v in datos.items()}
    if isinstance(datos, list):
        return [a_python(v) for v in datos]
    return datos


def _mezclar(actual, datos):
    """El valor nuevo para algo que hoy vale `actual` (reusa lo que se pueda:
    los dicts y listas del espejo pueden tener objetos que no viajan)."""
    if isinstance(datos, dict) and len(datos) == 1 and "R" in datos and _es_rect(actual):
        actual.update(*datos["R"])
        return actual
    if _es_ref(datos):
        return a_python(datos)
    if _es_objeto(datos):
        return _armar(datos, actual)
    if isinstance(datos, dict) and not (len(datos) == 1 and next(iter(datos)) in ("R", "S")):
        if isinstance(actual, dict):
            for clave, v in datos.items():
                clave = _clave_python(clave)
                actual[clave] = _mezclar(actual.get(clave), v)
            return actual
        if actual is not None and hasattr(actual, "__dict__"):
            aplicar(actual, datos)
            return actual
        return a_python(datos)
    if isinstance(datos, list):
        if isinstance(actual, (list, tuple)) and len(actual) == len(datos):
            # (un None del otro lado es "esto no se pudo mandar": se deja el de aquí)
            nuevos = [a if d is None and a is not None else _mezclar(a, d)
                      for a, d in zip(actual, datos)]
            if isinstance(actual, list):
                actual[:] = nuevos
                return actual
            return tuple(nuevos)
        if isinstance(actual, list) and any(isinstance(d, dict) for d in datos) and (
                not actual or any(hasattr(a, "__dict__") for a in actual)):
            # Eran objetos del otro lado (logros, publicaciones...): aquí no se
            # pueden armar, así que se deja la lista del espejo como está.
            return actual
        nuevos = a_python(datos)
        return tuple(nuevos) if isinstance(actual, tuple) else nuevos
    return a_python(datos)


def aplicar(destino, datos):
    """Escribe `datos` (de `atributos`) encima de `destino`."""
    for clave, v in datos.items():
        try:
            actual = getattr(destino, clave, None)
            if isinstance(getattr(type(destino), clave, None), property):
                continue           # (calculado: se arregla solo)
            setattr(destino, clave, _mezclar(actual, v))
        except (AttributeError, TypeError, ValueError):
            pass


def diferencias(antes, ahora):
    """Las claves de `ahora` que no valen lo mismo en `antes` (un nivel).
    Una clave que desapareció se manda como None."""
    salida = {clave: v for clave, v in ahora.items() if antes.get(clave, NADA) != v}
    for clave in antes:
        if clave not in ahora:
            salida[clave] = None
    return salida
