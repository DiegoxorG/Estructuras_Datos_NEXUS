"""El dibujo sencillo del prototipo (fondo, sprites, aliens como círculos y un
HUD de texto). Ahora el cliente dibuja con el espejo (cliente_servidor/espejo.py),
como el modo local; esto queda de respaldo por si el espejo falla, y usa la
instantánea "legible" (protocolo.legible)."""

import math
import os

import pygame

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COLOR_ALIEN = {"vigia": (235, 90, 80), "cazador": (240, 150, 40), "ciego": (180, 120, 230),
               "sombra": (90, 90, 120), "cambiaformas": (80, 200, 160), "guardia": (230, 60, 150)}
COLOR_JUGADOR = [(90, 170, 255), (120, 230, 120), (250, 210, 80), (240, 120, 200)]


def vistas(ancho, alto, cantidad):
    """Una vista por jugador local: completa, mitades o cuartos (con 3 se
    piden 4 y el cuarto que sobra es para el equipo)."""
    if cantidad <= 1:
        return [pygame.Rect(0, 0, ancho, alto)]
    mx, my = ancho // 2, alto // 2
    if cantidad == 2:
        return [pygame.Rect(0, 0, mx, alto), pygame.Rect(mx, 0, ancho - mx, alto)]
    return [pygame.Rect(0, 0, mx, my), pygame.Rect(mx, 0, ancho - mx, my),
            pygame.Rect(0, my, mx, alto - my), pygame.Rect(mx, my, ancho - mx, alto - my)]


