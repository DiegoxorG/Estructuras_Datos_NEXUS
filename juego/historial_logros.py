"""Los logros que se han conseguido alguna vez en este computador.

Cada partida empieza su árbol de cero (misiones/logros.py); aquí se anota,
al terminar cada ronda, qué logros salieron, para que la opción "Logros" del
menú principal muestre el árbol completo con los que ya se consiguieron en
alguna partida. Se guarda en Guardado/logros.json (fuera de git: cada
computador lleva el suyo). Si el archivo no se puede leer o escribir, el
juego sigue igual: solo no se recuerda.
"""

import json
import os

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA = os.path.join(_RAIZ, "Guardado", "logros.json")


def cargar(ruta=RUTA):
    """{clave: veces que se consiguió}."""
    try:
        with open(ruta, "r", encoding="utf-8") as fh:
            datos = json.load(fh)
        return {str(k): int(v) for k, v in datos.get("conseguidos", {}).items()}
    except (OSError, ValueError, AttributeError, TypeError):
        return {}


def agregar(claves, ruta=RUTA):
    """Suma los logros de una partida al historial. Las pruebas (sin ventana,
    SDL_VIDEODRIVER=dummy) no escriben: si no, llenarían el historial de
    verdad con partidas de mentira."""
    claves = list(claves)
    if not claves or (ruta == RUTA and os.environ.get("SDL_VIDEODRIVER") == "dummy"):
        return
    conseguidos = cargar(ruta)
    for clave in claves:
        conseguidos[clave] = conseguidos.get(clave, 0) + 1
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump({"conseguidos": conseguidos}, fh, ensure_ascii=False, indent=1)
    except OSError:
        pass
