# 🎬 FLUJOS DE DATOS EN ACCIÓN

Documentación de cómo fluyen los datos entre módulos y APIs en casos reales.

---

## 📍 Caso 1: Usuario Busca 10 Leads Nuevos

### Vista General
```
Dashboard Web
    ↓ [Usuario: País="Argentina", Limit=10]
    ↓ (POST /api/agents/agent_1/run)
    ↓
FastAPI
    ↓ (obtiene "agent_1" del app.state)
    ↓
Agent1SearchLeads.run(country="Argentina", limit=10)
    ↓
execute()
    ├─ 🔍 Busca vía Web APIs (Google Search API, scraping, etc.)
    │   └─ Retorna: [lead_1, lead_2, ..., lead_10]
    │
    ├─ SheetsClient.get_all_leads()
    │   └─ Lee Google Sheet "leads_tracking"
    │   └─ Retorna: [lead_old_1, lead_old_2, ...]
    │
    ├─ Filtra duplicados (email ya existe)
    │   └─ new_leads = [lead_3, lead_5, lead_7]
    │
    └─ SheetsClient.add_lead(lead) x3
        └─ Escribe a Sheet: filas nuevas
        └─ Cada fila: [business_name, contact, email, ..., send_status="Pendiente"]
    
    ↓
    output = [lead_3, lead_5, lead_7]
    requires_approval = False
    ↓
Retorna: AgentResult(status="complete", output=[...], duration=2.3s)
    ↓
FastAPI → JSON response
    ↓
Dashboard: "✅ 3 leads nuevos añadidos"
Tabla se actualiza (auto-refresh cada 10s)
```

### Cambios en Google Sheet

**Antes:**
```
| Negocio | Contacto | Email | Track | Enviado? |
|---------|----------|-------|-------|----------|
| Agencia A | Juan | juan@a.com | Marketing | Enviado (28/8) |
```

**Después (3 filas nuevas agregadas):**
```
| Negocio | Contacto | Email | Track | Enviado? |
|---------|----------|-------|-------|----------|
| Agencia A | Juan | juan@a.com | Marketing | Enviado (28/8) |
| Agencia B | María | maria@b.com | Marketing | Pendiente | ← NEW
| Freelancer C | Pedro | pedro@c.com | Marketing | Pendiente | ← NEW
| Agencia D | Sofia | sofia@d.com | Marketing | Pendiente | ← NEW
```

---

## 📍 Caso 2: Usuario Prepara 5 Mails

### Vista General
```
Dashboard Web
    ↓ [Usuario: Limit=5]
    ↓ (POST /api/agents/agent_2/run)
    ↓
Agent2SendEmails.run(limit=5)
    ↓
execute()
    ├─ SheetsClient.get_pending_leads()
    │   └─ Query: send_status == "Pendiente"
    │   └─ Retorna: [lead_1, lead_2, lead_3, lead_4, lead_5]
    │
    ├─ Para cada lead:
    │   └─ body = EMAIL_TEMPLATE_BODY.format(contact_name="María")
    │   └─ Email(
    │       to="maria@b.com",
    │       subject="Developer freelance",
    │       body="Hola María, soy Germán...",
    │       lead_id="2"
    │   )
    │   └─ self.emails_to_send.append(email)
    │
    └─ return {
        "emails": [email_1, email_2, ...],
        "count": 5,
        "preview": [
            {"to": "maria@b.com", "subject": "...", "body_preview": "..."},
            ...
        ]
    }, True  ← REQUIERE APROBACIÓN
    
    ↓
AgentResult(
    status="waiting_approval",
    output={...},
    requires_approval=True,
    approval_token="550e8400-e29b-41d4-a716-446655440000"
)
    ↓
FastAPI → JSON
    ↓
Dashboard: Muestra preview de 5 mails
         Button: "✅ Aprobar"
```

### Si Usuario Aprueba

