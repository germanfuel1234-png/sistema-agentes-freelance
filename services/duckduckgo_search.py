"""
Búsqueda web gratuita vía DuckDuckGo HTML (sin API key, sin cuenta de
facturación). Se usa como motor por defecto cuando no hay Google Custom
Search configurado, y como respaldo si Google falla (cuota, facturación,
etc.).

DuckDuckGo no ofrece una API pública gratuita "oficial", pero su versión
HTML (html.duckduckgo.com/html/) no requiere key y es estable para este
uso (volumen bajo, unas pocas búsquedas por corrida del agente).
"""
import logging
import re
from typing import List, Optional, TypedDict

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

_EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

# Direcciones de ejemplo/placeholder que aparecen en formularios de contacto
# (atributos placeholder=, texto de ayuda, etc.) y que NO son emails reales.
_PLACEHOLDER_EMAILS = {
    "tu@email.com", "your@email.com", "email@example.com", "ejemplo@ejemplo.com",
    "nombre@dominio.com", "test@test.com", "info@example.com", "correo@ejemplo.com",
    "name@example.com", "usuario@dominio.com", "example@example.com",
}

_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")


class DuckDuckGoResult(TypedDict):
    title: str
    link: str
    snippet: str


def search_duckduckgo(query: str, limit: int = 10, session: requests.Session = None) -> List[DuckDuckGoResult]:
    """Busca en DuckDuckGo (HTML) y devuelve título/link/snippet por resultado.

    No lanza excepción: si falla, loguea y devuelve lista vacía, para que
    el llamador pueda decidir sin necesidad de try/except propio.
    """
    sess = session or requests
    try:
        resp = sess.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers=_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"⚠️  DuckDuckGo no respondió para '{query}': {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results: List[DuckDuckGoResult] = []

    for result in soup.select(".result"):
        title_el = result.select_one(".result__a")
        if not title_el:
            continue
        link = title_el.get("href", "")
        # Salta anuncios (redirect de tracking de DDG, no es un sitio real)
        if not link or "duckduckgo.com/y.js" in link:
            continue
        snippet_el = result.select_one(".result__snippet")
        results.append({
            "title": title_el.get_text(strip=True),
            "link": link,
            "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
        })
        if len(results) >= limit:
            break

    logger.info(f"🦆 DuckDuckGo: {len(results)} resultados para '{query}'")
    return results


def find_email_on_page(url: str, session: requests.Session = None, timeout: int = 8) -> Optional[str]:
    """Visita una página real y busca un email de contacto genuino.

    Prioriza enlaces mailto: (más confiables) y recién si no hay ninguno cae
    a un regex sobre el texto VISIBLE de la página (nunca sobre atributos
    como placeholder=, que suelen traer direcciones de ejemplo tipo
    "tu@email.com" en vez de un contacto real).

    Devuelve None si no encuentra nada o si la petición falla; nunca
    inventa un email.
    """
    if not url:
        return None

    sess = session or requests
    try:
        resp = sess.get(url, headers=_HEADERS, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.debug(f"No se pudo visitar {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    for a in soup.select("a[href^=mailto]"):
        candidate = a.get("href", "")[len("mailto:"):].split("?")[0].strip().lower()
        if candidate and candidate not in _PLACEHOLDER_EMAILS and not candidate.endswith(_IMAGE_EXTENSIONS):
            return candidate

    visible_text = soup.get_text(" ")
    for match in _EMAIL_PATTERN.findall(visible_text):
        candidate = match.lower()
        if candidate not in _PLACEHOLDER_EMAILS and not candidate.endswith(_IMAGE_EXTENSIONS):
            return candidate

    return None
