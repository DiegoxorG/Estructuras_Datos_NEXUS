# Estructuras de datos en NEXUS

Este documento explica cada estructura del curso que usa el juego: dónde está
en el código, de qué datos se arma, qué operaciones tiene y cuánto cuesta cada
una. Los números de nodos y hojas los sacamos corriendo las clases sobre los
datos de `data/` (no los contamos a mano), y los nombres de métodos son los
que están en el código hoy.

Notación que usamos en las complejidades:

- `n`: número de nodos del árbol; `h`: su altura (en nodos, como la calcula
  `altura()`); `k`: tamaño de un subárbol.
- `V` y `E`: nodos y aristas de un grafo; `d`: grado de salida de un nodo.
- `C`: celdas libres de la cuadrícula de navegación.

Todos los "O(1)" sobre diccionarios y conjuntos de Python son en promedio
(tablas hash).

---

## 1. Árbol binario de comportamiento de los aliens

### Dónde está

| Pieza | Archivo | Qué tiene |
|---|---|---|
| Clase del árbol | `Estructuras/arbol_comportamiento.py` | `ArbolComportamiento` |
| Nodo | `Estructuras/nodo_comportamiento.py` | `NodoComportamiento` (tipo `"pregunta"` con `condicion`, `si`, `no`; o tipo `"accion"` con `accion`) |
| Datos de los aliens de ruta | `data/comportamiento_alien.py` | `ARBOL_ALIEN` |
| Datos del Cambiaformas | `data/comportamiento_cambiaformas.py` | `ARBOL_CAMBIAFORMAS` |
| Datos del Guardia | `data/comportamiento_guardia.py` | `ARBOL_GUARDIA` |
| Datos de la Sombra | `data/comportamiento_sombra.py` | `ARBOL_SOMBRA` |
| Quién lo usa | `entidades/alien.py` (`Alien.actualizar`, `Alien.percibir`, `Alien._ejecutar`), `entidades/cambiaformas.py`, `entidades/guardia.py`, `entidades/sombra.py` | |
| Vista en vivo | `screens/arbol_alien.py` (Pausa > Opciones > Árbol del alien) | usa `por_niveles()` |

Es un árbol binario de decisión, no de búsqueda: no hay una clave que se
compare. Cada nodo interno es una pregunta de sí o no y cada hoja es una
acción. Lo que importa es el orden: las preguntas más urgentes van más cerca
de la raíz, así que la forma del árbol es la prioridad del alien.

### Cómo se construye

Los datos son diccionarios anidados. Una pregunta es
`{"pregunta": texto, "condicion": nombre, "si": {...}, "no": {...}}` y una hoja
es `{"accion": NOMBRE, "texto": texto}`. `ArbolComportamiento(datos)` llama a
`construir_desde_dict`, que baja recursivamente y cuelga `si` y `no` de cada
pregunta. Si a una pregunta le falta un hijo, lanza `ValueError`.

En la partida hay un árbol para los aliens de ruta y uno por cada alien
especial:

- `juego/app.py` arma `self.arbol_alien = ArbolComportamiento(ARBOL_ALIEN)`
  una vez y lo comparten todos los aliens de ruta (Vigía, Ciego y Cazador).
  Lo que cambia entre tipos no es el árbol sino lo que perciben
  (`data/tipos_alien.py`: el Ciego tiene `alcance_vision` 0 y `oido` 1.9).
- `Cambiaformas.__init__`, `Guardia.__init__` y `Sombra.__init__` arman el
  suyo con `ArbolComportamiento(ARBOL_CAMBIAFORMAS)`, etc., y se lo pasan a
  `Alien.__init__`.

Tamaños (contados con `contar()`, `hojas()` y `altura()`):

| Árbol | Nodos | Preguntas | Hojas (acciones) | Altura |
|---|---|---|---|---|
| `ARBOL_ALIEN` | 15 | 7 | 8 | 6 |
| `ARBOL_CAMBIAFORMAS` | 23 | 11 | 12 | 10 |
| `ARBOL_GUARDIA` | 15 | 7 | 8 | 8 |
| `ARBOL_SOMBRA` | 11 | 5 | 6 | 6 |

