"""
API interna del "runner" - ejecuta los scripts pesados (Lighthouse,
generador de presupuestos) que n8n no puede correr en su propio
contenedor (la imagen oficial de n8n es "hardened", sin Python/Chrome
ni gestor de paquetes - a propósito, por seguridad).

Solo se accede a esto desde la red interna de Docker Compose (nunca
publicado a la LAN ni a internet) - n8n le pega por HTTP (nodo HTTP
Request) en vez de usar Execute Command, así nunca hay ejecución de
comandos arbitrarios expuesta.

Excepción acotada: /procesos/{nombre}/iniciar y /detener pueden arrancar
o frenar los 3 scripts de loop del proyecto (loop_caza.py, send_loop.py,
postular_formularios.py) para que el dashboard tenga botones reales - los
comandos están fijos en SCRIPTS_LANZABLES (sin parámetros del usuario, sin
shell=True), nunca se ejecuta una cadena arbitraria.
"""
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
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

WHATSAPP_TAB = "whatsapp_enviados"
WHATSAPP_HEADERS = ["Fecha", "Hora", "Cliente", "Resultado"]

CLIENTES_TAB = "clientes"
CLIENTES_HEADERS = [
    "Fecha Confirmacion", "Cliente", "URL", "Precio Total", "Pagado",
    "Presupuesto HTML", "Presupuesto PDF", "Carpeta Local",
]
CLIENTES_DIR = DATA_DIR / "clientes"

SEGUIMIENTO_TAB = "seguimiento_manual"

PROCESOS_TAB = "estado_procesos"
PROCESOS_ACTIVO_MINUTOS = 20  # sin heartbeat en este lapso -> se considera inactivo

# Registro fijo de scripts lanzables desde el dashboard - nombre -> comando
# (lista, nunca string con shell=True) y archivo STOP para frenarlo. No hay
# forma de agregar/editar esto desde afuera, es codigo, no input del usuario.
SCRIPTS_LANZABLES = {
    "loop_caza": {
        "cmd": [sys.executable, "loop_caza.py"],
        "stop_file": DATA_DIR / "STOP.loop",
    },
    "send_loop": {
        "cmd": [sys.executable, "send_loop.py"],
        "stop_file": DATA_DIR / "STOP_send.loop",
    },
    "postular_formularios": {
        "cmd": [sys.executable, "postular_formularios.py", "--intervalo", "1"],
        "stop_file": DATA_DIR / "STOP_postular.loop",
    },
    "buscar_postulaciones_linkedin": {
        "cmd": [sys.executable, "buscar_postulaciones_linkedin.py", "--intervalo", "60"],
        "stop_file": DATA_DIR / "STOP_linkedin.loop",
    },
}
# Procesos arrancados por ESTE runner (si el runner se reinicia, se pierde
# la referencia - igual se pueden frenar via stop_file, que es un archivo
# compartido en /data y no depende de tener el Popen en memoria).
_PROCESOS_ACTIVOS: dict[str, subprocess.Popen] = {}

# El contenedor corre como root, así que todo lo que escribe queda
# root:root en el host - inutilizable para el usuario real (uid/gid 1000)
# en su editor. Se pisa el dueño en cada archivo/carpeta que generamos
# para que se pueda abrir y editar normalmente (ej. en VS Code).
HOST_UID = int(os.environ.get("HOST_UID", "1000"))
HOST_GID = int(os.environ.get("HOST_GID", "1000"))


def _dar_permisos_host(path: Path):
    try:
        os.chown(path, HOST_UID, HOST_GID)
        if path.is_dir():
            for hijo in path.rglob("*"):
                os.chown(hijo, HOST_UID, HOST_GID)
    except Exception:
        pass

sys.path.insert(0, str(AGENTES_DIR))
sys.path.insert(0, str(DATA_DIR))

app = FastAPI(title="runner interno - sistema_agentes_freelance")


class PresupuestoRequest(BaseModel):
    cliente: str
    url: str
    estrategia: str = "mobile"
    generar_pdf: bool = True
    dias_cobertura: int = 30


class WhatsappLogRequest(BaseModel):
    cliente: str
    resultado: str = "enviado"


class EnviarPresupuestoRequest(BaseModel):
    cliente: str
    email: str
    pdf_nombre: str


