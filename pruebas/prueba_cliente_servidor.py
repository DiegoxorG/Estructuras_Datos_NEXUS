"""Prueba del modo cliente-servidor (cliente_servidor/), sin ventana.

    python pruebas/prueba_cliente_servidor.py

Levanta el servidor en OTRO proceso (como de verdad) con un puerto libre,
conecta dos clientes falsos por socket (uno por jugador), revisa el saludo
(hola -> bienvenida con número de jugador), los manda a caminar a la derecha
y comprueba que las instantáneas que llegan cambian de posición. También
prueba lo de una vez (pulsar "celular" abre el panel del celular y "volver"
lo cierra), que el ack de las intenciones vuelve y que a un tercero se le
dice que la partida está llena. Termina sola en unos segundos.
"""

import os, sys, socket, subprocess, time
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

from cliente_servidor.protocolo import VERSION, LectorLineas, enviar, sin_nagle


def arrancar_servidor():
    """El servidor en un proceso aparte; el puerto 0 lo escoge el sistema y
    el servidor lo dice en su primera línea."""
    proceso = subprocess.Popen(
        [sys.executable, "-u", "-m", "cliente_servidor.servidor", "--jugadores", "2",
         "--puerto", "0", "--mapa", "Nave", "--segundos", "30",
         "--sin-presentaciones", "--aliens-quietos"],
        cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    limite = time.time() + 20
    while time.time() < limite:
        linea = proceso.stdout.readline()
        if not linea:
            break
        if "escuchando en" in linea:
            puerto = int(linea.split("escuchando en ")[1].split()[0].rsplit(":", 1)[1])
            return proceso, puerto
    proceso.kill()
    raise AssertionError("el servidor no dijo en qué puerto escucha")


class ClienteFalso:
    def __init__(self, puerto, nombre):
        self.sock = socket.create_connection(("127.0.0.1", puerto), timeout=20)
        sin_nagle(self.sock)
        self.lector = LectorLineas(self.sock)
        self.n = 0
        enviar(self.sock, {"tipo": "hola", "version": VERSION, "nombre": nombre})
        self.bienvenida = self.lector.siguiente()
        assert self.bienvenida["tipo"] == "bienvenida", self.bienvenida

    def intencion(self, mantener=(), pulsar=()):
        self.n += 1
        enviar(self.sock, {"tipo": "intencion", "n": self.n,
                           "mantener": list(mantener), "pulsar": list(pulsar)})

    def estado(self):
        """La siguiente instantánea (se salta los avisos de espera)."""
        while True:
            m = self.lector.siguiente()
            if m["tipo"] == "estado":
                return m

    def ultimo_estado(self, segundos):
        """Lee lo que llegue durante `segundos` y devuelve la última instantánea."""
        fin = time.time() + segundos
        ultimo = self.estado()
        while time.time() < fin:
            ultimo = self.estado()
        return ultimo


proceso, puerto = arrancar_servidor()
try:
    inicio = time.time()
    a = ClienteFalso(puerto, "falso 1")
    b = ClienteFalso(puerto, "falso 2")
    assert (a.bienvenida["jugador"], b.bienvenida["jugador"]) == (0, 1), "cada conexión es un jugador"
    assert a.bienvenida["jugadores"] == 2 and a.bienvenida["mapa"] == "Nave"
    print("bienvenida:", a.bienvenida)

    # Quietos: la posición no cambia entre instantáneas.
    a.intencion(); b.intencion()
    e0 = a.ultimo_estado(0.3)
    e1 = a.ultimo_estado(0.3)
    antes = [(j["hx"], j["hy"]) for j in e0["jugadores"]]
    assert antes == [(j["hx"], j["hy"]) for j in e1["jugadores"]], "sin intención no se mueven"
    assert e1["cuadro"] > e0["cuadro"], "el servidor avanza solo"
    assert e0["fase"] and len(e0["aliens"]) > 0, "la instantánea trae la misión y los aliens"

    # Los dos a la derecha (la intención se repite como haría el cliente).
    for _ in range(12):
        a.intencion(mantener=["derecha"]); b.intencion(mantener=["derecha"])
        a.ultimo_estado(0.1); b.ultimo_estado(0.0)
    e2 = a.ultimo_estado(0.1)
    despues = [(j["hx"], j["hy"]) for j in e2["jugadores"]]
    print("antes:", antes, "después:", despues)
    for (x0, _), (x1, _) in zip(antes, despues):
        assert x1 > x0, "con 'derecha' mantenida cada jugador va a la derecha"
    assert max(x1 - x0 for (x0, _), (x1, _) in zip(antes, despues)) > 40
    assert e2["ack"][0] == a.n, f"el ack es la última intención de J1 ({e2['ack']} vs {a.n})"
    # Las dos conexiones reciben la misma partida.
    eb = b.ultimo_estado(0.1)
    assert abs(eb["cuadro"] - e2["cuadro"]) < 60

    # Soltar: se quedan quietos otra vez.
    a.intencion(); b.intencion()
    q0 = a.ultimo_estado(0.2)
    q1 = a.ultimo_estado(0.3)
    assert [(j["hx"], j["hy"]) for j in q0["jugadores"]] == \
           [(j["hx"], j["hy"]) for j in q1["jugadores"]], "al soltar se detienen"

    # Lo de una vez: el celular se abre y "volver" lo cierra (solo el de J2).
    b.intencion(pulsar=["celular"])
    e3 = b.ultimo_estado(0.3)
    assert e3["jugadores"][1]["panel"] is not None and e3["jugadores"][1]["panel"]["tipo"] == "celular"
    assert e3["jugadores"][0]["panel"] is None, "la tecla de J2 no le abre nada a J1"
    print("panel de J2:", e3["jugadores"][1]["panel"]["titulo"])
    b.intencion(pulsar=["volver"])
    e4 = b.ultimo_estado(0.3)
    for _ in range(5):          # el celular puede tener una vista abierta: atrás hasta cerrar
        if e4["jugadores"][1]["panel"] is None:
            break
        b.intencion(pulsar=["volver"])
        e4 = b.ultimo_estado(0.3)
    assert e4["jugadores"][1]["panel"] is None, "volver cierra el celular"

    # Un tercero que llega tarde: la partida está llena.
    tarde = socket.create_connection(("127.0.0.1", puerto), timeout=10)
    enviar(tarde, {"tipo": "hola", "version": VERSION, "nombre": "tarde"})
    respuesta = LectorLineas(tarde).siguiente()
    assert respuesta["tipo"] == "error" and "2 jugadores" in respuesta["texto"], respuesta
    tarde.close()

    a.sock.close(); b.sock.close()
    proceso.wait(timeout=10)       # sin jugadores, el servidor se apaga solo
    salida = proceso.stdout.read()
    assert "se desconectaron todos" in salida, salida
    print(f"OK cliente-servidor en {time.time() - inicio:.1f} s")
finally:
    if proceso.poll() is None:
        proceso.kill()
