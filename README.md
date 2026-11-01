# NEXUS

*En el vacío, nada está realmente solo.*

Videojuego educativo en Python/Pygame sobre el uso responsable de las redes
sociales. Proyecto de laboratorio de **Estructura de Datos II**, Universidad
del Norte.

Cuatro personas fueron secuestradas por una nave alienígena y despiertan en
una prisión. Para escapar tienen que trabajar juntas: encontrar el código de
la puerta, apagar las consolas de navegación, reparar una cápsula y llegar a
ella sin que los aliens las atrapen. No hay armas: solo sigilo, las
habilidades de cada rol (Tecnomante, Forjador, Biomante y Resonante) y la
**NEXUS**, la red social de la nave, donde uno de los que escriben es un
alien disfrazado de prisionero. Se juega de 2 a 4 personas en la misma
pantalla, partida en una vista por jugador.

## Estructuras de datos

| Estructura | Donde | Para que |
|---|---|---|
| Arbol binario de comportamiento | `Estructuras/arbol_comportamiento.py` | La "IA" de cada alien: cada frame baja de la raiz a una hoja respondiendo preguntas (¿ve a alguien?, ¿oye un ruido?) y la hoja dice que hace. Se ve en vivo en Pausa > Opciones > Arbol del alien. |
| Arbol binario de habilidades | `Estructuras/arbol_habilidades.py` | Progresion de cada rol durante la ronda. Al subir se escoge **una de dos** ramas y la otra se cierra, asi que lo desbloqueado cambia las opciones que el jugador ve. Recorrido por niveles (BFS) para dibujarlo y preorden para descartar la rama perdida. |
| Arbol N-ario de logros | `Estructuras/arbol_logros.py` | Los logros de la partida, como los de Minecraft: cada uno abre otros. Indice clave -> nodo, subir por los padres hasta la raiz al conseguir uno, BFS por niveles, preorden para moverse por la vista y postorden para ubicar cada nodo al dibujarlo. Pausa > Logros. |
| Arbol de comportamiento del Cambiaformas | `data/comportamiento_cambiaformas.py`, `cambiaformas.py` | Otro arbol binario de decision con la misma clase: ¿fuera de combate? ¿huyendo? ¿lo llevan creyendo que es un prisionero? ¿ya se revelo? ¿la presa se escondio? ¿esta cerca y sola? ¿tiene presa? ¿hay un rumor de carnada? -> seguir (y traicionar), acechar, revelarse, perseguir, revisar escondite, huir... |
| Grafo de la nave (BFS) | `navegacion.py` | Los aliens buscan camino por una cuadricula del mapa (cada celda es un nodo) para llegar a un ruido rodeando paredes. |
| Grafo dirigido de NEXUS | `Estructuras/grafo.py`, `nexus.py` | La red social del celular. Cada cuenta es un nodo y "lo que publica A le llega a B" es una arista (lista de adyacencia). Los rumores y los desmentidos se propagan con **BFS por niveles** (un nivel por tick); "¿de donde salio esto?" es el **camino mas corto** desde el bot que lo empezo; reportar un bot es **borrar su nodo**; las barras de confianza son el % de nodos verdes y rojos. |

## Como correrlo

Requiere Python 3 y Pygame (`pip install pygame`).

```bash
python main.py                        # el juego
python pruebas/prueba_partida.py      # una ronda completa sin abrir ventana
python pruebas/prueba_seleccion.py    # el flujo de cantidad y roles, a 2, 3 y 4
python pruebas/prueba_controles.py    # que nadie se robe las teclas de otro
python pruebas/prueba_paneles.py      # los paneles a varias resoluciones
python pruebas/prueba_estructuras.py  # los arboles por consola
python pruebas/prueba_textos.py       # que la fuente pueda dibujar todo el texto
```

### Como se juega

