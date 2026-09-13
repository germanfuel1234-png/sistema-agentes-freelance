"""Actualizador de oportunidades freelance -> Google Sheets.
Sheet: 1hjwAUrKaCu53McleYaJZj99b65IoKHBVqIZ96qfvF1I
Destino default: pestana 'oportunidades_freelance' (no pisa leads_tracking.csv).

REGLA ESTRICTA (obligatoria): prohibido buscar/extraer datos de portales de
empleo (Freelancer, Upwork, Workana, Fiverr, Computrabajo, etc.). Solo
posteos ORGANICOS de LinkedIn o X de personas/reclutadores/agencias.
Uso (desde la raiz del repo): python busqueda_linkedin/actualizar_oportunidades_freelance.py --dry-run
"""
import argparse
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED_PATH = os.path.join(ROOT, "credentials.json")
sys.path.insert(0, ROOT)
from config.settings import settings
from core.sheets_client import SheetsClient

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
UA_BOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
SPREADSHEET_ID = "1hjwAUrKaCu53McleYaJZj99b65IoKHBVqIZ96qfvF1I"
DEFAULT_TAB = "oportunidades_freelance"
FOOTPRINTS = ["Estamos buscando talento freelance",
              "creando nuestra red de talento freelance",
              "buscamos perfiles freelance para",
              "busco freelance"]
SKILLS = ["desarrollo web", "diseno web", "SEO tecnico",
          "analisis de sistemas", "Python", "PHP", "Dart", "Kotlin",
          "Backend", "Automatizacion"]
# Frase de contratacion directa ("buscamos desarrollador web"), no solo el
# patron generico de "talento freelance". Se cruza con region, no con SKILLS
# (no tiene sentido "buscamos desarrollador web" + "Kotlin" como frase).
FOOTPRINTS_DEV_WEB = ["buscamos desarrollador web freelance",
                      "necesitamos desarrollador web freelance",
                      "buscamos desarrollador web"]
FOOTPRINTS_EN = ["looking for a freelance web developer",
                 "hiring a freelance web developer",
                 "seeking a freelance web developer"]
REGIONES_ES = ["España", "Madrid", "Barcelona", "Argentina", "México",
               "Colombia", "Chile", "Perú"]
REGIONES_EN = ["United States", "Europe", "remote", "UK"]
FREELANCE_SIGNALS = ["freelance", "freelancer", "por proyecto", "por hora",
                     "remoto", "red de talento", "base de datos",
                     "talent pool", "bolsa de talento"]
DEPENDENCIA_BLOCK = ["relacion de dependencia", "planta permanente",
                     "nomina", "prestaciones de ley"]
SHEET_HEADERS = ["Fecha hallazgo", "Empresa/Agencia", "Fecha publicacion",
                 "Enlace", "Requisitos / Match perfil", "Fuente",
                 "Frase detectada"]
MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}

# REGLA ESTRICTA: portales de empleo prohibidos (nunca buscar ni extraer de aca)
PORTALES_BLOCK = ["freelancer.com", "freelancer.com.ar", "upwork.com", "workana.com",
                  "fiverr.com", "computrabajo", "bumeran.com", "zonajobs.com",
                  "indeed.com", "glassdoor.com", "freelanceargentina.com",
                  "getonbrd.com", "toptal.com", "peopleperhour.com", "guru.com"]
# Solo se aceptan posteos organicos de estas redes
REDES_OK = ("linkedin.com", "x.com", "twitter.com")
# Acortadores oficiales que resuelven a un post real (linkedin.com/posts/...)
ACORTADORES = ("lnkd.in",)


def es_portal(url):
    low = (url or "").lower()
    return any(p in low for p in PORTALES_BLOCK)


def resolver_shortlink(url):
    """Si es un acortador conocido (ej. lnkd.in), sigue el redirect y
    devuelve la URL final real, sin parametros de tracking (?utm_source=...)
    para que el dedup por URL funcione aunque dos personas compartan el
    mismo post con links de tracking distintos. Si no es acortador o
    falla, devuelve la URL tal cual."""
    netloc = urlparse(url or "").netloc.lower()
    if not any(d in netloc for d in ACORTADORES):
        return url
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=10, allow_redirects=True)
        final = r.url or url
        return final.split("?")[0]
    except requests.RequestException:
        return url


