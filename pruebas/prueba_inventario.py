"""Prueba del inventario (entidades/jugador.py: Inventario).

    python pruebas/prueba_inventario.py

Al soltar o entregar lo último de un tipo, el tipo tiene que desaparecer del
inventario. Counter.__delitem__ solo borra si `tipo in self`, y como
Inventario cambia __contains__ (cuenta > 0), con la cuenta en 0 no borraba:
quedaba {"fruta": 0}, el inventario "vacío" seguía siendo verdadero y len()
contaba un tipo que no llevaba (lo encontró pruebas/simulador_masivo.py
después de que el Biomante le diera la fruta al Guardia).
"""

import os, sys
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from entidades.jugador import Inventario

inv = Inventario()
inv.add("fruta")
inv.discard("fruta")
assert "fruta" not in inv
assert dict(inv) == {}, f"quedó algo en el inventario: {dict(inv)}"
assert not inv and len(inv) == 0 and list(inv) == []

# Varios del mismo: se van de a uno y al final no queda la clave.
inv.add("kit", 2)
inv.discard("kit")
assert inv["kit"] == 1 and "kit" in inv
inv.discard("kit")
assert dict(inv) == {}, dict(inv)

# Soltar algo que no tiene no deja claves en 0.
inv.discard("abono")
assert dict(inv) == {}, dict(inv)
print("OK: el inventario no deja tipos en 0")
