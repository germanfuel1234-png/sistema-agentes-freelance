"""Caza empresas REALES que buscan desarrollador web/freelance vía Indeed.

Estrategia distinta a cazar_brave.py: en vez de buscar "agencia de
marketing", busca ofertas de empleo reales para developer. Una empresa
publicando esa búsqueda tiene presupuesto y necesidad confirmados - mejor
señal que una agencia genérica.

Importante (por diseño, a pedido): usa Indeed como buscador, NO Brave/Bing/
DuckDuckGo - así no compite por la misma cuota que cazar_brave.py. Para
encontrar el email de cada empresa tampoco vuelve a buscar en un motor:
adivina el dominio propio a partir del nombre (empresa.com.ar, empresa.com,
etc.) con pedidos HTTP directos, y recién ahí visita esa página real para
sacar el email de contacto (mismo find_email_on_page que ya usa el resto
del sistema).

Uso: venv312/bin/python3 cazar_indeed.py --limit 10
"""
import argparse
import csv
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import requests
from bs4 import BeautifulSoup

from core.models import Lead, TrackType
from core.sheets_client import SheetsClient
from services.duckduckgo_search import find_email_on_page

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# (etiqueta, query, ciudad, dominio de Indeed a usar)
QUERIES = [
    ("Desarrollador web Buenos Aires", "desarrollador web", "Buenos Aires", "ar.indeed.com"),
    ("Programador freelance Argentina", "programador freelance", "Argentina", "ar.indeed.com"),
    ("Desarrollador web freelance Argentina", "desarrollador web freelance", "Argentina", "ar.indeed.com"),
    ("Desarrollador web Madrid", "desarrollador web", "Madrid", "es.indeed.com"),
    ("Desarrollador web freelance España", "desarrollador web freelance", "España", "es.indeed.com"),
    ("Desarrollador web Ciudad de México", "desarrollador web", "Ciudad de México", "mx.indeed.com"),
    ("Desarrollador web Guadalajara", "desarrollador web", "Guadalajara", "mx.indeed.com"),
    ("Desarrollador web Bogotá", "desarrollador web", "Bogotá", "co.indeed.com"),
    ("Desarrollador web freelance Colombia", "desarrollador web freelance", "Colombia", "co.indeed.com"),
    ("Desarrollador web Santiago", "desarrollador web", "Santiago", "cl.indeed.com"),
    ("Desarrollador web freelance Chile", "desarrollador web freelance", "Chile", "cl.indeed.com"),
    ("Desarrollador web Lima", "desarrollador web", "Lima", "pe.indeed.com"),
    ("Desarrollador web Caracas", "desarrollador web", "Caracas", "ve.indeed.com"),
    ("Desarrollador web Panamá", "desarrollador web", "Panamá", "pa.indeed.com"),
]

# Nombres genericos que a veces aparecen y no son una empresa real contactable
_EXCLUIR_EMPRESA = {"confidencial", "empresa confidencial"}

_PATRON_EMPRESA = re.compile(r"Ver todos los\s+Empleos de\s+(.+?)\s+-\s+empleo en\s+(.+?)\s+-")

# Sufijos societarios que rara vez estan en el dominio (Tecnoap SA -> tecnoap.com)
_SUFIJOS_SOCIETARIOS = ("sa", "srl", "sl", "inc", "llc", "group", "grupo", "ltda", "corp")