class ClienteConfirmadoRequest(BaseModel):
    cliente: str
    url: str
    precio_total: str = ""
    html_path: str = ""
    pdf_path: str = ""


class TogglePagadoRequest(BaseModel):
    pagado: bool


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
    _dar_permisos_host(html_path)

    if req.generar_pdf:
        if not html_path.exists():
            raise HTTPException(500, f"se esperaba el HTML en {html_path} pero no está")
        pdf_path = html_path.with_suffix(".pdf")
        try:
            _html_a_pdf(html_path, pdf_path)
        except Exception as e:
            raise HTTPException(500, detail={"error": "el HTML se generó pero falló el PDF", "detalle": str(e)})
        _dar_permisos_host(pdf_path)
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


class PresupuestoBriefRequest(BaseModel):
    cliente: str
    brief: str
    precio_base: int
    precio_total: int
    url: str = ""
    dias_cobertura: int = 30
    generar_pdf: bool = True


@app.post("/presupuesto/brief")
def generar_presupuesto_desde_brief(req: PresupuestoBriefRequest):
    """Genera un presupuesto SIN correr Lighthouse - para cuando no hay URL
    (sitio nuevo, o el cliente no la compartió todavía). Import directo en
    vez de subprocess (como /presupuesto) porque acá no hay Lighthouse de
    por medio, es liviano - no hace falta aislarlo en otro proceso."""
    if not req.brief.strip():
        raise HTTPException(400, "el brief no puede estar vacío")

    from agente_presupuesto_seo import generar_presupuesto_brief

    try:
        html_path = generar_presupuesto_brief(
            req.cliente, req.brief, req.precio_base, req.precio_total, sitio=req.url
        )
    except Exception as e:
        raise HTTPException(500, detail={"error": "no se pudo generar el presupuesto", "detalle": str(e)})

    respuesta = {"ok": True, "html_path": str(html_path)}
    _dar_permisos_host(html_path)

    if req.generar_pdf:
        pdf_path = html_path.with_suffix(".pdf")
        try:
            _html_a_pdf(html_path, pdf_path)
        except Exception as e:
            raise HTTPException(500, detail={"error": "el HTML se generó pero falló el PDF", "detalle": str(e)})
        _dar_permisos_host(pdf_path)
        respuesta["pdf_path"] = str(pdf_path)

    hoy = datetime.now()
    try:
        sheets = _sheets_client()
        sheets.add_sheet(PRESUPUESTOS_TAB, headers=PRESUPUESTOS_HEADERS)
        fila = [
            hoy.strftime("%d/%m/%Y"), req.cliente, req.url,
            str(req.precio_base), str(req.precio_total),
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
    for i, fila in enumerate(filas):
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
            "fila": i + 2,
            "fecha": fila[0], "cliente": fila[1], "url": fila[2],
            "precio_base": fila[3], "precio_total": fila[4],
            "dias_cobertura": fila[5], "fecha_inicio_cobertura": fila[6],
            "fecha_vencimiento_cobertura": vence.strftime("%d/%m/%Y") if vence else None,
            "cobertura_vigente": vigente,
            "html": fila[7], "pdf": fila[8],
        })
    return {"presupuestos": resultado}


class EditarPresupuestoRequest(BaseModel):
    fecha: str
    cliente: str
    url: str
    precio_total: str
    dias_cobertura: str


@app.post("/presupuesto/{fila}/editar")
def editar_presupuesto(fila: int, req: EditarPresupuestoRequest):
    """Edita Fecha/Cliente/Sitio/Precio total/Dias de cobertura de una fila
    ya existente - precio_base, fecha_inicio_cobertura, HTML y PDF quedan
    intactos (se lee la fila completa y solo se pisan los campos editables,
    para no perder nada)."""
    sheets = _sheets_client()
    actual = sheets.read_range(f"'{PRESUPUESTOS_TAB}'!A{fila}:I{fila}")
    if not actual or not actual[0]:
        raise HTTPException(404, "fila no encontrada")
    row = actual[0] + [""] * (9 - len(actual[0]))
    row[0] = req.fecha
    row[1] = req.cliente
    row[2] = req.url
    row[4] = req.precio_total
    row[5] = req.dias_cobertura
    sheets.write_range(f"'{PRESUPUESTOS_TAB}'!A{fila}", [row], append=False)
    return {"ok": True}


