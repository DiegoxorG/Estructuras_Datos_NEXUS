"""Árbol N-ario de logros, como los "avances" de Minecraft.

Las cinco preguntas que plantea el laboratorio:

1) ¿Qué problema resuelve?
   Llevar la cuenta de los logros de una partida y mostrar cómo se derivan
   unos de otros: "Libertad" (escapar) sale de "Chatarrero" (llevar las
   piezas), que sale de "Sin rumbo" (apagar las consolas)... Cada logro abre
   los siguientes, y los que todavía no se abren se ven como "?".

2) ¿Por qué esta estructura?
   Porque la relación "este logro se deriva de aquel" es de padre a hijo, y
   cada logro tiene un solo padre pero puede abrir varios: eso es un árbol
   N-ario. En una lista no hay forma de decir de dónde viene cada logro ni de
   dibujar las ramas (sigilo, escape, NEXUS, equipo, nave, aliens).

3) ¿Qué variante se utiliza?
   Un árbol N-ario general (no binario, no de búsqueda): cada nodo guarda una
   lista de hijos de cualquier tamaño y un puntero a su padre. La forma la
   fija el diseño (data/logros.py), no un orden entre claves. Aparte se guarda
   un diccionario clave -> nodo, como índice, para encontrar un logro en O(1)
   cuando el juego avisa que pasó algo.

4) ¿Cómo se insertan y eliminan elementos?
   Se construye una vez, recursivamente, desde el diccionario anidado de
   data/logros.py (`construir_desde_dict`); `insertar(clave_padre, ...)`
   cuelga un logro nuevo de cualquier nodo. No se eliminan nodos: lo que
   cambia es su estado. Al conseguir un logro se **sube por los padres hasta
   la raíz** (`camino_a_la_raiz`) marcando los que falten, para que el árbol
   nunca tenga un hijo obtenido con el padre sin obtener (salvo un padre
   "compuesto", que dice "cualquiera de los de abajo", quedan marcados "por el
   camino"). Cada partida empieza con un árbol nuevo (`reiniciar`). El orden
   de data/logros.py está pensado para que eso casi nunca pase.

5) ¿Cómo se realiza su recorrido?
   - **Por niveles (BFS con una cola)** para contar y listar por profundidad.
   - **Preorden (DFS)** para ordenar los nodos de arriba a abajo en la vista y
     moverse con el cursor.
   - **Postorden** para dibujarlo: cada hoja toma la siguiente fila y cada
     padre se centra entre su primer y su último hijo, que ya están puestos
     (`posiciones`). Así sale el dibujo de izquierda a derecha como el de
     Minecraft, con la raíz a la izquierda.
"""

from collections import deque

from Estructuras.nodo_logro import NodoLogro


class ArbolLogros:
    def __init__(self, datos=None):
        self.raiz = None
        self.indice = {}          # clave -> nodo
        if datos:
            self.raiz = self.construir_desde_dict(datos)

    # -- Construcción ---------------------------------------------------------------

    def construir_desde_dict(self, datos, padre=None, rama=""):
        rama = datos.get("rama", rama)
        nodo = NodoLogro(datos["clave"], datos["nombre"], datos["descripcion"], rama, padre)
        nodo.compuesto = bool(datos.get("compuesto", False))
        if nodo.clave in self.indice:
            raise ValueError(f"logro repetido: {nodo.clave}")
        self.indice[nodo.clave] = nodo
        for hijo in datos.get("hijos", []):
            nodo.hijos.append(self.construir_desde_dict(hijo, nodo, rama))
        return nodo

    def insertar(self, clave_padre, clave, nombre, descripcion):
        padre = self.indice[clave_padre]
        nodo = NodoLogro(clave, nombre, descripcion, padre.rama, padre)
        padre.hijos.append(nodo)
        self.indice[clave] = nodo
        return nodo

    def reiniciar(self):
        for nodo in self.preorden():
            nodo.obtenido, nodo.quien, nodo.por_camino = False, None, False

    # -- Conseguir un logro ------------------------------------------------------------

    def buscar(self, clave):
        return self.indice.get(clave)

    def falta_un_padre(self, clave):
        """¿Le falta algún antecesor (que no sea compuesto) para conseguirlo
        "en orden"?"""
        nodo = self.buscar(clave)
        padre = nodo.padre if nodo is not None else None
        while padre is not None:
            if not padre.obtenido and not padre.compuesto:
                return True
            padre = padre.padre
        return False

    def camino_a_la_raiz(self, nodo):
        """[nodo, padre, abuelo, ..., raíz]"""
        camino = []
        while nodo is not None:
            camino.append(nodo)
            nodo = nodo.padre
        return camino

    def conseguir(self, clave, quien=None):
        """Marca el logro y los que le falten hacia la raíz. Devuelve la lista
        de nodos recién obtenidos, de la raíz hacia abajo (vacía si ya lo tenía)."""
        nodo = self.buscar(clave)
        if nodo is None or nodo.obtenido:
            return []
        nuevos = []
        for i, n in enumerate(self.camino_a_la_raiz(nodo)):
            if n.obtenido:
                break
            n.obtenido, n.quien, n.por_camino = True, quien, i > 0 and not n.compuesto
            nuevos.append(n)
        return list(reversed(nuevos))

    # -- Recorridos -----------------------------------------------------------------------

    def preorden(self, nodo=None):
        nodo = nodo or self.raiz
        if nodo is None:
            return []
        lista = [nodo]
        for hijo in nodo.hijos:
            lista.extend(self.preorden(hijo))
        return lista

    def por_niveles(self):
        """Lista de niveles: [[raíz], [hijos de la raíz], [nietos], ...] (BFS)."""
        if self.raiz is None:
            return []
        niveles, cola = [], deque([(self.raiz, 0)])
        while cola:
            nodo, nivel = cola.popleft()
            if nivel == len(niveles):
                niveles.append([])
            niveles[nivel].append(nodo)
            for hijo in nodo.hijos:
                cola.append((hijo, nivel + 1))
        return niveles

    def posiciones(self):
        """{nodo: (columna, fila)} para dibujarlo de izquierda a derecha.

        Postorden: primero se ubican los hijos; cada hoja toma la siguiente
        fila libre y cada padre queda a la altura del medio de sus hijos.
        La columna es la profundidad.
        """
        pos, siguiente = {}, [0]

        def ubicar(nodo, profundidad):
            for hijo in nodo.hijos:
                ubicar(hijo, profundidad + 1)
            if nodo.hijos:
                fila = (pos[nodo.hijos[0]][1] + pos[nodo.hijos[-1]][1]) / 2
            else:
                fila = siguiente[0]
                siguiente[0] += 1
            pos[nodo] = (profundidad, fila)

        if self.raiz is not None:
            ubicar(self.raiz, 0)
        return pos

    def total(self):
        return len(self.indice)

    def obtenidos(self):
        return sum(1 for n in self.indice.values() if n.obtenido)
