"""
Loop que se postula solo en los formularios de contacto de la pestaña
seguimiento_manual (empresas con sitio real pero sin email encontrado -
por eso quedan ahí en vez de ir por send_loop.py). Usa Playwright para
completar y mandar el "Mensaje sugerido" que ya tiene cada fila.

Totalmente automático (sin revisión manual por fila) - por eso es
conservador: si no encuentra con confianza un formulario de contacto real,
o si el sitio tiene CAPTCHA, NO inventa ni fuerza nada - marca la fila para
revisión manual y sigue con la siguiente. Nunca intenta resolver/evadir
CAPTCHAs.

Columnas de seguimiento_manual (A a G ya existían, se agregan H e I):
A: Fecha hallazgo | B: Empresa | C: Ciudad | D: Sitio web |
E: Formulario de contacto | F: Mensaje sugerido | G: Fuente |
H: Estado postulación (se agrega acá) | I: Fecha postulación (se agrega acá)

Uso:
    python postular_formularios.py --una-vez     -> procesa 1 fila y sale
    python postular_formularios.py                -> loop infinito
    python postular_formularios.py --dry-run       -> no manda nada, solo prueba deteccion
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

TAB = "seguimiento_manual"
HEADERS_EXTRA = ["Estado postulación", "Fecha postulación"]
STOP_FILE = os.path.join(os.path.dirname(__file__), "STOP_postular.loop")

MI_NOMBRE = "Germán Rodríguez"
MI_EMAIL = "rodriguezg.dev@gmail.com"
ASUNTO_DEFAULT = "Colaboración freelance - Desarrollo Web"

_NAME_KEYS = ["name", "nombre", "your-name", "fullname", "full-name", "apellido"]
_EMAIL_KEYS = ["email", "correo", "mail", "your-email"]
_SUBJECT_KEYS = ["subject", "asunto", "your-subject"]
_MESSAGE_KEYS = ["message", "mensaje", "comment", "comentario", "your-message", "consulta"]

_CAPTCHA_SIGNALS = ["recaptcha", "hcaptcha", "turnstile", "cf-chl", "are you human", "verify you are human"]
_COOKIE_ACCEPT_TEXTS = ["aceptar todas", "aceptar", "accept all", "accept", "entendido", "ok, entendido", "i agree", "got it"]


def _matches(attr_value, keywords):
    v = (attr_value or "").lower()
    return any(k in v for k in keywords)


def _cerrar_banner_cookies(page):
    """Best-effort: cierra banners de cookies que tapan el formulario. Si
    no encuentra nada no rompe (try/except silencioso) - no es crítico."""
    for texto in _COOKIE_ACCEPT_TEXTS:
        try:
            boton = page.get_by_role("button", name=re.compile(texto, re.IGNORECASE))
            if boton.count() > 0:
                boton.first.click(timeout=2000)
                page.wait_for_timeout(500)
                return
        except Exception:
            continue


def _tiene_captcha(page) -> bool:
    try:
        html = page.content().lower()
        return any(s in html for s in _CAPTCHA_SIGNALS)
    except Exception:
        return False


def _campo_por_keywords(form, keywords, tags=("input", "textarea")):
    """Busca dentro de `form` el primer input/textarea cuyo name/id/
    placeholder/aria-label matchee alguna keyword. None si no encuentra."""
    for tag in tags:
        elementos = form.locator(tag)
        n = elementos.count()
        for i in range(n):
            el = elementos.nth(i)
            try:
                for attr in ("name", "id", "placeholder", "aria-label"):
                    valor = el.get_attribute(attr)
                    if valor and _matches(valor, keywords):
                        tipo = (el.get_attribute("type") or "").lower()
                        if tipo in ("hidden", "submit", "button", "checkbox", "radio"):
                            continue
                        return el
            except Exception:
                continue
    return None


def _completar_formulario(page, mensaje: str, dry_run: bool) -> tuple[bool, str]:
    """Intenta encontrar y completar el formulario de contacto real de la
    página ya cargada. Devuelve (ok, detalle)."""
    if _tiene_captcha(page):
        return False, "captcha detectado - requiere revisión manual"

    _cerrar_banner_cookies(page)

    textareas = page.locator("textarea")
    if textareas.count() == 0:
        return False, "no se encontró textarea (sin formulario de contacto claro)"

    # El textarea es la señal más fuerte de "este es el formulario de
    # contacto real" (a diferencia de un simple input de newsletter que
    # solo pide email). Se usa el primero visible.
    textarea = None
    for i in range(textareas.count()):
        cand = textareas.nth(i)
        try:
            if cand.is_visible():
                textarea = cand
                break
        except Exception:
            continue
    if textarea is None:
        return False, "textarea encontrado pero no visible"

    try:
        form = textarea.locator("xpath=ancestor::form[1]")
        if form.count() == 0:
            return False, "el textarea no está dentro de un <form>"
    except Exception:
        return False, "no se pudo resolver el <form> del textarea"

    if _tiene_captcha(page):  # el cierre del banner de cookies puede haber revelado uno
        return False, "captcha detectado - requiere revisión manual"

    try:
        textarea.fill(mensaje, timeout=5000)
    except Exception as e:
        return False, f"no se pudo completar el mensaje: {e}"

    campo_nombre = _campo_por_keywords(form, _NAME_KEYS)
    campo_email = _campo_por_keywords(form, _EMAIL_KEYS)
    campo_asunto = _campo_por_keywords(form, _SUBJECT_KEYS)

    for campo, valor in ((campo_nombre, MI_NOMBRE), (campo_email, MI_EMAIL), (campo_asunto, ASUNTO_DEFAULT)):
        if campo is not None:
            try:
                campo.fill(valor, timeout=3000)
            except Exception:
                pass  # campo opcional - si no se puede completar, se sigue igual

    if dry_run:
        return True, f"[DRY-RUN] formulario detectado y completado (nombre={'sí' if campo_nombre else 'no'}, email={'sí' if campo_email else 'no'}, asunto={'sí' if campo_asunto else 'no'})"

    boton_submit = None
    for selector in ("button[type=submit]", "input[type=submit]"):
        cand = form.locator(selector)
        if cand.count() > 0:
            boton_submit = cand.first
            break
    if boton_submit is None:
        try:
            boton_submit = form.get_by_role("button", name=re.compile("enviar|send|submit|contact", re.IGNORECASE)).first
        except Exception:
            boton_submit = None
    if boton_submit is None:
        return False, "se completó el mensaje pero no se encontró botón de enviar"

    try:
        boton_submit.click(timeout=5000)
        page.wait_for_timeout(2500)
    except Exception as e:
        return False, f"error al hacer click en enviar: {e}"

    try:
        invalidos = page.evaluate("document.querySelectorAll(':invalid').length")
        if invalidos and invalidos > 0:
            return False, f"formulario no se pudo enviar - {invalidos} campo(s) requerido(s) sin completar (posible teléfono u otro campo no detectado)"
    except Exception:
        pass

    return True, "enviado (no se puede confirmar recepción del lado del servidor)"


def procesar_fila(fila: list, dry_run: bool) -> tuple[str, str]:
    """Devuelve (estado, detalle) para escribir en la Sheet."""
    empresa = fila[1] if len(fila) > 1 else ""
    url_formulario = fila[4] if len(fila) > 4 else ""
    mensaje = fila[5] if len(fila) > 5 else ""

    if not url_formulario or not url_formulario.startswith("http"):
        return "Sin formulario", "no hay URL de formulario cargada en la Sheet"
    if not mensaje:
        return "Sin mensaje", "no hay Mensaje sugerido cargado en la Sheet"

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ))
        try:
            page.goto(url_formulario, timeout=20000, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            ok, detalle = _completar_formulario(page, mensaje, dry_run)
        except Exception as e:
            ok, detalle = False, f"no se pudo cargar el sitio: {e}"
        finally:
            browser.close()

    print(f"  [{empresa}] {'OK' if ok else 'FALLO'} - {detalle}")

    if not ok:
        if "captcha" in detalle.lower():
            return "Requiere revisión (captcha)", detalle
        return "Error", detalle
    return "Enviado" if not dry_run else "Enviado (dry-run)", detalle


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--intervalo", type=int, default=5, help="Minutos de espera entre cada postulación (default: 5)")
    ap.add_argument("--una-vez", action="store_true", help="Procesa una sola fila pendiente y sale")
    ap.add_argument("--dry-run", action="store_true", help="Detecta y completa el formulario pero NO lo envía")
    a = ap.parse_args()

    if os.path.exists(STOP_FILE):
        os.remove(STOP_FILE)

    sheets = SheetsClient(credentials_file="credentials.json")

    # Asegura que existan las columnas H/I de tracking - si ya existen
    # (corridas anteriores) no las pisa.
    headers = sheets.read_range(f"'{TAB}'!A1:I1")
    headers = headers[0] if headers else []
    if len(headers) < 9:
        sheets.write_range(f"'{TAB}'!H1", [HEADERS_EXTRA], append=False)

    print(f"LOOP postular_formularios intervalo={a.intervalo}min dry_run={a.dry_run}")
    n = 0
    while True:
        n += 1
        filas = sheets.read_range(f"'{TAB}'!A2:I10000")
        pendiente_idx = None
        for i, f in enumerate(filas):
            if not f or not f[0]:
                continue
            estado = f[7] if len(f) > 7 else ""
            if not estado.strip():
                pendiente_idx = i
                break

        if pendiente_idx is None:
            print("No quedan filas pendientes en seguimiento_manual. Fin del loop.")
            reportar_heartbeat(sheets, "postular_formularios", detalle=f"ciclo {n}, sin pendientes")
            break

        fila = filas[pendiente_idx]
        fila_num = pendiente_idx + 2
        print(f"===== CICLO {n} - fila {fila_num}: {fila[1] if len(fila) > 1 else '?'} =====")

        try:
            estado, detalle = procesar_fila(fila, a.dry_run)
        except Exception as e:
            estado, detalle = "Error", f"excepción no controlada: {e}"
            print(f"  ERROR: {e}")
        print(f"  -> {estado}: {detalle}")

        if not a.dry_run:
            sheets.write_range(
                f"'{TAB}'!H{fila_num}",
                [[estado, datetime.now().strftime("%d/%m/%Y %H:%M:%S")]],
                append=False,
            )

        reportar_heartbeat(sheets, "postular_formularios", detalle=f"ciclo {n}, {fila[1] if len(fila) > 1 else '?'}: {estado}")

        if a.una_vez:
            break

        for m in range(a.intervalo * 60, 0, -60):
            if os.path.exists(STOP_FILE):
                print("STOP_postular.loop, saliendo.")
                return
            time.sleep(60)


if __name__ == "__main__":
    main()
