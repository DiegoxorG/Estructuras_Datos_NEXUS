"""La pantalla de carga: el Cambiaformas persigue a los personajes que
eligieron los jugadores (uno a cuatro) por un pasillo de la nave mientras el
juego arma la partida (Game.empezar_carga).

Los dos corren en su lugar y el piso se mueve (como una caminadora), así la
animación no se acaba aunque la carga tarde. El Cambiaformas se acerca y se
aleja un poco, y cada tanto da un salto hacia adelante. Abajo, la barra (va
por tiempo: la carga no avisa cuánto le falta) y un consejo.
"""

import math
import os

import pygame

from juego.fuentes import fuente_de_tamano
from screens.paneles import partir_lineas

COLOR_FONDO = (12, 12, 22)
COLOR_PARED = (30, 33, 52)
COLOR_PARED_LINEA = (46, 50, 76)
COLOR_LUZ = (80, 220, 230)
COLOR_PISO = (40, 43, 64)
COLOR_PISO_LINEA = (58, 62, 90)
COLOR_TITULO = (255, 214, 64)
COLOR_TEXTO = (220, 224, 244)
COLOR_TENUE = (150, 156, 190)
COLOR_BARRA = (96, 200, 120)

VELOCIDAD_PISO = 0.55      # px por ms
FPS_CORRER = 12

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_cuadros = {}


def _corriendo(carpeta, alto):
    """Los cuadros de correr hacia la derecha, de `alto` px. [] si no hay arte."""
    clave = (carpeta, alto)
    if clave not in _cuadros:
        cuadros = []
        try:
            from Movimiento.Personaje import cargar_animaciones
            animaciones = cargar_animaciones(os.path.join(_RAIZ, *carpeta), escala=1.0, ancho_ratio=1.0)
            crudos = animaciones.get("walking", {}).get("east") or []
            for cuadro in crudos:
                caja = cuadro.get_bounding_rect()
                if caja.height == 0:
                    continue
                recorte = cuadro.subsurface(caja)
                escala = alto / caja.height
                cuadros.append(pygame.transform.scale(
                    recorte, (max(1, int(caja.width * escala)), alto)))
        except (pygame.error, OSError, ValueError):
            cuadros = []
        _cuadros[clave] = cuadros
    return _cuadros[clave]


def precargar(alto_pantalla, roles=None):
    """Carga los cuadros antes de mostrar la pantalla (si no, el primer
    cuadro de la carga se traba cargándolos)."""
    roles = list(roles or ["Tecnomante"])
    for rol in roles:
        _corriendo(("Imagenes", "Personajes", rol), _alto_figura(alto_pantalla, len(roles)))
        _corriendo(("Imagenes", "Personajes", rol), int(_alto_figura(alto_pantalla, len(roles)) * 0.9))
    _corriendo(("Imagenes", "Aliens", "Alien_Cambiaformas"), int(_alto_figura(alto_pantalla, len(roles)) * 1.25))


def _alto_figura(alto_pantalla, cuantos=1):
    # Con más gente, un poquito más chicos para que quepan todos.
    return max(56, int(alto_pantalla * (0.2 - 0.012 * (max(1, cuantos) - 1))))


COLOR_ROL = {"Tecnomante": (150, 120, 255), "Forjador": (255, 170, 50),
             "Biomante": (90, 220, 120), "Resonante": (255, 90, 170)}


