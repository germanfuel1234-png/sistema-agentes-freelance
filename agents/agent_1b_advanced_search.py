"""
Agent 1B - Advanced Lead Search
Busca leads en LinkedIn, PyMEs, Instagram
Extrae: Nombre + Email
Agrega automáticamente a Google Sheets
"""
import logging
from dataclasses import dataclass
from typing import List, Tuple

from services.advanced_search_service import AdvancedSearchService
from core.models import Lead, TrackType
from agents.base_agent import BaseAgent
from core.sheets_client import SheetsClient

logger = logging.getLogger(__name__)


@dataclass
class AdvancedSearchResult:
    """Resultado de búsqueda avanzada."""
    leads_found: List[Lead]
    sources_searched: List[str]
    total_unique: int
    duplicates_removed: int


class Agent1BAdvancedSearch(BaseAgent):
    """
    Agent que busca leads en múltiples fuentes:
    - LinkedIn (perfiles, empresas)
    - PyMEs (directorios)
    - Instagram (perfiles marketing)
    
    Extrae SOLO: nombre + email
    Agrega automáticamente a Sheets (sin aprobación)
    """
    
    def __init__(self, sheets_client: SheetsClient):
        super().__init__(name="agent_1b_advanced_search")
        self.search_service = AdvancedSearchService()
        self.sheets = sheets_client
    
    async def execute(self) -> Tuple[AdvancedSearchResult, bool]:
        """
        Ejecuta búsqueda en todas las fuentes.
        
        Retorna:
            (AdvancedSearchResult, requires_approval=False)
            No requiere aprobación - se agrega automáticamente a Sheets
        """
        logger.info("🚀 Agent 1B: Iniciando búsqueda avanzada multi-fuente")
        
        try:
            # 1. Buscar en LinkedIn
            logger.info("📱 Buscando en LinkedIn...")
            linkedin_results = self.search_service.search_linkedin_professionals(
                keywords="marketing manager, community manager",
                region="latam",
                limit=15
            )
            linkedin_results += self.search_service.search_linkedin_professionals(
                keywords="agencia marketing, publicidad digital",
                region="spain",
                limit=10
            )
            
            # 2. Buscar PyMEs
            logger.info("🏢 Buscando PyMEs...")
            pymes_results = self.search_service.search_pymes_directory(
                industry="marketing",
                region="latam",
                limit=15
            )
            pymes_results += self.search_service.search_pymes_directory(
                industry="marketing",
                region="spain",
                limit=10
            )
            
            # 3. Buscar en Instagram
            logger.info("📸 Buscando en Instagram...")
            instagram_results = self.search_service.search_instagram_marketing_profiles(
                hashtags=["#agenciamarketing", "#marketingdigital", "#communitymanager"],
                region="latam",
                limit=15
            )
            instagram_results += self.search_service.search_instagram_marketing_profiles(
                hashtags=["#agenciamarketing", "#marketingagency", "#socialmedia"],
                region="spain",
                limit=10
            )
            
            # 4. Consolidar y eliminar duplicados
            consolidated = self.search_service.consolidate_leads(
                linkedin_results,
                pymes_results,
                instagram_results
            )
            
            # 5. Convertir a modelo Lead
            leads_to_add = []
            for consolidated_lead in consolidated:
                lead = self.search_service.to_lead_model(consolidated_lead)
                leads_to_add.append(lead)
            
            # 6. Agregar a Sheets AUTOMÁTICAMENTE
            logger.info(f"💾 Agregando {len(leads_to_add)} leads a Sheets...")
            added_count = 0
            for lead in leads_to_add:
                try:
                    self.sheets.add_lead(lead)
                    added_count += 1
                except Exception as e:
                    logger.warning(f"⚠️ No se pudo agregar lead {lead.contact_email}: {e}")
            
            result = AdvancedSearchResult(
                leads_found=leads_to_add,
                sources_searched=["LinkedIn", "PyMEs", "Instagram"],
                total_unique=len(leads_to_add),
                duplicates_removed=len(linkedin_results) + len(pymes_results) + len(instagram_results) - len(leads_to_add)
            )
            
            logger.info(f"""
✅ Agent 1B Completado:
   • LinkedIn: {len(linkedin_results)} perfiles
   • PyMEs: {len(pymes_results)} empresas
   • Instagram: {len(instagram_results)} perfiles
   • Total ÚNICO agregado a Sheets: {added_count}
   • Duplicados removidos: {result.duplicates_removed}
            """)
            
            # NO requiere aprobación - ya está en Sheets
            return (result, False)
        
        except Exception as e:
            logger.error(f"❌ Error en Agent 1B: {e}", exc_info=True)
            return (AdvancedSearchResult([], [], 0, 0), False)
    
    async def on_approved(self):
        """
        No se ejecuta - esta búsqueda es automática.
        Los leads ya fueron agregados a Sheets en execute().
        """
        logger.info("ℹ️ Agent 1B no requiere aprobación")
        pass