```
Dashboard
    ↓ [Usuario: Click "Aprobar"]
    ↓ (POST /api/agents/agent_2/approve?approval_token=550e8400...)
    ↓
FastAPI
    ↓
Agent2SendEmails.approve(approval_token="550e8400...")
    ├─ Valida token (debe coincidir con current_result)
    ├─ Llama: on_approved(output)
    │   ├─ Para cada email en self.emails_to_send:
    │   │   ├─ GmailService.send_email(email)
    │   │   │   └─ OAuth2 → Gmail API
    │   │   │   └─ Retorna: message_id
    │   │   │
    │   │   └─ SheetsClient.update_lead(
    │   │       lead_id=2,
    │   │       send_status="Enviado",
    │   │       send_date="2025-09-06",
    │   │       asunto_usado="Developer freelance"
    │   │   )
    │   │   └─ Gmail actualiza Sheet
    │   │
    │   └─ Log: "✅ 5 mails enviados"
    └─ status = "complete"
    
    ↓
Dashboard: "✅ 5 mails enviados exitosamente"
Tabla se actualiza: send_status = "Enviado"
```

### Cambios en Google Sheet

**Antes:**
```
| Negocio | Email | send_status | send_date | subject_used |
|---------|-------|-------------|-----------|--------------|
| Agencia B | maria@b.com | Pendiente | | |
```

**Después:**
```
| Negocio | Email | send_status | send_date | subject_used |
|---------|-------|-------------|-----------|--------------|
| Agencia B | maria@b.com | Enviado | 2025-09-06 | Developer freelance |
```

---

## 📍 Caso 3: Cliente Responde → Generar Presupuesto

### Contexto

Cliente (Agencia B) responde:
> "Hola Germán, nos interesa. Necesitamos una landing page + integración con HubSpot CRM para esta campaña."

### Vista General

```
Usuario: "Dame presupuesto para Agencia B, necesita landing + CRM"
    ↓
Dashboard
    ├─ client_name: "Agencia B"
    └─ project_description: "Landing page + integración HubSpot CRM"
    ↓ (POST /api/agents/agent_3/run)
    ↓
Agent3BudgetBuilder.run(
    client_name="Agencia B",
    project_description="Landing page + integración HubSpot CRM"
)
    ↓
execute()
    ├─ SheetsClient.get_all_prices()
    │   └─ Lee pestaña "precios_base"
    │   └─ Retorna: [
    │       Price("Landing Page", 100000),
    │       Price("Web Corporativa", 400000),
    │       Price("E-Commerce", 530000),
    │       ...
    │   ]
    │
    ├─ Análisis del brief (con IA)
    │   ├─ "landing page" → Price("Landing Page") = 100.000
    │   ├─ "HubSpot CRM" → integración = +12% → +12.000
    │   ├─ Complejidad media = 1.3x → 132.000
    │   └─ Ajuste final: 130.000 (redondeado)
    │
    ├─ GeminiService.generate_budget_proposal(project, base_price)
    │   └─ Prompt: "Genera propuesta profesional para [Agencia B]..."
    │   └─ Retorna: HTML con descripción, alcance, precio, plazo
    │
    └─ return Budget(
        client_name="Agencia B",
        project_description="Landing + CRM",
        base_price_ars=100000,
        adjustments_ars=30000,
        total_price_ars=130000,
        estimated_days=7,
        proposal_text="<html>...</html>",
        status=BudgetStatus.DRAFT
    ), True  ← REQUIERE APROBACIÓN
    
    ↓
AgentResult(
    status="waiting_approval",
    output=Budget(...),
    requires_approval=True,
    approval_token="660e8400-e29b-41d4-a716-446655440001"
)
    ↓
Dashboard: Muestra
    - Cliente: Agencia B
    - Proyecto: Landing + CRM
    - Base: $100.000
    - Ajustes: +$30.000
    - Total: $130.000
    - Plazo: 7 días
    Button: "✅ Aprobar Monto"
```

### Si Usuario Aprueba

```
Dashboard
    ↓ [Usuario: Click "Aprobar"]
    ↓ (POST /api/agents/agent_3/approve?token=660e8400...)
    ↓
Agent3BudgetBuilder.approve(token)
    ├─ SheetsClient.add_budget(budget)
    │   └─ Escribe fila en pestaña "presupuestos"
    │   └─ Columnas: Fecha, Cliente, Proyecto, Alcance, Monto, Moneda, Status, Notas
    │   └─ Status: "BORRADOR" (no enviado aún)
    │
    └─ status = "complete"
    
    ↓
Dashboard: "✅ Presupuesto guardado"
Tabla "Presupuestos" se actualiza
```

