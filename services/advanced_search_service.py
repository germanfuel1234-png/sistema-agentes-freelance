"""
Advanced Search Service - Búsqueda multi-fuente de leads (LinkedIn, PyMEs, Instagram)
Extrae: Nombre + Email
Objetivo: Agregar rápidamente a Google Sheets
"""
import logging
import re
from typing import Optional, List, Dict, Tuple
import requests
from bs4 import BeautifulSoup

from core.models import Lead, TrackType

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
            # Búsqueda simulada (en producción, usar LinkedIn API oficial o scraping avanzado)
            # Por ahora, genera leads de prueba realistas
            
            test_leads = [
                {"nombre": "Juan García López", "email": "juan.garcia@marketingagency.com", "linkedin": "linkedin.com/in/juangarcia"},
                {"nombre": "María Rodríguez", "email": "maria.r@agenciadigital.es", "linkedin": "linkedin.com/in/mariar"},
                {"nombre": "Carlos Mendez", "email": "carlos@socialmedia.mx", "linkedin": "linkedin.com/in/carlosmendez"},
            ]
            
            results = test_leads[:limit]
            logger.info(f"✅ Encontrados {len(results)} profesionales en LinkedIn")
            
        except Exception as e:
            logger.error(f"❌ Error buscando LinkedIn: {e}")
        
        return results
    
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
                    "url": lead.get("linkedin")
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
        return Lead(
            business_name=consolidated_lead.get("empresa", consolidated_lead.get("nombre", "N/A")),
            contact_name=consolidated_lead.get("nombre", "N/A"),
            email=consolidated_lead.get("email", ""),
            industry="Marketing",
            track=TrackType.MARKETING,
            notes=f"Fuente: {consolidated_lead.get('fuente')} | {consolidated_lead.get('url', '')} {consolidated_lead.get('instagram', '')}"
        )
