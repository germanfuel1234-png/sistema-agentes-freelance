"""
Búsqueda web gratuita vía Yahoo Search HTML (sin API key, sin cuenta de
facturación). Cuarto motor de respaldo, además de Brave/Bing/DuckDuckGo.

Probado en vivo (05/09/2026): cuando responde, trae resultados orgánicos
reales sin CAPTCHA (requiere mandar Accept y Accept-Language además del
User-Agent, si no Yahoo devuelve 500 directamente). PERO es inconsistente:
en ráfagas de pruebas solo respondió ~40-60% de las veces, el resto tira
un 500 "INKApi Error" (no es rate-limit clásico con 429, es un error de
su backend). Por eso va DESPUÉS de DuckDuckGo en la cadena de fallback,
nunca antes: cuando falla no cuesta nada (devuelve lista vacía como los
demás), pero no es confiable como motor principal.
"""
import logging
import re
import urllib.parse
from typing import List, TypedDict

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9",
}

_RU_PATTERN = re.compile(r"RU=([^/]+)/R[KO]")


class YahooResult(TypedDict):
    title: str
    link: str
    snippet: str


def _decode_yahoo_url(yahoo_url: str) -> str:
    """Yahoo envuelve el link real en r.search.yahoo.com/.../RU=<url-encoded>/RK=...
    en vez de linkear directo. Decodifica ese parámetro para obtener la URL
    real del sitio (si no puede, devuelve la URL de Yahoo tal cual)."""
    m = _RU_PATTERN.search(yahoo_url)
    if not m:
        return yahoo_url
    try:
        decoded = urllib.parse.unquote(m.group(1))
        return decoded if decoded.startswith("http") else yahoo_url
    except Exception:
        return yahoo_url


def search_yahoo(query: str, limit: int = 10, session: requests.Session = None) -> List[YahooResult]:
    """Busca en Yahoo Search (HTML) y devuelve título/link real/snippet por
    resultado.

    No lanza excepción: si falla o Yahoo bloquea, loguea y devuelve lista
    vacía, para que el llamador pueda decidir sin try/except propio.
    """
    sess = session or requests
    try:
        resp = sess.get(
            "https://search.yahoo.com/search",
            params={"p": query},
            headers=_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"⚠️  Yahoo no respondió para '{query}': {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results: List[YahooResult] = []

    for item in soup.select("div.algo-sr"):
        link_el = item.select_one(".compTitle a")
        title_el = item.select_one(".compTitle h3")
        if not link_el or not title_el:
            continue
        raw_link = link_el.get("href", "")
        if not raw_link:
            continue
        link = _decode_yahoo_url(raw_link)
        if "yahoo.com" in link:
            continue  # links propios de Yahoo (noticias, finance, etc.), no un sitio real
        snippet_el = item.select_one(".compText")
        results.append({
            "title": title_el.get_text(strip=True),
            "link": link,
            "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
        })
        if len(results) >= limit:
            break

    logger.info(f"🟪 Yahoo: {len(results)} resultados para '{query}'")
    return results