### Cambios en Google Sheet (Pestaña "presupuestos")

**Fila nueva agregada:**
```
| Fecha | Cliente | Proyecto | Alcance | Monto | Moneda | Status | Notas |
|-------|---------|----------|---------|-------|--------|--------|-------|
| 2025-09-06 | Agencia B | Landing + CRM | Landing con integración HubSpot | 130000 | ARS | Borrador | |
```

---

## 📍 Caso 4: Actualizar Precios (Agent 0)

### Vista General

```
Usuario: "Voy a actualizar precios de mi web"
    ↓
[Modifica https://germanrodriguez.ar/]
    ├─ Cambio: Landing Page de $100k → $120k
    └─ Nueva sección: "Auditoría SEO" desde $50k
    ↓
[Vuelve al dashboard]
    ↓ (POST /api/agents/agent_0/run)
    ↓
Agent0WebStudy.run()
    ↓
execute()
    ├─ WebScraperService.scrape_germanrodriguez_ar()
    │   └─ Descarga HTML de tu web
    │   └─ Busca tabla de precios
    │   └─ Extrae: [
    │       Price("Landing Page", 120000),  ← NUEVO
    │       Price("Web Corporativa", 400000),
    │       ...
    │       Price("Auditoría SEO", 50000),  ← NUEVO
    │   ]
    │
    ├─ Extrae posicionamiento
    │   └─ value_proposition: "Desarrollo web profesional..."
    │   └─ target_industries: ["Estudios jurídicos", "Consultorios", ...]
    │
    ├─ SheetsClient.update_prices(prices)
    │   └─ Sobrescribe pestaña "precios_base"
    │   └─ Filas actualizadas
    │
    └─ return WebStudy(...), False  ← NO REQUIERE APROBACIÓN
    
    ↓
Dashboard: "✅ Web estudiada. Precios actualizados."
```

### Cambios en Google Sheet (Pestaña "precios_base")

**Antes:**
```
| Servicio | Precio (ARS) | Descripción | Días |
|----------|--------------|-------------|------|
| Landing Page | 100000 | ... | 7 |
| Web Corporativa | 400000 | ... | 14 |
```

**Después:**
```
| Servicio | Precio (ARS) | Descripción | Días |
|----------|--------------|-------------|------|
| Landing Page | 120000 | ... | 7 | ← ACTUALIZADO
| Web Corporativa | 400000 | ... | 14 |
| Auditoría SEO | 50000 | Análisis completo de SEO | 3 | ← NUEVO
```

**Ahora cuando genere presupuesto (Agent 3), usará estos precios actualizados.**

---

## 🔄 Ciclo Completo: Lead → Mail → Respuesta → Presupuesto

```
Semana 1
├─ Lunes: Agent 1 busca 20 leads nuevos
│  └─ Agrega 15 filas a "leads_tracking" (send_status=Pendiente)
│
├─ Martes-Jueves: Agent 2 (manual cada día)
│  ├─ Day 1: Prepara 7 mails, aprueba, envía
│  ├─ Day 2: Prepara 5 mails, aprueba, envía
│  └─ Day 3: Prepara 3 mails, aprueba, envía
│  └─ Total: 15 leads con send_status=Enviado
│
├─ Friday-Friday siguiente: Espera respuestas
│  └─ Algunos clientes responden (tu inbox de Gmail)
│  └─ Vos marcas manualmente en Sheet: send_status=REPLIED
│
Semana 2
├─ Cliente A responde: "Necesito landing"
│  └─ Agent 3: Presupuesto $120k
│  └─ Presupuesto guardado en Sheet, status=BORRADOR
│  └─ Vos lo envías por mail (copia-pega o archivo)
│
├─ Cliente B responde: "Completa, con CRM + pagos"
│  └─ Agent 3: Presupuesto $530k (E-Commerce)
│  └─ Presupuesto guardado
│
└─ Cliente C no responde
   └─ Vos esperas, o marcar como "Sin respuesta" en Sheet
```

---

## 🔗 Mapa de Dependencias

