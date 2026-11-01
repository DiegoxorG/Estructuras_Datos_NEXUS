"""Que se sienta: el latido que se oye, los pasos del alien y el susto.

No cambia nada de las reglas del juego; solo hace que lo que ya pasa se oiga y
se vea más fuerte:

- **Latido**: suena al ritmo del jugador más asustado (el de pulso más alto).
  Tranquilo apenas se oye; en pánico, fuerte y rápido. Un solo latido para
  todos, porque cuatro corazones a la vez serían ruido.
- **Pasos del alien**: se oyen cuando un alien camina cerca de alguien, más
  fuerte y más seguido entre más cerca y si está persiguiendo.
- **Susto**: al ser atrapado, golpe de sonido, destello rojo, la pantalla de ese
  jugador tiembla y aparece la cara del alien. Medio segundo, lo justo.
- **Sustos del Cambiaformas**: su propia familia, con su sprite y un glitch
  (como cuando le falla el nombre) en colores fríos. Al **transformarse** el
  prisionero se convierte en el monstruo (destello verde azulado); al
  **atraparte**, el monstruo se te abalanza y todo se oscurece en violeta.
- **Un susto por tipo de alien**, con su sprite y lo que lo define:
  el **Ciego** (no ve, oye) te encuentra con ecos que se cierran en la
  oscuridad y de golpe aparece su cara; el **Cazador** (el rápido) cruza la
  pantalla a toda velocidad, con estela y líneas de velocidad, y te da un
  zarpazo; el **Vigía** (el que ve lejos) te barre con su haz de luz, la mira
  se cierra sobre ti y se pone roja. Si falta el arte de un alien, se usa el
  de siempre: destello rojo y una cara verde.

Los sonidos se piden por nombre a audio_manager; si no hay audio, no pasa nada.
"""

import math
import random

from juego.audio_manager import audio_manager


DURACION_SUSTO_MS = 750       # el de siempre ("alien")
# Los sustos con forma propia (cada uno con el sprite de su alien).
DURACION_SUSTO_TIPO = {"cf_revela": 1000, "cf_captura": 850,
                       "ciego": 950, "cazador": 700, "vigia": 950, "sombra": 1000}
RADIO_SUSURRO_SOMBRA = 450   # la Sombra no hace pasos: susurra
INTERVALO_SUSURRO_MS = 2600
ALCANCE_PASOS = 650          # a qué distancia se empiezan a oír los pasos
INTERVALO_PASO_MS = 520
INTERVALO_PASO_PERSIGUE_MS = 340
AMPLITUD_TEMBLOR = 14        # píxeles


def sonar(nombre, volumen=1.0):
    audio_manager.play_sfx(nombre, volumen)


