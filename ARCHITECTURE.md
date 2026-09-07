# 📐 ARQUITECTURA — Sistema de Agentes Freelance

## 🎯 Visión General

Este es un sistema de **4 agentes especializados** que trabajan sobre **Google Sheets como memoria compartida**, sin automatismo puro. Cada agente hace una cosa bien, y **todo requiere tu aprobación antes de ejecutarse**.

### Patrón clave: Supervisor Humano Integrado

```
Usuario (vos)
    ↓
[Requests API → Agente]
    ↓
[Agente ejecuta → prepara resultado]
    ↓
IF requiere_aprobacion THEN
    → Muestra preview en dashboard
    → Espera tu click "Aprobar"
    → Ejecuta acción real (mail, presupuesto, etc.)
ELSE
    → Ejecuta y retorna resultado
```

---

## 📂 Módulos Core

### 1. **`config/settings.py`** — Configuración

Carga variables de `.env` y expone constantes:

```python
settings.google_sheet_id          # ID de la Sheet
settings.gmail_client_id          # OAuth2 de Gmail
settings.gemini_api_key           # API key de Gemini
settings.daily_email_limit        # Máximo 20 mails/día
settings.your_website_url         # https://germanrodriguez.ar
```

**Patrón**: Singleton global → todos los módulos lo importan.

---

### 2. **`core/models.py`** — Estructuras de Datos

Define los objetos principales (dataclasses con métodos útiles):

```python
class Lead:
    """Un prospecto/cliente potencial"""
    business_name: str      # Negocio/Agencia
    track: TrackType        # PyME o Marketing
    email: str
    send_status: SendStatus # Pendiente, Enviado, Respondió, etc.
    
    def is_pending() → bool
    def to_sheet_row() → List  # Convierte a fila para escribir

class Email:
    """Mail listo para enviar"""
    to: str
    subject: str
    body: str
    lead_id: str
    approval_token: str

class Budget:
    """Presupuesto personalizado"""
    client_name: str
    project_description: str
    total_price_ars: float
    status: BudgetStatus
    proposal_text: str

class Price:
    """Precio base de servicio"""
    service: str           # "Landing Page", "E-Commerce", etc.
    base_price_ars: float

class WebStudy:
    """Resultado del análisis de germanrodriguez.ar"""
    services: List[Price]
    target_industries: List[str]
    value_proposition: str
```

**Patrón**: Cada modelo tiene `to_sheet_row()` para escribir a Google Sheets.

---

### 3. **`core/sheets_client.py`** — Cliente Google Sheets

Wrapper alrededor de Google Sheets API:

```python
class SheetsClient:
    # CRUD básico
    read_range(range_name: str) → List[List[str]]
    write_range(range_name: str, values: List[List[str]], append=False) → bool
    
    # Leads
    get_all_leads() → List[Lead]
    get_pending_leads() → List[Lead]
    add_lead(lead: Lead) → bool
    update_lead(lead: Lead, row_id: int) → bool
    
    # Budgets
    get_all_budgets() → List[Budget]
    add_budget(budget: Budget) → bool
    
    # Prices
    get_all_prices() → List[Price]
    update_prices(prices: List[Price]) → bool
```

**Flujo de autenticación:**
1. Primera ejecución: lanza navegador → OAuth2 → genera `token.json`
2. Siguientes: reutiliza token persistente
3. Si expira, refresca automáticamente

**Rango de la Sheet:**
- `leads_tracking!A1:L1000` — tabla de leads
- `precios_base!A1:E100` — tabla de precios
- `presupuestos!A1:H100` — tabla de presupuestos

---

### 4. **`core/constants.py`** — Configuración de Negocio

Parámetros editables:

```python
EMAIL_TEMPLATE_SUBJECT = "Developer freelance"
EMAIL_TEMPLATE_BODY = "Hola {contact_name}..."

EXCLUDED_COMPANIES = ["mercadolibre", "globant", "telefonica", ...]
MARKETING_KEYWORDS = ["agencia de marketing", "community manager", ...]

COMPLEXITY_MULTIPLIERS = {
    "simple": 1.0,
    "media": 1.3,
    "alta": 1.6,
}

MAX_DAILY_EMAILS = 20
MAX_LEADS_PER_SEARCH = 50
```

---

