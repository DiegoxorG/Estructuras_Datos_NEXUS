# PR: prototipo cliente-servidor (punto 13)

Rama `claude/cliente-servidor`, desde `main`.

## Qué hay

- `docs/cliente_servidor.md`: el diseño (procesos, hilos, protocolo, quién es
  dueño de qué, latencia, qué falta y cómo seguir).
- `cliente_servidor/` (paquete nuevo; `redes/` no se tocó, esa es la red
  social del juego):
  - `protocolo.py`: TCP con un objeto JSON por línea; `LectorLineas` arma los
    mensajes completos a partir de lo que llega por `recv`. Solo librería estándar.
  - `servidor.py`: escucha en 127.0.0.1, acepta una conexión por jugador
    (2-4), corre el `Game` de siempre sin ventana a 60 Hz y manda
    instantáneas a 30 Hz. Un hilo lector por conexión; solo el hilo principal
    toca `Game`. Se apaga solo cuando se desconectan todos; al que llega con
    la partida llena le contesta `error`.
  - `cliente.py`: una sola ventana, una conexión por jugador local, teclado
    (las teclas de cada puesto de `entidades/jugador.py`) y mandos
    (`juego/mandos.py`), pantalla dividida con el fondo del mapa, los sprites
    de los personajes, aliens con su cono de visión, cápsula, piezas, HUD de
    texto, paneles en texto y la "respuesta" medida en ms.
- `pruebas/prueba_cliente_servidor.py`: levanta el servidor en otro proceso
  con un puerto libre, conecta 2 clientes falsos por socket, revisa el
  saludo, que quietos no se mueven, que con `derecha` los dos van a la
  derecha, que al soltar se paran, el `ack`, que el celular se abre y se
  cierra solo para quien lo pidió y que un tercero recibe "partida llena".
  Tarda ~5 s.
- README: una sección corta con los comandos.

**El juego no se tocó**: `python main.py` funciona igual y ningún archivo de
`juego/`, `entidades/`, `screens/`, `misiones/` ni assets cambió. El gancho
para meter la entrada es reemplazar `envolver` en la instancia de `Mandos`
del `Game` del servidor (ver el diseño).

## Cómo probarlo a mano en una laptop

Desde la carpeta del proyecto, en dos terminales:

```bash
# Terminal 1: el servidor (tarda unos segundos en armar la partida)
python -m cliente_servidor.servidor --jugadores 2

# Terminal 2: el cliente, con J1 (WASD, E, F, Q, Shift, Tab, X) y J2 (flechas, Enter, -, Shift der., AltGr, punto, coma)
python -m cliente_servidor.cliente --jugadores 2
```

Variantes:

```bash
# Escoger roles y dificultad
python -m cliente_servidor.servidor --jugadores 2 --roles Biomante,Resonante --dificultad facil

# Probar la red sin que los aliens molesten (ni la ventana de "alien nuevo")
python -m cliente_servidor.servidor --jugadores 2 --aliens-quietos --sin-presentaciones

# Cuatro jugadores: J3 y J4 con mando (como en el modo local)
python -m cliente_servidor.servidor --jugadores 4
python -m cliente_servidor.cliente --jugadores 4

# Un jugador por ventana (dos clientes, cada uno con WASD): para ver que de
# verdad son conexiones separadas. Ojo: el teclado solo va a la ventana con foco.
python -m cliente_servidor.servidor --jugadores 2
python -m cliente_servidor.cliente --jugadores 1      # J1
python -m cliente_servidor.cliente --jugadores 1      # J2 (otra terminal)

# Otro puerto
python -m cliente_servidor.servidor --puerto 6000
python -m cliente_servidor.cliente --puerto 6000

# La prueba automática (sin ventana)
python pruebas/prueba_cliente_servidor.py
```

Esc cierra el cliente. Cuando se cierran todos los clientes, el servidor
termina solo (o Ctrl+C).

## Limitaciones

- Sin menús en red: cantidad, roles y dificultad van por argumentos del
  servidor. El tutorial se salta. No hay pausa ni pantalla de resultados
  (sale "¡ESCAPARON!" o "DERROTA" encima y el servidor deja de actualizar).
- El dibujo del cliente es sencillo: sin oscuridad ni linternas, sin sonido,
  aliens como círculos, paneles (notas, códigos, celular, árbol) como listas
  de texto. Se puede jugar la misión, pero el modo local se ve mucho mejor.
  Las piezas se ven aunque el rol no las "vea" en el modo local.
- La "ventana de alien nuevo" depende del tamaño de pantalla del servidor
  (sin ventana), no del de cada cliente.
- Sin reconexión: si un cliente se cae, su jugador se queda quieto.
- Sin interpolación ni predicción: va bien en localhost (respuesta de
  15-20 ms medida) y debería ir bien en una LAN; por Internet no.
- `--host 0.0.0.0` permite clientes de otras máquinas, pero no se probó.
- J3 y J4 sin mando solo tienen I/K/O y T/G/Y (arriba, abajo, interactuar),
  igual que en local.
- Se probó con pygame 2.6.1 y con pygame-ce 2.5.8 (la prueba automática y el
  cliente con el driver dummy); no con una ventana de verdad ni con mandos
  físicos.
