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
