"""
Corré esto UNA sola vez para loguearte en LinkedIn y guardar la sesión -
así buscar_postulaciones_linkedin.py no necesita loguearse en cada corrida
(logins repetidos automatizados son justo lo que más dispara las alertas
anti-bot de LinkedIn).

IMPORTANTE: este script nunca ve ni maneja tu contraseña. Se abre una
ventana real de Chrome y la escribís vos mismo, como cualquier login
normal. Lo único que hace el script es guardar las cookies de sesión ya
autenticada para reusarlas después.

Uso:
    python linkedin_login_setup.py

Cuando tengas que volver a loguearte (la sesión expiró, o LinkedIn pidió
una verificación de seguridad), corré esto de nuevo.
"""
import os

from playwright.sync_api import sync_playwright

SESSION_FILE = os.path.join(os.path.dirname(__file__), "linkedin_session.json")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.linkedin.com/login")

        print("=" * 70)
        print("Se abrió una ventana de Chrome - iniciá sesión en LinkedIn ahí,")
        print("de forma normal (incluido cualquier 2FA/verificación que pida).")
        print("Cuando veas tu feed/inicio cargado, volvé a esta terminal y")
        print("presioná Enter.")
        print("=" * 70)
        input()

        context.storage_state(path=SESSION_FILE)
        print(f"✅ Sesión guardada en {SESSION_FILE}")
        browser.close()


if __name__ == "__main__":
    main()
