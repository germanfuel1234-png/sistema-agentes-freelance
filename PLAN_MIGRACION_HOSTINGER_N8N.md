# Plan: migrar todo a un servidor Hostinger + n8n

Documento de visión para arrancar la próxima etapa del proyecto. Describe
a dónde quiere llegar Germán y qué de lo que ya existe hoy en este repo
sirve como base, para no repetir trabajo ni perder contexto entre charlas.

## Objetivo general

Mover todo el sistema (caza de empresas, envío de mails, generación de
presupuestos) a un servidor de **Hostinger**, orquestado con **n8n**
(herramienta de automatización de flujos con nodos - similar a Zapier
pero self-hosteable). La idea es que deje de depender de tener una
notebook prendida corriendo `loop_caza.py`/`loop_indeed.py` a mano, y
que todo el flujo (buscar → contactar → armar presupuesto → notificar)
viva en el servidor de forma continua.

## Flujo completo que se quiere lograr

```
1. BUSCAR EMPRESAS (ya existe, corre en loop)
   └─ cazar_brave.py / cazar_indeed.py / caza_programador.py

2. MANDAR MAIL (ya existe el agente, falta activarlo en el server)
   └─ agent_2_send_emails.py

3. EL CLIENTE RESPONDE POR WHATSAPP (nuevo)
   └─ Notificación a Germán de que hay una respuesta
   └─ n8n escucha el mensaje entrante (WhatsApp Business API / Twilio,
      a definir) y dispara el resto del flujo

4. GENERAR PRESUPUESTO (ya existe el generador, falta el panel + envío)
   └─ Panel/dashboard donde Germán carga los datos del cliente que
      hacen falta (nombre, URL del sitio, tipo de proyecto, etc.)
   └─ El script corre Lighthouse sobre la URL del cliente (si aplica)
   └─ Arma el HTML del presupuesto automáticamente
   └─ Lo comparte por WhatsApp al cliente (nuevo - hoy no envía nada,
      solo genera el archivo)
```

## Lo que YA EXISTE hoy en este repo (no arrancar de cero)

### Búsqueda de empresas - funcionando en loop, local
- [`loop_caza.py`](loop_caza.py) - cada 10 min, agencias de marketing con
  email real vía Brave/Bing/DuckDuckGo/Yahoo. Lee queries de
  [`queries_loop_caza.txt`](queries_loop_caza.txt) (42 queries, 14 países).
- [`loop_indeed.py`](loop_indeed.py) - cada 3 hs, alterna
  `cazar_indeed.py` (desarrollador web) / `caza_programador.py`
  (automatización/RPA) vía Indeed.
- Ver [`ARQUITECTURA_BUSQUEDA_EMPRESAS.md`](ARQUITECTURA_BUSQUEDA_EMPRESAS.md)
  para el detalle completo de esta parte.
- **Para migrar**: esto ya corre como script standalone con `venv312`,
  no depende de nada más que Python + `requests`/`bs4` + credenciales
  de Google Sheets (`credentials.json`/`token.json`). Portable a un
  server sin mucho cambio - el punto a resolver es cómo mantenerlo vivo
  ahí (systemd service, PM2, cron, o que n8n lo dispare por webhook/CLI).

### Envío de mails - agente ya armado, no sé si activo en producción
- [`agents/agent_2_send_emails.py`](agents/agent_2_send_emails.py) -
  clase `Agent2SendEmails`, parte del framework de agentes original
  (`agents/agent_0` a `agent_4`).
- **Para migrar**: revisar si esto está probado con envíos reales o
  quedó a mitad de camino. Definir si el envío lo sigue haciendo este
  script en Python o si conviene que n8n mande el mail directamente
  (n8n tiene nodo nativo de Gmail/SMTP) y este script solo arma el
  contenido.

### Generador de presupuesto con diagnóstico Lighthouse - YA FUNCIONA
- [`agentes/agente_presupuesto_seo.py`](../agentes/agente_presupuesto_seo.py)
  (ojo: está en `marketin/agentes/`, no dentro de
  `sistema_agentes_freelance/`). Esto es prácticamente lo que pediste:
  - Corre una auditoría **real de Lighthouse** sobre la URL del cliente.
  - Mapea los problemas encontrados a texto en español
    (`agentes/lighthouse_mapeo.json`).
  - Calcula el presupuesto según cantidad/severidad de problemas
    (`agentes/precios_seo.json`).
  - Genera un HTML de propuesta (`agentes/plantilla_presupuesto.html`
    como base) en `presupuestos_generados/`.
  - **Ya tiene el diseño definitivo** (confirmado 15/09): se portó el
    hero animado 3D (tubos interactivos vía Three.js) y el footer con
    íconos sociales del ejemplo de referencia (`presupuesto-alkanos-2.html`)
    a la plantilla. También ya muestra las **métricas iniciales de
    Lighthouse** (SEO/Performance/Accesibilidad/Buenas prácticas, con
    color según severidad) en una sección propia justo debajo del hero,
    antes de la lista de problemas - así el cliente ve su situación
    actual antes del diagnóstico y el precio.
  - **No manda nada por mail ni WhatsApp** - hoy es 100% manual: vos
    revisás el HTML generado y lo adjuntás a mano.
  - Se corre por CLI: `python3 agentes/agente_presupuesto_seo.py
    --cliente "Nombre" --url "https://sitio.com"`.