Las 8 acciones de `ARBOL_ALIEN` son DESCANSAR, ATRAPAR, PERSEGUIR,
REVISAR_ESCONDITE, INVESTIGAR, BUSCAR, VOLVER y PATRULLAR.

### Operaciones

| Método | Qué hace | Complejidad | Por qué |
|---|---|---|---|
| `construir_desde_dict(datos)` | arma el árbol desde el diccionario | O(n) | visita cada diccionario una vez |
| `decidir(condiciones)` | baja de la raíz a una hoja y devuelve `(accion, camino)` | O(h) | en cada pregunta mira una condición en el diccionario (O(1)) y baja un nivel |
| `insertar_pregunta(accion_hoja, ...)` | cambia una hoja por una pregunta con dos hojas | O(n) | `_buscar_padre_de_hoja` puede recorrer todo el árbol para encontrar la hoja |
| `por_niveles()` | BFS con `deque`: lista de `(nodo, nivel, padre)` | O(n) | cada nodo entra y sale de la cola una vez |
| `preorden()` | lista de `(nodo, nivel)` | O(n·h) | visita n nodos, pero cada nivel copia con `extend` la lista de sus hijos; con h ≤ 10 en la práctica es lineal |
| `hojas()`, `contar()`, `condiciones()` | se apoyan en `preorden()` | O(n·h) | lo mismo que `preorden` |
| `altura()` | recursiva | O(n) | cada nodo se visita una vez |

Lo que más se repite es `decidir`: lo llama `Alien.actualizar` en cada
cuadro por cada alien. Con 11 aliens de ruta en `MapaFinal` (5 Vigías, 3
Cazadores y 3 Ciegos) y altura 6, son a lo sumo 66 comparaciones por cuadro.
Lo caro de verdad es `percibir()` (mirar a cada jugador, la línea de vista y
los escondites), no el árbol.

### Ejemplo en una partida

La Biomante está metida en un casillero del Laboratorio con el pulso alto.
Un Cazador pasa por el pasillo de al lado. En ese cuadro `Alien.percibir()`
devuelve:

```
recuperandose=False, ve_jugador=False, jugador_al_alcance=False,
oye_ruido=True, en_escondite=False, rastro_reciente=False, fuera_de_ruta=False
```

`decidir` hace este camino: la raíz pregunta "¿Está fuera de combate?" (no,
baja por `no`); "¿Ve a un jugador?" (no, la Biomante está escondida); "¿Oyó
un latido?" (sí, baja por `si`); "¿Ya llegó al escondite de donde sale?"
(todavía no): la hoja es **INVESTIGAR**. Cuatro preguntas y una hoja, y ese
`camino` es lo que la vista del árbol pinta en amarillo. Unos cuadros
después, ya frente al casillero, `en_escondite` pasa a `True`, el mismo
recorrido termina en **REVISAR_ESCONDITE** y `Game` arranca el minijuego de
latidos (`entidades/minijuego_latidos.py`).