class Ambiente:
    def __init__(self):
        self.fase_latido = 0.0
        self.pasos_ms = {}       # id(alien) -> ms hasta el próximo paso
        self.ultimos = []        # (nombre, volumen) de lo que sonó; lo leen las pruebas

    def sonar(self, nombre, volumen=1.0):
        self.ultimos.append((nombre, round(volumen, 2)))
        del self.ultimos[:-30]
        sonar(nombre, volumen)

    def susto(self, jugador, tipo="alien", disfraz=None):
        """`tipo`: el tipo del alien que lo atrapó ("ciego", "cazador",
        "vigia", "sombra"; otro, como "alien", es el susto de siempre),
        "cf_revela" (el Cambiaformas se transformó delante de él) o
        "cf_captura" (lo atrapó el Cambiaformas). `disfraz`: el sprite del
        prisionero que imitaba (para la transformación)."""
        if tipo not in DURACION_SUSTO_TIPO:
            tipo = "alien"
        jugador.susto_tipo = tipo
        jugador.susto_disfraz = disfraz
        jugador.susto_total_ms = DURACION_SUSTO_TIPO.get(tipo, DURACION_SUSTO_MS)
        jugador.susto_ms = jugador.susto_total_ms
        if tipo == "cf_revela":
            self.sonar("cf_revela", 1.0)
        elif tipo == "cf_captura":
            self.sonar("cf_captura", 1.0)
        elif tipo == "ciego":
            self.sonar("captura_ciego", 1.0)
        elif tipo == "cazador":
            self.sonar("captura_cazador", 1.0)
        elif tipo == "vigia":
            self.sonar("captura_vigia", 1.0)
        elif tipo == "sombra":
            self.sonar("captura_sombra", 1.0)
        else:
            self.sonar("captura", 1.0)

    def actualizar(self, dt, jugadores, aliens):
        for j in jugadores:
            j.susto_ms = max(0, getattr(j, "susto_ms", 0) - dt)
            if j.susto_ms == 0:
                j.susto_tipo = "alien"

        libres = [j for j in jugadores if j.puede_moverse and j.preso is None
                  and not getattr(j, "eliminado", False)]
        if libres:
            asustado = max(libres, key=lambda j: j.pulso)
            self.fase_latido += asustado.latidos_por_minuto / 60 * dt / 1000
            if self.fase_latido >= 1:
                self.fase_latido %= 1
                fuerza = max(0.0, min(1.0, (asustado.pulso - 20) / 75))
                self.sonar("latido", 0.12 + 0.88 * fuerza)

        for alien in aliens:
            if alien.tipo == "sombra":
                self._susurro(alien, libres, dt)
                continue
            if alien.accion in ("DESCANSAR", "BUSCAR", "REVISAR_ESCONDITE", "ATRAPAR"):
                continue
            distancia = min((math.dist(alien.centro, j.hitbox.center) for j in libres), default=None)
            if distancia is None or distancia > ALCANCE_PASOS:
                continue
            clave = id(alien)
            self.pasos_ms[clave] = self.pasos_ms.get(clave, 0) - dt
            if self.pasos_ms[clave] <= 0:
                rapido = alien.accion == "PERSEGUIR" or alien.alerta
                self.pasos_ms[clave] = INTERVALO_PASO_PERSIGUE_MS if rapido else INTERVALO_PASO_MS
                self.sonar("paso_alien", 0.15 + 0.85 * (1 - distancia / ALCANCE_PASOS))


    def _susurro(self, sombra, libres, dt):
        """La Sombra no hace ruido al caminar: cerca se oye un susurro."""
        if getattr(sombra, "oculta", False):
            return
        distancia = min((math.dist(sombra.centro, j.hitbox.center) for j in libres), default=None)
        if distancia is None or distancia > RADIO_SUSURRO_SOMBRA:
            return
        clave = id(sombra)
        self.pasos_ms[clave] = self.pasos_ms.get(clave, 0) - dt
        if self.pasos_ms[clave] <= 0:
            self.pasos_ms[clave] = INTERVALO_SUSURRO_MS
            self.sonar("susurro", 0.25 + 0.75 * (1 - distancia / RADIO_SUSURRO_SOMBRA))


