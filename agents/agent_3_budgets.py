"""
Agent 3 - Armador de Presupuestos (Actualizado)
Toma brief de cliente, arma propuesta con Gemini, espera tu ok.
"""
import logging
from typing import Any

from agents.base_agent import BaseAgent
from core.models import Budget, BudgetStatus
from core.sheets_client import SheetsClient
from services.gemini_service import GeminiService

logger = logging.getLogger(__name__)


class Agent3BudgetBuilder(BaseAgent):
    """
    Arma presupuestos personalizados para leads que respondieron con proyecto.
    Usa Gemini para generar propuestas inteligentes.
    """
    
    def __init__(self, sheets_client: SheetsClient,
                 gemini_service: GeminiService = None):
        super().__init__("agent_3_budget_builder")
        self.sheets = sheets_client
        self.gemini = gemini_service
    
    async def execute(self,
                     client_name: str,
                     project_description: str,
                     **kwargs) -> tuple[Any, bool]:
        """
        Arma presupuesto para un cliente.
        
        Args:
            client_name: Nombre del cliente
            project_description: Descripción del proyecto
        
        Returns:
            (Budget objeto, True) - REQUIERE APROBACIÓN del monto
        """
        logger.info(f"💰 {self.name}: armando presupuesto para {client_name}...")
        
        try:
            # Obtiene precios base
            prices = self.sheets.get_all_prices()
            
            # Intenta calcular presupuesto
            base_price = self._calculate_base_price(project_description, prices)
            adjustments = self._calculate_adjustments(project_description)
            total_price = base_price + adjustments
            
            # Genera propuesta con Gemini si está disponible
            if self.gemini:
                proposal_text = self.gemini.generate_budget_proposal(
                    client_name, project_description, total_price
                )
            else:
                proposal_text = f"<h2>Propuesta para {client_name}</h2><p>{project_description}</p>"
            
            budget = Budget(
                client_name=client_name,
                project_description=project_description,
                project_scope=self._generate_scope(project_description),
                base_price_ars=base_price,
                adjustments_ars=adjustments,
                total_price_ars=total_price,
                estimated_days=self._estimate_days(project_description),
                status=BudgetStatus.DRAFT,
                proposal_text=proposal_text,
            )
            
            logger.info(f"📊 Presupuesto generado: ${budget.total_price_ars:,.0f} ARS")
            
            return budget, True  # ✓ REQUIERE APROBACIÓN del monto
        
        except Exception as e:
            logger.error(f"❌ Error en Agent 3: {e}")
            raise
    
    async def on_approved(self, output: Any) -> None:
        """
        Usuario aprobó el monto. Guarda en la Sheet.
        """
        budget: Budget = output
        logger.info(f"✅ Presupuesto aprobado. Guardando en Sheet...")
        
        try:
            self.sheets.add_budget(budget)
            logger.info(f"📋 Presupuesto guardado: {budget.client_name}")
        except Exception as e:
            logger.error(f"❌ Error guardando presupuesto: {e}")
    
    def _calculate_base_price(self, description: str, prices) -> float:
        """Calcula precio base según descripción."""
        desc_lower = description.lower()
        
        # Mapeo simple
        if "landing" in desc_lower or "lading" in desc_lower:
            for p in prices:
                if "landing" in p.service.lower():
                    return p.base_price_ars
            return 100000
        
        elif "ecommerce" in desc_lower or "tienda" in desc_lower:
            for p in prices:
                if "ecommerce" in p.service.lower():
                    return p.base_price_ars
            return 530000
        
        elif "app" in desc_lower or "sistema" in desc_lower:
            for p in prices:
                if "app" in p.service.lower() or "sistema" in p.service.lower():
                    return p.base_price_ars
            return 500000
        
        else:  # Web corporativa default
            for p in prices:
                if "corporativa" in p.service.lower():
                    return p.base_price_ars
            return 400000
    
    def _calculate_adjustments(self, description: str) -> float:
        """Calcula ajustes por complejidad."""
        adjustments = 0
        desc_lower = description.lower()
        
        # Adicionales
        if "crm" in desc_lower:
            adjustments += 30000
        if "pagos" in desc_lower or "payment" in desc_lower:
            adjustments += 25000
        if "integracion" in desc_lower or "api" in desc_lower:
            adjustments += 20000
        if "urgente" in desc_lower or "rapido" in desc_lower:
            adjustments += 15000
        
        return adjustments
    
    def _generate_scope(self, description: str) -> str:
        """Genera resumen del alcance."""
        return f"Desarrollo completo del proyecto: {description}"
    
    def _estimate_days(self, description: str) -> int:
        """Estima días de desarrollo."""
        desc_lower = description.lower()
        
        if "ecommerce" in desc_lower:
            return 21
        elif "app" in desc_lower or "sistema" in desc_lower:
            return 21
        elif "landing" in desc_lower or "lading" in desc_lower:
            return 7
        else:
            return 14
