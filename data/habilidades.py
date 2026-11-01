"""Árboles de habilidades de cada rol (árbol binario, uno por jugador).

Son los de la lámina de Anny: una habilidad base por rol y dos hijas. Cada nodo
es un diccionario que `Estructuras/arbol_habilidades.py` convierte en un
NodoHabilidad. La raíz se tiene desde el inicio de la ronda; después el
jugador **escoge una de las dos hijas** con su tecla de habilidades y pierde la
otra hasta que termine la partida.

La base es gratis; la segunda habilidad cuesta COSTO_NIVEL_2 puntos **del
equipo** (mision.Equipo): lo que gana cualquiera de la tripulación suma, y se
gasta al desbloquear. Abrir la puerta de la prisión ya alcanza para una.

`uso` dice cómo se usa la habilidad en partida, y lo lee acciones_rol.py:
- "pasiva": funciona sola todo el tiempo.
- "estacion": se usa con la tecla de interactuar frente a una terminal o un
  panel del mapa.
- "activa": se usa con la tecla de habilidad, en cualquier lado, y después
  tiene un tiempo de recarga (`recarga_s`).

Las claves importan: acciones_rol.py pregunta `arbol.tiene("ESCANEO")`. No se
cambian sin actualizar ese archivo.
"""

COSTO_NIVEL_2 = 15


TECNOMANTE = {
    "clave": "CONEXION",
    "nombre": "Conexión digital",
    "descripcion": ("Le permite acceder a los sistemas electrónicos de la nave "
                    "y visualizar su estado."),
    "costo": 0,
    "detalle_puntos": "En una terminal: muestra el mapa de la nave con los aliens.",
    "uso": "estacion",
    "hijos": [
        {
            "clave": "HACKEO",
            "nombre": "Hackeo básico",
            "descripcion": ("Desbloquea puertas, terminales y sistemas de "
                            "seguridad simples."),
            "costo": COSTO_NIVEL_2,
            "detalle_puntos": "En una terminal: apaga a los aliens cercanos unos segundos. +10",
            "uso": "estacion",
            "hijos": [],
        },
        {
            "clave": "ESCANEO",
            "nombre": "Escaneo de sistemas",
            "descripcion": ("Revela información del entorno, como cámaras, "
                            "puertas y señales de vida cercanas."),
            "costo": COSTO_NIVEL_2,
            "detalle_puntos": "Tecla de habilidad: mapa con los aliens y sus conos, en cualquier lado.",
            "uso": "activa",
            "recarga_s": 18,
            "hijos": [],
        },
    ],
}

FORJADOR = {
    "clave": "INGENIO",
    "nombre": "Ingenio mecánico",
    "descripcion": ("Le permite interactuar con la maquinaria de la nave, "
                    "reconocer piezas útiles y preparar reparaciones."),
    "costo": 0,
    "detalle_puntos": "Ve y recoge las piezas sueltas del mapa.",
    "uso": "pasiva",
    "hijos": [
        {
            "clave": "REPARACION",
            "nombre": "Reparación básica",
            "descripcion": ("Restaura el funcionamiento de sistemas dañados, como "
                            "generadores, puertas y paneles."),
            "costo": COSTO_NIVEL_2,
            "detalle_puntos": "En un panel dañado: lo repara con 1 pieza y levanta su sello. +15",
            "uso": "estacion",
            "recarga_s": 25,
            "hijos": [],
        },
        {
            "clave": "FABRICACION",
            "nombre": "Fabricación improvisada",
            "descripcion": ("Crea herramientas y dispositivos usando piezas "
                            "encontradas en la nave."),
            "costo": COSTO_NIVEL_2,
            "detalle_puntos": "Tecla de habilidad: con 1 pieza arma un señuelo que atrae a los aliens.",
            "uso": "activa",
            "recarga_s": 6,
            "hijos": [],
        },
    ],
}

BIOMANTE = {
    "clave": "VINCULO",
    "nombre": "Vínculo vital",
    "descripcion": ("Le permite percibir, canalizar y transferir energía vital "
                    "entre seres vivos."),
    "costo": 0,
    "detalle_puntos": "Ve el pulso y las vidas de sus compañeros encima de ellos.",
    "uso": "pasiva",
    "hijos": [
        {
            "clave": "REGENERACION",
            "nombre": "Regeneración dirigida",
            "descripcion": ("Cura heridas específicas y detiene efectos "
                            "negativos."),
            "costo": COSTO_NIVEL_2,
            "detalle_puntos": ("Tecla de habilidad: devuelve una vida a los compañeros "
                               "cercanos (cada 40 s), calma su pulso y le quita amenaza "
                               "a un escondite revisado. +5"),
            "uso": "activa",
            "recarga_s": 14,
            "hijos": [],
        },
        {
            "clave": "IMPULSO",
            "nombre": "Impulso energético",
            "descripcion": ("Transfiere energía vital a un compañero, restaurando su "
                            "energía para que pueda seguir actuando."),
            "costo": COSTO_NIVEL_2,
            "detalle_puntos": ("Tecla de habilidad: recarga al instante la habilidad de los "
                               "compañeros cercanos (también la Reparación) y reinicia todas "
                               "las terminales para un nuevo hackeo. +5"),
            "uso": "activa",
            "recarga_s": 20,
            "hijos": [],
        },
    ],
}

RESONANTE = {
    "clave": "SINTONIA",
    "nombre": "Sintonía de señales",
    "descripcion": ("Le permite percibir, interpretar y trabajar con múltiples "
                    "señales que circulan por la nave."),
    "costo": 0,
    "detalle_puntos": ("Flechas en el borde de su pantalla hacia los aliens que no ve, y "
                       "los pasos (rosados) de los que tiene cerca pero no ve."),
    "uso": "pasiva",
    "hijos": [
        {
            "clave": "INTERCEPCION",
            "nombre": "Interceptación básica",
            "descripcion": ("Capta y analiza transmisiones de la nave, descubriendo "
                            "mensajes ocultos o información relevante."),
            "costo": COSTO_NIVEL_2,
            "detalle_puntos": "Tecla de habilidad: ve la ruta y la decisión de cada alien por 8 s.",
            "uso": "activa",
            "recarga_s": 16,
            "hijos": [],
        },
        {
            "clave": "EMISION",
            "nombre": "Emisión modulada",
            "descripcion": ("Transmite y modifica señales para comunicarse, "
                            "confundir, distraer o establecer contacto."),
            "costo": COSTO_NIVEL_2,
            "detalle_puntos": ("Tecla de habilidad: abre el mapa y escoges dónde cae una "
                               "señal falsa que los aliens van a revisar."),
            "uso": "activa",
            "recarga_s": 15,
            "hijos": [],
        },
    ],
}


ARBOLES_POR_ROL = {
    "Tecnomante": TECNOMANTE,
    "Forjador": FORJADOR,
    "Biomante": BIOMANTE,
    "Resonante": RESONANTE,
}
