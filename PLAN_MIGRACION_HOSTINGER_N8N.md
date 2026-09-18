# Plan: arquitectura completa con n8n (primero local, después hosting)

Documento de visión para arrancar la próxima etapa del proyecto. Describe
a dónde quiere llegar Germán y qué de lo que ya existe hoy en este repo
sirve como base, para no repetir trabajo ni perder contexto entre charlas.

## Objetivo general

Armar todo el sistema (caza de empresas, envío de mails, generación de
presupuestos, WhatsApp) orquestado con **n8n** (herramienta de
automatización de flujos con nodos - similar a Zapier pero
self-hosteable). La idea final es que el flujo completo (buscar →
contactar → armar presupuesto → notificar) viva de forma continua sin
depender de tener una terminal abierta a mano.

**Estrategia decidida (15/09): primero local, después hosting.**
En vez de saltar directo a levantar un VPS pago, armamos y probamos
toda la arquitectura (n8n + WhatsApp + generador de presupuestos)
corriendo en la PC de Germán. Recién cuando esté funcionando de punta a
punta se evalúa mover eso a un servidor (Hostinger VPS, PC propia con
Cloudflare Tunnel, o un free tier como Oracle Cloud - comparación al
final de este documento). Ventaja: no se gasta un peso hasta confirmar
que el flujo entero sirve tal cual se lo pensó.

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

## Qué hay instalado hoy en la PC (verificado 15/09) y qué falta

| Herramienta | ¿Para qué hace falta? | Estado |
|---|---|---|
| Python 3.12 (`venv312`) | Loops de caza, agentes | ✅ Instalado y en uso |
| Node.js v24 / npm | Lighthouse, y va a hacer falta para n8n/Playwright | ✅ Instalado |
| Google Chrome | Lighthouse lo usa como navegador headless | ✅ Instalado (v151) |
| Lighthouse (npm, en `marketin/node_modules`) | Auditoría del generador de presupuestos | ✅ Instalado y probado en vivo |
| **Docker** | Forma estándar de correr n8n self-hosted | ❌ No instalado (necesita `sudo`, ver `n8n/README.md`) |
| **n8n** (config Docker Compose) | El orquestador central de todo el flujo | ✅ `docker-compose.yml` + `.env` listos en [`n8n/`](n8n/) - falta instalar Docker para poder levantarlo |
| **cloudflared** (Cloudflare Tunnel) | Exponer la PC a internet para que WhatsApp le pegue al webhook de n8n, sin abrir puertos del router | ❌ No instalado |
| **Playwright** (para el PDF) | Exportar el HTML del presupuesto a PDF con el hero 3D renderizado | ❌ No instalado (hay una instalación de otro proyecto que no cuenta) |
| Proveedor de WhatsApp | Recibir/mandar mensajes | ❌ Ni siquiera decidido cuál usar (ver preguntas abiertas) |

**Orden sugerido para armar esto localmente:**
1. ~~Armar el `docker-compose.yml` de n8n~~ ✅ hecho (18/09) - ver [`n8n/README.md`](n8n/README.md).
2. ~~Instalar Docker~~ ✅ hecho (18/09).
3. ~~Decidir cómo n8n corre los scripts de Python~~ ✅ decidido (18/09) - ver
   sección "n8n ↔ Python" más abajo: **contenedor `runner` separado**, sin
   SSH y sin tocar la imagen oficial de n8n.
4. ~~Instalar `cloudflared` y armar el túnel hacia el n8n local~~ **descartado (18/09)** -
   se decidió no exponer la PC local a internet con un túnel. En vez de
   eso, cuando haga falta una URL pública real (para el webhook de
   WhatsApp), se migra directo a **Oracle Cloud Free Tier** (ver
   comparación de hosting más abajo) en vez de tunelear la PC de casa.
   Hasta entonces, todo lo que se prueba localmente (como el nodo HTTP
   Request contra el `runner`) no necesita ninguna URL pública - es
   tráfico interno entre contenedores, nunca sale a internet.
5. Definir y conectar el proveedor de WhatsApp (ver pregunta abierta) contra esa URL.
6. Ampliar el dashboard (`web/`) para cargar datos del cliente y disparar `agente_presupuesto_seo.py` (vía el `runner`, ver abajo).
7. Sumar el endpoint de PDF en el `runner` (Playwright ya está instalado ahí).
8. Conectar todo el flujo en n8n: WhatsApp → aviso a Germán → carga de datos → genera presupuesto (HTML+PDF) → responde por WhatsApp.

