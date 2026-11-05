"""El árbol de logros de una partida (Estructuras/arbol_logros.py).

Cada logro: clave, nombre, descripcion y sus hijos (los que se abren cuando
se consigue). "rama" se hereda hacia abajo y decide el color. Se pueden
cambiar nombres y descripciones sin tocar código; si se agrega un logro nuevo,
hay que avisarle al juego cuándo se consigue (logros.py).
"""


def L(clave, nombre, descripcion, *hijos, rama=None, compuesto=False):
    d = {"clave": clave, "nombre": nombre, "descripcion": descripcion, "hijos": list(hijos)}
    if rama:
        d["rama"] = rama
    if compuesto:
        # Se consigue con el primero de sus hijos (su descripción lo dice):
        # no queda "por el camino", es un logro de verdad.
        d["compuesto"] = True
    return d


# Orden (oct 29): cada logro va debajo de lo que en una partida pasa ANTES de
# él, para que casi nunca se consiga un hijo antes que su padre. Las raíces de
# cada rama son lo primero que pasa en ese tema (moverse en sigilo, la puerta
# del código, abrir NEXUS, el primer apagón, el primer alien que ves...).
# Si igual pasa (casi en el mismo instante), logros.py espera un momento a
# que llegue el padre antes de dar el hijo.
ARBOL_LOGROS = L(
    "despertar", "Despertar", "Terminar los pasos del tutorial. Los aliens también despiertan.",

    L("sigiloso", "Sigiloso", "Caminar en sigilo o meterte en un escondite.",
      L("pasos_de_gato", "Pasos de gato", "Caminar 30 segundos en sigilo."),
      L("shhh", "Shhh", "Pasar a menos de 100 px del Ciego, en sigilo, sin que te oiga."),
      L("fantasma", "Fantasma", "Que un alien revise tu escondite y no te encuentre."),
      rama="sigilo"),

    L("codigo_roto", "Código roto", "Abrir la puerta con el código.",
      L("a_la_primera", "A la primera", "Abrirla sin fallar el código ni una vez."),
      L("sin_rumbo", "Sin rumbo", "Apagar todas las consolas de navegación.",
        L("sin_rastro", "Sin rastro",
          "Terminar el sabotaje o la cápsula sin que atrapen a nadie en esa fase."),
        L("chatarrero", "Chatarrero", "Llevar las 3 piezas a la cápsula.",
          L("libertad", "Libertad", "Escapar de la nave.",
            L("todos_a_bordo", "Todos a bordo", "Escapar sin que eliminen a nadie."),
            L("nadie_me_vio", "Nadie me vio", "Escapar sin que atrapen a nadie en toda la partida.")))),
      rama="escape"),

    L("conectado", "Conectado", "Abrir NEXUS (en el celular o en una terminal).",
      L("fact_checker", "Fact-checker", "Desmentir un rumor con una foto del lugar.",
        L("perfil_bajo", "Perfil bajo", "Publicar una foto recortada, sin mostrar dónde estás.")),
      L("planos", "Planos en mano", "Ganarse la confianza de la tripulación: los planos de la cápsula."),
      L("cazador_de_bots", "Cazador de bots", "Reportar una cuenta falsa del Cambiaformas."),
      L("perfil_robado", "Perfil robado", "Reportar una publicación suplantada por el Cambiaformas."),
      rama="nexus"),

    L("una_mano", "Una mano", "Ayudar a alguien: cualquiera de los logros de esta rama.",
      L("nadie_atras", "Nadie se queda atrás", "Sacar a un compañero de una celda.",
        L("segunda_oportunidad", "Última oportunidad", "Rescatar a alguien que estaba en su última vida.")),
      L("trabajo_en_equipo", "Trabajo en equipo", "Abrir una puerta para dos."),
      L("rescate", "Rescate", "Llevar a un prisionero hasta la cápsula de escape."),
      L("medico", "Médico de guerra", "Devolverle una vida a un compañero (Regeneración)."),
      rama="equipo", compuesto=True),

    L("a_oscuras", "A oscuras", "Que se vaya la luz: vivir un apagón.",
      L("hagase_la_luz", "Hágase la luz", "Encender la caja de fusibles en un apagón.",
        L("electricista", "Electricista", "Devolver la luz en menos de 30 segundos."),
        L("luz_salvadora", "Luz salvadora", "Prender la caja de fusibles con la Sombra cerca."),
        L("sin_miedo", "Sin miedo a la oscuridad",
          "Que vuelva la luz sin que la Sombra haya alcanzado a nadie.")),
      L("ojos_en_la_oscuridad", "Ojos en la oscuridad", "Ver los ojos de la Sombra en un apagón.",
        L("no_parpadees", "No parpadees", "Alumbrar a la Sombra con la linterna hasta que se esfume.")),
      rama="nave"),

    L("primer_encuentro", "Primer encuentro",
      "Tu primer encuentro con un alien: verlo de cerca (o hackearlo, frenarlo o engañarlo).",
      L("agotalo", "Agótalo", "Que el Cazador se canse persiguiéndote."),
      L("apagado", "Fuera de servicio", "Apagar a un alien con un hackeo (Tecnomante)."),
      L("por_aqui_no", "Por aquí no", "Que un sello frene a un alien (Forjador)."),
      L("titiritero", "Titiritero", "Atraer a un alien con una señal falsa (Resonante)."),
      L("canto_de_sirena", "Canto de sirena", "Distraer al Guardia de la Bahía (Resonante)."),
      L("jardinero", "Mano verde", "Hacer crecer la planta de la Biosfera.",
        L("buen_provecho", "Buen provecho", "Darle la fruta al Guardia para que deje la cápsula.")),
      L("conoce_a_tu_enemigo", "Conoce a tu enemigo",
        "Ver de cerca a todos los tipos de alien: el Cambiaformas, la Sombra y el Guardia incluidos."),
      rama="aliens", compuesto=True),

    L("cara_a_cara", "Cara a cara", "Ver al Cambiaformas como es (revelado o desenmascarado).",
      L("sobreviviente", "Sobreviviente", "Sobrevivir a que el Cambiaformas se revele frente a ti."),
      L("en_manada", "En manada", "Que el Cambiaformas no se atreva porque iban juntos."),
      L("no_me_enganas", "No me engañas", "Hackear al Cambiaformas mientras está disfrazado."),
      L("lobo_con_piel_de_oveja", "Lobo con piel de oveja",
        "Descubrir al Cambiaformas mientras lo llevan creyendo que es un prisionero."),
      rama="cambiaformas"),

    L("algo_no_cuadra", "Algo no cuadra", "Encontrar una prueba del Cambiaformas.",
      L("evidencia", "Evidencia", "Subir una prueba a NEXUS.",
        L("caso_cerrado", "Caso cerrado", "Exponer al Cambiaformas con las 3 pruebas."),
        L("corazonada", "Corazonada", "Acusar al Cambiaformas correcto antes de tener las 3 pruebas."),
        L("acusacion_falsa", "Acusación falsa", "Acusar a un inocente. La nave te delató.")),
      rama="caso"),
    rama="inicio",
)

# Colores de cada rama (cajas del árbol y del aviso).
COLOR_RAMA = {
    "inicio": (240, 242, 252),
    "sigilo": (140, 170, 255),
    "escape": (90, 220, 230),
    "nexus": (233, 120, 200),
    "equipo": (120, 230, 150),
    "nave": (255, 214, 64),
    "aliens": (245, 130, 120),
    "cambiaformas": (190, 150, 255),
    "caso": (255, 152, 40),            # la investigación del Cambiaformas (infiltrado.py)
}
