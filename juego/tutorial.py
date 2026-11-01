"""Tutorial al empezar la partida, sin tiempo: cada quien va a su ritmo.

En la feria la gente se sienta a jugar sin haber leído nada. Antes de que los
aliens despierten, cada jugador ve en su pantalla unos pasos cortos y pasa al
siguiente con su tecla de habilidad cuando ya lo leyó. Los de moverse y
caminar en sigilo también se completan solos al hacerlos. Mientras dura:

- los aliens duermen (no se mueven ni ven ni oyen),
- el cronómetro de la partida no corre,
- no hay eventos aleatorios,
- la puerta de la prisión no abre (mision.py pregunta `juego.en_tutorial`),
  para que nadie avance con los aliens dormidos.

Termina, y la nave "arranca", solo cuando todos los que se pueden mover
terminaron sus pasos. Quien acaba primero puede caminar por la prisión
mientras espera a los demás.
"""

MS_SIGILO_NECESARIO = 700

# {mover}, {sigilo}, {interactuar}, {habilidad}, {habilidades}, {celular}, {soltar} y {vidas} se cambian por
# las teclas de cada jugador. "accion" dice si además se completa haciéndolo.
PASOS = [
    {"texto": "Muévete con {mover}.", "accion": "mover"},
    {"texto": "Mantén {sigilo} mientras caminas: vas lento pero casi no haces ruido.",
     "accion": "sigilo"},
    {"texto": "El anillo a tu alrededor es tu ruido. Si un alien queda adentro, te oye. "
              "Entre más asustado, más grande.", "accion": "leer"},
    {"texto": "No ves a través de las paredes. Si se va la luz, solo alumbra tu "
              "linterna, nada eléctrico funciona y no verás a los aliens ni por dónde "
              "miran. Busquen la caja de fusibles que parpadea en rojo y enciéndanla.",
     "accion": "leer"},
    {"texto": "{celular}: tu celular con NEXUS. Los aliens riegan rumores falsos: vayan "
              "al lugar, saquen una foto y desmiéntanlos. Si la tripulación les cree, les "
              "pasan los planos de la cápsula. Ojo: con el celular abierto no te mueves.",
     "accion": "leer"},
    {"texto": "Por la nave caminan otros prisioneros. Uno es el Cambiaformas disfrazado: "
              "no habla y su nombre falla. Si te ve solo, se revela. ¡No te alejes de tu equipo!",
     "accion": "leer"},
    {"texto": "{interactuar}: usar, leer notas y esconderte. {soltar}: dejar algo del "
              "inventario en el piso. Si te atrapan vas a una celda y tus compañeros te sacan. "
              "Tienes {vidas}.", "accion": "leer"},
    {"texto": "{interactuar} junto a un prisionero: \"¿vienes conmigo?\". Los verdes te "
              "siguen; llévalos a la cápsula y contarán en NEXUS que los salvaste ({interactuar} "
              "otra vez junto a él: que te espere). Si uno acepta sin decir nada y se te pega "
              "demasiado... desconfía.", "accion": "leer"},
    {"texto": "{habilidad}: usar tu habilidad.  {habilidades}: árbol de habilidades. "
              "¡Escapen juntos!", "accion": "leer"},
]


def con_teclas(texto, jugador):
    """Cambia {mover}, {sigilo}... por las teclas de ese jugador."""
    esquema = getattr(jugador, "esquema", jugador.puesto)
    mover = "WASD" if esquema == 0 else "las flechas" if esquema == 1 \
        else "el stick" if getattr(jugador, "con_mando", False) else jugador.controles_nombre
    return texto.format(
        mover=mover, sigilo=jugador.nombre_tecla("sigilo"),
        interactuar=jugador.nombre_tecla("interactuar"),
        habilidad=jugador.nombre_tecla("habilidad"),
        habilidades=jugador.nombre_tecla("habilidades"),
        celular=jugador.nombre_tecla("celular"),
        soltar=jugador.nombre_tecla("soltar"),
        vidas=_vidas_texto(jugador))


def _vidas_texto(jugador):
    if getattr(jugador, "vidas_infinitas", False):
        return "vidas infinitas"
    n = getattr(jugador, "vidas_max", 3)
    return f"{n} vida{'s' if n != 1 else ''}"


def pasos_con_teclas(jugador):
    """Todos los pasos, ya con las teclas del jugador (para repasarlos en una
    Terminal NEXUS)."""
    return [con_teclas(p["texto"], jugador) for p in PASOS]


class Tutorial:
    def __init__(self, jugadores):
        self.activo = True
        self.estado = {id(j): {"paso": 0, "sigilo_ms": 0, "listo": False} for j in jugadores}
        self.jugadores = list(jugadores)

    def _de(self, jugador):
        return self.estado.setdefault(id(jugador), {"paso": 0, "sigilo_ms": 0, "listo": False})

    def _necesarios(self):
        """Los que tienen que terminarlo: los que se pueden mover (un puesto de
        mando sin mando conectado no puede ni presionar la tecla)."""
        return [j for j in self.jugadores if j.puede_moverse and not j.eliminado] or self.jugadores

    def listos(self):
        """(cuántos terminaron, cuántos tienen que terminar)."""
        necesarios = self._necesarios()
        return sum(self._de(j)["listo"] for j in necesarios), len(necesarios)

    def esta_listo(self, jugador):
        return self._de(jugador)["listo"]

    def _avanzar(self, e):
        e["paso"] += 1
        if e["paso"] >= len(PASOS):
            e["paso"] = len(PASOS) - 1
            e["listo"] = True

    def actualizar(self, dt):
        if not self.activo:
            return
        for jugador in self.jugadores:
            e = self._de(jugador)
            if e["listo"]:
                continue
            accion = PASOS[e["paso"]]["accion"]
            if accion == "mover" and jugador.personaje.moviendose:
                self._avanzar(e)
            elif accion == "sigilo":
                if jugador.personaje.moviendose and jugador.sigilo:
                    e["sigilo_ms"] += dt
                if e["sigilo_ms"] >= MS_SIGILO_NECESARIO:
                    self._avanzar(e)
        hechos, total = self.listos()
        if hechos >= total:
            self.activo = False

    def siguiente(self, jugador):
        """Tecla de habilidad: pasa al siguiente paso (en el último, termina)."""
        e = self._de(jugador)
        if not e["listo"]:
            self._avanzar(e)
        self.actualizar(0)

    def texto(self, jugador):
        """(número de paso, total, texto ya con sus teclas) o None si ya acabó."""
        if not self.activo:
            return None
        e = self._de(jugador)
        if e["listo"]:
            hechos, total = self.listos()
            return (len(PASOS), len(PASOS),
                    f"¡Listo! Esperando a los demás ({hechos}/{total} listos)...")
        return (e["paso"] + 1, len(PASOS), con_teclas(PASOS[e["paso"]]["texto"], jugador))
