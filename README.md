# 🚀 Sistema Agentes Freelance - Automatización Completa

**Automatiza el ciclo completo de outreach + presupuestos + mails para tu agencia freelance.**

Construido con Python, Google APIs (Gmail, Sheets, Gemini) y FastAPI.

---

## 🎯 Qué hace

```
FLUJO AUTOMATIZADO
==================

[ Agent 0: Web Study ]
     ↓
  Extrae servicios + precios de germanrodriguez.ar
  Guarda en Google Sheets (tabla: precios_base)

     ↓

[ Agent 1: Search Leads ]
     ↓
  Busca PyMEs o agencias en Argentina vía Google Custom Search
  Valida emails, evita duplicados
  Guarda en Sheet (tabla: leads_tracking)

     ↓

[ Agent 4: Supervisor ]
     ↓
  Verifica salud del sistema:
  ✅ Google Sheets conexión
  ✅ Gmail autenticación
  ✅ Integridad de datos

     ↓

[ Agent 2: Send Emails ] ⏸️ REQUIERE APROBACIÓN
     ↓
  Genera emails personalizados con Gemini
  Muestra previews para revisión
  Envía vía Gmail API después de tu "OK"

     ↓

[ Agent 3: Budget Builder ] ⏸️ REQUIERE APROBACIÓN
     ↓
  Calcula presupuestos: base + ajustes por complejidad
  Genera propuestas HTML personalizadas
  Espera tu aprobación del monto final
```

**Resultado:** Todo automatizado, pero TÚ controlas antes de enviar.

---

## ⚡ Setup Rápido (5 minutos)

### 1️⃣ Descarga credentials.json

```bash
# Google Cloud Console → mailpaginaweb → Credenciales
# Descargar "Agente Mails Freelance" → guardar como credentials.json

# En el directorio del proyecto:
ls -la credentials.json
```

### 2️⃣ Instala dependencias

```bash
pip install -r requirements.txt
```

### 3️⃣ Test de Gmail

```bash
# Primer run: te pedirá confirmar en navegador
python test_gmail_real.py

# Esperado:
# ✅ Email 1 enviado a rodriguezg.dev@gmail.com
# ✅ Email 2 enviado a germanty123@gmail.com
```

### 4️⃣ Ejecuta los agentes

**Opción A: Dashboard web (visual)**
```bash
python -m uvicorn web.app:app --reload
# Abre http://localhost:8000
```

**Opción B: Script manual (terminal)**
```bash
python run_agents.py
```

---

## 📊 Estructura

```
sistema_agentes_freelance/
│
├── 🧪 test_gmail_real.py          ← Verifica Gmail funciona
├── 🤖 run_agents.py               ← Ejecuta todos los agentes
├── 📚 SETUP.md                    ← Guía detallada de configuración
│
├── services/                      ← Integraciones con APIs
│   ├── gmail_service.py           (envía mails vía OAuth2)
│   ├── gemini_service.py          (genera contenido con IA)
│   ├── web_scraper.py             (extrae precios de tu web)
│   └── search_service.py          (busca leads)
│
├── agents/                        ← Los 5 agentes
│   ├── agent_0_web_study.py       (estudia tu web)
│   ├── agent_1_search_leads.py    (busca clientes)
│   ├── agent_2_send_emails.py     (genera + envía mails)
│   ├── agent_3_budgets.py         (arma presupuestos)
│   └── agent_4_supervisor.py      (valida sistema)
│
├── core/                          ← Modelos + Sheets
│   ├── models.py                  (dataclasses: Lead, Email, Budget)
│   └── sheets_client.py           (lee/escribe Google Sheets)
│
├── web/                           ← Dashboard FastAPI
│   ├── app.py                     (inicializa servicios)
│   └── routes.py                  (endpoints API)
│
└── config/
    └── settings.py                (configuración centralizada)
```

---

## 🔧 Características

### ✅ Email Automation
- ✉️ Genera emails personalizados con Gemini
- 🔐 Envía vía Gmail OAuth2 (seguro, sin almacenar contraseña)
- ⏸️ Aprobación manual antes de enviar
- 📊 Registra en Google Sheets

### ✅ Lead Generation
- 🔍 Busca PyMEs por industria/ciudad
- 🏢 Busca agencias de marketing
- 📧 Valida emails, evita duplicados
- 🛡️ Filtro de empresas excluidas

