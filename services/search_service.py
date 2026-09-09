"""
Search Service - Búsqueda de leads vía APIs y scraping.
"""
import logging
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
    
    def search_marketing_agencies(self, country: str = "Argentina", 
                                 limit: int = 10) -> List[Lead]:
        """
        Busca agencias de marketing sin developer.
        
        Args:
            country: País
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
            query = f"agencia de marketing digital {country}"
            
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
                    lead = Lead(
                        business_name=item.get("title", "Unknown"),
                        email=email,
                        track=TrackType.MARKETING,
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
    
    def _search_marketing_agencies_duckduckgo(self, country: str, limit: int) -> List[Lead]:
        """Busca agencias de marketing reales vía DuckDuckGo (sin API key).

        Usa la misma estrategia de búsqueda general (no restringida a un
        sitio) que se usó para relevar leads a mano: nombre de rubro +
        país, extrayendo el email de verdad del snippet del resultado.
        """
        query = f"agencia de marketing digital {country} contacto email"
        results = search_duckduckgo(query, limit=limit * 3, session=self.session)

        leads = []
        seen_domains = set()
        pages_visited = 0
        for item in results:
            domain = urlparse(item.get("link", "")).netloc.lower()
            if domain and domain in seen_domains:
                continue
            email = self._extract_email(item.get("snippet", "") + " " + item.get("title", ""))
            # Los snippets casi nunca traen el email; visitamos la página real
            # (con un tope para no demorar de más ni golpear muchos sitios).
            if not email and pages_visited < 15:
                pages_visited += 1
                email = find_email_on_page(item.get("link", ""), session=self.session)
            if not email:
                continue
            if domain:
                seen_domains.add(domain)
            lead = Lead(
                business_name=item.get("title", "Unknown").split(" - ")[0].strip(),
                email=email,
                track=TrackType.MARKETING,
                country=country,
                website=item.get("link") or None,
                source="DuckDuckGo",
            )
            if self.validate_lead(lead):
                leads.append(lead)
            if len(leads) >= limit:
                break

        return leads

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
                business_name=item.get("title", "Unknown").split(" - ")[0].strip(),
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
