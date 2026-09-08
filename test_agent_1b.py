"""
Test Agent 1B - Advanced Lead Search
Busca y agrega leads de forma automática en LinkedIn, PyMEs, Instagram
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from core.sheets_client import SheetsClient
from agents.agent_1b_advanced_search import Agent1BAdvancedSearch
from config.settings import Settings


async def main():
    """Ejecuta Agent 1B"""
    print("=" * 70)
    print("🚀 Agent 1B - Advanced Lead Search (Multi-fuente)")
    print("=" * 70)
    
    try:
        # Cargar configuración
        settings = Settings()
        
        # Inicializar Sheets
        sheets = SheetsClient(credentials_file='credentials.json')
        
        # Crear y ejecutar Agent 1B
        agent = Agent1BAdvancedSearch(sheets)
        result, requires_approval = await agent.execute()
        
        # Mostrar resultados
        print("\n" + "=" * 70)
        print("📊 RESULTADOS:")
        print("=" * 70)
        print(f"✅ Total leads encontrados: {result.total_unique}")
        print(f"📱 Fuentes: {', '.join(result.sources_searched)}")
        print(f"🔄 Duplicados removidos: {result.duplicates_removed}")
        print(f"💾 Agregados a Sheets: Sí (automático)")
        
        print("\n📋 LEADS AGREGADOS:")
        for i, lead in enumerate(result.leads_found, 1):
            print(f"\n{i}. {lead.contact_name}")
            print(f"   📧 {lead.contact_email}")
            print(f"   🏢 {lead.business_name}")
            print(f"   📍 {lead.source}")
        
        print("\n" + "=" * 70)
        print("✅ ¡Agent 1B completado exitosamente!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
