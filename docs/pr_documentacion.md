# Documentación técnica para la entrega final

Este PR solo agrega documentación en `docs/` y un enlace a ella en el README.
No cambia código, datos, mapas ni assets.

## Qué documentos hay

- `docs/estructuras.md`: cada estructura del curso que usa el juego.
  - Árbol binario de comportamiento (`ArbolComportamiento`) con sus cuatro
    árboles de datos: aliens de ruta, Cambiaformas, Guardia y Sombra.
  - Árbol binario de habilidades por rol (`ArbolHabilidades`).
  - Árbol N-ario de logros (`ArbolLogros`) con su índice clave → nodo, el
    gestor que decide cuándo se consigue cada uno y el historial en disco.
  - El `Grafo` y sus tres usos: la red NEXUS (BFS por niveles un tick a la
    vez, camino más corto, borrar nodos al reportar, % de confianza), el
    grafo de salas y la navegación de los aliens sobre la cuadrícula.
  - Otras estructuras: la pila del rastro del alien, las colas `deque`, el
    montículo del A*, los diccionarios usados como índice y los conjuntos.

  Para cada una: dónde está (archivo, clase, método), de qué datos se arma,
  sus operaciones con la complejidad en notación O y una línea de por qué, y
  un ejemplo de una partida.
- `docs/arquitectura.md`: diagrama Mermaid de los módulos y cómo se comunican,
  diagrama del flujo de pantallas, diagrama de secuencia del bucle de un
  cuadro (eventos → actualizar → dibujar) con el orden real de
  `_actualizar_partida`, y diagrama del modo en red. Aclara que el modo en red
  vive en la rama `claude/cliente-servidor` (su propio PR) y no en `main`.
- `docs/guia_rapida.md`: requisitos (Python 3, pygame o pygame-ce), cómo
  correr el juego, las teclas globales (F3, F9, F11, ESC), cómo correr todas
  las pruebas con `SDL_VIDEODRIVER=dummy` y `SDL_AUDIODRIVER=dummy`, el
  simulador con sus argumentos y qué hace cada editor de `Editores/`.
- `README.md`: una línea en "Estructura del repositorio" con el enlace a los
  tres documentos.

## Qué se verificó y cómo

- **Nombres**: cada clase, método, constante y archivo que se nombra en los
  documentos se buscó en el código de `main` (con grep y leyendo los
  archivos). Los del modo en red se leyeron de la rama
  `claude/cliente-servidor` con `git show claude/cliente-servidor:<archivo>`
  (`docs/cliente_servidor.md`, `cliente_servidor/servidor.py`,
  `cliente_servidor/cliente.py`, `cliente_servidor/protocolo.py`).
- **Tamaños de los árboles**: no los contamos a mano. Un script construyó cada
  árbol con las clases del juego sobre los datos de `data/` y usó `contar()`,
  `hojas()`, `altura()`, `condiciones()`, `por_niveles()` y `total()`:

  | Árbol | Nodos | Hojas | Altura |
  |---|---|---|---|
  | `ARBOL_ALIEN` | 15 | 8 | 6 |
  | `ARBOL_CAMBIAFORMAS` | 23 | 12 | 10 |
  | `ARBOL_GUARDIA` | 15 | 8 | 8 |
  | `ARBOL_SOMBRA` | 11 | 6 | 6 |
  | Habilidades (cada rol) | 3 | 2 | 2 |
  | `ARBOL_LOGROS` | 51 | 33 | 6 niveles (1, 8, 27, 12, 1, 2) |

- **Complejidades**: se sacaron leyendo cada método (no de los comentarios).
  Donde el código cuesta más de lo que parece lo dijimos: `preorden()` es
  O(n·h) por las copias de `extend`, `expandir` y `camino_mas_corto` tienen un
  log por el `sorted` de los vecinos, `eliminar_nodo` es O(V).
- **Números de NEXUS y del mapa**: 14 prisioneros y 5 bots salen de
  `data/nexus.py`; las 11 rutas de alien (5 Vigías, 3 Cazadores, 3 Ciegos) y
  las 10 salas, de `Hitboxes/MapaFinal_objetos.json`; el mapa activo, de
  `Hitboxes/mapa_activo.json`.
- **Ejemplos**: cada ejemplo de partida se siguió en el código (qué devuelve
  `percibir()`, qué hojas salen, qué llama a qué). Uno lo corregimos al
  revisarlo: al perder de vista a un jugador el alien no pasa por BUSCAR
  antes de INVESTIGAR, sino al revés.
- **Mermaid**: los cuatro diagramas de `arquitectura.md` se pasaron por
  `mermaid.parse` (mermaid 11.4.1 con jsdom, instalado aparte en una carpeta
  temporal, fuera del repo). Los cuatro dan OK; se probó también que el
  validador sí rechaza un diagrama roto.
- **Pruebas**: con `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy` se corrieron
  los 33 `pruebas/prueba_*.py` antes de empezar y antes del último commit. Las
  33 pasan las dos veces (ningún `FALLA`).
- **README**: la guía rápida se revisó contra el README para no
  contradecirlo. Lo que el README dice y el código no hace está abajo.

## Contradicciones encontradas

No cambiamos nada de esto (el PR es solo de documentación). Los documentos
nuevos describen lo que hace el código, no lo que dicen los comentarios.