### ✅ Budget Generation
- 💰 Calcula precios base por tipo de proyecto
- ⚙️ Ajustes automáticos por complejidad (CRM, pagos, APIs)
- 📄 Genera propuestas HTML profesionales
- ⏸️ Aprobación del monto antes de guardar

### ✅ System Health
- 🏥 Supervisor valida todas las conexiones
- 📊 Reportes de leads/status
- 🔍 Detecta duplicados y datos inválidos

### ✅ Safe Automation
- 🛑 Approval gates en emails y presupuestos
- 🔐 OAuth2 (no almacena credenciales)
- 📝 Logging detallado de cada acción
- 🔄 Fallbacks graceful (API no disponible → usa templates)

---

## 🚀 Ejemplo de Uso

```python
# 1. Import servicios
from services.gmail_service import GmailService
from agents.agent_2_send_emails import Agent2SendEmails

# 2. Inicializa
gmail = GmailService("credentials.json", "token_gmail.json")
agent = Agent2SendEmails(sheets_client, gmail, gemini_service)

# 3. Genera draft (sin aprobar)
emails, requires_approval = await agent.execute(limit=5)

# 4. Revisa
for email in emails:
    print(f"Para: {email.to}")
    print(f"Asunto: {email.subject}")

# 5. Si está bien, aprueba
await agent.on_approved(emails)  # ✅ Envía!
```

---

## 🔐 Seguridad

| Aspecto | Cómo se maneja |
|---------|-----------------|
| **Contraseñas Gmail** | No se almacenan. Usa OAuth2 con token refresh automático |
| **API Keys** | En `.env` (ignorado en Git via .gitignore) |
| **Credenciales** | `credentials.json` en .gitignore |
| **Tokens** | `token_gmail.json` en .gitignore, se auto-refresh |
| **Approval gates** | Cada envío masivo requiere tu confirmación manual |

---

## 📋 Requirements

```
Python >= 3.8
Google Cloud Project (mailpaginaweb) - preconfigurado
Cuenta Gmail + Google Sheets acceso
Opcional: Gemini API key (fallback a templates si no)
```

---

## 🐛 Troubleshooting

**Error: "credentials.json no encontrado"**
→ Ver paso 1 del SETUP.md

**Error: Gmail no envía**
→ Revisar permisos en Google Cloud Console + scopes

**Agent 1 no encuentra leads**
→ Normal sin GOOGLE_API_KEY. Usa mocks para testing

**Presupuestos muy altos/bajos**
→ Ajusta lógica en `agent_3_budgets.py` (_calculate_base_price)

---

## 📞 Próximos Pasos

- [ ] Agregar Agent 5: Follow-up automático
- [ ] Integrar Pipedrive o HubSpot
- [ ] Dashboard más visual (React frontend)
- [ ] A/B testing de asuntos de email
- [ ] Webhook para Google Forms (captureadas de prospects)
- [ ] Reportes PDF de presupuestos

---

## 📄 Licencia

MIT - Úsalo como necesites.

---

**¿Listo para despegar?** 🚀

Lee [SETUP.md](SETUP.md) para instrucciones detalladas.

O ejecuta: `python test_gmail_real.py`
   # Edita .env con tus credenciales
   ```

3. **Credenciales Google:**
   - Descarga `credentials.json` de Google Cloud Console
   - Coloca en la raíz del proyecto

4. **Inicia el servidor:**
   ```bash
   python main.py
   ```
   - Abre: http://localhost:8000

### Agentes

| Agente | Función | Aprobación |
|--------|---------|-----------|
| **0** | Estudio de web y precios | No |
| **1** | Búsqueda de leads | No |
| **2** | Redacción de mails | ✅ Sí |
| **3** | Presupuestos | ✅ Sí |

### Flujo

1. **Agent 0** → Estudia tu web → Actualiza tabla `precios_base`
2. **Agent 1** → Busca leads → Agrega filas a `leads_tracking` (Pendiente)
3. **Agent 2** → Prepara mails → Espera tu aprobación → Envía
4. **Agent 3** → Arma presupuesto → Espera aprobación de monto → Guarda en Sheet

### Próximos pasos

- [ ] Integración Gmail API (envío real)
- [ ] Integración Gemini (generación de mails/presupuestos)
- [ ] Web scraping de germanrodriguez.ar
- [ ] Búsqueda de leads vía APIs (Google, LinkedIn)
- [ ] Tests unitarios
- [ ] Deploy (AWS Lambda, Cloud Run)