def _extraer_datos_presupuesto_html(contenido: str) -> dict:
    """Busca cliente/sitio/precios en un HTML de presupuesto - funciona
    porque agente_presupuesto_seo.py siempre arma esos datos con los mismos
    marcadores (ver agentes/plantilla_presupuesto.html: "Cliente:</strong>
    X</span>", "Sitio:</strong> X</span>", dos <div class="plan-price">
    con $base y $total). Si el HTML no tiene esa estructura (no es uno de
    los nuestros), simplemente no encuentra nada y devuelve campos vacíos -
    no inventa datos."""
    datos = {"cliente": "", "url": "", "precio_base": "", "precio_total": ""}

    m = re.search(r"Cliente:\s*</strong>\s*([^<]+?)\s*</span>", contenido)
    if m:
        datos["cliente"] = m.group(1).strip()

    m = re.search(r"Sitio:\s*</strong>\s*([^<]+?)\s*</span>", contenido)
    if m:
        datos["url"] = m.group(1).strip()

    precios = re.findall(r'class="plan-price">\s*\$([\d.]+)\s*</div>', contenido)
    precios_num = [p.replace(".", "") for p in precios]
    if len(precios_num) >= 2:
        datos["precio_base"], datos["precio_total"] = precios_num[0], precios_num[1]
    elif len(precios_num) == 1:
        datos["precio_total"] = precios_num[0]

    return datos


@app.post("/presupuestos/subir-html")
async def subir_html_presupuesto(archivo: UploadFile = File(...)):
    """Guarda un HTML de presupuesto subido a mano (no generado por
    agente_presupuesto_seo.py) e intenta extraer cliente/sitio/precios de
    la misma estructura que usa nuestra plantilla. Los "días de cobertura"
    NUNCA se pueden extraer (esa plantilla no los incluye) - eso siempre lo
    completa el usuario en la confirmación."""
    contenido_bytes = await archivo.read()
    contenido_texto = contenido_bytes.decode("utf-8", errors="ignore")
    datos = _extraer_datos_presupuesto_html(contenido_texto)

    nombre = archivo.filename or f"presupuesto-subido-{uuid.uuid4().hex[:8]}.html"
    if not nombre.endswith(".html"):
        nombre += ".html"
    destino = OUTPUT_DIR / nombre
    contador = 1
    while destino.exists():
        destino = OUTPUT_DIR / f"{Path(nombre).stem}-{contador}.html"
        contador += 1
    destino.write_bytes(contenido_bytes)
    _dar_permisos_host(destino)

    return {"ok": True, "html_path": str(destino), **datos}


class ConfirmarHtmlRequest(BaseModel):
    html_path: str
    cliente: str
    url: str
    precio_base: str = ""
    precio_total: str = ""
    dias_cobertura: int = 30
    generar_pdf: bool = True


@app.post("/presupuestos/confirmar-html")
def confirmar_html_presupuesto(req: ConfirmarHtmlRequest):
    """Registra en la Sheet el HTML ya subido (con los datos confirmados/
    corregidos por el usuario) - mismo flujo que un presupuesto generado
    normal, así aparece igual en el panel (Ver HTML/PDF, Enviar mail,
    editar, etc.)."""
    html_path = Path(req.html_path).resolve()
    if OUTPUT_DIR.resolve() not in html_path.parents or not html_path.exists():
        raise HTTPException(404, "el HTML subido no existe (¿se borró o expiró?)")

    respuesta = {"ok": True, "html_path": str(html_path)}

    if req.generar_pdf:
        pdf_path = html_path.with_suffix(".pdf")
        try:
            _html_a_pdf(html_path, pdf_path)
            _dar_permisos_host(pdf_path)
            respuesta["pdf_path"] = str(pdf_path)
        except Exception as e:
            respuesta["pdf_error"] = str(e)

    hoy = datetime.now()
    try:
        sheets = _sheets_client()
        sheets.add_sheet(PRESUPUESTOS_TAB, headers=PRESUPUESTOS_HEADERS)
        fila = [
            hoy.strftime("%d/%m/%Y"), req.cliente, req.url,
            req.precio_base, req.precio_total,
            str(req.dias_cobertura), hoy.strftime("%d/%m/%Y"),
            str(html_path), respuesta.get("pdf_path", ""),
        ]
        sheets.write_range(f"'{PRESUPUESTOS_TAB}'!A2", [fila], append=True)
        respuesta["registrado_en_sheet"] = True
    except Exception as e:
        respuesta["registrado_en_sheet"] = False
        respuesta["error_sheet"] = str(e)

    return respuesta


