"""
Rutas API del dashboard.
"""
from fastapi import APIRouter, HTTPException, Request
from typing import List, Optional
import logging

from core.models import Lead
from core.sheets_client import SheetsClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["agents"])


@router.get("/leads")
async def get_leads(request: Request):
    """Obtiene todos los leads."""
    sheets: SheetsClient = request.app.state.sheets_client
    try:
        leads = sheets.get_all_leads()
        return {"count": len(leads), "leads": leads}
    except Exception as e:
        logger.error(f"Error obteniendo leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leads/pending")
async def get_pending_leads(request: Request):
    """Obtiene solo leads pendientes."""
    sheets: SheetsClient = request.app.state.sheets_client
    try:
        leads = sheets.get_pending_leads()
        return {"count": len(leads), "leads": leads}
    except Exception as e:
        logger.error(f"Error obteniendo leads pendientes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/agent_1/run")
async def run_agent_1(request: Request, country: str = "Argentina", limit: int = 10):
    """Dispara Agent 1 (búsqueda de leads)."""
    agent = request.app.state.agents.get("agent_1")
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 1 no encontrado")
    
    try:
        result = await agent.run(country=country, limit=limit)
        return {
            "agent": result.agent_name,
            "status": result.status.value,
            "output": result.output,
            "duration_seconds": result.duration_seconds()
        }
    except Exception as e:
        logger.error(f"Error en Agent 1: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/agent_2/run")
async def run_agent_2(request: Request, limit: int = 5):
    """Dispara Agent 2 (preparar mails)."""
    agent = request.app.state.agents.get("agent_2")
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 2 no encontrado")
    
    try:
        result = await agent.run(limit=limit)
        return {
            "agent": result.agent_name,
            "status": result.status.value,
            "requires_approval": result.requires_approval,
            "approval_token": result.approval_token,
            "output": result.output,
            "duration_seconds": result.duration_seconds()
        }
    except Exception as e:
        logger.error(f"Error en Agent 2: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/{agent_name}/approve")
async def approve_agent(request: Request, agent_name: str, approval_token: str):
    """Aprueba un resultado pendiente."""
    agent = request.app.state.agents.get(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"{agent_name} no encontrado")
    
    try:
        result = await agent.approve(approval_token)
        return {
            "agent": result.agent_name,
            "status": result.status.value,
            "duration_seconds": result.duration_seconds()
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error aprobando {agent_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/agent_3/run")
async def run_agent_3(request: Request, client_name: str, project_description: str):
    """Dispara Agent 3 (armar presupuesto)."""
    agent = request.app.state.agents.get("agent_3")
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 3 no encontrado")
    
    try:
        result = await agent.run(
            client_name=client_name,
            project_description=project_description
        )
        return {
            "agent": result.agent_name,
            "status": result.status.value,
            "requires_approval": result.requires_approval,
            "approval_token": result.approval_token,
            "output": result.output,
            "duration_seconds": result.duration_seconds()
        }
    except Exception as e:
        logger.error(f"Error en Agent 3: {e}")
        raise HTTPException(status_code=500, detail=str(e))
