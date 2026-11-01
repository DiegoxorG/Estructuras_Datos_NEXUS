"""El árbol de comportamiento del Guardia (entidades/guardia.py).

El Guardia es enorme, lento y no sale de su sala (la Bahía): protege la
cápsula de escape. Se le puede quitar de en medio de dos formas:

- **Un rato** (Resonante): su Sintonía de señales lo distrae; se va a un
  rincón de la Bahía a escuchar y no ve a nadie mientras dura.
- **Para siempre**: con la fruta de la planta de la Biosfera (la hace crecer
  el Biomante, o cualquiera con abono). Se la lleva a un rincón y se queda
  comiendo. Al que entra con la fruta no lo ataca: se le acerca y espera a
  que se la dé (pero si entra alguien más sin fruta, a ese sí lo ataca).

Es un árbol binario de decisión, como el de los demás aliens
(Estructuras/arbol_comportamiento.py). Cada `condicion` tiene que existir en
`Guardia.percibir()` y cada `accion` en `Guardia._ejecutar()`.
"""

ARBOL_GUARDIA = {
    "pregunta": "¿Le dieron la fruta?",
    "condicion": "comiendo",
    "si": {"accion": "COMER", "texto": "Comer en su rincón (para siempre)"},
    "no": {
        "pregunta": "¿Lo distrajo la Sintonía del Resonante?",
        "condicion": "distraido",
        "si": {"accion": "ESCUCHAR", "texto": "Ir a escuchar la señal"},
        "no": {
            "pregunta": "¿Acaba de atrapar a alguien?",
            "condicion": "recuperandose",
            "si": {"accion": "DESCANSAR", "texto": "Descansar"},
            "no": {
                "pregunta": "¿Tiene a un intruso (sin fruta) al alcance de los brazos?",
                "condicion": "intruso_al_alcance",
                "si": {"accion": "ATRAPAR", "texto": "Atraparlo"},
                "no": {
                    "pregunta": "¿Hay un intruso sin fruta en su sala?",
                    "condicion": "hay_intruso",
                    "si": {"accion": "PERSEGUIR", "texto": "Ir por él (sin salir de la sala)"},
                    "no": {
                        "pregunta": "¿Alguien le trae la fruta?",
                        "condicion": "le_traen_fruta",
                        "si": {"accion": "ESPERAR_FRUTA", "texto": "Acercarse y esperar la fruta"},
                        "no": {
                            "pregunta": "¿Está lejos de su puesto?",
                            "condicion": "lejos_del_puesto",
                            "si": {"accion": "VOLVER", "texto": "Volver frente a la cápsula"},
                            "no": {"accion": "VIGILAR", "texto": "Vigilar la cápsula"},
                        },
                    },
                },
            },
        },
    },
}
