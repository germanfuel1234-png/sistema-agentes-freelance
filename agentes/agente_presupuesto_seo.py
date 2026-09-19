#!/usr/bin/env python3
"""
Agente 3 - Armador de Presupuestos SEO/Performance.

Corre una auditoria real de Lighthouse sobre el sitio de un cliente,
mapea los problemas encontrados a texto en espanol, calcula un
presupuesto en base a la cantidad/severidad de problemas, y genera
un HTML de propuesta con la misma estetica de presupuesto-ejemplo.html.

No envia nada por mail. Solo genera el archivo HTML en
presupuestos_generados/ para que vos (o el Agente 2) lo revisen y
lo adjunten a un mail cuando esten de acuerdo con el contenido y el precio.

Uso:
    python3 agentes/agente_presupuesto_seo.py --cliente "Alkanos" --url "https://alkanos.com.ar"
    python3 agentes/agente_presupuesto_seo.py --cliente "Nombre" --url "https://sitio.com" --estrategia desktop
"""
import argparse
import json
import re
import subprocess
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
PLANTILLA_PATH = BASE_DIR / "plantilla_presupuesto.html"
MAPEO_PATH = BASE_DIR / "lighthouse_mapeo.json"
PRECIOS_PATH = BASE_DIR / "precios_seo.json"
LIGHTHOUSE_BIN = PROJECT_DIR / "node_modules" / ".bin" / "lighthouse"
REPORTS_DIR = PROJECT_DIR / "lighthouse_reports"
OUTPUT_DIR = PROJECT_DIR / "presupuestos_generados"

CATEGORIAS = ["seo", "performance", "accessibility", "best-practices"]
CATEGORIA_LABEL = {
    "seo": "SEO",
    "performance": "Performance",
    "accessibility": "Accesibilidad",
    "best-practices": "Buenas prácticas",
}
MAX_PROBLEMAS = 10

# Auditorias que son metricas/diagnostico puro (no un "problema" accionable en si
# mismo) - se excluyen de la propuesta para no confundir al cliente. La mejora de
# estas metricas surge de resolver los problemas de arriba (unused-js, render
# blocking, etc.), no son un item de trabajo aparte.
EXCLUIR_IDS = {
    "first-contentful-paint",
    "speed-index",
    "interactive",
    "max-potential-fid",
    "server-response-time",
    "forced-reflow",
    "forced-reflow-insight",
    "network-dependency-tree-insight",
    "critical-request-chains",
    "bf-cache",
    "third-party-summary",
    "legacy-javascript",
}


def slugify(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^a-zA-Z0-9]+", "-", texto).strip("-").lower()
    return texto or "cliente"


def correr_lighthouse(url: str, estrategia: str) -> dict:
    if not LIGHTHOUSE_BIN.exists():
        sys.exit(
            f"No se encontro Lighthouse en {LIGHTHOUSE_BIN}.\n"
            f"Instalalo una vez con: cd {PROJECT_DIR} && npm install --no-save lighthouse"
        )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(url)
    out_json = REPORTS_DIR / f"{slug}-{estrategia}.json"

    cmd = [
        str(LIGHTHOUSE_BIN),
        url,
        "--output=json",
        f"--output-path={out_json}",
        "--chrome-flags=--headless=new --no-sandbox",
        f"--only-categories={','.join(CATEGORIAS)}",
        f"--form-factor={estrategia}",
        "--throttling-method=simulate",
        "--quiet",
    ]
    if estrategia == "desktop":
        cmd += [
            "--screenEmulation.mobile=false",
            "--screenEmulation.width=1350",
            "--screenEmulation.height=940",
            "--screenEmulation.deviceScaleFactor=1",
        ]

    print(f"-> Corriendo Lighthouse ({estrategia}) sobre {url} ... (puede tardar 20-40s)")
    resultado = subprocess.run(cmd, capture_output=True, text=True)
    if resultado.returncode != 0 or not out_json.exists():
        print(resultado.stdout)
        print(resultado.stderr)
        sys.exit("Lighthouse fallo. Revisa que la URL sea publica y accesible.")

    with open(out_json, encoding="utf-8") as f:
        return json.load(f)


