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


def extraer(valor, profundidad=4):
    """`valor` en forma de JSON, o NADA si no se puede (o no vale la pena)."""
    if valor is None or isinstance(valor, (bool, int, str)):
        return valor
    if isinstance(valor, float):
        # Dos decimales alcanzan para dibujar y achican mucho el JSON.
        return round(valor, 2)
    if _es_rect(valor):
        return {"R": [int(valor.x), int(valor.y), int(valor.w), int(valor.h)]}
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
            if not isinstance(clave, str) or clave in SALTAR:
                continue
            e = extraer(v, profundidad - 1)
            if e is not NADA:
                salida[clave] = e
        # Las claves "R" y "S" solas se confundirían con un Rect o un set.
        if len(salida) == 1 and next(iter(salida)) in ("R", "S"):
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
            return set(a_python(v) for v in datos["S"])
        return {k: a_python(v) for k, v in datos.items()}
    if isinstance(datos, list):
        return [a_python(v) for v in datos]
    return datos


def _mezclar(actual, datos):
    """El valor nuevo para algo que hoy vale `actual` (reusa lo que se pueda:
    los dicts y listas del espejo pueden tener objetos que no viajan)."""
    if isinstance(datos, dict) and len(datos) == 1 and "R" in datos and _es_rect(actual):
        actual.update(*datos["R"])
        return actual
    if isinstance(datos, dict) and not (len(datos) == 1 and next(iter(datos)) in ("R", "S")):
        if isinstance(actual, dict):
            for clave, v in datos.items():
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
