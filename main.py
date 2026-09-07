"""
Entrypoint de la aplicación.
Inicia el servidor FastAPI en modo desarrollo.
"""
import logging
import sys
from pathlib import Path

# Añade el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    import uvicorn
    from config.settings import settings
    
    logger.info("=" * 60)
    logger.info("🚀 Iniciando Sistema de Agentes Freelance")
    logger.info("=" * 60)
    logger.info(f"   Dashboard: http://{settings.app_host}:{settings.app_port}")
    logger.info(f"   Debug: {settings.debug}")
    logger.info(f"   Google Sheet ID: {settings.google_sheet_id[:30]}...")
    logger.info("=" * 60)
    
    uvicorn.run(
        "web.app:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
