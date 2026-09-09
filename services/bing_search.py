"""
Búsqueda web gratuita vía Bing HTML (sin API key, sin cuenta de
facturación). Tercer motor además de DuckDuckGo y Brave: si uno de los
tres está bloqueado, los otros siguen funcionando (cada uno tiene su
propio límite de rate-limit, independiente).
"""
import base64
import logging
from typing import List, Optional, TypedDict
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}


class BingResult(TypedDict):
    title: str
    link: str
    snippet: str


def _decode_bing_url(bing_url: str) -> str:
    """Bing envuelve el link real en /ck/a?...&u=a1<base64>&... en vez de
    linkear directo. Decodifica ese parámetro para obtener la URL real del
    sitio (si no puede, devuelve la URL de Bing tal cual)."""
    try:
        params = parse_qs(urlparse(bing_url).query)
        u = params.get("u", [""])[0]
        if not u:
            return bing_url
        payload = u[2:]  # Bing antepone 2 caracteres (ej. "a1") al base64 real
        payload += "=" * (-len(payload) % 4)
        decoded = base64.b64decode(payload).decode("utf-8", errors="ignore")
        return decoded if decoded.startswith("http") else bing_url
    except Exception:
        return bing_url


def search_bing(query: str, limit: int = 10, session: requests.Session = None) -> List[BingResult]:
    """Busca en Bing (HTML) y devuelve título/link real/snippet por resultado.

    No lanza excepción: si falla o Bing bloquea, loguea y devuelve lista
    vacía, para que el llamador pueda decidir sin try/except propio.
    """
    sess = session or requests
    try:
        resp = sess.get(
            "https://www.bing.com/search",
            params={"q": query},
            headers=_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"⚠️  Bing no respondió para '{query}': {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results: List[BingResult] = []

    for item in soup.select("li.b_algo"):
        title_el = item.select_one("h2 a")
        if not title_el:
            continue
        raw_link = title_el.get("href", "")
        if not raw_link:
            continue
        link = _decode_bing_url(raw_link)
        snippet_el = item.select_one(".b_caption p") or item.select_one("p")
        results.append({
            "title": title_el.get_text(strip=True),
            "link": link,
            "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
        })
        if len(results) >= limit:
            break

    logger.info(f"🔎 Bing: {len(results)} resultados para '{query}'")
    return results
