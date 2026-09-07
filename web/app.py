"""
FastAPI App - Dashboard web para controlar los agentes (Actualizado)
Integra Gmail, Gemini, Web Scraper y Search Service.
"""
import logging
import os
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from config.settings import settings
from core.sheets_client import SheetsClient
from agents.agent_0_web_study import Agent0WebStudy
from agents.agent_1_search_leads import Agent1SearchLeads
from agents.agent_2_send_emails import Agent2SendEmails
from agents.agent_3_budgets import Agent3BudgetBuilder
from agents.agent_4_supervisor import Agent4Supervisor
from services.gmail_service import GmailService
from services.gemini_service import GeminiService
from web import routes

# Setup logging
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

# FastAPI App
app = FastAPI(
    title="Sistema Agentes Freelance",
    description="Dashboard para gestionar agentes de outreach y presupuestos",
    version="0.2.0"
)

# Inicializa servicios compartidos
try:
    sheets_client = SheetsClient()
    logger.info("✅ Google Sheets client inicializado")
except Exception as e:
    logger.error(f"❌ Error inicializando Sheets: {e}")
    sheets_client = None

# Gmail Service (opcional, fallback a mock)
gmail_service = None
try:
    if os.path.exists("credentials.json"):
        gmail_service = GmailService("credentials.json", "token_gmail.json")
        logger.info("✅ Gmail Service inicializado")
    else:
        logger.warning("⚠️  credentials.json no encontrado, Gmail en modo mock")
except Exception as e:
    logger.warning(f"⚠️  Gmail Service no disponible: {e}")

# Gemini Service (opcional, se configura con API key después)
gemini_service = None
gemini_api_key = os.getenv("GEMINI_API_KEY")
if gemini_api_key:
    gemini_service = GeminiService(gemini_api_key)
    logger.info("✅ Gemini Service inicializado")
else:
    gemini_service = GeminiService()  # Modo template
    logger.info("ℹ️  Gemini en modo template (sin API key)")

# Search APIs (opcional)
google_api_key = os.getenv("GOOGLE_API_KEY")
google_engine_id = os.getenv("GOOGLE_ENGINE_ID")

# Inicializa agentes
agents = {
    "agent_0": Agent0WebStudy(sheets_client),
    "agent_1": Agent1SearchLeads(sheets_client, google_api_key, google_engine_id),
    "agent_2": Agent2SendEmails(sheets_client, gmail_service, gemini_service),
    "agent_3": Agent3BudgetBuilder(sheets_client, gemini_service),
    "agent_4": Agent4Supervisor(sheets_client, gmail_service),
}

# Guarda agentes en app state
app.state.sheets_client = sheets_client
app.state.agents = agents
app.state.gmail_service = gmail_service
app.state.gemini_service = gemini_service

# Monta rutas API
app.include_router(routes.router)

# Monta archivos estáticos
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Root endpoint
@app.get("/")
async def root():
    """Retorna el dashboard HTML."""
    html_file = Path(__file__).parent / "static" / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    return {"message": "Dashboard - Sistema Agentes Freelance"}

@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "ok",
        "sheets_connected": sheets_client is not None,
        "agents": list(agents.keys())
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "web.app:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug
    )
