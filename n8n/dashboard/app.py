"""
Dashboard chico para cargar datos de un cliente y disparar el
generador de presupuestos (via el runner, nunca directo - el runner es
el unico que tiene Python/Chromium/Playwright instalados).

Separado a proposito del dashboard viejo (web/app.py, que depende de
todo el framework de agentes original - Gmail, Gemini, agent_0..4) que
no se usa para este flujo. Este es liviano: solo FastAPI + httpx.

Publicado solo en 127.0.0.1 (ver docker-compose.yml), igual que n8n -
no expuesto a la LAN ni a internet.
"""
from pathlib import Path

import httpx
from fastapi import FastAPI, Form
from fastapi.responses import FileResponse, HTMLResponse

RUNNER_URL = "http://runner:8000"
OUTPUT_DIR = Path("/data/presupuestos_generados")

app = FastAPI(title="Dashboard de presupuestos")

FORM_HTML = """
<!DOCTYPE html>
<html lang="es-AR">
<head>
<meta charset="UTF-8">
<title>Generar presupuesto</title>
<style>
  body {{ background:#0a0a0c; color:#f2f0ea; font-family:-apple-system,'Segoe UI',sans-serif;
         max-width:560px; margin:60px auto; padding:0 20px; line-height:1.6; }}
  h1 {{ font-size:22px; }}
  label {{ display:block; margin-top:18px; font-size:13px; color:#a8a6a0; }}
  input, select {{ width:100%; padding:10px; margin-top:6px; background:#1c1c1f;
                   border:1px solid #2a2a2e; color:#f2f0ea; border-radius:4px; font-size:14px; }}
  button {{ margin-top:26px; padding:12px 20px; background:#e0a339; color:#0a0a0c;
            border:none; border-radius:4px; font-weight:600; cursor:pointer; font-size:14px; }}
  button:hover {{ opacity:0.9; }}
  .msg {{ margin-top:24px; padding:16px; border-radius:4px; font-size:14px; }}
  .ok {{ background:#14241a; border:1px solid #2d5a3d; }}
  .error {{ background:#241414; border:1px solid #5a2d2d; }}
  a {{ color:#e0a339; }}
</style>
</head>
<body>
  <h1>Generar presupuesto para un cliente</h1>
  <form method="post" action="/generar">
    <label>Nombre del cliente
      <input name="cliente" required placeholder="Ej: Alkanos">
    </label>
    <label>URL del sitio
      <input name="url" required placeholder="https://sitio.com">
    </label>
    <label>Estrategia de auditoría
      <select name="estrategia">
        <option value="mobile">Mobile</option>
        <option value="desktop">Desktop</option>
      </select>
    </label>
    <button type="submit">Generar presupuesto (HTML + PDF)</button>
  </form>
  {resultado}
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def home():
    return FORM_HTML.format(resultado="")


@app.post("/generar", response_class=HTMLResponse)
def generar(cliente: str = Form(...), url: str = Form(...), estrategia: str = Form("mobile")):
    try:
        r = httpx.post(
            f"{RUNNER_URL}/presupuesto",
            json={"cliente": cliente, "url": url, "estrategia": estrategia},
            timeout=180,
        )
        data = r.json()
    except Exception as e:
        resultado = f'<div class="msg error">No se pudo contactar al runner: {e}</div>'
        return FORM_HTML.format(resultado=resultado)

    if r.status_code != 200 or not data.get("ok"):
        resultado = f'<div class="msg error">Falló la generación: {data}</div>'
        return FORM_HTML.format(resultado=resultado)

    html_name = Path(data["html_path"]).name
    pdf_name = Path(data["pdf_path"]).name if data.get("pdf_path") else None
    links = f'<a href="/descargar/{html_name}">Ver HTML</a>'
    if pdf_name:
        links += f' · <a href="/descargar/{pdf_name}">Descargar PDF</a>'
    resultado = f'<div class="msg ok">Listo para <strong>{cliente}</strong>. {links}</div>'
    return FORM_HTML.format(resultado=resultado)


@app.get("/descargar/{nombre_archivo}")
def descargar(nombre_archivo: str):
    """Sirve un archivo ya generado. Se restringe a OUTPUT_DIR (sin ..
    ni rutas absolutas) para no poder pedir cualquier archivo del /data
    montado - solo lo que el propio runner generó ahí."""
    destino = (OUTPUT_DIR / nombre_archivo).resolve()
    if OUTPUT_DIR.resolve() not in destino.parents or not destino.exists():
        return HTMLResponse("Archivo no encontrado", status_code=404)
    return FileResponse(destino)


@app.get("/health")
def health():
    return {"status": "ok"}