@app.post("/presupuesto/enviar-mail")
def enviar_presupuesto_mail(req: EnviarPresupuestoRequest):
    """Manda por Gmail el PDF de un presupuesto ya generado. Se restringe a
    OUTPUT_DIR (sin .. ni rutas absolutas) - mismo criterio que /descargar
    del dashboard, así no se puede pedir adjuntar cualquier archivo del
    /data montado."""
    pdf_path = (OUTPUT_DIR / req.pdf_nombre).resolve()
    if OUTPUT_DIR.resolve() not in pdf_path.parents or not pdf_path.exists():
        raise HTTPException(404, "El PDF no existe")

    asunto = f"Tu presupuesto - {req.cliente}"
    cuerpo = (
        f"Hola!\n\n"
        f"Te paso el presupuesto que armé para {req.cliente}. Lo dejo adjunto en este mail.\n\n"
        f"Cualquier duda, quedo atento.\n\n"
        f"Saludos!"
    )
    gmail = _gmail_service()
    message_id = gmail.send_email_con_adjunto(to=req.email, subject=asunto, body=cuerpo, adjunto_path=str(pdf_path))
    if not message_id:
        raise HTTPException(500, "No se pudo enviar el mail - revisá los logs del runner")
    return {"ok": True, "message_id": message_id}


@app.post("/clientes")
def confirmar_cliente(req: ClienteConfirmadoRequest):
    """Promueve un presupuesto ya generado a "cliente confirmado": crea una
    carpeta local (bajo /data/clientes, visible en el host en
    sistema_agentes_freelance/clientes/) con el HTML/PDF ya generados -
    lista para abrir en VS Code - y registra la fila en la Sheet."""
    from agente_presupuesto_seo import slugify

    slug = slugify(req.cliente)
    carpeta = CLIENTES_DIR / slug
    carpeta.mkdir(parents=True, exist_ok=True)

    for origen_str in (req.html_path, req.pdf_path):
        if not origen_str:
            continue
        origen = Path(origen_str)
        if origen.exists():
            (carpeta / origen.name).write_bytes(origen.read_bytes())

    _dar_permisos_host(carpeta)
    carpeta_relativa = f"clientes/{slug}"

    sheets = _sheets_client()
    sheets.add_sheet(CLIENTES_TAB, headers=CLIENTES_HEADERS)
    fila = [
        datetime.now().strftime("%d/%m/%Y"), req.cliente, req.url, req.precio_total,
        "No", req.html_path, req.pdf_path, carpeta_relativa,
    ]
    sheets.write_range(f"'{CLIENTES_TAB}'!A2", [fila], append=True)

    return {"ok": True, "carpeta_local": carpeta_relativa}


@app.get("/clientes")
def listar_clientes():
    sheets = _sheets_client()
    filas = sheets.read_range(f"'{CLIENTES_TAB}'!A2:H10000")
    resultado = []
    for i, fila in enumerate(filas):
        if not fila or not fila[0]:
            continue
        fila = fila + [""] * (8 - len(fila))
        resultado.append({
            "fila": i + 2,  # numero de fila real en la Sheet (para poder editarla despues)
            "fecha_confirmacion": fila[0], "cliente": fila[1], "url": fila[2],
            "precio_total": fila[3], "pagado": fila[4],
            "html": fila[5], "pdf": fila[6], "carpeta_local": fila[7],
        })
    return {"total": len(resultado), "items": resultado[::-1]}


@app.post("/clientes/{fila}/pagado")
def marcar_pagado(fila: int, req: TogglePagadoRequest):
    sheets = _sheets_client()
    sheets.add_sheet(CLIENTES_TAB, headers=CLIENTES_HEADERS)
    valor = "Si" if req.pagado else "No"
    sheets.write_range(f"'{CLIENTES_TAB}'!E{fila}", [[valor]], append=False)
    return {"ok": True}


