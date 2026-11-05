"""El servidor de NEXUS: dueño de la partida, sin ventana.

    python -m cliente_servidor.servidor --jugadores 2
    python -m cliente_servidor.servidor --jugadores 4 --roles Tecnomante,Forjador,Biomante,Resonante
    python -m cliente_servidor.servidor --jugadores 2 --puerto 6000 --dificultad facil --mapa Nave

Escucha en 127.0.0.1, espera a que se conecten todos (una conexión por
jugador) y corre la partida de verdad: el mismo `Game` de juego/app.py, sin
ventana (SDL_VIDEODRIVER=dummy), como lo hace pruebas/simulador.py. Lo que
mandan los clientes se convierte en las teclas del puesto de cada jugador.

Hilos:
- el principal acepta las conexiones y después corre el juego a 60 Hz y
  manda las instantáneas (30 por segundo). Es el ÚNICO que toca `Game`.
- uno por conexión que lee las intenciones y las deja en el `Buzon` de ese
  jugador (con un candado: el principal las saca de ahí cada cuadro).

Se termina cuando se desconectan todos (o con Ctrl+C, o con --segundos).
"""

import argparse
import os
import socket
import sys
import threading
import time

# El servidor nunca abre ventana ni suena: eso es del cliente.
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(RAIZ)            # las imágenes y mapas se buscan desde aquí (como main.py)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from cliente_servidor.protocolo import (VERSION, HOST, PUERTO, HZ_JUEGO, CUADROS_POR_INSTANTANEA,
                                        MANTENER, PULSAR, LectorLineas, ConexionCerrada,
                                        enviar, a_bytes, sin_nagle)

DT_MS = 1000 // HZ_JUEGO      # 16, lo mismo que usa pruebas/simulador.py


class Teclas(dict):
    """Lo que el juego cree que es `pygame.key.get_pressed()`: lo que no está
    es una tecla suelta."""

    def __getitem__(self, tecla):
        return self.get(tecla, False)


class Buzon:
    """Lo último que pidió un jugador. Lo escribe su hilo lector y lo lee el
    hilo del juego, por eso todo pasa con `candado`."""

    def __init__(self):
        self.candado = threading.Lock()
        self.mantener = set()     # acciones mantenidas (estado: la última manda)
        self.pulsar = []          # acciones de una vez (eventos: se acumulan)
        self.ultimo_n = -1        # número de la última intención (para el ack)
        self.conectado = True

    def sacar(self):
        with self.candado:
            pulsar, self.pulsar = self.pulsar, []
            return set(self.mantener), pulsar, self.ultimo_n