class Dibujo:
    def __init__(self, bienvenida):
        self.b = bienvenida
        self.escala = int(bienvenida.get("escala", 3)) or 1
        self.ancho, self.alto = bienvenida["ancho"], bienvenida["alto"]
        self.fondo = self._cargar_fondo(bienvenida["mapa"])
        self.fuente = pygame.font.Font(None, 22)
        self.fuente_grande = pygame.font.Font(None, 56)
        self.sprites = [self._cargar_sprite(rol) for rol in bienvenida["roles"]]

    @staticmethod
    def _cargar_fondo(nombre):
        """El PNG original, SIN escalar: el mapa escalado entero pesa cientos
        de MB; aquí se escala solo el pedazo que se ve."""
        for extension in (".png", ".jpg", ".jpeg"):
            ruta = os.path.join(RAIZ, "Imagenes", "Fondos", nombre + extension)
            if os.path.isfile(ruta):
                return pygame.image.load(ruta).convert()
        return None

    @staticmethod
    def _cargar_sprite(rol):
        try:
            from Movimiento.Personaje import Personaje
            return Personaje(0, 0, os.path.join("Imagenes", "Personajes", rol), velocidad=4)
        except Exception:          # sin sprites se dibuja un círculo
            return None

    def animar(self, estado):
        """Una vez por cuadro (no por vista): la animación es del cliente."""
        for datos, sprite in zip(estado["jugadores"], self.sprites):
            if sprite is None:
                continue
            sprite.x, sprite.y = datos["x"], datos["y"]
            sprite.direccion = datos["dir"]
            nuevo = "walking" if datos["mov"] else (
                "breathing" if sprite.animaciones.get("breathing", {}).get(sprite.direccion) else "idle")
            if nuevo != sprite.estado:
                sprite.estado, sprite.frame_actual, sprite.contador_animacion = nuevo, 0, 0
            sprite._avanzar_animacion()

    def texto(self, superficie, texto, pos, color=(235, 235, 235), fuente=None, fondo=True):
        imagen = (fuente or self.fuente).render(str(texto), True, color)
        if fondo:
            caja = imagen.get_rect(topleft=pos).inflate(8, 4)
            pygame.draw.rect(superficie, (10, 12, 20), caja)
        superficie.blit(imagen, pos)
        return imagen.get_height() + 4

    def vista(self, pantalla, rect, estado, numero, conexion):
        sup = pantalla.subsurface(rect)
        sup.fill((14, 16, 24))
        yo = estado["jugadores"][numero]
        # La cámara centrada en su jugador, recortada al borde del mapa.
        ox = int(max(0, min(yo["hx"] - rect.w / 2, self.ancho - rect.w)))
        oy = int(max(0, min(yo["hy"] - rect.h / 2, self.alto - rect.h)))
        self._fondo(sup, ox, oy, rect.w, rect.h)

        if estado.get("capsula"):
            x, y, w, h = estado["capsula"]
            pygame.draw.rect(sup, (120, 200, 255), (x - ox, y - oy, w, h), 3)
            self.texto(sup, f"Cápsula {estado.get('entregadas', 0)}/3", (x - ox, y - oy - 20), fondo=False)
        for px, py in estado.get("piezas", ()):
            pygame.draw.rect(sup, (250, 220, 60), (px - ox - 6, py - oy - 6, 12, 12))
        for a in estado["aliens"]:
            self._alien(sup, a, ox, oy)
        for j in estado["jugadores"]:
            self._jugador(sup, j, ox, oy)
        self._hud(sup, yo, estado, conexion)
        pygame.draw.rect(sup, (60, 70, 90), sup.get_rect(), 2)

    def _fondo(self, sup, ox, oy, w, h):
        if self.fondo is None:
            sup.fill((46, 62, 54))
            return
        e = self.escala
        origen = pygame.Rect(ox // e, oy // e, w // e + 2, h // e + 2).clip(self.fondo.get_rect())
        if origen.w <= 0 or origen.h <= 0:
            return
        pedazo = pygame.transform.scale(self.fondo.subsurface(origen), (origen.w * e, origen.h * e))
        sup.blit(pedazo, (origen.x * e - ox, origen.y * e - oy))

    def _alien(self, sup, a, ox, oy):
        x, y = a["x"] - ox, a["y"] - oy
        color = COLOR_ALIEN.get(a["tipo"], (230, 80, 80))
        if a["vis"] > 0 and a["medio"] > 0:
            puntos = [(x, y)]
            for k in range(9):
                ang = a["ang"] - a["medio"] + 2 * a["medio"] * k / 8
                puntos.append((x + math.cos(ang) * a["vis"], y + math.sin(ang) * a["vis"]))
            pygame.draw.polygon(sup, color, puntos, 1)
        pygame.draw.circle(sup, color, (int(x), int(y)), 18)
        pygame.draw.circle(sup, (20, 20, 20), (int(x), int(y)), 18, 2)
        self.texto(sup, f"{a['nombre']} ({a['acc'].lower()})", (x - 40, y - 40), color, fondo=False)

    def _jugador(self, sup, j, ox, oy):
        sprite = self.sprites[j["n"]] if j["n"] < len(self.sprites) else None
        color = COLOR_JUGADOR[j["n"] % len(COLOR_JUGADOR)]
        if j["esc"]:
            pygame.draw.circle(sup, color, (j["hx"] - ox, j["hy"] - oy), 10, 2)   # escondido
        elif sprite is not None:
            sprite.dibujar(sup, (ox, oy))
        else:
            pygame.draw.circle(sup, color, (j["hx"] - ox, j["hy"] - oy), 14)
        etiqueta = f"J{j['n'] + 1} {j['rol']}"
        if j["preso"]:
            etiqueta += " (PRESO)"
        elif j["elim"]:
            etiqueta += " (fuera)"
        elif not j["on"]:
            etiqueta += " (desconectado)"
        self.texto(sup, etiqueta, (j["hx"] - ox - 40, j["hy"] - oy - 90), color, fondo=False)
        if j["msg"]:
            self.texto(sup, j["msg"], (j["hx"] - ox - 60, j["hy"] - oy - 110), (255, 240, 150))

    def _hud(self, sup, yo, estado, conexion):
        vidas = "inf" if yo["infinitas"] else f"{yo['vidas']}/{yo['vmax']}"
        y = 6
        y += self.texto(sup, f"J{yo['n'] + 1} {yo['rol']}  vidas {vidas}  pulso {yo['pulso']}  "
                             f"puntos {yo['puntos']}  {yo['sala']}", (6, y), COLOR_JUGADOR[yo["n"] % 4])
        segundos = estado["t"] // 1000
        respuesta = getattr(conexion, "respuesta_ms", None)
        y += self.texto(sup, f"Fase: {estado['fase']}  ·  {segundos // 60}:{segundos % 60:02d}  ·  "
                             f"respuesta {'?' if respuesta is None else f'{respuesta:.0f} ms'}"
                             + ("  ·  APAGÓN" if estado.get("apagon") else ""), (6, y))
        if estado.get("objetivo"):
            y += self.texto(sup, estado["objetivo"], (6, y), (200, 220, 255))
        if yo["pista"]:
            y += self.texto(sup, yo["pista"], (6, y), (255, 214, 64))
        if yo["prog"]:
            texto, valor = yo["prog"]
            y += self.texto(sup, texto, (6, y))
            pygame.draw.rect(sup, (60, 60, 70), (6, y, 200, 10))
            pygame.draw.rect(sup, (110, 220, 120), (6, y, int(200 * valor), 10))
            y += 14
        if yo["panel"]:
            self._panel(sup, yo["panel"], y + 6)

    def _panel(self, sup, panel, y):
        """El panel abierto, en texto (el bonito es de screens/, ver el diseño)."""
        x = 10
        caja = pygame.Rect(x - 4, y - 4, min(sup.get_width() - 12, 560), 0)
        lineas = [(panel["titulo"], (255, 230, 140))]
        lineas += [(c, (220, 220, 220)) for c in panel["cuerpo"]]
        for i, o in enumerate(panel["opciones"]):
            marcado = i == panel["cursor"]
            lineas.append((("> " if marcado else "   ") + o, (130, 230, 255) if marcado else (200, 200, 200)))
        if panel["pie"]:
            lineas.append((panel["pie"], (160, 160, 170)))
        caja.h = len(lineas) * 22 + 8
        pygame.draw.rect(sup, (16, 20, 34), caja)
        pygame.draw.rect(sup, (90, 110, 160), caja, 1)
        for texto, color in lineas:
            y += self.texto(sup, texto, (x, y), color, fondo=False)

    def equipo(self, pantalla, rect, estado):
        """Con 3 jugadores sobra un cuarto de pantalla: ahí va el equipo."""
        sup = pantalla.subsurface(rect)
        sup.fill((14, 16, 24))
        y = 12
        y += self.texto(sup, f"Equipo · {estado['puntos']} puntos · piezas en la cápsula "
                             f"{estado.get('entregadas', 0)}/3", (12, y), (255, 230, 140), fondo=False)
        for j in estado["jugadores"]:
            situacion = ("preso" if j["preso"] else "fuera" if j["elim"] else
                         "escondido" if j["esc"] else "desconectado" if not j["on"] else j["sala"] or "libre")
            y += self.texto(sup, f"J{j['n'] + 1} {j['rol']}: vidas {j['vidas']}  ·  {situacion}",
                            (12, y), COLOR_JUGADOR[j["n"] % 4], fondo=False)

    def encima(self, pantalla, estado):
        """Lo que va sobre todas las vistas: la presentación de un alien y el final."""
        if estado.get("presentacion"):
            p = estado["presentacion"]
            caja = pygame.Rect(0, 0, min(700, pantalla.get_width() - 40), 60 + 24 * len(p["lineas"]))
            caja.center = pantalla.get_rect().center
            pygame.draw.rect(pantalla, (16, 20, 34), caja)
            pygame.draw.rect(pantalla, (240, 200, 90), caja, 2)
            y = caja.y + 10
            y += self.texto(pantalla, p["titulo"], (caja.x + 12, y), (255, 230, 140), fondo=False)
            for linea in p["lineas"]:
                y += self.texto(pantalla, linea, (caja.x + 12, y), fondo=False)
            self.texto(pantalla, "(interactuar o habilidad para seguir)", (caja.x + 12, y + 4),
                       (160, 160, 170), fondo=False)
        if estado.get("resultado"):
            texto = "¡ESCAPARON!" if estado["resultado"] == "victoria" else "DERROTA"
            imagen = self.fuente_grande.render(texto, True, (255, 240, 160))
            caja = imagen.get_rect(center=pantalla.get_rect().center).inflate(40, 20)
            pygame.draw.rect(pantalla, (10, 12, 20), caja)
            pantalla.blit(imagen, imagen.get_rect(center=caja.center))
