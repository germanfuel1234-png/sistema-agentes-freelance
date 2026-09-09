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
        
        # Alternativa 1: Si tenemos Google Custom Search API
        if self.api_key and self.engine_id:
            leads = self._search_with_custom_search(country, limit)
        
        # Alternativa 2: Scraping local de info mock
        if not leads or len(leads) < limit:
            leads.extend(self._generate_mock_leads(country, limit - len(leads)))
        
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
        
        if not leads or len(leads) < limit:
            leads.extend(self._generate_mock_leads_pymes(industry, city, limit - len(leads)))
        
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
    
    def _generate_mock_leads(self, country: str, limit: int) -> List[Lead]:
        """Genera leads mock para demo."""
        mock_leads = [
            Lead(
                business_name="Agencia Marketing Pro",
                contact_name="Juan García",
                email=f"juan{i}@agenciapro.com.ar",
                track=TrackType.MARKETING,
                city="Buenos Aires",
                country=country,
                industry="Marketing Digital",
                source="Demo Mock",
            )
            for i in range(1, min(limit + 1, 6))
        ]
        logger.info(f"ℹ️  Usando {len(mock_leads)} leads de demo (sin API)")
        return mock_leads
    
    def _generate_mock_leads_pymes(self, industry: str, city: str, 
                                   limit: int) -> List[Lead]:
        """Genera PyMEs mock."""
        mock_leads = [
            Lead(
                business_name=f"{industry.title()} {i}",
                contact_name=f"Contacto {i}",
                email=f"contacto{i}@negocio.ar",
                track=TrackType.PYME,
                city=city,
                country="Argentina",
                industry=industry,
                source="Demo Mock",
            )
            for i in range(1, min(limit + 1, 6))
        ]
        return mock_leads
    
    @staticmethod
    def _extract_email(text: str) -> Optional[str]:
        """Extrae email de texto."""
        import re
        match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        return match.group(0) if match else None
    
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
