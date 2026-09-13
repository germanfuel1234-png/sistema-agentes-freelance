# Arquitectura — Sistema de búsqueda de empresas (cazadores de leads)

Este documento explica el sistema que busca clientes potenciales de forma
automática y continua. Es un sistema aparte de los agentes originales
(`agents/agent_0` a `agent_4`) — se enfoca solo en **encontrar empresas
reales con contacto real**, sin depender de facturación de Google ni de
herramientas pagas.

## Principio rector: nunca inventar datos

Todo el sistema está construido alrededor de una sola regla, no negociable:
**si no se encuentra un dato real, se deja vacío — nunca se inventa.**
Esto aplica a nombres de empresa, emails, países, y también al mensaje de
contacto (se arma el texto, pero nunca se envía solo).

## Los dos motores, y por qué están separados

Hay **dos loops corriendo en paralelo**, cada uno con su propio motor de
búsqueda, a propósito, para que no compitan por el mismo cupo/rate-limit:

```
┌─────────────────────────────┐         ┌─────────────────────────────┐
│   loop_caza.py  (PRIORIDAD 1)│         │   loop_indeed.py (PRIORIDAD 2)│
│   cada 10 minutos            │         │   cada 3 horas                │
│                               │         │                                │
│   Motor: Brave → Bing →       │         │   Motor: Indeed EXCLUSIVO      │
│   DuckDuckGo → Yahoo          │         │   (nunca toca Bing/Brave)      │
│                               │         │                                │
│   Busca: "agencia de          │         │   Alterna cada ciclo:          │
│   marketing", "freelance",    │         │   - cazar_indeed.py            │
│   "community manager",        │         │     (desarrollador web)        │
│   "diseñador gráfico"         │         │   - caza_programador.py        │
│   en Argentina/LatAm/España   │         │     (automatización/RPA)       │
└──────────────┬────────────────┘         └──────────────┬─────────────────┘
               │                                          │
               ▼                                          ▼
      leads_tracking.csv                    leads_tracking.csv (desarrollador web)
      (pestaña principal)                   leads_automatizacion (RPA/bots)
```

**Por qué la separación importa:** `loop_caza.py` depende de Bing como
respaldo cada vez que Brave lo bloquea (pasa todo el tiempo). Si otro
proceso le pega fuerte a Bing al mismo tiempo (como hacía la búsqueda
automática de LinkedIn/X, con ~84 consultas por ciclo), le come el cupo
justo al que más importa. Por eso `loop_indeed.py` usa Indeed en
exclusiva — un motor que ninguno de los otros dos toca.

## Flujo de una búsqueda, paso a paso

Los dos loops siguen la misma lógica interna, solo cambia el motor:

```
1. BUSCAR
   ├─ loop_caza.py:   pide resultados a Brave; si falla (429), prueba
   │                  Bing; si falla, prueba DuckDuckGo; si falla, prueba
   │                  Yahoo como último recurso (funciona pero solo
   │                  responde ~40-60% de las veces, por eso va último).
   └─ loop_indeed.py: pide la página de resultados de Indeed
                       (ar/es/mx/co/cl/ve/pa.indeed.com), hasta 3 páginas.

2. EXTRAER EMPRESAS del HTML de resultados
   (regex sobre el texto visible, nunca sobre datos inventados)

3. FILTRAR RUIDO
   ├─ ¿Es una multinacional grande? (EXCLUDED_COMPANIES: Accenture,
   │  Deloitte, PwC, KPMG, BDO, Capgemini, Mercado Libre, Wood, etc.)
   │  -> se descarta, no es el target (PyME/agencia sin developer propio)
   ├─ ¿Es ruido de buscador? (Wikipedia, GitHub, Zhihu, Streamlabs,
   │  agencias de noticias/gobierno que matchean "agencia" por casualidad)
   │  -> se descarta
   └─ ¿Ya la vimos en esta misma corrida?
      -> se descarta (dedup local)

4. ENCONTRAR EL EMAIL
   ├─ loop_caza.py:   saca el email del snippet del buscador, o visita
   │                  la página real si el snippet no lo tiene.
   └─ loop_indeed.py: Indeed no da el sitio de la empresa directo -
                       ADIVINA el dominio propio (empresa.com.ar,
                       empresa.com, según el país real de la oferta) con
                       pedidos HTTP directos, sin usar ningún buscador.
                       Rechaza dominios parkeados/redirects a otro sitio.

5. GUARDAR
   ├─ Si hay email real         -> Lead completo a la Sheet
   ├─ Si hay sitio pero sin      -> a "seguimiento_manual" (nombre,
   │  email (solo loop_indeed)     sitio, form de contacto si existe,
   │                                mensaje ya redactado)
   └─ Si ya existe ese email     -> se descarta (dedup contra la Sheet real)
      en la Sheet
```

## El caso "sin email": seguimiento manual, nunca automático

Cuando `cazar_indeed.py` o `caza_programador.py` encuentran una empresa
real pero no logran sacarle un email (el sitio solo tiene un formulario
de contacto), **no se pierde el dato ni se completa el formulario solo**.
Se guarda en la pestaña `seguimiento_manual` con:

- El link directo al formulario de contacto (detectado, no completado)
- Un mensaje ya redactado (`mensaje_contacto.py`), adaptado según si la
  empresa buscaba desarrollador web o automatización/RPA

Completar y enviar el formulario queda para que el usuario lo haga a
mano, caso por caso — mandar el mismo mensaje en bloque a muchos
formularios es spam, y usar el botón de "postularme" de una oferta de
empleo para pitchear otra cosa es engañoso. El sistema deja todo listo
para copiar/pegar, pero el envío es una decisión humana.

## Mapa de archivos por responsabilidad

```
BÚSQUEDA (motor)
├─ services/bing_search.py         Bing HTML, sin API key
├─ services/duckduckgo_search.py   DuckDuckGo HTML, sin API key
├─ services/yahoo_search.py        Yahoo HTML, sin API key (respaldo final,
│                                   flaky: ~40-60% responde, el resto 500)
└─ cazar_brave.py                  Brave HTML + orquesta el fallback
                                    Brave -> Bing -> DuckDuckGo -> Yahoo

CAZADORES (qué se busca)
├─ cazar_brave.py       Agencias/freelancers/community managers/
│                       diseñadores (Argentina/LatAm/España)
├─ cazar_indeed.py      Empresas que buscan "desarrollador web"
│                       (ofertas de empleo reales en Indeed)
└─ caza_programador.py  Empresas que buscan "automatización/bot/RPA"
                        (mismo motor que cazar_indeed.py, reutiliza
                        buscar_ofertas/encontrar_sitio_y_email)

LOOPS (cuándo se busca)
├─ loop_caza.py     cada 10 min -> cazar_brave.py
└─ loop_indeed.py   cada 3 hs, alterna -> cazar_indeed.py / caza_programador.py

FILTROS COMPARTIDOS
├─ core/constants.py    EXCLUDED_COMPANIES (multinacionales)
├─ cazar_indeed.py      es_empresa_excluida() (usa la lista de arriba,
│                       + exactas cortas: wood, sanofi, bbva, etc.)
└─ cazar_brave.py       _es_relevante() + _EXCLUDED_DOMAINS (ruido)

SEGUIMIENTO MANUAL
└─ mensaje_contacto.py  Arma el mensaje + detecta formulario de contacto
                        (nunca completa ni envía nada)

BÚSQUEDA MANUAL (aparte, no está en ningún loop)
└─ busqueda_linkedin/   Posteos orgánicos de LinkedIn/X pidiendo
                        freelancers. La búsqueda automática rinde casi
                        nada (LinkedIn no deja indexar sin login) y le
                        pega fuerte a Bing, por eso no corre sola - se
                        usa con consultas_linkedin.txt a mano.
```

## La Google Sheet como memoria compartida

Todos los cazadores escriben a la misma planilla, cada uno en su pestaña:

| Pestaña | Quién escribe | Contenido |
|---|---|---|
| `leads_tracking.csv` | `loop_caza.py`, `loop_indeed.py` (mitad desarrollador web) | Leads con email real, listos para mandar el mail de outreach |
| `leads_automatizacion` | `loop_indeed.py` (mitad automatización) | Idem, pero para el ángulo de automatización/RPA |
| `seguimiento_manual` | `cazar_indeed.py`, `caza_programador.py` | Empresas reales sin email — revisión manual |
| `oportunidades_freelance` | `busqueda_linkedin/` (manual) | Posteos orgánicos de gente pidiendo freelancers |

`leads_tracking.csv` es la que alimenta el resto del sistema original
(`agent_2_send_emails.py` lee de ahí para mandar el mail de outreach).

## Límites conocidos (no son bugs, son la realidad de cada plataforma)

- **Brave/Bing/DuckDuckGo**: bloquean con 429 (rate limit) si se insiste
  mucho en poco tiempo. Se recupera solo en unas horas. Por eso la cadena
  de 3 motores: si uno está bloqueado, los otros suelen seguir sirviendo.
- **Indeed**: mismo tipo de bloqueo (403), por país/dominio.
- **Google, Startpage, Mojeek, Yandex, ZipRecruiter, Qwant, SearXNG
  (instancias públicas), Boardreader**: tienen CAPTCHA o anti-bot activo
  (Cloudflare, reCAPTCHA, Anubis, DataDome), o directamente no traen datos
  en el HTML crudo (Qwant y Boardreader son apps JS - React/Angular - sin
  resultados server-side, igual que pasaba con Google Jobs). Probados en
  vivo y descartados por eso. Sortear un CAPTCHA no es algo que este
  sistema haga, bajo ninguna circunstancia.
- **Yahoo**: no tiene CAPTCHA ni bloqueo duro, pero es inconsistente - en
  pruebas seguidas solo respondió ~40-60% de las veces (el resto, error
  500 de su propio backend). Por eso está como cuarto motor, después de
  DuckDuckGo, nunca como principal.
- **LinkedIn**: los posteos y perfiles no están indexados por ningún
  buscador público sin sesión iniciada — por eso la búsqueda de LinkedIn
  es manual, no automática.