def es_red_social(url):
    return any(d in urlparse(url or "").netloc.lower() for d in REDES_OK)

def build_queries():
    qs = []
    for fp in FOOTPRINTS:
        for sk in SKILLS:
            qs.append('site:linkedin.com/posts "%s" "%s"' % (fp, sk))
    for fp in FOOTPRINTS:
        qs.append('site:x.com "%s"' % fp)
        qs.append('"%s" (Python OR PHP OR "desarrollo web" OR SEO)' % fp)
    # "Buscamos desarrollador web" (contratacion directa) por region:
    # España/LatAm en español, EEUU/Europa/remoto en ingles.
    for fp in FOOTPRINTS_DEV_WEB:
        for region in REGIONES_ES:
            qs.append('site:linkedin.com/posts "%s" "%s"' % (fp, region))
    for fp in FOOTPRINTS_EN:
        for region in REGIONES_EN:
            qs.append('site:linkedin.com/posts "%s" "%s"' % (fp, region))
    return qs

QUERIES = build_queries()

def _clean(t, lim=500):
    return " ".join((t or "").split())[:lim]

def search_google_cse(q, key, cx, days):
    r = requests.get("https://www.googleapis.com/customsearch/v1", params={"q": q, "key": key, "cx": cx, "num": 10, "dateRestrict": "d%d" % days}, timeout=25)
    r.raise_for_status()
    return [{"link": i.get("link", ""), "title": i.get("title", ""), "snippet": i.get("snippet", ""), "source": "Google"} for i in r.json().get("items", [])]

def _ddg_url(h):
    if "duckduckgo.com/l/" in h:
        qq = parse_qs(urlparse(h).query)
        if "uddg" in qq:
            return unquote(qq["uddg"][0])
    return h

def search_ddg(q):
    for ep in ("https://html.duckduckgo.com/html/", "https://lite.duckduckgo.com/lite/"):
        try:
            r = requests.get(ep, params={"q": q}, headers={"User-Agent": UA}, timeout=20)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            ancs = soup.select("a.result__a") or soup.select('a[rel="nofollow"]')
            out = []
            for a in ancs:
                href = _ddg_url(a.get("href", ""))
                if href.startswith("/") or "duckduckgo.com" in href:
                    continue
                par = a.find_parent("div") or a.parent
                sn = par.get_text(" ", strip=True) if par else ""
                out.append({"link": href, "title": a.get_text(strip=True), "snippet": sn[:500], "source": "DuckDuckGo"})
            if out:
                return out
        except Exception:
            continue
    return []

def search_bing(q):
    try:
        r = requests.get("https://www.bing.com/search", params={"q": q}, headers={"User-Agent": UA}, timeout=20)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        out = []
        for li in soup.select("li.b_algo"):
            a = li.select_one("h2 a")
            if not a:
                continue
            p = li.select_one("p")
            txt = p.get_text(" ", strip=True) if p else ""
            out.append({"link": a.get("href", ""), "title": a.get_text(strip=True), "snippet": txt[:500], "source": "Bing"})
        return out
    except Exception:
        return []
def parse_fecha(text):
    low = (text or "").lower()
    m = re.search(r"hace\s+(\d+)\s*(h|hora?s?|d|dias?|semana?s?|mes(?:es)?)", low)
    if m:
        n, u = int(m.group(1)), m.group(2)
        if u.startswith("h"):
            return "hace %d h" % n, 0
        if u.startswith("d"):
            return "hace %d d" % n, n
        if u.startswith("sem"):
            return "hace %d sem" % n, n * 7
        return "hace %d mes" % n, n * 30
    m = re.search(r"(\d+)\s+(days?|hours?|weeks?)\s+ago", low)
    if m:
        n, u = int(m.group(1)), m.group(2)
        for k, v in (("hour", 0), ("day", 1), ("week", 7)):
            if u.startswith(k):
                return "hace %d %s" % (n, k), n * v
    m = re.search(r"(\d{1,2})\s+de\s+([a-z]+)\s+(?:de\s+)?(20\d{2})", low)
    if m and MESES.get(m.group(2)):
        try:
            d = datetime(int(m.group(3)), MESES[m.group(2)], int(m.group(1)))
            return d.strftime("%d/%m/%Y"), max((datetime.now() - d).days, 0)
        except Exception:
            return m.group(0), None
    m = re.search(r"(20\d{2})-(\d{2})-(\d{2})", text or "")
    if m:
        try:
            d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return d.strftime("%d/%m/%Y"), max((datetime.now() - d).days, 0)
        except Exception:
            pass
    return "", None

