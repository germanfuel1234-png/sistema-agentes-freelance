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
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from playwright.sync_api import sync_playwright
from pydantic import BaseModel

DATA_DIR = Path("/data")
AGENTES_DIR = DATA_DIR / "agentes"
PRESUPUESTO_SCRIPT = AGENTES_DIR / "agente_presupuesto_seo.py"
OUTPUT_DIR = DATA_DIR / "presupuestos_generados"
CREDENTIALS_FILE = DATA_DIR / "credentials.json"
TOKEN_FILE = DATA_DIR / "token.json"

PRESUPUESTOS_TAB = "presupuestos_generados"
PRESUPUESTOS_HEADERS = [
    "Fecha", "Cliente", "URL", "Precio Base", "Precio Total",
    "Dias Cobertura", "Fecha Inicio Cobertura", "HTML", "PDF",
]

sys.path.insert(0, str(AGENTES_DIR))
sys.path.insert(0, str(DATA_DIR))

app = FastAPI(title="runner interno - sistema_agentes_freelance")


class PresupuestoRequest(BaseModel):
    cliente: str
    url: str
    estrategia: str = "mobile"
    generar_pdf: bool = True
    dias_cobertura: int = 30


def _sheets_client():
    """SheetsClient apuntando a las credenciales montadas en /data (la raiz
    del repo). Import diferido: si algun dia falla la auth de Sheets, no
    tira abajo /health ni /presupuesto (que igual generan el archivo)."""
    from core.sheets_client import SheetsClient
    return SheetsClient(credentials_file=str(CREDENTIALS_FILE), token_file=str(TOKEN_FILE))


def _gmail_service():
    """GmailService apuntando al token_gmail.json montado en /data - ya
    tiene permiso de lectura (gmail.readonly) ademas de envio, no hace
    falta pedir autorizacion de nuevo."""
    from services.gmail_service import GmailService
    return GmailService(credentials_file=str(CREDENTIALS_FILE), token_file=str(DATA_DIR / "token_gmail.json"))


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

    # El script imprime una linea "RESULTADO_JSON:{...}" al final con los
    # datos estructurados (precio, scores) - evita tener que scrapear el
    # texto legible por humanos que imprime arriba.
    datos = {}
    for linea in resultado.stdout.splitlines():
        if linea.startswith("RESULTADO_JSON:"):
            datos = json.loads(linea[len("RESULTADO_JSON:"):])
            break

    html_path = Path(datos["archivo_html"]) if datos.get("archivo_html") else None
    if not html_path:
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

    # Registrar en la Sheet para el panel de "presupuestos generados" +
    # cobertura. Si falla (ej. token vencido), no se pierde el presupuesto
    # ya generado - solo se avisa en la respuesta, no se rompe todo.
    hoy = datetime.now()
    try:
        sheets = _sheets_client()
        sheets.add_sheet(PRESUPUESTOS_TAB, headers=PRESUPUESTOS_HEADERS)
        fila = [
            hoy.strftime("%d/%m/%Y"), req.cliente, req.url,
            str(datos.get("precio_base", "")), str(datos.get("precio_total", "")),
            str(req.dias_cobertura), hoy.strftime("%d/%m/%Y"),
            str(html_path), respuesta.get("pdf_path", ""),
        ]
        sheets.write_range(f"'{PRESUPUESTOS_TAB}'!A2", [fila], append=True)
        respuesta["registrado_en_sheet"] = True
    except Exception as e:
        respuesta["registrado_en_sheet"] = False
        respuesta["error_sheet"] = str(e)

    return respuesta