Al darle **Jugar** se pregunta primero cuantos juegan (2, 3 o 4) y despues cada
uno escoge su rol desde su propia seccion de pantalla. Dos jugadores no pueden
quedarse con el mismo rol. Ya en partida, cada uno se mueve por la nave en su
trozo de pantalla y usa su tecla de interaccion con lo que tenga cerca.

| | Jugador 1 | Jugador 2 | Jugador 3 | Jugador 4 |
|---|---|---|---|---|
| Moverse | WASD | Flechas | mando: stick o cruceta | mando: stick o cruceta |
| Interactuar / confirmar | E | Enter | A (o O) | A (o Y) |
| Elegir opcion | W / S | Flecha arriba / abajo | stick / cruceta (o I / K) | stick / cruceta (o T / G) |
| Arbol de habilidades | Q | Shift derecho | Y (o U) | Y (o R) |
| Usar habilidad | F | - (junto al Shift derecho) | X (o P) | X (o V) |
| Caminar en sigilo (mantener) | Shift izquierdo | AltGr o 0 del numerico | LB o LT | LB o LT |
| Celular (NEXUS): abrir / atras | TAB | . (punto) | RB (o J) | RB (o B) |
| Soltar algo del inventario | X | , (coma) | B (o L) | B (o N) |
| Cerrar un panel | - | - | B | B |

Cada jugador puede escoger con que juega: WASD, flechas, Mando 1 o Mando 2 (el
primer y el segundo mando que se conectan). Si hay algun mando conectado, despues
de la dificultad sale la pantalla **"¿Con que juega cada uno?"**: cada jugador, en
orden, presiona el boton de aceptar de su control (E, Enter o A) y ese control
queda suyo; dos no pueden tener el mismo, y presionarlo otra vez lo suelta. Asi
se puede jugar de 2 con dos mandos. Sin mandos no sale y es como siempre: el
jugador 1 con WASD, el 2 con flechas, y el 3 y el 4 (sin mando) escogen rol con
letras del teclado pero en partida no se mueven. En los menus el mando hace de
flechas y Enter. `python pruebas/probar_mando.py` muestra que boton manda cada
cosa por si algun mando sale con los numeros cambiados (se ajusta en `mandos.py`). No hay tecla de correr; la de sigilo hace caminar a la
mitad de velocidad y casi sin ruido.

Teclas globales: **[F11]** alterna ventana, **[F3]** muestra los FPS y cuanto tarda
cada cuadro (los cuadros lentos se escriben en la consola) y **[ESC]** (o START en el mando) abre el
menu de pausa: continuar, opciones, logros y terminar partida. En Opciones, ademas del
sonido y la pantalla completa, estan las vistas para probar: apagar el campo de vision y
la oscuridad, ver las hitboxes y ver el arbol de comportamiento de cada alien en vivo. No hay limite de tiempo: se pierde si atrapan a todos o se quedan sin vidas. Al terminar sale una pantalla de resultados (con cuanto duro la partida), desde donde se puede ver el arbol de logros de la partida. En el menu principal, **Logros** muestra el arbol completo con los que ya se consiguieron alguna vez en ese computador (se guardan en `Guardado/logros.json`).

Ademas hay editores para preparar los assets:

```bash
python Editores/editor_mapa.py       # poner aliens, escondites, terminales... (ver abajo)
python Editores/hitbox_editor.py     # dibujar las hitboxes de un mapa (rueda = zoom, 0 = ver todo, clic del medio = mover)
python Editores/personaje_editor.py  # calibrar escala e hitbox de un personaje
python Editores/visor_personajes.py  # revisar que sprites y config tiene cada personaje
```

### NEXUS: la red social en el celular

