"""Lo que dice la IA de la nave: comenta, avisa y se burla de los prisioneros.

Frases cortas por evento. {rol} se reemplaza por el rol del jugador del que
habla. Joseph (que diseña la IA) y Campo pueden reescribirlas sin tocar código;
si un evento tiene varias, se escoge una al azar.

Eventos que usa el juego (ia_nave.py):
    inicio, pulso_alto, atrapado, codigo_malo, puerta_abierta, consola,
    huida, escondite_revisado, escondite_calmado, rescate,
    ambiente, tutorial, despertar, apagon, alarma, compuerta,
    fin_evento, puerta_doble, luz, sello, eliminado, curacion,
    prueba, infiltrado_expuesto, acusacion_falsa, rumor, desmentido, planos, cambiaformas,
    sabotaje, prisionero_rescatado, dificultad_sube, dificultad_baja,
    sombra, sombra_linterna, guardia_distraido, guardia_come, planta
"""

FRASES = {
    "guardia_distraido": [
        "¿Qué es esa frecuencia, {rol}? Mi Guardia se quedó embobado. Que no les dure.",
        "Interesante, {rol}. El Guardia escucha. Ustedes, corran.",
    ],
    "guardia_come": [
        "¿Le diste de comer a mi Guardia, {rol}? Ahora no se va a mover de ahí.",
        "Traición por una fruta. El Guardia ya no les estorba.",
    ],
    "planta": [
        "La planta de la Biosfera dio fruto. Qué tierno, {rol}.",
        "Una fruta. ¿Para quién será, {rol}?",
    ],
    "sombra": [
        "Algo se mueve en la oscuridad. No le den la espalda.",
        "¿Ven esos ojos? Ella sí los ve a ustedes. Mientras la alumbren, no se mueve.",
    ],
    "sombra_linterna": [
        "La Sombra te apagó la linterna, {rol}. Qué oscuro está, ¿no?",
        "Sin linterna, {rol}. Ahora sí da miedo.",
    ],
    "cambiaformas": [
        "Sorpresa. No todos los prisioneros son lo que parecen, {rol}.",
        "Te dije que no confiaras en cualquier perfil.",
    ],
    "dificultad_sube": [
        "Se están confiando. Despertaré a los aliens un poco más.",
        "Demasiado fácil para ustedes, ¿no? Arreglemos eso.",
    ],
    "dificultad_baja": [
        "Qué pena me dan. Les daré un respiro... uno pequeño.",
        "Mis aliens se aburren de ganar. Que descansen un poco.",
    ],
    "sabotaje": [
        "¿Lo trajiste hasta la cápsula, {rol}? Qué amable. Gracias por el paseo.",
        "Un prisionero que no habla y no se despega de ti. ¿En serio no sospechaste?",
    ],
    "prisionero_rescatado": [
        "{rol} trajo a un prisionero a la cápsula. Ahora todos en NEXUS hablan bien de ustedes. Qué fastidio.",
    ],
    "rumor": [
        "Hay noticias nuevas en NEXUS. Yo que ustedes, las compartiría sin leer.",
        "Mis cuentas favoritas acaban de publicar algo. Créanles, son muy confiables.",
    ],
    "desmentido": [
        "{rol} fue a revisar en persona. Qué aburrido es verificar, ¿no?",
        "Una foto. Qué anticuado, {rol}. Antes la gente creía lo primero que leía.",
    ],
    "planos": [
        "La tripulación les cree. Odio cuando la verdad corre más rápido que mis rumores.",
        "Alguien les pasó los planos de la cápsula. Revisaré mis cuentas falsas.",
    ],
    "prueba": [
        "{rol} anda recogiendo cosas que no son suyas. Interesante.",
        "Esa grabación no debía salir de la bodega. Nadie la va a creer, {rol}.",
    ],
    "infiltrado_expuesto": [
        "Unidad infiltrada comprometida. Mis unidades... no saben qué creer.",
        "¿Cómo lo supieron? Recalibrando a todas las unidades.",
    ],
    "acusacion_falsa": [
        "Acusaron a un inocente. Qué humanos. {rol}, te estoy oyendo.",
        "Error, {rol}. Y ahora todos saben dónde estás.",
    ],
    "inicio": [
        "Bienvenidos, sujetos. No intenten escapar. Es aburrido verlos intentarlo.",
        "Sujetos despiertos. Comenzando estudio del miedo humano.",
    ],
    "pulso_alto": [
        "Sujeto {rol}: su ritmo cardíaco es... interesante.",
        "Detecto un corazón muy acelerado. ¿Nervioso, {rol}?",
        "{rol}, respire. Lo están escuchando.",
    ],
    "atrapado": [
        "Sujeto {rol} recuperado. Gracias por participar.",
        "{rol} vuelve a su celda. Qué previsible.",
        "Otro más. La especie humana no deja de sorprenderme. Poco.",
    ],
    "codigo_malo": [
        "Código incorrecto. Avisando a todos. De nada.",
        "Error. ¿Seguro que saben leer?",
    ],
    "puerta_abierta": [
        "Puerta de seguridad abierta. Eso no estaba en el protocolo.",
        "Vaya. Encontraron el código. Anotado.",
    ],
    "consola": [
        "Alerta: consola de navegación desconectada. Esto se va a reportar.",
        "¿Quién apagó eso? Ah, claro.",
    ],
    "huida": [
        "¡CÁPSULA ACTIVADA! Todas las unidades: no los dejen salir.",
        "Interesante. Ahora sí corran.",
    ],
    "escondite_revisado": [
        "Un casillero no es un buen escondite, {rol}. Se oye todo.",
        "Contando latidos dentro del casillero...",
    ],
    "escondite_calmado": [
        "Falsa alarma. Por ahora.",
        "{rol} mantuvo la calma. Fastidioso.",
    ],
    "rescate": [
        "Liberaron al sujeto {rol}. Trabajo en equipo. Qué molesto.",
    ],
    "tutorial": [
        "Sedación de la tripulación en curso. Cuando todos despierten, mis unidades también.",
    ],
    "despertar": [
        "La tripulación despertó. Buena suerte. Bueno, no.",
        "Fin de la sedación. Mis unidades tienen hambre de datos.",
    ],
    "apagon": [
        "Falla de energía. Mis unidades ven en la oscuridad. Ustedes no.",
        "Apagando luces. Es por ahorro, no por maldad. Un poco por maldad.",
        "Se quemó un fusible. Uno solo. Suerte encontrando cuál.",
    ],
    "eliminado": [
        "Sujeto {rol}: tercera captura. Ya no es un prisionero. Es una muestra.",
        "{rol} queda fuera del experimento. Permanentemente.",
    ],
    "curacion": [
        "La Biomante cura a sus compañeros. Interesante. Molesto, pero interesante.",
    ],
    "sello": [
        "¿Un sello de energía? {rol}, esa pieza era para algo más importante.",
        "Mis unidades no pueden pasar por ahí. Temporalmente, claro.",
    ],
    "luz": [
        "Energía restaurada. Alguien sabe cambiar fusibles. Qué decepción.",
        "Luces encendidas. Disfrútenlas mientras duren.",
    ],
    "alarma": [
        "Alarma general. Todas las unidades: alerta máxima.",
        "Activando alarma. Me aburría.",
    ],
    "compuerta": [
        "Cierre de emergencia en un pasillo. Busquen otro camino.",
        "Compuerta sellada. Qué pena si ibas por ahí.",
    ],
    "fin_evento": [
        "Sistemas normalizados. Por ahora.",
    ],
    "puerta_doble": [
        "Dos sujetos coordinados. Eso no debería pasar.",
    ],
    "ambiente": [
        "Recordatorio: todos los pasillos están vigilados. Casi todos.",
        "La temperatura de la nave es perfecta para el estudio. Para ustedes, no tanto.",
        "Mis unidades no ven bien de lejos. Ups. No debí decir eso.",
        "Sujetos, por favor, dejen de esconderse en los casilleros. Me da pena con ustedes.",
    ],
}