## 🤖 Los 4 Agentes

### Estructura Común

Todos heredan de `BaseAgent` y siguen este patrón:

```
Agente.run(args)
    ↓
execute(args) → (output, requires_approval: bool)
    ↓
IF requires_approval:
    → Retorna AgentResult con approval_token
    → Status = WAITING_APPROVAL
ELSE:
    → Completa inmediatamente
    → Status = COMPLETE
    ↓
[Si requería aprobación]
Usuario ve preview en dashboard → Click "Aprobar"
    ↓
Agente.approve(approval_token)
    ↓
on_approved(output)  # Hook que ejecuta la acción real
```

---

### Agent 0: Estudio de Web 🔍

**Objetivo:** Mantener actualizada la tabla de precios.

**Entrada:** Nada (se dispara manual con "Estudiar Web")

**Proceso:**
1. Scraping de germanrodriguez.ar (TODO)
2. Extrae servicios, precios, posicionamiento
3. Actualiza tabla `precios_base` en Sheet

**Salida:**
```python
WebStudy(
    services=[
        Price("Landing Page", 100000, "...", 7),
        Price("Web Corporativa", 400000, "...", 14),
        ...
    ],
    target_industries=["Estudios jurídicos", "Consultorios médicos", ...],
    value_proposition="...",
)
```

**¿Requiere aprobación?** ❌ No
- Es información que vos pedís explícitamente
- Solo lee y actualiza tabla de precios
- No toma decisiones ni envía nada

---

### Agent 1: Buscador de Leads 🔎

**Objetivo:** Encontrar agencias sin developer.

**Entrada:**
```python
country: str = "Argentina"      # Dónde buscar
limit: int = 10                 # Cantidad
```

**Proceso:**
1. Búsqueda vía APIs (Google Custom Search, web scraping)
2. Filtra EXCLUIDOS (Mercadolibre, Globant, etc.)
3. Busca palabra clave (agencia, marketing, freelancer)
4. Cruza contra leads existentes (evita duplicados)
5. Agrega filas nuevas a `leads_tracking` con `Enviado?=Pendiente`

**Salida:**
```python
[
    Lead(
        business_name="Agencia XYZ",
        contact_name="Juan",
        email="juan@xyz.com",
        send_status=SendStatus.PENDING,
        ...
    ),
    ...
]
```

**¿Requiere aprobación?** ❌ No
- Solo lectura de web + escritura de nuevas filas
- No envía mails ni hace cambios de estado
- Vos revisas los leads después (en la planilla o en la tabla del dashboard)

---

### Agent 2: Redactor y Enviador de Mails ✉️

**Objetivo:** Tomar leads Pendiente, mostrar borradores, enviar con aprobación.

**Entrada:**
```python
limit: int = 5                  # Cuántos mails preparar
```

**Proceso:**
1. Busca leads con `send_status=PENDING`
2. Arma mail con plantilla fija (asunto + cuerpo)
3. Retorna preview para review

**Salida (antes de aprobación):**
```python
{
    "emails": [
        {
            "to": "juan@agenciaxyz.com",
            "subject": "Developer freelance",
            "body_preview": "Hola Juan, soy Germán..."
        },
        ...
    ],
    "count": 5,
}
```

**En el dashboard:**
- Ve preview de cada mail
- Button "✅ Aprobar"
- Vos aprobás → Agente envía vía Gmail API

**¿Requiere aprobación?** ✅ SÍ
- Antes de enviar mail, mostrá preview
- No se pueden enviar sin tu ok explícito
- Regla dura: un envío por lead (nunca reenvía)

---

### Agent 3: Armador de Presupuestos 💰

**Objetivo:** Generar propuesta de precio personalizada.

**Entrada:**
```python
client_name: str                # "Agencia XYZ"
project_description: str        # "Necesitan landing + CRM"
```

**Proceso:**
1. Obtiene precio base según tipo proyecto (Landing, Web, Ecommerce, etc.)
2. Ajusta por complejidad (descrito en brief)
3. Suma adicionales si menciona (SEO, CRM, mantenimiento)
4. Genera texto de propuesta (Gemini)
5. Retorna Budget con monto calculado