def _resumen_24h(nombre: str, sheets) -> str:
    """Estadística de las últimas 24hs para los procesos donde hay un
    timestamp confiable para calcularla. loop_caza no tiene (leads_tracking
    no guarda fecha de hallazgo, solo fecha de envío), así que no devuelve
    nada para ese - mejor no mostrar un número que no es real."""
    ahora = datetime.now()
    if nombre == "postular_formularios":
        filas = sheets.read_range(f"'{SEGUIMIENTO_TAB}'!A2:I10000")
        conteo: dict[str, int] = {}
        for f in filas:
            if not f or len(f) < 9 or not f[8]:
                continue
            try:
                fecha = datetime.strptime(f[8], "%d/%m/%Y %H:%M:%S")
            except ValueError:
                continue
            if (ahora - fecha).total_seconds() <= 24 * 3600:
                estado = f[7] or "?"
                conteo[estado] = conteo.get(estado, 0) + 1
        if not conteo:
            return "Sin postulaciones en las últimas 24hs"
        partes = ", ".join(f"{v} {k}" for k, v in conteo.items())
        return f"Últimas 24hs: {partes}"

    if nombre == "send_loop":
        leads = sheets.get_all_leads()
        hoy = ahora.date()
        enviados = sum(1 for l in leads if l.send_date and l.send_date.date() == hoy and l.send_status and l.send_status.value == "Enviado")
        return f"Enviados hoy: {enviados}"

    return ""


@app.get("/procesos")
def listar_procesos():
    """Lee los heartbeats que van dejando los scripts de loop (loop_caza.py,
    send_loop.py, y los que se agreguen despues via core/heartbeat.py) -
    no hay una lista fija acá, se muestra lo que sea que haya reportado
    algo en la Sheet. Para los que están en SCRIPTS_LANZABLES suma si son
    controlables desde el dashboard y si este runner los inició."""
    sheets = _sheets_client()
    filas = sheets.read_range(f"'{PROCESOS_TAB}'!A2:C1000")
    ahora = datetime.now()
    resultado = []
    vistos = set()
    for fila in filas:
        if not fila or not fila[0]:
            continue
        fila = fila + [""] * (3 - len(fila))
        nombre = fila[0]
        vistos.add(nombre)
        minutos, activo = None, False
        try:
            ultima = datetime.strptime(fila[1], "%d/%m/%Y %H:%M:%S")
            minutos = (ahora - ultima).total_seconds() / 60
            activo = minutos <= PROCESOS_ACTIVO_MINUTOS
        except ValueError:
            pass
        proceso_local = _PROCESOS_ACTIVOS.get(nombre)
        resultado.append({
            "proceso": nombre, "ultima_actividad": fila[1], "detalle": fila[2],
            "activo": activo, "minutos_desde_ultima": round(minutos, 1) if minutos is not None else None,
            "controlable": nombre in SCRIPTS_LANZABLES,
            "corriendo_en_runner": proceso_local is not None and proceso_local.poll() is None,
            "resumen_24h": _resumen_24h(nombre, sheets),
        })
    # Scripts lanzables que todavía no reportaron ningún heartbeat (nunca
    # se corrieron) - igual aparecen, para poder iniciarlos por primera vez.
    for nombre in SCRIPTS_LANZABLES:
        if nombre not in vistos:
            proceso_local = _PROCESOS_ACTIVOS.get(nombre)
            resultado.append({
                "proceso": nombre, "ultima_actividad": None, "detalle": "",
                "activo": False, "minutos_desde_ultima": None,
                "controlable": True,
                "corriendo_en_runner": proceso_local is not None and proceso_local.poll() is None,
            })
    return {"procesos": resultado}


