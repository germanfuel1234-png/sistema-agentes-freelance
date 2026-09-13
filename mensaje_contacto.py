"""Arma el mensaje de contacto para empresas donde NO se encontró un email
(pero sí un sitio propio real), adaptado del mail que ya usamos para
pitchear el mismo servicio por ese canal.

IMPORTANTE: este archivo NO completa ni envía ningún formulario. Solo
genera el texto y, si puede, detecta el link a la página de contacto del
sitio, para que sea el usuario quien decida completar el formulario a
mano. Completar/enviar formularios en nombre del usuario sin que él lo
haga y confirme cada uno es algo que este sistema no automatiza.
"""
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# Mismo pitch que el mail (core/constants.py EMAIL_TEMPLATE_BODY), adaptado
# a un mensaje corto para formulario de contacto (sin asunto, más breve, y
# mencionando explícitamente la oferta de empleo que vimos).
MENSAJE_TEMPLATE = """Hola,

Vi que están buscando un/a desarrollador/a web y quería presentarme: soy Germán Rodríguez, desarrollador web freelance (Buenos Aires, Argentina).

Si están evaluando resolver el proyecto con un freelance en vez de una contratación full-time, me encantaría ser una opción - sin los costos fijos de un empleado.

Te comparto mi portfolio: https://germanrodriguez.ar/

Quedo a disposición.
Saludos,
Germán Rodríguez"""


# Variante para leads que buscan automatización/bots/RPA (caza_programador.py),
# mencionando la experiencia real en vez del pitch genérico de "desarrollador web".
MENSAJE_TEMPLATE_AUTOMATIZACION = """Hola,

Vi que están buscando automatizar procesos y quería presentarme: soy Germán Rodríguez, desarrollador backend freelance (Buenos Aires, Argentina), especializado en automatización con Python.

Actualmente desarrollo bots de automatización operativa para el Gobierno de la Provincia de Buenos Aires, reduciendo tareas manuales en un 30%. Si están evaluando resolver esto con un freelance en vez de una contratación full-time, me encantaría ser una opción.

Te comparto mi portfolio: https://germanrodriguez.ar/

Quedo a disposición.
Saludos,
Germán Rodríguez"""


def generar_mensaje():
    """Devuelve el texto listo para pegar en un formulario de contacto."""
    return MENSAJE_TEMPLATE


def generar_mensaje_automatizacion():
    """Variante del mensaje para leads que buscan automatización/bots/RPA."""
    return MENSAJE_TEMPLATE_AUTOMATIZACION


def detectar_formulario_contacto(url, session=None):
    """Busca si el sitio tiene un <form> en la home o un link a una página
    de contacto. No completa ni envía nada - solo devuelve la URL de esa
    página para seguimiento manual. Devuelve None si no encuentra nada."""
    sess = session or requests
    try:
        r = sess.get(url, headers={"User-Agent": UA}, timeout=8)
        r.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    if soup.find("form"):
        return url

    for a in soup.find_all("a", href=True):
        texto = a.get_text(" ", strip=True).lower()
        href = a["href"].lower()
        if "contacto" in texto or "contact" in texto or "contacto" in href or "contact" in href:
            return urljoin(url, a["href"])
    return None