Con el Cambiaformas pasa algo parecido pero con más preguntas: si un jugador
lo rescata creyendo que es un prisionero, `lo_escoltan` es `True` y el
recorrido se corta en la tercera pregunta con **SEGUIR** ("Seguirlo y
traicionar"), sin llegar nunca a las ramas de caza. Con la Sombra, si una
linterna la apunta (`alumbrada`), la hoja es **CONGELARSE**; apenas le dan la
espalda vuelve a bajar hasta **ACECHAR**.

---

## 2. Árbol binario de habilidades por rol

### Dónde está

| Pieza | Archivo | Qué tiene |
|---|---|---|
| Clase | `Estructuras/arbol_habilidades.py` | `ArbolHabilidades`, función `construir_arbol(rol, datos)` |
| Nodo | `Estructuras/nodo_habilidad.py` | `NodoHabilidad` (`izquierdo`, `derecho`, `padre`, `desbloqueada`, `descartada`, `uso`, `recarga_s`) |
| Datos | `data/habilidades.py` | `TECNOMANTE`, `FORJADOR`, `BIOMANTE`, `RESONANTE` y `ARBOLES_POR_ROL` |
| Quién lo arma | `entidades/jugador.py` | `self.arbol = construir_arbol(rol, ARBOLES_POR_ROL.get(rol))` al escoger rol |
| Quién desbloquea | `juego/app.py` | `Game._confirmar_habilidad` llama `jugador.arbol.desbloquear(...)` |
| Quién pregunta | `entidades/acciones_rol.py` | `arbol.tiene("ESCANEO")`, etc. |
| Dibujo | `screens/panel_habilidades.py` | `por_niveles()` da la fila de cada nodo |

Cada jugador tiene su propio árbol. Es binario porque al subir se escoge una
de dos ramas y la otra se cierra para el resto de la ronda.

### Cómo se construye

`construir_desde_dict` llama a `_construir`, que recibe un diccionario con
`clave`, `nombre`, `descripcion`, `costo`, `uso`, `recarga_s` e `hijos` (una
lista de 0 o 2 diccionarios). El primero de la lista queda como `izquierdo`
y el segundo como `derecho`, y a cada hijo se le guarda el `padre`. Si alguien
pone tres hijos, lanza `ValueError`. La raíz queda desbloqueada desde el
principio y `actual` apunta a ella.

Hoy cada rol tiene 3 nodos (altura 2): la habilidad base gratis y dos hijas
que cuestan `COSTO_NIVEL_2 = 15` puntos del equipo.

| Rol | Raíz | Izquierda | Derecha |
|---|---|---|---|
| Tecnomante | CONEXION (estación) | HACKEO (estación) | ESCANEO (activa, 18 s) |
| Forjador | INGENIO (pasiva) | REPARACION (estación) | FABRICACION (activa) |
| Biomante | VINCULO (pasiva) | REGENERACION (activa) | IMPULSO (activa) |
| Resonante | SINTONIA (pasiva) | INTERCEPCION (activa) | EMISION (activa) |

La clase no está atada a esa profundidad: si `data/habilidades.py` cuelga
más niveles, `desbloquear` y el panel funcionan igual.

### Operaciones

| Método | Qué hace | Complejidad | Por qué |
|---|---|---|---|
| `construir_desde_dict(datos)` | arma el árbol | O(n) | un nodo por diccionario |
| `opciones()` | hijos de `actual` que no estén desbloqueados ni descartados | O(1) | un nodo tiene a lo sumo 2 hijos |
| `desbloquear(clave, puntos)` | valida que la clave esté en `opciones()`, cobra y descarta al hermano | O(k) | buscar es O(1); descartar recorre el subárbol del hermano (k nodos) |
| `_descartar(nodo)` | marca `descartada` en preorden | O(k) | visita cada nodo del subárbol una vez |
| `desbloqueadas()` | sube desde `actual` por `padre` hasta la raíz | O(h) | un paso por nivel |
| `tiene(clave)` | ¿la clave está en `desbloqueadas()`? | O(h) | recorre el camino desbloqueado |
| `por_niveles()` | BFS con `deque`: `(nodo, profundidad)` | O(n) | cada nodo entra a la cola una vez |
| `altura()` | recursiva | O(n) | visita todos los nodos |

`tiene` es O(h) y no O(1) porque lo desbloqueado siempre es un camino desde
la raíz: no hace falta guardar un conjunto aparte, basta subir por los padres.

### Ejemplo en una partida

El Tecnomante (jugador 1) abre la puerta de la prisión y el equipo junta 15
puntos. Presiona Q (la tecla de árbol del jugador 1) y `screens/panel_habilidades.py` dibuja el
árbol con `por_niveles()`: CONEXION en la fila 0, HACKEO y ESCANEO en la fila
1. `opciones()` devuelve `[HACKEO, ESCANEO]`. Escoge ESCANEO y confirma con E:
`Game._confirmar_habilidad` llama `desbloquear("ESCANEO", 15)`, que marca
ESCANEO, llama `_descartar(HACKEO)` y mueve `actual` a ESCANEO. El equipo
gasta 15 puntos con `equipo.gastar(costo)`. Desde ahí, cuando el Tecnomante
presiona F, `acciones_rol.py` pregunta `arbol.tiene("ESCANEO")` (sube
ESCANEO → CONEXION: dos pasos) y le muestra el mapa con los conos de los
aliens. HACKEO queda en gris en el panel el resto de la ronda.

---

## 3. Árbol N-ario de logros

### Dónde está

| Pieza | Archivo | Qué tiene |
|---|---|---|
| Clase | `Estructuras/arbol_logros.py` | `ArbolLogros` (raíz, `indice` clave → nodo) |
| Nodo | `Estructuras/nodo_logro.py` | `NodoLogro` (`hijos` como lista, `padre`, `obtenido`, `quien`, `por_camino`, `compuesto`, propiedad `visible`) |
| Datos | `data/logros.py` | `ARBOL_LOGROS`, armado con la función `L(...)` |
| Cuándo se consigue cada uno | `misiones/logros.py` | `GestorLogros` y la función `logro(juego, clave, jugador)` |
| Dibujo | `screens/logros.py` | `render_aviso_logro`, `render_arbol_logros` |
| Historial entre partidas | `juego/historial_logros.py` | `cargar()`, `agregar(claves)` sobre `Guardado/logros.json` |

Cada logro tiene un solo padre pero puede abrir cualquier cantidad de hijos,
así que es un árbol N-ario general. Además de los punteros, `ArbolLogros`
guarda un diccionario `indice` para llegar a un logro por su clave sin
recorrer el árbol.

### Cómo se construye

`ArbolLogros(ARBOL_LOGROS)` llama a `construir_desde_dict`, que crea el nodo,
lo mete en `indice` (si la clave ya estaba, lanza `ValueError("logro
repetido")`), hereda la `rama` del padre si el diccionario no trae una, y se
llama a sí mismo con cada hijo. `GestorLogros.__init__` arma uno nuevo en
cada partida, así que los logros arrancan de cero solos.

Contado con el script: **51 logros** en 6 niveles (1, 8, 27, 12, 1 y 2 nodos
por nivel) y 33 hojas. La raíz es `despertar` y tiene 8 hijos, uno por rama:
`sigiloso` (sigilo), `codigo_roto` (escape), `conectado` (nexus), `una_mano`
(equipo), `a_oscuras` (nave), `primer_encuentro` (aliens), `cara_a_cara`
(cambiaformas) y `algo_no_cuadra` (caso). `una_mano` y `primer_encuentro`
son "compuestos": se consiguen con el primero de sus hijos.

### Operaciones

| Método | Qué hace | Complejidad | Por qué |
|---|---|---|---|
| `construir_desde_dict(datos)` | arma el árbol y el índice | O(n) | un nodo y una inserción en el diccionario por logro |
| `insertar(clave_padre, ...)` | cuelga un logro nuevo | O(1) | busca al padre en `indice` y hace `append` |
| `buscar(clave)` | nodo por clave | O(1) | diccionario |
| `camino_a_la_raiz(nodo)` | `[nodo, padre, ..., raíz]` | O(h) | sube un nivel por paso |
| `falta_un_padre(clave)` | ¿algún antecesor no compuesto sin obtener? | O(h) | sube por los padres |
| `conseguir(clave, quien)` | marca el logro y los que falten hacia arriba | O(h) | sube hasta el primer antecesor ya obtenido |
| `reiniciar()` | deja todo sin obtener | O(n·h) | usa `preorden()` |
| `preorden()` | lista en preorden (para el cursor de la vista) | O(n·h) | igual que en el árbol de comportamiento, por las copias de `extend` |
| `por_niveles()` | `[[raíz], [hijos], ...]` con `deque` | O(n) | BFS |
| `posiciones()` | `{nodo: (columna, fila)}` en postorden | O(n) | cada hoja toma la siguiente fila y cada padre se centra entre su primer y último hijo |
| `total()` | cantidad de logros | O(1) | `len(indice)` |
| `obtenidos()` | cuántos van | O(n) | recorre el índice |

En `misiones/logros.py`, `GestorLogros.conseguir` primero busca el nodo
(O(1)) y pregunta `falta_un_padre` (O(h)). Si el padre todavía no llega, no
lo da enseguida: lo deja en la lista `pendientes` con `ESPERA_PADRE_MS =
2500` ms y `_pendientes(dt)` lo revisa en cada cuadro. Los avisos que salen
abajo al centro también son una lista que se usa como cola (`avisos`): se
muestra el primero y, si hay varios esperando, duran menos
(`DURACION_AVISO_EN_COLA_MS`).

### Ejemplo en una partida

El equipo termina el tutorial y `GestorLogros.actualizar` llama
`conseguir("despertar")`: es la raíz, `conseguir` la marca y sale un aviso.
Más tarde llevan la última pieza a la cápsula y `_mision` llama
`conseguir("chatarrero")`. `falta_un_padre("chatarrero")` sube por
`sin_rumbo` → `codigo_roto` → `despertar`; los tres ya están obtenidos, así
que se da enseguida. Cuando escapan, `al_terminar` pide `libertad`, cuyo
camino a la raíz es `libertad → chatarrero → sin_rumbo → codigo_roto →
despertar` (5 nodos), así que `conseguir` revisa a lo sumo 5. Al terminar
la ronda, `historial_logros.agregar(...)` suma las claves conseguidas a
`Guardado/logros.json` y el menú principal > Logros pinta el árbol completo
con lo que se ha conseguido alguna vez en ese computador. En las pruebas
(`SDL_VIDEODRIVER=dummy`) `agregar` no escribe, para no llenar el historial
con partidas de mentira.

---

## 4. Grafo (`Estructuras/grafo.py`)

`Grafo` es un grafo dirigido y sin pesos guardado como lista de adyacencia:
`self.ady` es un diccionario `nodo -> set(nodos a los que les llega lo que
publica)` y `self.datos` guarda lo que se quiera de cada nodo (nombre,
usuario, color, tipo). Escogimos lista de adyacencia porque la red es
dispersa: cada cuenta tiene unas pocas conexiones, no todas con todas.

### Operaciones

| Método | Qué hace | Complejidad | Por qué |
|---|---|---|---|
| `agregar_nodo(nodo, **datos)` | crea el nodo (o actualiza sus datos) | O(1) | inserción en diccionario |
| `agregar_arista(desde, hasta)` | `desde` → `hasta` | O(1) | inserción en un `set` |
| `eliminar_nodo(nodo)` | borra el nodo y todas sus aristas | O(V) | hay que quitarlo del conjunto de cada nodo (`discard` es O(1)) |
| `vecinos(nodo)` | a quién le llega lo que publica | O(1) | devuelve el conjunto |
| `seguidos_por(nodo)` | de quién le llega algo | O(V) | revisa el conjunto de todos |
| `grado_salida(nodo)` | | O(1) | `len` del conjunto |
| `aristas()` | total de aristas | O(V) | suma los tamaños |
| `expandir(frontera, visitados, puede_pasar)` | un paso del BFS: el siguiente nivel | O(Σ d·log d) sobre la frontera | revisa los vecinos de cada nodo de la frontera; los ordena con `sorted(..., key=str)` para que el orden sea siempre el mismo |
| `bfs_niveles(origen, puede_pasar, max_niveles)` | `[[origen], [seguidores], ...]` | O(V + E·log d) | cada nodo entra una vez a `visitados`; el log es por el `sorted` |
| `camino_mas_corto(origen, destino)` | BFS guardando el padre de cada nodo | O(V + E·log d) | en un grafo sin pesos el primer BFS que llega da el camino con menos saltos |
| `componentes()` | grupos conectados sin mirar la dirección | O(V + E) | arma la versión sin dirección y hace un BFS por grupo |

### 4.1 La red NEXUS (`redes/nexus.py`)

**Cómo se arma.** `RedNexus.__init__` llama a `_armar_red`, con los datos de
`data/nexus.py`:

- 14 prisioneros (`CUENTAS`, nodos `preso_0` a `preso_13`, en gris). Cada uno
  publica a `SEGUIDORES_PRISIONERO = 2` prisioneros al azar.
- Un nodo por jugador (`jugador_<puesto>`, en verde). Lo que publica le llega
  a 3 prisioneros (`SEGUIDORES_JUGADOR`) y 4 prisioneros le publican a él
  (`SIGUE_CADA_JUGADOR`).
- Los bots del Cambiaformas (`BOTS`, 5 cuentas como `@p47_libre` o
  `@infonave247`, en rojo). Empiezan 3 (`BOTS_AL_EMPEZAR`); `_nuevo_bot` le da
  a cada uno 3 seguidores y hace que 2 prisioneros lo sigan para que parezca
  real. Si reportan uno, después de `NUEVO_BOT_CADA_S` sale otro, hasta
  gastar los 5.

Con 4 jugadores la red arranca con 14 + 4 + 3 = 21 nodos.

**Rumores por BFS por niveles.** Una publicación que avanza es un objeto
`Propagacion` con su `frontera` y su conjunto `visitados`. En
`RedNexus.actualizar`, cada `TICK_PROPAGACION_MS = 1300` ms `_avanzar(prop)`
llama una vez a `grafo.expandir(frontera, visitados, puede_pasar)`. O sea,
no se hace el BFS completo de una: se hace un nivel por tick, y por eso en el
celular el rumor llega primero a unos y después a otros. `puede_pasar`
cambia según el color: un rumor (ROJO) solo lo reenvían los rojos (el bot y
los que se lo creyeron); un desmentido (VERDE) solo los verdes que no son
bots, y hasta `NIVELES_DESMENTIDO = 6` saltos. A cada prisionero gris que le
llega un rumor se lo cree con probabilidad `prob_creer` de la dificultad
(0.30 en Fácil, 0.45 en Pesadilla) y se pone rojo. Los verdes no lo reenvían:
la confianza hace de cortafuegos.

**"¿De dónde salió esto?".** `RedNexus.rastrear(jugador, pub)` llama
`grafo.camino_mas_corto(pub.autor, nodo_del_jugador)`. Si el bot ya fue
borrado y no hay camino, reconstruye el recorrido con el diccionario
`pub.via` (nodo → de quién le llegó), que `_avanzar` fue llenando. El
resultado queda en `ultimo_rastreo` para que la vista del grafo lo pinte en
amarillo.

**Reportar borra el nodo.** `RedNexus.reportar(jugador, nodo)`: si es bot,
lo anota en `borrados` y llama `grafo.eliminar_nodo(nodo)` (O(V)). Desde el
siguiente tick, los rumores que pasaban por ese bot ya no tienen por dónde
seguir, porque `_avanzar` filtra la frontera con `n in g`. Si es un
prisionero que solo se creyó el rumor, no se borra nada y se pone rojo.

**% de confianza.** `RedNexus.barras()` cuenta los prisioneros verdes y rojos
y los divide por el total de prisioneros (O(V)). La barra verde y la roja de
arriba al centro son exactamente esos dos números. `_revisar_umbrales`
compara la verde con `umbral_planos` (60% en Fácil, 70% en Normal e
Inteligente, 75% en Difícil, de `data/dificultad.py`) y, al pasarlo, llama
`desbloquear_planos`. `potencia_aliens()` usa la diferencia rojo − verde
para hacer a los aliens más rápidos.

**Ejemplo.** `@infonave247` publica "la cápsula de escape explotó". Tick 1:
`expandir` lleva el rumor a sus 3 seguidores; dos estaban grises y uno se lo
cree (se pone rojo). Tick 2: solo el rojo reenvía, y de sus 2 seguidores uno
es `jugador_1` (el nodo del jugador 2, que aquí es el Forjador; los nodos
van por `puesto`, que empieza en 0), al que le aparece en la pestaña
Misiones. El Forjador va a la Bahía, la foto sale sola, y desde el celular toca "¿De dónde salió esto?":
`camino_mas_corto` devuelve `bot_2 → preso_7 → jugador_1`. Reporta a
`bot_2`: `eliminar_nodo` lo borra, en la vista del grafo queda una X un rato,
y después desmiente con la foto recortada, que arranca una `Propagacion`
verde desde su nodo.

**Vista en vivo.** `screens/grafo_vista.py` (`render_grafo_nexus`, Pausa >
Opciones > Grafo) dibuja los nodos con una disposición por fuerzas, hace
parpadear el último nivel que recibió la publicación, pinta el último
rastreo y los bots borrados, y muestra nodos, aristas y
`len(grafo.componentes())`.

### 4.2 El grafo de salas (`juego/salas_selladas.py`)

`grafo_de_salas(salas)` usa el mismo `Grafo`: cada rectángulo de sala es un
nodo y los que se tocan tienen arista en los dos sentidos (O(S²) para S
rectángulos, porque compara cada par con `itertools.combinations`).
`_alcanzables` hace `bfs_niveles` desde Control pasando solo por salas
abiertas, para no sellar una sala que deje el mapa partido. Hoy este modo
está apagado (`ACTIVO = False`), pero el código y su prueba
(`pruebas/prueba_salas_selladas.py`) siguen.

### 4.3 La navegación de los aliens por la nave (`juego/navegacion.py`)

Aquí el grafo no usa la clase `Grafo`: es un grafo implícito sobre una
cuadrícula del mapa.

**Cómo se arma.** `Navegacion.__init__` recorre el mapa en pasos de `PASO =
16` px y guarda en el conjunto `self.libre` cada celda donde cabe el alien
sin chocar con `mundo.paredes_base` (O(C·P), con P paredes, porque cada
celda prueba `collidelist`). Se arma una vez por mapa y por tamaño de hitbox
(`de_mundo(mundo, ancho, alto)` lo guarda en un diccionario dentro del
mundo). `_vecinos()` arma, también una vez, la lista de adyacencia: para cada
celda, sus vecinas libres en 8 direcciones con costo 1 o 1.4142, sin cortar
esquinas (O(C)).

Lo que cambia en la partida (la puerta del código, las puertas para dos,
los sellos del Forjador) no está en la cuadrícula fija: `_estado()` calcula
qué celdas tapa y guarda una máscara de pygame por cada combinación de
puertas cerradas (hasta 8).

**Operaciones.**

| Método | Qué hace | Complejidad | Por qué |
|---|---|---|---|
| `conectados(a, b)` | ¿se puede ir de a a b con lo que está cerrado ahora? | O(1) si las zonas ya están calculadas; O(C) la primera vez para ese estado | compara el número de zona (componente conexa) de las dos celdas; la zona sale de `Mask.connected_component` |
| `camino(desde, hasta, parcial, ...)` | lista de puntos para llegar | O(C log C) en el peor caso | A* con montículo (`heapq`) sobre la cuadrícula, con tope de `MAX_NODOS = 40000` celdas |
| `distancia_camino(desde, hasta, max_px)` | largo del camino más corto, o None si pasa de `max_px` | O(C' log C'), C' = celdas dentro del tope | A* que no encola nada cuyo costo estimado pase el tope |
| `estirar(puntos)` | quita puntos intermedios a los que ya se llega en línea recta | O(k²) en el peor caso, k = puntos del camino | prueba `libre_entre` hacia adelante desde cada punto |
| `_componentes()` | BFS con `deque` (4 direcciones) para numerar las zonas | O(C) | solo lo usa la vista del grafo de la nave |

Antes de buscar, `_busqueda` mira si inicio y meta están en la misma zona.
Si no lo están y `parcial=True`, cambia la meta por la celda de su zona más
cercana al destino (`_mas_cercana_en_zona`), y el alien llega hasta la puerta
en vez de quedarse quieto. La búsqueda es un generador: con `por_partes` se
reparte en varios cuadros (`PRESUPUESTO_ALIEN = 4000` celdas o
`LIMITE_MS_CUADRO = 3` ms por cuadro), para que un camino largo no congele
la imagen. Los caminos ya calculados se guardan en `_guardados`.

Un detalle importante: la búsqueda de caminos ya no es un BFS puro. Es un
A* con la heurística multiplicada por `PESO_ESTIMADO = 1.6`, lo que la hace
revisar muchas menos celdas a cambio de que el camino pueda salir un poco
más largo que el óptimo (después `estirar` lo endereza). El BFS por niveles
sí se usa para las zonas (`_componentes`) y en el grafo de salas. Lo
anotamos en las contradicciones del PR porque varios comentarios y el README
todavía dicen "BFS".

**Ejemplo.** Un Vigía persigue al Resonante, que dobla hacia Motores y
queda detrás de una pared. Mientras lo veía, `percibir()` iba guardando en
`punto_ruido` su última posición; ahora `ve_jugador` es `False` pero
`oye_ruido` sigue en `True`, y el árbol baja hasta INVESTIGAR.
`Alien._ir_por_camino` pregunta `libre_entre`: hay pared, así que pide
`nav.camino(self.centro, punto, parcial=True, por_partes=PRESUPUESTO_ALIEN,
quien=id(self))`. Si el camino es largo, en el primer cuadro el A* gasta su
presupuesto y devuelve `None` con `ocupada=True` (mientras tanto el alien va
directo); en el siguiente termina, `estirar` deja unas pocas esquinas y el
alien las sigue con `ruta_ruido`. Al llegar al punto, INVESTIGAR borra
`punto_ruido`, `busqueda_ms` todavía corre y el árbol baja a BUSCAR: se queda
mirando a los lados. Si no encuentra nada, `fuera_de_ruta` es `True` y la
hoja es VOLVER (la pila del rastro, abajo). En Pausa > Opciones > Grafo >
Nave (`render_grafo_nave`) se ven las celdas que revisó esa búsqueda
(`Navegacion.ultima_busqueda`) y el camino.

---

## 5. Otras estructuras que aparecen

- **Pila del rastro del alien** (`entidades/alien.py`, `self.rastro`): cuando
  un alien sale de su ruta va dejando un punto cada `SEPARACION_RASTRO = 36`
  px (`_dejar_rastro`, `append`). Para volver, la acción VOLVER va hacia
  `self.rastro[-1]` y hace `pop()` al llegar: deshace su camino exacto, el
  último punto en entrar es el primero en salir. `push` y `pop` son O(1). La
  condición `fuera_de_ruta` del árbol es simplemente `bool(self.rastro)`.
- **Colas (`collections.deque`)**: en todos los BFS (`por_niveles` de los tres
  árboles, `camino_mas_corto`, `componentes`, `Navegacion._componentes`).
  `popleft` es O(1); con una lista normal `pop(0)` sería O(n).
- **Montículo (`heapq`)**: la lista de abiertos del A* de `juego/navegacion.py`.
  `heappush` y `heappop` son O(log n).
- **Diccionarios como índice**: `ArbolLogros.indice` (clave → nodo),
  `Grafo.ady` y `Grafo.datos`, `Publicacion.via` (nodo → de quién le llegó el
  rumor), `RedNexus.evidencias` (jugador → fotos), `Navegacion._guardados`
  (caché de caminos) y la caché de navegaciones por tamaño en `de_mundo`.
- **Conjuntos**: `Navegacion.libre`, los `visitados` de cada `Propagacion`,
  `GestorLogros.tipos_vistos`. Preguntar `in` es O(1).
- **Listas usadas como cola de espera**: `GestorLogros.avisos` y
  `GestorLogros.pendientes` (logros que esperan a su padre).
