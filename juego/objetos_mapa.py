"""Lo que hay puesto en el mapa: dónde aparecen los jugadores, por dónde
patrullan los aliens y dónde están los escondites, terminales, paneles, piezas,
terminales NEXUS y todo lo de la misión.

Todo eso vive en `Hitboxes/<mapa>_objetos.json`, que se arma con el editor
visual (`python Editores/editor_mapa.py`), así que cambiar el mapa no requiere
tocar código. Si el archivo no existe, o le falta alguna parte, esa parte queda
vacía (un mapa sin cápsula no tiene misión, sin rutas no tiene aliens...).

Qué mapa usa el juego lo dice `Hitboxes/mapa_activo.json`, que también se
cambia desde el editor (tecla M).

Las coordenadas van de 0 a 1 sobre el tamaño del mapa, como en el resto del
proyecto, para que sigan sirviendo si cambia la escala.
"""

import copy
import json
import os

# La raíz del proyecto (este archivo está en una subcarpeta).
_RAIZ_PROYECTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


RAIZ = _RAIZ_PROYECTO
CARPETA = os.path.join(RAIZ, "Hitboxes")
ARCHIVO_MAPA_ACTIVO = os.path.join(CARPETA, "mapa_activo.json")
MAPA_POR_DEFECTO = "Nave"
VERSION = 1

# En False no se lee ningún archivo: el mapa queda vacío (sin aliens ni misión).
# Sirve para probar algo sin depender de lo que alguien guardó con el editor.
USAR_ARCHIVOS = True

# Las partes del archivo, en el orden en que las muestra el editor.
#
# Las de la misión (celdas, puerta, notas, consolas, cápsula, consumibles) y
# las terminales NEXUS no tienen valores de fábrica: un mapa sin cápsula no
# tiene misión y se juega como antes, por tiempo (ver mision.py).
#
# `puertas_codigo`: las puertas que se abren con un código; cada una trae sus
# notas de código (en una sale su código). La primera es la de la prisión (la
# fase 1). `puerta` es el formato viejo (una sola): se lee y pasa a ser la
# primera de `puertas_codigo`.
#
# `tipos_aliens` va de la mano con `rutas_aliens`: el tipo del alien de cada
# ruta (data/tipos_alien.py). Las `compuertas` las cierra un evento aleatorio
# (eventos.py) y las `puertas_dobles` se abren con dos jugadores a la vez
# (puertas.py).
PARTES = ("spawn", "rutas_aliens", "tipos_aliens", "escondites", "terminales", "paneles",
          "piezas", "celdas", "puertas_codigo", "puerta", "notas", "consolas", "capsula", "consumibles",
          "nexus", "compuertas", "puertas_dobles", "fusibles", "pruebas", "salas",
          "guardia", "planta")


def ruta_archivo(mapa):
    return os.path.join(CARPETA, f"{mapa}_objetos.json")


# -- Mapa activo -----------------------------------------------------------------------

def mapa_activo():
    """Nombre del fondo (Imagenes/Fondos/<nombre>.png) con el que se juega."""
    if not USAR_ARCHIVOS:
        return MAPA_POR_DEFECTO
    try:
        with open(ARCHIVO_MAPA_ACTIVO, "r", encoding="utf-8") as fh:
            nombre = json.load(fh).get("mapa")
        return nombre or MAPA_POR_DEFECTO
    except (OSError, ValueError, AttributeError):
        return MAPA_POR_DEFECTO


def fijar_mapa_activo(mapa):
    os.makedirs(CARPETA, exist_ok=True)
    with open(ARCHIVO_MAPA_ACTIVO, "w", encoding="utf-8") as fh:
        json.dump({"mapa": mapa}, fh, indent=2, ensure_ascii=False)


# -- Valores por defecto: un mapa vacío ---------------------------------------------------

def por_defecto():
    return {
        "version": VERSION,
        "spawn": None,     # None = alrededor del centro del mapa
        "rutas_aliens": [],
        "tipos_aliens": [],  # vacío = todos del tipo por defecto (Vigía)
        "escondites": [],
        "terminales": [],
        "paneles": [],
        "piezas": [],
        "celdas": [],
        "puertas_codigo": [],  # [{"rx", "ry", "ancho", "alto", "notas": [[rx, ry], ...], "notas_dificil": [...]}]; la 1.ª, la de la prisión
        "notas": [],
        "consolas": [],
        "capsula": None,     # [rx, ry]
        "consumibles": [],
        "nexus": [],
        "compuertas": [],     # [{"rx", "ry", "ancho", "alto"}]
        "puertas_dobles": [], # [{"rx", "ry", "ancho", "alto", "paneles": [[rx, ry], [rx, ry]]}]
        "fusibles": [],       # cajas de fusibles: sin ellas no hay apagones
        "pruebas": [],        # dónde pueden caer las pruebas del infiltrado (se usan 3)
        "salas": [],          # [{"nombre", "rx", "ry", "ancho", "alto"}]: el nombre en el HUD
        "guardia": None,      # [rx, ry]: el puesto del Guardia (misiones/guardia.py), en la sala de la cápsula
        "planta": None,       # [rx, ry]: la planta que da la fruta para el Guardia
    }


# -- Cargar y guardar ----------------------------------------------------------------------

