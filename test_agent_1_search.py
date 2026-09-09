"""
Test Agent 1 - Buscador de Leads (arquitectura de búsqueda general,
sin restringir a un sitio, tipo "agencia de marketing digital [ciudad]")
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from core.sheets_client import SheetsClient
from agents.agent_1_search_leads import Agent1SearchLeads
from config.settings import settings


async def main():
    print("=" * 70)
    print("🚀 Agent 1 - Búsqueda general de leads (Google Custom Search)")
    print("=" * 70)
    print(f"🔑 API key configurada: {'sí' if settings.google_custom_search_api_key else 'NO'}")
    print(f"🔑 Engine ID configurado: {'sí' if settings.google_custom_search_engine_id else 'NO'}")

    sheets = SheetsClient(credentials_file='credentials.json')
    agent = Agent1SearchLeads(
        sheets,
        api_key=settings.google_custom_search_api_key,
        engine_id=settings.google_custom_search_engine_id,
    )

    new_leads, _ = await agent.execute(
        search_type="marketing",
        country="Argentina",
        limit=3,
    )

    print("\n" + "=" * 70)
    print(f"📊 Leads nuevos agregados a Sheets: {len(new_leads)}")
    print("=" * 70)
    for i, lead in enumerate(new_leads, 1):
        print(f"\n{i}. {lead.business_name}")
        print(f"   📧 {lead.email}")
        print(f"   📍 Fuente: {lead.source}")


if __name__ == "__main__":
    asyncio.run(main())
