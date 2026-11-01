"""El árbol de comportamiento de La Sombra (entidades/sombra.py).

La Sombra solo existe mientras la nave está a oscuras (el apagón de
eventos.py): aparece unos segundos después de que se va la luz y se disuelve
cuando alguien prende la caja de fusibles. En la oscuridad solo se le ven
los ojos. Es como los ángeles llorones: mientras una linterna la alumbra no
se puede mover; si le dan la espalda, se acerca. Si la alumbran mucho rato
se esfuma y aparece en otro lado. Si alcanza a alguien le apaga la linterna:
un rato, o hasta que vuelva la luz (Pesadilla, en Inteligente).

Es un árbol binario de decisión, con la misma clase que los demás aliens
(Estructuras/arbol_comportamiento.py). Cada `condicion` tiene que existir en
`Sombra.percibir()` y cada `accion` en `Sombra._ejecutar()`.
"""

ARBOL_SOMBRA = {
    "pregunta": "¿Está fuera de combate?",
    "condicion": "recuperandose",
    "si": {"accion": "DESCANSAR", "texto": "Descansar"},
    "no": {
        "pregunta": "¿Se esfumó (la alumbraron mucho o ya alcanzó a alguien)?",
        "condicion": "esfumada",
        "si": {"accion": "ESFUMARSE", "texto": "Reaparecer en otro lado"},
        "no": {
            "pregunta": "¿La alumbra una linterna?",
            "condicion": "alumbrada",
            "si": {"accion": "CONGELARSE", "texto": "Congelarse"},
            "no": {
                "pregunta": "¿Tiene a alguien al alcance?",
                "condicion": "presa_al_alcance",
                "si": {"accion": "ALCANZAR", "texto": "Alcanzarlo"},
                "no": {
                    "pregunta": "¿Siente a alguien en la oscuridad?",
                    "condicion": "siente_a_alguien",
                    "si": {"accion": "ACECHAR", "texto": "Acercarse a oscuras"},
                    "no": {"accion": "MERODEAR", "texto": "Merodear"},
                },
            },
        },
    },
}
