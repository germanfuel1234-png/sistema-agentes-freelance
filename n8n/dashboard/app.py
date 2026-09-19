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
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

RUNNER_URL = "http://runner:8000"
N8N_WEBHOOK_URL = "http://n8n:5678/webhook/generar-presupuesto"
OUTPUT_DIR = Path("/data/presupuestos_generados")
GMAIL_ACCOUNT = "rodriguezg.dev@gmail.com"

# Path real en el HOST (no el /data del contenedor) - Chrome bloquea la
# navegación a file:// desde una página http:// (probado en vivo: un link
# <a href="file://..."> no hace nada al clickearlo, ni en pestaña nueva),
# así que no hay forma de "abrir el explorador de archivos" desde acá.
# Lo que SI se puede: mostrar la ruta real para copiarla.
HOST_PROJECT_ROOT = "/home/german/Escritorio/marketin/sistema_agentes_freelance"

app = FastAPI(title="Dashboard - sistema_agentes_freelance")

NAV = [
    ("/generar", "Generar presupuesto"),
    ("/presupuestos", "Presupuestos generados"),
    ("/leads", "Leads"),
    ("/clientes", "Clientes"),
    ("/mails", "Mails"),
    ("/estado", "Estado"),
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
  input, select, textarea {{ width:100%; padding:10px; margin-top:6px; background:var(--surface-2);
                   border:1px solid var(--line); color:var(--text); border-radius:4px; font-size:14px; font-family:inherit; }}
  td input.v-editable {{ margin-top:0; padding:6px 8px; font-size:13px; min-width:100px; }}
  button {{ margin-top:26px; padding:12px 20px; background:var(--amber); color:var(--bg);
            border:none; border-radius:4px; font-weight:600; cursor:pointer; font-size:14px; }}
  button:hover {{ opacity:0.9; }}
  button.ver-mas {{ margin-top:10px; padding:8px 14px; background:var(--surface-2);
                    color:var(--text); font-size:13px; font-weight:500; border:1px solid var(--line); }}
  button.btn-mail {{ margin-top:0; padding:6px 12px; background:var(--surface-2);
                     color:var(--text); font-size:13px; font-weight:500; border:1px solid var(--line); }}
  button.btn-mail:disabled {{ opacity:0.5; cursor:default; }}
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
  a.stat {{ text-decoration:none; cursor:pointer; }}
  a.stat:hover {{ border-color:var(--amber); }}
  .filtro {{ margin-top:20px; max-width:320px; }}
  .modal-overlay {{ display:none; position:fixed; inset:0; background:rgba(0,0,0,0.7);
                    z-index:100; align-items:center; justify-content:center; }}
  .modal-box {{ background:var(--surface); width:92%; max-width:900px; height:88vh;
               border-radius:6px; display:flex; flex-direction:column; overflow:hidden;
               border:1px solid var(--line); }}
  .modal-header {{ display:flex; justify-content:space-between; align-items:center;
                   padding:12px 16px; border-bottom:1px solid var(--line); flex-shrink:0; }}
  .modal-header span {{ font-size:14px; color:var(--text-dim); }}
  .modal-header .acciones {{ display:flex; gap:10px; align-items:center; }}
  .modal-header a {{ font-size:13px; }}
  .modal-header button {{ margin:0; padding:6px 12px; background:var(--surface-2);
                          color:var(--text); font-size:13px; }}
  #modalFrame {{ flex:1; border:none; background:#fff; width:100%; }}
</style>
</head>
<body>
<nav>
  {nav_links}
</nav>
<main>
{contenido}
</main>

<div id="modalOverlay" class="modal-overlay" onclick="if(event.target===this) cerrarModal()">
  <div class="modal-box">
    <div class="modal-header">
      <span id="modalTitulo"></span>
      <div class="acciones">
        <a id="modalDescargar" href="#" download>⬇ Descargar</a>
        <button onclick="cerrarModal()">Cerrar ✕</button>
      </div>
    </div>
    <iframe id="modalFrame" src="about:blank"></iframe>
  </div>
</div>

<script>
function abrirModal(url, titulo) {{
  document.getElementById('modalFrame').src = url;
  document.getElementById('modalTitulo').textContent = titulo;
  document.getElementById('modalDescargar').href = url;
  document.getElementById('modalOverlay').style.display = 'flex';
}}
function cerrarModal() {{
  document.getElementById('modalOverlay').style.display = 'none';
  document.getElementById('modalFrame').src = 'about:blank';
}}
function filtrarTabla(tablaId, texto) {{
  const tabla = document.getElementById(tablaId);
  if (!tabla) return;
  const q = texto.toLowerCase();
  const expandida = tabla.dataset.expandida === '1';
  tabla.querySelectorAll('tbody tr').forEach(fila => {{
    const coincide = fila.textContent.toLowerCase().includes(q);
    const esExtra = fila.classList.contains('fila-extra');
    fila.style.display = coincide && (q !== '' || expandida || !esExtra) ? '' : 'none';
  }});
}}
function toggleVerMas(boton, tablaId) {{
  const tabla = document.getElementById(tablaId);
  if (!tabla) return;
  const expandir = tabla.dataset.expandida !== '1';
  tabla.querySelectorAll('tbody tr.fila-extra').forEach(fila => {{
    fila.style.display = expandir ? '' : 'none';
  }});
  tabla.dataset.expandida = expandir ? '1' : '0';
  boton.textContent = expandir ? boton.dataset.verMenos : boton.dataset.verMas;
}}
async function enviarMailPresupuesto(boton) {{
  const cliente = boton.dataset.cliente;
  const pdfNombre = boton.dataset.pdf;
  const sugerido = boton.dataset.email || '';
  const email = prompt(`Enviar presupuesto de "${{cliente}}" a qué email?`, sugerido);
  if (!email) return;
  boton.disabled = true;
  const textoOriginal = boton.textContent;
  boton.textContent = 'Enviando...';
  try {{
    const form = new FormData();
    form.append('cliente', cliente);
    form.append('pdf_nombre', pdfNombre);
    form.append('email', email);
    const resp = await fetch('/presupuestos/enviar-mail', {{ method: 'POST', body: form }});
    const data = await resp.json();
    alert(data.ok ? `Mail enviado a ${{email}}` : `No se pudo enviar: ${{JSON.stringify(data.error || data)}}`);
  }} catch (e) {{
    alert('Error de red: ' + e);
  }} finally {{
    boton.disabled = false;
    boton.textContent = textoOriginal;
  }}
}}
function toggleModoGeneracion() {{
  const modo = document.getElementById('modoGeneracion').value;
  const formUrl = document.getElementById('formUrl');
  const formBrief = document.getElementById('formBrief');
  if (formUrl) formUrl.style.display = modo === 'url' ? '' : 'none';
  if (formBrief) formBrief.style.display = modo === 'brief' ? '' : 'none';
}}
async function copiarRuta(boton, ruta) {{
  try {{
    await navigator.clipboard.writeText(ruta);
    const original = boton.textContent;
    boton.textContent = '✓ Copiado';
    setTimeout(() => {{ boton.textContent = original; }}, 1500);
  }} catch (e) {{
    // Fallback si el navegador bloquea el clipboard (permisos, foco, etc.)
    // - prompt() deja el texto seleccionable/copiable con Ctrl+C, a
    // diferencia de un alert() que en algunos navegadores no se puede.
    prompt('No se pudo copiar automáticamente. Copiá con Ctrl+C:', ruta);
  }}
}}
async function controlarProceso(boton, nombre, accion) {{
  if (accion === 'iniciar' && !confirm(`¿Arrancar "${{nombre}}"? Va a correr solo, sin supervisión.`)) return;
  if (accion === 'detener' && !confirm(`¿Frenar "${{nombre}}"?`)) return;
  boton.disabled = true;
  try {{
    const resp = await fetch(`/estado/${{nombre}}/${{accion}}`, {{ method: 'POST' }});
    const data = await resp.json();
    if (data.ok) {{
      alert(accion === 'iniciar' ? 'Arrancó.' : 'Se avisó que pare (puede tardar hasta el próximo ciclo).');
      location.reload();
    }} else {{
      alert('No se pudo: ' + (data.detalle || JSON.stringify(data)));
    }}
  }} catch (e) {{
    alert('Error de red: ' + e);
  }} finally {{
    boton.disabled = false;
  }}
}}
function toggleEditarFila(boton) {{
  const fila = boton.closest('tr');
  const editando = fila.dataset.editando === '1';
  fila.querySelectorAll('.v-mostrado').forEach(el => el.style.display = editando ? '' : 'none');
  fila.querySelectorAll('.v-editable').forEach(el => el.style.display = editando ? 'none' : '');
  fila.dataset.editando = editando ? '0' : '1';
  if (editando) {{
    boton.textContent = '✏️';
    boton.onclick = () => toggleEditarFila(boton);
  }} else {{
    boton.textContent = '💾 Guardar';
    boton.onclick = () => guardarFila(boton);
  }}
}}
async function guardarFila(boton) {{
  const fila = boton.closest('tr');
  const filaId = fila.dataset.fila;
  const form = new FormData();
  form.append('fecha', fila.querySelector('.campo-fecha').value);
  form.append('cliente', fila.querySelector('.campo-cliente').value);
  form.append('url', fila.querySelector('.campo-url').value);
  form.append('precio_total', fila.querySelector('.campo-precio').value);
  form.append('dias_cobertura', fila.querySelector('.campo-dias').value);
  boton.disabled = true;
  try {{
    const resp = await fetch(`/presupuestos/${{filaId}}/editar`, {{ method: 'POST', body: form }});
    const data = await resp.json();
    if (data.ok) {{
      location.reload();
    }} else {{
      alert('No se pudo guardar: ' + (data.detalle || JSON.stringify(data)));
      boton.disabled = false;
    }}
  }} catch (e) {{
    alert('Error de red: ' + e);
    boton.disabled = false;
  }}
}}
async function subirHtmlPresupuesto(event) {{
  event.preventDefault();
  const zona = document.getElementById('zonaSubidaHtml');
  if (zona) zona.style.borderColor = 'var(--line)';
  const archivo = (event.dataTransfer && event.dataTransfer.files[0]) || (event.target && event.target.files && event.target.files[0]);
  if (!archivo) return;
  const textoOriginal = zona.textContent;
  zona.textContent = 'Subiendo y leyendo el HTML...';
  const form = new FormData();
  form.append('archivo', archivo);
  try {{
    const resp = await fetch('/presupuestos/subir-html', {{ method: 'POST', body: form }});
    const data = await resp.json();
    if (!data.ok) {{
      alert('No se pudo subir: ' + (data.detalle || JSON.stringify(data)));
      return;
    }}
    mostrarFormConfirmarHtml(data);
  }} catch (e) {{
    alert('Error de red: ' + e);
  }} finally {{
    zona.textContent = textoOriginal;
  }}
}}
function mostrarFormConfirmarHtml(data) {{
  const cont = document.getElementById('formConfirmarHtml');
  const detectado = data.cliente || data.url || data.precio_total;
  cont.innerHTML = `
    <div class="msg ok">
      <p>${{detectado ? '✓ Se detectaron algunos datos automáticamente - revisá y completá lo que falte.' : '⚠ No se pudo auto-detectar nada (¿es un HTML externo, no generado por el sistema?) - completá todo a mano.'}}</p>
      <label>Cliente<input id="ch-cliente" value="${{data.cliente || ''}}"></label>
      <label>URL<input id="ch-url" value="${{data.url || ''}}"></label>
      <label>Precio base (opcional)<input id="ch-precio-base" value="${{data.precio_base || ''}}"></label>
      <label>Precio total<input id="ch-precio-total" value="${{data.precio_total || ''}}"></label>
      <label>Días de cobertura<input id="ch-dias" value="30"></label>
      <button type="button" onclick="confirmarHtmlPresupuesto(this, '${{data.html_path}}')">Confirmar y guardar</button>
      <button type="button" class="btn-mail" style="margin-left:8px;" onclick="document.getElementById('formConfirmarHtml').innerHTML=''">Cancelar</button>
    </div>`;
}}
async function confirmarHtmlPresupuesto(boton, htmlPath) {{
  boton.disabled = true;
  const form = new FormData();
  form.append('html_path', htmlPath);
  form.append('cliente', document.getElementById('ch-cliente').value);
  form.append('url', document.getElementById('ch-url').value);
  form.append('precio_base', document.getElementById('ch-precio-base').value);
  form.append('precio_total', document.getElementById('ch-precio-total').value);
  form.append('dias_cobertura', document.getElementById('ch-dias').value);
  try {{
    const resp = await fetch('/presupuestos/confirmar-html-guardar', {{ method: 'POST', body: form }});
    const data = await resp.json();
    if (data.ok) {{
      location.reload();
    }} else {{
      alert('No se pudo guardar: ' + (data.detalle || JSON.stringify(data)));
      boton.disabled = false;
    }}
  }} catch (e) {{
    alert('Error de red: ' + e);
    boton.disabled = false;
  }}
}}
document.addEventListener('keydown', e => {{ if (e.key === 'Escape') cerrarModal(); }});
</script>
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

<label style="margin-top:0;">¿Tenés la URL del sitio para auditar?
  <select id="modoGeneracion" onchange="toggleModoGeneracion()">
    <option value="url">Sí - auditoría automática con Lighthouse</option>
    <option value="brief">No - cargar la info a mano (brief)</option>
  </select>
</label>

<form id="formUrl" method="post" action="/generar">
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

<form id="formBrief" method="post" action="/generar-brief" style="display:none;">
  <label>Nombre del cliente
    <input name="cliente" required placeholder="Ej: Alkanos">
  </label>
  <label>URL del sitio (opcional - si todavía no la tienen)
    <input name="url" placeholder="https://sitio.com (opcional)">
  </label>
  <label>Brief / alcance del proyecto
    <textarea name="brief" required rows="6" placeholder="Contanos qué necesita el cliente: tipo de sitio, secciones, funcionalidades, etc. Una idea por línea."></textarea>
  </label>
  <label>Precio base (ARS)
    <input name="precio_base" type="number" required placeholder="Ej: 300000">
  </label>
  <label>Precio total (ARS)
    <input name="precio_total" type="number" required placeholder="Ej: 550000">
  </label>
  <label>Días de cobertura incluidos en el presupuesto
    <select name="dias_cobertura">
      <option value="7">7 días</option>
      <option value="30" selected>30 días</option>
    </select>
  </label>
  <button type="submit">Generar presupuesto desde brief (HTML + PDF)</button>
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
    links = f"<a href=\"#\" onclick=\"abrirModal('/descargar/{html_name}','{cliente} · HTML'); return false;\">Ver HTML</a>"
    if pdf_name:
        links += f" · <a href=\"#\" onclick=\"abrirModal('/descargar/{pdf_name}','{cliente} · PDF'); return false;\">Ver PDF</a>"

    # Dispara el webhook de n8n para avisar por WhatsApp que se generó el
    # presupuesto - no vuelve a llamar al runner (el webhook va directo al
    # nodo de WhatsApp), así que no duplica la fila en la Sheet ni los
    # archivos. Si falla, no rompe la generación que ya se hizo bien.
    try:
        r_wh = httpx.post(
            N8N_WEBHOOK_URL,
            json={"cliente": cliente, "url": url, "estrategia": estrategia, "dias_cobertura": dias_cobertura},
            timeout=15,
        )
        whatsapp_resultado = "Enviado" if r_wh.status_code < 300 else f"Error HTTP {r_wh.status_code}"
    except Exception as e:
        whatsapp_resultado = f"Error: {e}"

    # Registro en la Sheet (bitácora) - si esto falla no afecta nada más.
    try:
        httpx.post(f"{RUNNER_URL}/whatsapp/log", json={"cliente": cliente, "resultado": whatsapp_resultado}, timeout=10)
    except Exception:
        pass

    resultado = f'<div class="msg ok">Listo para <strong>{cliente}</strong>. {links}'
    if whatsapp_resultado != "Enviado":
        resultado += f' <br><small>(no se pudo avisar por WhatsApp: {whatsapp_resultado})</small>'
    resultado += "</div>"
    return render("Generar presupuesto", FORM_HTML.format(resultado=resultado), activo="/generar")


@app.post("/generar-brief", response_class=HTMLResponse)
def generar_brief(
    cliente: str = Form(...),
    url: str = Form(""),
    brief: str = Form(...),
    precio_base: int = Form(...),
    precio_total: int = Form(...),
    dias_cobertura: int = Form(30),
):
    """Igual que /generar pero sin URL/Lighthouse - para cuando todavía no
    hay sitio o el cliente prefiere no compartir el link. El alcance y el
    precio los carga el usuario a mano (ver agente_presupuesto_seo.
    generar_presupuesto_brief)."""
    try:
        r = httpx.post(
            f"{RUNNER_URL}/presupuesto/brief",
            json={
                "cliente": cliente, "brief": brief, "precio_base": precio_base,
                "precio_total": precio_total, "url": url, "dias_cobertura": dias_cobertura,
            },
            timeout=60,
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
    links = f"<a href=\"#\" onclick=\"abrirModal('/descargar/{html_name}','{cliente} · HTML'); return false;\">Ver HTML</a>"
    if pdf_name:
        links += f" · <a href=\"#\" onclick=\"abrirModal('/descargar/{pdf_name}','{cliente} · PDF'); return false;\">Ver PDF</a>"

    try:
        r_wh = httpx.post(
            N8N_WEBHOOK_URL,
            json={"cliente": cliente, "url": url, "dias_cobertura": dias_cobertura},
            timeout=15,
        )
        whatsapp_resultado = "Enviado" if r_wh.status_code < 300 else f"Error HTTP {r_wh.status_code}"
    except Exception as e:
        whatsapp_resultado = f"Error: {e}"

    try:
        httpx.post(f"{RUNNER_URL}/whatsapp/log", json={"cliente": cliente, "resultado": whatsapp_resultado}, timeout=10)
    except Exception:
        pass

    resultado = f'<div class="msg ok">Listo para <strong>{cliente}</strong> (sin auditoría, desde brief). {links}'
    if whatsapp_resultado != "Enviado":
        resultado += f' <br><small>(no se pudo avisar por WhatsApp: {whatsapp_resultado})</small>'
    resultado += "</div>"
    return render("Generar presupuesto", FORM_HTML.format(resultado=resultado), activo="/generar")


@app.get("/presupuestos", response_class=HTMLResponse)
def ver_presupuestos():
    try:
        r = httpx.get(f"{RUNNER_URL}/presupuestos", timeout=30)
        data = r.json().get("presupuestos", [])
    except Exception as e:
        return render("Presupuestos generados", f'<h1>Presupuestos generados</h1><div class="msg error">No se pudo leer la Sheet: {e}</div>', activo="/presupuestos")

    zona_subida = """
    <div id="zonaSubidaHtml" class="msg"
         style="border:2px dashed var(--line); text-align:center; padding:28px; cursor:pointer; margin-top:24px;"
         ondragover="event.preventDefault(); this.style.borderColor='var(--amber)';"
         ondragleave="this.style.borderColor='var(--line)';"
         ondrop="subirHtmlPresupuesto(event)"
         onclick="document.getElementById('inputHtmlPresupuesto').click()">
      📄 Arrastrá acá un HTML de presupuesto ya armado, o hacé click para elegir el archivo
      <input type="file" id="inputHtmlPresupuesto" accept=".html" style="display:none" onchange="subirHtmlPresupuesto(event)">
    </div>
    <div id="formConfirmarHtml"></div>
    """

    if not data:
        contenido = f'<h1>Presupuestos generados</h1><p class="empty">Todavía no generaste ninguno.</p>{zona_subida}'
        return render("Presupuestos generados", contenido, activo="/presupuestos")

    vigentes = sum(1 for p in data if p.get("cobertura_vigente"))
    vencidos = sum(1 for p in data if p.get("cobertura_vigente") is False)

    # Mapa negocio -> email para sugerir el destinatario al mandar el
    # presupuesto, en vez de un campo en blanco. Prioridad: el remitente
    # real de un hilo en la bandeja de entrada (contacto confirmado) por
    # sobre el email scrapeado en leads_tracking.
    mapa_email: dict[str, str] = {}
    try:
        r_leads = httpx.get(f"{RUNNER_URL}/leads", params={"limite": 1000}, timeout=30)
        for x in r_leads.json().get("leads_tracking", {}).get("items", []):
            if x.get("email") and x.get("negocio"):
                mapa_email.setdefault(x["negocio"].strip().lower(), x["email"])
    except Exception:
        pass
    try:
        r_mails = httpx.get(f"{RUNNER_URL}/mails/estado", params={"dias": 90}, timeout=30)
        for h in r_mails.json().get("bandeja_entrada", {}).get("items", []):
            if h.get("es_lead_conocido") and h.get("negocio") and h.get("remitente"):
                mapa_email[h["negocio"].strip().lower()] = h["remitente"]
    except Exception:
        pass

    def _email_sugerido(cliente: str) -> str:
        c = (cliente or "").strip().lower()
        if not c:
            return ""
        if c in mapa_email:
            return mapa_email[c]
        for negocio, email in mapa_email.items():
            if negocio and (negocio in c or c in negocio):
                return email
        return ""

    filas = []
    for p in reversed(data):  # mas recientes primero
        if p.get("cobertura_vigente") is True:
            badge = f'<span class="badge badge-ok">Vigente hasta {p["fecha_vencimiento_cobertura"]}</span>'
        elif p.get("cobertura_vigente") is False:
            badge = f'<span class="badge badge-bad">Venció {p["fecha_vencimiento_cobertura"]}</span>'
        else:
            badge = '<span class="badge badge-warn">Sin datos</span>'
        html_name = Path(p["html"]).name if p.get("html") else None
        pdf_name = Path(p["pdf"]).name if p.get("pdf") else None
        html_url = f'/descargar/{html_name}' if html_name else None
        pdf_url = f'/descargar/{pdf_name}' if pdf_name else None
        cliente_attr = p['cliente'].replace('"', "&quot;")
        html_link = f"<a href=\"#\" onclick=\"abrirModal('{html_url}','{p['cliente']} · HTML'); return false;\">Ver HTML</a>" if html_url else "-"
        pdf_link = f"<a href=\"#\" onclick=\"abrirModal('{pdf_url}','{p['cliente']} · PDF'); return false;\">Ver PDF</a>" if pdf_url else "-"
        # Copiar ruta en vez de "abrir" - Chrome bloquea la navegación a
        # file:// desde una página http:// (probado en vivo, no hay forma
        # real de abrir el explorador de archivos desde el navegador).
        nombre_archivo = pdf_name or html_name
        if nombre_archivo:
            ruta_local = f"{HOST_PROJECT_ROOT}/presupuestos_generados/{nombre_archivo}".replace("'", "\\'")
            local_link = f'<button type="button" class="btn-mail" style="margin:0;" onclick="copiarRuta(this, \'{ruta_local}\')">📋 Copiar ruta</button>'
        else:
            local_link = "-"
        email_sug = _email_sugerido(p['cliente'])
        mail_btn = (
            f'<button type="button" class="btn-mail" data-cliente="{cliente_attr}" data-pdf="{pdf_name}" '
            f'data-email="{email_sug}" onclick="enviarMailPresupuesto(this)">✉ Enviar mail</button>' if pdf_name else ""
        )
        precio = f'${int(p["precio_total"]):,}'.replace(",", ".") if p.get("precio_total") else "-"
        url_attr = p['url'].replace('"', "&quot;")
        filas.append(f"""<tr data-fila="{p['fila']}">
          <td><span class="v-mostrado">{p['fecha']}</span><input class="v-editable campo-fecha" style="display:none" value="{p['fecha']}"></td>
          <td><span class="v-mostrado">{p['cliente']}</span><input class="v-editable campo-cliente" style="display:none" value="{cliente_attr}"></td>
          <td><span class="v-mostrado">{p['url']}</span><input class="v-editable campo-url" style="display:none" value="{url_attr}"></td>
          <td><span class="v-mostrado">{precio}</span><input class="v-editable campo-precio" style="display:none" value="{p.get('precio_total') or ''}"></td>
          <td><span class="v-mostrado">{p['dias_cobertura']} días</span><input class="v-editable campo-dias" style="display:none" value="{p['dias_cobertura']}"></td>
          <td>{badge}</td>
          <td>{html_link} · {pdf_link} · {local_link}</td>
          <td>{mail_btn}</td>
          <td><button type="button" class="btn-mail btn-editar" onclick="toggleEditarFila(this)">✏️</button></td>
        </tr>""")

    contenido = f"""
    <h1>Presupuestos generados</h1>
    <div class="stat"><b>{len(data)}</b><span>Total</span></div>
    <div class="stat"><b>{vigentes}</b><span>Con cobertura vigente</span></div>
    <div class="stat"><b>{vencidos}</b><span>Cobertura vencida</span></div>
    {_tabla_filtrable("tabla-presupuestos", filas, ["Fecha", "Cliente", "Sitio", "Precio", "Cobertura", "Estado", "Archivos", "Mail", "Editar"])}
    {zona_subida}
    """
    return render("Presupuestos generados", contenido, activo="/presupuestos")


@app.post("/presupuestos/{fila}/editar")
async def editar_presupuesto(fila: int, fecha: str = Form(...), cliente: str = Form(...), url: str = Form(...), precio_total: str = Form(...), dias_cobertura: str = Form(...)):
    try:
        r = httpx.post(
            f"{RUNNER_URL}/presupuesto/{fila}/editar",
            json={"fecha": fecha, "cliente": cliente, "url": url, "precio_total": precio_total, "dias_cobertura": dias_cobertura},
            timeout=15,
        )
        return r.json()
    except Exception as e:
        return {"ok": False, "detalle": str(e)}


@app.post("/presupuestos/subir-html")
async def subir_html_presupuesto(archivo: UploadFile = File(...)):
    try:
        contenido = await archivo.read()
        files = {"archivo": (archivo.filename, contenido, archivo.content_type or "text/html")}
        r = httpx.post(f"{RUNNER_URL}/presupuestos/subir-html", files=files, timeout=30)
        return r.json()
    except Exception as e:
        return {"ok": False, "detalle": str(e)}


@app.post("/presupuestos/confirmar-html-guardar")
async def confirmar_html_presupuesto(
    html_path: str = Form(...), cliente: str = Form(...), url: str = Form(...),
    precio_base: str = Form(""), precio_total: str = Form(""), dias_cobertura: str = Form("30"),
):
    try:
        r = httpx.post(f"{RUNNER_URL}/presupuestos/confirmar-html", json={
            "html_path": html_path, "cliente": cliente, "url": url,
            "precio_base": precio_base, "precio_total": precio_total,
            "dias_cobertura": int(dias_cobertura) if dias_cobertura else 30,
        }, timeout=60)
        return r.json()
    except Exception as e:
        return {"ok": False, "detalle": str(e)}


@app.post("/presupuestos/enviar-mail")
async def enviar_mail_presupuesto(cliente: str = Form(...), pdf_nombre: str = Form(...), email: str = Form(...)):
    """Proxy hacia el runner - el dashboard no tiene acceso directo a Gmail,
    todo pasa por el runner (único contenedor con las credenciales)."""
    try:
        r = httpx.post(
            f"{RUNNER_URL}/presupuesto/enviar-mail",
            json={"cliente": cliente, "email": email, "pdf_nombre": pdf_nombre},
            timeout=30,
        )
        data = r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}
    if r.status_code != 200:
        return {"ok": False, "error": data.get("detail", data)}
    return data


def _tabla_filtrable(tabla_id: str, filas: list[str], columnas: list[str], limite_inicial: int | None = None) -> str:
    """Tabla con una caja de busqueda arriba que filtra filas en el cliente
    (JS, sin recargar la pagina) - matchea contra el texto completo de la
    fila, no columna por columna.

    Si limite_inicial esta seteado, las filas que exceden ese numero
    arrancan ocultas (clase fila-extra) y aparece un boton "Ver más" que
    las despliega - para no tener listas larguísimas siempre abiertas."""
    if not filas:
        return '<p class="empty">Sin datos todavía.</p>'
    encabezado = "".join(f"<th>{c}</th>" for c in columnas)

    if limite_inicial is not None and len(filas) > limite_inicial:
        visibles = filas[:limite_inicial]
        ocultas = [f.replace("<tr>", '<tr class="fila-extra" style="display:none">', 1) for f in filas[limite_inicial:]]
        filas_html = "".join(visibles) + "".join(ocultas)
        boton = (
            f'<button type="button" class="ver-mas" onclick="toggleVerMas(this, \'{tabla_id}\')" '
            f'data-ver-mas="Ver más ({len(ocultas)})" data-ver-menos="Ver menos">Ver más ({len(ocultas)})</button>'
        )
    else:
        filas_html = "".join(filas)
        boton = ""

    return f"""
    <input type="text" class="filtro" placeholder="Filtrar..." oninput="filtrarTabla('{tabla_id}', this.value)">
    <table id="{tabla_id}">
      <thead><tr>{encabezado}</tr></thead>
      <tbody>{filas_html}</tbody>
    </table>
    {boton}
    """


@app.get("/leads", response_class=HTMLResponse)
def ver_leads():
    try:
        r = httpx.get(f"{RUNNER_URL}/leads", params={"limite": 50}, timeout=30)
        data = r.json()
    except Exception as e:
        return render("Clientes / Leads", f'<h1>Clientes / Leads</h1><div class="msg error">No se pudo leer la Sheet: {e}</div>', activo="/leads")

    lt = data.get("leads_tracking", {"total": 0, "items": []})
    la = data.get("leads_automatizacion", {"total": 0, "items": []})
    sm = data.get("seguimiento_manual", {"total": 0, "items": []})

    filas_lt = [
        f"<tr><td>{x['negocio']}</td><td>{x['email']}</td><td>{x['ciudad']}</td>"
        f"<td>{x['rubro']}</td><td>{x['estado_envio']}</td></tr>"
        for x in lt["items"]
    ]
    filas_la = [
        f"<tr><td>{x['fecha_envio']}</td><td>{x['negocio']}</td><td>{x['ciudad']}</td>"
        f"<td>{x['rubro']}</td><td>{x['mail']}</td><td>{x['respondio']}</td></tr>"
        for x in la["items"]
    ]
    filas_sm = [
        f"<tr><td>{x['fecha']}</td><td>{x['empresa']}</td><td>{x['ciudad']}</td>"
        f"<td><a href=\"{x['sitio']}\" target=\"_blank\">{x['sitio']}</a></td><td>{x['fuente']}</td></tr>"
        for x in sm["items"]
    ]

    contenido = f"""
    <h1>Leads</h1>
    <div class="stat"><b>{lt['total']}</b><span>Agencias con email (leads_tracking)</span></div>
    <div class="stat"><b>{la['total']}</b><span>Automatización/RPA (leads_automatizacion)</span></div>
    <div class="stat"><b>{sm['total']}</b><span>Sin email, seguimiento manual</span></div>

    <h2 style="margin-top:36px;font-size:16px;">Agencias con email real (últimas {len(lt['items'])} de {lt['total']})</h2>
    {_tabla_filtrable("tabla-leads-tracking", filas_lt, ["Negocio", "Email", "Ciudad", "Rubro", "Estado envío"])}

    <h2 style="margin-top:36px;font-size:16px;">Automatización/RPA (últimas {len(la['items'])} de {la['total']})</h2>
    {_tabla_filtrable("tabla-leads-automatizacion", filas_la, ["Fecha envío", "Negocio", "Ciudad", "Rubro", "Mail", "Respondió"])}

    <h2 style="margin-top:36px;font-size:16px;">Sin email - seguimiento manual (últimas {len(sm['items'])} de {sm['total']})</h2>
    <p class="empty" style="padding:0 0 8px;">Estas empresas tienen sitio real pero no se les encontró email - hay que entrar al formulario de contacto a mano.</p>
    {_tabla_filtrable("tabla-seguimiento-manual", filas_sm, ["Fecha", "Empresa", "Ciudad", "Sitio", "Fuente"])}
    """
    return render("Leads", contenido, activo="/leads")


@app.get("/clientes", response_class=HTMLResponse)
def ver_clientes():
    try:
        r = httpx.get(f"{RUNNER_URL}/clientes", timeout=30)
        data = r.json()
    except Exception as e:
        return render("Clientes", f'<h1>Clientes</h1><div class="msg error">No se pudo leer la Sheet: {e}</div>', activo="/clientes")

    items = data.get("items", [])
    pagados = sum(1 for c in items if c["pagado"].strip().lower() == "si")
    pendientes = len(items) - pagados

    encabezado_extra = '<a href="/clientes/nuevo" style="margin-left:16px;">+ Agregar cliente</a>'

    if not items:
        contenido = f"""
        <h1>Clientes {encabezado_extra}</h1>
        <p class="empty">Todavía no confirmaste ningún cliente. Andá a "Presupuestos generados" y confirmá uno desde ahí.</p>
        """
        return render("Clientes", contenido, activo="/clientes")

    filas = []
    for c in items:
        html_name = Path(c["html"]).name if c.get("html") else None
        pdf_name = Path(c["pdf"]).name if c.get("pdf") else None
        html_link = f"<a href=\"#\" onclick=\"abrirModal('/descargar/{html_name}','{c['cliente']} · HTML'); return false;\">Ver HTML</a>" if html_name else "-"
        pdf_link = f"<a href=\"#\" onclick=\"abrirModal('/descargar/{pdf_name}','{c['cliente']} · PDF'); return false;\">Ver PDF</a>" if pdf_name else "-"
        portal_link = f'<a href="{c["url"]}" target="_blank">Abrir portal</a>' if c.get("url") else "-"

        pagado_si = c["pagado"].strip().lower() == "si"
        badge = '<span class="badge badge-ok">Pagado</span>' if pagado_si else '<span class="badge badge-bad">Pendiente</span>'
        try:
            balance = "$0" if pagado_si else f'${int(float(c["precio_total"])):,}'.replace(",", ".")
        except (ValueError, TypeError):
            balance = "-"

        toggle_form = f"""<form method="post" action="/clientes/{c['fila']}/pagado" style="display:inline;margin:0;">
          <input type="hidden" name="pagado" value="{'false' if pagado_si else 'true'}">
          <button type="submit" class="btn-mail" style="margin:0;">{'Marcar pendiente' if pagado_si else 'Marcar pagado'}</button>
        </form>"""

        if c.get("carpeta_local"):
            ruta_carpeta = f"{HOST_PROJECT_ROOT}/{c['carpeta_local']}".replace("'", "\\'")
            carpeta_html = (
                f'<code style="font-size:12px;">{c["carpeta_local"]}</code><br>'
                f'<button type="button" class="btn-mail" style="margin:4px 0 0;" onclick="copiarRuta(this, \'{ruta_carpeta}\')">📋 Copiar ruta</button>'
            )
        else:
            carpeta_html = "-"

        filas.append(f"""<tr>
          <td>{c['cliente']}</td><td>{portal_link}</td><td>{html_link} · {pdf_link}</td>
          <td>{balance}</td><td>{badge}</td><td>{carpeta_html}</td><td>{toggle_form}</td>
        </tr>""")

    contenido = f"""
    <h1>Clientes {encabezado_extra}</h1>
    <div class="stat"><b>{len(items)}</b><span>Total confirmados</span></div>
    <div class="stat"><b>{pagados}</b><span>Pagados</span></div>
    <div class="stat"><b>{pendientes}</b><span>Pendientes de pago</span></div>
    {_tabla_filtrable("tabla-clientes", filas, ["Cliente", "Portal", "Presupuesto", "Balance", "Pago", "Carpeta local", "Acción"])}
    """
    return render("Clientes", contenido, activo="/clientes")


@app.get("/clientes/nuevo", response_class=HTMLResponse)
def nuevo_cliente_form():
    try:
        r = httpx.get(f"{RUNNER_URL}/presupuestos", timeout=30)
        presupuestos = r.json().get("presupuestos", [])
    except Exception as e:
        return render("Agregar cliente", f'<h1>Agregar cliente</h1><div class="msg error">No se pudo leer presupuestos: {e}</div>', activo="/clientes")

    opciones = "".join(
        f'<option value="{Path(p["html"]).name}">{p["cliente"]} · {p["fecha"]} · {p["url"]}</option>'
        for p in reversed(presupuestos) if p.get("html")
    )
    if not opciones:
        contenido = '<h1>Agregar cliente</h1><p class="empty">Todavía no generaste ningún presupuesto para sincronizar.</p>'
        return render("Agregar cliente", contenido, activo="/clientes")

    contenido = f"""
    <h1>Agregar cliente confirmado</h1>
    <form method="post" action="/clientes/agregar">
      <label>¿Qué presupuesto es? (sincroniza cliente, URL, precio y archivos automáticamente)
        <select name="html_nombre" required>
          <option value="" disabled selected>Elegí un presupuesto...</option>
          {opciones}
        </select>
      </label>
      <button type="submit">Confirmar cliente</button>
    </form>
    """
    return render("Agregar cliente", contenido, activo="/clientes")


@app.post("/clientes/agregar", response_class=HTMLResponse)
def agregar_cliente(html_nombre: str = Form(...)):
    try:
        r = httpx.get(f"{RUNNER_URL}/presupuestos", timeout=30)
        presupuestos = r.json().get("presupuestos", [])
    except Exception as e:
        return render("Clientes", f'<h1>Clientes</h1><div class="msg error">No se pudo leer presupuestos: {e}</div>', activo="/clientes")

    match = next((p for p in presupuestos if p.get("html") and Path(p["html"]).name == html_nombre), None)
    if not match:
        return render("Clientes", '<h1>Clientes</h1><div class="msg error">No se encontró ese presupuesto.</div>', activo="/clientes")

    try:
        httpx.post(f"{RUNNER_URL}/clientes", json={
            "cliente": match["cliente"], "url": match["url"],
            "precio_total": str(match.get("precio_total") or ""),
            "html_path": match.get("html") or "", "pdf_path": match.get("pdf") or "",
        }, timeout=30)
    except Exception as e:
        return render("Clientes", f'<h1>Clientes</h1><div class="msg error">No se pudo confirmar: {e}</div>', activo="/clientes")

    return ver_clientes()


@app.post("/clientes/{fila}/pagado", response_class=HTMLResponse)
def marcar_pagado(fila: int, pagado: str = Form(...)):
    try:
        httpx.post(f"{RUNNER_URL}/clientes/{fila}/pagado", json={"pagado": pagado.lower() == "true"}, timeout=15)
    except Exception:
        pass
    return ver_clientes()


@app.get("/mails", response_class=HTMLResponse)
def ver_mails():
    try:
        r = httpx.get(f"{RUNNER_URL}/mails/estado", params={"dias": 30}, timeout=60)
        data = r.json()
    except Exception as e:
        return render("Mails", f'<h1>Mails</h1><div class="msg error">No se pudo leer Gmail/Sheets: {e}</div>', activo="/mails")

    try:
        r_wa = httpx.get(f"{RUNNER_URL}/whatsapp/enviados", timeout=30)
        whatsapp = r_wa.json()
    except Exception:
        whatsapp = {"total": 0, "items": []}

    pend = data.get("pendientes_de_enviar", {"total": 0, "items": []})
    enviados = data.get("ya_enviados", {"total": 0, "items": []})
    bandeja = data.get("bandeja_entrada", {"total_hilos_activos": 0, "faltan_responder": 0, "items": []})

    hilos = bandeja["items"]
    leads_sin_responder = [h for h in hilos if h["falta_responder"] and h["es_lead_conocido"]]
    otros_sin_responder = [h for h in hilos if h["falta_responder"] and not h["es_lead_conocido"]]
    pendientes_contestar = leads_sin_responder + otros_sin_responder

    def _fila_hilo(h):
        asunto = h["asunto"] or "(sin asunto)"
        if h.get("thread_id"):
            # authuser=email (no /u/0/) para forzar SIEMPRE la cuenta del
            # negocio, sin importar en qué "uN" esté logueada en el
            # navegador - si se deja u/0 fijo, abre la cuenta que sea que
            # esté en esa posición, que puede no ser la del negocio.
            gmail_url = f"https://mail.google.com/mail/?authuser={GMAIL_ACCOUNT}#all/{h['thread_id']}"
            asunto = f'<a href="{gmail_url}" target="_blank">{asunto}</a>'
        return (f"<tr><td>{h['negocio'] or '-'}</td><td>{h['remitente']}</td>"
                f"<td>{asunto}</td><td>{h['fecha']}</td><td>{h['cantidad_mensajes']}</td></tr>")

    filas_pendientes_contestar = [_fila_hilo(h) for h in pendientes_contestar]
    filas_recibidos = [_fila_hilo(h) for h in hilos]

    filas_enviados_campana = [
        f"<tr><td>{x['negocio']}</td><td>{x['email']}</td><td>{x['ciudad']}</td></tr>"
        for x in enviados["items"][:50]
    ]
    filas_pend_envio = [
        f"<tr><td>{x['negocio']}</td><td>{x['email']}</td><td>{x['ciudad']}</td></tr>"
        for x in pend["items"][:50]
    ]
    filas_whatsapp = [
        f"<tr><td>{x['fecha']}</td><td>{x['hora']}</td><td>{x['cliente']}</td><td>{x['resultado']}</td></tr>"
        for x in whatsapp["items"]
    ]

    contenido = f"""
    <h1>Mails</h1>
    <a class="stat" href="#enviados"><b>{enviados['total']}</b><span>Enviados (campaña)</span></a>
    <a class="stat" href="#recibidos"><b>{bandeja['total_hilos_activos']}</b><span>Recibidos (últimos 30 días)</span></a>
    <a class="stat" href="#pendientes-contestar"><b>{len(pendientes_contestar)}</b><span>⚠ Pendientes de contestar</span></a>

    <h2 id="pendientes-contestar" style="margin-top:36px;font-size:16px;color:var(--amber);">⚠ Pendientes de contestar ({len(pendientes_contestar)})</h2>
    <p class="empty" style="padding:0 0 8px;">{len(leads_sin_responder)} son leads que tenés en la Sheet, {len(otros_sin_responder)} son otros mensajes (notificaciones, newsletters, etc.). Hacé click en el asunto para abrir el mail en Gmail.</p>
    {_tabla_filtrable("tabla-pendientes-contestar", filas_pendientes_contestar, ["Negocio", "De", "Asunto", "Fecha", "Mensajes"], limite_inicial=10)}

    <h2 id="enviados" style="margin-top:36px;font-size:16px;">📤 Enviados - campaña de primer contacto ({enviados['total']})</h2>
    {_tabla_filtrable("tabla-enviados", filas_enviados_campana, ["Negocio", "Email", "Ciudad"], limite_inicial=10)}

    <h2 style="margin-top:16px;font-size:14px;color:var(--text-dim);">Todavía sin mandar ({pend['total']})</h2>
    {_tabla_filtrable("tabla-pendientes-envio", filas_pend_envio, ["Negocio", "Email", "Ciudad"], limite_inicial=10)}

    <h2 id="recibidos" style="margin-top:36px;font-size:16px;">📥 Recibidos - bandeja de entrada ({bandeja['total_hilos_activos']})</h2>
    <p class="empty" style="padding:0 0 8px;">Hacé click en el asunto para abrir el mail en Gmail.</p>
    {_tabla_filtrable("tabla-recibidos", filas_recibidos, ["Negocio", "De", "Asunto", "Fecha", "Mensajes"], limite_inicial=10)}

    <h2 id="whatsapp" style="margin-top:36px;font-size:16px;">📱 WhatsApp enviados - registro ({whatsapp['total']})</h2>
    {_tabla_filtrable("tabla-whatsapp", filas_whatsapp, ["Fecha", "Hora", "Cliente", "Resultado"], limite_inicial=10)}
    """
    return render("Mails", contenido, activo="/mails")


@app.get("/estado", response_class=HTMLResponse)
def ver_estado():
    try:
        r = httpx.get(f"{RUNNER_URL}/procesos", timeout=15)
        procesos = r.json().get("procesos", [])
    except Exception as e:
        return render("Estado del sistema", f'<h1>Estado del sistema</h1><div class="msg error">No se pudo leer el estado: {e}</div>', activo="/estado")

    intro = (
        '<p class="empty" style="padding:0 0 16px;">Scripts que corren aparte de Docker '
        '(loop_caza.py, send_loop.py, y los que se sumen después) avisan acá cada vez que '
        'completan un ciclo. Si no hay actividad hace rato, probablemente se cortaron.</p>'
    )

    if not procesos:
        contenido = f'<h1>Estado del sistema</h1>{intro}<p class="empty">Todavía ningún script reportó actividad.</p>'
        return render("Estado del sistema", contenido, activo="/estado")

    tarjetas = ""
    for p in sorted(procesos, key=lambda x: x["proceso"]):
        dot = "🟢" if p["activo"] else "🔴"
        estado_txt = "Activo" if p["activo"] else "Sin actividad reciente"
        if p.get("minutos_desde_ultima") is not None:
            mins = p["minutos_desde_ultima"]
            hace = f'hace {int(mins)} min' if mins < 60 else f'hace {mins/60:.1f} hs'
        else:
            hace = "nunca"
        detalle_html = f'<div style="font-size:12px;color:var(--text-dim);margin-top:6px;">{p["detalle"]}</div>' if p.get("detalle") else ""
        resumen_html = f'<div style="font-size:13px;color:var(--amber);margin-top:8px;font-weight:600;">{p["resumen_24h"]}</div>' if p.get("resumen_24h") else ""

        botones = ""
        if p.get("controlable"):
            botones = f"""<div style="margin-top:10px;">
              <button type="button" class="btn-mail" style="margin:0 6px 0 0;" onclick="controlarProceso(this, '{p['proceso']}', 'iniciar')">▶ Iniciar</button>
              <button type="button" class="btn-mail" style="margin:0;" onclick="controlarProceso(this, '{p['proceso']}', 'detener')">⏹ Detener</button>
            </div>"""

        tarjetas += f"""
        <div class="stat" style="display:block;min-width:240px;">
          <div style="font-size:16px;font-weight:600;">{dot} {p['proceso']}</div>
          <div style="font-size:13px;color:var(--text-dim);margin-top:4px;">{estado_txt} · {hace}</div>
          <div style="font-size:12px;color:var(--text-dim);margin-top:4px;">Última: {p['ultima_actividad'] or '-'}</div>
          {detalle_html}
          {resumen_html}
          {botones}
        </div>"""

    contenido = f"""
    <h1>Estado del sistema</h1>
    {intro}
    <div>{tarjetas}</div>
    """
    return render("Estado del sistema", contenido, activo="/estado")


@app.post("/estado/{nombre}/iniciar")
async def iniciar_script(nombre: str):
    try:
        r = httpx.post(f"{RUNNER_URL}/procesos/{nombre}/iniciar", timeout=15)
        return r.json()
    except Exception as e:
        return {"ok": False, "detalle": str(e)}


@app.post("/estado/{nombre}/detener")
async def detener_script(nombre: str):
    try:
        r = httpx.post(f"{RUNNER_URL}/procesos/{nombre}/detener", timeout=15)
        return r.json()
    except Exception as e:
        return {"ok": False, "detalle": str(e)}


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