def footprint_de(text):
    low = (text or "").lower()
    for fp in FOOTPRINTS:
        if fp.lower() in low:
            return fp
    return ""

def es_freelance(text):
    low = (text or "").lower()
    if any(b in low for b in DEPENDENCIA_BLOCK) and "freelance" not in low:
        return False
    return any(s in low for s in FREELANCE_SIGNALS)

def match_skills(text):
    low = (text or "").lower()
    f = [s for s in SKILLS if s.lower() in low]
    return f

def autor_de(url, title=""):
    m = re.search(r"/posts/([^/]+)", urlparse(url).path)
    if m:
        slug = re.sub(r"-\d+[A-Za-z_]*$", "", m.group(1).split("_")[0])
        return slug.replace("-", " ").strip()[:80]
    m = re.search(r"(?:x\.com|twitter\.com)/([^/?#]+)/status", url)
    if m:
        return "@" + m.group(1)
    if title and "linkedin" not in title.lower():
        return title[:80]
    return urlparse(url).netloc.replace("www.", "")

def enrich(url, snippet):
    autor = autor_de(url)
    fl, dd = parse_fecha(snippet)
    if autor and fl:
        return autor, fl, dd
    try:
        r = requests.get(url, headers={"User-Agent": UA_BOT, "Accept-Language": "es-AR,es;q=0.9"}, timeout=10)
        if r.status_code == 200 and "authwall" not in r.text.lower():
            m = re.search(r'property="og:title" content="([^"]+)"', r.text)
            if m and (not autor or "." in autor):
                autor = m.group(1).replace(" | LinkedIn", "").strip()[:80]
            m = re.search(r'property="article:published_time" content="([^"]+)"', r.text)
            if m:
                try:
                    d = datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
                    fl = d.strftime("%d/%m/%Y")
                    dd = max((datetime.now() - d.replace(tzinfo=None)).days, 0)
                except Exception:
                    pass
            if not fl:
                fl, dd = parse_fecha(r.text[:6000])
    except Exception:
        pass
    return autor, fl, dd

def collect(queries, key=None, cx=None, days=30, do_enrich=False, limit=50):
    found, seen = [], set()
    for i, q in enumerate(queries):
        if i > 0:
            # Pausa entre queries: sin esto se martilla Bing/DuckDuckGo sin
            # parar (24+ combinaciones frase x skill), arriesgando el rate
            # limit compartido con el resto del sistema (loop_caza.py, etc.)
            time.sleep(4)
        print("buscando: %s" % q[:110])
        items = []
        if key and cx:
            try:
                items = search_google_cse(q, key, cx, days)
            except Exception as e:
                print("  Google CSE fallo (%s); fallback." % e)
        if not items:
            items = search_ddg(q)
        if not items:
            items = search_bing(q)
        for it in items:
            link = (it.get("link") or "").strip()
            if not link.startswith("http") or link in seen:
                continue
            if es_portal(link):
                print("  REGLA ESTRICTA - descartado portal de empleo: %s" % link[:80])
                continue
            if not es_red_social(link):
                print("  descartado (solo LinkedIn/X): %s" % link[:80])
                continue
            blob = "%s %s" % (it.get("title", ""), it.get("snippet", ""))
            if not es_freelance(blob + " " + q):
                continue
            sk = match_skills(blob)
            low = blob.lower()
            if not sk and not any(k in low for k in ("web", "seo", "python", "php", "dart", "kotlin", "sistema")):
                continue
            seen.add(link)
            if do_enrich:
                autor, fl, dd = enrich(link, it.get("snippet", ""))
            else:
                autor = autor_de(link, it.get("title", ""))
                fl, dd = parse_fecha(it.get("snippet", ""))
            if dd is not None and dd > days:
                print("  vieja (%s): %s" % (fl, link[:90]))
                continue
            req = _clean(it.get("snippet") or it.get("title"))
            found.append({"link": link, "empresa": autor, "fecha": fl, "req": req, "fuente": it.get("source", ""), "frase": footprint_de(blob) or "ver post", "skills": sk})
            if len(found) >= limit:
                return found
        if len(found) >= limit:
            break
    return found

