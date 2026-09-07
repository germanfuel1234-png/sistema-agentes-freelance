"""
Agent 1 - Buscador de Leads (Actualizado)
Encuentra agencias de marketing, freelancers sin developer propio.
Agrega filas nuevas a leads_tracking.
"""
import logging
from typing import Any, List

from agents.base_agent import BaseAgent
from core.models import Lead, TrackType
from core.sheets_client import SheetsClient
from services.search_service import SearchService

logger = logging.getLogger(__name__)


class Agent1SearchLeads(BaseAgent):
    """
    Busca nuevos leads de agencias/freelancers de marketing o PyMEs.
    Usa APIs o scraping según configuración.
    """
    
    def __init__(self, sheets_client: SheetsClient, 
                 api_key: str = None,
                 engine_id: str = None):
        super().__init__("agent_1_search_leads")
        self.sheets = sheets_client
        self.search_service = SearchService(api_key, engine_id)
    
    async def execute(self, 
                     search_type: str = "marketing",
                     country: str = "Argentina",
                     limit: int = 10,
                     **kwargs) -> tuple[Any, bool]:
        """
        Busca leads nuevos.
        
        Args:
            search_type: "marketing" o "pymes"
            country: País donde buscar
            limit: Cantidad de leads a buscar
        
        Returns:
            (Lista de leads encontrados, False) - no requiere aprobación
        """
        logger.info(f"🔎 {self.name}: buscando {search_type} leads...")
        
        try:
            # Búsqueda según tipo
            if search_type == "marketing":
                found_leads = self.search_service.search_marketing_agencies(
                    country, limit
                )
            else:  # pymes
                found_leads = self.search_service.search_pymes(
                    industry=kwargs.get("industry", "restaurante"),
                    city=kwargs.get("city", "Buenos Aires"),
                    limit=limit
                )
            
            # Obtiene leads existentes para validar duplicados
            existing_leads = self.sheets.get_all_leads()
            existing_emails = {l.email.lower() for l in existing_leads if l.email}
            
            # Filtra duplicados y valida
            new_leads = []
            for lead in found_leads:
                if lead.email:
                    if lead.email.lower() not in existing_emails:
                        # Valida que sea lead válido
                        if self.search_service.validate_lead(lead):
                            new_leads.append(lead)
                            existing_emails.add(lead.email.lower())
            
            # Agrega a Sheet
            for lead in new_leads:
                self.sheets.add_lead(lead)
                logger.info(f"✅ Lead añadido: {lead.business_name} ({lead.email})")
            
            logger.info(f"✅ {len(new_leads)} leads nuevos añadidos")
            return new_leads, False
        
        except Exception as e:
            logger.error(f"❌ Error en Agent 1: {e}")
            raise