@app.get("/presupuestos")
def listar_presupuestos():
    """Lista los presupuestos generados, con la cobertura calculada al
    vuelo (vigente/vencido) comparando fecha inicio + dias contra hoy -
    no se guarda el estado, siempre se recalcula para que sea exacto."""
    sheets = _sheets_client()
    filas = sheets.read_range(f"'{PRESUPUESTOS_TAB}'!A2:I10000")
    hoy = datetime.now()
    resultado = []
    for fila in filas:
        if not fila or not fila[0]:
            continue
        fila = fila + [""] * (9 - len(fila))
        try:
            fecha_inicio = datetime.strptime(fila[6], "%d/%m/%Y") if fila[6] else None
            dias = int(fila[5]) if fila[5] else 0
        except ValueError:
            fecha_inicio, dias = None, 0
        vigente = None
        vence = None
        if fecha_inicio and dias:
            vence = fecha_inicio + timedelta(days=dias)
            vigente = hoy <= vence
        resultado.append({
            "fecha": fila[0], "cliente": fila[1], "url": fila[2],
            "precio_base": fila[3], "precio_total": fila[4],
            "dias_cobertura": fila[5], "fecha_inicio_cobertura": fila[6],
            "fecha_vencimiento_cobertura": vence.strftime("%d/%m/%Y") if vence else None,
            "cobertura_vigente": vigente,
            "html": fila[7], "pdf": fila[8],
        })
    return {"presupuestos": resultado}


@app.get("/leads")
def listar_leads(limite: int = 100):
    """Junta las 3 pestañas de leads en una sola respuesta:
    leads_tracking.csv (agencias con email real, vía loop_caza.py),
    leads_automatizacion (vía loop_indeed.py, ángulo automatización/RPA),
    seguimiento_manual (empresas reales sin email, revisión a mano).
    `limite` corta cada lista a los N más recientes para no mandar miles
    de filas de una - el dashboard solo necesita un vistazo reciente."""
    sheets = _sheets_client()

    leads_tracking = []
    for lead in sheets.get_all_leads():
        leads_tracking.append({
            "negocio": lead.business_name, "email": lead.email, "ciudad": lead.city,
            "pais": lead.country, "rubro": lead.industry,
            "estado_envio": lead.send_status.value if lead.send_status else "",
            "fuente": lead.source,
        })

    leads_automatizacion = []
    for f in sheets.read_range("'leads_automatizacion'!A2:L10000"):
        if not f or not f[0]:
            continue
        f = f + [""] * (9 - len(f))
        leads_automatizacion.append({
            "fecha_envio": f[0], "negocio": f[1], "track": f[2], "rubro": f[3],
            "ciudad": f[4], "mail": f[6], "respondio": f[8] if len(f) > 8 else "",
        })

    seguimiento_manual = []
    for f in sheets.read_range("'seguimiento_manual'!A2:G10000"):
        if not f or not f[0]:
            continue
        f = f + [""] * (7 - len(f))
        seguimiento_manual.append({
            "fecha": f[0], "empresa": f[1], "ciudad": f[2], "sitio": f[3],
            "formulario": f[4], "fuente": f[6],
        })

    return {
        "leads_tracking": {"total": len(leads_tracking), "items": leads_tracking[-limite:][::-1]},
        "leads_automatizacion": {"total": len(leads_automatizacion), "items": leads_automatizacion[-limite:][::-1]},
        "seguimiento_manual": {"total": len(seguimiento_manual), "items": seguimiento_manual[-limite:][::-1]},
    }


@app.get("/mails/estado")
def estado_mails(dias: int = 30):
    """Resumen de mails: cuántos leads con email real todavía no recibieron
    nada (send_status distinto de "Enviado"), y estado de la bandeja de
    entrada real (hilos recientes, marcando cuáles quedaron sin responder
    de nuestra parte). Cruza el remitente de cada hilo contra los leads
    conocidos para decir si es un lead identificado o no."""
    sheets = _sheets_client()
    todos = sheets.get_all_leads()

    pendientes_envio = [
        {"negocio": l.business_name, "email": l.email, "ciudad": l.city}
        for l in todos
        if l.email and "@" in l.email and (not l.send_status or l.send_status.value != "Enviado")
    ]
    emails_contactados = {l.email.lower(): l.business_name for l in todos if l.email}

    hilos = _gmail_service().estado_bandeja_entrada(dias=dias)
    for h in hilos:
        h["es_lead_conocido"] = h["remitente"] in emails_contactados
        h["negocio"] = emails_contactados.get(h["remitente"], "")

    faltan_responder = [h for h in hilos if h["falta_responder"]]

    return {
        "pendientes_de_enviar": {"total": len(pendientes_envio), "items": pendientes_envio[:100]},
        "bandeja_entrada": {
            "total_hilos_activos": len(hilos),
            "faltan_responder": len(faltan_responder),
            "items": sorted(hilos, key=lambda h: not h["falta_responder"]),
        },
    }
