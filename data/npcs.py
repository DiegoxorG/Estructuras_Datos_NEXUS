"""Los prisioneros que caminan por la nave (npcs.py) y el Cambiaformas
(cambiaformas.py). Se pueden editar sin tocar código.

Cada prisionero que camina es una cuenta de NEXUS (data/nexus.py: CUENTAS):
el mismo nodo del grafo. Su color en NEXUS (gris, verde o rojo) decide cómo
trata a los jugadores cuando pasan cerca.
"""

NPCS_POR_PARTIDA = 7       # cuántas cuentas de NEXUS salen a caminar (una es el Cambiaformas)

# Aspecto provisional (hasta que haya arte): un muñeco simple dibujado con
# formas, con overol de prisionero. Cada prisionero toma un estilo de aquí.
# "pelo": "corto", "largo", "calvo" o "gorro".
ESTILOS = [
    {"overol": (214, 120, 52), "piel": (236, 196, 160), "pelo": (60, 40, 30), "tipo_pelo": "corto"},
    {"overol": (120, 128, 140), "piel": (196, 140, 100), "pelo": (25, 20, 20), "tipo_pelo": "largo"},
    {"overol": (200, 100, 60), "piel": (150, 100, 70), "pelo": (20, 18, 18), "tipo_pelo": "calvo"},
    {"overol": (110, 140, 120), "piel": (240, 210, 180), "pelo": (200, 160, 70), "tipo_pelo": "largo"},
    {"overol": (150, 120, 160), "piel": (120, 80, 55), "pelo": (35, 30, 30), "tipo_pelo": "corto"},
    {"overol": (190, 150, 70), "piel": (225, 180, 145), "pelo": (140, 60, 40), "tipo_pelo": "gorro"},
    {"overol": (100, 120, 170), "piel": (210, 160, 120), "pelo": (90, 90, 95), "tipo_pelo": "corto"},
]

VELOCIDAD_NPC = 1.25
ESPERA_NPC_MS = (1500, 5000)        # cuánto se quedan quietos al llegar a un punto
RADIO_CHARLA = 120                  # a esta distancia de un jugador te hablan
ENFRIAMIENTO_CHARLA_MS = 22000      # cada cuánto puede hablar el mismo prisionero
DURACION_BURBUJA_MS = 3600
PROB_DELATAR = 0.5                  # un rojo que te ve, a veces avisa a los aliens

# Lo que dice cada uno. {alien}, {direccion}, {usuario} y {lugar} se cambian.
FRASES_VERDE_ALIEN = [
    "Vi al {alien} hacia el {direccion}. Cuidado.",
    "El {alien} anda por el {direccion}. Yo no iría por ahí.",
]
FRASES_VERDE_CAMBIAFORMAS = [
    "Ojo con {usuario}: no me contestó y su nombre se veía raro.",
    "Hay algo raro con {usuario}: no se le oye el corazón.",
]
FRASES_VERDE_RUMOR = [
    "Dicen algo de {lugar} en NEXUS. Yo lo verificaría antes de creerlo.",
]
FRASES_VERDE = ["Gracias por desmentir lo de NEXUS. Les creo.", "Ánimo, ya casi salimos."]
FRASES_GRIS = ["...", "¿Tú también estás perdido?", "No sé a quién creerle en NEXUS.",
               "Tengo hambre.", "¿Qué día es hoy?"]
FRASES_ROJO = ["¡Aquí está {usuario}! ¡Aliens, aquí!", "No me hables. NEXUS dice que ustedes mienten."]

# -- Rescate ----------------------------------------------------------------------------
FRASE_PIDE_RESCATE = "¿Me sacas de aquí? Llévame a la cápsula."
RADIO_HABLAR = 85               # a esta distancia, interactuar le pregunta "¿vienes conmigo?"
DISTANCIA_SEGUIR = 70           # un prisionero que te sigue va a esta distancia
RADIO_RESCATE_CAPSULA = 110     # a esta distancia del borde de la cápsula, queda a salvo
PUNTOS_RESCATE = 10
FRASE_ACEPTA = "¡Sí, vamos!"
FRASE_ESPERA = "Está bien, te espero aquí."
RADIO_SOLTAR = 130              # junto al que te sigue, interactuar le dice que te espere
ESPERA_SOLTADO_MS = 45000       # cuánto se queda quieto esperándote antes de volver a pasear
FRASE_DUDA = "No sé si creerles... primero convénzanme en NEXUS."
FRASE_NIEGA = "¡Ni loco! NEXUS dice que ustedes mienten."
FRASE_RESCATADO = "¡Me rescataron! Confíen en ellos, dicen la verdad."
FRASES_ADVIERTE_ESCOLTA = ["¿Por qué vas con {usuario}? Esa no es la persona que conozco...",
                           "Cuidado: {usuario} no me reconoció hace un rato."]

