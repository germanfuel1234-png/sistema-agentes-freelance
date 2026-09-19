"""
Busca publicaciones (posts) en LinkedIn de las últimas 24hs que mencionen
las keywords de búsqueda y que parezcan una oferta real de trabajo
freelance/remoto (no solo alguien hablando del tema). Guarda los
matches en la Sheet y avisa a n8n (que manda el WhatsApp) cuando hay
matches nuevos.

Requiere haber corrido linkedin_login_setup.py una vez antes (guarda la
sesión logueada en linkedin_session.json - este script nunca loguea con
usuario/contraseña, solo reusa esa sesión).

IMPORTANTE - riesgo real: automatizar LinkedIn viola sus Términos de
Servicio y puede terminar en un bloqueo/verificación de la cuenta. Por
eso este script:
  - NUNCA intenta resolver un checkpoint/verificación de seguridad - si
    aparece uno, aborta ese ciclo entero y avisa (no reintenta solo).
  - Va lento a propósito: pausas largas entre keywords, y por default un
    ciclo completo cada 60 min (no una búsqueda continua).
  - Reusa la MISMA sesión ya logueada en vez de loguearse de nuevo cada
    vez (los logins repetidos son lo que más dispara las alertas).

Uso:
    python buscar_postulaciones_linkedin.py --una-vez
    python buscar_postulaciones_linkedin.py --intervalo 60
"""
import argparse
import os
import random
import re
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from core.heartbeat import reportar_heartbeat
from core.sheets_client import SheetsClient

SESSION_FILE = os.path.join(os.path.dirname(__file__), "linkedin_session.json")
STOP_FILE = os.path.join(os.path.dirname(__file__), "STOP_linkedin.loop")

TAB = "postulaciones_linkedin"
HEADERS = ["Fecha hallazgo", "Autor", "Contenido", "Link", "Palabra clave"]

KEYWORDS = ["Web Developer", "programación", "python", "desarrollador web"]

# Frases que indican que el posteo busca CANDIDATOS (no solo menciona el
# tema) - se exige al menos una de estas.
_SEÑALES_BUSQUEDA = [
    "buscamos", "estamos buscando", "necesitamos", "se busca", "buscando",
    "contratando", "vacante", "sumate", "se necesita", "buscar talento",
    "join our team", "we're hiring", "we are hiring", "hiring", "now hiring",
    "looking for", "open position", "open role", "apply now", "send your cv",
    "send your resume", "postulate", "postúlate", "enviar cv",
]

# Señales de que es freelance/remoto (se exige al menos una).
_SEÑALES_FREELANCE_REMOTO = [
    "freelance", "freelancer", "remoto", "remote", "home office",
    "trabajo remoto", "100% remoto", "full remote", "contract", "part-time",
]

# n8n dispara el WhatsApp cuando le pega este webhook (ver
# PLAN_MIGRACION_HOSTINGER_N8N.md para cómo armarlo en el editor de n8n,
# mismo patrón que "generar-presupuesto").
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_LINKEDIN", "http://localhost:5678/webhook/nueva-postulacion-linkedin")


def _es_oferta_de_trabajo(texto: str) -> bool:
    t = texto.lower()
    tiene_busqueda = any(s in t for s in _SEÑALES_BUSQUEDA)
    tiene_freelance_remoto = any(s in t for s in _SEÑALES_FREELANCE_REMOTO)
    return tiene_busqueda and tiene_freelance_remoto


def _hay_checkpoint(page) -> bool:
    """Detecta la pantalla de verificación de seguridad de LinkedIn - si
    aparece, hay que parar YA, nunca intentar resolverla."""
    url = page.url.lower()
    if "checkpoint" in url or "challenge" in url:
        return True
    try:
        texto = page.content().lower()
        return "let's do a quick security check" in texto or "verify it's you" in texto
    except Exception:
        return False


def _extraer_autor(texto: str) -> str:
    """La primera línea del bloque es un label genérico ("Publicación en
    el feed") en esta versión de la UI de LinkedIn - el autor es la
    primera línea real después de eso."""
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    if lineas and lineas[0].lower().startswith(("publicaci", "post in")):
        lineas = lineas[1:]
    return lineas[0] if lineas else "?"


def _obtener_link_post(page, item) -> str:
    """LinkedIn ya no deja un <a href> directo al post en el HTML de
    resultados (UI nueva, "SDUI", con clases ofuscadas que cambian solas) -
    el único lugar donde da un permalink real es el menú "..." de la
    publicación -> "Copiar enlace a la publicación", que lo deja en el
    portapapeles. Por eso hace falta requestear permisos de clipboard al
    crear el browser context."""
    try:
        boton_menu = item.locator(
            'button[aria-label*="menú de controles" i], button[aria-label*="control menu" i], '
            'button[aria-label*="more options" i], button[aria-label*="más opciones" i]'
        ).first
        boton_menu.click(timeout=4000)
        page.wait_for_timeout(800)
        page.get_by_role("menuitem", name=re.compile("copiar enlace|copy link", re.IGNORECASE)).click(timeout=4000)
        page.wait_for_timeout(800)
        link = page.evaluate("navigator.clipboard.readText()")
        return (link or "").strip()
    except Exception as e:
        print(f"    (no se pudo copiar el link: {e})")
        return ""
    finally:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass


