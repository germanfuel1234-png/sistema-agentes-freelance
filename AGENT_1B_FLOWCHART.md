# 📊 Sistema de Agentes - Flujo Completo con Agent 1B

## 🔄 Flujo de Ejecución

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SISTEMA AGENTES FREELANCE                            │
│                   Con busca de leads MULTI-FUENTE (1B)                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ INICIO                                                                       │
└────────────────────────────────────┬──────────────────────────────────────────┘
                                     │
                    ┌────────────────▼──────────────────┐
                    │ AGENT 0: Web Study               │
                    │ 🔍 Estudia germanrodriguez.ar    │
                    │ 📋 Extrae: Servicios, Precios    │
                    │ 📝 Actualiza: precios_base Sheet │
                    │ ❓ Aprobación: NO                │
                    └────────────────┬──────────────────┘
                                     │
                    ┌────────────────▼──────────────────┐
                    │ AGENT 1: Lead Search (Básico)    │
                    │ 🔎 Busca con keywords simples    │
                    │ 📧 Extrae: Email, nombre, rubro  │
                    │ 📝 Agrega: leads_tracking Sheet  │
                    │ ❓ Aprobación: NO                │
                    └────────────────┬──────────────────┘
                                     │
        ┌────────────────────────────▼────────────────────────────┐
        │                                                          │
        │                  🆕 AGENT 1B: Advanced                  │
        │                 Lead Search (MULTI-FUENTE)              │
        │                                                          │
        │    ┌─────────────┬─────────────┬──────────────┐         │
        │    │             │             │              │         │
        │    ▼             ▼             ▼              ▼         │
        │  LinkedIn      PyMEs       Instagram      Consolidar   │
        │  Profiles     Dirs         Profiles       & Dedup       │
        │  (LinkedIn)   (España)     (Hashtags)                   │
        │                (Latam)                                  │
        │                                                          │
        │  📱 Profesionales        🏢 Empresas       📸 Agencias  │
        │  Marketing Managers      Marketing         Marketing    │
        │  Community Managers      Services         Profiles      │
        │  Agencias Digitales      PyMEs            Influencers  │
        │                                                          │
        │  ✅ RESULTADO: Nombre + Email (x50-100 leads)          │
        │  ✅ Elimina duplicados                                 │
        │  ✅ Agrega AUTOMÁTICAMENTE a Sheets                    │
        │  ❓ Aprobación: NO                                      │
        │                                                          │
        └────────────────┬────────────────────────────────────────┘
                         │
                    ┌────▼─────────────────────────┐
                    │ AGENT 4: Supervisor          │
                    │ 🔍 Valida sistema            │
                    │ ✅ Verifica conexiones       │
                    │ 📊 Reporta estado            │
                    │ ❓ Aprobación: NO            │
                    └────┬──────────────────────────┘
                         │
                    ┌────▼──────────────────────────┐
                    │ AGENT 2: Send Emails 📧      │
                    │ ✉️ Genera emails personalizados
                    │ 📋 Con firma profesional      │
                    │ 👁️ Muestra preview            │
                    │ ❓ Aprobación: SÍ (MANUAL)   │
                    │ 🚀 Envía si apruebas        │
                    │ 📊 Actualiza: emails_sent    │
                    └────┬──────────────────────────┘
                         │
                    ┌────▼──────────────────────────┐
                    │ AGENT 3: Generate Budgets 💰 │
                    │ 💵 Calcula presupuestos       │
                    │ 🧮 Ajustes automáticos        │
                    │ 👁️ Muestra propuestas         │
                    │ ❓ Aprobación: SÍ (MANUAL)   │
                    │ 💾 Guarda si apruebas        │
                    │ 📊 Actualiza: presupuestos    │
                    └────┬──────────────────────────┘
                         │
                    ┌────▼──────────────────────────┐
                    │ FIN                          │
                    │ ✅ Sistema completado        │
                    │ 📊 Google Sheet actualizada  │
                    └──────────────────────────────┘