class Servidor:
    def __init__(self, jugadores=2, host=HOST, puerto=PUERTO, roles=None,
                 dificultad="normal", mapa=None, segundos=None, avisar=print,
                 presentaciones=True, aliens_quietos=False):
        self.n = jugadores
        self.host, self.puerto = host, puerto
        self.roles = roles
        self.clave_dificultad = dificultad
        self.mapa = mapa
        self.segundos = segundos
        self.avisar = avisar
        self.presentaciones = presentaciones
        self.aliens_quietos = aliens_quietos
        self.sock = None
        self.juego = None
        self.conexiones = []      # (socket, LectorLineas), una por jugador
        self.buzones = []
        self.teclas = Teclas()
        self.activo = True
        self.cuadro = 0

    # -- Arranque -----------------------------------------------------------------

    def escuchar(self):
        """Abre el puerto. Con puerto 0 el sistema da uno libre (las pruebas)."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if os.name != "nt":
            # Para poder volver a abrir el servidor enseguida en Linux/Mac. En
            # Windows esta opción deja que DOS servidores tomen el mismo puerto.
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.puerto))
        self.sock.listen(self.n)
        self.puerto = self.sock.getsockname()[1]
        # Esta línea la busca pruebas/prueba_cliente_servidor.py para saber el puerto.
        self.avisar(f"escuchando en {self.host}:{self.puerto} (esperando {self.n} jugadores)")

    def preparar_partida(self):
        """El mismo Game del modo local, pero saltándose los menús: la
        cantidad, la dificultad y los roles vienen de los argumentos."""
        import pygame
        pygame.init()
        from juego import app as App
        from juego import objetos_mapa
        from juego.dificultad import Dificultad
        if self.mapa:
            objetos_mapa.mapa_activo = lambda: self.mapa
        g = App.Game()
        if self.clave_dificultad:
            g.dificultad = Dificultad(self.clave_dificultad)
        nombres = [r["nombre"] for r in App.ROLES]
        roles = list(self.roles or nombres[:self.n])
        if len(roles) != self.n or any(r not in nombres for r in roles) or len(set(roles)) != len(roles):
            raise SystemExit(f"--roles necesita {self.n} roles distintos de: {', '.join(nombres)}")
        g.cantidad_jugadores = self.n
        g.abrir_seleccion_roles(ir=False)
        for estado, rol in zip(g.seleccion_roles, roles):
            estado["rol"], estado["listo"] = rol, True
        g._preparar_partida()
        g.current_screen = "partida"
        # El tutorial se maneja con los paneles del modo local: en el prototipo
        # se salta y los aliens despiertan de una.
        g.saltar_tutorial()
        if not self.presentaciones:
            g.presentacion = None
        if self.aliens_quietos:
            for alien in g.aliens:          # como en pruebas/prueba_partida.py
                alien.descanso_ms = 10 ** 9
        for jugador in g.jugadores:
            # En local los puestos 3 y 4 solo caminan con mando; aquí su
            # entrada viene del socket.
            jugador.puede_moverse = True
        # El gancho de la entrada: el juego pregunta las teclas con
        # self.mandos.envolver(pygame.key.get_pressed()). Cambiando `envolver`
        # en ESTA instancia, lo que lee son las teclas que armó el servidor
        # con lo que mandaron los clientes (no hay que tocar app.py).
        g.mandos.envolver = lambda _teclado_real: self.teclas
        self.juego = g
        self.avisar(f"partida lista: mapa {g.mundo.nombre_mapa}, roles {roles}")

    def aceptar(self):
        """Espera a los N jugadores. Cada uno manda `hola` y recibe su número."""
        self.sock.settimeout(0.5)
        while len(self.conexiones) < self.n and self.activo:
            try:
                s, direccion = self.sock.accept()
            except socket.timeout:
                continue
            sin_nagle(s)
            s.settimeout(5.0)
            lector = LectorLineas(s)
            try:
                hola = lector.siguiente()
                if hola.get("tipo") != "hola" or hola.get("version") != VERSION:
                    enviar(s, {"tipo": "error", "texto": f"se esperaba hola versión {VERSION}"})
                    s.close()
                    continue
                numero = len(self.conexiones)
                g = self.juego
                enviar(s, {"tipo": "bienvenida", "jugador": numero, "jugadores": self.n,
                           "roles": [j.rol for j in g.jugadores],
                           "mapa": g.mundo.nombre_mapa, "ancho": g.mundo.ancho,
                           "alto": g.mundo.alto, "escala": g.mundo.escala,
                           "hz": HZ_JUEGO // CUADROS_POR_INSTANTANEA})
            except (OSError, ConexionCerrada):
                s.close()
                continue
            # Con timeout el hilo lector puede despertar a ver si se apagó el
            # servidor, y un cliente que no lee no traba al juego para siempre.
            s.settimeout(1.0)
            buzon = Buzon()
            self.conexiones.append((s, lector))
            self.buzones.append(buzon)
            threading.Thread(target=self._leer, args=(lector, buzon), daemon=True,
                             name=f"lector-J{numero + 1}").start()
            self.avisar(f"J{numero + 1} conectado desde {direccion[0]}:{direccion[1]} "
                        f"({hola.get('nombre', '')})")
            self._a_todos({"tipo": "espera", "conectados": len(self.conexiones),
                           "faltan": self.n - len(self.conexiones)})

    # -- Hilos lectores -----------------------------------------------------------------

    def _leer(self, lector, buzon):
        try:
            while self.activo:
                try:
                    mensaje = lector.siguiente()
                except socket.timeout:
                    continue
                tipo = mensaje.get("tipo")
                if tipo == "intencion":
                    mantener = {a for a in mensaje.get("mantener", ()) if a in MANTENER}
                    pulsar = [a for a in mensaje.get("pulsar", ()) if a in PULSAR]
                    with buzon.candado:
                        buzon.mantener = mantener
                        buzon.pulsar.extend(pulsar[:16])
                        del buzon.pulsar[:-32]      # que nadie llene la cola
                        if isinstance(mensaje.get("n"), int):
                            buzon.ultimo_n = mensaje["n"]
                elif tipo == "adios":
                    break
        except (OSError, ConexionCerrada):
            pass
        with buzon.candado:
            buzon.conectado = False
            buzon.mantener = set()

    # -- El juego ---------------------------------------------------------------------

    def bucle(self):
        """60 cuadros por segundo con paso fijo; instantánea cada 2."""
        paso = 1.0 / HZ_JUEGO
        siguiente = time.perf_counter()
        inicio = siguiente
        fin_avisado = False
        while self.activo:
            acks = self._aplicar_entradas()
            g = self.juego
            if g.mision.resultado is None and g.current_screen == "partida":
                g._actualizar_partida(DT_MS)
            elif not fin_avisado:
                fin_avisado = True
                self.avisar(f"partida terminada: {g.mision.resultado}")
            self.cuadro += 1
            if self.cuadro % HZ_JUEGO == 0:
                self._rechazar_sobrantes()
            if self.cuadro % CUADROS_POR_INSTANTANEA == 0:
                self._a_todos(self.instantanea(acks))
            if not any(b.conectado for b in self.buzones):
                self.avisar("se desconectaron todos")
                break
            if self.segundos is not None and time.perf_counter() - inicio > self.segundos:
                self.avisar(f"pasaron {self.segundos} s (--segundos)")
                break
            siguiente += paso
            espera = siguiente - time.perf_counter()
            if espera > 0:
                time.sleep(espera)
            elif espera < -0.25:
                siguiente = time.perf_counter()   # se atrasó mucho: no intenta recuperar

    def _rechazar_sobrantes(self):
        """Con la partida andando, al que llega tarde se le dice que está llena
        (si no, se quedaría esperando la bienvenida en la cola del socket)."""
        self.sock.settimeout(0)
        while True:
            try:
                s, _ = self.sock.accept()
            except OSError:          # BlockingIOError: no hay nadie esperando
                return
            # En otro hilo: primero se lee su hola (cerrar con datos sin leer
            # manda un RST y el cliente no alcanzaría a ver el error).
            threading.Thread(target=self._rechazar, args=(s,), daemon=True).start()

    def _rechazar(self, s):
        try:
            s.settimeout(2.0)
            LectorLineas(s).siguiente()
        except (OSError, ConexionCerrada):
            pass
        try:
            enviar(s, {"tipo": "error", "texto": f"la partida ya tiene sus {self.n} jugadores"})
            s.shutdown(socket.SHUT_WR)
        except OSError:
            pass
        s.close()

    def _aplicar_entradas(self):
        """Lo que mandaron los clientes -> las teclas de cada puesto."""
        g = self.juego
        teclas = Teclas()
        pulsados, acks = [], []
        for jugador, buzon in zip(g.jugadores, self.buzones):
            mantener, pulsar, ultimo_n = buzon.sacar()
            acks.append(ultimo_n)
            for accion in mantener:
                for tecla in jugador.teclas.get(accion, ()):
                    teclas[tecla] = True
                for tecla in jugador.personaje.controles.get(accion, ()):
                    teclas[tecla] = True
            pulsados.append((jugador, pulsar))
        self.teclas = teclas
        # Lo pulsado va antes de actualizar, como en el modo local (primero
        # los eventos y después _actualizar_partida).
        for jugador, pulsar in pulsados:
            for accion in pulsar:
                self._pulsar(jugador, accion)
        return acks

    def _pulsar(self, jugador, accion):
        """Una acción de una vez = el KEYDOWN de la tecla de ese jugador."""
        g = self.juego
        if g.mision.resultado is not None:
            return
        if g.presentacion is not None and g.presentacion.abierta:
            # Fácil: la ventana que presenta un alien se cierra como con el mando.
            if accion in ("interactuar", "habilidad", "volver"):
                g.presentacion.cerrar()
            return
        if accion == "volver":
            # Lo mismo que el botón B del mando (Game._tecla_mando).
            if jugador.ocupado:
                if jugador.panel.get("tipo") == "celular":
                    from redes import celular
                    celular.volver(g, jugador)
                else:
                    jugador.cerrar_panel()
                return
            accion = "soltar"
        teclas = jugador.teclas.get(accion, ())
        if teclas:
            g._tecla_en_partida(teclas[0])

    # -- Instantáneas -----------------------------------------------------------------

    def instantanea(self, acks=None):
        g = self.juego
        m = g.mision
        jugadores = []
        for i, j in enumerate(g.jugadores):
            p = j.personaje
            buzon = self.buzones[i] if i < len(self.buzones) else None
            jugadores.append({
                "n": i, "rol": j.rol,
                "x": round(p.x, 1), "y": round(p.y, 1),            # esquina del sprite
                "hx": j.hitbox.centerx, "hy": j.hitbox.centery,     # centro de la hitbox
                "dir": p.direccion, "mov": bool(p.moviendose),
                "vidas": j.vidas, "vmax": j.vidas_max, "infinitas": j.vidas_infinitas,
                "preso": j.preso is not None, "elim": j.eliminado, "esc": j.escondido,
                "sig": j.sigilo, "pulso": round(j.pulso), "puntos": j.puntos,
                "piezas": j.piezas, "objetos": dict(j.objetos),
                "sala": j.sala or "", "msg": j.mensaje if j.mensaje_ms > 0 else "",
                "pista": j.pista_mision or "",
                "prog": [j.progreso[0], round(j.progreso[1], 2)] if j.progreso else None,
                "panel": _panel(j),
                "on": buzon.conectado if buzon else False,
            })
        aliens = [{"tipo": a.tipo, "nombre": a.nombre,
                   "x": round(a.centro[0]), "y": round(a.centro[1]),
                   "ang": round(a.angulo, 3), "acc": a.accion,
                   "vis": round(a.alcance_vision), "medio": round(a.datos.get("medio_angulo", 0), 3)}
                  for a in g._aliens_a_la_vista()]
        return {
            "tipo": "estado", "cuadro": self.cuadro, "t": g.tiempo_jugado_ms,
            "fase": m.fase, "objetivo": m.objetivo() if m.activa else "",
            "resultado": m.resultado, "entregadas": m.piezas_entregadas,
            "apagon": bool(g.eventos is not None and g.eventos.apagon),
            "capsula": list(m.capsula) if m.capsula is not None else None,
            "piezas": [list(p["rect"].center) for p in g.piezas if not p.get("recogida")],
            "puntos": g.equipo.total,
            "ack": acks or [],
            "presentacion": _presentacion(g),
            "jugadores": jugadores, "aliens": aliens,
        }

    def _a_todos(self, mensaje):
        datos = a_bytes(mensaje)
        for (s, _), buzon in zip(self.conexiones, self.buzones):
            if not buzon.conectado:
                continue
            try:
                s.sendall(datos)
            except OSError:
                # Incluye el timeout: un cliente que no lee se queda afuera
                # en vez de congelar la partida de los demás.
                with buzon.candado:
                    buzon.conectado = False
                    buzon.mantener = set()

    # -- Todo junto ---------------------------------------------------------------------

    def correr(self):
        try:
            if self.sock is None:
                self.escuchar()
            # Se escucha ANTES de armar la partida (tarda unos segundos): los
            # clientes que llegan mientras tanto esperan en la cola del socket.
            self.preparar_partida()
            self.aceptar()
            if self.activo:
                self.avisar("empieza la partida")
                self.bucle()
        except KeyboardInterrupt:
            self.avisar("Ctrl+C")
        finally:
            self.cerrar()

    def cerrar(self):
        self.activo = False
        for s, _ in self.conexiones:
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            s.close()
        if self.sock is not None:
            self.sock.close()


def _presentacion(g):
    """La ventana que presenta un alien nuevo (pausa a todos hasta que alguien
    la cierre con interactuar o habilidad)."""
    p = g.presentacion
    if p is None or not p.abierta:
        return None
    titulo, lineas = p.textos()
    return {"titulo": titulo, "lineas": lineas, "jugador": g.jugadores.index(p.actual["jugador"]),
            "x": p.actual["alien"].centro[0], "y": p.actual["alien"].centro[1]}


def _panel(jugador):
    """El panel abierto, en texto: título, cuerpo, opciones y cursor."""
    p = jugador.panel
    if p is None:
        return None

    def texto(x):
        # Las opciones son de varias formas: {"texto": ...}, ("Volver", "volver"),
        # ("post", Publicacion) en el celular...
        if isinstance(x, (tuple, list)):
            con_texto = next((e for e in x if hasattr(e, "texto")), None)
            x = con_texto if con_texto is not None else next((e for e in x if isinstance(e, str)), "")
        if isinstance(x, dict):
            x = x.get("texto") or x.get("titulo") or x.get("nombre") or ""
        elif hasattr(x, "texto"):
            x = x.texto
        return str(x)[:90]

    cuerpo = p.get("cuerpo") or []
    if isinstance(cuerpo, str):
        cuerpo = [cuerpo]
    titulo = p.get("titulo") or (f"NEXUS · {p.get('pestana', '')}" if p.get("tipo") == "celular"
                                 else p.get("tipo") or "")
    return {"tipo": p.get("tipo"), "titulo": texto(titulo),
            "cuerpo": [texto(c) for c in cuerpo if isinstance(c, (str, dict))][:8],
            "opciones": [texto(o) for o in (p.get("opciones") or [])][:12],
            "cursor": jugador.cursor, "pie": texto(p.get("pie") or "")}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Servidor de NEXUS (una conexión por jugador).")
    ap.add_argument("--jugadores", type=int, default=2, choices=(2, 3, 4))
    ap.add_argument("--host", default=HOST, help="127.0.0.1 (por defecto); 0.0.0.0 para la red local")
    ap.add_argument("--puerto", type=int, default=PUERTO, help="0 = uno libre")
    ap.add_argument("--roles", default=None,
                    help="separados por coma, p. ej. Tecnomante,Forjador (por defecto, en orden)")
    ap.add_argument("--dificultad", default="normal",
                    choices=("facil", "normal", "dificil", "inteligente"))
    ap.add_argument("--mapa", default=None, help="por defecto el de Hitboxes/mapa_activo.json")
    ap.add_argument("--segundos", type=float, default=None, help="apagarse solo después de esto")
    ap.add_argument("--sin-presentaciones", action="store_true",
                    help="no pausar la primera vez que se ve cada alien")
    ap.add_argument("--aliens-quietos", action="store_true",
                    help="los aliens no se mueven (para pruebas y para mostrar la red)")
    args = ap.parse_args(argv)
    roles = [r.strip() for r in args.roles.split(",")] if args.roles else None
    Servidor(args.jugadores, args.host, args.puerto, roles, args.dificultad, args.mapa,
             args.segundos, avisar=lambda texto: print("[servidor]", texto, flush=True),
             presentaciones=not args.sin_presentaciones, aliens_quietos=args.aliens_quietos).correr()


if __name__ == "__main__":
    main()