SEP_LANGS = {"es", "pt", "fr", "de", "it", "nl", "ru", "pl", "tr", "sv",
             "da", "fi", "ro", "ca", "gl", "eu", "cs", "hu", "id", "vi"}


def _sep_formula(sheets):
    """Separador de argumentos de formulas segun la locale del spreadsheet.
    Locale es_AR detectada -> ';'. Locales en_US -> ','."""
    try:
        props = sheets.service.spreadsheets().get(
            spreadsheetId=sheets.sheet_id, fields="properties.locale").execute()
        lang = props.get("properties", {}).get("locale", "es_AR").split("_")[0].lower()
    except Exception:
        lang = "es"
    return ";" if lang in SEP_LANGS else ","


def _link_formula(url, sep):
    """Columna Enlace como formula HYPERLINK clickeable."""
    if "linkedin.com" in url:
        label = "Ver post LinkedIn"
    elif "x.com" in url or "twitter.com" in url:
        label = "Ver post X"
    else:
        label = "Ver publicacion"
    return '=HYPERLINK("%s"%s"%s")' % (url, sep, label)


def _url_sin_tracking(url):
    """Saca ?utm_source=... y similares para que dos links del mismo post
    (compartidos por gente distinta) se reconozcan como iguales."""
    return (url or "").split("?")[0]


def _extraer_url(celda):
    """Recupera la URL de una celda Enlace (texto plano o formula HYPERLINK)."""
    c = (celda or "").strip()
    if c.startswith("=HYPERLINK"):
        m = re.search(r'=HYPERLINK\("([^"]+)"', c)
        return _url_sin_tracking(m.group(1)) if m else ""
    return _url_sin_tracking(c) if c.startswith("http") else ""


def guardar(results, tab, sheets):
    sheets.add_sheet(tab, headers=SHEET_HEADERS)
    sheets.write_range("'%s'!A1:G1" % tab, [SHEET_HEADERS], append=False)
    # Dedup leyendo FORMULA: las celdas Enlace son =HYPERLINK("url";"label")
    # y con render default devolverian el label, rompiendo el dedup.
    ex = sheets.service.spreadsheets().values().get(
        spreadsheetId=sheets.sheet_id, range="'%s'!A1:G10000" % tab,
        valueRenderOption="FORMULA").execute().get("values", [])
    urls = {_extraer_url(r[3]) for r in ex if len(r) > 3}
    urls.discard("")
    sep = _sep_formula(sheets)
    nuevos = []
    for r in results:
        link_clave = _url_sin_tracking(r["link"])
        if link_clave in urls:
            continue
        urls.add(link_clave)
        req = r["req"]
        tag = ", ".join(r.get("skills") or [])
        if tag and tag.lower() not in req.lower():
            req = ("[%s] %s" % (tag, req))[:500]
        nuevos.append([datetime.now().strftime("%d/%m/%Y %H:%M"), r.get("empresa", ""), r.get("fecha", ""), _link_formula(r["link"], sep), req, r.get("fuente", ""), r.get("frase", "")])
    base = max(len(ex) - 1, 0)
    if nuevos:
        # USER_ENTERED para que Sheets parsee la formula (RAW la dejaria como texto)
        sheets.service.spreadsheets().values().append(
            spreadsheetId=sheets.sheet_id, range="'%s'!A2" % tab,
            valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS",
            body={"values": nuevos}).execute()
    return nuevos, base
