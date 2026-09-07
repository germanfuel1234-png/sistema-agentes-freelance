# 🚀 Sistema Agentes Freelance - Guía de Setup Completa

## 🎯 Qué hace este sistema

Automatiza el ciclo completo de outreach freelance:

1. **Agent 0** → Estudia tu web (germanrodriguez.ar), extrae servicios y precios
2. **Agent 1** → Busca nuevos leads (agencias marketing o PyMEs)
3. **Agent 2** → Genera emails personalizados y los envía vía Gmail
4. **Agent 3** → Arma presupuestos con Gemini
5. **Agent 4** → Valida que todo esté funcionando (Supervisor)

---

## ✅ Prerequisitos

- Python 3.8+
- Pip (package manager)
- Cuenta Google (para Gmail + Sheets + Gemini)
- Google Cloud Project creado (`mailpaginaweb`)

---

## 📋 Paso 1: Descargar credentials.json

El sistema usa **OAuth2** para autenticarse en Gmail de forma segura.

### 1a. Google Cloud Console

1. Andá a https://console.cloud.google.com
2. Seleccioná el proyecto **`mailpaginaweb`**
3. En el menú lateral, andá a **Credenciales** (o "APIs & Services" → "Credentials")

### 1b. Descargar la clave

4. Buscá la aplicación cliente llamada **`Agente Mails Freelance`** (tipo "Installed application")
5. Hacé click en el ícono de **descargar** (↓) del lado derecho
6. Se descargará un archivo `client_secret_XXXXX.json`

### 1c. Guardar en el repo

7. Renombrá el archivo a **`credentials.json`**
8. Copialo a este directorio: `/home/german/Escritorio/marketin/sistema_agentes_freelance/credentials.json`

✅ **Listo!** En el primer run, te pedirá que confirmes en el navegador. Después guarda el token automáticamente.

---

## 🔑 Paso 2: Configurar variables de entorno (OPCIONAL)

Crea un archivo `.env` en la raíz del repo:

```bash
# .env
GEMINI_API_KEY=tu_gemini_key_aqui
GOOGLE_API_KEY=tu_custom_search_key
GOOGLE_ENGINE_ID=tu_search_engine_id
SHEETS_CREDENTIALS=path/a/sheets_credentials.json
```

**Notas:**
- **GEMINI_API_KEY**: Si no lo pones, usa templates (funciona igual para MVP)
- **GOOGLE_API_KEY + GOOGLE_ENGINE_ID**: Para búsqueda real de leads. Sin ellos, genera mocks.
- **SHEETS_CREDENTIALS**: Usa el mismo OAuth2 de Gmail por defecto (no necesitas especificar)

---

## 🧪 Paso 3: Test de Gmail

Verificar que Gmail API funciona correctamente:

```bash
cd /home/german/Escritorio/marketin/sistema_agentes_freelance

# Primera vez: te pedirá autorización en navegador
python test_gmail_real.py
```

**Qué pasa:**
1. Se abre una ventana del navegador (localhost:8080)
2. Confirmás que autorizas acceso a Gmail
3. Se guarda el token automáticamente en `token_gmail.json`
4. Envía 2 emails de prueba:
   - Email 1: `rodriguezg.dev@gmail.com` → él mismo
   - Email 2: `rodriguezg.dev@gmail.com` → `germanty123@gmail.com`

**Esperado:**
```
✅ Test EXITOSO
📧 Email 1 a rodriguezg.dev@gmail.com: OK (ID: abc123...)
📧 Email 2 a germanty123@gmail.com: OK (ID: def456...)

🎉 Gmail API está funcionando correctamente!
```

✅ Si ves este mensaje, **Gmail está listo!**

---

## 🏃 Paso 4: Ejecutar los agentes

### Opción A: Dashboard Web (interfaz visual)

```bash
python -m uvicorn web.app:app --reload --host 0.0.0.0 --port 8000
```

Abre http://localhost:8000 en el navegador.

**Dashboard incluye:**
- ✅ Ejecutar cada agente manualmente
- ✅ Ver preview de emails antes de enviar
- ✅ Aprobar/rechazar presupuestos
- ✅ Monitoreo de leads
- ✅ Historial de actividades

### Opción B: Script manual (sin interfaz)

```bash
python run_agents.py
```

Ejecuta la secuencia completa en terminal.

---

## 📊 Paso 5: Verificar Google Sheets

El sistema usa **Google Sheets** como base de datos:

1. Abre Google Drive
2. Busca una hoja llamada **"Sistema Agentes Freelance"** (se crea automáticamente)
3. Dentro hay 4 tabs:
   - `precios_base` → Servicios + precios de germanrodriguez.ar
   - `leads_tracking` → Leads encontrados, status de contacto, respuestas
   - `emails_sent` → Registro de mails enviados
   - `budgets` → Presupuestos generados