Cada jugador tiene NEXUS en su celular. Los aliens (el Cambiaformas, con cuentas
falsas que parecen prisioneros) riegan **rumores falsos** sobre lugares de la nave
("la capsula exploto", "las celdas tienen gas"...). El celular tiene tres pestanas
(se cambian con A/D, las flechas o la cruceta): **Misiones** (lo que hay que ir a
verificar, con su estado: por verificar, vas para alla, foto lista, desmentido),
**Equipo** (lo que publican tus companeros) y **Red** (lo demas). Cada jugador tiene
como maximo 3 cosas por verificar a la vez (si le llega otra estando lleno, no le
aparece). Con el celular se puede:

- **Ir a verificarlo**: una flecha lleva al lugar; al llegar se saca una foto sola.
- **Desmentir** con la foto: la verdad corre por la red y la tripulacion confia en
  ustedes. La foto tal cual convence a mas gente, pero se ve donde estas y el alien
  mas cercano va por ti; recortada es mas segura.
- **Compartir**: compartir un rumor sin verificar lo riega mas y tus seguidores
  dejan de confiar en ti.
- **¿De donde salio esto?** y **reportar**: reportar al bot que lo empezo lo borra
  de la red; reportar a un prisionero que solo se lo creyo no sirve de nada.

Arriba al centro esta la **barra de confianza** de la tripulacion, una sola para
todo el equipo: la parte **verde** (confian en ustedes) crece desde la izquierda, la
**roja** (le creen a los aliens) desde la derecha y en medio queda gris (los que no
deciden). Con la verde en 80% (la raya blanca) les pasan los **planos de la capsula**
(sin ellos no se puede reparar). Mientras la roja le gana a la verde, los aliens son
mas rapidos y ven mas lejos (pero con la roja alta no se pierde: solo se pierde
por vidas o si quedan todos encerrados). Con el celular abierto no te mueves: si un alien llega, te atrapa. Al final,
los resultados muestran como usaron NEXUS. Cuentas, rumores y numeros se editan en
`data/nexus.py`.

Las **Terminales NEXUS** del mapa son centrales de ayuda: muestran como va la
confianza, cuanto falta para los planos y que rumores faltan por desmentir, y
explican el uso sano de la red (como reconocer un rumor falso, cuidar la ubicacion,
cuentas falsas y reportes). Tambien dejan repasar el tutorial y, por ahora, abrir
el caso del infiltrado.

### El Guardia de la Bahia

En la sala de la capsula (la Bahia) hay un alien enorme, el **Guardia**: no sale
de ahi, ve a todo el que entra, no se le puede atravesar y atrapa a quien alcanza.
No le hacen nada el hackeo ni el señuelo. Hay dos formas de quitarlo:

- **Un rato (Resonante):** cerca de el, la tecla de interactuar (su Sintonia de
  señales) lo distrae 18 s: se va a un rincon a escuchar y no ve a nadie. Hay que
  reparar la capsula rapido y salir. Una Emision que caiga en la Bahia tambien.
- **Para siempre (Biomante):** mantener la tecla junto a la planta de la Biosfera
  hasta que crece y le da una **fruta** (queda en su inventario; la puede soltar
  para que otro la lleve). Quien la tenga se la da al Guardia y este
  se va a su rincon a comer. Sin Biomante (o si lo eliminan) aparece **abono**, y
  con el cualquiera hace crecer la planta (mas lento).

Se ponen con el editor de mapa (herramientas "Guardia" y "Planta").

```bash
python pruebas/prueba_guardia.py   # el Guardia, la planta, la fruta y el abono
```

### Los prisioneros y el Cambiaformas

Por la nave caminan 6 prisioneros, cada uno con su nombre de NEXUS encima y un
puntito de color: los **verdes** (confian en ustedes) dan pistas al pasar cerca,
los **grises** solo charlan y los **rojos** a veces gritan donde estas.

