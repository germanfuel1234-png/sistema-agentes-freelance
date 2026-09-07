"""
Clase base para todos los agentes.
Define la interfaz común y métodos compartidos.
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Estados posibles de un agente."""
    IDLE = "idle"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    ERROR = "error"
    COMPLETE = "complete"


@dataclass
class AgentResult:
    """Resultado estándar de ejecución de un agente."""
    
    agent_name: str
    status: AgentStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    output: Any = None  # El resultado principal
    error: Optional[str] = None
    requires_approval: bool = False
    approval_token: Optional[str] = None
    
    def duration_seconds(self) -> float:
        """Retorna duración en segundos."""
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds()


class BaseAgent(ABC):
    """
    Clase abstracta para todos los agentes.
    
    Patrón:
    1. Agent.run() inicia ejecución
    2. Agent.execute() hace el trabajo
    3. Si necesita aprobación, retorna AgentResult con requires_approval=True
    4. Si no, ejecuta directamente
    5. Agent.approve(token) permite al usuario confirmar y completar
    """
    
    def __init__(self, name: str):
        """
        Args:
            name: Identificador único del agente (ej: "agent_1_search_leads")
        """
        self.name = name
        self.status = AgentStatus.IDLE
        self.current_result: Optional[AgentResult] = None
        self.logger = logging.getLogger(f"agents.{name}")
    
    async def run(self, **kwargs) -> AgentResult:
        """
        Entrypoint público: inicia ejecución.
        
        Returns:
            AgentResult con estado y posible aprobación pendiente
        """
        self.status = AgentStatus.RUNNING
        result = AgentResult(
            agent_name=self.name,
            status=AgentStatus.RUNNING,
            started_at=datetime.now(),
        )
        
        try:
            # Ejecuta lógica del agente
            output, requires_approval = await self.execute(**kwargs)
            
            if requires_approval:
                result.status = AgentStatus.WAITING_APPROVAL
                result.requires_approval = True
                result.output = output
                # Token para identificar esta ejecución específica
                result.approval_token = self._generate_approval_token()
                self.status = AgentStatus.WAITING_APPROVAL
                self.logger.info(f"⏳ {self.name} esperando aprobación (token: {result.approval_token})")
            else:
                result.status = AgentStatus.COMPLETE
                result.output = output
                result.completed_at = datetime.now()
                self.status = AgentStatus.COMPLETE
                self.logger.info(f"✅ {self.name} completado sin aprobación")
        
        except Exception as e:
            self.logger.error(f"❌ Error en {self.name}: {e}", exc_info=True)
            result.status = AgentStatus.ERROR
            result.error = str(e)
            self.status = AgentStatus.ERROR
        
        self.current_result = result
        return result
    
    async def approve(self, approval_token: str) -> AgentResult:
        """
        Usuario aprueba la acción pendiente.
        
        Args:
            approval_token: Token del resultado que se aprueba
        
        Returns:
            AgentResult actualizado
        """
        if not self.current_result or self.current_result.approval_token != approval_token:
            raise ValueError("Token inválido o no hay ejecución pendiente")
        
        try:
            await self.on_approved(self.current_result.output)
            self.current_result.status = AgentStatus.COMPLETE
            self.current_result.completed_at = datetime.now()
            self.status = AgentStatus.COMPLETE
            self.logger.info(f"✅ {self.name} aprobado y ejecutado")
        except Exception as e:
            self.logger.error(f"❌ Error al ejecutar {self.name} tras aprobación: {e}")
            self.current_result.status = AgentStatus.ERROR
            self.current_result.error = str(e)
            self.status = AgentStatus.ERROR
        
        return self.current_result
    
    @abstractmethod
    async def execute(self, **kwargs) -> tuple[Any, bool]:
        """
        Ejecuta la lógica del agente.
        
        Returns:
            Tupla (output, requires_approval)
            - output: resultado principal
            - requires_approval: si necesita aprobación del usuario
        """
        pass
    
    async def on_approved(self, output: Any) -> None:
        """
        Hook: se ejecuta cuando usuario aprueba resultado.
        Por default no hace nada (para agentes sin aprobación).
        Subclases pueden sobrescribir.
        """
        pass
    
    def _generate_approval_token(self) -> str:
        """Genera token único para esta ejecución."""
        import uuid
        return str(uuid.uuid4())


# Import after to avoid circular dependency
from dataclasses import dataclass
from datetime import datetime
