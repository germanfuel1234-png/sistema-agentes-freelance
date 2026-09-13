"""Caza empresas REALES que buscan automatización de procesos / bots en
Python / RPA vía Indeed.

Misma infraestructura que cazar_indeed.py (Indeed como fuente, adivina el
dominio propio de la empresa para el email - sin tocar Brave/Bing/
DuckDuckGo), pero con otro ángulo de búsqueda: en vez de "desarrollador
web", apunta a automatización/bots/RPA - el perfil real de Germán (bots
para el Gobierno de la Provincia de Buenos Aires, -30% en tareas
manuales, ver cv-german-rodriguez.pdf).

Guarda en una pestaña NUEVA y separada de la misma planilla
(leads_automatizacion), no en leads_tracking.csv, para no mezclar este
perfil de búsqueda con las agencias de marketing / desarrollador web
genérico que ya cazan los otros scripts.

Uso: venv312/bin/python3 caza_programador.py --limit 10
"""
import argparse
import os
import sys
import time
import random
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
import requests

from cazar_indeed import (
    SEGUIMIENTO_HEADERS,
    SEGUIMIENTO_TAB,
    buscar_ofertas,
    encontrar_sitio_y_email,
    es_empresa_excluida,
)
from core.models import Lead, TrackType
from core.sheets_client import SheetsClient
from mensaje_contacto import detectar_formulario_contacto, generar_mensaje_automatizacion

# (etiqueta, query, ciudad, dominio de Indeed a usar)
QUERIES = [
    ("Automatización Buenos Aires", "automatizacion de procesos", "Buenos Aires", "ar.indeed.com"),
    ("Bot Python Argentina", "bot python", "Argentina", "ar.indeed.com"),
    ("RPA freelance Argentina", "RPA freelance", "Argentina", "ar.indeed.com"),
    ("Automatización Madrid", "automatizacion de procesos", "Madrid", "es.indeed.com"),
    ("RPA freelance España", "RPA freelance", "España", "es.indeed.com"),
    ("Automatización Ciudad de México", "automatizacion de procesos", "Ciudad de México", "mx.indeed.com"),
    ("Bot Python Bogotá", "bot python", "Bogotá", "co.indeed.com"),
    ("Automatización Santiago", "automatizacion de procesos", "Santiago", "cl.indeed.com"),
]

TAB = "leads_automatizacion"
HEADERS = ["Fecha envio", "Negocio/Agencia", "Track (PyME/Marketing)", "Rubro",
           "Ciudad", "Contacto", "Mail o IG", "Asunto usado", "Respondio (Si/No)",
           "Fecha follow-up 1", "Fecha follow-up 2", "Resultado"]


def cazar(limit=10, queries=None):
    session = requests.Session()
    leads = []
    sin_email = []  # (empresa, ciudad, sitio) - sitio real pero sin email
    seen_empresas = set()
    for label, query, ciudad, dominio_indeed in (queries or QUERIES):
        if len(leads) >= limit:
            break
        print(f"[BUSCA-AUTOMATIZACION] {query} en {ciudad}")
        ofertas = buscar_ofertas(query, ciudad, dominio_indeed, limit=15)
        print(f"  -> {len(ofertas)} ofertas reales")
        for empresa, ciudad_real in ofertas:
            if len(leads) >= limit:
                break
            key = empresa.lower()
            if key in seen_empresas:
                continue
            seen_empresas.add(key)
            if es_empresa_excluida(empresa):
                print(f"  [EXCLUIDA] {empresa} (multinacional grande, no es el target)")
                continue
            website, email = encontrar_sitio_y_email(empresa, dominio_indeed, session)
            if email:
                lead = Lead(
                    business_name=empresa,
                    email=email.lower(),
                    track=TrackType.PYME,
                    industry="Busca automatización/bot/RPA (oferta de empleo real)",
                    city=ciudad_real,
                    country="",
                    website=website,
                    source="Indeed",
                )
                leads.append(lead)
                print(f"  [REAL] {empresa} | {email} | {website}")
            elif website:
                sin_email.append((empresa, ciudad_real, website))
                print(f"  [SIN EMAIL - sitio real] {empresa} | {website}")
            else:
                print(f"  [SIN SITIO] {empresa}")
        time.sleep(3 * random.uniform(0.7, 1.4))
    return leads, sin_email


def _guardar_seguimiento_manual(sin_email, sheets, session):
    """Empresas con sitio real pero sin email: se guardan en la MISMA
    pestaña de seguimiento manual que usa cazar_indeed.py (es el mismo
    concepto - "revisar a mano"), pero con el mensaje adaptado a
    automatización/bots/RPA en vez del pitch de desarrollador web."""
    sheets.add_sheet(SEGUIMIENTO_TAB, headers=SEGUIMIENTO_HEADERS)
    # Se lee la columna B sola (Empresa), asi que cada fila es [valor] -> r[0]
    existentes = {r[0].strip().lower() for r in sheets.read_range(f"'{SEGUIMIENTO_TAB}'!B2:B10000") if r}

    filas = []
    for empresa, ciudad, website in sin_email:
        if empresa.strip().lower() in existentes:
            continue
        formulario = detectar_formulario_contacto(website, session=session) or ""
        filas.append([
            datetime.now().strftime("%d/%m/%Y"), empresa, ciudad, website,
            formulario, generar_mensaje_automatizacion(), "Indeed (automatización)",
        ])
    if filas:
        sheets.write_range(f"'{SEGUIMIENTO_TAB}'!A2", filas, append=True)
    return len(filas)


def main(limit=10, queries=None):
    sheets = SheetsClient()
    sheets.add_sheet(TAB, headers=HEADERS)
    existentes_raw = sheets.read_range(f"'{TAB}'!G2:G10000")
    existentes = {r[0].strip().lower() for r in existentes_raw if r and r[0]}
    print(f"[INFO] En '{TAB}': {len(existentes)} emails")

    nuevos, sin_email = cazar(limit=limit, queries=queries)
    frescos = [l for l in nuevos if l.email.lower() not in existentes]
    print(f"[INFO] Frescos: {len(frescos)}/{len(nuevos)}")

    if frescos:
        filas = [l.to_sheet_row() for l in frescos]
        sheets.write_range(f"'{TAB}'!A2", filas, append=True)
        for l in frescos:
            print(f"  [SHEETS] {l.business_name} <{l.email}>")
    print(f"[OK] Guardados: {len(frescos)}/{len(frescos)} en '{TAB}'")

    if sin_email:
        session = requests.Session()
        n = _guardar_seguimiento_manual(sin_email, sheets, session)
        print(f"[SEGUIMIENTO] {n} empresas sin email nuevas guardadas en '{SEGUIMIENTO_TAB}' para seguimiento manual")

    return len(frescos) > 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    a = ap.parse_args()
    sys.exit(0 if main(limit=a.limit) else 1)
