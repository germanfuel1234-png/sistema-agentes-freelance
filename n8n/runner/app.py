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
from pydantic import BaseModel

DATA_DIR = Path("/data")
PRESUPUESTO_SCRIPT = DATA_DIR / "agentes" / "agente_presupuesto_seo.py"

app = FastAPI(title="runner interno - sistema_agentes_freelance")


class PresupuestoRequest(BaseModel):
    cliente: str
    url: str
    estrategia: str = "mobile"


@app.get("/health")
def health():
    return {"status": "ok", "script_presupuesto_existe": PRESUPUESTO_SCRIPT.exists()}


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

    return {"ok": True, "stdout": resultado.stdout}