def extraer_hallazgos(reporte: dict) -> tuple[dict, list[dict]]:
    scores = {}
    candidatos = []

    for cat in CATEGORIAS:
        categoria = reporte["categories"].get(cat)
        if not categoria or categoria.get("score") is None:
            continue
        scores[cat] = round(categoria["score"] * 100)

        for ref in categoria["auditRefs"]:
            audit = reporte["audits"].get(ref["id"])
            if not audit or audit.get("score") is None:
                continue
            if audit["score"] >= 0.9:
                continue
            if audit.get("scoreDisplayMode") == "notApplicable":
                continue
            if ref["id"] in EXCLUIR_IDS:
                continue
            candidatos.append(
                {
                    "id": ref["id"],
                    "categoria": cat,
                    "score": audit["score"],
                    "title": audit["title"],
                    "description": re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", audit.get("description", "")),
                }
            )

    # Orden: SEO primero, despues por score ascendente (mas critico primero)
    orden_categoria = {c: i for i, c in enumerate(CATEGORIAS)}
    candidatos.sort(key=lambda a: (orden_categoria.get(a["categoria"], 99), a["score"]))

    # Deduplicar por id y cortar al maximo
    vistos = set()
    problemas = []
    for c in candidatos:
        if c["id"] in vistos:
            continue
        vistos.add(c["id"])
        problemas.append(c)
        if len(problemas) >= MAX_PROBLEMAS:
            break

    return scores, problemas


def cargar_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def construir_problema_html(idx: int, problema: dict, mapeo: dict) -> str:
    info = mapeo.get(problema["id"])
    categoria_label = CATEGORIA_LABEL.get(problema["categoria"], problema["categoria"])
    if info:
        titulo = info["problema"]
        descripcion = info["descripcion"]
        tag = info.get("categoria", categoria_label)
    else:
        titulo = problema["title"]
        descripcion = problema["description"] or "Detectado por la auditoría automatizada de Lighthouse."
        tag = categoria_label

    return f"""
    <div class="problem">
      <div class="problem-num">{idx:02d}</div>
      <div>
        <span class="tag">{tag}</span>
        <h3>{titulo}</h3>
        <p>{descripcion}</p>
      </div>
    </div>"""


def construir_step_html(idx: int, problema: dict, mapeo: dict) -> str:
    info = mapeo.get(problema["id"])
    if info:
        titulo = f"Corregimos: {info['problema'].lower()}"
        descripcion = info["solucion"]
    else:
        titulo = f"Corregimos: {problema['title'].lower()}"
        descripcion = "Aplicamos la corrección recomendada por Lighthouse para este punto."

    return f"""
    <div class="step">
      <div class="step-num">{idx:02d}</div>
      <div>
        <h3>{titulo}</h3>
        <p>{descripcion}</p>
      </div>
    </div>"""


def score_class(score: int) -> str:
    if score >= 90:
        return "score-good"
    if score >= 50:
        return "score-mid"
    return "score-bad"


def construir_score_chips(scores: dict) -> str:
    chips = []
    for cat in CATEGORIAS:
        if cat not in scores:
            continue
        label = CATEGORIA_LABEL[cat]
        valor = scores[cat]
        chips.append(
            f'<div class="score-chip {score_class(valor)}"><strong>{valor}</strong>{label}</div>'
        )
    return "\n      ".join(chips)


def calcular_precio(cantidad_problemas: int, config: dict) -> tuple[int, int]:
    base = config["precio_base_ars"] + cantidad_problemas * config["precio_por_problema_ars"]
    base = min(base, config["precio_base_max_ars"])
    total = round(base * config["multiplicador_total"] / 10000) * 10000
    return base, total


def formatear_ars(monto: int) -> str:
    return f"${monto:,.0f}".replace(",", ".")


