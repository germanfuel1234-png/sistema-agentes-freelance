# busqueda_linkedin — Cazador de posteos orgánicos de LinkedIn/X (100% freelance)

**Planilla:** `https://docs.google.com/spreadsheets/d/1hjwAUrKaCu53McleYaJZj99b65IoKHBVqIZ96qfvF1I`
**Pestaña destino:** `oportunidades_freelance` (no toca `leads_tracking.csv`)

## REGLA ESTRICTA (aplicada en código)

1. **Prohibido** buscar o extraer datos de portales de empleo: Freelancer, Upwork,
   Workana, Fiverr, Computrabajo, Bumeran, Zonajobs, Indeed, Glassdoor, etc.
   → `PORTALES_BLOCK` en el script; cualquier URL de esos dominios se descarta
   automáticamente y `--add` se niega a guardarlas.
2. **Solo posteos orgánicos** de personas/reclutadores/dueños de agencias en
   **LinkedIn o X** (`linkedin.com/posts`, `x.com|twitter.com/status`).
3. Ventana de **últimos 7 días** (descarte por fecha del posteo).
4. Frases exactas ("footprints"): `estamos buscando talento freelance`,
   `creando nuestra red de talento freelance`, `buscamos perfiles freelance para`.
5. Skills del perfil: desarrollo/diseño web, SEO técnico, análisis de sistemas,
   Python, PHP, Dart, Kotlin.

## Archivos

| Archivo | Qué es |
|---|---|
| `actualizar_oportunidades_freelance.py` | Buscador + escritor a Sheets. Web-search (Google CSE si hay keys, sino DDG/Bing) **filtrado por red social**; `--manual` imprime las URLs de búsqueda logueado; `--add` valida y guarda con dedup. |
| `linkedin_manual_busqueda.py` | Asistente **interactivo**: te muestra las búsquedas listas para pegar (logueado en LinkedIn/X), aceptas URLs una por una (rechaza portales), enriquece autor/fecha y guarda con dedup. |
| `consultas_linkedin.txt` | Las consultas exactas copiables (LinkedIn y X, con filtro de 7 días). |
| `resultados_busqueda_2026-09-09.md` | Bitácora de la búsqueda del 09/09/2026: qué se probó, qué se descartó y qué quedó válido. |

## Por qué el paso "manual/logueado"

Los `/posts/` de LinkedIn y los `status` de X **no están indexados** por
Google/Bing (authwall verificado el 09/09/2026): ningún buscador público los
devuelve. Por eso el flujo confiable es: buscás **logueado** con las consultas
de `consultas_linkedin.txt` (filtro "Última semana"), copiás las URLs de los
posteos y las pegás en el asistente. Lo que se pueda indexar vía Google CSE
(configurando `GOOGLE_CUSTOM_SEARCH_API_KEY` + `GOOGLE_CUSTOM_SEARCH_ENGINE_ID`
en `.env`) se automatiza solo con `--days 7`.

## Uso (desde la raíz del repo)

```powershell
# 1) ver las búsquedas listas
python busqueda_linkedin/actualizar_oportunidades_freelance.py --manual

# 2) buscar logueado en LinkedIn/X con esas URLs, copiar posteos y pegarlos acá
python busqueda_linkedin/linkedin_manual_busqueda.py

# 3) o directo por CLI (valida regla estricta y deduplica)
python busqueda_linkedin/actualizar_oportunidades_freelance.py --add "https://www.linkedin.com/posts/..." --empresa "Agencia X"

# opcional: búsqueda automática respetando regla estricta
python busqueda_linkedin/actualizar_oportunidades_freelance.py --days 7 --enrich
```

## Columnas de la pestaña

`Fecha hallazgo | Empresa/Agencia | Fecha publicacion | Enlace (clickeable) |
Requisitos / Match perfil | Fuente | Frase detectada`