def main():
    p = argparse.ArgumentParser(description="Actualiza Sheets con oportunidades freelance.")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--tab", default=DEFAULT_TAB)
    p.add_argument("--query")
    p.add_argument("--enrich", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--manual", action="store_true")
    p.add_argument("--add", nargs="+", metavar="URL")
    p.add_argument("--empresa", default="")
    a = p.parse_args()
    print("=" * 78)
    print("ACTUALIZADOR FREELANCE -> %s | tab '%s' | <= %d dias" % (SPREADSHEET_ID, a.tab, a.days))
    print("=" * 78)
    if a.manual:
        print("\n== PASO 1: LinkedIn LOGUEADO (los /posts/ NO estan indexados por Google/Bing) ==")
        for i, fp in enumerate(FOOTPRINTS, 1):
            kw = "%22" + fp.replace(" ", "%20") + "%22%20(%22desarrollo%20web%22%20OR%20SEO%20OR%20Python%20OR%20PHP%20OR%20Dart%20OR%20Kotlin)"
            print("%d. https://www.linkedin.com/search/results/content/?keywords=%s" % (i, kw))
        print("   Dentro de LinkedIn: filtro Fecha = 'Ultima semana'.")
        print("\n== PASO 2: X (Twitter), busqueda en vivo ==")
        for i, fp in enumerate(FOOTPRINTS, 1):
            print("%d. https://x.com/search?q=%s+%%28%%22desarrollo+web%%22+OR+SEO+OR+Python+OR+PHP%%29&f=live" % (i, fp.replace(" ", "+")))
        print("   En X: 'Advanced search' > fecha desde hace 7 dias.")
        print("\n== PASO 3 ==")
        print("python busqueda_linkedin/linkedin_manual_busqueda.py   (asistente interactivo)")
        print("o directo: python busqueda_linkedin/actualizar_oportunidades_freelance.py --add URL1 URL2 ...")
        return 0
    if a.add:
        items, rechazadas = [], []
        for u in a.add:
            u = u.strip()
            if not u.startswith("http"):
                continue
            u = resolver_shortlink(u)
            if es_portal(u):
                rechazadas.append(u)
                print("REGLA ESTRICTA - portal de empleo prohibido, NO se agrega: %s" % u)
                continue
            if not es_red_social(u):
                rechazadas.append(u)
                print("Solo LinkedIn/X organicos, NO se agrega: %s" % u)
                continue
            items.append({"link": u, "empresa": a.empresa or autor_de(u), "fecha": "", "req": "Pegado a mano: revisar match web/SEO/Python/PHP/Dart/Kotlin.", "fuente": "manual", "frase": "", "skills": []})
        if not items:
            print("Sin URLs validas." + (" (%d rechazadas por regla estricta)" % len(rechazadas) if rechazadas else ""))
            return 1
        if a.dry_run:
            for r in items:
                print("  %s | %s" % (r["empresa"], r["link"]))
            return 0
        nuevos, base = guardar(items, a.tab, SheetsClient(CRED_PATH))
        print("%d guardados | %d ya existian en '%s'" % (len(nuevos), base, a.tab))
        return 0
    key = settings.google_custom_search_api_key
    cx = settings.google_custom_search_engine_id
    if key and cx:
        print("Motor: Google CSE (dateRestrict=d%d)" % a.days)
    else:
        print("Sin keys CSE -> Bing/DDG best-effort. Para fecha exacta configura GOOGLE_CUSTOM_SEARCH_API_KEY/ENGINE_ID en .env")
    res = collect([a.query] if a.query else QUERIES, key if key and cx else None, cx if key and cx else None, days=a.days, do_enrich=a.enrich, limit=a.limit)
    print("-" * 78)
    if not res:
        print("Sin hallazgos freelance (<= %d dias). Proba --manual." % a.days)
        return 1
    print("%d hallazgos:" % len(res))
    for i, r in enumerate(res, 1):
        print("\n%d. %s | %s\n   %s\n   %s" % (i, r["empresa"], r["fecha"] or "fecha a confirmar", r["link"], r["req"][:200]))
    if a.dry_run:
        print("\n[dry-run] Nada escrito.")
        return 0
    nuevos, base = guardar(res, a.tab, SheetsClient(CRED_PATH))
    print("\n%d filas nuevas | %d ya existentes en '%s'" % (len(nuevos), base, a.tab))
    print("Ver: https://docs.google.com/spreadsheets/d/%s" % SPREADSHEET_ID)
    return 0

if __name__ == "__main__":
    sys.exit(main())



