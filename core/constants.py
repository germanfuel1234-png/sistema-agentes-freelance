"""
Constantes y configuraciones compartidas entre agentes.
"""

# Email Templates
EMAIL_TEMPLATE_SUBJECT = "Developer freelance"

# Firma profesional
EMAIL_SIGNATURE = """
---
Germán Rodríguez
DESARROLLO WEB
Landing Pages · E-Commerce · Apps
rodriguezg.dev@gmail.com

germanrodriguez.ar
Zona Oeste · Buenos Aires, Argentina
Backend & Automatización · Docente
"""

EMAIL_TEMPLATE_BODY = """Hola {contact_name},

Soy Germán Rodríguez, desarrollador web freelance.

Trabajo con agencias y freelancers de marketing armando las webs, landings y sistemas
que ustedes les prometen a sus clientes.

Te comparto mi página web:
https://germanrodriguez.ar/

Si en algún momento tenés un desarrollo que necesiten resolver, me encantaría ser esa opción.

¡Saludos!
Germán
""" + EMAIL_SIGNATURE

# Version en ingles del primer contacto, para leads de mercados de habla
# inglesa (EEUU, Canada) que ahora tambien busca loop_caza.py. Misma firma
# (EMAIL_SIGNATURE) - cambia el cuerpo, no el nombre/contacto de abajo.
EMAIL_SUBJECT_EN = "💾 Freelance Web Developer"

PORTFOLIO_URL = "https://germanrodriguez.ar/"

# Version texto plano SIN firma - la usa gemini_service.py directamente
# (GmailService agrega la firma sola). El link va como URL pelada, no hay
# forma de hacer "portfolio" clickeable sin HTML.
EMAIL_TEMPLATE_BODY_EN_PLAIN = f"""Hi,

I'm a web developer and programmer specializing in partnering with marketing agencies and professionals to provide technical support for their campaigns. I handle everything from building high-converting landing pages to developing custom web systems.

I'm reaching out to introduce myself and get on your radar. If you ever face a high workload or need a reliable developer to delegate a project to, I'd be glad to help.

You can check out my portfolio to see my work here: {PORTFOLIO_URL}

Best regards,"""

# Con firma incluida - para usos directos fuera de gemini_service.py
# (que agrega la firma por su cuenta via GmailService).
EMAIL_TEMPLATE_BODY_EN = EMAIL_TEMPLATE_BODY_EN_PLAIN + "\n" + EMAIL_SIGNATURE

# Version HTML - "portfolio" queda como link real en vez de mostrar el URL
# pelado. Usar con Email.html_body (ver core/models.py y
# GmailService.send_email, que lo prioriza sobre Email.body si viene seteado).
EMAIL_TEMPLATE_BODY_EN_HTML = f"""Hi,<br><br>

I'm a web <strong>developer</strong> and programmer specializing in partnering with marketing agencies and professionals to provide technical <strong>support</strong> for their campaigns. I handle everything from building high-converting <strong>landing pages</strong> to developing custom web systems.<br><br>

I'm reaching out to <strong>introduce myself</strong> and get on your radar. If you ever face a high workload or need a <strong>reliable developer</strong> to delegate a project to, I'd be glad to help.<br><br>

You can check out my <a href="{PORTFOLIO_URL}">portfolio</a> to see my work here:<br><br>

Best regards,"""

# Marcadores de texto (en minuscula) que identifican un mercado de habla
# inglesa a partir del campo `city` de un Lead (que en este sistema
# funciona como "ubicacion" en general, no solo la ciudad - ver
# cazar_brave.py). Se usa para decidir el idioma del primer contacto.
_MERCADOS_INGLES = [
    "united states", "usa", "eeuu", "estados unidos",
    "canada", "canadá",
    "united kingdom", "uk", "reino unido",
    "australia", "new zealand", "ireland", "irlanda",
]


def es_mercado_ingles(ubicacion: str) -> bool:
    """True si `ubicacion` (tipicamente lead.city) corresponde a un
    mercado de habla inglesa - decide si el primer contacto se manda en
    inglés en vez de español."""
    u = (ubicacion or "").lower()
    return any(marca in u for marca in _MERCADOS_INGLES)

# Lead Search
EXCLUDED_COMPANIES = [
    "mercadolibre",
    "globant",
    "telefónica",
    "accenture",
    "infosys",
    "tcs",
    "ibm",
    "deloitte",
    "pwc",
    "kpmg",
    "bdo",
    "capgemini",
]

MARKETING_KEYWORDS = [
    "agencia de marketing",
    "marketing digital",
    "community manager",
    "social media",
    "marketing freelance",
    "consultor de marketing",
    "especialista en marketing",
]

TARGET_INDUSTRIES = [
    "Marketing",
    "Publicidad",
    "Diseño Gráfico",
    "Social Media",
    "Consultoría",
    "Servicios Profesionales",
]

# Pricing Adjustments (como porcentajes)
COMPLEXITY_MULTIPLIERS = {
    "simple": 1.0,
    "media": 1.3,
    "alta": 1.6,
    "urgente": 1.5,
}

ADDON_PRICES = {
    "seo": 0.15,           # +15% del precio base
    "analytics": 0.10,     # +10%
    "crm_integration": 0.12,  # +12%
    "maintenance_3m": 0.18,   # +18%
}

# Limits
MAX_DAILY_EMAILS = 20
MAX_LEADS_PER_SEARCH = 50

# Search Channels
SEARCH_CHANNELS = {
    "linkedin": {"enabled": True, "priority": 1},
    "google_maps": {"enabled": True, "priority": 2},
    "google_search": {"enabled": True, "priority": 3},
    "workana": {"enabled": False, "priority": 4},  # Future
    "upwork": {"enabled": False, "priority": 5},   # Future
}

# API Limits
GEMINI_MAX_TOKENS = 1000
SEARCH_TIMEOUT_SECONDS = 10
