"""
Search Service - Búsqueda de leads vía APIs y scraping.
"""
import logging
import time
from typing import Optional, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from core.models import Lead, TrackType
from core.constants import EXCLUDED_COMPANIES, MARKETING_KEYWORDS
from services.duckduckgo_search import search_duckduckgo, find_email_on_page

logger = logging.getLogger(__name__)


def get_session():
    """Sesión requests con reintentos."""
    session = requests.Session()
    retry = Retry(connect=3, backoff_factor=0.5)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


class SearchService:
    """Servicio para buscar y verificar leads."""

    # Regiones soportadas además de un país puntual: "latam" busca en varios
    # países de LatAm a la vez (OR en la query) en vez de uno solo.
    _REGION_QUERY_HINTS = {
        "latam": "Argentina OR Chile OR Colombia OR México OR Perú OR Uruguay",
        "espana": "España",
        "spain": "España",
    }
    _REGION_LABELS = {
        "latam": "LatAm",
        "espana": "España",
        "spain": "España",
    }
    # ccTLD -> país real, para no etiquetar todo con la región genérica
    # cuando se puede saber el país real por el dominio del sitio encontrado.
    _TLD_TO_COUNTRY = {
        "ar": "Argentina", "cl": "Chile", "co": "Colombia", "mx": "México",
        "pe": "Perú", "uy": "Uruguay", "es": "España",
    }

    def __init__(self, api_key: Optional[str] = None,
                 custom_search_engine_id: Optional[str] = None):
        """
        Args:
            api_key: Google Custom Search API key
            custom_search_engine_id: ID del motor de búsqueda personalizado
        """
        self.api_key = api_key
        self.engine_id = custom_search_engine_id
        self.session = get_session()

    @classmethod
    def _country_query_fragment(cls, country_or_region: str) -> str:
        """Convierte "latam"/"espana"/"spain" en un OR de países para la
        query; si es un país puntual (ej. "Argentina") lo deja igual."""
        return cls._REGION_QUERY_HINTS.get(country_or_region.strip().lower(), country_or_region)

    @classmethod
    def _region_fallback_label(cls, country_or_region: str) -> str:
        """Nombre a mostrar en la columna Ciudad/País si no se pudo inferir
        el país real del lead a partir de su dominio."""
        return cls._REGION_LABELS.get(country_or_region.strip().lower(), country_or_region)

    @classmethod
    def _infer_country_from_domain(cls, domain: str, fallback: str) -> str:
        """Deduce el país real por el ccTLD del sitio (ej. .com.ar ->
        Argentina). Si no matchea ninguno conocido, usa el fallback (el país
        puntual pedido, o la etiqueta de región si se buscó por LatAm/España)."""
        domain = (domain or "").lower()
        for tld, country in cls._TLD_TO_COUNTRY.items():
            if domain.endswith(f".{tld}"):
                return country
        return fallback

    def search_marketing_agencies(self, country: str = "Argentina",
                                 limit: int = 10) -> List[Lead]:
        """
        Busca agencias de marketing sin developer.

        Args:
            country: País puntual (ej. "Argentina") o región completa
                     ("latam" o "espana"/"spain")
            limit: Cantidad de resultados

        Returns:
            Lista de leads encontrados
        """
        logger.info(f"🔎 Buscando agencias de marketing en {country}...")
        
        leads = []

        # Alternativa 1: Google Custom Search API (si está configurada y con billing activo)
        if self.api_key and self.engine_id:
            leads = self._search_with_custom_search(country, limit)

        # Alternativa 2: DuckDuckGo (gratis, sin key, sin facturación) - siempre
        # disponible como respaldo si Google no está configurado o falló
        if len(leads) < limit:
            leads.extend(
                self._search_marketing_agencies_duckduckgo(country, limit - len(leads))
            )

        # Sin resultados reales: no se inventa nada, se devuelve lo que haya
        # (puede ser una lista vacía) para que el llamador no escriba datos falsos.
        if not leads:
            logger.warning(f"⚠️  No se encontraron leads reales para {country}")

        return leads[:limit]
    
    def search_pymes(self, industry: str, city: str, 
                    limit: int = 10) -> List[Lead]:
        """
        Busca PyMEs del rubro especificado sin web.
        
        Args:
            industry: Rubro (restaurante, inmobiliaria, etc.)
            city: Ciudad
            limit: Cantidad
        
        Returns:
            Lista de leads
        """
        logger.info(f"🔎 Buscando {industry} en {city}...")
        
        leads = []

        if self.api_key and self.engine_id:
            leads = self._search_pymes_with_api(industry, city, limit)

        if len(leads) < limit:
            leads.extend(
                self._search_pymes_duckduckgo(industry, city, limit - len(leads))
            )

        if not leads:
            logger.warning(f"⚠️  No se encontraron PyMEs reales de {industry} en {city}")

        return leads[:limit]
    
    def _search_with_custom_search(self, country: str, limit: int) -> List[Lead]:
        """Búsqueda con Google Custom Search API."""
        try:
            leads = []
            query = f"agencia de marketing digital {self._country_query_fragment(country)}"
            fallback_country = self._region_fallback_label(country)

            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "q": query,
                "key": self.api_key,
                "cx": self.engine_id,
                "num": min(limit, 10),  # Max 10 por query
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            for item in data.get("items", []):
                # Busca email o contacto
                email = self._extract_email(item.get("snippet", ""))

                if email:
                    domain = urlparse(item.get("link", "")).netloc.lower()
                    lead = Lead(
                        business_name=item.get("title", "Unknown"),
                        email=email,
                        track=TrackType.MARKETING,
                        country=self._infer_country_from_domain(domain, fallback_country),
                        source="Google Custom Search",
                    )
                    leads.append(lead)
            
            logger.info(f"✅ {len(leads)} leads encontrados con API")
            return leads
        except requests.HTTPError as e:
            self._log_custom_search_http_error(e, context="search_marketing_agencies")
            return []
        except requests.RequestException as e:
            logger.warning(f"⚠️  Error de red con Custom Search: {e}")
            return []
        except Exception as e:
            logger.warning(f"⚠️  Error inesperado con Custom Search: {e}")
            return []
    
    def _search_pymes_with_api(self, industry: str, city: str, 
                              limit: int) -> List[Lead]:
        """Búsqueda de PyMEs con API."""
        try:
            leads = []
            query = f"{industry} {city} Argentina sin web"
            
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "q": query,
                "key": self.api_key,
                "cx": self.engine_id,
                "num": min(limit, 10),
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            for item in data.get("items", []):
                email = self._extract_email(item.get("snippet", ""))
                
                if email:
                    lead = Lead(
                        business_name=item.get("title", "Unknown"),
                        email=email,
                        industry=industry,
                        city=city,
                        country="Argentina",
                        track=TrackType.PYME,
                        source="Google Custom Search",
                    )
                    leads.append(lead)
            
            return leads
        except requests.HTTPError as e:
            self._log_custom_search_http_error(e, context="search_pymes")
            return []
        except requests.RequestException as e:
            logger.warning(f"⚠️  Error de red buscando PyMEs con Custom Search: {e}")
            return []
        except Exception as e:
            logger.warning(f"⚠️  Error inesperado buscando PyMEs: {e}")
            return []

    @staticmethod
    def _sanitize_url(url: str) -> str:
        """Oculta credenciales en query params para logs."""
        if not url:
            return ""

        parsed = urlparse(url)
        params = parse_qsl(parsed.query, keep_blank_values=True)
        safe_params = []
        for key, value in params:
            if key.lower() in {"key", "api_key", "apikey", "token"}:
                masked = f"***{value[-4:]}" if value else "***"
                safe_params.append((key, masked))
            else:
                safe_params.append((key, value))

        safe_query = urlencode(safe_params)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, safe_query, parsed.fragment))

    @staticmethod
    def _extract_google_error_reason(response: requests.Response) -> tuple[str, str]:
        """Extrae reason/message estándar de Google APIs."""
        reason = ""
        message = ""
        try:
            payload = response.json()
            error_obj = payload.get("error", {}) if isinstance(payload, dict) else {}
            message = str(error_obj.get("message", ""))
            errors = error_obj.get("errors", [])
            if isinstance(errors, list) and errors:
                first = errors[0] if isinstance(errors[0], dict) else {}
                reason = str(first.get("reason", ""))
        except ValueError:
            message = response.text[:200]

        return reason, message

    @staticmethod
    def _google_cse_hint_for_reason(reason: str) -> str:
        hints = {
            "keyInvalid": "API key inválida: revisa GOOGLE_CUSTOM_SEARCH_API_KEY.",
            "API_KEY_INVALID": "API key inválida: revisa GOOGLE_CUSTOM_SEARCH_API_KEY.",
            "accessNotConfigured": "Habilita Custom Search API en Google Cloud para este proyecto.",
            "SERVICE_DISABLED": "Habilita Custom Search API en Google Cloud para este proyecto.",
            "dailyLimitExceeded": "Cuota diaria agotada.",
            "quotaExceeded": "Cuota del proyecto agotada.",
            "userRateLimitExceeded": "Rate limit excedido.",
            "ipRefererBlocked": "Restricciones de API key (IP/referrer) bloquean esta llamada.",
            "forbidden": "Revisa billing, API habilitada y restricciones de la API key.",
            "billingNotActive": "Billing no activo en Google Cloud.",
        }
        return hints.get(reason, "")

    def _log_custom_search_http_error(self, error: requests.HTTPError, context: str) -> None:
        response = error.response
        if response is None:
            logger.warning("⚠️  Error HTTP en Google Custom Search (%s) sin respuesta asociada", context)
            return

        safe_url = self._sanitize_url(response.url)
        reason, message = self._extract_google_error_reason(response)
        hint = self._google_cse_hint_for_reason(reason)

        logger.warning(
            "⚠️  Google Custom Search %s (%s) | reason=%s | message=%s | url=%s%s",
            response.status_code,
            context,
            reason or "unknown",
            message or "sin mensaje",
            safe_url,
            f" | hint={hint}" if hint else "",
        )
    
    # Segmentos reales del target definido en sistema_agentes_freelance.md:
    # "agencias de marketing, freelancers y community managers ... sin
    # developer propio". Se rota entre ellos para no traer siempre el mismo
    # tipo de perfil (antes quedaba fijo en "agencia de marketing digital").
    _MARKETING_SEGMENTS = [
        ("Agencia de marketing digital", "agencia de marketing digital {country} contacto email"),
        ("Freelance de marketing digital", "freelance marketing digital {country} contacto email"),
        ("Community manager freelance", "community manager freelance {country} contacto email"),
        ("Diseñador gráfico freelance", "diseñador gráfico freelance {country} contacto email"),
    ]

    def _search_marketing_agencies_duckduckgo(self, country: str, limit: int) -> List[Lead]:
        """Busca agencias/freelancers/community managers/diseñadores reales
        vía DuckDuckGo (sin API key), repartiendo el límite entre los
        distintos segmentos del target para traer una mezcla real de
        perfiles en vez de agotar el cupo con el primer segmento.
        """
        leads = []
        seen_domains = set()
        pages_visited = 0
        num_segments = len(self._MARKETING_SEGMENTS)
        per_segment = max(1, -(-limit // num_segments))  # ceil(limit / segmentos)
        country_fragment = self._country_query_fragment(country)
        fallback_country = self._region_fallback_label(country)

        for segment_index, (industry_label, query_template) in enumerate(self._MARKETING_SEGMENTS):
            if len(leads) >= limit:
                break

            if segment_index > 0:
                # Pausa corta entre segmentos: varias queries seguidas al
                # toque disparan el rate-limit de DuckDuckGo aunque no sean
                # muchas (confirmado en vivo - 2 queries seguidas ya alcanzan).
                time.sleep(4)

            segment_target = min(per_segment, limit - len(leads))
            query = query_template.format(country=country_fragment)
            results = search_duckduckgo(query, limit=segment_target * 3, session=self.session)

            added_this_segment = 0
            for item in results:
                if added_this_segment >= segment_target:
                    break
                domain = urlparse(item.get("link", "")).netloc.lower()
                if domain and domain in seen_domains:
                    continue
                email = self._extract_email(item.get("snippet", "") + " " + item.get("title", ""))
                # Los snippets casi nunca traen el email; visitamos la página
                # real (con un tope para no demorar de más ni golpear muchos
                # sitios).
                if not email and pages_visited < 15:
                    pages_visited += 1
                    email = find_email_on_page(item.get("link", ""), session=self.session)
                if not email:
                    continue
                if domain:
                    seen_domains.add(domain)
                lead = Lead(
                    business_name=self._business_name_from_result(item.get("title", ""), item.get("link", "")),
                    email=email,
                    track=TrackType.MARKETING,
                    industry=industry_label,
                    country=self._infer_country_from_domain(domain, fallback_country),
                    website=item.get("link") or None,
                    source="DuckDuckGo",
                )
                if self.validate_lead(lead):
                    leads.append(lead)
                    added_this_segment += 1

        return leads[:limit]

    def _search_pymes_duckduckgo(self, industry: str, city: str, limit: int) -> List[Lead]:
        """Busca PyMEs reales vía DuckDuckGo (sin API key)."""
        query = f"{industry} {city} Argentina contacto email -linkedin"
        results = search_duckduckgo(query, limit=limit * 3, session=self.session)

        leads = []
        seen_domains = set()
        pages_visited = 0
        for item in results:
            domain = urlparse(item.get("link", "")).netloc.lower()
            if domain and domain in seen_domains:
                continue
            email = self._extract_email(item.get("snippet", "") + " " + item.get("title", ""))
            if not email and pages_visited < 15:
                pages_visited += 1
                email = find_email_on_page(item.get("link", ""), session=self.session)
            if not email:
                continue
            if domain:
                seen_domains.add(domain)
            lead = Lead(
                business_name=self._business_name_from_result(item.get("title", ""), item.get("link", "")),
                email=email,
                industry=industry,
                city=city,
                country="Argentina",
                track=TrackType.PYME,
                website=item.get("link") or None,
                source="DuckDuckGo",
            )
            if self.validate_lead(lead):
                leads.append(lead)
            if len(leads) >= limit:
                break

        return leads
    
    _GENERIC_PAGE_TITLES = {
        "contacto", "contáctanos", "contactanos", "contact", "contact us",
        "inicio", "home", "nosotros", "bienvenidos", "bienvenido",
    }

    @classmethod
    def _business_name_from_result(cls, title: str, link: str) -> str:
        """Nombre de negocio a partir del resultado de búsqueda.

        Muchos sitios usan como <title> de la página de contacto solo
        "Contacto" o "Inicio" (no el nombre del negocio). En ese caso el
        título no sirve, así que se usa el dominio del sitio como nombre
        (siempre dato real, nunca inventado).
        """
        cleaned = (title or "").split(" - ")[0].strip()
        if cleaned.lower() in cls._GENERIC_PAGE_TITLES or not cleaned:
            domain = urlparse(link).netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            return domain.split(".")[0].capitalize() if domain else "Unknown"
        return cleaned

    @staticmethod
    def _extract_email(text: str) -> Optional[str]:
        """Extrae email de texto.

        Los snippets de buscadores suelen venir con espacios/saltos de línea
        colapsados, lo que a veces pega la palabra anterior al inicio del
        email (ej. "atenderte.Emailinfo@dominio.com"). Un email real casi
        siempre es todo minúscula, así que si el candidato trae mayúsculas
        internas se descarta por sospechoso en vez de guardar basura.
        """
        import re
        match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        if not match:
            return None
        candidate = match.group(0)
        if candidate != candidate.lower():
            return None
        return candidate
    
    def validate_lead(self, lead: Lead) -> bool:
        """
        Valida que un lead sea válido (no en exclusión, etc.).
        
        Returns:
            True si es válido
        """
        # Chequea excluidos
        business_lower = lead.business_name.lower()
        for excluded in EXCLUDED_COMPANIES:
            if excluded in business_lower:
                logger.info(f"⏭️  Lead descartado (empresa excluida): {lead.business_name}")
                return False
        
        # Valida email
        if not lead.email or "@" not in lead.email:
            logger.info(f"⏭️  Lead sin email válido: {lead.business_name}")
            return False
        
        return True
