"""Lo que dicen las notas que hay tiradas por la nave (estilo Resident Evil).

Cortas a propósito: en la feria nadie lee un párrafo. Campo puede reescribirlas
sin tocar código; dónde está cada nota se pone con el editor de mapa (tecla de
la herramienta "Notas"), y el texto se les asigna en este orden.

Hay dos tipos de notas: las normales (de historia, con NOTAS) y las de código,
que vienen con la puerta con código (en el editor, herramienta "Puerta": después
de ponerla, los clics ponen sus notas). Una de las de código que se alcanzan
desde la prisión dice el código (se sortea en cada partida, y el código también,
mision.py: por eso NOTA_CODIGO lleva {codigo}, y {puerta} es su color); las otras dicen algo de
NOTAS_CODIGO_VACIAS. Si el mapa no tiene notas de código, va en una normal.
"""

NOTA_CODIGO = {
    "titulo": "Nota arrugada",
    "texto": ("Si alguien encuentra esto: vi al guardia marcar la puerta {puerta}. "
              "El código es {codigo}. No dejen que los oigan."),
}

# Las notas de código que no salieron sorteadas (en orden; si faltan, se repiten).
NOTAS_CODIGO_VACIAS = [
    {"titulo": "Nota rota",
     "texto": "Anoté el código aquí, pero se borró con la humedad. Debe haber otra copia."},
    {"titulo": "Papel con números tachados",
     "texto": "Todos tachados. Alguien lo cambió. Sigan buscando."},
    {"titulo": "Recordatorio del guardia",
     "texto": "No dejar el código por ahí. (Lo dejé en otro lado, por si acaso.)"},
    {"titulo": "Hoja arrancada",
     "texto": "Solo quedó la mitad. La otra mitad tenía el código."},
]

NOTAS = [
    {"titulo": "Diario del prisionero 7",
     "texto": "Día 3. Nos miden el pulso todo el tiempo. Cuando te asustas, te encuentran."},
    {"titulo": "Etiqueta alienígena",
     "texto": "Sujeto 4: reacciona al ruido. Recomendación: aislar en celda."},
    {"titulo": "Mensaje rayado en la pared",
     "texto": "Las consolas moradas controlan la navegación. Si las apagan, no pueden seguirnos."},
    {"titulo": "Manual de la cápsula",
     "texto": "Cápsula de emergencia: requiere 3 piezas de repuesto y reparación manual."},
    {"titulo": "Papel quemado",
     "texto": "Uno de los que escriben en NEXUS no es humano. Lo vi cambiar de cara."},
]
