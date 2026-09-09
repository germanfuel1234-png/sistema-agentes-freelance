"""Caza 2 REALES via Brave (no bloqueado) y guarda en gid=353922196."""
import csv, sys, os, re, time
sys.path.insert(0, os.path.dirname(__file__))
SHEET_ID = "1hjwAUrKaCu53McleYaJZj99b65IoKHBVqIZ96qfvF1I"
GID = "353922196"
PENDING_CSV = "nuevos_leads_para_sheet.csv"
QUERIES = [
    ("Agencia marketing", "agencia marketing digital Buenos Aires contacto email"),
    ("Agencia marketing 2", "agencia publicidad Argentina contacto email"),
]
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}
UA_ROT = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.2 Safari/605.1.15",
]
_n_brave = [0]
def _headers():
    _n_brave[0] += 1
    h = dict(H)
    h["User-Agent"] = UA_ROT[_n_brave[0] % len(UA_ROT)]
    return h
def brave_links(query, limit=9, reintentos=2):
    import requests
    from bs4 import BeautifulSoup
    last = None
    for intento in range(1, reintentos + 1):
        try:
            r = requests.get("https://search.brave.com/search", params={"q": query}, headers=_headers(), timeout=25)
            r.raise_for_status()
            break
        except Exception as e:
            last = e
            print("  intento %d/%d FAIL: %s" % (intento, reintentos, e))
            if intento < reintentos:
                time.sleep(60)
    else:
        raise last
    s = BeautifulSoup(r.text, "html.parser")
    out = []
    for a in s.select("a[href^=http]"):
        href = a.get("href", "")
        if "brave.com" in href or href in out:
            continue
        title = a.get_text(strip=True)
        if len(title) < 4:
            continue
        out.append((title, href))
        if len(out) >= limit:
            break
    return out
def _clean_name(title, link):
    """Limpia titulos sucios de Brave. Ej:
    'HooplaHoopla Hoopla es una Agencia...' -> 'Hoopla'
    'TOTAL MEDIOStotalmedios.com directorio...' -> 'Total Medios'"""
    from urllib.parse import urlparse
    from services.search_service import SearchService
    base = SearchService._business_name_from_result(title, link)
    domain = urlparse(link).netloc.lower().replace("www.", "")
    dom_simple = domain.split(".")[0] if domain else ""
    # 1) quita prefijo de dominios pegados al inicio:
    #    "ar.mdm.comar.mdm.comAgencia..." -> "Agencia..."
    base = re.sub(
        r"(?i)^((?:[a-z0-9-]+\.)+(?:com|ar|mx|co|cl|pe|es|la|net|org|io))+",
        "", base).strip()
    # 2) corta migas/titulos largos, conserva parte principal
    for sep in ["›", "»"]:
        if sep in base:
            base = base.split(sep)[0]
    for sep in [" | ", " — ", " – ", " - "]:
        if sep in base:
            left = base.split(sep)[0].strip()
            if len(left) >= 3:
                base = left
            break
    # 3) corta colas descriptivas EN BUCLE hasta que no quede ninguna
    markers = [" es una ", " es un ", " agencia de ", " estudio de ",
               " directorio", " disenador", " diseñador", " portada",
               " home", " coagencia", " marketing digital"]
    while True:
        low = base.lower()
        cut = None
        for marker in markers:
            i = low.find(marker)
            if i > 3:
                cut = i
                break
        if cut is None:
            break
        base = base[:cut].strip()
    # 4) quita dominio pegado/duplicado
    if dom_simple and len(dom_simple) > 3:
        base = re.sub(r"(?i)^(\w{4,})\1(?=[A-Z ])", r"\1 ", base)
        base = re.sub(re.escape(domain), " ", base, flags=re.I)
        base = re.sub(r"\.(com|ar|mx|co|cl|pe|es|la)\b", " ", base, flags=re.I)
        base = re.sub(r"(?i)\b(" + re.escape(dom_simple) + r"){2,}\b",
                      dom_simple, base)
    base = re.sub(r"\s+", " ", base).strip(" -|›")
    # 5) colapsa duplicada con espacio (ya con espacios normalizados)
    base = re.sub(r"(?i)^(\w{4,}) \1(\s|$)", r"\1\2", base).strip()
    base = base[:60].strip()
    # 6) si quedo generico ("Agencia", "CoAgencia de Marketing") usa el dominio
    if not base or len(base) < 3 or base.lower() in _GENERIC_NAMES:
        base = _pretty_domain(domain)
    if base and base[0].islower():
        base = base[0].upper() + base[1:]
    return base
def _pretty_domain(domain):
    """Nombre legible desde dominio: 'mdmarketingdigital.com' -> 'Md Marketing Digital'."""
    parts = domain.split(".")
    core = parts[0] if len(parts[0]) > 2 or len(parts) == 1 else (parts[1] if len(parts) > 1 else parts[0])
    core = core.replace("-", " ")
    for kw in ["marketing", "digital", "agencia", "agencias", "publicidad",
               "diseno", "diseño", "design", "web", "estudio", "media",
               "medios", "branding", "social", "creativa", "creativo",
               "empresa", "total", "hoopla", "seo", "online"]:
        core = re.sub(r"(?i)" + kw, r" \g<0> ", core)
    core = re.sub(r"\s+", " ", core).strip().title()
    return core or domain
