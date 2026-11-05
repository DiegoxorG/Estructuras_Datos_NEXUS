"""Las dos pantallas previas a la partida: cuántos juegan y quién es quién.

Hay dos pasos:

1. **Cantidad**: 2, 3 o 4. Ese número decide en cuántas partes se corta la
   pantalla, así que se pregunta antes que nada.
2. **Roles**: la pantalla ya se ve partida y cada jugador escoge el suyo desde
   su propia sección, con sus propias teclas. Dos no pueden repetir rol: el que
   ya está tomado se ve tachado y no se puede confirmar.

La sección de cada jugador se dibuja con el mismo `calcular_viewports` de la
partida, así que desde la selección ya se ve qué trozo de pantalla le va a
tocar a cada uno.
"""

import os

import pygame

from data.roles import ROLES, MINIMO_JUGADORES, MAXIMO_JUGADORES
from juego.fuentes import fuente_de_tamano
from juego.mandos import nombre_boton, tipo_de, PUESTOS_CON_MANDO


COLOR_FONDO = (26, 28, 48)
COLOR_TITULO = (255, 214, 64)
COLOR_TEXTO = (245, 246, 252)
COLOR_TENUE = (168, 176, 214)
COLOR_BORDE = (120, 132, 190)
COLOR_SELECCION_FONDO = (52, 57, 92)
COLOR_TOMADO = (104, 108, 132)
COLOR_LISTO = (96, 188, 118)

MARGEN = 18

# Franja de arriba reservada para el aviso de "faltan N por elegir". Las
# secciones que tocan el borde superior empiezan su contenido por debajo, o el
# aviso se monta encima del título del jugador de la derecha.
ALTO_AVISO = 34


# --------------------------------------------------------------------------
# Paso 1: cuántos juegan
# --------------------------------------------------------------------------