@app.post("/procesos/{nombre}/iniciar")
def iniciar_proceso(nombre: str):
    if nombre not in SCRIPTS_LANZABLES:
        raise HTTPException(404, "script desconocido")

    proceso_local = _PROCESOS_ACTIVOS.get(nombre)
    if proceso_local is not None and proceso_local.poll() is None:
        return {"ok": False, "detalle": "ya está corriendo (lanzado por este runner)"}

    # Heartbeat reciente = probablemente ya está corriendo en otro lado
    # (ej. el usuario lo arrancó a mano en el host) - no lo sabemos con
    # certeza (no hay visibilidad de PIDs entre el host y el contenedor),
    # pero es la única señal disponible y evita duplicar instancias.
    sheets = _sheets_client()
    filas = sheets.read_range(f"'{PROCESOS_TAB}'!A2:C1000")
    for fila in filas:
        if fila and fila[0] == nombre and len(fila) > 1:
            try:
                ultima = datetime.strptime(fila[1], "%d/%m/%Y %H:%M:%S")
                minutos = (datetime.now() - ultima).total_seconds() / 60
                if minutos <= PROCESOS_ACTIVO_MINUTOS:
                    return {"ok": False, "detalle": f"parece estar corriendo ya (heartbeat hace {minutos:.0f} min) - probablemente en el host. Si estás seguro de que no, esperá a que el heartbeat se vuelva viejo o frenalo primero."}
            except ValueError:
                pass

    info = SCRIPTS_LANZABLES[nombre]
    stop_file = info["stop_file"]
    if stop_file.exists():
        stop_file.unlink()

    log_path = DATA_DIR / f"{nombre}.log"
    log_file = open(log_path, "a")
    proceso = subprocess.Popen(info["cmd"], cwd=str(DATA_DIR), stdout=log_file, stderr=subprocess.STDOUT)
    _PROCESOS_ACTIVOS[nombre] = proceso
    return {"ok": True, "pid": proceso.pid}


@app.post("/procesos/{nombre}/detener")
def detener_proceso(nombre: str):
    if nombre not in SCRIPTS_LANZABLES:
        raise HTTPException(404, "script desconocido")

    info = SCRIPTS_LANZABLES[nombre]
    # El archivo STOP funciona sin importar si el proceso corre en el host
    # o fue lanzado por este runner (mismo /data compartido) - es la forma
    # principal y más confiable de frenarlo.
    info["stop_file"].touch()

    proceso_local = _PROCESOS_ACTIVOS.get(nombre)
    if proceso_local is not None and proceso_local.poll() is None:
        proceso_local.terminate()

    return {"ok": True, "detalle": "se avisó al proceso que pare (puede tardar hasta el próximo chequeo del loop)"}


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
    ya_enviados = [
        {"negocio": l.business_name, "email": l.email, "ciudad": l.city}
        for l in todos
        if l.email and "@" in l.email and l.send_status and l.send_status.value == "Enviado"
    ]
    emails_contactados = {l.email.lower(): l.business_name for l in todos if l.email}

    hilos = _gmail_service().estado_bandeja_entrada(dias=dias)
    for h in hilos:
        h["es_lead_conocido"] = h["remitente"] in emails_contactados
        h["negocio"] = emails_contactados.get(h["remitente"], "")

    faltan_responder = [h for h in hilos if h["falta_responder"]]

    return {
        "pendientes_de_enviar": {"total": len(pendientes_envio), "items": pendientes_envio[:100]},
        "ya_enviados": {"total": len(ya_enviados), "items": ya_enviados[:100]},
        "bandeja_entrada": {
            "total_hilos_activos": len(hilos),
            "faltan_responder": len(faltan_responder),
            "items": sorted(hilos, key=lambda h: not h["falta_responder"]),
        },
    }


@app.post("/whatsapp/log")
def registrar_whatsapp(req: WhatsappLogRequest):
    """Registra en la Sheet cada vez que se dispara un aviso de WhatsApp
    (desde el dashboard, al generar un presupuesto) - deja fecha/hora y si
    salió bien o falló, para tener un registro tipo bitácora."""
    ahora = datetime.now()
    sheets = _sheets_client()
    sheets.add_sheet(WHATSAPP_TAB, headers=WHATSAPP_HEADERS)
    fila = [ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), req.cliente, req.resultado]
    sheets.write_range(f"'{WHATSAPP_TAB}'!A2", [fila], append=True)
    return {"ok": True}


@app.get("/whatsapp/enviados")
def listar_whatsapp_enviados(limite: int = 100):
    sheets = _sheets_client()
    filas = sheets.read_range(f"'{WHATSAPP_TAB}'!A2:D10000")
    items = []
    for fila in filas:
        if not fila or not fila[0]:
            continue
        fila = fila + [""] * (4 - len(fila))
        items.append({"fecha": fila[0], "hora": fila[1], "cliente": fila[2], "resultado": fila[3]})
    return {"total": len(items), "items": items[-limite:][::-1]}