def construir_plan_items(problemas: list[dict], mapeo: dict, extra_items: list[str]) -> tuple[str, str]:
    items_base = []
    for p in problemas:
        info = mapeo.get(p["id"])
        texto = info["problema"] if info else p["title"]
        items_base.append(f"<li>Corrección: {texto}</li>")

    items_total = list(items_base)
    items_total.insert(0, "<li>Todo lo incluido en el Alcance 01</li>")
    for extra in extra_items:
        items_total.append(f"<li>{extra}</li>")

    return "\n          ".join(items_base), "\n          ".join(items_total)


def generar_presupuesto(cliente: str, url: str, estrategia: str) -> Path:
    mapeo = cargar_json(MAPEO_PATH)
    precios_config = cargar_json(PRECIOS_PATH)
    plantilla = PLANTILLA_PATH.read_text(encoding="utf-8")

    reporte = correr_lighthouse(url, estrategia)
    scores, problemas = extraer_hallazgos(reporte)

    if not problemas:
        print("No se encontraron problemas relevantes (todos los scores >= 90). "
              "Igual se genera el documento con el resultado positivo de la auditoría.")

    problems_html = "\n".join(
        construir_problema_html(i + 1, p, mapeo) for i, p in enumerate(problemas)
    ) or '<p class="section-lead">No se detectaron problemas relevantes en la auditoría automatizada — el sitio ya tiene buen puntaje en todas las categorías evaluadas.</p>'

    steps_html = "\n".join(
        construir_step_html(i + 1, p, mapeo) for i, p in enumerate(problemas)
    ) or '<p class="section-lead">No hay correcciones pendientes según la auditoría automatizada.</p>'

    precio_base, precio_total = calcular_precio(len(problemas), precios_config)
    items_base_html, items_total_html = construir_plan_items(
        problemas, mapeo, precios_config["items_incluidos_alcance_total_extra"]
    )

    hoy = datetime.now()
    estrategia_label = "Mobile" if estrategia == "mobile" else "Desktop"
    seccion_auditoria_html = f"""<section>
  <div class="wrap">
    <h2>Resultado de la auditoría</h2>
    <p class="section-lead">Medido con Google Lighthouse (Google PageSpeed / Chrome DevTools), la misma herramienta que usa Google para evaluar la calidad técnica de un sitio. Estrategia: {estrategia_label}.</p>
    <div class="score-row">
      {construir_score_chips(scores)}
    </div>
  </div>
</section>"""
    reemplazos = {
        "{{TITULO}}": f"Presupuesto — Auditoría SEO {cliente}",
        "{{TITULO_H1}}": "Auditoría SEO y correcciones",
        "{{EYEBROW}}": "PROPUESTA TÉCNICA · AUDITORÍA SEO Y PERFORMANCE",
        "{{HERO_SUB}}": "Auditoría automatizada (Google Lighthouse) del sitio, alcance de trabajo y presupuesto para resolver los problemas detectados.",
        "{{CLIENTE}}": cliente,
        "{{SITIO}}": url,
        "{{FECHA}}": hoy.strftime("%B %Y").capitalize(),
        "{{ANIO}}": str(hoy.year),
        "{{ESTRATEGIA}}": estrategia_label,
        "{{SECCION_AUDITORIA_HTML}}": seccion_auditoria_html,
        "{{TITULO_PROBLEMAS}}": "Problemas detectados",
        "{{LEAD_PROBLEMAS}}": f"{len(problemas)} puntos relevados automáticamente sobre {url}, ordenados por impacto.",
        "{{LEAD_COMO_RESOLVEMOS}}": "Orden de trabajo propuesto para corregir lo detectado.",
        "{{LEAD_PRESUPUESTO}}": "Valores en pesos argentinos, sin IVA. Estimados a partir de la cantidad y severidad de los problemas encontrados — sujetos a confirmación tras relevar el acceso al sitio.",
        "{{ALCANCE_01_NOMBRE}}": "Corrección puntual",
        "{{ALCANCE_01_DESC}}": "Resuelve los problemas críticos detectados en la auditoría.",
        "{{ALCANCE_02_NOMBRE}}": "Optimización integral",
        "{{ALCANCE_02_DESC}}": "Todo lo del alcance puntual, más una pasada completa de SEO técnico y performance para acercar el sitio a un score alto en Lighthouse.",
        "{{NOTA_PRECIO}}": "* Precios estimativos según hallazgos automatizados de Lighthouse. Tiempo estimado de entrega: 1-3 semanas según alcance.",
        "{{FOOTER_NOTA}}": "Auditoría generada automáticamente con Lighthouse",
        "{{SCORE_CHIPS_HTML}}": construir_score_chips(scores),
        "{{CANTIDAD_PROBLEMAS}}": str(len(problemas)),
        "{{PROBLEMS_HTML}}": problems_html,
        "{{STEPS_HTML}}": steps_html,
        "{{PRECIO_BASE}}": formatear_ars(precio_base),
        "{{PRECIO_TOTAL}}": formatear_ars(precio_total),
        "{{PLAN_BASE_ITEMS_HTML}}": items_base_html or "<li>Sin correcciones críticas pendientes</li>",
        "{{PLAN_TOTAL_ITEMS_HTML}}": items_total_html,
    }

    html_final = plantilla
    for token, valor in reemplazos.items():
        html_final = html_final.replace(token, valor)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    salida = OUTPUT_DIR / f"presupuesto-{slugify(cliente)}.html"
    salida.write_text(html_final, encoding="utf-8")

    print("\n=== Resumen ===")
    print(f"Cliente: {cliente}  |  Sitio: {url}")
    print(f"Scores: {scores}")
    print(f"Problemas detectados (usados en la propuesta): {len(problemas)}")
    print(f"Precio Alcance 01 (Corrección puntual): {formatear_ars(precio_base)}")
    print(f"Precio Alcance 02 (Optimización integral): {formatear_ars(precio_total)}")
    print(f"\nArchivo generado: {salida}")
    print("Revisalo antes de adjuntarlo a un mail — los precios son un punto de partida, no una tarifa final.")

    # Linea final en JSON (ademas de los prints legibles de arriba) para que
    # quien llame a este script por subprocess (ej. el runner de n8n) pueda
    # parsear los datos sin tener que scrapear el texto humano.
    resultado = {
        "cliente": cliente, "url": url, "estrategia": estrategia,
        "scores": scores, "cantidad_problemas": len(problemas),
        "precio_base": precio_base, "precio_total": precio_total,
        "archivo_html": str(salida),
    }
    print("RESULTADO_JSON:" + json.dumps(resultado))
    return salida