Uno de ellos no es un prisionero: es el **Cambiaformas**, un alien unico con su
propio arbol de comportamiento. Escoge a la presa mas sola, la sigue disfrazado y,
cuando la tiene cerca, se revela (susto) y corre mas rapido que nadie un rato. Si
falla, huye, se disfraza de otro prisionero y vuelve por la misma presa. Revisa el
casillero donde te vio esconderte, espera junto al lugar de sus rumores y se entera
cuando alguien te delata. Pistas: no habla, su nombre falla, puede haber dos con el
mismo nombre, el Escaneo y la Sintonia lo marcan y disfrazado no sube el pulso.
El hackeo lo aturde y le quita el disfraz; el **caso del Cambiaformas** (3 pruebas
subidas en una Terminal NEXUS, los sospechosos son los prisioneros que caminan) lo
deja 60 s sin poder disfrazarse. Numeros en `data/npcs.py`.

Tambien **suplanta** cuentas: publica en NEXUS como el prisionero que imita para
citar a alguien en un lugar apartado y emboscarlo. "¿De donde salio esto?" muestra
"dispositivo desconocido"; reportar la suplantacion lo deja al descubierto. Cerca
de el, disfrazado, se oye un **susurro**.

**Rescatar prisioneros:** con la tecla de interactuar junto a un prisionero le
preguntas "¿vienes conmigo?". Los verdes te siguen, los grises dudan y los rojos
no. Llevarlo a la capsula da puntos y publica un testimonio que riega confianza.
Ojo: el Cambiaformas disfrazado tambien acepta (sin decir nada) y te traiciona:
si te quedas solo con el, se revela; si llega con el grupo a la capsula, la
sabotea: arranca una pieza, la tira lejos y deshace parte de la reparacion. Si la
capsula ya estaba lista, deja de estarlo: hay que traer la pieza y repararla de
nuevo para poder escapar. Los verdes te
advierten si vas con el.

### Dificultad

Despues de escoger cuantos juegan se elige la dificultad (numeros en
`data/dificultad.py`):

| | Vidas | Aliens | Planos | Flecha | Fuga de la celda |
|---|---|---|---|---|---|
| **Facil** | no se pierden | 70% de velocidad/vision/oido | 60% | si | 8 s |
| **Normal** | 5 | 82% | 70% | si | 20 s |
| **Dificil** | 4 | 92% | 75% | no | no (solo si te liberan) |
| **Inteligente** | 3 | se ajusta solo (empieza en Normal) | 70% | hasta Normal | segun el nivel |

Tambien cambian cuanto espera el Cambiaformas para cazar, cuanto descansa, cuanto
tarda en traicionar y cada cuanto suplanta, y cada cuanto salen rumores y que tan
facil se los creen. La **flecha** amarilla señala lo que toca hacer (notas,
puerta, consolas, piezas, rumores, capsula o un compañero encerrado). Con **fuga**,
el encerrado sale solo despues de ese tiempo y que esten todos presos no es derrota.
La flecha amarilla va en este orden, segun el rol y lo que lleve cada uno:
rescatar a un compañero; notas y puerta; **consolas** (las hackea el Tecnomante o
quien tenga decodificador; si hay uno suelto, ir por el; los demas adelantan la
planta, el abono o el kit, o cuidan al que hackea); en la capsula, primero
**planta y fruta** para quitar al Guardia (el Resonante lo distrae cuando alguien
lleva una pieza o va a reparar, o si ya no hay como darle de comer); despues
piezas, kit, planos y **reparar la capsula**.
En un apagon solo puede fallar una caja de fusibles a la que se llegue caminando
desde el inicio con lo que este cerrado (la de la prision no, mientras su puerta
siga cerrada). Cual falla depende de la dificultad y de cuanto llevan de mision:
en Facil casi siempre la mas cercana a los jugadores, y cada vez mas lejos en
Normal, Dificil y a medida que avanzan.
La flecha **azul** (el lugar del rumor que vas a verificar) y la **roja** (la caja
de fusibles en un apagon) salen en todas las dificultades.
En todas las dificultades, la primera vez que alguien ve cada tipo de alien (el
Cambiaformas, cuando ya se revelo) el juego se pausa y una ventana lo señala y
explica como funciona (`juego/presentacion_aliens.py`, textos en
`data/presentacion_aliens.py`).

