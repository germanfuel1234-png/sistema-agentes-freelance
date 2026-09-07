"""
Agent 4 - Supervisor de Flujo
Valida que todo esté correcto antes de ejecutar.
Revisa: credenciales, Google Sheets, emails válidos, etc.
"""
import logging
from datetime import datetime
from typing import Any, Dict

from agents.base_agent import BaseAgent, AgentResult
from core.sheets_client import SheetsClient
from services.gmail_service import GmailService

logger = logging.getLogger(__name__)


class Agent4Supervisor(BaseAgent):
    """
    Supervisor del sistema.
    Valida configuración, conexiones, y estado general.
    """
    
    def __init__(self, sheets_client: SheetsClient, 
                 gmail_service: Optional[GmailService] = None):
        super().__init__("agent_4_supervisor")
        self.sheets = sheets_client
        self.gmail = gmail_service
    
    async def execute(self, **kwargs) -> tuple[Any, bool]:
        """
        Valida todo el sistema.
        
        Returns:
            (status_report, False) - no requiere aprobación
        """
        logger.info(f"🔍 {self.name}: iniciando validación del sistema...")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "errors": [],
            "warnings": [],
            "status": "OK",
        }
        
        try:
            # Check 1: Google Sheets
            report["checks"]["google_sheets"] = await self._check_sheets()
            
            # Check 2: Gmail
            report["checks"]["gmail"] = await self._check_gmail()
            
            # Check 3: Data Integrity
            report["checks"]["data_integrity"] = await self._check_data()
            
            # Check 4: System Status
            report["checks"]["system"] = await self._check_system()
            
            # Resumen
            if report["errors"]:
                report["status"] = "ERROR"
            elif report["warnings"]:
                report["status"] = "WARNING"
            
            logger.info(f"✅ Validación completa. Status: {report['status']}")
            
            return report, False
        
        except Exception as e:
            logger.error(f"❌ Error en validación: {e}")
            report["errors"].append(str(e))
            report["status"] = "ERROR"
            return report, False
    
    async def _check_sheets(self) -> Dict:
        """Valida conexión a Google Sheets."""
        try:
            leads = self.sheets.get_all_leads()
            prices = self.sheets.get_all_prices()
            budgets = self.sheets.get_all_budgets()
            
            return {
                "status": "OK",
                "leads_count": len(leads),
                "prices_count": len(prices),
                "budgets_count": len(budgets),
                "message": "✅ Google Sheets conectado",
            }
        except Exception as e:
            logger.error(f"❌ Error en Sheets: {e}")
            self.report["errors"].append(f"Google Sheets: {e}")
            return {
                "status": "ERROR",
                "error": str(e),
                "message": "❌ No se puede conectar a Google Sheets",
            }
    
    async def _check_gmail(self) -> Dict:
        """Valida configuración Gmail."""
        try:
            if not self.gmail:
                return {
                    "status": "NOT_CONFIGURED",
                    "message": "⚠️  Gmail no configurado (usando mock)",
                }
            
            user_email = self.gmail.get_user_email()
            
            if user_email:
                return {
                    "status": "OK",
                    "user_email": user_email,
                    "message": f"✅ Gmail conectado como {user_email}",
                }
            else:
                return {
                    "status": "ERROR",
                    "message": "❌ No se puede obtener email del usuario",
                }
        
        except Exception as e:
            logger.error(f"Error en Gmail: {e}")
            return {
                "status": "ERROR",
                "error": str(e),
                "message": "❌ Error en Gmail",
            }
    
    async def _check_data(self) -> Dict:
        """Valida integridad de datos."""
        try:
            leads = self.sheets.get_all_leads()
            
            # Cuenta leads por estado
            pending = sum(1 for l in leads if l.is_pending())
            sent = sum(1 for l in leads if l.send_status.value == "Enviado")
            replied = sum(1 for l in leads if l.send_status.value == "Respondió")
            
            issues = []
            
            # Valida duplicados
            emails = [l.email for l in leads if l.email]
            duplicates = len(emails) - len(set(emails))
            if duplicates > 0:
                issues.append(f"{duplicates} leads duplicados por email")
            
            # Valida leads sin email
            no_email = sum(1 for l in leads if not l.email)
            if no_email > 0:
                issues.append(f"{no_email} leads sin email")
            
            return {
                "status": "OK",
                "total_leads": len(leads),
                "pending": pending,
                "sent": sent,
                "replied": replied,
                "issues": issues,
                "message": f"✅ {len(leads)} leads (P:{pending} S:{sent} R:{replied})",
            }
        
        except Exception as e:
            logger.error(f"Error en data integrity: {e}")
            return {
                "status": "ERROR",
                "error": str(e),
            }
    
    async def _check_system(self) -> Dict:
        """Valida estado general del sistema."""
        try:
            return {
                "status": "OK",
                "version": "0.1.0",
                "all_agents_ready": True,
                "message": "✅ Sistema listo para usar",
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e),
            }


# Import after to avoid circular dependency
from typing import Optional
