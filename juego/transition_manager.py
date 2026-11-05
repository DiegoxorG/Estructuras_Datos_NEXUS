"""
Gestor de transiciones de pantalla para NEXUS.
Aplica un fade-out seguido de un fade-in al cambiar de pantalla.
Si no hay surface disponible, falla silenciosamente.
"""

import pygame
from juego.config import TRANSITION_DURATION_MS


class TransitionManager:
    """
    Aplica fade-out → cambio de pantalla → fade-in en TRANSITION_DURATION_MS ms.

    Uso:
        # Solicitar un cambio con transición:
        game.transitions.request(game, "partida")

        # En el loop principal, antes de flip():
        game.transitions.update(game, dt_ms)
        game.transitions.draw(game.screen)
    """

    def __init__(self):
        self._phase = "idle"      # idle | fade_out | fade_in
        self._elapsed = 0
        self._pending_screen = None
        self._pending_callback = None
        self._overlay = None      # pygame.Surface creada bajo demanda
        self._duration_override = None   # None -> usa TRANSITION_DURATION_MS

    @property
    def active(self):
        return self._phase != "idle"

    def is_idle(self):
        return self._phase == "idle"

    def request(self, game, new_screen, callback=None, duration_ms=None):
        """
        Solicita una transición hacia new_screen.
        callback opcional se llama justo al completar el fade-out (antes del fade-in).
        duration_ms anula TRANSITION_DURATION_MS solo para esta transición.
        Si ya hay una transición activa, la ignora.
        """
        if self._phase != "idle":
            return
        self._pending_screen = new_screen
        self._pending_callback = callback
        self._duration_override = duration_ms
        self._phase = "fade_out"
        self._elapsed = 0

    def _dur(self):
        return self._duration_override if self._duration_override is not None else TRANSITION_DURATION_MS

    def update(self, game, dt_ms):
        """Avanza la transición. Debe llamarse cada frame."""
        if self._phase == "idle":
            return

        self._elapsed += dt_ms
        dur = self._dur()

        if self._phase == "fade_out" and self._elapsed >= dur:
            if self._pending_screen is not None:
                game.current_screen = self._pending_screen
            if self._pending_callback:
                self._pending_callback()
            self._phase = "fade_in"
            self._elapsed = 0

        elif self._phase == "fade_in" and self._elapsed >= dur:
            self._phase = "idle"
            self._elapsed = 0
            self._pending_screen = None
            self._pending_callback = None
            self._duration_override = None

    def draw(self, screen):
        """Dibuja el overlay de transición sobre el screen ya renderizado. Llamar justo antes de pygame.display.flip()."""
        if self._phase == "idle":
            return

        dur = self._dur()
        progress = min(1.0, self._elapsed / max(1, dur))

        if self._phase == "fade_out":
            alpha = int(255 * progress)
        else:  # fade_in
            alpha = int(255 * (1.0 - progress))

        # alfa 0 no tapa nada; 255 es negro entero: un fill. Las dos puntas
        # eran lo más caro: en pygame 2.6 pegar una capa con set_alpha(255)
        # va por un camino lento (~11 ms a 1536x960 en la nube, varias veces
        # más en la laptop), y así quedaba todo el cuadro en que la pantalla
        # está negra del todo (y en las dos pantallas).
        if alpha <= 0:
            return
        if alpha >= 255:
            screen.fill((0, 0, 0))
            return

        w, h = screen.get_size()
        if self._overlay is None or self._overlay.get_size() != (w, h):
            self._overlay = pygame.Surface((w, h))
            self._overlay.fill((0, 0, 0))

        self._overlay.set_alpha(alpha)
        screen.blit(self._overlay, (0, 0))