1. **La navegación ya no es BFS, es A\* ponderado.**
   `juego/navegacion.py:8` dice "busca un camino con **BFS**", y lo repiten
   `entidades/alien.py:538` ("sigue un camino buscado con BFS"),
   `juego/navegacion.py:28` ("tope del BFS") y `README.md:26` ("Grafo de la
   nave (BFS)"). El código de `Navegacion._busqueda` (`juego/navegacion.py:346`
   en adelante) es un A* con `heapq` y la heurística multiplicada por
   `PESO_ESTIMADO = 1.6`. El mismo archivo lo reconoce en
   `juego/navegacion.py:277-278`, pero ahí dice que "encuentra el mismo tipo
   de camino que el BFS de antes": con peso 1.6 la heurística deja de ser
   admisible y el camino puede salir más largo que el más corto. El BFS
   sigue en `_componentes` (solo para la vista) y en el grafo de salas.
2. **Las habilidades no son gratis.** `Estructuras/arbol_habilidades.py:164-166`
   dice "Con costo 0 esto nunca se cumple: hoy las habilidades son gratis",
   pero `data/habilidades.py:24` tiene `COSTO_NIVEL_2 = 15` y todas las hijas
   lo usan, y `Game._confirmar_habilidad` cobra con `equipo.gastar(costo)`.
3. **El umbral de los planos no es 80%.** `README.md:112` dice "Con la verde
   en 80% (la raya blanca) les pasan los planos". `data/nexus.py:124` tiene
   `UMBRAL_PLANOS = 0.80`, pero `juego/app.py:690` lo reemplaza con el de la
   dificultad (`data/dificultad.py:75`: 60% Fácil, 70% Normal, 75% Difícil,
   70% Inteligente). El mismo README, en la tabla de dificultad, ya dice
   60/70/75/70.
4. **"La nave es el único mapa".** `README.md:366` lo dice, pero en
   `Hitboxes/` hay tres mapas (`Nave`, `MapaE2` y `MapaFinal`) y
   `Hitboxes/mapa_activo.json` dice `MapaFinal`. El README mismo habla de
   `MapaFinal` y `MapaE2` en "La misión".
5. **Comentarios de `app.py` de cuando eran dos jugadores con teclado.**
   `juego/app.py:19-20` dice que cada jugador juega "en su mitad de la
   pantalla" y que "los dos comparten teclado"; se juega de 2 a 4
   (`data/roles.py:48-49`, `MINIMO_JUGADORES = 2`, `MAXIMO_JUGADORES = 4`) y
   con mandos.
6. **Los mandos sí están hechos.** `juego/app.py:117-119` dice que los puestos
   3 y 4 van sin controles "porque les toca mando y eso todavía no está
   hecho". Justo debajo, `_controles_mando` les da teclas virtuales, y
   `juego/mandos.py` implementa los mandos.
7. **Duración de la ronda.** `juego/app.py:105` tiene `DURACION_RONDA_S = 300`
   con el comentario "cinco minutos, como pide el diseño", y
   `juego/app.py:18` dice "La ronda dura unos minutos". Con misión no hay
   límite: `juego/app.py:682` pone `tiempo_restante_ms = None`, como dice el
   README ("No hay limite de tiempo"). Los 300 s solo cuentan en un mapa sin
   misión.
8. **El tutorial no es de 30 s.** `juego/app.py:107` dice "Tutorial de 30 s al
   empezar"; `juego/tutorial.py:1` dice "sin tiempo: cada quien va a su
   ritmo", igual que `README.md:266`.
9. **La presentación de aliens no es solo en Fácil.** `juego/app.py:1111` dice
   "Fácil: la ventana que presenta a un alien nuevo pausa todo", pero
   `data/dificultad.py:85` (`PRESENTAR_ALIENS`) la activa en las cuatro
   dificultades, como dice `README.md:209`.
10. **"El árbol es el mismo para todos los aliens".** `entidades/alien.py:11`
    lo dice, pero el Cambiaformas, el Guardia y la Sombra tienen su propio
    árbol (`entidades/cambiaformas.py:71`, `entidades/guardia.py:46`,
    `entidades/sombra.py:48`). Es cierto solo para los aliens de ruta
    (Vigía, Ciego y Cazador).
11. **El simulador sin `--dificultad` no juega "como Difícil".**
    `pruebas/simulador.py:55` dice "(sin eso: como Difícil)". Sin la opción,
    `g.dificultad` queda en `None` (`juego/app.py:239`) y
    `dificultad.valor(...)` devuelve el valor por defecto de cada llamada, que
    según `juego/dificultad.py:4-6` son los números base del juego
    (Pesadilla), no los de Difícil.

### Otras observaciones (no son contradicciones exactas)

- `pruebas/simulador.py:34` fija el mapa con
  `objetos_mapa.mapa_activo = lambda: "Nave"`, así que los números de
  balance del simulador son del mapa viejo y no de `MapaFinal`, que es el que
  carga el juego.
- La frase de `Estructuras/arbol_logros.py:29-33` sobre los padres
  "compuestos" está cortada y cuesta entenderla. Lo que hace el código es:
  `conseguir` sube por los padres marcando los que falten con
  `por_camino = True`, salvo los compuestos, que quedan como conseguidos de
  verdad; y `GestorLogros.conseguir` (`misiones/logros.py:67-76`) espera hasta
  `ESPERA_PADRE_MS` a que llegue el padre antes de dar el hijo.

## Cómo revisarlo

```bash
git diff main --stat          # solo docs/ y una línea del README
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
for f in pruebas/prueba_*.py; do python "$f" >/dev/null 2>&1 || echo FALLA $f; done
```

Los diagramas se ven en la vista de GitHub de `docs/arquitectura.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01Kyk2UbVPtUpGTo4hWXh4at