def _buscar_keyword(page, keyword: str) -> list[dict]:
    """Busca UNA keyword en el buscador de publicaciones de LinkedIn,
    filtrado a las últimas 24hs, y devuelve los posts visibles en la
    primera pantalla (sin scrollear infinito - más lento pero más
    discreto). No pide el link acá todavía (es caro, involucra abrir un
    menú y leer el portapapeles) - eso se hace después, solo para los
    que pasan el filtro de "oferta de trabajo real" en ciclo()."""
    from urllib.parse import quote

    url = (
        "https://www.linkedin.com/search/results/content/"
        f"?keywords={quote(keyword)}&datePosted=%22past-24h%22&sortBy=%22date_posted%22"
    )
    page.goto(url, timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(random.uniform(3000, 5000))

    if _hay_checkpoint(page):
        raise RuntimeError("LinkedIn pidió una verificación de seguridad (checkpoint) - abortando este ciclo")

    # Scroll suave un par de veces para que cargue más contenido (LinkedIn
    # usa scroll infinito) - despacio, simulando lectura, no un salto brusco.
    for _ in range(2):
        page.mouse.wheel(0, random.randint(600, 900))
        page.wait_for_timeout(random.uniform(1500, 2500))

    resultados = []
    # role="listitem" es la señal más estable para "esto es un post" en la
    # UI actual - las clases CSS son hashes generados que cambian solos
    # (ej. "_646798e5"), no sirven como ancla.
    items = page.locator('[role="listitem"]')
    n = items.count()
    for i in range(min(n, 25)):
        item = items.nth(i)
        try:
            texto = item.inner_text(timeout=3000)
        except Exception:
            continue
        if not texto:
            continue
        resultados.append({"item": item, "texto": texto, "autor": _extraer_autor(texto), "keyword": keyword})

    return resultados


def ciclo(sheets: SheetsClient) -> int:
    """Corre una pasada completa por todas las keywords. Devuelve la
    cantidad de matches NUEVOS guardados."""
    from playwright.sync_api import sync_playwright

    if not os.path.exists(SESSION_FILE):
        raise RuntimeError(f"No existe {SESSION_FILE} - corré primero: python linkedin_login_setup.py")

    sheets.add_sheet(TAB, headers=HEADERS)
    existentes = {f[3] for f in sheets.read_range(f"'{TAB}'!A2:E10000") if f and len(f) > 3}

    nuevos = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(storage_state=SESSION_FILE, permissions=["clipboard-read", "clipboard-write"])
        page = context.new_page()

        try:
            for idx, kw in enumerate(KEYWORDS):
                print(f"[BUSCA] '{kw}'")
                try:
                    posts = _buscar_keyword(page, kw)
                except RuntimeError as e:
                    print(f"  ABORTADO: {e}")
                    break

                for post in posts:
                    if not _es_oferta_de_trabajo(post["texto"]):
                        continue
                    link = _obtener_link_post(page, post["item"])
                    if not link or link in existentes:
                        continue
                    existentes.add(link)
                    nuevos.append({"autor": post["autor"], "texto": post["texto"], "url": link, "keyword": kw})
                    print(f"  [MATCH] {post['autor']} - {link}")

                if idx < len(KEYWORDS) - 1:
                    time.sleep(random.uniform(15, 30))  # pausa entre keywords, nada de ráfaga
        finally:
            browser.close()

    if nuevos:
        filas = [
            [datetime.now().strftime("%d/%m/%Y %H:%M:%S"), p["autor"], p["texto"][:500], p["url"], p["keyword"]]
            for p in nuevos
        ]
        sheets.write_range(f"'{TAB}'!A2", filas, append=True)
        _avisar_n8n(len(nuevos), nuevos[0])

    return len(nuevos)


def _avisar_n8n(cantidad: int, primero: dict):
    """Le pega al webhook de n8n para que dispare el WhatsApp - si n8n no
    está levantado o el webhook no existe todavía, no rompe el script
    (los matches ya quedaron guardados en la Sheet de todas formas)."""
    try:
        import requests
        requests.post(N8N_WEBHOOK_URL, json={
            "cantidad": cantidad, "autor": primero["autor"], "url": primero["url"],
        }, timeout=10)
    except Exception as e:
        print(f"⚠️  No se pudo avisar a n8n ({N8N_WEBHOOK_URL}): {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--intervalo", type=int, default=60, help="Minutos entre cada ciclo completo (default: 60 - despacio a propósito)")
    ap.add_argument("--una-vez", action="store_true")
    a = ap.parse_args()

    if os.path.exists(STOP_FILE):
        os.remove(STOP_FILE)

    sheets = SheetsClient(credentials_file="credentials.json")
    n = 0
    while True:
        n += 1
        print(f"===== CICLO {n} =====")
        try:
            nuevos = ciclo(sheets)
            print(f"CICLO {n}: {nuevos} matches nuevos")
            reportar_heartbeat(sheets, "buscar_postulaciones_linkedin", detalle=f"ciclo {n}, {nuevos} nuevos")
        except Exception as e:
            print(f"CICLO {n} ERROR: {e}")
            reportar_heartbeat(sheets, "buscar_postulaciones_linkedin", detalle=f"ciclo {n}, ERROR: {e}")

        if a.una_vez:
            break

        for _ in range(a.intervalo * 60 // 30):
            if os.path.exists(STOP_FILE):
                print("STOP_linkedin.loop, saliendo.")
                return
            time.sleep(30)


if __name__ == "__main__":
    main()
