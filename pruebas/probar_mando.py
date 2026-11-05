"""Muestra en vivo qué hace en el juego cada botón del mando conectado.

    python pruebas/probar_mando.py

Para revisar en un minuto los mandos de verdad (Xbox, PlayStation...):

- al conectar cada uno dice si se tomó como **controller** (SDL lo reconoce:
  botones por posición, lo normal) o como **joystick de respaldo** (números
  de Xbox de mandos.py: BOTONES, EJE_X, EJE_Y, EJE_LT), y de qué tipo es;
- cada botón, gatillo o cruceta que se presione sale con la ACCIÓN del juego
  que dispara (interactuar, habilidad, celular...) y cómo se llama en ese
  mando (A / Cruz...);
- "ahora" muestra lo que se está manteniendo (moverse, sigilo, mantener A).

Los eventos JOY* de un mando que va por controller salen como "ignorado":
SDL los manda igual, pero el juego no los cuenta (si no, cada botón contaría
dos veces). Cierra la ventana o presiona ESC para salir.
"""

import os, sys
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
import pygame
from juego import mandos
pygame.init()
pantalla = pygame.display.set_mode((900, 560))
pygame.display.set_caption("Probar mando")
fuente = pygame.font.SysFont("consolas", 17)
reloj = pygame.time.Clock()
m = mandos.Mandos()
log = []

NOMBRE_SDL = {v: k for k, v in mandos.BOTONES_CONTROLLER.items()}
NOMBRE_SDL.update({b: "DPAD_" + a.upper() for b, a in mandos.CRUCETA_CONTROLLER.items()})
EJES_SDL = {mandos.EJE_C_X: "stick izq. X", mandos.EJE_C_Y: "stick izq. Y",
            mandos.EJE_C_LT: "gatillo izq. (LT/L2)"}


def como_se_toma(mando):
    tipo = mandos.tipo_de_mando(mando)
    tipo = "otro (pistas como Xbox)" if tipo == "otro" else mandos.NOMBRE_TIPO[tipo]
    forma = "controller (por posición)" if mandos.es_controller(mando) else "joystick de respaldo (números de Xbox)"
    return f"{mando.get_name()}  ->  {forma}, tipo {tipo}"


def describir(puesto, acciones):
    if not acciones:
        return "(nada)"
    tipo = m.tipo(puesto)
    return ", ".join(f"{a} [{mandos.nombre_boton(a, tipo)}]" for _, a in acciones)


def anotar(texto):
    log.append(texto)
    print(texto)


while True:
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
            pygame.quit(); sys.exit()
        antes = dict(m.por_puesto)
        puesto = m._puesto_de(getattr(ev, "instance_id", None))
        mando = m.por_puesto.get(puesto)
        acciones = m.evento(ev)
        if ev.type in mandos.EVENTOS_CONEXION:
            for p, x in m.por_puesto.items():
                if antes.get(p) is not x:
                    anotar(f"CONECTADO Mando {p - 1}: {como_se_toma(x)}")
            for p in antes:
                if p not in m.por_puesto:
                    anotar(f"DESCONECTADO Mando {p - 1}")
            continue
        if mando is None:
            continue
        quien = f"Mando {puesto - 1}"
        es_c = mandos.es_controller(mando)
        if ev.type in (pygame.JOYBUTTONDOWN, pygame.JOYHATMOTION, pygame.JOYAXISMOTION) and es_c:
            if ev.type == pygame.JOYBUTTONDOWN:
                anotar(f"{quien}: joy botón {ev.button} (ignorado: va por controller)")
            continue
        if ev.type == pygame.JOYBUTTONDOWN:
            extra = ("sigilo (mantener)" if ev.button == mandos.BOTONES["LB"]
                     else describir(puesto, acciones))
            anotar(f"{quien}: botón {ev.button}  ->  {extra}")
        elif ev.type == pygame.JOYHATMOTION and ev.value != (0, 0):
            anotar(f"{quien}: cruceta {ev.value}  ->  {describir(puesto, acciones)}")
        elif ev.type == pygame.JOYAXISMOTION and abs(ev.value) > 0.6:
            anotar(f"{quien}: eje {ev.axis} = {ev.value:+.2f}  ->  {describir(puesto, acciones)}")
        elif ev.type == pygame.CONTROLLERBUTTONDOWN:
            sdl = NOMBRE_SDL.get(ev.button, str(ev.button))
            local = mandos.NOMBRES_BOTONES.get(m.tipo(puesto), mandos.NOMBRES_BOTONES["xbox"]).get(sdl, sdl)
            extra = "sigilo (mantener)" if sdl == "LB" else describir(puesto, acciones)
            anotar(f"{quien}: botón {local} (SDL {sdl})  ->  {extra}")
        elif ev.type == pygame.CONTROLLERAXISMOTION and abs(mandos._normalizar(ev.value)) > 0.6:
            nombre = EJES_SDL.get(ev.axis, f"eje {ev.axis}")
            extra = "sigilo (mantener)" if ev.axis == mandos.EJE_C_LT else describir(puesto, acciones)
            anotar(f"{quien}: {nombre} = {mandos._normalizar(ev.value):+.2f}  ->  {extra}")
        log = log[-16:]
    pantalla.fill((18, 19, 30))
    y = 12
    if not m.por_puesto:
        pantalla.blit(fuente.render("No hay mandos conectados.", True, (245, 130, 120)), (12, y))
        y += 26
    for puesto, joy in sorted(m.por_puesto.items()):
        estado = {a: m.presionada(mandos.tecla_virtual(puesto, a)) for a in mandos.ACCIONES}
        tipo = m.tipo(puesto)
        activos = [f"{a} [{mandos.nombre_boton(a, tipo)}]" for a, v in estado.items() if v]
        pantalla.blit(fuente.render(f"Mando {puesto - 1}: {como_se_toma(joy)}", True, (255, 214, 64)), (12, y))
        y += 22
        pantalla.blit(fuente.render(f"  ahora: {', '.join(activos) or '-'}", True, (235, 238, 250)), (12, y))
        y += 30
    for linea in log:
        pantalla.blit(fuente.render(linea, True, (150, 156, 190)), (12, y))
        y += 20
    pygame.display.flip()
    reloj.tick(60)