### n8n ↔ Python: contenedor `runner` separado (decidido 18/09)

La imagen oficial de n8n es **"hardened"** (Docker Hardened Images) - a
propósito no tiene Python, Chrome, ni siquiera un gestor de paquetes
(`apk`/`apt`) adentro. Eso descarta instalarle cosas directo. Se evaluaron
3 opciones y German eligió la de **mayor seguridad, sin importar el
trabajo que generara**:

- ❌ SSH (n8n → PC por SSH): descartado - aunque quede solo en loopback
  y nunca se exponga a internet, sigue siendo un servicio de red más
  (`sshd`) corriendo permanentemente, con sus propias claves para
  gestionar.
- ❌ Instalar Python/Chrome directo en la imagen de n8n: **no es
  posible** - la imagen hardened no tiene gestor de paquetes.
- ✅ **Contenedor `runner` aparte** ([`n8n/runner/`](n8n/runner/)): un
  segundo contenedor, con su propia imagen (`node:20-bookworm-slim` +
  Python + Chromium + Playwright), que expone una API HTTP mínima
  (FastAPI) con endpoints como `POST /presupuesto`. La imagen de n8n
  queda intacta - cero paquetes nuevos, cero superficie de ataque
  agregada ahí. El `runner` **no publica ningún puerto** a la LAN ni a
  internet, solo es alcanzable *dentro* de la red interna de Docker
  Compose - n8n le pega por `http://runner:8000` con el nodo nativo
  **HTTP Request** (nunca `Execute Command`, que permite correr
  comandos arbitrarios).
- El `runner` monta la raíz del proyecto (`marketin/`) completa como
  volumen de solo trabajo en `/data` - ve `agentes/`,
  `presupuestos_generados/`, `sistema_agentes_freelance/`, etc. tal
  cual están en el host.
- Ya reutiliza el `lighthouse` que está instalado en `marketin/node_modules`
  (no hace falta reinstalarlo adentro de la imagen - llega solo, montado
  vía el volumen); Chromium y Playwright sí se instalan dentro de la
  imagen del `runner` porque un navegador real no es portable por un
  simple mount de archivos.

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

1. **Integración de WhatsApp** - ✅ **envío probado de punta a punta (18/09)**,
   falta la parte de recibir (necesita URL pública, ver Oracle Cloud).
   - **Proveedor decidido**: WhatsApp Business Platform oficial de Meta
     (Cloud API), vía el nodo nativo "WhatsApp Business Cloud" de n8n -
     no Twilio, no librerías no oficiales. Gratis hasta 1.000
     conversaciones de servicio por mes, sin riesgo de baneo.
   - Se creó la app en developers.facebook.com ("automotazidormensajes"),
     se generó el número de prueba gratis, se guardó la credencial en
     n8n (Credentials → WhatsApp account, con el Access Token y el
     Business Account ID).
   - **Se mandó un mensaje real de prueba desde n8n y llegó al WhatsApp
     real** (confirmado visualmente) - el nodo "Send template" con la
     plantilla `hello_world` (la única que existe de verdad en la
     cuenta - ojo, ver nota abajo) y sin parámetros.
   - **Nota importante para la próxima vez que se toque esto**: el
     desplegable de plantillas en n8n/Meta muestra opciones de ejemplo
     de un negocio ficticio ("jaspers_market_order_confirmation_v1" y
     similares) que **no existen de verdad** en la cuenta - probarlas
     tira error de Meta ("número de parámetros no coincide"). Para ver
     qué plantillas son reales, ir a **business.facebook.com → Administrador
     de WhatsApp → Plantillas de mensajes → Administrar plantillas**.
     Hoy solo existe `hello_world` (aparece como "hola_mundo" en el
     desplegable de n8n, mismo template, nombre traducido) - fijo, sin
     variables. Para mandar el presupuesto real con nombre de cliente,
     hace falta **crear una plantilla nueva propia** ahí mismo (botón
     "Crear plantilla"), con variables `{{1}}`, `{{2}}`, etc., y
     esperar la aprobación de Meta (minutos a horas) antes de poder
     usarla desde n8n.
   - **Cuidado con el número argentino en el campo "recipientPhoneNumber"
     de n8n**: hay que mandarlo **sin el "9"** después del código de país
     (`541136239969`, no `5491136239969`) - si no, tira "número no está
     en la lista permitida" aunque el número sí esté verificado en Meta.
   - **Nunca pegar el Access Token en el chat con Claude** - pasó una vez
     sin querer en esta sesión, se regeneró el token de inmediato. Va
     directo en el campo de credenciales de n8n, nunca en otro lado.

