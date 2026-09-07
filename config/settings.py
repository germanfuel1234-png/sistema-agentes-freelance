"""
Configuración centralizada del sistema de agentes.
Carga variables de .env y expone constantes globales.
"""
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Configuración global del aplicación."""
    
    # Google Sheets
    google_sheet_id: str = "1hjwAUrKaCu53McleYaJZj99b65IoKHBVqIZ96qfvF1I"
    google_sheet_leads_range: str = "leads_tracking!A1:L1000"
    google_sheet_prices_range: str = "precios_base!A1:E100"
    google_sheet_budgets_range: str = "presupuestos!A1:H100"
    
    # Gmail OAuth2 (opcional - se cargan de credentials.json)
    gmail_client_id: Optional[str] = None
    gmail_client_secret: Optional[str] = None
    gmail_redirect_uri: str = "http://localhost:8000/callback"
    
    # Gemini API (opcional)
    gemini_api_key: Optional[str] = None
    
    # Search APIs (opcional)
    google_custom_search_api_key: Optional[str] = None
    google_custom_search_engine_id: Optional[str] = None
    
    # App
    debug: bool = True
    log_level: str = "INFO"
    app_port: int = 8000
    app_host: str = "0.0.0.0"
    
    # Limits
    daily_email_limit: int = 20
    leads_search_limit: int = 50
    
    # Your Info
    your_website_url: str = "https://germanrodriguez.ar"
    your_email: str = "rodriguezg.dev@gmail.com"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Instancia global
settings = Settings()  # type: ignore


# Rutas del proyecto
PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)
