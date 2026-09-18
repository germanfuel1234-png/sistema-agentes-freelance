"""
Dashboard del sistema: generar presupuestos, ver los ya generados (con
cobertura vigente/vencida), clientes/leads, y estado de mails - todo
consumiendo al runner (via httpx), nunca corriendo Lighthouse/Gmail acá
mismo (el runner es el unico con Python/Chromium/Playwright instalados).

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

app = FastAPI(title="Dashboard - sistema_agentes_freelance")

NAV = [
    ("/generar", "Generar presupuesto"),
    ("/presupuestos", "Presupuestos generados"),
    ("/leads", "Clientes / Leads"),
    ("/mails", "Mails"),
]

LAYOUT = """
<!DOCTYPE html>
<html lang="es-AR">
<head>
<meta charset="UTF-8">
<title>{titulo}</title>
<style>
  :root {{ --bg:#0a0a0c; --surface:#141416; --surface-2:#1c1c1f; --line:#2a2a2e;
           --text:#f2f0ea; --text-dim:#a8a6a0; --amber:#e0a339; --good:#6fbf73; --bad:#d9584f; }}
  * {{ box-sizing:border-box; }}
  body {{ background:var(--bg); color:var(--text); font-family:-apple-system,'Segoe UI',sans-serif;
         margin:0; line-height:1.6; }}
  nav {{ display:flex; gap:4px; padding:16px 24px; border-bottom:1px solid var(--line);
        flex-wrap:wrap; align-items:center; }}
  nav a {{ color:var(--text-dim); text-decoration:none; padding:8px 14px; border-radius:4px; font-size:14px; }}
  nav a:hover {{ background:var(--surface); color:var(--text); }}
  nav a.active {{ background:var(--surface-2); color:var(--amber); font-weight:600; }}
  main {{ max-width:1000px; margin:0 auto; padding:32px 24px; }}
  h1 {{ font-size:22px; margin-top:0; }}
  label {{ display:block; margin-top:18px; font-size:13px; color:var(--text-dim); }}
  input, select {{ width:100%; padding:10px; margin-top:6px; background:var(--surface-2);
                   border:1px solid var(--line); color:var(--text); border-radius:4px; font-size:14px; }}
  button {{ margin-top:26px; padding:12px 20px; background:var(--amber); color:var(--bg);
            border:none; border-radius:4px; font-weight:600; cursor:pointer; font-size:14px; }}
  button:hover {{ opacity:0.9; }}
  .msg {{ margin-top:24px; padding:16px; border-radius:4px; font-size:14px; }}
  .ok {{ background:#14241a; border:1px solid #2d5a3d; }}
  .error {{ background:#241414; border:1px solid #5a2d2d; }}
  a {{ color:var(--amber); }}
  table {{ width:100%; border-collapse:collapse; margin-top:16px; font-size:14px; }}
  th, td {{ text-align:left; padding:10px 12px; border-bottom:1px solid var(--line); }}
  th {{ color:var(--text-dim); font-weight:500; font-size:12px; text-transform:uppercase; }}
  .badge {{ padding:3px 9px; border-radius:3px; font-size:12px; font-weight:600; }}
  .badge-ok {{ background:#14241a; color:var(--good); }}
  .badge-bad {{ background:#241414; color:var(--bad); }}
  .badge-warn {{ background:#2a2210; color:var(--amber); }}
  .empty {{ color:var(--text-dim); padding:24px 0; }}
  .stat {{ display:inline-block; background:var(--surface); border:1px solid var(--line);
           border-radius:4px; padding:14px 20px; margin:0 12px 12px 0; }}
  .stat b {{ display:block; font-size:24px; color:var(--amber); }}
  .stat span {{ font-size:12px; color:var(--text-dim); }}
</style>
</head>
<body>
<nav>
  {nav_links}
</nav>
<main>
{contenido}
</main>
</body>
</html>
"""


def render(titulo: str, contenido: str, activo: str = "") -> str:
    links = "".join(
        f'<a href="{href}" class="{"active" if href == activo else ""}">{label}</a>'
        for href, label in NAV
    )
    return LAYOUT.format(titulo=titulo, nav_links=links, contenido=contenido)


FORM_HTML = """
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
  <label>Días de cobertura incluidos en el presupuesto
    <select name="dias_cobertura">
      <option value="7">7 días</option>
      <option value="30" selected>30 días</option>
    </select>
  </label>
  <button type="submit">Generar presupuesto (HTML + PDF)</button>
</form>
{resultado}
"""


@app.get("/", response_class=HTMLResponse)
def home():
    return render("Dashboard", FORM_HTML.format(resultado=""), activo="/generar")


@app.get("/generar", response_class=HTMLResponse)
def generar_form():
    return render("Generar presupuesto", FORM_HTML.format(resultado=""), activo="/generar")


@app.post("/generar", response_class=HTMLResponse)
def generar(
    cliente: str = Form(...),
    url: str = Form(...),
    estrategia: str = Form("mobile"),
    dias_cobertura: int = Form(30),
):
    try:
        r = httpx.post(
            f"{RUNNER_URL}/presupuesto",
            json={
                "cliente": cliente, "url": url, "estrategia": estrategia,
                "dias_cobertura": dias_cobertura,
            },
            timeout=180,
        )
        data = r.json()
    except Exception as e:
        resultado = f'<div class="msg error">No se pudo contactar al runner: {e}</div>'
        return render("Generar presupuesto", FORM_HTML.format(resultado=resultado), activo="/generar")

    if r.status_code != 200 or not data.get("ok"):
        resultado = f'<div class="msg error">Falló la generación: {data}</div>'
        return render("Generar presupuesto", FORM_HTML.format(resultado=resultado), activo="/generar")

    html_name = Path(data["html_path"]).name
    pdf_name = Path(data["pdf_path"]).name if data.get("pdf_path") else None
    links = f'<a href="/descargar/{html_name}">Ver HTML</a>'
    if pdf_name:
        links += f' · <a href="/descargar/{pdf_name}">Descargar PDF</a>'
    resultado = f'<div class="msg ok">Listo para <strong>{cliente}</strong>. {links}</div>'
    return render("Generar presupuesto", FORM_HTML.format(resultado=resultado), activo="/generar")


@app.get("/presupuestos", response_class=HTMLResponse)
def ver_presupuestos():
    try:
        r = httpx.get(f"{RUNNER_URL}/presupuestos", timeout=30)
        data = r.json().get("presupuestos", [])
    except Exception as e:
        return render("Presupuestos generados", f'<h1>Presupuestos generados</h1><div class="msg error">No se pudo leer la Sheet: {e}</div>', activo="/presupuestos")

    if not data:
        contenido = '<h1>Presupuestos generados</h1><p class="empty">Todavía no generaste ninguno.</p>'
        return render("Presupuestos generados", contenido, activo="/presupuestos")

    vigentes = sum(1 for p in data if p.get("cobertura_vigente"))
    vencidos = sum(1 for p in data if p.get("cobertura_vigente") is False)

    filas = ""
    for p in reversed(data):  # mas recientes primero
        if p.get("cobertura_vigente") is True:
            badge = f'<span class="badge badge-ok">Vigente hasta {p["fecha_vencimiento_cobertura"]}</span>'
        elif p.get("cobertura_vigente") is False:
            badge = f'<span class="badge badge-bad">Venció {p["fecha_vencimiento_cobertura"]}</span>'
        else:
            badge = '<span class="badge badge-warn">Sin datos</span>'
        html_link = f'<a href="/descargar/{Path(p["html"]).name}">HTML</a>' if p.get("html") else "-"
        pdf_link = f'<a href="/descargar/{Path(p["pdf"]).name}">PDF</a>' if p.get("pdf") else "-"
        precio = f'${int(p["precio_total"]):,}'.replace(",", ".") if p.get("precio_total") else "-"
        filas += f"""<tr>
          <td>{p['fecha']}</td><td>{p['cliente']}</td><td>{p['url']}</td>
          <td>{precio}</td><td>{p['dias_cobertura']} días</td><td>{badge}</td>
          <td>{html_link} · {pdf_link}</td>
        </tr>"""

    contenido = f"""
    <h1>Presupuestos generados</h1>
    <div class="stat"><b>{len(data)}</b><span>Total</span></div>
    <div class="stat"><b>{vigentes}</b><span>Con cobertura vigente</span></div>
    <div class="stat"><b>{vencidos}</b><span>Cobertura vencida</span></div>
    <table>
      <tr><th>Fecha</th><th>Cliente</th><th>Sitio</th><th>Precio</th><th>Cobertura</th><th>Estado</th><th>Archivos</th></tr>
      {filas}
    </table>
    """
    return render("Presupuestos generados", contenido, activo="/presupuestos")


@app.get("/leads", response_class=HTMLResponse)
def ver_leads():
    return render("Clientes / Leads", "<h1>Clientes / Leads</h1><p class='empty'>Próximamente.</p>", activo="/leads")


@app.get("/mails", response_class=HTMLResponse)
def ver_mails():
    return render("Mails", "<h1>Mails</h1><p class='empty'>Próximamente.</p>", activo="/mails")


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
