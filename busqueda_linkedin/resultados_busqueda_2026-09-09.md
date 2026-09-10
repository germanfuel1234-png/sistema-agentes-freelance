# Bitácora de búsqueda — 09/09/2026 (ventana: 02/09 → 09/09/2026)

## REGLA ESTRICTA vigente
Prohibido Freelancer/Upwork/Workana/Fiverr/Computrabajo/etc. Solo posteos
orgánicos de LinkedIn/X. Resultado anterior con portales fue purgado.

## 1) Acción de limpieza en Google Sheet
- **6 filas eliminadas** de `oportunidades_freelance`: todas provenían de
  `freelancer.com` (portal de empleo prohibido por la regla estricta).
- **1 fila conservada**: posteo orgánico de LinkedIn de la agencia **ABAR**
  (fecha aprox. 08/09/2026, dentro de la ventana de 7 días), footprint
  **"Estamos buscando talento freelance"**, 100% freelance, match con
  diseño/desarrollo web + SEO técnico. Aplicación por formulario (lnkd.in).

## 2) Motores probados (búsqueda automatizada, sin login)
| Motor / fuente | Consulta | Resultado |
|---|---|---|
| Google (`tbs=qdr:w`) | `"buscamos perfiles freelance" site:linkedin.com/posts` | Página sin resultados orgánicos (redirección JS/consent). No extraíble. |
| Bing | `"estamos buscando talento freelance" site:linkedin.com/posts` | Ignora el `site:` → devuelve diccionarios (llevatilde, buscapalabra), Wikipedia, gob.ar. Cero posts. |
| Bing | `"buscamos perfiles freelance para" site:linkedin.com/posts` | Igual: adopción argentina, Instagram, Clarín. Cero posts. |
| Bing | `"creando nuestra red de talento freelance"` | GitHub/ChatGPT topics, zhihu. Cero posts. |
| Bing con filtro de fecha (`filters=ex1:"ez5_..."`) | `site:linkedin.com/posts "freelance" (web/SEO/Python)` | Ignora `site:` → devuelve **portales de empleo** (freelancer.com, fiverr, workana, upwork, computrabajo, freelanceargentina). Todos DESCARTADOS por regla estricta. |
| Bing con filtro de fecha | x.com / twitter.com `site:` | Cero posts relevantes (radios "La Red", reddit). |
| LinkedIn `search/results/content` | `"buscamos perfiles freelance para"` | **Muro de login** (authwall). Sin sesión no lista nada. |
| X / Twitter | búsquedas con `f=live` | **Muro de login**. |
| DuckDuckGo html/lite | varias | Challenge anti-bot (bloqueo). |
| Reddit JSON (`r/forhire`) | — | 403 Blocked. |

**Causa raíz (verificada):** los `/posts/` de LinkedIn y los `status` de X están
detrás de authwall → **ningún buscador público los indexa**. No existe hoy vía
automatizada sin credenciales que devuelva posteos orgánicos ≤7 días con esas
frases exactas. Cualquier lista con links+fechas "de LinkedIn" obtenida sin
login sería inventada, y no se fabricó.

## 3) Resultado final válido en la pestaña `oportunidades_freelance`
| Campo | Valor |
|---|---|
| Empresa/Agencia | ABAR (agencia) |
| Fecha publicación | 08/09/2026 aprox. ('16 h' al leerlo el 09/09/2026) |
| Enlace | post LinkedIn `trabajamos-juntos-share-7502673187508297728` (clickeable en la hoja) |
| Frase detectada | "Estamos buscando talento freelance" / "creando red de talento freelance" |
| Requisitos | diseño gráfico/branding, diseño y desarrollo web, foto/video, Paid Media, **SEO técnico** — aplicación por formulario `https://lnkd.in/eEPatUkp` |
| Freelance | Sí, 100% (armado de red/base de talento) |

## 4) Camino para completar la pestaña (pipeline recomendado)
1. Logueado en LinkedIn → pegar URLs de `consultas_linkedin.txt` → filtro
   **Fecha: Última semana** → copiar links de posteos.
2. Pegarlas en `python busqueda_linkedin/linkedin_manual_busqueda.py`
   (rechaza portales, enriquece autor/fecha, deduplica) o
   `actualizar_oportunidades_freelance.py --add URL... --empresa "..."`.
3. Opcional: configurar Google CSE en `.env` para automatizar lo indexable.