def _dibujar_pasillo(screen, piso_y, t_ms):
    ancho, alto = screen.get_size()
    techo = int(piso_y - alto * 0.34)
    pygame.draw.rect(screen, COLOR_PARED, (0, techo, ancho, piso_y - techo))
    desplazamiento = (t_ms * VELOCIDAD_PISO)
    # Paneles de la pared y sus luces (se mueven más lento: están más atrás).
    paso = 220
    x0 = -(desplazamiento * 0.6 % paso)
    for i in range(int(ancho / paso) + 2):
        x = int(x0 + i * paso)
        pygame.draw.line(screen, COLOR_PARED_LINEA, (x, techo), (x, piso_y), 3)
        luz = pygame.Rect(0, 0, 34, 8)
        luz.center = (x + paso // 2, techo + 26)
        pygame.draw.rect(screen, COLOR_LUZ, luz, border_radius=3)
    pygame.draw.line(screen, COLOR_PARED_LINEA, (0, techo), (ancho, techo), 4)
    # El piso: baldosas que corren hacia la izquierda.
    pygame.draw.rect(screen, COLOR_PISO, (0, piso_y, ancho, int(alto * 0.12)))
    paso = 90
    x0 = -(desplazamiento % paso)
    for i in range(int(ancho / paso) + 2):
        x = int(x0 + i * paso)
        pygame.draw.line(screen, COLOR_PISO_LINEA, (x, piso_y), (x - 40, piso_y + int(alto * 0.12)), 2)
    pygame.draw.line(screen, COLOR_PISO_LINEA, (0, piso_y), (ancho, piso_y), 3)


def _figura(screen, cuadros, centro_x, piso_y, t_ms, fps, color_respaldo, alto):
    if cuadros:
        img = cuadros[int(t_ms / 1000 * fps) % len(cuadros)]
    else:   # sin arte: una silueta
        img = pygame.Surface((alto // 2, alto), pygame.SRCALPHA)
        pygame.draw.ellipse(img, color_respaldo, img.get_rect())
    rebote = int(abs(math.sin(t_ms / 1000 * fps * math.pi / 2)) * 4)
    sombra = pygame.Rect(0, 0, int(img.get_width() * 0.8), 12)
    sombra.center = (centro_x, piso_y + 6)
    pygame.draw.ellipse(screen, (8, 8, 16), sombra)
    screen.blit(img, img.get_rect(midbottom=(centro_x, piso_y + 4 - rebote)))


def render_carga(screen, t_ms, progreso, consejo="", roles=None, titulo="Cargando la nave"):
    """`t_ms`: cuánto lleva la pantalla; `progreso`: 0 a 1 para la barra;
    `roles`: los personajes que eligieron (en orden de jugador)."""
    ancho, alto = screen.get_size()
    screen.fill(COLOR_FONDO)
    piso_y = int(alto * 0.62)
    _dibujar_pasillo(screen, piso_y, t_ms)

    roles = list(roles or ["Tecnomante"])[:4]
    n = len(roles)
    alto_fig = _alto_figura(alto, n)
    alien = _corriendo(("Imagenes", "Aliens", "Alien_Cambiaformas"), int(alto_fig * 1.25))
    # El grupo corre adelante, escalonado en dos carriles DEL PISO (el de atrás
    # un poco más arriba en el piso y más chico, como más lejos; antes el de
    # atrás quedaba con los pies sobre la pared, como flotando); cada uno se
    # adelanta y se atrasa un poquito a su ritmo. El
    # Cambiaformas, detrás del último, se acerca y se aleja, y cada ~2.4 s se
    # lanza hacia adelante.
    separacion = ancho * (0.095 if n <= 2 else 0.082)
    frente = ancho * (0.6 + 0.045 * (n - 1))
    alto_piso = int(alto * 0.12)
    fondo, frente_piso = int(alto_piso * 0.3), int(alto_piso * 0.72)
    corredores = []
    for i, rol in enumerate(roles):
        # Con uno solo, al medio del piso; si no, los impares van más al fondo.
        carril = (int(alto_piso * 0.5) if n == 1 else (fondo if i % 2 else frente_piso))
        x = frente - i * separacion + math.sin(t_ms / (780 + 130 * i) + i * 1.7) * ancho * 0.012
        corredores.append((carril, x, rol, i))
    ultimo = min(x for _, x, _, _ in corredores)
    ciclo = (t_ms % 2400) / 2400
    salto = math.sin(ciclo * math.pi) ** 6 if ciclo > 0.0 else 0
    distancia = ancho * (0.22 - 0.03 * math.sin(t_ms / 650)) - ancho * 0.08 * salto
    x_alien = int(ultimo - distancia)
    # De atrás hacia adelante: el carril del fondo primero (y un poco más chico).
    alto_fondo = int(alto_fig * 0.9)
    figuras = [(carril, x, rol, i) for carril, x, rol, i in corredores]
    figuras.append((int(alto_piso * 0.5), x_alien, None, -1))
    for carril, x, rol, i in sorted(figuras, key=lambda c: c[0]):
        if rol is None:
            _figura(screen, alien, int(x), piso_y + carril, t_ms, FPS_CORRER * 1.3, (120, 40, 60),
                    int(alto_fig * 1.25))
            continue
        tam = alto_fondo if carril == fondo and n > 1 else alto_fig
        cuadros = _corriendo(("Imagenes", "Personajes", rol), tam)
        _figura(screen, cuadros, int(x), piso_y + carril, t_ms + i * 137, FPS_CORRER + i,
                COLOR_ROL.get(rol, (140, 110, 255)), tam)
    if salto > 0.5:
        # ¡Casi lo alcanza!: un "!" sobre el que va de último.
        carril, x, rol, _ = min(corredores, key=lambda c: c[1])
        f_alerta = fuente_de_tamano(max(18, alto_fig // 3))
        alerta = f_alerta.render("!", True, (255, 90, 80))
        tam = alto_fondo if carril == fondo and n > 1 else alto_fig
        screen.blit(alerta, alerta.get_rect(midbottom=(int(x), piso_y + carril - tam - 10)))

    # Título, barra y consejo.
    f_titulo = fuente_de_tamano(max(22, min(44, ancho // 30)))
    puntos = "." * (1 + int(t_ms / 400) % 3)
    img = f_titulo.render(f"{titulo}{puntos}", True, COLOR_TITULO)
    screen.blit(img, (int(ancho / 2 - f_titulo.size(f"{titulo}...")[0] / 2), int(alto * 0.12)))

    barra = pygame.Rect(0, 0, int(ancho * 0.42), 12)
    barra.center = (ancho // 2, int(alto * 0.80))
    pygame.draw.rect(screen, (34, 36, 58), barra, border_radius=6)
    lleno = barra.copy()
    lleno.width = max(0, int(barra.width * min(1.0, progreso)))
    if lleno.width > 0:
        pygame.draw.rect(screen, COLOR_BARRA, lleno, border_radius=6)
    pygame.draw.rect(screen, (70, 76, 110), barra, 2, border_radius=6)

    if consejo:
        f = fuente_de_tamano(max(14, min(24, ancho // 60)))
        y = barra.bottom + 22
        for linea in partir_lineas(consejo, f, int(ancho * 0.7)):
            img = f.render(linea, True, COLOR_TEXTO)
            screen.blit(img, img.get_rect(midtop=(ancho // 2, y)))
            y += f.get_linesize()
