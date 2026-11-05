"""Lo que se dibuja por las habilidades de los roles (ver acciones_rol.py).

Todo es provisional en formas simples hasta que llegue el arte: terminales,
paneles, piezas, el señuelo y la señal falsa. Cada función recibe el `dueño`
del viewport, porque varias cosas solo las ve un rol: las piezas solo el
Forjador, el pulso de los demás solo la Biomante, las flechas hacia los aliens
solo la Resonante.

`extras` es el diccionario que arma juego/app.py con todo lo del mapa: terminales,
paneles, piezas, senuelos, senales, aliens, jugadores y mundo.
"""

import math

import pygame

from juego import salas_selladas
from juego.fuentes import fuente, fuente_de_tamano


COLOR_SOMBRA = (12, 11, 23)
COLOR_TERMINAL = (150, 120, 255)
COLOR_FORJADOR = (255, 170, 50)
COLOR_BIOMANTE = (90, 220, 120)
COLOR_RESONANTE = (255, 90, 170)
COLOR_ALIEN = (236, 70, 60)

_cache_minimapa = {}


def _texto(screen, texto, centro_x, y, color, f=None):
    f = f or fuente("small")
    etiqueta = f.render(texto, True, color)
    sombra = f.render(texto, True, COLOR_SOMBRA)
    pos = (int(centro_x - etiqueta.get_width() // 2), int(y))
    screen.blit(sombra, (pos[0] + 2, pos[1] + 2))
    screen.blit(etiqueta, pos)


def _tiene(jugador, clave):
    arbol = getattr(jugador, "arbol", None)
    return arbol is not None and arbol.tiene(clave)


# -- En el mundo, debajo de los personajes ------------------------------------------

def _dibujar_sello(screen, offset, camara, panel, tiempo_ms):
    """El sello de un panel: apagado, solo un contorno punteado (y una línea
    hasta su panel, para saber cuál lo levanta); activo, un campo de energía."""
    sello = panel.get("sello_rect")
    if sello is None or not sello.inflate(200, 200).colliderect(camara):
        return
    r = sello.move(-offset[0], -offset[1])
    if panel.get("sello_on"):
        capa = pygame.Surface(r.size, pygame.SRCALPHA)
        alfa = int(110 + 50 * math.sin(tiempo_ms / 160))
        capa.fill((90, 200, 255, alfa))
        screen.blit(capa, r.topleft)
        vertical = r.height > r.width
        largo = r.height if vertical else r.width
        for i in range(0, largo, 10):
            d = (i + tiempo_ms // 40) % largo
            if vertical:
                pygame.draw.line(screen, (220, 245, 255), (r.x, r.y + d), (r.right - 1, r.y + d), 1)
            else:
                pygame.draw.line(screen, (220, 245, 255), (r.x + d, r.y), (r.x + d, r.bottom - 1), 1)
        pygame.draw.rect(screen, (150, 230, 255), r, 2)
        return
    for x in range(r.x, r.right, 8):
        pygame.draw.line(screen, (90, 160, 210), (x, r.y), (min(x + 4, r.right), r.y), 1)
        pygame.draw.line(screen, (90, 160, 210), (x, r.bottom - 1), (min(x + 4, r.right), r.bottom - 1), 1)
    for y in range(r.y, r.bottom, 8):
        pygame.draw.line(screen, (90, 160, 210), (r.x, y), (r.x, min(y + 4, r.bottom)), 1)
        pygame.draw.line(screen, (90, 160, 210), (r.right - 1, y), (r.right - 1, min(y + 4, r.bottom)), 1)
    a = (panel["rect"].centerx - offset[0], panel["rect"].centery - offset[1])
    b = r.center
    largo = max(1, int(math.dist(a, b) // 14))
    for i in range(0, largo, 2):
        p0 = (a[0] + (b[0] - a[0]) * i / largo, a[1] + (b[1] - a[1]) * i / largo)
        p1 = (a[0] + (b[0] - a[0]) * (i + 1) / largo, a[1] + (b[1] - a[1]) * (i + 1) / largo)
        pygame.draw.line(screen, (90, 160, 210), p0, p1, 1)



def dibujar_piso(screen, offset, camara, dueño, extras, tiempo_ms):
    """Terminales, paneles, piezas, señuelos y señales."""
    cerca = getattr(dueño, "estacion_cerca", None)

    for t in extras.get("terminales", ()):
        if not t["rect"].inflate(0, 120).colliderect(camara):
            continue
        caja = pygame.Rect(0, 0, 44, 56)
        caja.midbottom = (t["rect"].centerx - offset[0], t["rect"].top + 8 - offset[1])
        pygame.draw.rect(screen, (30, 30, 52), caja, border_radius=4)
        pantalla = caja.inflate(-12, -24).move(0, -6)
        brillo = 0.6 + 0.4 * math.sin(tiempo_ms / 300)
        apagada = t["recarga_ms"] > 0 or extras.get("sin_luz")
        color = (90, 90, 110) if apagada else COLOR_TERMINAL
        if extras.get("sin_luz"):
            brillo = 0.35
        pygame.draw.rect(screen, tuple(int(c * brillo) for c in color), pantalla)
        pygame.draw.rect(screen, (255, 214, 64) if cerca is t else color, caja, 2, border_radius=4)

    for p in extras.get("paneles", ()):
        _dibujar_sello(screen, offset, camara, p, tiempo_ms)
        if not p["rect"].inflate(0, 120).colliderect(camara):
            continue
        caja = pygame.Rect(0, 0, 52, 40)
        caja.midbottom = (p["rect"].centerx - offset[0], p["rect"].top + 8 - offset[1])
        pygame.draw.rect(screen, (60, 64, 80), caja, border_radius=3)
        if p["reparado"]:
            pygame.draw.rect(screen, COLOR_BIOMANTE, caja.inflate(-14, -14))
        else:
            # Chispas que saltan.
            for i in range(3):
                fase = (tiempo_ms / 90 + i * 37) % 20
                if fase < 6:
                    x = caja.x + 10 + (i * 14 + int(tiempo_ms / 50)) % (caja.width - 16)
                    pygame.draw.line(screen, (255, 230, 120), (x, caja.y + 6), (x + 5, caja.y - 4), 2)
            pygame.draw.line(screen, (30, 30, 40), caja.topleft, caja.bottomright, 3)
        borde = (255, 214, 64) if cerca is p else (COLOR_BIOMANTE if p["reparado"] else COLOR_ALIEN)
        pygame.draw.rect(screen, borde, caja, 2, border_radius=3)

    # Las piezas solo las reconoce el Forjador (Ingenio mecánico); si no hay
    # Forjador, quien lleve el kit de herramientas (Mision.ve_piezas).
    mision = extras.get("mision")
    if mision.ve_piezas(dueño) if mision is not None else _tiene(dueño, "INGENIO"):
        for pieza in extras.get("piezas", ()):
            if pieza["recogida"] or not pieza["rect"].colliderect(camara):
                continue
            cx = pieza["rect"].centerx - offset[0]
            cy = pieza["rect"].centery - offset[1]
            halo = 14 + 3 * math.sin(tiempo_ms / 200)
            capa = pygame.Surface((60, 60), pygame.SRCALPHA)
            pygame.draw.circle(capa, (*COLOR_FORJADOR, 70), (30, 30), int(halo + 6))
            screen.blit(capa, (cx - 30, cy - 30))
            for i in range(6):   # un engranaje
                a = i * math.pi / 3 + tiempo_ms / 900
                pygame.draw.circle(screen, COLOR_FORJADOR, (int(cx + math.cos(a) * 9),
                                                            int(cy + math.sin(a) * 9)), 4)
            pygame.draw.circle(screen, COLOR_FORJADOR, (cx, cy), 8)
            pygame.draw.circle(screen, (40, 30, 10), (cx, cy), 3)

    for senuelo in extras.get("senuelos", ()):
        _ondas(screen, senuelo, offset, COLOR_FORJADOR, tiempo_ms, cuerpo=True)
    for senal in extras.get("senales", ()):
        _ondas(screen, senal, offset, COLOR_RESONANTE, tiempo_ms, cuerpo=False)


def _ondas(screen, cosa, offset, color, tiempo_ms, cuerpo):
    cx, cy = cosa["pos"][0] - offset[0], cosa["pos"][1] - offset[1]
    for i in range(3):
        fase = ((tiempo_ms / 700) + i / 3) % 1
        radio = int(14 + fase * 90)
        capa = pygame.Surface((radio * 2 + 4, radio * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(capa, (*color, int(200 * (1 - fase))), (radio + 2, radio + 2), radio, 3)
        screen.blit(capa, (cx - radio - 2, cy - radio - 2))
    if cuerpo:
        pygame.draw.rect(screen, (60, 50, 30), (cx - 10, cy - 8, 20, 16), border_radius=3)
        pygame.draw.rect(screen, color, (cx - 10, cy - 8, 20, 16), 2, border_radius=3)
        pygame.draw.circle(screen, color, (cx, cy - 12), 3)


# -- En el mundo, encima de los personajes ------------------------------------------

def dibujar_encima(screen, offset, camara, dueño, extras, tiempo_ms):
    """Pulso de los compañeros (Biomante) y rutas de los aliens (Interceptación)."""
    if _tiene(dueño, "VINCULO"):
        for otro in extras.get("jugadores", ()):
            if otro is dueño or getattr(otro, "escondido", False) or getattr(otro, "eliminado", False):
                continue
            rect = otro.personaje.hitbox
            x = rect.centerx - offset[0] - 24
            y = int(otro.personaje.y) - offset[1] - 4
            pygame.draw.rect(screen, (30, 32, 50), (x, y, 48, 8))
            color = COLOR_BIOMANTE if otro.pulso < 45 else (255, 196, 64) if otro.pulso < 72 else COLOR_ALIEN
            pygame.draw.rect(screen, color, (x, y, int(48 * otro.pulso / 100), 8))
            pygame.draw.rect(screen, COLOR_BIOMANTE, (x, y, 48, 8), 1)
            # Y sus vidas, para saber a quién curar: solo si le falta alguna
            # (con todos sanos eran tres corazones encima de cada uno, todo el
            # rato; en Fácil no se pierden, así que no salen).
            from screens.paneles import dibujar_corazon
            from entidades.jugador import VIDAS_INICIALES
            maximo = getattr(otro, "vidas_max", VIDAS_INICIALES)
            if getattr(otro, "vidas_infinitas", False) or getattr(otro, "vidas", maximo) >= maximo:
                continue
            for i in range(maximo):
                dibujar_corazon(screen, (x + 8 + i * 16, y - 10), 12, i < otro.vidas)

    if "intercepcion" in getattr(dueño, "efectos", {}):
        f = fuente_de_tamano(14)
        for alien in extras.get("aliens", ()):
            if getattr(alien, "disfrazado", False):
                continue      # el Cambiaformas disfrazado no se delata así
            ruta = alien.ruta if getattr(alien, "tipo", "") != "cambiaformas" else []
            puntos = [(x - offset[0], y - offset[1]) for x, y in ruta]
            if len(puntos) >= 2:
                pygame.draw.lines(screen, COLOR_RESONANTE, len(puntos) > 2, puntos, 2)
            for p in puntos:
                pygame.draw.circle(screen, COLOR_RESONANTE, p, 5)
            if ruta and 0 <= alien.indice_ruta < len(ruta):
                siguiente = ruta[alien.indice_ruta]
                pygame.draw.line(screen, (255, 214, 64),
                                 (alien.centro[0] - offset[0], alien.centro[1] - offset[1]),
                                 (siguiente[0] - offset[0], siguiente[1] - offset[1]), 1)
            decision = alien.camino[-1].texto if alien.camino else ""
            _texto(screen, decision, alien.centro[0] - offset[0],
                   alien.hitbox.top - offset[1] - 92, COLOR_RESONANTE, f)


# -- En el HUD del viewport ---------------------------------------------------------------

# Pasos que oye la Sintonía: por alien, dónde pisó la última vez y sus huellas.
PASO_PX = 38                 # cada cuánto deja una huella (el Guardia, más)
DURA_HUELLA_MS = 1600
DURA_ONDA_MS = 650
COLOR_PASOS = (255, 120, 200)
_pasos = {}


def _oye_pasos_de(alien):
    """La Sombra no hace ruido al caminar; el Cambiaformas disfrazado camina
    como un prisionero más."""
    if alien.__class__.__name__ == "Sombra":
        return False
    return not getattr(alien, "disfrazado", False)


def _registrar_pasos(alien, ahora):
    rastro = _pasos.get(id(alien))
    x, y = alien.hitbox.midbottom
    if rastro is None or rastro["alien"] is not alien:
        _pasos[id(alien)] = {"alien": alien, "ultimo": (x, y), "huellas": [], "lado": 1}
        return
    lx, ly = rastro["ultimo"]
    d = math.hypot(x - lx, y - ly)
    if d > 400:                              # lo movieron de golpe: empieza de nuevo
        rastro["ultimo"], rastro["huellas"] = (x, y), []
        return
    paso = PASO_PX * (1.8 if alien.__class__.__name__ == "Guardia" else 1)
    if d >= paso:
        angulo = math.atan2(y - ly, x - lx)
        lado = rastro["lado"]
        ancho = 9 if alien.__class__.__name__ != "Guardia" else 22
        hx = x + math.cos(angulo + math.pi / 2) * ancho * lado
        hy = y + math.sin(angulo + math.pi / 2) * ancho * lado
        rastro["huellas"].append((hx, hy, ahora, alien.__class__.__name__ == "Guardia"))
        rastro["ultimo"], rastro["lado"] = (x, y), -lado
    rastro["huellas"] = [h for h in rastro["huellas"] if ahora - h[2] < DURA_HUELLA_MS]


def dibujar_pasos(screen, offset, camara, dueño, aliens, visibles, a_oscuras, tiempo_ms):
    """Sintonía de señales: los aliens que están en su pantalla pero no ve
    (detrás de una pared, fuera de su campo de visión o a oscuras) se oyen:
    sus pasos salen como huellas rosadas y una onda donde acaba de pisar.
    (Los que están más lejos ya los marcan las flechas del borde.)"""
    if not _tiene(dueño, "SINTONIA"):
        return
    ids_visibles = {id(a) for a in visibles}
    for alien in aliens:
        if not camara.inflate(200, 200).colliderect(alien.hitbox) or not _oye_pasos_de(alien):
            continue
        _registrar_pasos(alien, tiempo_ms)
        if id(alien) in ids_visibles and not a_oscuras:
            continue                         # lo ve: no hace falta
        rastro = _pasos.get(id(alien))
        if not rastro:
            continue
        for hx, hy, t, grande in rastro["huellas"]:
            vida = 1 - (tiempo_ms - t) / DURA_HUELLA_MS
            if vida <= 0:
                continue
            w, h = (16, 10) if grande else (9, 6)
            huella = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
            pygame.draw.ellipse(huella, (*COLOR_PASOS, int(210 * vida)), (1, 1, w, h))
            screen.blit(huella, (int(hx - offset[0] - w / 2), int(hy - offset[1] - h / 2)))
        if rastro["huellas"]:
            # La onda del último paso: se abre y se apaga.
            hx, hy, t, grande = rastro["huellas"][-1]
            edad = (tiempo_ms - t) / DURA_ONDA_MS
            if 0 <= edad < 1:
                radio = int((10 + 26 * edad) * (1.6 if grande else 1))
                onda = pygame.Surface((radio * 2 + 4, radio * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(onda, (*COLOR_PASOS, int(200 * (1 - edad))), (radio + 2, radio + 2),
                                   radio, 2)
                screen.blit(onda, (int(hx - offset[0] - radio - 2), int(hy - offset[1] - radio - 2)))


def dibujar_flechas(screen, vista, camara, dueño, extras):
    """Sintonía de señales: flechas en el borde hacia los aliens que no se ven."""
    if not _tiene(dueño, "SINTONIA"):
        return
    centro = dueño.hitbox.center
    margen = 34
    for alien in extras.get("aliens", ()):
        if camara.collidepoint(alien.centro):
            continue
        dx, dy = alien.centro[0] - centro[0], alien.centro[1] - centro[1]
        distancia = math.hypot(dx, dy)
        if distancia > 1000 or distancia < 1:
            continue
        ux, uy = dx / distancia, dy / distancia
        # Punto del borde del viewport en esa dirección.
        mitad_w, mitad_h = vista.width / 2 - margen, vista.height / 2 - margen
        escala = min(mitad_w / abs(ux) if ux else 1e9, mitad_h / abs(uy) if uy else 1e9)
        px, py = vista.centerx + ux * escala, vista.centery + uy * escala
        tam = 10 + 10 * (1 - distancia / 1000)
        angulo = math.atan2(uy, ux)
        punta = (px + math.cos(angulo) * tam, py + math.sin(angulo) * tam)
        izq = (px + math.cos(angulo + 2.5) * tam, py + math.sin(angulo + 2.5) * tam)
        der = (px + math.cos(angulo - 2.5) * tam, py + math.sin(angulo - 2.5) * tam)
        color = COLOR_ALIEN if alien.accion in ("PERSEGUIR", "INVESTIGAR", "REVISAR_ESCONDITE") \
            else COLOR_RESONANTE
        pygame.draw.polygon(screen, color, [punta, izq, der])
        pygame.draw.polygon(screen, COLOR_SOMBRA, [punta, izq, der], 2)


def render_minimapa(screen, vista, dueño, extras):
    """Mapa de la nave (Conexión digital / Escaneo) en la esquina del viewport."""
    if "mapa" not in getattr(dueño, "efectos", {}):
        return
    mundo = extras.get("mundo")
    if mundo is None:
        return
    # Abajo a la izquierda, justo encima del pulso: arriba a la derecha lo
    # tapaban los avisos, la barra de confianza y el celular.
    from screens.paneles import rect_pulso, alto_hud
    pulso = rect_pulso(screen, vista, dueño)
    lado = int(min(vista.width * 0.34, pulso.top - 8 - (alto_hud(vista, dueño) + 40), 260))
    if lado < 60:
        return
    clave = (id(mundo.imagen), lado, salas_selladas.clave_cache(mundo))
    if clave not in _cache_minimapa:
        miniatura = salas_selladas.oscurecer_miniatura(
            pygame.transform.smoothscale(mundo.imagen, (lado, lado)), mundo)
        miniatura.fill((120, 120, 140), special_flags=pygame.BLEND_RGB_MULT)
        _cache_minimapa[clave] = miniatura
    caja = pygame.Rect(0, 0, lado, lado)
    caja.bottomleft = (pulso.left, pulso.top - 8)
    screen.blit(_cache_minimapa[clave], caja.topleft)
    pygame.draw.rect(screen, COLOR_TERMINAL, caja, 2)
    ex, ey = lado / mundo.ancho, lado / mundo.alto

    def a_mapa(p):
        return int(caja.x + p[0] * ex), int(caja.y + p[1] * ey)

    for t in extras.get("terminales", ()):
        pygame.draw.rect(screen, COLOR_TERMINAL, (*a_mapa(t["rect"].center), 5, 5))
    for e in extras.get("escondites", ()):
        pygame.draw.rect(screen, (140, 160, 190), (*a_mapa(e["rect"].center), 5, 5), 1)
    if "escaneo" in dueño.efectos:
        for alien in extras.get("aliens", ()):
            cx, cy = a_mapa(alien.centro)
            medio = alien.datos["medio_angulo"]
            if alien.alcance_vision <= 0:
                continue   # el Ciego no tiene cono
            r = alien.alcance_vision * ex
            puntos = [(cx, cy)] + [
                (cx + math.cos(alien.angulo + a) * r, cy + math.sin(alien.angulo + a) * r)
                for a in (-medio, 0, medio)]
            capa = pygame.Surface(caja.size, pygame.SRCALPHA)
            pygame.draw.polygon(capa, (*COLOR_ALIEN, 70),
                                [(x - caja.x, y - caja.y) for x, y in puntos])
            screen.blit(capa, caja.topleft)
    for alien in extras.get("aliens", ()):
        pygame.draw.circle(screen, COLOR_ALIEN, a_mapa(alien.centro), 4)
    for jugador in extras.get("jugadores", ()):
        color = (255, 255, 255) if jugador is dueño else (255, 214, 64)
        pygame.draw.circle(screen, color, a_mapa(jugador.hitbox.center), 3)
    # El nombre va arriba del mapa: abajo queda el pulso.
    _texto(screen, "Escaneo" if "escaneo" in dueño.efectos else "Estado de la nave",
           caja.centerx, caja.top - 18, COLOR_TERMINAL, fuente_de_tamano(13))
