"""
Heartbeat generico para scripts de loop (loop_caza.py, send_loop.py, y
los que se agreguen despues). Un solo lugar (pestaña 'estado_procesos'
en la Sheet) que el dashboard lee para mostrar un semaforo por proceso -
agregar un script nuevo a la lista no requiere tocar el dashboard, solo
que ese script llame a reportar_heartbeat() una vez por ciclo.
"""
from datetime import datetime

from core.sheets_client import SheetsClient

TAB = "estado_procesos"
HEADERS = ["Proceso", "Ultima Actividad", "Detalle"]


def reportar_heartbeat(sheets: SheetsClient, proceso: str, detalle: str = "") -> None:
    """Escribe o actualiza la fila de `proceso` con la hora actual. No
    lanza excepcion si falla (un problema de Sheets no debe frenar el
    loop real que está haciendo el trabajo)."""
    try:
        sheets.add_sheet(TAB, headers=HEADERS)
        filas = sheets.read_range(f"'{TAB}'!A2:C1000")
        fila_nueva = [proceso, datetime.now().strftime("%d/%m/%Y %H:%M:%S"), detalle]

        for i, fila in enumerate(filas):
            if fila and fila[0] == proceso:
                sheets.write_range(f"'{TAB}'!A{i + 2}", [fila_nueva], append=False)
                return
        sheets.write_range(f"'{TAB}'!A2", [fila_nueva], append=True)
    except Exception as e:
        print(f"⚠️  No se pudo reportar heartbeat de '{proceso}': {e}")