- **Para migrar**: la lógica de negocio y el diseño ya están resueltos.
  Lo que falta es (a) el panel para cargar los datos en vez de pasarlos
  por CLI, y (b) el envío automático por WhatsApp - ver siguiente punto.

### Entrega por WhatsApp: HTML + PDF (pedido nuevo, 15/09)
- Cuando todo esté montado en n8n, cada presupuesto generado se tiene
  que mandar al cliente por WhatsApp en **dos formatos a la vez**: el
  archivo `.html` (el que ya genera el script) y un **`.pdf`** del
  mismo contenido.
- **El PDF todavía no existe, hay que generarlo.** El HTML actual tiene
  el hero animado con Three.js (JS que corre en el navegador), así que
  un PDF "de verdad" (no una captura rota) necesita renderizar la
  página con un navegador headless y exportarla - ej. Playwright/
  Puppeteer con `page.pdf()` después de esperar a que cargue el canvas,
  o generar una plantilla paralela sin la animación 3D pensada
  específicamente para impresión/PDF (más liviana, sin dependencias de
  Three.js/CDN). A decidir cuál conviene.
- Este paso de "página → PDF" es un buen candidato para que lo resuelva
  Python (con Playwright) y n8n solo dispare el envío por WhatsApp de
  los dos archivos ya generados - no meter la generación de PDF adentro
  de n8n.
- También existe [`agents/agent_3_budgets.py`](agents/agent_3_budgets.py)
  (otro generador de presupuestos, más viejo, usa Gemini en vez de
  Lighthouse) - **decidir cuál de los dos es el que se sigue usando**,
  no tiene sentido mantener los dos.

### Dashboard web - ya existe un esqueleto
- [`web/app.py`](web/app.py) + [`web/routes.py`](web/routes.py) - un
  dashboard (parece FastAPI) con una ruta que ya dispara el Agent 3
  ("armar presupuesto"). Hoy es un esqueleto básico.
- **Para migrar**: esto es la base natural para el "panel donde le
  ponemos los datos del cliente" que pediste - hay que ampliarlo con un
  formulario (nombre del cliente, URL, tipo de proyecto, lo que haga
  falta) que dispare `agente_presupuesto_seo.py` con esos datos, en vez
  de la línea de comandos.

## Lo que FALTA construir (nuevo, no existe nada todavía)

1. **Integración de WhatsApp** (no hay nada de esto en el repo todavía):
   - Notificar a Germán cuando un cliente responde por WhatsApp.
   - Mandar el HTML del presupuesto al cliente por WhatsApp
     automáticamente.
   - Hay que decidir el proveedor: WhatsApp Business API oficial (Meta,
     requiere aprobación de negocio), o un intermediario tipo Twilio,
     o el nodo nativo de WhatsApp de n8n (usa Twilio/oficial por
     detrás). A definir en la próxima charla.

2. **Ampliar el dashboard** para que sea el panel real de carga de
   datos del cliente (hoy es solo un botón que dispara el agente).

3. **Orquestación con n8n**: decidir qué vive en n8n (los flujos/
   triggers, ej. "llegó un WhatsApp nuevo → avisame → esperar que yo
   cargue los datos → correr el script → mandar el resultado") y qué
   sigue viviendo en Python (la lógica pesada: scraping, Lighthouse,
   cálculo de precio, generación del HTML). n8n orquesta, Python hace
   el trabajo pesado - no reescribir toda la lógica en nodos de n8n.

4. **Despliegue en Hostinger**: qué tipo de plan/servidor (VPS con
   acceso SSH y Node.js instalado, porque Lighthouse lo necesita -
   ver `node_modules/.bin/lighthouse` en
   `agentes/agente_presupuesto_seo.py`), cómo se instala n8n ahí
   (Docker es lo más común), y cómo quedan corriendo los loops de caza
   de forma persistente (no como proceso de terminal como ahora).

## Preguntas para resolver en la próxima charla

- ¿Qué proveedor de WhatsApp vamos a usar (oficial Meta, Twilio, u otro)?
- ¿`agent_3_budgets.py` (Gemini) se descarta a favor de
  `agente_presupuesto_seo.py` (Lighthouse), o se combinan?
- ¿El envío de mails lo sigue haciendo `agent_2_send_emails.py` en
  Python, o pasa a manejarlo n8n directamente?
- ¿Qué plan de Hostinger (necesita ser VPS, no hosting compartido,
  para poder correr Python + Node.js + n8n con acceso SSH)?
- ¿Los loops de búsqueda (`loop_caza.py`/`loop_indeed.py`) siguen
  corriendo standalone en el server (systemd/PM2), o pasan a ser
  disparados por n8n en vez de tener su propio loop infinito?
