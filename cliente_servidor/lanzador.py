"""Menú > Jugar en red: crear una partida en esta laptop o unirse a otra.

Es una pantalla aparte con su propio bucle (no toca el flujo del modo local):

- Crear partida: levanta el servidor en OTRO proceso
  (`python -m cliente_servidor.servidor --host 0.0.0.0`), así cualquier
  laptop de la misma red puede unirse, y conecta aquí a los jugadores de
  esta laptop. Si faltan jugadores, el resto entra con "Unirse por IP" desde
  otra laptop (la IP de esta se muestra en pantalla).
- Unirse por IP: escribe la IP de la laptop que creó la partida.

Las flechas cambian la opción y el valor; Enter elige; Esc vuelve al menú.
"""

import os
import socket
import subprocess
import sys
import threading
import time

import pygame

from cliente_servidor.protocolo import PUERTO
from cliente_servidor import cliente

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIFICULTADES = ["facil", "normal", "dificil"]
NOMBRE_DIFICULTAD = {"facil": "Fácil", "normal": "Normal", "dificil": "Difícil"}


def ip_local():
    """La IP de esta laptop en la red local (la que hay que darle a la otra).
    Conectar un socket UDP no manda nada: solo hace que el sistema escoja la
    interfaz de salida."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def levantar_servidor(jugadores, dificultad, puerto=PUERTO, host="0.0.0.0", extra=()):
    """El servidor en otro proceso. Devuelve (proceso, puerto) cuando ya
    escucha, o (None, texto del error)."""
    proceso = subprocess.Popen(
        [sys.executable, "-u", "-m", "cliente_servidor.servidor", "--jugadores", str(jugadores),
         "--host", host, "--puerto", str(puerto), "--dificultad", dificultad, *extra],
        cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    limite = time.time() + 20
    while time.time() < limite:
        linea = proceso.stdout.readline()
        if not linea:
            break
        if "escuchando en" in linea:
            puerto = int(linea.split("escuchando en ")[1].split()[0].rsplit(":", 1)[1])
            # Que el proceso no se trabe con la salida llena: alguien la lee.
            threading.Thread(target=lambda: [print(l, end="") for l in proceso.stdout],
                             daemon=True).start()
            return proceso, puerto
    proceso.kill()
    return None, "el servidor no arrancó (¿el puerto ya está ocupado?)"


class MenuRed:
    """Las opciones de la pantalla. Cada fila: (clave, texto)."""

    def __init__(self):
        self.fila = 0
        self.total = 2            # jugadores en la partida
        self.locales = 2          # cuántos juegan en esta laptop
        self.mandos = False       # los de esta laptop, ¿con mando primero?
        self.dificultad = "normal"
        self.ip = ""
        self.ip_propia = ip_local()

    def filas(self):
        return [
            ("total", f"Jugadores en la partida: {self.total}"),
            ("locales", f"Juegan en esta laptop: {self.locales}"),
            ("mandos", "Controles: " + ("mandos primero" if self.mandos else "teclado primero")),
            ("dificultad", f"Dificultad: {NOMBRE_DIFICULTAD[self.dificultad]}"),
            ("crear", "Crear partida en esta laptop"),
            ("ip", f"IP para unirse: {self.ip or '(escribe la IP)'}"),
            ("unirse", "Unirse por IP"),
            ("volver", "Volver"),
        ]

    def cambiar(self, clave, paso):
        if clave == "total":
            self.total = min(4, max(2, self.total + paso))
            self.locales = min(self.locales, self.total)
        elif clave == "locales":
            self.locales = min(self.total, max(1, self.locales + paso))
        elif clave == "mandos":
            self.mandos = not self.mandos
        elif clave == "dificultad":
            i = DIFICULTADES.index(self.dificultad)
            self.dificultad = DIFICULTADES[(i + paso) % len(DIFICULTADES)]

    def tecla(self, ev):
        """Devuelve la acción elegida ("crear", "unirse", "volver") o None."""
        claves = [c for c, _ in self.filas()]
        clave = claves[self.fila]
        if ev.key == pygame.K_ESCAPE:
            return "volver"
        if ev.key in (pygame.K_UP, pygame.K_w):
            self.fila = (self.fila - 1) % len(claves)
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.fila = (self.fila + 1) % len(claves)
        elif ev.key in (pygame.K_LEFT, pygame.K_a):
            self.cambiar(clave, -1)
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.cambiar(clave, 1)
        elif clave == "ip" and ev.key == pygame.K_BACKSPACE:
            self.ip = self.ip[:-1]
        elif clave == "ip" and ev.unicode and (ev.unicode.isdigit() or ev.unicode in ".:"):
            self.ip = (self.ip + ev.unicode)[:21]
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if clave in ("crear", "unirse", "volver"):
                return clave
            if clave == "ip":
                return "unirse"
            self.cambiar(clave, 1)
        return None

    def dibujar(self, pantalla, aviso=""):
        from juego.fuentes import fuente
        pantalla.fill((12, 14, 26))
        ancho, alto = pantalla.get_size()
        titulo = fuente("title").render("Jugar en red", True, (240, 242, 252))
        pantalla.blit(titulo, titulo.get_rect(midtop=(ancho // 2, int(alto * 0.08))))
        y = int(alto * 0.25)
        letra = fuente("subtitle")
        for i, (_, texto) in enumerate(self.filas()):
            marcado = i == self.fila
            imagen = letra.render(texto, True, (130, 230, 255) if marcado else (205, 210, 225))
            rect = imagen.get_rect(midtop=(ancho // 2, y))
            if marcado:
                pygame.draw.rect(pantalla, (40, 60, 100), rect.inflate(30, 10), border_radius=6)
            pantalla.blit(imagen, rect)
            y += imagen.get_height() + 14
        pequena = fuente("small")
        for k, linea in enumerate([f"La IP de esta laptop es {self.ip_propia} (puerto {PUERTO})",
                                   "Flechas para cambiar  ·  Enter para elegir  ·  Esc para volver",
                                   aviso]):
            if linea:
                imagen = pequena.render(linea, True, (255, 214, 120) if k == 2 else (170, 180, 200))
                pantalla.blit(imagen, imagen.get_rect(midtop=(ancho // 2, alto - 110 + k * 30)))


def abrir(juego):
    """La pantalla de "Jugar en red", con su bucle. Vuelve al menú al salir."""
    menu = MenuRed()
    reloj = pygame.time.Clock()
    aviso = ""
    while juego.running:
        reloj.tick(30)
        accion = None
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                juego.running = False
            elif ev.type == pygame.KEYDOWN:
                accion = menu.tecla(ev) or accion
        if accion == "volver":
            break
        if accion in ("crear", "unirse"):
            aviso = _jugar(juego, menu, accion) or ""
            if not juego.running:
                break
        menu.dibujar(juego.screen, aviso)
        pygame.display.flip()
    juego.current_screen = "menu"


def _jugar(juego, menu, accion):
    """Crea o se une; juega; devuelve un aviso para la pantalla (o "")."""
    esquemas = cliente.esquemas_para(menu.locales, menu.mandos)
    proceso = None
    if accion == "crear":
        cliente.aviso(juego.screen, ["Levantando el servidor..."])
        pygame.display.flip()
        proceso, puerto = levantar_servidor(menu.total, menu.dificultad)
        if proceso is None:
            return puerto
        host = "127.0.0.1"
    else:
        texto = menu.ip.strip() or "127.0.0.1"
        host, _, puerto = texto.partition(":")
        puerto = int(puerto) if puerto.isdigit() else PUERTO
    try:
        motivo = cliente.jugar(juego, host, puerto, esquemas,
                               avisar=lambda t: print("[red]", t, flush=True))
    finally:
        if proceso is not None:
            proceso.terminate()
            try:
                proceso.wait(3)
            except subprocess.TimeoutExpired:
                proceso.kill()
    if motivo == "salir":
        juego.running = False
    return {"error": "No se pudo conectar.", "perdida": "Se perdió la conexión.",
            "fin": "El servidor cerró la partida."}.get(motivo, "")