2. **Ampliar el dashboard** para que sea el panel real de carga de
   datos del cliente (hoy es solo un botón que dispara el agente).

3. **Orquestación con n8n**: decidir qué vive en n8n (los flujos/
   triggers, ej. "llegó un WhatsApp nuevo → avisame → esperar que yo
   cargue los datos → correr el script → mandar el resultado") y qué
   sigue viviendo en Python (la lógica pesada: scraping, Lighthouse,
   cálculo de precio, generación del HTML). n8n orquesta, Python hace
   el trabajo pesado - no reescribir toda la lógica en nodos de n8n.

4. **Despliegue en un servidor** - **pospuesto a propósito.** Primero se
   valida todo local (ver checklist más arriba). Recién cuando el flujo
   completo funcione en la PC se decide dónde queda en producción - ver
   la comparación de opciones al final de este documento.

## Preguntas para resolver en la próxima charla

- ¿El envío de mails lo sigue haciendo `agent_2_send_emails.py` en
  Python, o pasa a manejarlo n8n directamente?
- ¿Los loops de búsqueda (`loop_caza.py`/`loop_indeed.py`) siguen
  corriendo standalone (systemd/PM2/Docker), o pasan a ser disparados
  por n8n en vez de tener su propio loop infinito?
- Falta crear la plantilla de WhatsApp real (con nombre del cliente y
  link al presupuesto) en el Administrador de WhatsApp de Meta, y
  esperar su aprobación - ver nota en la sección de WhatsApp arriba.
- Ya resuelto (15/09): `agente_presupuesto_seo.py` (Lighthouse) es el
  generador definitivo - se descarta `agent_3_budgets.py` (Gemini),
  no tiene sentido mantener los dos.
- Ya resuelto (18/09): proveedor de WhatsApp = Meta Cloud API oficial,
  probado y funcionando en vivo.

## Opciones de hosting (para cuando se decida migrar de la PC)

Comparación armada el 15/09, para cuando llegue el momento de decidir
dónde queda esto en producción. Lo importante primero: **tiene que ser
algo con acceso root/SSH** (VPS o equivalente) - el hosting compartido
tradicional no sirve, no permite procesos en background, Docker, ni
instalar Node/Chrome.

| Opción | Costo | A favor | En contra |
|---|---|---|---|
| **Hostinger VPS (KVM 2)** | ~$9/mes | 2 vCPU / 8GB RAM / 100GB, siempre encendido, IP fija, sin depender de la PC/internet de casa | Tiene costo mensual |
| **PC propia + Cloudflare Tunnel** | Gratis (+ luz) | Cero costo de hosting, control total | Se cae si se corta la luz/internet/se reinicia la PC; depende de la conexión de casa |
| **Oracle Cloud "Always Free"** | Gratis para siempre | Generoso de verdad (hasta 4 OCPU / 24GB RAM en ARM) - alcanza cómodo para todo esto | Aprobación de cuenta puede ser difícil/lenta; hay que verificar que las imágenes Docker que se usen soporten ARM64 |
| AWS/GCP free tier | Gratis 12 meses, después cobra (o nivel gratis permanente muy chico, ~1GB RAM) | Conocido, mucha documentación | El nivel realmente gratis para siempre no alcanza para n8n + Docker + Chrome juntos |
| Railway/Render/Fly.io free tier | Gratis con límites | Fácil de deployar | Pensados para apps web livianas, no para procesos 24/7 con Chrome adentro (duermen la app o limitan horas de cómputo) |

**Lo que realmente pesa en cualquiera de estas opciones**: los loops de
caza y n8n en reposo son livianos. Lo pesado son los picos cuando corre
Lighthouse (genera un presupuesto) o Playwright (genera el PDF) - cada
uno levanta un Chrome headless completo por 20-40 segundos. Si se suma
WhatsApp con una librería no oficial (no la API de Meta/Twilio), eso
agrega OTRO navegador headless corriendo permanentemente - mucho más
pesado que si se usa la API oficial (que es solo llamadas HTTP).
