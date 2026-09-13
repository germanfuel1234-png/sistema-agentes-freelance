"""Loop que alterna entre cazar_indeed.py (desarrollador web) y
caza_programador.py (automatización/bots/RPA) - ambos usan Indeed
exclusivamente, sin tocar Brave/Bing/DuckDuckGo en ningún momento.

Diseño a propósito: loop_caza.py (agencias de marketing, la prioridad
real del usuario) depende de Bing como respaldo cuando Brave falla. La
búsqueda automática de LinkedIn/X (que vivía antes en este mismo loop)
le pegaba fuerte a Bing con muy poco rendimiento real (~1 hallazgo en
+180 intentos en toda la sesión), compitiendo justo por el recurso que
más le importa a loop_caza.py. Se sacó de la rotación automática por
eso - sigue disponible para búsqueda manual en
busqueda_linkedin/consultas_linkedin.txt.

Uso: venv312/bin/python3 -u loop_indeed.py
Para frenarlo: touch STOP_indeed.loop
"""
import argparse
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(__file__))

STOP_FILE = os.path.join(os.path.dirname(__file__), "STOP_indeed.loop")


def ciclo_desarrollador_web(limit):
    import cazar_indeed
    return cazar_indeed.main(limit=limit)


def ciclo_automatizacion(limit):
    import caza_programador
    return caza_programador.main(limit=limit)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--intervalo", type=int, default=180)
    ap.add_argument("--por-ciclo", type=int, default=5)
    ap.add_argument("--una-vez", action="store_true")
    ap.add_argument("--max-ciclos", type=int, default=0)
    a = ap.parse_args()

    if os.path.exists(STOP_FILE):
        os.remove(STOP_FILE)

    print(f"LOOP INDEED (desarrollador web + automatización) intervalo={a.intervalo}min por-ciclo={a.por_ciclo}")
    n = 0
    while True:
        n += 1
        print(f"===== CICLO {n} =====")
        if n % 2 == 1:
            print("-- Indeed: desarrollador web --")
            try:
                ok = ciclo_desarrollador_web(a.por_ciclo)
            except Exception as e:
                print(f"ERROR desarrollador web: {e}")
                traceback.print_exc()
                ok = False
        else:
            print("-- Indeed: automatización/bots/RPA --")
            try:
                ok = ciclo_automatizacion(a.por_ciclo)
            except Exception as e:
                print(f"ERROR automatización: {e}")
                traceback.print_exc()
                ok = False
        print(f"CICLO {n} ok={ok}")

        if a.una_vez:
            break
        if a.max_ciclos and n >= a.max_ciclos:
            break
        for m in range(a.intervalo * 60, 0, -60):
            if os.path.exists(STOP_FILE):
                print("STOP_indeed.loop, saliendo.")
                return
            # Avisa cada 30 min, no minuto a minuto.
            if m % 1800 == 0:
                print(f"próx ciclo en {(m + 59) // 60}min (STOP_indeed.loop frena)")
            time.sleep(60)


if __name__ == "__main__":
    main()