def generar_presupuesto_brief(cliente: str, brief: str, precio_base: int, precio_total: int, sitio: str = "") -> Path:
    """Genera un presupuesto SIN correr Lighthouse - para cuando no hay URL
    (sitio nuevo, o el cliente prefiere no compartir el link todavía). El
    alcance sale de un brief en texto libre que carga el usuario a mano, no
    de una auditoría automática - por eso no hay scores ni "problemas
    detectados", y el precio es el que el usuario define (no se calcula
    solo a partir de una cantidad de hallazgos, porque acá no hay
    hallazgos)."""
    plantilla = PLANTILLA_PATH.read_text(encoding="utf-8")

    parrafos_brief = [p.strip() for p in brief.strip().split("\n") if p.strip()]
    brief_html = "\n".join(f'<p class="section-lead">{p}</p>' for p in parrafos_brief) or \
        '<p class="section-lead">Sin brief cargado.</p>'

    hoy = datetime.now()
    reemplazos = {
        "{{TITULO}}": f"Presupuesto — {cliente}",
        "{{TITULO_H1}}": "Propuesta de desarrollo web",
        "{{EYEBROW}}": "PROPUESTA TÉCNICA · DESARROLLO A MEDIDA",
        "{{HERO_SUB}}": "Propuesta de trabajo y presupuesto armados a partir del brief compartido por el cliente.",
        "{{CLIENTE}}": cliente,
        "{{SITIO}}": sitio or "A definir",
        "{{FECHA}}": hoy.strftime("%B %Y").capitalize(),
        "{{ANIO}}": str(hoy.year),
        "{{ESTRATEGIA}}": "",
        "{{SECCION_AUDITORIA_HTML}}": "",  # sin auditoria, no hay scores que mostrar
        "{{TITULO_PROBLEMAS}}": "Alcance del proyecto",
        "{{LEAD_PROBLEMAS}}": "Detalle compartido por el cliente para armar esta propuesta.",
        "{{PROBLEMS_HTML}}": brief_html,
        "{{LEAD_COMO_RESOLVEMOS}}": "Orden de trabajo propuesto según lo conversado.",
        "{{STEPS_HTML}}": '<p class="section-lead">El desarrollo se realiza según lo acordado en el brief inicial, con entregas parciales para revisión.</p>',
        "{{LEAD_PRESUPUESTO}}": "Valores en pesos argentinos, sin IVA. Estimados a partir del brief compartido — sujetos a confirmación tras definir el alcance final.",
        "{{ALCANCE_01_NOMBRE}}": "Propuesta base",
        "{{ALCANCE_01_DESC}}": "Alcance definido según el brief compartido.",
        "{{PRECIO_BASE}}": formatear_ars(precio_base),
        "{{PLAN_BASE_ITEMS_HTML}}": "<li>Según brief compartido</li>",
        "{{ALCANCE_02_NOMBRE}}": "Propuesta completa",
        "{{ALCANCE_02_DESC}}": "Incluye el alcance base más mejoras y extras adicionales a definir.",
        "{{PRECIO_TOTAL}}": formatear_ars(precio_total),
        "{{PLAN_TOTAL_ITEMS_HTML}}": "<li>Todo lo incluido en la propuesta base</li>\n          <li>Ajustes y revisiones adicionales</li>",
        "{{NOTA_PRECIO}}": "* Precios estimativos según el brief compartido, sin auditoría técnica del sitio. Tiempo estimado de entrega: a definir según alcance.",
        "{{FOOTER_NOTA}}": "Propuesta armada a partir del brief compartido por el cliente",
        "{{SCORE_CHIPS_HTML}}": "",
        "{{CANTIDAD_PROBLEMAS}}": "",
    }

    html_final = plantilla
    for token, valor in reemplazos.items():
        html_final = html_final.replace(token, valor)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    salida = OUTPUT_DIR / f"presupuesto-{slugify(cliente)}.html"
    salida.write_text(html_final, encoding="utf-8")

    print(f"\nArchivo generado (sin auditoría, desde brief): {salida}")

    resultado = {
        "cliente": cliente, "url": sitio, "precio_base": precio_base,
        "precio_total": precio_total, "archivo_html": str(salida),
    }
    print("RESULTADO_JSON:" + json.dumps(resultado))
    return salida


def main():
    parser = argparse.ArgumentParser(description="Genera un presupuesto de corrección SEO en base a una auditoría real de Lighthouse (o, con --brief, sin auditoría).")
    parser.add_argument("--cliente", required=True, help="Nombre del cliente/negocio, ej: 'Alkanos'")
    parser.add_argument("--url", default="", help="URL completa del sitio a auditar, ej: https://alkanos.com.ar (opcional si se usa --brief)")
    parser.add_argument("--estrategia", choices=["mobile", "desktop"], default="mobile", help="Estrategia de auditoría (default: mobile)")
    parser.add_argument("--brief", default="", help="Texto libre con el alcance del proyecto - si se pasa, NO corre Lighthouse (para cuando no hay URL)")
    parser.add_argument("--precio-base", type=int, default=0, help="Precio base en ARS (requerido con --brief)")
    parser.add_argument("--precio-total", type=int, default=0, help="Precio total en ARS (requerido con --brief)")
    args = parser.parse_args()

    if args.brief:
        generar_presupuesto_brief(args.cliente, args.brief, args.precio_base, args.precio_total, sitio=args.url)
    else:
        generar_presupuesto(args.cliente, args.url, args.estrategia)


if __name__ == "__main__":
    main()
