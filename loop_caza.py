"""Loop caza constante. Uso: python loop_caza.py --una-vez"""
import sys, os, time, argparse, traceback
sys.path.insert(0, os.path.dirname(__file__))
QUERIES_FILE = os.path.join(os.path.dirname(__file__), "queries_loop_caza.txt")


def _cargar_queries():
    """Lee queries_loop_caza.txt: una query por línea, se ignoran vacías y
    las que empiezan con '#' (separadores/comentarios de país). Separado
    del código para poder sumar ciudades/países nuevos sin tocar nada acá."""
    with open(QUERIES_FILE, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]


def ciclo(por_ciclo, inicio_q):
    import cazar_brave as cz
    todas = _cargar_queries()
    q = todas[inicio_q % len(todas):] + todas[:inicio_q % len(todas)]
    qs = [("Loop %d" % (i + 1), x) for i, x in enumerate(q[:4])]
    return cz.main(limit=por_ciclo, queries=qs)
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--intervalo", type=int, default=10)
    ap.add_argument("--por-ciclo", type=int, default=2)
    ap.add_argument("--una-vez", action="store_true")
    ap.add_argument("--max-ciclos", type=int, default=0)
    a = ap.parse_args()
    stop = os.path.join(os.path.dirname(__file__), "STOP.loop")
    if os.path.exists(stop):
        os.remove(stop)
    print("LOOP intervalo=%dmin por-ciclo=%d" % (a.intervalo, a.por_ciclo))
    n, idx = 0, 0
    while True:
        n += 1
        print("===== CICLO %d =====" % n)
        try:
            print("CICLO %d ok=%s" % (n, ciclo(a.por_ciclo, idx)))
        except Exception as e:
            print("CICLO %d ERROR: %s" % (n, e))
            traceback.print_exc()
        idx = (idx + 4) % len(_cargar_queries())
        if a.una_vez:
            break
        if a.max_ciclos and n >= a.max_ciclos:
            break
        for m in range(a.intervalo * 60, 0, -60):
            if os.path.exists(stop):
                print("STOP.loop, saliendo.")
                return
            print("prox en %dmin (STOP.loop frena)" % ((m + 59) // 60))
            time.sleep(60)
if __name__ == "__main__":
    main()
