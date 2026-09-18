"""
API interna del "runner" - ejecuta los scripts pesados (Lighthouse,
generador de presupuestos) que n8n no puede correr en su propio
contenedor (la imagen oficial de n8n es "hardened", sin Python/Chrome
ni gestor de paquetes - a propósito, por seguridad).

Solo se accede a esto desde la red interna de Docker Compose (nunca
publicado a la LAN ni a internet) - n8n le pega por HTTP (nodo HTTP
Request) en vez de usar Execute Command, así nunca hay ejecución de
comandos arbitrarios expuesta.
"""
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from playwright.sync_api import sync_playwright
from pydantic import BaseModel

DATA_DIR = Path("/data")
AGENTES_DIR = DATA_DIR / "agentes"
PRESUPUESTO_SCRIPT = AGENTES_DIR / "agente_presupuesto_seo.py"
OUTPUT_DIR = DATA_DIR / "presupuestos_generados"

sys.path.insert(0, str(AGENTES_DIR))

app = FastAPI(title="runner interno - sistema_agentes_freelance")


class PresupuestoRequest(BaseModel):
    cliente: str
    url: str
    estrategia: str = "mobile"
    generar_pdf: bool = True


@app.get("/health")
def health():
    return {"status": "ok", "script_presupuesto_existe": PRESUPUESTO_SCRIPT.exists()}


def _html_a_pdf(html_path: Path, pdf_path: Path):
    """Abre el HTML ya generado (con el hero animado en Three.js) en
    Chromium headless y lo exporta a PDF. emulate_media("screen") en vez
    de dejar el media "print" por defecto - más confiable para que el
    canvas WebGL del hero se capture como se ve en pantalla, no en blanco."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"file://{html_path}", wait_until="networkidle")
        page.emulate_media(media="screen")
        page.wait_for_timeout(2000)  # deja animar el hero 3D antes de capturar
        page.pdf(path=str(pdf_path), format="A4", print_background=True)
        browser.close()


@app.post("/presupuesto")
def generar_presupuesto(req: PresupuestoRequest):
    if req.estrategia not in ("mobile", "desktop"):
        raise HTTPException(400, "estrategia debe ser 'mobile' o 'desktop'")
    if not PRESUPUESTO_SCRIPT.exists():
        raise HTTPException(500, f"no se encontró {PRESUPUESTO_SCRIPT} - ¿está montado /data?")

    resultado = subprocess.run(
        [
            sys.executable, str(PRESUPUESTO_SCRIPT),
            "--cliente", req.cliente,
            "--url", req.url,
            "--estrategia", req.estrategia,
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if resultado.returncode != 0:
        raise HTTPException(500, detail={
            "error": "el generador de presupuesto falló",
            "stdout": resultado.stdout[-3000:],
            "stderr": resultado.stderr[-3000:],
        })

    from agente_presupuesto_seo import slugify
    html_path = OUTPUT_DIR / f"presupuesto-{slugify(req.cliente)}.html"
    respuesta = {"ok": True, "stdout": resultado.stdout, "html_path": str(html_path)}

    if req.generar_pdf:
        if not html_path.exists():
            raise HTTPException(500, f"se esperaba el HTML en {html_path} pero no está")
        pdf_path = html_path.with_suffix(".pdf")
        try:
            _html_a_pdf(html_path, pdf_path)
        except Exception as e:
            raise HTTPException(500, detail={"error": "el HTML se generó pero falló el PDF", "detalle": str(e)})
        respuesta["pdf_path"] = str(pdf_path)

    return respuesta