_GENERIC_NAMES = {"agencia", "agencia de", "marketing", "marketing digital",
                  "agencia de marketing", "agencia de marketing digital",
                  "coagencia", "coagencia de marketing", "agencia digital",
                  "disenador", "diseñador", "home", "portada", "ar"}
def _pais_de_query(q):
    ql = q.lower()
    if "mexico" in ql or "méxico" in ql:
        return "México"
    if "colombia" in ql:
        return "Colombia"
    if "chile" in ql:
        return "Chile"
    if "peru" in ql or "perú" in ql:
        return "Perú"
    if "cordoba" in ql or "córdoba" in ql:
        return "Córdoba, Argentina"
    if "rosario" in ql:
        return "Rosario, Argentina"
    if "buenos aires" in ql:
        return "Buenos Aires, Argentina"
    return "Argentina"
_EXCLUDED_DOMAINS = ["sortlist", "clutch.co", "facebook.com", "instagram.com", "linkedin.com", "youtube.com"]


def _buscar_multi_motor(q):
    """Prueba Brave primero; si falla o no trae nada, cae a Bing; si Bing
    tampoco trae nada, cae a DuckDuckGo. Cada motor tiene su propio
    rate-limit independiente, así que si uno está bloqueado los otros
    dos suelen seguir funcionando. Nunca inventa resultados: si los tres
    fallan, devuelve lista vacía.

    Devuelve (items, motor) donde cada item es (title, link, snippet).
    """
    try:
        brave = brave_links(q)
    except Exception as e:
        print("  FAIL Brave: %s" % e)
        brave = []
    if brave:
        return [(t, l, "") for t, l in brave], "Brave"

    from services.bing_search import search_bing
    bing = search_bing(q, limit=9)
    if bing:
        return [(r["title"], r["link"], r["snippet"]) for r in bing], "Bing"

    from services.duckduckgo_search import search_duckduckgo
    ddg = search_duckduckgo(q, limit=9)
    if ddg:
        return [(r["title"], r["link"], r["snippet"]) for r in ddg], "DuckDuckGo"

    return [], None


def cazar(limit=2, queries=None):
    import requests
    from urllib.parse import urlparse
    from core.models import Lead, TrackType
    from services.search_service import SearchService
    from services.duckduckgo_search import find_email_on_page
    svc = SearchService()
    leads, seen = [], set()
    qs = queries if queries else QUERIES
    for label, q in qs:
        if len(leads) >= limit:
            break
        print("[BUSCA] " + q)
        results, motor = _buscar_multi_motor(q)
        if not motor:
            print("  -> los 3 motores (Brave/Bing/DuckDuckGo) fallaron o bloquearon, sigo con la próxima query")
            time.sleep(20)
            continue
        print("  -> %d links vía %s" % (len(results), motor))
        for title, link, snippet in results:
            if len(leads) >= limit:
                break
            domain = urlparse(link).netloc.lower()
            if not link or domain in seen or any(x in domain for x in _EXCLUDED_DOMAINS):
                continue
            email = svc._extract_email(title + " " + snippet)
            if not email:
                try:
                    email = find_email_on_page(link, session=requests.Session())
                except Exception:
                    email = None
            if not email:
                continue
            seen.add(domain)
            nombre = _clean_name(title, link)
            pais = _pais_de_query(q)
            lead = Lead(business_name=nombre, email=email.lower(), track=TrackType.MARKETING, industry="Agencia de marketing digital", city=pais, country="", website=link, source=motor)
            if svc.validate_lead(lead):
                leads.append(lead)
                print("  [REAL] %s | %s | %s" % (lead.business_name, lead.email, lead.website))
        time.sleep(20)
    return leads
def main(limit=2, queries=None):
    import argparse, sys as _sys
    if queries is None and len(_sys.argv) > 1:
        ap = argparse.ArgumentParser()
        ap.add_argument("--limit", type=int, default=2)
        a = ap.parse_args()
        limit = a.limit
    from core.sheets_client import SheetsClient
    sheets = SheetsClient()
    existentes = {l.email.strip().lower() for l in sheets.get_all_leads() if l.email and "@" in l.email}
    print("[INFO] En Sheets: %d emails" % len(existentes))
    nuevos = cazar(limit=limit, queries=queries)
    frescos = [l for l in nuevos if l.email.lower() not in existentes]
    print("[INFO] Frescos: %d/%d" % (len(frescos), len(nuevos)))
    with open(PENDING_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Fecha envio", "Negocio/Agencia", "Track (PyME/Marketing)", "Rubro", "Ciudad", "Contacto", "Mail o IG", "Asunto usado", "Respondio (Si/No)", "Resultado", "Enviado?"])
        for l in frescos:
            w.writerow(l.to_sheet_row())
    ok = 0
    for l in frescos:
        if sheets.add_lead(l):
            ok += 1
            print("  [SHEETS] %s <%s>" % (l.business_name, l.email))
        else:
            print("  [FAIL] %s" % l.email)
    print("[OK] Guardados: %d/%d -> https://docs.google.com/spreadsheets/d/%s/edit#gid=%s" % (ok, len(frescos), SHEET_ID, GID))
    return ok > 0
def main_limit(n, queries=None):
    return main(limit=n, queries=queries)
if __name__ == "__main__":
    sys.exit(0 if main() else 1)