def cargar(mapa=None, ruta=None):
    """Los objetos del mapa: lo del archivo, y lo que falte, de data/."""
    datos = por_defecto()
    if not USAR_ARCHIVOS and ruta is None:
        return datos
    ruta = ruta or ruta_archivo(mapa or mapa_activo())
    try:
        with open(ruta, "r", encoding="utf-8") as fh:
            guardado = json.load(fh)
    except (OSError, ValueError):
        return datos
    for parte in PARTES:
        if parte in guardado:
            datos[parte] = guardado[parte]
    return normalizar(datos)


def guardar(mapa, datos, ruta=None):
    ruta = ruta or ruta_archivo(mapa)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    limpio = normalizar(copy.deepcopy(datos))
    limpio["version"] = VERSION
    limpio["mapa"] = mapa
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(limpio, fh, indent=2, ensure_ascii=False)
    return ruta


def normalizar(datos):
    """Redondea, recorta a 0-1 y les pone clave a los objetos que no tengan."""
    def r(v):
        return round(min(1.0, max(0.0, float(v))), 4)

    if datos.get("spawn"):
        datos["spawn"] = [r(datos["spawn"][0]), r(datos["spawn"][1])]
    datos["rutas_aliens"] = [[[r(x), r(y)] for x, y in ruta] for ruta in datos.get("rutas_aliens", [])]
    datos["piezas"] = [[r(x), r(y)] for x, y in datos.get("piezas", [])]
    for parte in ("celdas", "notas", "consolas", "consumibles", "nexus", "fusibles", "pruebas"):
        datos[parte] = [[r(x), r(y)] for x, y in datos.get(parte) or []]
    for unico in ("capsula", "guardia", "planta"):
        if datos.get(unico):
            datos[unico] = [r(datos[unico][0]), r(datos[unico][1])]
        else:
            datos[unico] = None
    def rect_normal(puerta):
        return {"rx": r(puerta["rx"]), "ry": r(puerta["ry"]),
                "ancho": round(min(0.3, max(0.005, float(puerta.get("ancho", 0.02)))), 4),
                "alto": round(min(0.3, max(0.005, float(puerta.get("alto", 0.07)))), 4)}

    # Puertas con código (y el formato viejo, una sola "puerta", pasa a ser la primera).
    puertas = list(datos.get("puertas_codigo") or [])
    vieja = datos.pop("puerta", None)
    if vieja and not puertas:
        puertas = [dict(vieja, notas=datos.pop("notas_codigo", None) or [])]
    datos.pop("notas_codigo", None)
    limpias = []
    for puerta in puertas:
        limpia = rect_normal(puerta)
        limpia["notas"] = [[r(x), r(y)] for x, y in (puerta.get("notas") or [])]
        # Las que solo aparecen en Difícil (e Inteligente), donde nadie sale
        # solo de la celda: para que el código de una puerta que en Fácil y
        # Normal está adentro de la prisión, en Difícil se lea afuera.
        limpia["notas_dificil"] = [[r(x), r(y)] for x, y in (puerta.get("notas_dificil") or [])]
        limpias.append(limpia)
    datos["puertas_codigo"] = limpias
    datos["compuertas"] = [rect_normal(c) for c in datos.get("compuertas") or []]
    dobles = []
    for doble in datos.get("puertas_dobles") or []:
        limpia = rect_normal(doble)
        limpia["paneles"] = [[r(x), r(y)] for x, y in (doble.get("paneles") or [])[:2]]
        dobles.append(limpia)
    datos["puertas_dobles"] = dobles
    # Las salas pueden ser grandes (no tienen el tope de 0.3 de las puertas).
    salas = []
    for sala in datos.get("salas") or []:
        salas.append({"nombre": str(sala.get("nombre") or "").strip() or "Sala",
                      "rx": r(sala["rx"]), "ry": r(sala["ry"]),
                      "ancho": round(min(1.0, max(0.002, float(sala.get("ancho", 0.05)))), 4),
                      "alto": round(min(1.0, max(0.002, float(sala.get("alto", 0.05)))), 4)})
    datos["salas"] = salas

    # Un tipo por ruta: se rellena con el tipo por defecto o se recorta. Uno
    # que no es de ruta (o que ya no existe, como el Rastreador) pasa a ser el
    # de por defecto.
    from data.tipos_alien import ORDEN_TIPOS, TIPO_POR_DEFECTO
    tipos = [t if t in ORDEN_TIPOS else TIPO_POR_DEFECTO for t in datos.get("tipos_aliens") or []]
    n = len(datos["rutas_aliens"])
    datos["tipos_aliens"] = (tipos + [TIPO_POR_DEFECTO] * n)[:n]
    for parte, prefijo, nombre in (("escondites", "escondite", "Casillero"),
                                   ("terminales", "terminal", "Terminal"),
                                   ("paneles", "panel", "Panel dañado")):
        usadas = set()
        for i, obj in enumerate(datos.get(parte, [])):
            obj["rx"], obj["ry"] = r(obj["rx"]), r(obj["ry"])
            obj.setdefault("nombre", nombre)
            clave = obj.get("clave")
            if not clave or clave in usadas:
                n = i + 1
                while f"{prefijo}_{n}" in usadas:
                    n += 1
                clave = f"{prefijo}_{n}"
            obj["clave"] = clave
            usadas.add(clave)
    # Cada panel dañado puede traer su sello: la barrera que levanta al
    # repararlo (ver acciones_rol._reparar_panel).
    for panel in datos.get("paneles", []):
        if panel.get("sello"):
            panel["sello"] = rect_normal(panel["sello"])
        else:
            panel.pop("sello", None)
    return datos
