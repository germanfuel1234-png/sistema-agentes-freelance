"""
Agent 1B - Advanced Lead Search
Busca leads en LinkedIn, PyMEs, Instagram
Extrae: Nombre + Email
Agrega automáticamente a Google Sheets
"""
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

from services.advanced_search_service import AdvancedSearchService
from core.models import Lead, TrackType
from agents.base_agent import BaseAgent
from core.sheets_client import SheetsClient
from core.base_enricher import BaseEnricher, NoopEnricher
from core.fallback_enricher import FallbackEnricher
from core.hunter_client import HunterEnricher
from core.salesql_client import SalesQLEnricher
from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class AdvancedSearchResult:
    """Resultado de búsqueda avanzada."""
    leads_found: List[Lead]
    sources_searched: List[str]
    total_unique: int
    duplicates_removed: int
    filtered_missing_email: int = 0
    filtered_existing_email: int = 0


class Agent1BAdvancedSearch(BaseAgent):
    """
    Agent que busca leads en múltiples fuentes:
    - LinkedIn (perfiles, empresas)
    - PyMEs (directorios)
    - Instagram (perfiles marketing)
    
    Extrae SOLO: nombre + email
    Agrega automáticamente a Sheets (sin aprobación)
    """
    
    def __init__(self, sheets_client: SheetsClient, enricher: Optional[BaseEnricher] = None):
        super().__init__(name="agent_1b_advanced_search")
        self.search_service = AdvancedSearchService()
        self.sheets = sheets_client
        if enricher is not None:
            self.enricher = enricher
        else:
            self.enricher = self._build_default_enricher_chain()

    @staticmethod
    def _build_default_enricher_chain() -> BaseEnricher:
        """Construye cadena de enriquecimiento por prioridad de crédito/calidad.

        Orden: SalesQL primero (funciona a partir de la URL de LinkedIn, que
        es la fuente principal de este agente) y Hunter como respaldo
        (funciona a partir del dominio de la empresa, útil cuando SalesQL no
        encuentra nada o el lead no trae LinkedIn).
        """
        providers: List[BaseEnricher] = []

        if settings.salesql_api_key:
            providers.append(
                SalesQLEnricher(
                    api_key=settings.salesql_api_key,
                    endpoint=settings.salesql_endpoint,
                )
            )

        if settings.hunter_api_key:
            providers.append(
                HunterEnricher(
                    api_key=settings.hunter_api_key,
                    endpoint=settings.hunter_endpoint,
                )
            )

        if not providers:
            logger.info("ℹ️ Sin proveedores de enriquecimiento configurados. Usando NoopEnricher")
            return NoopEnricher()

        if len(providers) == 1:
            return providers[0]

        logger.info("🔗 FallbackEnricher activo con %s proveedor(es)", len(providers))
        return FallbackEnricher(providers)
    
    async def execute(self) -> Tuple[AdvancedSearchResult, bool]:
        """
        Ejecuta búsqueda en todas las fuentes.
        
        Retorna:
            (AdvancedSearchResult, requires_approval=False)
            No requiere aprobación - se agrega automáticamente a Sheets
        """
        logger.info("🚀 Agent 1B: MODO ESTRICTO (1 lead LinkedIn marketing, sin equipo tech, score mínimo)")
        
        try:
            # 1. Buscar en LinkedIn
            logger.info("📱 Buscando en LinkedIn...")
            linkedin_results = self.search_service.search_linkedin_professionals(
                keywords="marketing manager, community manager",
                region="latam",
                limit=15
            )

            # 2. Seleccionar SOLO 1 lead de marketing, priorizando sin señales de equipo tech
            linkedin_results = self.search_service.select_best_linkedin_marketing_leads(
                linkedin_results,
                limit=1,
            )

            # 2.1 Enriquecer candidatos antes de exigir email final
            enriched_linkedin = []
            for raw_lead in linkedin_results:
                candidate = self.search_service.enrich_lead_with_website_domain(
                    raw_lead,
                    region="latam",
                )
                enriched = await self.enricher.enrich_lead(candidate)
                enriched_linkedin.append(enriched)
            linkedin_results = enriched_linkedin

            if not linkedin_results:
                logger.info("ℹ️ Modo estricto: no se agregó ningún lead porque ninguno cumplió todos los criterios")

            # 3. Consolidar y eliminar duplicados (solo LinkedIn en esta modalidad)
            consolidated = self.search_service.consolidate_leads(
                linkedin_results,
                [],
                []
            )
            
            # 4. Convertir a modelo Lead
            leads_to_add = []
            for consolidated_lead in consolidated:
                lead = self.search_service.to_lead_model(consolidated_lead)
                leads_to_add.append(lead)

            # 4.1 Filtro duro final: email válido + no duplicado por email
            existing_emails = {
                l.email.strip().lower()
                for l in self.sheets.get_all_leads()
                if l.email and "@" in l.email
            }

            filtered_missing_email = sum(
                1 for lead in leads_to_add
                if not (lead.email and "@" in lead.email)
            )
            filtered_existing_email = sum(
                1 for lead in leads_to_add
                if lead.email and lead.email.strip().lower() in existing_emails
            )

            leads_to_add = [
                lead for lead in leads_to_add
                if lead.email and lead.email.strip().lower() not in existing_emails
            ]
            
            # 5. Agregar a Sheets AUTOMÁTICAMENTE
            logger.info(f"💾 Agregando {len(leads_to_add)} leads a Sheets...")
            added_count = 0
            for lead in leads_to_add:
                try:
                    self.sheets.add_lead(lead)
                    added_count += 1
                except Exception as e:
                    logger.warning(f"⚠️ No se pudo agregar lead {lead.email}: {e}")
            
            result = AdvancedSearchResult(
                leads_found=leads_to_add,
                sources_searched=["LinkedIn"],
                total_unique=len(leads_to_add),
                duplicates_removed=filtered_existing_email,
                filtered_missing_email=filtered_missing_email,
                filtered_existing_email=filtered_existing_email,
            )
            
            logger.info(f"""
✅ Agent 1B Completado:
   • LinkedIn: {len(linkedin_results)} perfiles
   • Total ÚNICO agregado a Sheets: {added_count}
    • Descartados por email faltante: {result.filtered_missing_email}
    • Descartados por duplicado: {result.filtered_existing_email}
            """)

            if added_count == 0:
                logger.info("ℹ️ No se agregó un nuevo lead: todos los candidatos ya existían o no tenían email utilizable")
            
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
