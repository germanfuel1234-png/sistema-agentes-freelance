"""Loop combinado: alterna entre cazar_indeed.py (ofertas de empleo reales,
rápido) y busqueda_linkedin (posteos orgánicos de LinkedIn/X, mucho más
lento y de rendimiento muy bajo - ver busqueda_linkedin/README.md). Se
alternan en vez de correr juntos en cada ciclo para que un ciclo de Indeed
no quede bloqueado esperando los ~66 queries de LinkedIn.

Uso: venv312/bin/python3 -u loop_indeed_linkedin.py
Para frenarlo: touch STOP_indeed_linkedin.loop
"""
import argparse
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(__file__))

STOP_FILE = os.path.join(os.path.dirname(__file__), "STOP_indeed_linkedin.loop")


def ciclo_indeed(por_ciclo):
    import cazar_indeed
    return cazar_indeed.main(limit=por_ciclo)


def ciclo_linkedin():
    from busqueda_linkedin.actualizar_oportunidades_freelance import collect, guardar, QUERIES, DEFAULT_TAB
    from core.sheets_client import SheetsClient
    from config.settings import settings

    key = settings.google_custom_search_api_key
    cx = settings.google_custom_search_engine_id
    res = collect(QUERIES, key if key and cx else None, cx if key and cx else None,
                   days=7, do_enrich=True, limit=10)
    if not res:
        print("Sin hallazgos de LinkedIn/X esta vez.")
        return False
    nuevos, base = guardar(res, DEFAULT_TAB, SheetsClient())
    print(f"{len(nuevos)} posteos nuevos guardados (de {base} ya existentes).")
    return len(nuevos) > 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--intervalo", type=int, default=180)
    ap.add_argument("--por-ciclo-indeed", type=int, default=5)
    ap.add_argument("--una-vez", action="store_true")
    ap.add_argument("--max-ciclos", type=int, default=0)
    a = ap.parse_args()

    if os.path.exists(STOP_FILE):
        os.remove(STOP_FILE)

    print(f"LOOP INDEED+LINKEDIN intervalo={a.intervalo}min por-ciclo-indeed={a.por_ciclo_indeed}")
    n = 0
    while True:
        n += 1
        print(f"===== CICLO {n} =====")
        if n % 2 == 1:
            print("-- Indeed (ofertas de empleo reales) --")
            try:
                ok = ciclo_indeed(a.por_ciclo_indeed)
            except Exception as e:
                print(f"ERROR Indeed: {e}")
                traceback.print_exc()
                ok = False
        else:
            print("-- LinkedIn/X (posteos orgánicos, puede tardar varios minutos) --")
            try:
                ok = ciclo_linkedin()
            except Exception as e:
                print(f"ERROR LinkedIn: {e}")
                traceback.print_exc()
                ok = False
        print(f"CICLO {n} ok={ok}")

        if a.una_vez:
            break
        if a.max_ciclos and n >= a.max_ciclos:
            break
        for m in range(a.intervalo * 60, 0, -60):
            if os.path.exists(STOP_FILE):
                print("STOP_indeed_linkedin.loop, saliendo.")
                return
            print(f"próx ciclo en {(m + 59) // 60}min (STOP_indeed_linkedin.loop frena)")
            time.sleep(60)


if __name__ == "__main__":
    main()