def render_cantidad(screen, seleccionado):
    """Menú de 2, 3 o 4 jugadores. `seleccionado` es el índice en OPCIONES."""
    screen.fill(COLOR_FONDO)
    ancho, alto = screen.get_size()

    f_titulo = fuente_de_tamano(max(22, min(40, ancho // 38)))
    f = fuente_de_tamano(max(15, min(24, ancho // 62)))

    titulo = f_titulo.render("¿CUÁNTOS JUEGAN?", True, COLOR_TEXTO)
    screen.blit(titulo, titulo.get_rect(center=(ancho // 2, int(alto * 0.22))))

    aviso = f.render("Con teclado o con mando, cada uno con su parte de la pantalla.",
                     True, COLOR_TENUE)
    screen.blit(aviso, aviso.get_rect(center=(ancho // 2, int(alto * 0.22) + 46)))

    # El recuadro cubre las DOS líneas de la opción (el número y el reparto de
    # pantalla). Antes solo envolvía la primera y su borde inferior cruzaba por
    # encima de la segunda, tachándola.
    linea = f.get_linesize()
    alto_opcion = linea * 2 + 16
    separacion = 26
    y = int(alto * 0.42)
    rects = []

    for i, cantidad in enumerate(OPCIONES):
        elegido = (i == seleccionado)
        ancho_caja = min(int(ancho * 0.6), 560)
        caja = pygame.Rect(0, 0, ancho_caja, alto_opcion)
        caja.center = (ancho // 2, y + alto_opcion // 2)
        rects.append(caja)

        if elegido:
            pygame.draw.rect(screen, COLOR_SELECCION_FONDO, caja)
            pygame.draw.rect(screen, COLOR_TITULO, caja, 2)

        texto = f.render(f"{cantidad} jugadores", True,
                         COLOR_TITULO if elegido else COLOR_TEXTO)
        screen.blit(texto, texto.get_rect(center=(ancho // 2, caja.y + 8 + linea // 2)))

        reparto = f.render(DESCRIPCION[cantidad], True, COLOR_TENUE)
        screen.blit(reparto, reparto.get_rect(center=(ancho // 2,
                                                      caja.y + 8 + linea + linea // 2)))
        y += alto_opcion + separacion

    pie = f.render("[W/S] o flechas para elegir    [ENTER] continuar    [ESC] volver al menú",
                   True, (194, 216, 248))
    screen.blit(pie, pie.get_rect(center=(ancho // 2, alto - 40)))
    return rects


OPCIONES = list(range(MINIMO_JUGADORES, MAXIMO_JUGADORES + 1))

DESCRIPCION = {
    2: "pantalla partida en dos, lado a lado",
    3: "dos arriba y uno abajo, a lo ancho",
    4: "pantalla partida en cuatro",
}


# --------------------------------------------------------------------------
# Paso 1.5: la dificultad (data/dificultad.py)
# --------------------------------------------------------------------------

COLOR_DIFICULTAD = {
    "facil": (96, 210, 120),
    "normal": (255, 214, 64),
    "dificil": (245, 110, 100),
    "inteligente": (190, 150, 255),
}


def render_dificultad(screen, seleccionado):
    """Las dificultades en columna y, abajo, qué cambia la elegida."""
    from data.dificultad import DIFICULTADES
    from screens.paneles import partir_lineas
    screen.fill(COLOR_FONDO)
    ancho, alto = screen.get_size()
    f_titulo = fuente_de_tamano(max(22, min(40, ancho // 38)))
    f = fuente_de_tamano(max(15, min(24, ancho // 62)))

    titulo = f_titulo.render("DIFICULTAD", True, COLOR_TEXTO)
    screen.blit(titulo, titulo.get_rect(center=(ancho // 2, int(alto * 0.14))))

    linea = f.get_linesize()
    alto_opcion = linea + 16
    separacion = 12
    ancho_caja = min(int(ancho * 0.5), 460)
    y = int(alto * 0.14) + 48
    rects = []
    for i, d in enumerate(DIFICULTADES):
        elegido = i == seleccionado
        color = COLOR_DIFICULTAD.get(d["clave"], COLOR_TITULO)
        caja = pygame.Rect(0, 0, ancho_caja, alto_opcion)
        caja.midtop = (ancho // 2, y)
        rects.append(caja)
        if elegido:
            pygame.draw.rect(screen, COLOR_SELECCION_FONDO, caja)
            pygame.draw.rect(screen, color, caja, 2)
        pygame.draw.circle(screen, color, (caja.x + 22, caja.centery), 7)
        texto = f.render(d["nombre"], True, color if elegido else COLOR_TEXTO)
        screen.blit(texto, texto.get_rect(center=caja.center))
        y += alto_opcion + separacion

    # Qué trae la elegida.
    d = DIFICULTADES[seleccionado]
    ancho_desc = min(int(ancho * 0.7), 720)
    renglones = partir_lineas(d["descripcion"], f, ancho_desc - 32)
    caja = pygame.Rect(0, 0, ancho_desc, len(renglones) * linea + 24)
    caja.midtop = (ancho // 2, y + 14)
    pygame.draw.rect(screen, (34, 37, 62), caja, border_radius=6)
    pygame.draw.rect(screen, COLOR_DIFICULTAD.get(d["clave"], COLOR_BORDE), caja, 1, border_radius=6)
    for k, renglon in enumerate(renglones):
        img = f.render(renglon, True, COLOR_TENUE)
        screen.blit(img, img.get_rect(midtop=(ancho // 2, caja.y + 12 + k * linea)))

    pie = f.render("[W/S] o flechas para elegir    [ENTER] continuar    [ESC] volver",
                   True, (194, 216, 248))
    screen.blit(pie, pie.get_rect(center=(ancho // 2, alto - 40)))
    return rects


# --------------------------------------------------------------------------
# Paso 2: qué rol juega cada uno
# --------------------------------------------------------------------------

BOTON_ESQUEMA = ["E", "Enter", "A", "A"]     # con qué se toma cada control


def _boton_esquema(esquema, accion="interactuar"):
    """El botón para tomar el control: en los mandos, el de ese mando
    (A en Xbox, Cruz en PlayStation)."""
    if esquema in PUESTOS_CON_MANDO:
        return nombre_boton(accion, tipo_de(esquema))
    return BOTON_ESQUEMA[esquema]


def render_controles(screen, esquemas, nombres, libres, conectados):
    """Cada jugador escoge su control presionando su botón de aceptar.

    `esquemas`: el de cada jugador (None = todavía no); `nombres`: el nombre
    de cada esquema; `libres`: los que se pueden escoger; `conectados`: si
    cada esquema de mando tiene un mando conectado.
    """
    screen.fill(COLOR_FONDO)
    ancho, alto = screen.get_size()
    f_titulo = fuente_de_tamano(max(22, min(40, ancho // 38)))
    f = fuente_de_tamano(max(15, min(24, ancho // 62)))
    f_chica = fuente_de_tamano(max(13, min(19, ancho // 80)))
    t = pygame.time.get_ticks()

    titulo = f_titulo.render("¿CON QUÉ JUEGA CADA UNO?", True, COLOR_TEXTO)
    screen.blit(titulo, titulo.get_rect(center=(ancho // 2, int(alto * 0.16))))
    for i, linea in enumerate(("Cada jugador presiona el botón de su control, en orden.",
                               "Presiónalo otra vez para soltarlo. Dos no pueden usar el mismo.")):
        img = f_chica.render(linea, True, COLOR_TENUE)
        screen.blit(img, img.get_rect(center=(ancho // 2, int(alto * 0.16) + 44 + i * (f_chica.get_linesize() + 2))))

    # Un renglón por jugador.
    ancho_caja = min(int(ancho * 0.56), 620)
    alto_caja = f.get_linesize() + 22
    y = int(alto * 0.33)
    siguiente = esquemas.index(None) if None in esquemas else None
    for jugador, esquema in enumerate(esquemas):
        caja = pygame.Rect(0, 0, ancho_caja, alto_caja)
        caja.midtop = (ancho // 2, y)
        if esquema is not None:
            pygame.draw.rect(screen, (34, 48, 40), caja)
            pygame.draw.rect(screen, COLOR_LISTO, caja, 2)
            derecha, color = nombres[esquema], COLOR_LISTO
        elif jugador == siguiente:
            pygame.draw.rect(screen, COLOR_SELECCION_FONDO, caja)
            pygame.draw.rect(screen, COLOR_TITULO, caja, 2)
            derecha = "presiona tu botón" + "." * (1 + (t // 400) % 3)
            color = COLOR_TITULO
        else:
            pygame.draw.rect(screen, COLOR_BORDE, caja, 1)
            derecha, color = "esperando", COLOR_TOMADO
        izq = f.render(f"Jugador {jugador + 1}", True, COLOR_TEXTO)
        screen.blit(izq, izq.get_rect(midleft=(caja.x + 18, caja.centery)))
        der = f.render(derecha, True, color)
        screen.blit(der, der.get_rect(midright=(caja.right - 18, caja.centery)))
        y += alto_caja + 12

    # Los controles: cuál está libre, tomado o sin conectar.
    y += 26
    ancho_ficha = min(int(ancho * 0.2), 230)
    sep = 14
    total = len(nombres) * ancho_ficha + (len(nombres) - 1) * sep
    x = (ancho - total) // 2
    for esquema, nombre in enumerate(nombres):
        ficha = pygame.Rect(x, y, ancho_ficha, f.get_linesize() * 2 + 18)
        if esquema in esquemas:
            estado, color, borde = f"Jugador {esquemas.index(esquema) + 1}", COLOR_LISTO, COLOR_LISTO
        elif esquema in libres:
            estado, color, borde = f"[{_boton_esquema(esquema)}] tomar", (194, 216, 248), COLOR_BORDE
        else:
            estado, color, borde = "sin conectar", COLOR_TOMADO, COLOR_TOMADO
        pygame.draw.rect(screen, (24, 26, 44), ficha)
        pygame.draw.rect(screen, borde, ficha, 2)
        img = f.render(nombre, True, COLOR_TEXTO if esquema in libres else COLOR_TOMADO)
        screen.blit(img, img.get_rect(midtop=(ficha.centerx, ficha.y + 8)))
        img = f_chica.render(estado, True, color)
        screen.blit(img, img.get_rect(midtop=(ficha.centerx, ficha.y + 12 + f.get_linesize())))
        x += ancho_ficha + sep

    # El "volver" de cada mando conectado: "B", "Círculo" o "B/Círculo".
    volver = []
    for esquema in PUESTOS_CON_MANDO:
        if esquema < len(conectados) and conectados[esquema]:
            nombre = _boton_esquema(esquema, "volver")
            if nombre not in volver:
                volver.append(nombre)
    pie = f_chica.render(f"[ESC] o {'/'.join(volver) or 'B'}: volver a la dificultad", True, (194, 216, 248))
    screen.blit(pie, pie.get_rect(center=(ancho // 2, alto - 40)))


def render_roles(screen, viewports, seleccion):
    """Dibuja la selección de rol de cada jugador en su propia sección.

    `seleccion` es una lista con un dict por jugador: cursor (índice del rol
    sobre el que está), listo (si ya confirmó) y rol (el nombre confirmado).
    """
    screen.fill((18, 16, 30))

    tomados = {s["rol"] for s in seleccion if s["listo"]}
    for indice, vista in enumerate(viewports):
        if indice >= len(seleccion):
            break
        # Solo las secciones pegadas al borde superior ceden espacio al aviso.
        tope = ALTO_AVISO if vista.top < ALTO_AVISO else 0
        _seccion_jugador(screen, vista, indice, seleccion[indice], tomados, tope)

    _separadores(screen, viewports)

    f = fuente_de_tamano(max(13, min(20, screen.get_width() // 80)))
    faltan = sum(1 for s in seleccion if not s["listo"])
    if faltan:
        mensaje = f"Faltan {faltan} por elegir" if faltan > 1 else "Falta uno por elegir"
        color = COLOR_TENUE
    else:
        mensaje = "Todos listos. Empezando…"
        color = COLOR_LISTO
    # Arriba y no abajo: con cuatro jugadores el borde inferior lo ocupan las
    # pistas de teclas de los dos de abajo, y el aviso se les montaba encima.
    etiqueta = f.render(mensaje, True, color)
    caja = etiqueta.get_rect(center=(screen.get_width() // 2, ALTO_AVISO // 2))
    fondo = pygame.Surface((etiqueta.get_width() + 28, etiqueta.get_height() + 12),
                           pygame.SRCALPHA)
    fondo.fill((18, 16, 30, 235))
    screen.blit(fondo, (caja.x - 14, caja.y - 6))
    pygame.draw.rect(screen, COLOR_BORDE,
                     (caja.x - 14, caja.y - 6, caja.width + 28, caja.height + 12), 1)
    screen.blit(etiqueta, caja)


_retratos = {}


def _retrato(rol, alto_max):
    """El personaje del rol, de frente y quieto, recortado y agrandado."""
    clave = (rol, alto_max)
    if clave not in _retratos:
        ruta = os.path.join("Imagenes", "Personajes", rol, f"{rol}_idle_south.png")
        imagen = None
        try:
            hoja = pygame.image.load(ruta).convert_alpha()
            lado = hoja.get_height()
            cuadro = hoja.subsurface((0, 0, min(lado, hoja.get_width()), lado))
            caja = cuadro.get_bounding_rect()
            recorte = cuadro.subsurface(caja).copy()
            escala = max(1, min(3, alto_max // max(1, recorte.get_height())))
            imagen = pygame.transform.scale(recorte, (recorte.get_width() * escala,
                                                      recorte.get_height() * escala))
        except (pygame.error, OSError, ValueError):
            imagen = None
        _retratos[clave] = imagen
    return _retratos[clave]


def _dibujar_retrato(screen, vista, rol, tope, color):
    imagen = _retrato(rol, max(40, min(190, vista.height // 3)))
    if imagen is None:
        return
    x = vista.right - MARGEN - imagen.get_width()
    y = vista.y + tope + MARGEN
    sombra = pygame.Rect(0, 0, imagen.get_width(), 14)
    sombra.midtop = (x + imagen.get_width() // 2, y + imagen.get_height() - 8)
    pygame.draw.ellipse(screen, (14, 15, 28), sombra)
    screen.blit(imagen, (x, y))
    pygame.draw.line(screen, color, (x, y + imagen.get_height() + 8),
                     (x + imagen.get_width(), y + imagen.get_height() + 8), 2)


def _seccion_jugador(screen, vista, indice, estado, tomados, tope=0):
    f = fuente_de_tamano(max(12, min(20, vista.width // 34)))
    f_titulo = fuente_de_tamano(max(14, min(26, vista.width // 26)))
    paso = f.get_linesize() + 2

    pygame.draw.rect(screen, COLOR_FONDO, vista)
    clip_previo = screen.get_clip()
    screen.set_clip(vista)

    y = vista.y + tope + MARGEN
    titulo = f_titulo.render(f"Jugador {indice + 1}", True,
                             COLOR_LISTO if estado["listo"] else COLOR_TEXTO)
    screen.blit(titulo, (vista.x + MARGEN, y))
    y += f_titulo.get_linesize()

    screen.blit(f.render(estado["controles"], True, COLOR_TENUE), (vista.x + MARGEN, y))
    y += paso + 8

    if estado["listo"]:
        _confirmado(screen, vista, f, y, estado)
        rol = next((r for r in ROLES if r["nombre"] == estado["rol"]), None)
        if rol is not None:
            _dibujar_retrato(screen, vista, rol["nombre"], tope, rol["color"])
        screen.set_clip(clip_previo)
        return


    for i, rol in enumerate(ROLES):
        sobre = (i == estado["cursor"])
        ocupado = rol["nombre"] in tomados

        alto_fila = paso * 2 + 8
        fila = pygame.Rect(vista.x + MARGEN - 6, y - 4, vista.width - MARGEN * 2 + 12, alto_fila)
        if sobre:
            pygame.draw.rect(screen, COLOR_SELECCION_FONDO, fila)
            pygame.draw.rect(screen, COLOR_TITULO if not ocupado else COLOR_TOMADO, fila, 2)

        if ocupado:
            nombre, color = f"{rol['nombre']} — ya lo tomaron", COLOR_TOMADO
        else:
            nombre, color = rol["nombre"], (rol["color"] if sobre else COLOR_TEXTO)
        screen.blit(f.render(("> " if sobre else "  ") + nombre, True, color),
                    (vista.x + MARGEN, y))
        y += paso
        screen.blit(f.render("   " + rol["resumen"], True,
                             COLOR_TOMADO if ocupado else COLOR_TENUE),
                    (vista.x + MARGEN, y))
        y += paso + 12

    sobre_rol = ROLES[estado["cursor"]]
    _dibujar_retrato(screen, vista, sobre_rol["nombre"], tope, sobre_rol["color"])

    pie = f.render(f"[{estado['tecla_mover']}] elegir   [{estado['tecla_ok']}] confirmar",
                   True, (194, 216, 248))
    screen.blit(pie, (vista.x + MARGEN, vista.bottom - MARGEN - pie.get_height()))
    screen.set_clip(clip_previo)


def _confirmado(screen, vista, f, y, estado):
    paso = f.get_linesize() + 2
    rol = next((r for r in ROLES if r["nombre"] == estado["rol"]), None)
    if rol is None:
        return

    from screens.paneles import partir_lineas
    # El retrato va a la derecha: la caja usa lo que queda, y el objetivo se
    # parte en renglones para que no se salga (antes iba en uno solo).
    imagen = _retrato(rol["nombre"], max(40, min(190, vista.height // 3)))
    libre = vista.right - MARGEN - (imagen.get_width() + 16 if imagen is not None else 0)
    derecha = min(vista.x + int(vista.width * 0.62), libre)
    ancho = max(120, derecha - (vista.x + MARGEN))
    renglones = partir_lineas(rol["objetivo"], f, ancho - 24)
    caja = pygame.Rect(vista.x + MARGEN, y, ancho, paso * (2 + len(renglones)) + 16)
    pygame.draw.rect(screen, (34, 48, 40), caja)
    pygame.draw.rect(screen, COLOR_LISTO, caja, 2)

    y += 10
    screen.blit(f.render(rol["nombre"], True, rol["color"]), (caja.x + 12, y))
    y += paso
    for renglon in renglones:
        screen.blit(f.render(renglon, True, COLOR_TEXTO), (caja.x + 12, y))
        y += paso
    screen.blit(f.render("Listo", True, COLOR_LISTO), (caja.x + 12, y))

    pie = f.render(f"[{estado['tecla_ok']}] cambiar", True, (194, 216, 248))
    screen.blit(pie, (vista.x + MARGEN, vista.bottom - MARGEN - pie.get_height()))


def _separadores(screen, viewports):
    """Mismo criterio que en la partida: el borde de cada sección, no líneas
    de punta a punta, que con tres jugadores partían en dos la de abajo."""
    from screens.partida import _dibujar_separadores
    _dibujar_separadores(screen, viewports, color=(18, 16, 30), grosor=4)