def temblor(jugador, tiempo_ms):
    """Desplazamiento de cámara mientras dura el susto (se apaga solo)."""
    restante = getattr(jugador, "susto_ms", 0)
    if restante <= 0:
        return 0, 0
    total = getattr(jugador, "susto_total_ms", 0) or DURACION_SUSTO_MS
    fuerza = AMPLITUD_TEMBLOR * min(1.0, restante / total)
    azar = random.Random(int(tiempo_ms // 30))
    return int(azar.uniform(-fuerza, fuerza)), int(azar.uniform(-fuerza, fuerza))


def dibujar_susto(screen, vista, jugador):
    """Destello rojo y la cara del alien que se acerca, en la mitad del atrapado."""
    import pygame
    restante = getattr(jugador, "susto_ms", 0)
    if restante <= 0:
        return
    tipo = getattr(jugador, "susto_tipo", "alien")
    total = getattr(jugador, "susto_total_ms", 0) or DURACION_SUSTO_TIPO.get(tipo, DURACION_SUSTO_MS)
    t = max(0.0, min(1.0, 1 - restante / total))      # 0 al empezar, 1 al terminar
    dibujo = {"cf_revela": _susto_transformacion, "cf_captura": _susto_captura,
              "ciego": _susto_ciego, "cazador": _susto_cazador, "vigia": _susto_vigia,
              "sombra": _susto_sombra}.get(tipo)
    # Sin el arte de ese alien: el de siempre.
    if dibujo is not None and (tipo.startswith("cf_") or _figura_alien(tipo) is not None):
        anterior = screen.get_clip()
        screen.set_clip(vista.clip(anterior) if anterior else vista)   # no invadir las otras vistas
        puesto = getattr(jugador, "puesto", 0)
        if tipo == "cf_revela":
            dibujo(screen, vista, t, getattr(jugador, "susto_disfraz", None), puesto)
        else:
            dibujo(screen, vista, t, puesto)
        screen.set_clip(anterior)
        return
    rojo = pygame.Surface(vista.size, pygame.SRCALPHA)
    rojo.fill((200, 0, 20, int(190 * (1 - t))))
    screen.blit(rojo, vista.topleft)

    # La cara crece rápido y se desvanece.
    lado = int(min(vista.width, vista.height) * (0.45 + 0.5 * min(1, t * 2.5)))
    cara = pygame.Surface((lado, lado), pygame.SRCALPHA)
    alfa = int(255 * (1 - max(0, t - 0.55) / 0.45))
    c = lado // 2
    pygame.draw.ellipse(cara, (112, 214, 120, alfa), (lado * 0.12, lado * 0.05, lado * 0.76, lado * 0.92))
    for lado_ojo in (-1, 1):
        ojo = pygame.Rect(0, 0, int(lado * 0.24), int(lado * 0.32))
        ojo.center = (c + lado_ojo * int(lado * 0.17), int(lado * 0.42))
        pygame.draw.ellipse(cara, (10, 10, 18, alfa), ojo)
        pygame.draw.circle(cara, (255, 40, 40, alfa), (ojo.centerx, ojo.centery + 4), max(2, lado // 40))
    boca = pygame.Rect(0, 0, int(lado * 0.3), int(lado * 0.1))
    boca.center = (c, int(lado * 0.74))
    pygame.draw.ellipse(cara, (20, 40, 25, alfa), boca)
    screen.blit(cara, cara.get_rect(center=vista.center))


# -- Los sustos del Cambiaformas ----------------------------------------------------

_escalados = {}     # (id de la imagen, alto) -> imagen agrandada
_rayas = {}         # tamaño de la vista -> capa de líneas de pantalla


_figuras = {}       # (de quién, animación, dirección) -> imagen recortada (o None)


def _recortar(datos, animacion, direccion):
    if not datos:
        return None
    animaciones = datos["animaciones"]
    cuadro = (animaciones.get(animacion, {}).get(direccion)
              or animaciones.get("idle", {}).get(direccion) or [None])[0]
    return cuadro.subsurface(cuadro.get_bounding_rect()) if cuadro is not None else None


def _figura_alien(tipo, animacion="idle", direccion="south"):
    """El sprite de ese alien (de frente, quieto), recortado; None si no tiene
    arte. Siempre la misma imagen: la caché de `_a_alto` va por id()."""
    clave = ("alien", tipo, animacion, direccion)
    if clave not in _figuras:
        if tipo == "sombra":                 # sin arte: su figura se dibuja con formas
            from entidades.sombra import figura_sombra
            figura = figura_sombra()
            _figuras[clave] = figura.subsurface(figura.get_bounding_rect())
        else:
            from entidades.alien import sprites_de
            _figuras[clave] = _recortar(sprites_de(tipo), animacion, direccion)
    return _figuras[clave]


def _figura_cambiaformas():
    """Su sprite de frente, recortado (o None si no hay arte)."""
    return _figura_alien("cambiaformas")


def _figura_prisionero(carpeta):
    if not carpeta:
        return None
    clave = ("prisionero", carpeta, "idle", "south")
    if clave not in _figuras:
        from entidades.npcs import sprites_prisionero
        _figuras[clave] = _recortar(sprites_prisionero(carpeta), "idle", "south")
    return _figuras[clave]


def _a_alto(img, alto):
    """La imagen agrandada a `alto` px, pixelada (nearest), con caché."""
    import pygame
    alto = max(8, int(alto))
    clave = (id(img), alto)
    if clave not in _escalados:
        if len(_escalados) > 60:
            _escalados.clear()
        ancho = max(1, int(img.get_width() * alto / img.get_height()))
        _escalados[clave] = pygame.transform.scale(img, (ancho, alto))
    return _escalados[clave]


def _glitch(screen, img, centro, fuerza, semilla):
    """La imagen con los colores corridos (cian y magenta) y cortada en tiras
    desplazadas: el "fallo" que identifica al Cambiaformas."""
    import pygame
    rng = random.Random(semilla)
    rect = img.get_rect(center=centro)
    if fuerza > 0:
        for color, dx in (((0, 255, 230), -fuerza), ((255, 40, 255), fuerza)):
            capa = img.copy()
            capa.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
            capa.set_alpha(110)
            screen.blit(capa, rect.move(dx, 0))
    alto_tira = max(4, img.get_height() // 18)
    for y in range(0, img.get_height(), alto_tira):
        dx = rng.randint(-fuerza * 2, fuerza * 2) if fuerza and rng.random() < 0.35 else 0
        screen.blit(img, (rect.x + dx, rect.y + y), pygame.Rect(0, y, img.get_width(), alto_tira))


def _fondo(screen, vista, color, alfa):
    """Color de fondo + líneas de pantalla (las dos sustos del Cambiaformas)."""
    import pygame
    capa = pygame.Surface(vista.size, pygame.SRCALPHA)
    capa.fill((*color, max(0, min(255, int(alfa)))))
    screen.blit(capa, vista.topleft)
    if vista.size not in _rayas:
        rayas = pygame.Surface(vista.size, pygame.SRCALPHA)
        for y in range(0, vista.height, 4):
            pygame.draw.line(rayas, (0, 0, 0, 70), (0, y), (vista.width, y))
        _rayas[vista.size] = rayas
    screen.blit(_rayas[vista.size], vista.topleft)


def _susto_transformacion(screen, vista, t, disfraz, puesto):
    """El prisionero en primer plano se convierte en el monstruo."""
    import pygame
    semilla = pygame.time.get_ticks() // 50 + puesto * 1000
    monstruo, prisionero = _figura_cambiaformas(), _figura_prisionero(disfraz)
    _fondo(screen, vista, (10, 150, 140), 170 * (1 - t) + 30)
    if monstruo is None:
        return
    prisionero = prisionero or monstruo
    h = vista.height
    if t < 0.4:                                          # el prisionero, cada vez más raro
        img, alto, fuerza = prisionero, h * (0.55 + 0.07 * t / 0.4), int(2 + 10 * t / 0.4)
    elif t < 0.65:                                       # cambia de forma a tirones
        img = monstruo if (semilla // 1) % 2 else prisionero
        alto, fuerza = h * 0.65, 14
    else:                                                # ya es el monstruo y se acerca
        k = (t - 0.65) / 0.35
        img, alto, fuerza = monstruo, h * (0.65 + 0.3 * k), int(14 * (1 - k)) + 2
    _glitch(screen, _a_alto(img, alto), vista.center, fuerza, semilla)


def _susto_captura(screen, vista, t, puesto):
    """El monstruo se abalanza hasta llenar la pantalla y todo se apaga."""
    import pygame
    semilla = pygame.time.get_ticks() // 40 + puesto * 1000
    monstruo = _figura_cambiaformas()
    _fondo(screen, vista, (28, 0, 44), 230 - 90 * t)
    if monstruo is not None:
        h = vista.height
        k = min(1.0, t / 0.3) ** 2                       # se lanza: lento y de golpe
        alto = h * (0.3 + 1.2 * k)
        img = _a_alto(monstruo, alto)
        # Entre más grande, más se centra la cabeza (la parte de arriba).
        centro = (vista.centerx + random.Random(semilla).randint(-8, 8) * (t > 0.3),
                  int(vista.centery + img.get_height() * 0.32 * k))
        _glitch(screen, img, centro, 4 if t < 0.3 else 12, semilla)
    if t > 0.7:                                          # se apaga la pantalla
        _fondo(screen, vista, (0, 0, 0), 255 * (t - 0.7) / 0.3)


# -- Un susto por tipo de alien -------------------------------------------------------

def _velo(screen, vista, color, alfa):
    """Toda la vista de un color, con transparencia (sin las líneas de
    pantalla, que son del Cambiaformas)."""
    import pygame
    alfa = max(0, min(255, int(alfa)))
    if alfa:
        capa = pygame.Surface(vista.size)
        capa.fill(color)
        capa.set_alpha(alfa)
        screen.blit(capa, vista.topleft)


def _con_alfa(img, alfa):
    """Copia de `img` con transparencia (para estelas y siluetas)."""
    copia = img.copy()
    copia.set_alpha(max(0, min(255, int(alfa))))
    return copia


def _oscura(img, factor):
    """`img` oscurecida (silueta apenas iluminada), con caché."""
    import pygame
    clave = ("oscura", id(img), round(factor, 2))
    if clave not in _escalados:
        copia = img.copy()
        v = int(255 * factor)
        copia.fill((v, v, v, 255), special_flags=pygame.BLEND_RGBA_MULT)
        _escalados[clave] = copia
    return _escalados[clave]


def _mezcla(a, b, k):
    return tuple(int(x + (y - x) * k) for x, y in zip(a, b))


def _apagar_al_final(screen, vista, t, desde=0.82):
    if t > desde:
        _velo(screen, vista, (0, 0, 0), 255 * (t - desde) / (1 - desde))


def _susto_ciego(screen, vista, t, puesto):
    """El Ciego no ve: te oye. En la oscuridad, ecos que se cierran sobre ti
    (te encontró por el ruido) y su silueta apenas; de golpe, su cara entera
    con un destello color hueso."""
    import pygame
    hueso = (205, 200, 185)
    semilla = pygame.time.get_ticks() // 45 + puesto * 1000
    rng = random.Random(semilla)
    _velo(screen, vista, (6, 5, 4), 238)
    figura = _figura_alien("ciego")
    h = vista.height
    cx, cy = vista.center
    radio_max = int(math.hypot(vista.width, vista.height) / 2)
    if t < 0.45:
        k = t / 0.45
        silueta = _a_alto(figura, h * (0.5 + 0.08 * k))
        screen.blit(_con_alfa(_oscura(silueta, 0.35), 60 + 140 * k), silueta.get_rect(center=(cx, cy)))
        for i in range(3):                       # tres ecos que se cierran hacia el centro
            fase = (k * 1.5 + i / 3) % 1
            radio = int(radio_max * (1 - fase))
            if radio > 6:
                pygame.draw.circle(screen, _mezcla((6, 5, 4), hueso, 0.25 + 0.75 * fase),
                                   (cx, cy), radio, max(2, int(6 * fase)))
    else:
        k = (t - 0.45) / 0.55
        figura = _a_alto(figura, h * (0.95 + 0.25 * min(1.0, k * 5)))
        temblor = 14 if k < 0.4 else 5
        centro = (cx + rng.randint(-temblor, temblor), cy + int(figura.get_height() * 0.18)
                  + rng.randint(-temblor, temblor))
        screen.blit(figura, figura.get_rect(center=centro))
        if k < 0.35:                             # el golpe: destello hueso
            _velo(screen, vista, hueso, 230 * (1 - k / 0.35))
        for i in range(2):                       # el último eco, rebotando
            radio = int(radio_max * (0.25 + 0.5 * ((k * 2 + i * 0.5) % 1)))
            pygame.draw.circle(screen, _mezcla(hueso, (6, 5, 4), 0.55), (cx, cy), radio, 2)
    _apagar_al_final(screen, vista, t)


def _susto_cazador(screen, vista, t, puesto):
    """El Cazador es el rápido: cruza la pantalla corriendo, con estela y
    líneas de velocidad, se frena delante de ti y te da un zarpazo."""
    import pygame
    naranja = (235, 115, 90)
    semilla = pygame.time.get_ticks() // 35 + puesto * 1000
    rng = random.Random(semilla)
    _velo(screen, vista, (62, 14, 6), 205)
    h = vista.height
    cx, cy = vista.center
    for _ in range(16):                          # líneas de velocidad (cambian cada pocos ms)
        y = vista.top + rng.randint(0, vista.height)
        largo = rng.randint(vista.width // 6, vista.width // 2)
        x = vista.left + rng.randint(-largo, vista.width)
        color = _mezcla((62, 14, 6), _mezcla(naranja, (255, 225, 190), rng.random() * 0.6), 0.6)
        pygame.draw.line(screen, color, (x, y), (x + largo, y), rng.randint(1, 3))
    if t < 0.35:
        k = (t / 0.35) ** 2                      # cada vez más rápido
        corriendo = _figura_alien("cazador", "walking", "east") or _figura_alien("cazador")
        img = _a_alto(corriendo, h * 0.62)
        ancho = img.get_width()
        x = vista.left - ancho + (cx + ancho / 2 - vista.left) * k
        for paso, alfa in ((3, 45), (2, 85), (1, 140)):     # la estela
            screen.blit(_con_alfa(img, alfa), (int(x - paso * ancho * 0.4) - ancho // 2,
                                               cy - img.get_height() // 2))
        screen.blit(img, (int(x) - ancho // 2, cy - img.get_height() // 2))
    else:
        k = (t - 0.35) / 0.65
        img = _a_alto(_figura_alien("cazador"), h * (0.9 + 0.18 * min(1.0, k * 4)))
        temblor = 12 if k < 0.45 else 4
        screen.blit(img, img.get_rect(center=(cx + rng.randint(-temblor, temblor),
                                              cy + int(img.get_height() * 0.15) + rng.randint(-temblor, temblor))))
        if k < 0.3:
            _velo(screen, vista, naranja, 210 * (1 - k / 0.3))
        if 0.05 < k < 0.75:                      # el zarpazo: tres cortes en diagonal
            avance = min(1.0, (k - 0.05) / 0.2)
            for i in range(3):
                dx = (i - 1) * vista.width * 0.12
                a = (cx + dx - vista.width * 0.28, cy - h * 0.34)
                b = (cx + dx + vista.width * 0.28, cy + h * 0.34)
                fin = (a[0] + (b[0] - a[0]) * avance, a[1] + (b[1] - a[1]) * avance)
                pygame.draw.line(screen, (120, 20, 10), a, fin, 16)
                pygame.draw.line(screen, (255, 96, 64), a, fin, 7)
    _apagar_al_final(screen, vista, t, 0.8)


def _susto_vigia(screen, vista, t, puesto):
    """El Vigía ve lejos: su haz de luz barre la oscuridad y se clava en ti,
    la mira se cierra, se pone roja y aparece él, dentro del haz."""
    import pygame
    azul = (120, 170, 240)
    rojo = (255, 60, 60)
    semilla = pygame.time.get_ticks() // 45 + puesto * 1000
    rng = random.Random(semilla)
    _velo(screen, vista, (4, 10, 28), 220)
    w, h = vista.width, vista.height
    cx, cy = vista.center
    fijado = t >= 0.45
    # El haz: un cono angosto desde arriba que barre y se queda en el centro.
    barrido = max(0.0, 1 - t / 0.42)
    angulo = math.sin(t * 15) * 0.55 * barrido
    origen = (cx, vista.top - h * 0.15)
    largo, medio = h * 1.4, 0.17
    haz = pygame.Surface(vista.size, pygame.SRCALPHA)
    puntos = [(origen[0] - vista.left, origen[1] - vista.top)]
    for lado in (-1, 1):
        a = angulo + lado * medio
        puntos.append((puntos[0][0] + largo * math.sin(a), puntos[0][1] + largo * math.cos(a)))
    pygame.draw.polygon(haz, (*azul, 95 if fijado else 60), puntos)
    screen.blit(haz, vista.topleft)
    figura = _figura_alien("vigia")
    if not fijado:
        k = t / 0.45
        img = _a_alto(figura, h * 0.45)
        rect = img.get_rect(center=(cx, cy))
        screen.blit(_con_alfa(_oscura(img, 0.3), 40 + 120 * k), rect)
        lado = w * (0.46 - 0.3 * k)              # la mira se cierra sobre su cabeza
        mira = (cx, int(cy + (rect.top + rect.height * 0.2 - cy) * k))
        color = azul
    else:
        k = (t - 0.45) / 0.55
        img = _a_alto(figura, h * (0.85 + 0.2 * min(1.0, k * 4)))
        temblor = 10 if k < 0.4 else 3
        rect = img.get_rect(center=(cx + rng.randint(-temblor, temblor),
                                    cy + int(img.get_height() * 0.16) + rng.randint(-temblor, temblor)))
        screen.blit(img, rect)
        if k < 0.3:
            _velo(screen, vista, (190, 220, 255), 220 * (1 - k / 0.3))
        lado = w * 0.16
        mira = (rect.centerx, int(rect.top + rect.height * 0.2))
        color = rojo if (pygame.time.get_ticks() // 90) % 2 else (150, 20, 20)
    # Las cuatro esquinas de la mira.
    alto_mira, brazo, grosor = lado * 0.8, max(14, int(lado * 0.28)), 5
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = mira[0] + sx * lado, mira[1] + sy * alto_mira
            pygame.draw.line(screen, color, (x, y), (x - sx * brazo, y), grosor)
            pygame.draw.line(screen, color, (x, y), (x, y - sy * brazo), grosor)
    if fijado:
        pygame.draw.circle(screen, color, mira, 6)
    _apagar_al_final(screen, vista, t)


def _susto_sombra(screen, vista, t, puesto):
    """La Sombra: negro total y unos ojos que se acercan rápido; un parpadeo
    de linterna y, de golpe, su boca llena de dientes."""
    import pygame
    semilla = pygame.time.get_ticks() // 40 + puesto * 1000
    rng = random.Random(semilla)
    _velo(screen, vista, (2, 1, 4), 250)
    h = vista.height
    cx, cy = vista.center
    figura = _figura_alien("sombra")
    if t < 0.5:
        k = (t / 0.5) ** 2                       # se acercan cada vez más rápido
        separacion = int(18 + 150 * k)
        radio = int(3 + 16 * k)
        from entidades.sombra import _brillo
        for lado in (-1, 1):
            for dy, r in ((0, radio), (int(radio * 1.8), max(2, radio // 2))):
                centro = (cx + lado * separacion // (2 if dy else 1), cy - 40 + dy)
                brillo = _brillo(max(6, r * 4))
                screen.blit(brillo, (centro[0] - brillo.get_width() // 2, centro[1] - brillo.get_height() // 2),
                            special_flags=pygame.BLEND_RGB_ADD)
                pygame.draw.circle(screen, (255, 250, 225), centro, r)
        if 0.38 < t < 0.44:                      # la linterna parpadea y se ve algo
            img = _a_alto(figura, h * 0.5)
            screen.blit(_con_alfa(img, 120), img.get_rect(center=(cx, cy)))
    else:
        k = (t - 0.5) / 0.5
        img = _a_alto(figura, h * (1.3 + 0.5 * min(1.0, k * 3)))
        temblor = 14 if k < 0.4 else 5
        # La cabeza (arriba a la derecha de la figura) en el centro de la pantalla.
        rect = img.get_rect()
        rect.center = (cx - int(rect.width * 0.28) + rng.randint(-temblor, temblor),
                       cy + int(rect.height * 0.3) + rng.randint(-temblor, temblor))
        screen.blit(img, rect)
        # Sus ojos también brillan aquí (la figura viene recortada: se corre).
        from entidades.sombra import figura_sombra, OJOS, ESCALA_FIGURA, _brillo
        recorte = figura_sombra().get_bounding_rect()
        escala = img.get_height() / figura.get_height()
        for i, (x, y, r) in enumerate(OJOS):
            px = rect.x + int((x * ESCALA_FIGURA - recorte.x) * escala)
            py = rect.y + int((y * ESCALA_FIGURA - recorte.y) * escala)
            radio = max(2, int(r * ESCALA_FIGURA * escala))
            brillo = _brillo(radio * 3)
            screen.blit(brillo, (px - brillo.get_width() // 2, py - brillo.get_height() // 2),
                        special_flags=pygame.BLEND_RGB_ADD)
            pygame.draw.circle(screen, (255, 250, 225), (px, py), radio)
        if k < 0.3:
            _velo(screen, vista, (176, 150, 236), 200 * (1 - k / 0.3))
    _apagar_al_final(screen, vista, t)


def figura_alien(tipo):
    """El sprite de frente de ese tipo de alien, recortado (None sin arte).
    Lo usa también la ventana que presenta a cada alien en Fácil."""
    return _figura_alien(tipo)
