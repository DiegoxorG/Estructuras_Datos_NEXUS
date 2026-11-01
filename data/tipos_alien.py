"""Los tipos de alien: mismo árbol de comportamiento, distintos sentidos.

Todos los aliens recorren el mismo árbol (data/comportamiento_alien.py). Lo que
cambia entre un tipo y otro son los números con los que responden las
preguntas del árbol: qué tan lejos ven, qué tan bien oyen, qué tan rápido van.
Así el árbol se queda igual y cada tipo se juega distinto.

    Vigía       lento, pero ve muy lejos con un cono angosto. Hay que
                cruzarle por detrás o esperar a que mire a otro lado.
    Ciego       no ve nada; oye el doble. Solo "siente" a quien tiene casi
                encima. Contra él sirve caminar en sigilo y no asustarse.
    Cazador     el más rápido (más que los jugadores), pero se cansa: después
                de perseguir un rato tiene que parar a recuperarse.

El tipo de cada alien se escoge en el editor de mapa (herramienta de rutas,
tecla T). Campo puede ajustar estos números sin tocar el resto del código.

Además están los dos únicos, que no patrullan rutas: el Cambiaformas
(cambiaformas.py) y la Sombra (sombra.py). El Rastreador (el alien "de
siempre", sin nada especial) se quitó en oct 2026: nadie lo usaba.
"""

import math


TIPOS_ALIEN = {
    "vigia": {
        "nombre": "Vigía",
        "descripcion": "Lento, pero ve muy lejos.",
        "vel_patrulla": 1.2, "vel_investigar": 1.9, "vel_perseguir": 2.8,
        "alcance_vision": 480, "medio_angulo": math.radians(24),
        "oido": 0.7,          # multiplica el radio de ruido de los jugadores
        "tacto": 0,           # a esta distancia lo "siente" aunque no vea
        "aguante_ms": 0,      # 0 = no se cansa
        "cansancio_ms": 0,
        "color": (120, 170, 240), "borde": (30, 50, 90),
    },
    "ciego": {
        "nombre": "Ciego",
        "descripcion": "No ve: oye el doble.",
        "vel_patrulla": 1.5, "vel_investigar": 2.7, "vel_perseguir": 3.1,
        "alcance_vision": 0, "medio_angulo": 0,
        "oido": 1.9, "tacto": 95, "aguante_ms": 0, "cansancio_ms": 0,
        "color": (205, 200, 185), "borde": (80, 70, 60),
    },
    "cazador": {
        "nombre": "Cazador",
        "descripcion": "Muy rápido, pero se cansa.",
        "vel_patrulla": 2.0, "vel_investigar": 2.9, "vel_perseguir": 4.5,
        "alcance_vision": 280, "medio_angulo": math.radians(45),
        "oido": 1.0, "tacto": 0, "aguante_ms": 2600, "cansancio_ms": 2400,
        "color": (235, 115, 90), "borde": (90, 30, 20),
    },
    # Única (sombra.py): no patrulla rutas; solo existe en los apagones. Las
    # velocidades son las de acercarse (ACECHAR usa vel_perseguir).
    "sombra": {
        "nombre": "Sombra",
        "descripcion": "Sale en los apagones; la luz la congela.",
        "vel_patrulla": 1.6, "vel_investigar": 2.4, "vel_perseguir": 3.0,
        "alcance_vision": 0, "medio_angulo": 0,
        "oido": 0, "tacto": 0, "aguante_ms": 0, "cansancio_ms": 0,
        "color": (176, 150, 236), "borde": (24, 16, 36),
    },
    # Único (entidades/guardia.py): no patrulla rutas ni sale de su sala (la
    # Bahía). Grande y lento: protege la cápsula. Lo ve todo dentro de su sala.
    "guardia": {
        "nombre": "Guardia",
        "descripcion": "Protege la cápsula y no sale de la Bahía.",
        "vel_patrulla": 1.4, "vel_investigar": 1.8, "vel_perseguir": 2.6,
        "alcance_vision": 0, "medio_angulo": math.pi,
        "oido": 0, "tacto": 0, "aguante_ms": 0, "cansancio_ms": 0,
        "color": (126, 132, 112), "borde": (30, 32, 26),
    },
    # Único (cambiaformas.py): no patrulla rutas, se disfraza de prisionero.
    # Usa su propio árbol (data/comportamiento_cambiaformas.py).
    "cambiaformas": {
        "nombre": "Cambiaformas",
        "descripcion": "Se disfraza de prisionero y se revela de cerca.",
        "vel_patrulla": 1.3, "vel_investigar": 2.6, "vel_perseguir": 4.7,
        "alcance_vision": 0, "medio_angulo": math.pi,
        "oido": 1.2, "tacto": 0, "aguante_ms": 0, "cansancio_ms": 0,
        "color": (120, 40, 140), "borde": (30, 10, 40),
    },
}

TIPO_POR_DEFECTO = "vigia"         # una ruta sin tipo (o con uno que ya no existe)
ORDEN_TIPOS = ["vigia", "ciego", "cazador"]     # los de ruta (tecla T del editor)


def datos_tipo(tipo):
    return TIPOS_ALIEN.get(tipo, TIPOS_ALIEN[TIPO_POR_DEFECTO])