---

## 🛠️ Troubleshooting

### Error: "credentials.json no encontrado"
→ Descargá de Google Cloud Console (paso 1)

### Error: "No module named 'google.auth'"
```bash
pip install -r requirements.txt
```

### OAuth2 no autoriza
→ Asegurate que `rodriguezg.dev@gmail.com` esté en "OAuth consent screen" como usuario de test

### Gmail no envía (error 403)
→ En Google Cloud, verificá:
- ✅ Gmail API habilitada
- ✅ OAuth2 client creado
- ✅ Scopes incluyen `https://www.googleapis.com/auth/gmail.send`

### Emails van a spam
→ Es normal en desarrollo. Gmail mejora la reputación después de varios envíos.

---

## 📁 Estructura del código

```
sistema_agentes_freelance/
├── test_gmail_real.py          ← RUN ESTO PRIMERO
├── credentials.json            ← Descargá de Google Cloud (⚠️ .gitignore)
├── token_gmail.json            ← Se crea automáticamente (⚠️ .gitignore)
├── requirements.txt
│
├── config/
│   └── settings.py            ← Configuración centralizada
│
├── core/
│   ├── models.py              ← Dataclasses (Lead, Email, Budget, etc)
│   └── sheets_client.py       ← Cliente Google Sheets
│
├── services/                  ← NUEVOS - Lógica de APIs
│   ├── gmail_service.py       ← Envía emails vía Gmail API
│   ├── gemini_service.py      ← Genera emails/presupuestos con Gemini
│   ├── web_scraper.py         ← Extrae datos de germanrodriguez.ar
│   └── search_service.py      ← Busca leads (Google Custom Search)
│
├── agents/                    ← Los 5 agentes
│   ├── base_agent.py          ← Clase base (async execute + on_approved)
│   ├── agent_0_web_study.py   ← Estudia web
│   ├── agent_1_search_leads.py ← Busca leads
│   ├── agent_2_send_emails.py ← Envía mails (con aprobación)
│   ├── agent_3_budgets.py     ← Arma presupuestos (con aprobación)
│   └── agent_4_supervisor.py  ← Valida salud del sistema
│
├── web/                       ← Dashboard FastAPI
│   ├── app.py                 ← Inicializa FastAPI + servicios
│   └── routes.py              ← Endpoints
│
└── run_agents.py             ← Script para ejecutar flujo completo
```

---

## 🎓 Flujo típico de uso

### Día 1: Setup
```bash
# 1. Descargar credentials.json
# 2. Test de Gmail
python test_gmail_real.py

# 3. Inicializar dashboard
python -m uvicorn web.app:app --reload
```

### Días siguientes: Ejecución
```bash
# Opción A: Web
python -m uvicorn web.app:app

# Opción B: Manual
python run_agents.py
```

**Flujo automatizado:**
1. Agent 0 → Extrae precios de tu web
2. Agent 1 → Busca 10 nuevas PyMEs
3. Agent 4 → Valida que todo está OK
4. Agent 2 → Genera previews de emails
5. ➡️ **TÚ REVISAS Y APROBÁS** (o rechazás)
6. Agent 2 (on_approved) → Envía los 10 emails vía Gmail
7. Agent 1 → Actualiza Sheet con status "ENVIADO"

---

## 🚨 Seguridad & Mejores Prácticas

### ✅ LO QUE HACE BIEN ESTE CÓDIGO
- Usa OAuth2 (no almacena contraseña)
- Tokens se guardan localmente + auto-refresh
- API keys en .env (no en código)
- Mock data para testing sin APIs
- Approval gates = tú controlas antes de enviar

### ⚠️ ANTES DE PRODUCCIÓN
- [ ] Revisar `.gitignore` (credentials.json, token_gmail.json, .env)
- [ ] Auditar Google Sheets permisos
- [ ] Montar sobre HTTPS (FastAPI en producción)
- [ ] Rate limiting en endpoints
- [ ] Logging centralizado (Sentry/CloudLogging)
- [ ] Database real en lugar de Sheets (si >1000 leads)

---

## 📞 Soporte & Siguiente

Si algo no funciona:
1. Revisá error exacto en los logs
2. Verificá que `credentials.json` esté en el lugar correcto
3. Ejecutá `python test_gmail_real.py` para aislar el problema
4. Revisá permisos en Google Cloud Console

**Próximos pasos después del setup:**
- Agregar más tipos de búsqueda de leads
- Personalizar templates de email
- Implementar A/B testing de asuntos
- Agregar Follow-up automático (Agent 5)
- Integrar CRM (Pipedrive, HubSpot)

---

**¡Listo para despegar!** 🚀

Cualquier duda, revisá los comentarios en el código o los logs en terminal.