**Salida (antes de aprobación):**
```python
Budget(
    client_name="Agencia XYZ",
    project_description="Landing + CRM",
    base_price_ars=100000,
    adjustments_ars=30000,
    total_price_ars=130000,
    estimated_days=7,
    proposal_text="<HTML propuesta>",
)
```

**En el dashboard:**
- Ve monto total, alcance, plazo
- Button "✅ Aprobar Monto"
- Vos aprobás → Agente guarda en Sheet en estado DRAFT

**¿Requiere aprobación?** ✅ SÍ
- Vos siempre aprobás montos antes de archivarlos
- Protege contra cálculos incorrectos

---

## 🌊 Flujos de Datos

### Flujo 1: Búsqueda → Mail → Respuesta

```
Agent 1 busca leads
    ↓
Agrega fila: business_name, email, send_status=PENDING
    ↓ (Sheet actualizada)
    ↓
Agent 2 lee Sheet: "¿hay leads PENDING?"
    ↓
Prepara mails (plantilla fija)
    ↓
Muestra preview en dashboard
    ↓
Usuario: "Mira bien, ¿apruebo?"
    ↓
Click "Aprobar" → Agent 2 envía vía Gmail API
    ↓
Agente marca: send_status=SENT, send_date=HOY, asunto_usado="Developer freelance"
    ↓ (Sheet actualizada)
    ↓
[Cliente responde...]
    ↓
Usuario marca manualmente en Sheet: send_status=REPLIED
```

### Flujo 2: Presupuesto

```
Cliente: "Necesito landing + integración"
    ↓
Usuario abre Agent 3, completa:
    client_name: "Agencia XYZ"
    project_description: "Landing con CRM de HubSpot"
    ↓
Agent 3 calcula:
    base (Landing) = 100k
    + complejidad (CRM) = +30k
    + integración = +12%
    = 130k
    ↓
Genera propuesta HTML con Gemini
    ↓
Muestra en dashboard: "$130.000 ARS | Landing + CRM"
    ↓
Usuario: "Suena bien" → Click "Aprobar"
    ↓
Agent 3 guarda en Sheet:
    pestaña "presupuestos"
    status: "BORRADOR"
    (Usuario luego lo envía por mail cuando quiera)
```

### Flujo 3: Actualización de Precios

```
Agent 0 corre (manual):
    Scraping de germanrodriguez.ar
    ↓
Extrae:
    - Landing: $100k
    - Web Corp: $400k
    - Ecommerce: $530k
    - Sistemas: $500k
    ↓
Actualiza Sheet: pestaña "precios_base"
    ↓
Agent 3 lee estos precios cuando calcula presupuesto
```

---

## 🔌 Integraciones Externas (TODO)

### Google Sheets API ✅ (Base)

```python
from core.sheets_client import SheetsClient

sheets = SheetsClient()  # Autentica automáticamente
leads = sheets.get_all_leads()
sheets.add_lead(new_lead)
```

### Gmail API (TODO)

```python
# services/gmail_service.py
class GmailService:
    def send_email(email: Email) → str:  # Retorna message_id
        # OAuth2, construye mensaje, envía
```

### Gemini API (TODO)

```python
# services/gemini_service.py
class GeminiService:
    def generate_mail_body(lead: Lead) → str
    def generate_budget_proposal(budget: Budget) → str
```

### Web Scraping (TODO)

```python
# services/web_scraper.py
class WebScraper:
    def scrape_germanrodriguez_ar() → WebStudy
    def search_leads_linkedin(query) → List[Lead]
    def search_leads_google_maps(query) → List[Lead]
```

---

## 🎛️ FastAPI Dashboard

### Rutas

```
GET  /                              # HTML dashboard
GET  /health                        # Status check

GET  /api/leads                     # Todos los leads
GET  /api/leads/pending             # Solo pendientes

POST /api/agents/agent_0/run        # Estudiar web
POST /api/agents/agent_1/run        # Buscar leads
POST /api/agents/agent_2/run        # Preparar mails
POST /api/agents/agent_3/run        # Armar presupuesto

POST /api/agents/{agent}/approve    # Aprobar resultado
```

### Estado de la App

```python
app.state.sheets_client             # Cliente Google Sheets (global)
app.state.agents = {                # Instancias de los 4 agentes
    "agent_0": Agent0WebStudy(...),
    "agent_1": Agent1SearchLeads(...),
    "agent_2": Agent2SendEmails(...),
    "agent_3": Agent3BudgetBuilder(...),
}
```