# -- Cambiaformas -----------------------------------------------------------------------
DISTANCIA_REVELARSE = 165       # se revela cuando su presa está así de cerca (y lo ve)
DISTANCIA_COMPANIA = 260        # si la presa tiene un compañero así de cerca, espera
VISION = 650                    # ve en todas direcciones (no tiene cono)
ESPERA_INICIAL_MS = 40000       # al empezar la partida merodea un rato antes de cazar
# No es impulsivo: antes de atacar "estudia" a su presa. Pasa cerca (como un
# prisionero más), se aleja, ronda, vuelve a pasar... y solo cuando ya la
# conoce y la encuentra sola y desprevenida (con el celular, en una consola,
# leyendo, de espaldas a él) se revela.
ESTUDIO_NECESARIO_MS = (14000, 24000)   # cuánto tiene que haberla visto de cerca (al azar)
RADIO_ESTUDIO = 300             # a esta distancia (y viéndola) la está estudiando
DISTANCIA_PASADA = 120          # en una "pasada" se acerca hasta aquí y se va
PASADA_MAX_MS = 9000            # si no logra acercarse en este tiempo, vuelve a rondar
RONDA_MS = (5000, 11000)        # cuánto ronda lejos entre una pasada y otra
RONDA_DISTANCIA = (350, 750)    # a qué distancia de la presa ronda
DE_ESPALDAS = 110               # grados: más que esto entre a dónde mira y él = de espaldas
ABURRIRSE_MS = 20000            # si la presa no se queda sola en este rato, se va lejos
ALEJARSE_CALMA_MS = (25000, 40000)   # y se olvida de cazar este tiempo
OLVIDA_TRAS_FALLAR = 0.5        # si se revela y falla, olvida esta parte de lo aprendido
CALMA_TRAS_FALLAR_MS = 15000    # y espera esto antes de volver a cazar
ENFRIAMIENTO_CAZA_MS = 25000    # después de atrapar a alguien, descansa de cazar
TRANSFORMARSE_MS = 750          # el susto: se transforma ahí y le da ese tiempo a la presa
RAFAGA_MS = 4200                # cuánto dura su carrera después de revelarse
PISTA_PRESA_MS = 6000           # cada cuánto "sabe" dónde está su presa (es persistente)
RECUERDA_ESCONDITE_MS = 25000   # si la vio esconderse hace menos, va a revisar
HUIDA_MAX_MS = 12000
EXPUESTO_MS = 60000             # al exponerlo en NEXUS no se puede disfrazar este rato
DESCANSO_TRAS_FALLAR_MS = 3000
# Suplantación en NEXUS: disfrazado de alguien, publica con su cuenta para
# atraer a un jugador a un lugar y emboscarlo. {lugar} se cambia.
TRAMPAS = [
    "Encontré una pieza para la cápsula en {lugar}. ¡Vengan rápido!",
    "Hay una salida secreta en {lugar}, la acabo de ver.",
    "Estoy herido en {lugar}, por favor alguien venga a ayudarme.",
]
PRIMERA_TRAMPA_MS = 60000
TRAMPA_CADA_MS = (55000, 80000)
DESENMASCARADO_MS = 20000       # al reportar la suplantación, este rato sin disfraz
# Escoltado (lo llevan creyendo que es un prisionero): traiciona.
DISTANCIA_SEGUIR_CF = 38        # camina demasiado pegado (una pista)
TRAICION_SOLO_MS = 3500         # si quien lo lleva se queda solo este rato, ataca
RADIO_SABOTAJE = 120            # a esta distancia del borde de la cápsula, la sabotea
DANIO_SABOTAJE = 0.4            # cuánto de la reparación deshace al sabotear (0-1)
SUSURRO_RADIO = 240             # disfrazado, se le oye un susurro a esta distancia
SUSURRO_CADA_MS = 5000
MANADA_MS = 2500                # cuánto tiene que esperar por verlos juntos (logro)
GLITCH_CADA_MS = 3600           # su nombre falla un instante cada tanto (una pista)
GLITCH_DURA_MS = 320