```
config/settings.py
    ↓ (importado por todos)
    ├─ config/settings.Settings
    │
core/models.py
    ↓ (estructuras de datos)
    ├─ Lead, Email, Budget, Price, WebStudy
    │
core/sheets_client.py
    ├─ Imports: config.settings, core.models
    ├─ Usa: Google Sheets API
    │
core/constants.py
    ├─ Constantes de negocio
    │
agents/base_agent.py
    ├─ Clase abstracta BaseAgent
    │
agents/agent_*.py
    ├─ Agent0, Agent1, Agent2, Agent3
    ├─ Imports: base_agent.BaseAgent, core.sheets_client, core.models
    │
services/gmail_service.py (TODO)
    ├─ Gmail API wrapper
    │
services/gemini_service.py (TODO)
    ├─ Gemini API wrapper
    │
services/web_scraper.py (TODO)
    ├─ Web scraping
    │
web/app.py
    ├─ FastAPI app
    ├─ Imports: config.settings, agents/*, core/sheets_client
    ├─ Inicializa: SheetsClient, 4 Agents
    ├─ app.state.sheets_client, app.state.agents
    │
web/routes.py
    ├─ Endpoints API
    ├─ Imports: web.app (app), agents
    │
web/static/index.html, css, js
    ├─ Frontend
    ├─ Llama: /api/agents/*/run, /api/agents/*/approve

main.py
    └─ Entrypoint (uvicorn)
```

---

## 📝 Flujos de Aprobación

### Pattern: Agent con Aprobación (Agent 2 y 3)

```
Cliente Frontend
    │
    ├─ POST /api/agents/agent_2/run
    │   └─ Response: {
    │       status: "waiting_approval",
    │       requires_approval: True,
    │       approval_token: "UUID",
    │       output: { emails: [...] }
    │   }
    │
    ├─ Usuario ve preview
    │
    └─ Si aprueba:
        ├─ POST /api/agents/agent_2/approve?token=UUID
        │   └─ Agent.approve(token)
        │   ├─ Valida token
        │   └─ on_approved(output)  ← Acción real
        │
        └─ Response: {
            status: "complete",
            ...
        }
```

---

## 🚨 Error Handling

```
Si Agent 1 (búsqueda) falla:
├─ Valida conexión a Google Sheets
├─ Valida APIs de búsqueda
└─ Retorna: AgentResult(status="error", error="Detail")

Si Agent 2 no puede enviar mail:
├─ Valida credenciales OAuth2
├─ Si token expiró → recarga
├─ Si falla → marca lead como "error_envío" en notas
└─ User puede reintentar manualmente

Si Agent 3 calcula mal presupuesto:
└─ Vos lo revisas antes de aprobar (safeguard)
```

---

## 📊 Estado de la App en Memoria

```
FastAPI app.state:
├─ sheets_client: SheetsClient
│   ├─ creds: Credentials (OAuth2)
│   ├─ service: googleapiclient.sheets.Resource
│   └─ sheet_id: "1hjwAUrKa..."
│
└─ agents: Dict[str, BaseAgent]
    ├─ "agent_0": Agent0WebStudy(sheets_client)
    │   └─ current_result: Optional[AgentResult]
    │
    ├─ "agent_1": Agent1SearchLeads(sheets_client)
    │   └─ current_result: Optional[AgentResult]
    │
    ├─ "agent_2": Agent2SendEmails(sheets_client)
    │   ├─ current_result: Optional[AgentResult]
    │   └─ emails_to_send: List[Email]  ← Borradores en RAM
    │
    └─ "agent_3": Agent3BudgetBuilder(sheets_client)
        └─ current_result: Optional[AgentResult]
```

---

## ✅ Checklist de Integración

- [ ] `services/gmail_service.py` → Gmail API OAuth2
- [ ] `services/gemini_service.py` → Generación de textos
- [ ] `services/web_scraper.py` → Scraping germanrodriguez.ar
- [ ] `services/search_service.py` → APIs de búsqueda de leads
- [ ] Tests: `tests/test_*.py`
- [ ] Documentación: Swagger en `/docs`
- [ ] Deploy: Cloud Run, Lambda, Heroku, etc.

---

**¿Listo?** Ahora que entiendes la arquitectura, ¿cuál es el siguiente paso? 🚀