---

## 🚀 Cómo Usar

### 1. Setup

```bash
cd sistema_agentes_freelance

# .env
GOOGLE_SHEET_ID=1hjwAUrKaCu53McleYaJZj99b65IoKHBVqIZ96qfvF1I
GMAIL_CLIENT_ID=xxx
GMAIL_CLIENT_SECRET=xxx
GEMINI_API_KEY=xxx
YOUR_EMAIL=tuemail@example.com

# Dependencias
pip install -r requirements.txt

# Start
python main.py
# → http://localhost:8000
```

### 2. Dashboard

**Barra de Status:**
- Leads totales (cargados de Sheet)
- Pendientes de envío
- Estado de conexión a Sheet

**Panel Agent 0:**
Button "Estudiar Web" → Lee germanrodriguez.ar → Actualiza precios

**Panel Agent 1:**
- Input: País, Límite
- Button "Buscar Leads"
- Resultado: "5 leads nuevos añadidos"

**Panel Agent 2:**
- Input: Límite de mails
- Button "Preparar Mails"
- Si hay leads pendientes → Muestra preview
- Button "✅ Aprobar" → Envía

**Panel Agent 3:**
- Inputs: Cliente, Proyecto
- Button "Armar Presupuesto"
- Muestra: Monto, plazo, alcance
- Button "✅ Aprobar Monto" → Guarda en Sheet

**Tabla Leads:**
Todos los leads con estado (Pendiente, Enviado, Respondió)

---

## 🔐 Reglas Duras (No negociables)

1. **Un envío por lead.** Nunca se reenvía a la misma persona (Agent 2 lo valida)
2. **Aprobación previa.** Nada de mails ni presupuestos se envía sin tu ok
3. **Plantilla fija.** Agent 2 usa siempre el mismo asunto y cuerpo (vos lo definís en `constants.py`)
4. **Exclusiones.** Agent 1 no sugiere companies grandes con equipo tech
5. **Target claro.** Agencias 3-15 personas, freelancers, no cliente final
6. **Límites.** Max 20 mails/día, max 50 leads/búsqueda

---

## 📊 Persistencia

Todo vive en **Google Sheets** (una sola fuente de verdad):

| Pestaña | Propósito | Actualiza |
|---------|-----------|-----------|
| `leads_tracking` | Lead, fecha envío, estado, resultado | Agent 1, Agent 2 |
| `precios_base` | Precio por servicio | Agent 0 |
| `presupuestos` | Presupuestos generados | Agent 3 |

---

## 🛣️ Próximos Pasos (MVP → V2)

### MVP (ahora)
- ✅ Estructura base
- ✅ Agentes con lógica mock
- ✅ Dashboard con control manual
- ⏳ Gmail API real
- ⏳ Gemini para generación de texto
- ⏳ Web scraping real

### V2 (escalabilidad)
- [ ] Schedules: Agent 1 busca cada lunes
- [ ] Agent 2 notifica diario: "X leads pendientes"
- [ ] Webhook: cuando cliente responde → Agent 3 sugiere presupuesto
- [ ] Multi-user: roles (Admin, Sales, Approver)
- [ ] Analytics: conversion rate, response time, etc.
- [ ] Canales extras: LinkedIn, WhatsApp

---

## 💡 Decisiones de Diseño

### ¿Por qué Google Sheets como DB?

- Ya lo usas → cero aprendizaje
- Visible y editable a mano → transparency
- Histórico automático → audit trail
- Comparte fácil con otros

### ¿Por qué no automatismo total?

- Reglas de compliance: un envío por persona
- Riesgo: automático puede romper marca
- Control: vos decidís cuándo enviar

### ¿Por qué FastAPI?

- Rápido, moderno, async nativo
- Documentación automática (/docs)
- Escalable (uvicorn → gunicorn → cloud)

### ¿Por qué async?

- Agentes corren sin bloquear (buenos para IO: Google APIs)
- Dashboard responsivo mientras busca leads
- Pronto: múltiples búsquedas en paralelo

---

**Ready to code?** 🚀

Siguiente paso: conectar Gmail + Gemini + web scraping en los servicios. ¿Quieres que empecemos con uno en particular?