def buscar_ofertas(query, ciudad, dominio_indeed, limit=15):
    """Busca ofertas de empleo reales en Indeed (sin login, sin captcha) y
    devuelve [(empresa, ciudad)] unicos. Si Indeed falla o bloquea, devuelve
    lista vacia - nunca inventa una empresa."""
    headers = {"User-Agent": UA}
    try:
        r = requests.get(f"https://{dominio_indeed}/jobs", params={"q": query, "l": ciudad},
                          headers=headers, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  [WARN] Indeed no respondió para '{query}': {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text(" ")
    empresas, seen = [], set()
    for m in _PATRON_EMPRESA.finditer(text):
        empresa = re.sub(r"\s+", " ", m.group(1)).strip()
        ciudad_real = re.sub(r"\s+", " ", m.group(2)).strip()
        key = empresa.lower()
        if key in seen or key in _EXCLUIR_EMPRESA:
            continue
        seen.add(key)
        empresas.append((empresa, ciudad_real))
        if len(empresas) >= limit:
            break
    return empresas


# TLDs esperados segun el pais de Indeed que se consultó. Importante: NO se
# prueban TLDs de otros países (ej. no se intenta .com.ar para una oferta de
# México) - eso fue justo lo que causó un falso positivo real ("Grupo
# Salinas" de Argentina aceptado para una oferta en Ciudad de México).
_TLDS_POR_INDEED = {
    "ar.indeed.com": ["com.ar"],
    "es.indeed.com": ["es"],
    "mx.indeed.com": ["com.mx", "mx"],
    "co.indeed.com": ["com.co"],
    "cl.indeed.com": ["cl"],
    "pe.indeed.com": ["com.pe"],
    "ve.indeed.com": ["com.ve"],
    "pa.indeed.com": ["com.pa"],
}


def _candidatos_dominio(empresa, dominio_indeed):
    """Genera candidatos de dominio propio a partir del nombre de la
    empresa - sin usar ningun buscador, solo pedidos HTTP directos. Prueba
    primero el/los TLD del país de la oferta, y ".com" genérico como
    último respaldo (muchas empresas lo usan sin importar el país)."""
    base = re.sub(r"[^a-z0-9]", "", empresa.lower())
    for suf in _SUFIJOS_SOCIETARIOS:
        if base.endswith(suf) and len(base) > len(suf) + 2:
            base = base[: -len(suf)]
            break
    if not base:
        return []
    tlds = _TLDS_POR_INDEED.get(dominio_indeed, [])
    candidatos = [f"https://{base}.{tld}" for tld in tlds]
    candidatos += [f"https://www.{base}.{tld}" for tld in tlds]
    candidatos += [f"https://{base}.com", f"https://www.{base}.com"]
    return candidatos


# Señales de que la URL "adivinada" NO es el sitio real de la empresa
# (dominio parkeado/en venta, o pagina de challenge/bloqueo tipo Cloudflare)
_SITIO_INVALIDO = [
    "domain for sale", "this domain is for sale", "buy this domain",
    "dominio en venta", "is parked", "just a moment", "attention required",
    "checking your browser", "acceso denegado", "access denied",
]


def _dominio_base(url):
    from urllib.parse import urlparse
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def encontrar_sitio_y_email(empresa, dominio_indeed, session):
    """Adivina el dominio propio de la empresa (sin buscador) y, si
    responde con contenido real (no un dominio parkeado/challenge, y sin
    redirigir a un sitio totalmente distinto), busca el email de contacto
    en esa misma página. No inventa nada: si ningún candidato resuelve,
    devuelve (None, None)."""
    for url in _candidatos_dominio(empresa, dominio_indeed):
        try:
            r = session.get(url, headers={"User-Agent": UA}, timeout=6, allow_redirects=True)
            if r.status_code >= 400 or len(r.text) < 200:
                continue
            # Si redirige a un dominio totalmente distinto al que pedimos
            # (ej. besit.com -> atom.com/name/Besit), no es el sitio real.
            if _dominio_base(r.url) != _dominio_base(url):
                continue
            if any(s in r.text.lower() for s in _SITIO_INVALIDO):
                continue
        except requests.RequestException:
            continue
        email = find_email_on_page(url, session=session)
        if email:
            return url, email
    return None, None


def cazar(limit=10, queries=None):
    session = requests.Session()
    leads = []
    seen_empresas = set()
    for label, query, ciudad, dominio_indeed in (queries or QUERIES):
        if len(leads) >= limit:
            break
        print(f"[BUSCA-INDEED] {query} en {ciudad}")
        ofertas = buscar_ofertas(query, ciudad, dominio_indeed, limit=15)
        print(f"  -> {len(ofertas)} ofertas reales")
        for empresa, ciudad_real in ofertas:
            if len(leads) >= limit:
                break
            key = empresa.lower()
            if key in seen_empresas:
                continue
            seen_empresas.add(key)
            website, email = encontrar_sitio_y_email(empresa, dominio_indeed, session)
            if not email:
                print(f"  [SIN SITIO/EMAIL] {empresa}")
                continue
            lead = Lead(
                business_name=empresa,
                email=email.lower(),
                track=TrackType.PYME,
                industry="Busca desarrollador web (oferta de empleo real)",
                city=ciudad_real,
                country="",
                website=website,
                source="Indeed",
            )
            leads.append(lead)
            print(f"  [REAL] {empresa} | {email} | {website}")
        time.sleep(3)
    return leads


def main(limit=10, queries=None):
    sheets = SheetsClient()
    existentes = {l.email.strip().lower() for l in sheets.get_all_leads() if l.email and "@" in l.email}
    print(f"[INFO] En Sheets: {len(existentes)} emails")
    nuevos = cazar(limit=limit, queries=queries)
    frescos = [l for l in nuevos if l.email.lower() not in existentes]
    print(f"[INFO] Frescos: {len(frescos)}/{len(nuevos)}")
    ok = 0
    for l in frescos:
        if sheets.add_lead(l):
            ok += 1
            print(f"  [SHEETS] {l.business_name} <{l.email}>")
    print(f"[OK] Guardados: {ok}/{len(frescos)}")
    return ok > 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    a = ap.parse_args()
    sys.exit(0 if main(limit=a.limit) else 1)
