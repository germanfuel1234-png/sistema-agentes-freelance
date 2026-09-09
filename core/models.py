"""
Modelos de datos compartidos entre agentes.
Basados en la estructura de Google Sheets.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class TrackType(str, Enum):
    """Tipo de lead (pyme o agencia)."""
    PYME = "PyME"
    MARKETING = "Marketing"


class SendStatus(str, Enum):
    """Estado de envío de mail."""
    PENDING = "Pendiente"
    SENT = "Enviado"
    BOUNCED = "Rebotó"
    REPLIED = "Respondió"


class BudgetStatus(str, Enum):
    """Estado de un presupuesto."""
    DRAFT = "Borrador"
    SENT = "Enviado"
    ACCEPTED = "Aceptado"
    REJECTED = "Rechazado"
    NO_RESPONSE = "Sin respuesta"


@dataclass
class Lead:
    """Representa un lead en la planilla leads_tracking."""
    
    # Identifiers
    id: Optional[str] = None  # Row number or unique ID
    
    # Info básica
    business_name: str = ""  # Negocio/Agencia
    contact_name: str = ""  # Nombre contacto
    track: TrackType = TrackType.MARKETING
    industry: str = ""  # Rubro
    city: str = ""  # Ciudad
    country: str = "Argentina"
    
    # Contact
    email: str = ""
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    website: Optional[str] = None
    
    # Tracking
    send_date: Optional[datetime] = None
    send_status: SendStatus = SendStatus.PENDING
    subject_used: str = ""
    result: str = ""  # Notas sobre resultado
    
    # Follow-ups
    followup_1_date: Optional[datetime] = None
    followup_2_date: Optional[datetime] = None
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    notes: str = ""
    source: str = ""  # Dónde lo encontramos (LinkedIn, Google Maps, etc.)
    
    def is_pending(self) -> bool:
        """Retorna True si el lead no ha recibido mail aún."""
        return self.send_status == SendStatus.PENDING
    
    def to_sheet_row(self) -> List:
        """Convierte a fila para escribir en Google Sheets.

        Orden real de columnas en la pestaña leads_tracking (A a L):
        A: Fecha envio | B: Negocio/Agencia | C: Track (PyME/Marketing) |
        D: Rubro | E: Ciudad | F: Contacto | G: Mail o IG | H: Asunto usado |
        I: Respondio (Si/No) | J: Fecha follow-up 1 | K: Fecha follow-up 2 |
        L: Resultado

        La columna M (Enviado?) NO se escribe nunca: es una formula viva en
        la planilla que se calcula sola a partir de la columna A.
        """
        respondio = ""
        if self.send_status == SendStatus.REPLIED:
            respondio = "Sí"
        elif self.send_status in (SendStatus.SENT, SendStatus.BOUNCED):
            respondio = "No"

        return [
            self.send_date.strftime("%d/%m/%Y") if self.send_date else "",  # A: Fecha envio
            self.business_name or "",                                       # B: Negocio/Agencia
            self.track.value,                                               # C: Track
            self.industry or "",                                            # D: Rubro
            self.city or "",                                                # E: Ciudad
            self.contact_name or "",                                        # F: Contacto
            self.email or "",                                               # G: Mail o IG
            self.subject_used or "",                                        # H: Asunto usado
            respondio,                                                      # I: Respondio (Si/No)
            "",                                                             # J: Fecha follow-up 1
            "",                                                             # K: Fecha follow-up 2
            self.result or "",                                              # L: Resultado
        ]


@dataclass
class Email:
    """Plantilla de email para envío."""
    
    to: str
    subject: str
    body: str
    html_body: Optional[str] = None
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    
    # Tracking
    lead_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    approved_by: Optional[str] = None
    sent_at: Optional[datetime] = None
    message_id: Optional[str] = None  # ID del mail en Gmail


@dataclass
class Price:
    """Precio base de un servicio."""
    
    service: str  # Landing, Web Corporativa, E-Commerce, etc.
    base_price_ars: float
    description: str = ""
    estimated_days: int = 0
    
    def to_sheet_row(self) -> List:
        """Orden real de la pestaña precios_base: Servicio | Precio base (ARS) | Notas."""
        return [
            self.service,
            self.base_price_ars,
            self.description,
        ]


@dataclass
class Budget:
    """Presupuesto personalizado para un lead."""
    
    # Identifiers
    id: Optional[str] = None
    lead_id: Optional[str] = None
    
    # Basic
    client_name: str = ""
    project_description: str = ""
    project_scope: str = ""  # Detalles del alcance
    
    # Pricing
    base_price_ars: float = 0.0
    adjustments_ars: float = 0.0  # Complejidad, urgencia, etc.
    total_price_ars: float = 0.0
    currency: str = "ARS"
    
    # Delivery
    estimated_days: int = 0
    payment_terms: str = "50% adelanto, 50% a entrega"
    
    # Status
    status: BudgetStatus = BudgetStatus.DRAFT
    sent_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    
    # Text
    proposal_text: str = ""  # HTML o plain text generado por Gemini
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    notes: str = ""
    approved_by: Optional[str] = None
    
    def to_sheet_row(self) -> List:
        return [
            self.created_at.isoformat() if self.created_at else "",
            self.client_name,
            self.project_description,
            self.project_scope,
            self.total_price_ars,
            self.currency,
            self.status.value,
            self.notes,
        ]


@dataclass
class WebStudy:
    """Resultado del estudio de la web propia."""
    
    studied_at: datetime = field(default_factory=datetime.now)
    
    # Services
    services: List[Price] = field(default_factory=list)
    
    # Positioning
    target_industries: List[str] = field(default_factory=list)
    value_proposition: str = ""
    portfolio_highlights: List[str] = field(default_factory=list)
    
    # Notes for Agent 1
    notes_for_lead_search: str = ""
    
    def get_price_for_service(self, service_name: str) -> Optional[float]:
        """Obtiene el precio base para un servicio específico."""
        for price in self.services:
            if service_name.lower() in price.service.lower():
                return price.base_price_ars
        return None
