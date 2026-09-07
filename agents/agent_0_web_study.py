"""
Agent 0 - Estudio de tu Web (Actualizado)
Lee germanrodriguez.ar, extrae servicios, precios y posicionamiento.
Actualiza la tabla precios_base de la Google Sheet.
"""
import logging
from datetime import datetime
from typing import Any

from agents.base_agent import BaseAgent
from core.models import WebStudy, Price
from core.sheets_client import SheetsClient
from services.web_scraper import WebScraper

logger = logging.getLogger(__name__)


class Agent0WebStudy(BaseAgent):
    """
    Agente que estudia la web propia (germanrodriguez.ar).
    Extrae precios y posicionamiento con scraping real.
    """
    
    def __init__(self, sheets_client: SheetsClient):
        super().__init__("agent_0_web_study")
        self.sheets = sheets_client
        self.scraper = WebScraper()
    
    async def execute(self, **kwargs) -> tuple[Any, bool]:
        """
        Estudia la web y actualiza precios en la Sheet.
        
        No requiere aprobación: es información que vos pedís,
        el agente solo extrae y actualiza la tabla de precios.
        """
        logger.info(f"🔍 {self.name}: iniciando estudio de web...")
        
        try:
            # Scraping real de germanrodriguez.ar
            scraped = self.scraper.scrape_germanrodriguez_ar()
            
            # Convierte a objetos Price
            services = [
                Price(
                    service=s["name"],
                    base_price_ars=s["price"],
                    description="",
                    estimated_days=7,
                )
                for s in scraped["services"]
            ]
            
            # Crea WebStudy
            study = WebStudy(
                studied_at=datetime.now(),
                services=services,
                target_industries=scraped["target_industries"],
                value_proposition=scraped["value_proposition"],
                notes_for_lead_search="Enfocarse en agencias sin developer interno",
            )
            
            # Actualiza tabla de precios en la Sheet
            self.sheets.update_prices(study.services)
            logger.info(f"✅ Tabla de precios actualizada ({len(services)} servicios)")
            
            return study, False  # No requiere aprobación
        
        except Exception as e:
            logger.error(f"❌ Error en Agent 0: {e}")
            raise
