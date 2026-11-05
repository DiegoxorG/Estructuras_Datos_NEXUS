"""Modo dos pantallas: una segunda ventana en la otra pantalla (TV o monitor).

En la feria se juega con la laptop y un monitor: en la laptop los dos de
teclado (WASD y flechas) y en la otra pantalla los dos de mando. Con 3 o 4
jugadores, J1 y J2 van en la ventana de siempre y J3 (y J4) en esta; con 3,
al lado de J3 va el panel del equipo (screens/partida.py, `pantalla_secundaria`).
Con 2 jugadores, y en los menús, esta pantalla muestra lo mismo que la laptop
(sirve para que el público vea).

Se adapta a cualquier pantalla: la ventana es sin bordes y mide lo que mide
el escritorio de esa pantalla (lo que diga Windows, con su escala), y las
vistas se reparten según ese tamaño. Para que funcione, Windows tiene que
estar en "Extender" (Win + P), no en "Duplicar", y la laptop tiene que ser la
pantalla principal (si no, J1 y J2 quedarían en la TV).

Funciona con pygame-ce (`pygame.Window`, se dibuja como cualquier Surface) y
con pygame normal (`pygame._sdl2.video`: se sube la imagen como textura en
cada cuadro, un poco más caro). F9 la prende y la apaga.
"""

import pygame


# SDL_WINDOWPOS_CENTERED_DISPLAY(i): "centrada en la pantalla i". Una ventana
# del tamaño de esa pantalla, centrada en ella, la llena justo.
def _centrada_en(indice):
    return 0x2FFF0000 | indice


def pantallas():
    """Tamaño de cada pantalla conectada [(ancho, alto), ...] (la 0, la principal)."""
    try:
        return list(pygame.display.get_desktop_sizes())
    except (AttributeError, pygame.error):
        return []


class SegundaPantalla:
    def __init__(self, indice=1):
        tamanos = pantallas()
        if len(tamanos) <= indice:
            raise RuntimeError("no hay otra pantalla (¿Windows está en Duplicar? Win + P -> Extender)")
        self.indice = indice
        self.size = tamanos[indice]
        pos = (_centrada_en(indice), _centrada_en(indice))
        self._renderer = None
        if hasattr(pygame, "Window") and hasattr(pygame.Window, "flip"):
            # pygame-ce: la ventana tiene su Surface, como la principal.
            self.ventana = pygame.Window("NEXUS - pantalla 2", self.size, position=pos, borderless=True)
            self.surface = self.ventana.get_surface()
        else:
            from pygame._sdl2.video import Window, Renderer
            self.ventana = Window("NEXUS - pantalla 2", size=self.size, position=pos, borderless=True)
            self._renderer = Renderer(self.ventana)
            self.surface = pygame.Surface(self.size)
        self.surface.fill((12, 11, 23))

    @property
    def ancho(self):
        return self.surface.get_width()

    @property
    def alto(self):
        return self.surface.get_height()

    def es_suyo(self, evento):
        """¿El evento (mouse, cerrar ventana) viene de esta ventana?"""
        ventana = getattr(evento, "window", None)
        return ventana is not None and (ventana is self.ventana or ventana == self.ventana)

    def mostrar(self):
        """Lo que se dibujó en `surface`, a la pantalla (como el flip)."""
        if self._renderer is None:
            self.ventana.flip()
            return
        # pygame normal: hay que subir la imagen como textura. Dos formas: una
        # textura "streaming" hecha una vez y actualizada, o una nueva en cada
        # cuadro (from_surface). Cuál es más rápida depende de la tarjeta de
        # video (en el PC de Diego from_surface costaba ~4-5 ms), así que los
        # primeros cuadros se prueban las dos y se queda la más rápida.
        import time
        from pygame._sdl2.video import Texture
        if not hasattr(self, "_metodos"):
            self._metodos = {"streaming": [], "nueva": []}
            self._elegido = None
            self._textura = None
        metodo = self._elegido
        if metodo is None:
            metodo = "streaming" if len(self._metodos["streaming"]) <= len(self._metodos["nueva"]) else "nueva"
        inicio = time.perf_counter()
        textura = None
        if metodo == "streaming":
            try:
                if self._textura is None:
                    self._textura = Texture(self._renderer, self.size, streaming=True)
                self._textura.update(self.surface)
                textura = self._textura
            except (TypeError, AttributeError, pygame.error):
                self._elegido = metodo = "nueva"
                self._metodos["streaming"] = [float("inf")] * 20
        if textura is None:
            textura = Texture.from_surface(self._renderer, self.surface)
        self._renderer.clear()
        textura.draw()
        self._renderer.present()
        if self._elegido is None:
            self._metodos[metodo].append(time.perf_counter() - inicio)
            if min(len(v) for v in self._metodos.values()) >= 20:
                self._elegido = min(self._metodos, key=lambda k: sorted(self._metodos[k])[10])
                print(f"[PANTALLAS] para la otra pantalla: textura {self._elegido}")

    def espejo(self, origen):
        """Copia `origen` (la pantalla principal) escalada para que quepa entera,
        centrada y con bandas negras si las proporciones no coinciden."""
        self.surface.fill((0, 0, 0))
        ow, oh = origen.get_size()
        escala = min(self.ancho / ow, self.alto / oh)
        tam = (max(1, int(ow * escala)), max(1, int(oh * escala)))
        imagen = origen if tam == (ow, oh) else pygame.transform.smoothscale(origen, tam)
        self.surface.blit(imagen, ((self.ancho - tam[0]) // 2, (self.alto - tam[1]) // 2))

    def cerrar(self):
        try:
            self.ventana.destroy()
        except (AttributeError, pygame.error):
            pass