**Inteligente** tiene un "director" (`dificultad.py`): cada 4 s mira como va el
equipo (que tan rapido avanza la mision, confianza en NEXUS, capturas
recientes, vidas) y sube o baja un nivel continuo entre Facil y "Pesadilla" (los
numeros base del juego, mas que Dificil: sin fuga y la Sombra te deja sin
linterna hasta que vuelva la luz). La IA de la nave avisa cuando cambia. En los resultados sale hasta
donde llego.

### La mision (mapa de la nave)

Cuatro prisioneros escapan de una nave alienigena: apagar las consolas de
navegacion y reparar la capsula de escape; despues los aliens entran en alerta
y todos tienen que llegar a la capsula. En el mapa final (`MapaFinal`, 10 salas;
la capsula esta en la Bahia) y en el de la segunda entrega (`MapaE2`) empiezan
encerrados en Control y la primera fase es abrir su puerta
con el codigo (en la `Nave` vieja, la puerta de la prision). Puede haber **varias
puertas con codigo**: cada una tiene su color, su codigo y sus notas. La primera
es la de la fase 1; las demas se abren cuando sea (si detras queda algo de la
mision, la flecha lleva a abrirlas). Hay dos tipos de notas: las **normales**
(historia) y las **de codigo** (con una tachuela del color de su puerta). El
codigo de cada puerta sale en una de sus notas de codigo (se sortea) a las que
se llega antes de abrirla (pueden estar detras de otra puerta que se abre
antes); las otras dicen que el codigo no esta ahi. Si una puerta no tiene notas
de codigo, su codigo va en una normal, como antes.
Si atrapan a alguien va a una celda y otro lo tiene que sacar. Las vidas (los
corazones arriba a la izquierda) dependen de la dificultad: sin vidas queda eliminado. La
Biomante puede devolver vidas con Regeneración. Si eliminan al Tecnomante deja un decodificador, y si eliminan
al Forjador deja un kit de herramientas (si no hay ya uno por ahi), para que la mision
se pueda terminar. Si falta un rol desde el principio, aparece **uno solo** de su
consumible (decodificador, kit o abono), cada uno en un lugar de consumibles distinto.
Lo que lleva cada uno se ve en el inventario, abajo a la derecha. Las consolas y la reparacion se hacen
**manteniendo** la tecla de interactuar. La habilidad escogida se usa con **F**
(jugador 1) o **-** (jugador 2, la tecla junto al Shift derecho) y se paga con puntos del equipo.

Cada jugador tiene un **campo de vision**, como en Among Us: no ve a traves de
las paredes ni de las compuertas bajadas; lo que queda detras se ve en penumbra
y los aliens que esten ahi no se dibujan. Si sale el evento de **apagon** todo
queda a oscuras (cada uno ve lo que alumbra su linterna, que tampoco atraviesa
paredes; de los aliens no se ven ni los ojos ni su rango de vision, y sus
señales quedan a oscuras como ellos) y no funciona nada electrico: terminales,
NEXUS, escaneo, teclados, consolas, puertas para dos y los sellos del Forjador.
Dura hasta que alguien encuentre la caja de fusibles que parpadea en rojo y la
encienda manteniendo la tecla; en cualquier dificultad, una **flecha roja**
alrededor de cada jugador señala dónde está. En el apagon, ademas, sale **la Sombra**
(`entidades/sombra.py`, idea de Joseph): a oscuras solo se le ven los ojos; si la
linterna la apunta no se puede mover (como los angeles llorones de Doctor Who), y si le das la
espalda se acerca. Si te alcanza te apaga la linterna un rato (en Pesadilla, el
nivel mas alto de Inteligente, hasta que alguien prenda la caja de fusibles); nunca atrapa. Al volver la luz se disuelve. Tiene su propio arbol de comportamiento.
Hay tres tipos de alien de ruta
(Vigia, Ciego y Cazador) con el mismo arbol de comportamiento y
distintos sentidos, ademas del Cambiaformas y la Sombra. Cada minuto, mas o menos, la nave lanza un evento al azar
(apagon, alarma o cierre de una compuerta; solo puede haber un apagon a la vez), y la puerta a la sala de control se
abre solo con dos jugadores, cada uno en un panel. En todas las dificultades la
partida empieza con unos pasos sin tiempo: cada jugador los pasa con su tecla de
habilidad, y los aliens despiertan (y la puerta de la prision deja meter el codigo)
solo cuando todos terminaron.

