"""Los niveles de dificultad (dificultad.py). Se pueden editar sin tocar código.

Hay tres fijos (Fácil, Normal y Difícil) e Inteligente. Cada valor de AJUSTES
es una lista con el valor en los niveles 0 a 3:

    0 Fácil · 1 Normal · 2 Difícil · 3 Pesadilla (solo la alcanza Inteligente)

(Antes había un nivel más: Fácil es el viejo Tutorial, Normal el viejo Fácil,
Difícil el viejo Normal y Pesadilla el viejo Difícil, que eran los números de
data/npcs.py, data/nexus.py, data/tipos_alien.py y jugador.py; las pruebas que
juegan sin dificultad siguen usando esos.)

"Inteligente" se mueve entre los niveles según cómo le va al equipo. Los pasos
del tutorial del principio salen en todas las dificultades.
"""

# Lo que se ve en la pantalla de elegir dificultad.
DIFICULTADES = [
    {"clave": "facil", "nombre": "Fácil",
     "descripcion": "Tu primera vez en la nave. Los aliens son lentos y despistados, "
                    "y si te atrapan no pierdes vidas: sales solito de la celda en un "
                    "momento. Una flecha te dice a dónde ir: explora con calma, lee "
                    "NEXUS y aprende cómo funciona todo."},
    {"clave": "normal", "nombre": "Normal",
     "descripcion": "La experiencia recomendada para jugar con amigos. Los aliens se "
                    "mueven más lento y les cuesta verte y oírte. Tienen muchas vidas y "
                    "la flecha los guía. El Cambiaformas tarda en aparecer y es paciente. "
                    "Si te encierran, al rato logras escapar por tu cuenta."},
    {"clave": "dificil", "nombre": "Difícil",
     "descripcion": "Para los que ya conocen la nave. Los aliens son una amenaza de "
                    "verdad, pero hay margen para equivocarse: cuatro vidas. Sin flecha "
                    "a la misión: hay que conocer la nave. Si te encierran, solo sales si un "
                    "compañero te libera: si encierran a todos, se acabó."},
    {"clave": "inteligente", "nombre": "Inteligente",
     "descripcion": "La nave los observa. Empieza como Normal y se va ajustando según "
                    "cómo jueguen: si avanzan rápido y nadie cae, los aliens se ponen "
                    "más listos y agresivos (incluso más que en Difícil); si les va "
                    "mal, les da un respiro. Nunca se juega igual dos veces."},
]
POR_DEFECTO = "normal"       # el que sale marcado al abrir la pantalla

#               Fácil   Normal  Difícil Pesadilla
AJUSTES = {
    # Aliens (multiplican lo de data/tipos_alien.py)
    "vel_aliens":        [0.70,   0.82,  0.92,  1.00],
    "vision_aliens":     [0.70,   0.80,  0.90,  1.00],
    "oido_aliens":       [0.70,   0.80,  0.90,  1.00],
    # Cambiaformas (ms)
    "cf_espera_ms":      [150000, 90000, 60000, 40000],   # antes de empezar a cazar
    "cf_calma_ms":       [60000,  45000, 35000, 25000],   # descanso después de atrapar
    "cf_traicion_ms":    [8000,   6000,  4800,  3500],    # a solas con él antes de que se revele
    "cf_trampas":        [2.0,    1.6,   1.25,  1.00],    # multiplica el tiempo entre suplantaciones
    "cf_estudio":        [2.0,    1.5,   1.25,  1.00],    # multiplica cuánto estudia a su presa
    # NEXUS
    "rumor_cada":        [1.60,   1.40,  1.20,  1.00],    # multiplica el tiempo entre rumores
    "prob_creer":        [0.30,   0.33,  0.39,  0.45],    # prob. de que un gris se crea un rumor
    # La Sombra (sale en los apagones): si alcanza a alguien le apaga la
    # linterna. ¿Hasta que vuelva la luz? (>= 0.5 sí; si no, `sombra_apaga_ms`).
    "sombra_hasta_luz":  [0,      0,     0,     1],
    "sombra_apaga_ms":   [4000,   6000,  10000, 12000],
    # Qué caja de fusibles falla en un apagón (misiones/eventos.py): 0 = la más
    # cercana a los jugadores, 1 = la más lejana. Empieza en `fusible_lejania`
    # y sube `fusible_avance` a medida que avanzan en la misión.
    "fusible_lejania":   [0.0,    0.12,  0.3,   0.5],
    "fusible_avance":    [0.35,   0.42,  0.5,   0.55],
}

# Se eligen al empezar y no cambian durante la partida (ni en Inteligente,
# para que la raya de los planos y los corazones no se muevan).
# No hay límite de tiempo: esto es solo lo que debería durar una misión bien
# jugada, para que Inteligente sepa si el equipo va rápido o lento.
RITMO_MISION_S = 420
VIDAS = {"facil": 3, "normal": 5, "dificil": 4, "inteligente": 3}
VIDAS_INFINITAS = {"facil"}          # atrapar no quita vidas
UMBRAL_PLANOS = {"facil": 0.60, "normal": 0.70, "dificil": 0.75, "inteligente": 0.70}
# Fuga: el que está en una celda fuerza la reja y sale solo después de este
# tiempo (None = solo lo saca un compañero). Mientras alguien pueda fugarse,
# que todos estén encerrados no es derrota. Inteligente: según su nivel.
FUGA_MS = {"facil": 8000, "normal": 20000, "dificil": None, "pesadilla": None}
# La flecha amarilla al objetivo. Inteligente la quita desde Difícil. (La azul
# del rumor que se va a verificar y la roja de la caja de fusibles en un
# apagón salen siempre.)
FLECHA = {"facil": True, "normal": True, "dificil": False}
# La ventana que presenta a cada tipo de alien la primera vez (pausa el juego).
PRESENTAR_ALIENS = {"facil", "normal", "dificil", "inteligente"}

# Inteligente: el "director" revisa cada tanto cómo va el equipo y mueve el
# nivel (0 = Fácil, 1 = Normal, 2 = Difícil, 3 = Pesadilla).
NIVEL_INICIAL = 1.0
NIVEL_MIN, NIVEL_MAX = 0.0, 3.0
REVISAR_CADA_MS = 4000
PASO_MAX = 0.07              # lo más que cambia en una revisión (~1 nivel por minuto)
VENTANA_CAPTURAS_MS = 90000  # cuenta las capturas de este último rato
NOMBRES_NIVEL = [(0.5, "Fácil"), (1.5, "Normal"), (2.5, "Difícil"), (99, "Pesadilla")]
