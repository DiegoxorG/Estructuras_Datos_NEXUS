"""Nodo del árbol de logros (Estructuras/arbol_logros.py)."""


class NodoLogro:
    def __init__(self, clave, nombre, descripcion, rama="", padre=None):
        self.clave = clave
        self.nombre = nombre
        self.descripcion = descripcion
        self.rama = rama              # "sigilo", "escape", "nexus"... (para el color)
        self.padre = padre
        self.hijos = []               # N-ario: cuantos hijos quiera
        self.obtenido = False
        self.quien = None             # rol de quien lo consiguió (o None: el equipo)
        self.por_camino = False       # se marcó porque consiguieron un hijo suyo
        # Compuesto: "cualquiera de los de abajo". Se consigue de verdad con el
        # primero de sus hijos (no queda "por el camino").
        self.compuesto = False

    @property
    def visible(self):
        """Como en Minecraft: se ve cuando su padre ya está obtenido."""
        return self.padre is None or self.padre.obtenido

    def __repr__(self):
        return f"NodoLogro({self.clave}, {'sí' if self.obtenido else 'no'})"