Mientras se arma la partida sale una **pantalla de carga** (`screens/carga.py`):
el Cambiaformas persigue al Tecnomante por un pasillo, con una barra y un consejo
(`data/consejos_carga.py`). La partida se arma en otro hilo para que la animacion
no se congele, y la pantalla dura al menos 2 s.

Mision secundaria (opcional), idea de Joseph: **el infiltrado**. Uno de los que
escriben en NEXUS es un alien cambiaformas. Por la nave hay tres pruebas (audio,
expediente y captura de camara); cada una revela un rasgo suyo y, al subirla
desde una Terminal NEXUS, descarta sospechosos. Con las tres queda expuesto y los
aliens se quedan confundidos 20 s. Se puede acusar antes, pero si fallan el caso
se cierra y la nave delata al que acuso.

```bash
python pruebas/prueba_mision.py    # juega la mision completa sin ventana
python pruebas/prueba_sorpresas.py # oscuridad, aliens, sigilo, eventos, puertas, tutorial
python pruebas/prueba_vision.py    # campo de vision: las paredes tapan
python pruebas/prueba_nexus.py     # NEXUS: grafo, rumores, celular, barras y planos
python pruebas/prueba_cambiaformas.py # prisioneros que caminan y el Cambiaformas
python pruebas/prueba_dificultad.py   # las 4 dificultades, la flecha, la fuga y el director
python pruebas/prueba_victoria.py     # una partida ganada en Normal (NEXUS, planos y Cambiaformas)
python pruebas/prueba_vista_grafo.py  # la vista de los grafos (Pausa > Opciones > Grafo)
python pruebas/prueba_infiltrado.py # mision secundaria del infiltrado de NEXUS
python pruebas/prueba_logros.py    # arbol de logros y cuando se consigue cada uno
python pruebas/prueba_sonidos.py   # que todo sonido pedido exista y suene donde va
python pruebas/simulador.py 8      # bots que juegan 8 partidas: bugs y balance
python pruebas/prueba_hud.py       # capturas del HUD con 2, 3 y 4 jugadores
python pruebas/prueba_salas_selladas.py # menos jugadores, menos salas
```

### Menos jugadores, menos salas (apagado)

**Apagado**: siempre se juega con el mapa entero (`ACTIVO = False` en
`juego/salas_selladas.py`). Si se prende: con 2 jugadores se juega en 6 salas, con 3 en 8 y con 4 en 10 (los pasillos no
cuentan como sala). Las que sobran se **sellan** al empezar la ronda
(`juego/salas_selladas.py`): se ven oscuras, con franjas de peligro en la
entrada, no se puede entrar y lo que habia adentro no sale en la partida.
Siempre quedan abiertas Control (inicio), Prision, General y Bahia (final), y
tambien la sala donde este la capsula. Las demas se escogen al azar, pero solo
si todo lo abierto queda conectado y alcanza para la mision (3 piezas, notas,
consolas, pruebas...). Para lo de conectado se usa un **grafo de salas** (el
mismo `Estructuras/grafo.py` de NEXUS): cada rectangulo de sala es un nodo y
los que se tocan tienen una arista; se recorre con BFS desde Control. Si un
mapa tiene menos salas que las que tocan, no se sella nada.