```

---

## 📊 Resumen de Agentes

| Agent | Nombre | Función | Entrada | Salida | Aprobación |
|-------|--------|---------|---------|--------|-----------|
| **0** | Web Study | Estudia germanrodriguez.ar | Scraping web | precios_base | ❌ No |
| **1** | Lead Search | Busca leads básico | Google Search | leads_tracking | ❌ No |
| **1B** | Advanced Search | Busca multi-fuente (LinkedIn, PyMEs, Instagram) | APIs + Directorios | leads_tracking | ❌ No |
| **4** | Supervisor | Valida sistema y conexiones | Estado interno | Reporte de estado | ❌ No |
| **2** | Send Emails | Genera y envía emails personalizados | Leads + Templates | emails_sent | ✅ Sí |
| **3** | Budgets | Genera propuestas de presupuesto | Leads + Precios | presupuestos | ✅ Sí |

---

## 🎯 Agentes Automáticos vs. Con Aprobación

### Automáticos (Se ejecutan sin intervención)
- ✅ **Agent 0:** Extrae datos de tu web
- ✅ **Agent 1:** Busca leads simples
- ✅ **Agent 1B:** Busca leads multi-fuente ← NUEVO
- ✅ **Agent 4:** Valida el sistema

### Con Aprobación (Requieren tu confirmación)
- 🔔 **Agent 2:** Antes de enviar emails
  - Muestra vista previa
  - Tú approves → Se envían
  
- 🔔 **Agent 3:** Antes de guardar presupuestos
  - Muestra cálculos
  - Tú approves → Se guardan

---

## 🌟 Lo Mejor de Agent 1B

```
✅ SIN RUIDO
   Solo nombre + email
   Nada de datos innecesarios

✅ MULTI-FUENTE
   LinkedIn + PyMEs + Instagram
   Máxima cobertura

✅ SIN DUPLICADOS
   Consolida automáticamente
   Un lead = Un registro

✅ 100% AUTOMÁTICO
   Busca y agrega directamente a Sheets
   No necesita tu aprobación

✅ ESCALABLE
   50-100 leads por ejecución
   Pronto: APIs reales de LinkedIn, etc.

✅ COBERTURA INTERNACIONAL
   España + 10 países de Latam
   Desde tu máquina ⚙️
```

---

## 🚀 Caso de Uso Completo

### Día 1: Lunes a las 9 AM
```bash
python run_agents.py
```

1. Agent 0 → Verifica tus precios
2. Agent 1 → Busca 20-30 leads básicos
3. Agent 1B → Busca 50-100 leads avanzados ← MULTI-FUENTE
4. Agent 4 → Valida todo está ok
5. Agent 2 → Te muestra 70+ emails para aprobar
6. Tú dices: "Envía todos" ✅
7. Agent 2 → Los envía
8. Agent 3 → Te muestra 70+ presupuestos para revisar
9. Tú dices: "Guarda todos" ✅
10. Agent 3 → Los guarda

**Resultado:** ~70+ leads nuevos + emails enviados + presupuestos generados en tu Sheet

### Día 5: Responden los primeros
- Algunos leads responden
- Cambias el estado en Sheets: "Respondió"
- Agent 2 puede generar email de seguimiento

---

## 💾 Google Sheet Actualizada

Cada ejecución completa actualiza automáticamente:

```
📋 SHEET STRUCTURE
├── precios_base
│   ├── Servicio (Landing, E-commerce, App, etc.)
│   ├── Precio base ARS
│   └── Descripción
│
├── leads_tracking
│   ├── Negocio
│   ├── Contacto
│   ├── Email ← AQUÍ agregan Agent 1 y 1B
│   ├── Rubro (Marketing)
│   ├── País (Argentina, Chile, etc.)
│   ├── Estado (Pendiente Outreach)
│   └── Fuente (LinkedIn / PyMEs / Instagram)
│
├── emails_sent
│   ├── Lead ID
│   ├── Email
│   ├── Fecha envío
│   └── Message ID Gmail
│
└── presupuestos
    ├── Lead ID
    ├── Presupuesto ID
    ├── Monto ARS
    ├── Estado
    └── Fecha creación
```

---

## 🔧 Ejecución Manual vs. Automática

### Manual (Recomendado para empezar)
```bash
# Terminal 1: Ejecuta todos los agentes
python run_agents.py

# Apruebas emails y presupuestos cuando se pida
# (Interactivo)
```

### Automática (Para producción)
```bash
# Agregar a crontab (Linux/Mac)
0 9 * * * cd /path/to/proyecto && python run_agents.py

# Cada día a las 9 AM:
# - Se buscan leads
# - Se actualizan datos
# - Se generan emails y presupuestos
# (NO interactivo - requiere setup de approval automática)
```

---

## 📈 Métricas que Puedes Trackear

Después de cada ejecución, consulta tu Google Sheet:

```
Leads encontrados esta semana:     45 (Agent 1B = 35)
Emails enviados:                   42
Presupuestos generados:            42
Respuestas recibidas:              8 (19%)
Proyectos ganados:                 2
Ingresos pipeline:                 $280,000 ARS
```

---

## 🎓 Próximos Pasos

1. **Habilita Google Sheets API** (5 min)
2. **Ejecuta `python test_agent_1b.py`** (1 min)
3. **Verifica en tu Sheet** que se agregaron leads (1 min)
4. **Ejecuta `python run_agents.py`** (5 min)
5. **Aprueba emails y presupuestos** (2 min)
6. **Monitorea respuestas en tu Sheet**

---

**¡Tu sistema de agentes está listo! 🚀**
