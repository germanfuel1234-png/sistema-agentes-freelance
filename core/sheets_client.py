"""
Cliente para interactuar con Google Sheets.
Maneja lectura/escritura de leads, presupuestos, precios.
"""
import logging
from typing import List, Optional, Dict, Any
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config.settings import settings
from core.models import Lead, Budget, Price, SendStatus

logger = logging.getLogger(__name__)

# Scopes para Google Sheets API
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsClient:
    """Cliente para Google Sheets con métodos CRUD para leads, presupuestos, etc."""
    
    def __init__(self, credentials_file: str = "credentials.json", token_file: str = "token.json"):
        """
        Inicializa el cliente con OAuth2.
        
        Args:
            credentials_file: Archivo credentials.json descargado de Google Cloud
            token_file: Archivo de token persistente (se crea automáticamente)
        """
        self.sheet_id = settings.google_sheet_id
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.service = None
        self.creds = None
        self._authenticate()
    
    def _authenticate(self):
        """Autentica con Google Sheets API usando OAuth2."""
        try:
            # Intenta cargar token existente
            if Path(self.token_file).exists():
                self.creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
            
            # Si no hay token o está expirado, solicita nuevo
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES
                    )
                    self.creds = flow.run_local_server(port=0)
                
                # Guarda token para futuras ejecuciones
                with open(self.token_file, "w") as token:
                    token.write(self.creds.to_json())
            
            self.service = build("sheets", "v4", credentials=self.creds)
            logger.info("✅ Autenticado con Google Sheets API")
        
        except FileNotFoundError as e:
            logger.error(f"❌ Archivo de credenciales no encontrado: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error en autenticación: {e}")
            raise
    
    def read_range(self, range_name: str) -> List[List[str]]:
        """
        Lee un rango de la planilla.
        
        Args:
            range_name: Rango en formato "Sheet!A1:Z100"
        
        Returns:
            Lista de filas (cada fila es una lista de celdas)
        """
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range=range_name
            ).execute()
            return result.get("values", [])
        except HttpError as e:
            logger.error(f"❌ Error leyendo rango {range_name}: {e}")
            return []
    
    def write_range(self, range_name: str, values: List[List[str]], 
                   append: bool = False) -> bool:
        """
        Escribe/añade datos a un rango.
        
        Args:
            range_name: Rango en formato "Sheet!A1:Z100"
            values: Lista de filas para escribir
            append: Si True, añade al final. Si False, sobrescribe.
        
        Returns:
            True si tuvo éxito
        """
        try:
            body = {"values": values}
            if append:
                self.service.spreadsheets().values().append(
                    spreadsheetId=self.sheet_id,
                    range=range_name,
                    valueInputOption="RAW",
                    body=body
                ).execute()
            else:
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.sheet_id,
                    range=range_name,
                    valueInputOption="RAW",
                    body=body
                ).execute()
            logger.info(f"✅ Datos escritos en {range_name}")
            return True
        except HttpError as e:
            logger.error(f"❌ Error escribiendo en {range_name}: {e}")
            return False
    
    # ========== LEADS ==========
    
    def get_all_leads(self) -> List[Lead]:
        """Obtiene todos los leads de leads_tracking."""
        rows = self.read_range(settings.google_sheet_leads_range)
        if not rows or len(rows) < 2:
            return []
        
        leads = []
        headers = rows[0]
        
        for i, row in enumerate(rows[1:], start=2):
            try:
                lead = self._row_to_lead(row, headers, row_id=i)
                if lead:
                    leads.append(lead)
            except Exception as e:
                logger.warning(f"⚠️  Error parseando fila {i}: {e}")
        
        return leads
    
    def get_pending_leads(self) -> List[Lead]:
        """Obtiene solo leads con Enviado?=Pendiente."""
        all_leads = self.get_all_leads()
        return [l for l in all_leads if l.is_pending()]
    
    def add_lead(self, lead: Lead) -> bool:
        """Añade un nuevo lead a la planilla."""
        row = lead.to_sheet_row()
        return self.write_range(
            settings.google_sheet_leads_range,
            [row],
            append=True
        )
    
    def update_lead(self, lead: Lead, row_id: int) -> bool:
        """Actualiza un lead existente (requiere row_id)."""
        row = lead.to_sheet_row()
        range_name = f"leads_tracking!A{row_id}:L{row_id}"
        return self.write_range(range_name, [row], append=False)
    
    def _row_to_lead(self, row: List[str], headers: List[str], row_id: int) -> Optional[Lead]:
        """Convierte una fila a objeto Lead."""
        if len(row) < 6:  # Mínimo campos esperados
            return None
        
        try:
            return Lead(
                id=str(row_id),
                business_name=row[0] if len(row) > 0 else "",
                contact_name=row[1] if len(row) > 1 else "",
                track=TrackType(row[2]) if len(row) > 2 and row[2] else TrackType.MARKETING,
                industry=row[3] if len(row) > 3 else "",
                city=row[4] if len(row) > 4 else "",
                email=row[5] if len(row) > 5 else "",
                phone=row[6] if len(row) > 6 else None,
                send_date=self._parse_date(row[7]) if len(row) > 7 else None,
                send_status=SendStatus(row[8]) if len(row) > 8 and row[8] else SendStatus.PENDING,
                subject_used=row[9] if len(row) > 9 else "",
                result=row[10] if len(row) > 10 else "",
            )
        except Exception as e:
            logger.error(f"Error parseando lead: {e}")
            return None
    
    # ========== PRESUPUESTOS ==========
    
    def get_all_budgets(self) -> List[Budget]:
        """Obtiene todos los presupuestos."""
        rows = self.read_range(settings.google_sheet_budgets_range)
        if not rows or len(rows) < 2:
            return []
        
        budgets = []
        for i, row in enumerate(rows[1:], start=2):
            try:
                budget = self._row_to_budget(row, row_id=i)
                if budget:
                    budgets.append(budget)
            except Exception as e:
                logger.warning(f"⚠️  Error parseando presupuesto en fila {i}: {e}")
        
        return budgets
    
    def add_budget(self, budget: Budget) -> bool:
        """Añade un nuevo presupuesto."""
        row = budget.to_sheet_row()
        return self.write_range(
            settings.google_sheet_budgets_range,
            [row],
            append=True
        )
    
    def _row_to_budget(self, row: List[str], row_id: int) -> Optional[Budget]:
        """Convierte una fila a objeto Budget."""
        if len(row) < 6:
            return None
        
        try:
            return Budget(
                id=str(row_id),
                client_name=row[1] if len(row) > 1 else "",
                project_description=row[2] if len(row) > 2 else "",
                project_scope=row[3] if len(row) > 3 else "",
                total_price_ars=float(row[4]) if len(row) > 4 and row[4] else 0.0,
                currency=row[5] if len(row) > 5 else "ARS",
                status=BudgetStatus(row[6]) if len(row) > 6 and row[6] else BudgetStatus.DRAFT,
                notes=row[7] if len(row) > 7 else "",
            )
        except Exception as e:
            logger.error(f"Error parseando presupuesto: {e}")
            return None
    
    # ========== PRECIOS ==========
    
    def get_all_prices(self) -> List[Price]:
        """Obtiene tabla de precios base."""
        rows = self.read_range(settings.google_sheet_prices_range)
        if not rows or len(rows) < 2:
            return []
        
        prices = []
        for row in rows[1:]:
            try:
                if len(row) >= 2:
                    price = Price(
                        service=row[0],
                        base_price_ars=float(row[1]) if row[1] else 0.0,
                        description=row[2] if len(row) > 2 else "",
                        estimated_days=int(row[3]) if len(row) > 3 and row[3] else 0,
                    )
                    prices.append(price)
            except Exception as e:
                logger.warning(f"⚠️  Error parseando precio: {e}")
        
        return prices
    
    def update_prices(self, prices: List[Price]) -> bool:
        """Actualiza tabla de precios completa."""
        rows = [["Servicio", "Precio (ARS)", "Descripción", "Días"]]
        rows.extend([p.to_sheet_row() for p in prices])
        return self.write_range(settings.google_sheet_prices_range, rows, append=False)
    
    @staticmethod
    def _parse_date(date_str: str) -> Optional:
        """Intenta parsear fecha de string."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str)
        except:
            return None


# Import after to avoid circular imports
from pathlib import Path
from datetime import datetime
from core.models import TrackType