### Editar el mapa sin tocar codigo

`python Editores/editor_mapa.py` abre el mapa y deja poner con el mouse todo lo
que va encima: inicio de los jugadores, rutas de los aliens, escondites,
celdas, puerta de la prision, notas, consolas, capsula, piezas, terminales NEXUS,
terminales y paneles de los roles, consumibles, compuertas, puertas para dos,
cajas de fusibles, pruebas del infiltrado y **salas** (rectangulos con nombre:
el HUD de cada jugador dice en que sala esta; el editor avisa si queda piso sin
sala) (la lista con sus teclas
esta en el editor). Clic izquierdo pone o arrastra, clic derecho borra, `Ctrl+S` guarda,
`M` hace que el juego use ese mapa y `F5` guarda y abre el juego para probar.
La herramienta **Puertas con codigo**: un clic pone una puerta y los siguientes
ponen sus **notas de codigo**, hasta presionar `X`; despues, otro clic pone otra
puerta (de otro color). Clic en una puerta la elige y sus notas siguen con los
clics. Clic derecho en una nota la borra; en una puerta, la quita con sus notas.
Con `F` las notas que pones son **solo Difícil** (salen en Difícil e Inteligente):
sirven para que el codigo de una puerta que en Facil/Normal esta adentro de la
prision (lo lee el que se escapa de su celda) en Dificil, donde nadie sale solo,
este afuera.
Marca en rojo lo que choca con paredes y en naranja lo que no se alcanza
caminando. Guarda en `Hitboxes/<mapa>_objetos.json`; las paredes se siguen
dibujando con `hitbox_editor.py`. Para un mapa nuevo: dibujar sus paredes con
el editor de hitboxes y despues poner todo lo demas con el editor de mapa.

```bash
python pruebas/prueba_editor_mapa.py  # el editor y que el juego use lo guardado
python pruebas/prueba_hitbox_editor.py  # zoom y paredes idénticas a las del juego
```

## Estructura del repositorio

- `main.py` -- arranca el juego (`python main.py`).
- `juego/` -- el motor: el loop (`app.py`), el mapa (`mundo.py`), la navegacion
  de los aliens (grafo de la nave), el campo de vision y la oscuridad, la pausa,
  el tutorial, la dificultad, el audio, las fuentes y los mandos.
- `entidades/` -- los que se mueven: jugadores, aliens, el Cambiaformas, los
  prisioneros (NPCs), las habilidades de cada rol y el minijuego del casillero.
- `misiones/` -- la mision por fases, los eventos, las puertas para dos, el caso
  del Cambiaformas, los logros y la IA de la nave.
- `redes/` -- NEXUS: el grafo de cuentas y rumores (`nexus.py`) y el celular.
- `Estructuras/` -- los arboles y el grafo (con sus nodos).
- `screens/` -- lo que se dibuja: menu, seleccion, partida, paneles, resultados...
- `data/` -- datos editables sin tocar codigo: roles, habilidades, aliens, logros,
  NEXUS, prisioneros, dificultad, notas, frases de la IA...
- `Movimiento/` -- carga de sprites, animaciones y movimiento de personajes.
- `Editores/` -- herramientas para hitboxes, el mapa y calibracion de personajes.
- `pruebas/` -- pruebas que corren sin abrir ventana y el simulador de bots.
- `Imagenes/` -- assets: `Fondos/` (la nave y el menu), `Personajes/<Rol>/`
  (`<Rol>_<animacion>_<direccion>.png`), `Aliens/` (incluido el Cambiaformas),
  `Prisioneros/<carpeta>/` (los que caminan; cada carpeta nueva se reparte
  sola) y `Objetos/`.
- `Hitboxes/` -- los JSON que generan los editores (paredes, objetos del mapa,
  hitbox de cada rol). La nave es el unico mapa.
- `Audio/`, `Fuentes/` -- efectos de sonido y la tipografia.
