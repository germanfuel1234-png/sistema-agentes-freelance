"""Caza clientes REALES para tu planilla gid=353922196."""
import csv, sys, os, time, logging
sys.path.insert(0, os.path.dirname(__file__))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
SHEET_ID = "1hjwAUrKaCu53McleYaJZj99b65IoKHBVqIZ96qfvF1I"
GID = "353922196"
PUBLIC_CSV = "planilla_public.csv"
PENDING_CSV = "nuevos_leads_para_sheet.csv"

QUERIES = [("Agencia marketing", "agencia de marketing digital Buenos Aires contacto email"), ("Agencia marketing 2", "agencia publicidad digital Argentina contacto"), ("Freelance marketing", "community manager freelance Argentina email contacto"), ("Disenador web", "disenador web freelance Argentina contacto email"), ("Agencia marketing MX", "agencia marketing digital Mexico contacto email"), ("Agencia marketing CO", "agencia marketing digital Colombia contacto email")]
def download_public_sheet():
    import requests
    url = "https://docs.google.com/spreadsheets/d/" + SHEET_ID + "/export?format=csv&gid=" + GID
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    open(PUBLIC_CSV, "wb").write(r.content)
    print("[OK] Planilla descargada: %d bytes" % len(r.content))
def existing_emails():
    import re
    emails = set()
    try:
        with open(PUBLIC_CSV, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                v = (row.get("Mail o IG") or "").lower()
                for m in re.findall(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", v):
                    emails.add(m)
    except FileNotFoundError:
        pass
    print("[INFO] Emails ya en planilla: %d" % len(emails))
    return emails
def cazar_reales(limit=2, espera=75):
    from services.search_service import SearchService
    from services.duckduckgo_search import search_duckduckgo, find_email_on_page
    from urllib.parse import urlparse
    from core.models import Lead, TrackType
    svc = SearchService()
    leads, seen = [], set()
    for label, query in QUERIES:
        if len(leads) >= limit:
            break
        print("[BUSCA] " + query)
        results = search_duckduckgo(query, limit=9, session=svc.session)
        print("  -> %d resultados" % len(results))
        for item in results:
            if len(leads) >= limit:
                break
            link = item.get("link", "")
            domain = urlparse(link).netloc.lower()
            if not link or domain in seen:
                continue
            email = svc._extract_email(item.get("snippet", "") + " " + item.get("title", ""))
            if not email:
                email = find_email_on_page(link, session=svc.session)
            if not email:
                continue
            seen.add(domain)
            lead = Lead(business_name=svc._business_name_from_result(item.get("title", ""), link), email=email.lower(), track=TrackType.MARKETING, industry=label, country=svc._infer_country_from_domain(domain, "Argentina"), website=link, source="DuckDuckGo")
            if svc.validate_lead(lead):
                leads.append(lead)
                print("  [REAL] %s | %s | %s" % (lead.business_name, lead.email, lead.website))
        if len(leads) < limit:
            print("  [espera %ds anti-bloqueo...]" % espera)
            time.sleep(espera)
    return leads
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=2)
    ap.add_argument("--espera", type=int, default=75)
    ap.add_argument("--reintentos", type=int, default=3)
    ap.add_argument("--no-download", action="store_true")
    args = ap.parse_args()
    if not args.no_download:
        try:
            download_public_sheet()
        except Exception as e:
            print("[WARN] no se pudo descargar: %s" % e)
    ya = existing_emails()
    nuevos = []
    for intento in range(1, args.reintentos + 1):
        print("[INTENTO %d/%d]" % (intento, args.reintentos))
        nuevos = cazar_reales(limit=args.limit, espera=args.espera)
        if nuevos:
            break
        if intento < args.reintentos:
            print("[REINTENTO en %ds...]" % args.espera)
            time.sleep(args.espera)
    frescos = [l for l in nuevos if l.email.lower() not in ya]
    print("[INFO] Nuevos no duplicados: %d/%d" % (len(frescos), len(nuevos)))
    with open(PENDING_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Fecha envio", "Negocio/Agencia", "Track (PyME/Marketing)", "Rubro", "Ciudad", "Contacto", "Mail o IG", "Asunto usado", "Respondio (Si/No)", "Resultado"])
        for l in frescos:
            w.writerow(["", l.business_name, l.track.value, l.industry, l.country, l.contact_name, l.email, "", "", l.website or ""])
    print("[OK] CSV local: %s (%d filas)" % (PENDING_CSV, len(frescos)))
    if not os.path.exists("credentials.json") and not os.path.exists("token.json"):
        print("[BLOQUEADO] Falta credentials.json (Opcion A). Pasos:")
        print("  1) https://console.cloud.google.com/apis/credentials?project=1062678513752")
        print("  2) Crear ID cliente OAuth tipo ESCRITORIO -> Descargar JSON")
        print("  3) Renombrar a credentials.json y copiar a esta carpeta:")
        print("     c:\\Users\\Gernet\\Downloads\\sistema-agentes-freelance-main (1)\\sistema-agentes-freelance-main\\")
        print("  4) Habilitar Sheets+Drive (una vez):")
        print("     https://console.developers.google.com/apis/api/sheets.googleapis.com/overview?project=1062678513752")
        print("     https://console.developers.google.com/apis/api/drive.googleapis.com/overview?project=1062678513752")
        print("  5) Re-ejecutar: python cazar_y_guardar.py --limit 2")
        print("Pega manual %s al final de gid=%s." % (PENDING_CSV, GID))
        return False
    from core.sheets_client import SheetsClient
    try:
        sheets = SheetsClient()
        print("[INFO] Pestanas: %s" % sheets._get_sheet_titles())
        ok = 0
        for l in frescos:
            if sheets.add_lead(l):
                ok += 1
                print("  [SHEETS] %s <%s>" % (l.business_name, l.email))
        print("[OK] Guardados: %d/%d" % (ok, len(frescos)))
        return ok > 0
    except Exception as e:
        print("[ERROR Sheets] %s" % e)
        import traceback; traceback.print_exc()
        return False
if __name__ == "__main__":
    sys.exit(0 if main() else 1)
