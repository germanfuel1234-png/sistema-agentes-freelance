"""
Advanced Search Service - Búsqueda multi-fuente de leads (LinkedIn, PyMEs, Instagram)
Extrae: Nombre + Email
Objetivo: Agregar rápidamente a Google Sheets
"""
import logging
import re
import random
from typing import Optional, List, Dict, Tuple
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
import requests
from bs4 import BeautifulSoup

from core.models import Lead, TrackType
from config.settings import settings
from services.duckduckgo_search import search_duckduckgo

logger = logging.getLogger(__name__)


class AdvancedSearchService:
    """
    Búsqueda avanzada de leads en múltiples fuentes:
    - LinkedIn (perfiles, empresas)
    - PyMEs (directorios, registros)
    - Instagram (perfiles marketing, hashtags)
    - Contacto directo (email extraction)
    
    Retorna: SOLO nombre + email (para agregar rápido a Sheets)
    """
    
    def __init__(self):
        self.session = self._get_session()
        self.custom_search_api_key = settings.google_custom_search_api_key
        self.custom_search_engine_id = settings.google_custom_search_engine_id
        
        # Patrones de búsqueda
        self.email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        self.linkedin_url_pattern = r'linkedin\.com/in/[\w-]+'
        
        # Regiones
        self.latam_countries = [
            "Argentina", "Chile", "Colombia", "México", "Perú", 
            "Bolivia", "Paraguay", "Uruguay", "Ecuador", "Venezuela"
        ]
        self.spain = "España"
    
    def _get_session(self):
        """Sesión HTTP con headers realistas."""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        return session

    @staticmethod
    def _region_query(region: str) -> str:
        if region == "spain":
            return "España OR Spain"
        return "Argentina OR Chile OR Colombia OR Mexico OR Peru OR Uruguay"

    def _search_with_google_custom_search(self, query: str, limit: int = 10) -> List[Dict]:
        """Ejecuta Google Custom Search y devuelve items crudos."""
        if not self.custom_search_api_key or not self.custom_search_engine_id:
            return []

        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "q": query,
                "key": self.custom_search_api_key,
                "cx": self.custom_search_engine_id,
                "num": min(limit, 10),
            }
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return data.get("items", [])
        except requests.HTTPError as e:
            response = e.response
            if response is not None:
                safe_url = self._sanitize_url(response.url)
                reason, message = self._extract_google_error_reason(response)
                hint = self._google_cse_hint_for_reason(reason)
                logger.warning(
                    "⚠️  Google Custom Search %s | reason=%s | message=%s | url=%s%s",
                    response.status_code,
                    reason or "unknown",
                    message or "sin mensaje",
                    safe_url,
                    f" | hint={hint}" if hint else "",
                )
            else:
                logger.warning("⚠️  Error HTTP en Google Custom Search sin respuesta asociada")
            return []
        except requests.RequestException as e:
            logger.warning(f"⚠️  Error de red en Google Custom Search: {e}")
            return []
        except Exception as e:
            logger.warning(f"⚠️  Error inesperado en Google Custom Search: {e}")
            return []

    @staticmethod
    def _sanitize_url(url: str) -> str:
        """Oculta secretos en query params antes de loggear URLs."""
        if not url:
            return ""

        parsed = urlparse(url)
        params = parse_qsl(parsed.query, keep_blank_values=True)
        safe_params = []
        for key, value in params:
            if key.lower() in {"key", "api_key", "apikey", "token"}:
                if value:
                    masked = f"***{value[-4:]}"
                else:
                    masked = "***"
                safe_params.append((key, masked))
            else:
                safe_params.append((key, value))

        safe_query = urlencode(safe_params)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, safe_query, parsed.fragment))

    @staticmethod
    def _extract_google_error_reason(response: requests.Response) -> Tuple[str, str]:
        """Devuelve reason/message de errores JSON de Google APIs."""
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
        """Sugiere la corrección más probable para errores conocidos de CSE."""
        hints = {
            "keyInvalid": "La API key no es válida. Revisa GOOGLE_CUSTOM_SEARCH_API_KEY en .env.",
            "API_KEY_INVALID": "La API key no es válida. Revisa GOOGLE_CUSTOM_SEARCH_API_KEY en .env.",
            "accessNotConfigured": "Habilita Custom Search API para ese proyecto en Google Cloud.",
            "SERVICE_DISABLED": "Habilita Custom Search API para ese proyecto en Google Cloud.",
            "dailyLimitExceeded": "Se agotó la cuota diaria del proyecto. Espera reset o aumenta cuota.",
            "quotaExceeded": "Se agotó la cuota del proyecto. Revisa cuotas en Google Cloud Console.",
            "userRateLimitExceeded": "Se excedió el rate limit. Reduce frecuencia o aumenta cuota.",
            "ipRefererBlocked": "La key tiene restricciones (IP/referrer) incompatibles con este entorno.",
            "forbidden": "Verifica billing habilitado, API activa y restricciones de la API key.",
            "billingNotActive": "Activa billing en el proyecto de Google Cloud para usar esta API.",
        }
        return hints.get(reason, "")

    @staticmethod
    def _extract_company_from_snippet(snippet: str) -> str:
        """Intenta extraer empresa del snippet de LinkedIn."""
        if not snippet:
            return ""
        parts = [p.strip() for p in snippet.split("·") if p.strip()]
        if len(parts) >= 2:
            return parts[1]
        return ""

    def _discover_email_for_profile(self, profile_name: str, company: str = "") -> str:
        """Busca email público relacionado al perfil usando CSE + regex."""
        if not self.custom_search_api_key or not self.custom_search_engine_id:
            return ""

        base_query = f'"{profile_name}" email contacto'
        if company:
            base_query += f' "{company}"'

        items = self._search_with_google_custom_search(base_query, limit=5)
        for item in items:
            text = f"{item.get('title', '')} {item.get('snippet', '')}"
            match = re.search(self.email_pattern, text)
            if match:
                return match.group(0).lower()

        return ""

    @staticmethod
    def _normalize_domain_from_url(url: str) -> str:
        """Normaliza URL a dominio raíz simple para proveedores de email finder."""
        if not url:
            return ""

        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = (parsed.netloc or "").lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host

    def _discover_company_website(self, company: str, region: str = "latam") -> str:
        """Intenta detectar el sitio oficial de la empresa usando Google CSE."""
        if not company or not self.custom_search_api_key or not self.custom_search_engine_id:
            return ""

        region_hint = self._region_query(region)
        query = f'"{company}" ({region_hint}) -site:linkedin.com -site:instagram.com'
        items = self._search_with_google_custom_search(query, limit=5)

        for item in items:
            link = (item.get("link") or "").strip()
            if not link:
                continue
            lower_link = link.lower()
            if "linkedin.com" in lower_link or "instagram.com" in lower_link:
                continue

            domain = self._normalize_domain_from_url(link)
            if domain:
                return link

        return ""

    def enrich_lead_with_website_domain(self, lead: Dict, region: str = "latam") -> Dict:
        """
        Completa website y website_domain para mejorar éxito de proveedores tipo Hunter.
        No pisa datos existentes.
        """
        enriched = dict(lead)
        current_website = (enriched.get("website") or "").strip()
        current_domain = (enriched.get("website_domain") or "").strip()

        if current_domain:
            return enriched

        if current_website and not current_domain:
            normalized = self._normalize_domain_from_url(current_website)
            if normalized:
                enriched["website_domain"] = normalized
                return enriched

        company = (enriched.get("empresa") or enriched.get("business_name") or "").strip()
        if company:
            website = self._discover_company_website(company, region=region)
            if website:
                enriched["website"] = website
                enriched["website_domain"] = self._normalize_domain_from_url(website)

        return enriched
    
    def search_linkedin_professionals(self, 
                                     keywords: str,
                                     region: str = "latam",
                                     limit: int = 20) -> List[Dict]:
        """
        Busca profesionales en LinkedIn.
        
        Args:
            keywords: "marketing manager", "community manager", "agencia marketing"
            region: "latam" o "spain"
            limit: Máximo de resultados
        
        Returns:
            [{"nombre": "Juan García", "email": "juan@example.com", "linkedin": "..."}]
        """
        logger.info(f"🔍 Buscando en LinkedIn: {keywords} ({region})")
        
        results = []
        
        try:
            region_hint = self._region_query(region)

            if self.custom_search_api_key and self.custom_search_engine_id:
                query = (
                    f"site:linkedin.com/in ({keywords}) (marketing OR agencia OR agency) "
                    f"({region_hint})"
                )
                items = self._search_with_google_custom_search(query, limit=limit)

                for item in items:
                    link = item.get("link", "")
                    if "linkedin.com/in/" not in link:
                        continue

                    title = item.get("title", "").replace(" | LinkedIn", "").strip()
                    snippet = item.get("snippet", "")
                    company = self._extract_company_from_snippet(snippet)
                    email = self._discover_email_for_profile(title, company)

                    # Cargo aproximado desde snippet
                    cargo = snippet.split("·")[0].strip() if snippet else ""

                    results.append({
                        "nombre": title or "N/A",
                        "email": email,
                        "linkedin": link,
                        "empresa": company,
                        "cargo": cargo,
                        "bio": snippet,
                    })

                logger.info(f"✅ LinkedIn real (Google CSE): {len(results)} perfiles")

            # Respaldo gratuito (sin API key, sin facturación) cuando Google
            # no está configurado o no devolvió nada útil. Nunca se inventan
            # perfiles: si no hay resultados reales, se devuelve lista vacía.
            if not results:
                query = (
                    f"site:linkedin.com/in {keywords} (marketing OR agencia OR agency) "
                    f"{region_hint}"
                )
                items = search_duckduckgo(query, limit=limit, session=self.session)

                for item in items:
                    link = item.get("link", "")
                    if "linkedin.com/in/" not in link:
                        continue

                    title = item.get("title", "").replace(" | LinkedIn", "").strip()
                    snippet = item.get("snippet", "")
                    company = self._extract_company_from_snippet(snippet)
                    email = self._discover_email_for_profile(title, company)
                    cargo = snippet.split("·")[0].strip() if snippet else ""

                    results.append({
                        "nombre": title or "N/A",
                        "email": email,
                        "linkedin": link,
                        "empresa": company,
                        "cargo": cargo,
                        "bio": snippet,
                    })

                logger.info(f"✅ LinkedIn real (DuckDuckGo): {len(results)} perfiles")

            if not results:
                logger.warning(f"⚠️  Sin resultados reales de LinkedIn para '{keywords}' ({region})")

        except Exception as e:
            logger.error(f"❌ Error buscando LinkedIn: {e}")

        return results

    @staticmethod
    def _seems_marketing_profile(lead: Dict) -> bool:
        """Evalúa si el lead parece pertenecer al sector marketing."""
        text = " ".join([
            str(lead.get("cargo", "")),
            str(lead.get("bio", "")),
            str(lead.get("empresa", "")),
        ]).lower()
        marketing_keywords = [
            "marketing", "social media", "branding", "publicidad", "growth", "performance"
        ]
        return any(k in text for k in marketing_keywords)

    @staticmethod
    def _has_tech_team_signals(lead: Dict) -> bool:
        """Detecta señales de equipo tecnológico interno para de-priorizar."""
        text = " ".join([
            str(lead.get("cargo", "")),
            str(lead.get("bio", "")),
            str(lead.get("empresa", "")),
        ]).lower()
        tech_signals = [
            "equipo tech", "developer", "desarrollo", "software", "cto", "engineering", "apps"
        ]
        return any(k in text for k in tech_signals)

    @staticmethod
    def _has_non_target_signals(lead: Dict) -> bool:
        """Descarta perfiles alejados de marketing/agencia objetivo."""
        text = " ".join([
            str(lead.get("cargo", "")),
            str(lead.get("bio", "")),
            str(lead.get("empresa", "")),
        ]).lower()
        non_target_signals = [
            "operations",
            "analytics",
            "organizational transformation",
            "transformation",
            "strategy",
            "data science",
        ]
        return any(k in text for k in non_target_signals)

    @staticmethod
    def _strict_marketing_score(lead: Dict) -> int:
        """Scoring estricto para priorizar mejores candidatos de marketing."""
        text = " ".join([
            str(lead.get("cargo", "")),
            str(lead.get("bio", "")),
            str(lead.get("empresa", "")),
            str(lead.get("nombre", "")),
        ]).lower()

        include_keywords = [
            "marketing",
            "digital",
            "social media",
            "branding",
            "publicidad",
            "community",
            "agency",
            "agencia",
            "performance",
            "growth",
        ]
        exclude_keywords = [
            "developer",
            "desarrollo",
            "engineering",
            "software",
            "cto",
            "operations",
            "analytics",
            "transformation",
        ]

        include_hits = sum(1 for k in include_keywords if k in text)
        exclude_hits = sum(1 for k in exclude_keywords if k in text)

        score = include_hits * 2 - exclude_hits * 3

        # Bonus por rol muy objetivo
        if "marketing manager" in text or "community manager" in text:
            score += 3
        if "founder" in text and ("agencia" in text or "agency" in text):
            score += 2

        return score

    def select_best_linkedin_marketing_leads(self, linkedin_leads: List[Dict], limit: int = 1) -> List[Dict]:
        """
        Devuelve leads de LinkedIn del sector marketing priorizando perfiles sin señales de equipo tech.
        """
        min_score = 4
        max_results = max(limit, 1)

        # Regla 1: Debe tener señales de marketing sí o sí.
        marketing_only = [lead for lead in linkedin_leads if self._seems_marketing_profile(lead)]

        # Regla 2: Excluir perfiles no objetivo y con señales tech internas.
        strict_pool = [
            lead for lead in marketing_only
            if not self._has_tech_team_signals(lead) and not self._has_non_target_signals(lead)
        ]

        # Regla 3: Score mínimo; si no cumple, no se agrega ningún lead.
        scored = []
        for lead in strict_pool:
            score = self._strict_marketing_score(lead)
            if score >= min_score:
                enriched = dict(lead)
                enriched["strict_score"] = score
                scored.append(enriched)

        scored.sort(key=lambda lead: lead.get("strict_score", 0), reverse=True)

        if max_results == 1 and scored:
            max_score = scored[0].get("strict_score", 0)
            top_band = [lead for lead in scored if lead.get("strict_score", 0) >= max_score - 1]
            selected = [random.choice(top_band)]
        else:
            selected = scored[:max_results]

        if selected:
            logger.info(
                "✅ Seleccionados %s lead(s) estrictos de LinkedIn marketing (score mínimo: %s)",
                len(selected),
                min_score,
            )
        else:
            logger.warning(
                "⚠️ No hubo leads que cumplan criterio estricto (marketing + sin tech + score >= %s)",
                min_score,
            )

        return selected
    
    def search_pymes_directory(self,
                              industry: str = "marketing",
                              region: str = "latam",
                              limit: int = 20) -> List[Dict]:
        """
        Busca PyMEs de marketing en directorios públicos.
        
        Args:
            industry: "marketing", "publicidad", "comunicación"
            region: "latam" o "spain"
            limit: Máximo de resultados
        
        Returns:
            [{"nombre_empresa": "Marketing Pro SRL", "contacto": "Juan García", "email": "info@..."}]
        """
        logger.info(f"🏢 Buscando PyMEs: {industry} ({region})")
        
        results = []
        
        try:
            # Búsqueda en directorios públicos (Argentina.gob.ar, registros comerciales, etc)
            # Simulado para demostración
            
            test_pymes = [
                {"nombre_empresa": "Marketing Pro Argentina SRL", "contacto": "Roberto Silva", "email": "ventas@marketingpro.com.ar"},
                {"nombre_empresa": "Agencia Digital Chile", "contacto": "Francisca González", "email": "contacto@agenciadigital.cl"},
                {"nombre_empresa": "Social Media España", "contacto": "Pablo López", "email": "info@socialmediaes.es"},
            ]
            
            results = test_pymes[:limit]
            logger.info(f"✅ Encontradas {len(results)} PyMEs")
            
        except Exception as e:
            logger.error(f"❌ Error buscando PyMEs: {e}")
        
        return results
    
    def search_instagram_marketing_profiles(self,
                                           hashtags: List[str] = None,
                                           region: str = "latam",
                                           limit: int = 20) -> List[Dict]:
        """
        Busca perfiles de marketing en Instagram (desde biografías públicas).
        
        Args:
            hashtags: ["#agenciamarketing", "#communitymanager", "#socialmedia"]
            region: "latam" o "spain"
            limit: Máximo de resultados
        
        Returns:
            [{"usuario_instagram": "@juanmarketing", "nombre": "Juan García", "email": "juan@..."}]
        """
        logger.info(f"📸 Buscando en Instagram: {hashtags} ({region})")
        
        if hashtags is None:
            hashtags = ["#agenciamarketing", "#marketingdigital", "#communitymanager"]
        
        results = []
        
        try:
            # Búsqueda simulada (Instagram requiere autenticación)
            # En producción, usar Instagram Graph API
            
            test_profiles = [
                {"usuario_instagram": "@juanmarketing_ar", "nombre": "Juan Pérez", "email": "juan@agenciamarketing.com.ar"},
                {"usuario_instagram": "@mariasocialmedia", "nombre": "María López", "email": "maria@socialmedia.es"},
                {"usuario_instagram": "@carlosdigital_mx", "nombre": "Carlos Rodríguez", "email": "carlos@agenciadigital.mx"},
            ]
            
            results = test_profiles[:limit]
            logger.info(f"✅ Encontrados {len(results)} perfiles en Instagram")
            
        except Exception as e:
            logger.error(f"❌ Error buscando Instagram: {e}")
        
        return results
    
    def search_email_from_domain(self,
                                domain: str,
                                contact_name: str = "") -> Optional[str]:
        """
        Intenta encontrar email de una empresa desde su dominio.
        
        Args:
            domain: "example.com"
            contact_name: "Juan García" (opcional)
        
        Returns:
            email encontrado o None
        """
        logger.info(f"📧 Buscando email en {domain}")
        
        try:
            # Intenta patrones comunes
            common_patterns = [
                f"hola@{domain}",
                f"contacto@{domain}",
                f"info@{domain}",
                f"ventas@{domain}",
                f"hello@{domain}",
            ]
            
            # En producción, validar con verificación SMTP
            # Por ahora, retorna el primero válido
            
            for email in common_patterns:
                logger.debug(f"Trying: {email}")
                # Aquí iría validación real
                return email
            
        except Exception as e:
            logger.error(f"❌ Error buscando email: {e}")
        
        return None
    
    def consolidate_leads(self, 
                         linkedin_leads: List[Dict],
                         pymes_leads: List[Dict],
                         instagram_leads: List[Dict]) -> List[Dict]:
        """
        Consolida resultados de múltiples fuentes y elimina duplicados.
        
        Args:
            linkedin_leads, pymes_leads, instagram_leads: resultados de cada fuente
        
        Returns:
            Lista única consolidada [{"nombre": "...", "email": "...", "fuente": "..."}]
        """
        logger.info("🔗 Consolidando leads de múltiples fuentes...")
        
        all_leads = []
        seen_emails = set()
        
        # Agregar LinkedIn
        for lead in linkedin_leads:
            email = lead.get("email", "").lower()
            if email and email not in seen_emails:
                all_leads.append({
                    "nombre": lead.get("nombre", "N/A"),
                    "email": email,
                    "fuente": "LinkedIn",
                    "url": lead.get("linkedin"),
                    "empresa": lead.get("empresa"),
                    "cargo": lead.get("cargo"),
                    "bio": lead.get("bio"),
                })
                seen_emails.add(email)
        
        # Agregar PyMEs
        for lead in pymes_leads:
            email = lead.get("email", "").lower()
            if email and email not in seen_emails:
                all_leads.append({
                    "nombre": f"{lead.get('contacto', 'N/A')} ({lead.get('nombre_empresa', 'N/A')})",
                    "email": email,
                    "fuente": "PyMEs",
                    "empresa": lead.get("nombre_empresa")
                })
                seen_emails.add(email)
        
        # Agregar Instagram
        for lead in instagram_leads:
            email = lead.get("email", "").lower()
            if email and email not in seen_emails:
                all_leads.append({
                    "nombre": lead.get("nombre", "N/A"),
                    "email": email,
                    "fuente": "Instagram",
                    "instagram": lead.get("usuario_instagram")
                })
                seen_emails.add(email)
        
        logger.info(f"✅ Total consolidado: {len(all_leads)} leads únicos")
        return all_leads
    
    def to_lead_model(self, consolidated_lead: Dict) -> Lead:
        """Convierte lead consolidado al modelo Lead para Sheets."""
        profile_bits = []
        if consolidated_lead.get("cargo"):
            profile_bits.append(f"Cargo: {consolidated_lead.get('cargo')}")
        if consolidated_lead.get("bio"):
            profile_bits.append(f"Bio: {consolidated_lead.get('bio')}")
        if consolidated_lead.get("strict_score") is not None:
            profile_bits.append(f"StrictScore: {consolidated_lead.get('strict_score')}")

        return Lead(
            business_name=consolidated_lead.get("empresa", consolidated_lead.get("nombre", "N/A")),
            contact_name=consolidated_lead.get("nombre", "N/A"),
            email=consolidated_lead.get("email", ""),
            linkedin_url=consolidated_lead.get("url"),
            industry="Marketing",
            track=TrackType.MARKETING,
            source=consolidated_lead.get("fuente", ""),
            notes=(
                f"Fuente: {consolidated_lead.get('fuente')} | "
                f"{consolidated_lead.get('url', '')} {consolidated_lead.get('instagram', '')} "
                f"{' | '.join(profile_bits)}"
            ).strip()
        )
