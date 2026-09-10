"""Loop caza constante. Uso: python loop_caza.py --una-vez"""
import sys, os, time, argparse, traceback
sys.path.insert(0, os.path.dirname(__file__))
QUERIES_ROT = ["agencia marketing digital Buenos Aires contacto email", "agencia publicidad Argentina contacto email", "agencia marketing digital Cordoba contacto email", "agencia marketing digital Rosario contacto email", "agencia marketing digital Mexico contacto email", "agencia marketing digital Colombia contacto email"]

QUERIES_ROT2 = ["agencia marketing digital Chile contacto email", "community manager freelance Argentina email contacto", "disenador web freelance Argentina contacto email", "agencia branding Mexico contacto email", "agencia digital Peru contacto email", "estudio diseno web Argentina contacto email"]

QUERIES_ESPANA = ["agencia marketing digital Madrid contacto email", "agencia marketing digital Barcelona contacto email", "agencia publicidad España contacto email", "community manager freelance España contacto email", "disenador grafico freelance España contacto email", "agencia digital Valencia contacto email"]
def ciclo(por_ciclo, inicio_q):
    import cazar_brave as cz
    todas = QUERIES_ROT + QUERIES_ROT2 + QUERIES_ESPANA
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
        idx = (idx + 4) % len(QUERIES_ROT + QUERIES_ROT2 + QUERIES_ESPANA)
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
