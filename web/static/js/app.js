/* ============================================
   SISTEMA AGENTES FREELANCE - JAVASCRIPT
   ============================================ */

const API_BASE = "/api";

// Estado global
let agentResults = {};

// Inicialización
document.addEventListener("DOMContentLoaded", () => {
    console.log("🚀 Dashboard cargado");
    loadStatus();
    loadLeads();
    setInterval(loadLeads, 10000); // Refresh cada 10s
});

// ============================================
// API Calls
// ============================================

async function runAgent(agentName) {
    const btn = document.getElementById(`btn-${agentName}`);
    const resultDiv = document.getElementById(`result-${agentName}`);
    
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Ejecutando...';
    resultDiv.innerHTML = '<p class="info">Procesando...</p>';
    
    try {
        let endpoint = `${API_BASE}/agents/${agentName}/run`;
        let payload = {};
        
        // Construye payload según agente
        if (agentName === "agent_1") {
            payload.country = document.getElementById("agent1-country").value;
            payload.limit = parseInt(document.getElementById("agent1-limit").value);
        } else if (agentName === "agent_2") {
            payload.limit = parseInt(document.getElementById("agent2-limit").value);
        } else if (agentName === "agent_3") {
            payload.client_name = document.getElementById("agent3-client").value;
            payload.project_description = document.getElementById("agent3-project").value;
            
            if (!payload.client_name || !payload.project_description) {
                throw new Error("Por favor completa todos los campos");
            }
        }
        
        const response = await fetch(`${endpoint}?${new URLSearchParams(payload)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || "Error en agente");
        }
        
        agentResults[agentName] = data;
        showResult(agentName, data);
        loadStatus();
        
    } catch (error) {
        resultDiv.innerHTML = `<p class="error">❌ Error: ${error.message}</p>`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = getButtonText(agentName);
    }
}

async function approveAgent(agentName, token) {
    const btn = event.target;
    btn.disabled = true;
    
    try {
        const response = await fetch(
            `${API_BASE}/agents/${agentName}/approve?approval_token=${token}`,
            { method: "POST" }
        );
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail);
        }
        
        const resultDiv = document.getElementById(`result-${agentName}`);
        resultDiv.innerHTML = `<p class="success">✅ Aprobado y ejecutado exitosamente</p>`;
        
    } catch (error) {
        alert("Error: " + error.message);
        btn.disabled = false;
    }
}

async function loadStatus() {
    try {
        const response = await fetch("/health");
        const data = await response.json();
        
        document.getElementById("app-status").innerHTML = 
            data.sheets_connected ? "✅ Conectado" : "❌ Error conexión";
        
    } catch (error) {
        document.getElementById("app-status").innerHTML = "❌ Error";
    }
}

async function loadLeads() {
    try {
        const response = await fetch(`${API_BASE}/leads`);
        const data = await response.json();
        
        document.getElementById("total-leads").textContent = data.count;
        renderLeadsTable(data.leads);
        
        // Carga pendientes
        const responseP = await fetch(`${API_BASE}/leads/pending`);
        const dataP = await responseP.json();
        document.getElementById("pending-leads").textContent = dataP.count;
        
    } catch (error) {
        console.error("Error cargando leads:", error);
    }
}

// ============================================
// UI Rendering
// ============================================

function showResult(agentName, result) {
    const resultDiv = document.getElementById(`result-${agentName}`);
    
    if (result.status === "error") {
        resultDiv.className = "result-area error";
        resultDiv.innerHTML = `
            <p>❌ ${result.error || "Error desconocido"}</p>
            <small>Duración: ${result.duration_seconds?.toFixed(2)}s</small>
        `;
    } else if (result.requires_approval) {
        resultDiv.className = "result-area warning";
        resultDiv.innerHTML = `
            <div>
                <p>⏳ <strong>Aprobación requerida</strong></p>
                <pre style="margin-top: 10px; background: white; padding: 10px; border-radius: 4px; font-size: 0.85em; max-height: 200px; overflow-y: auto;">
${JSON.stringify(result.output, null, 2)}
                </pre>
                <button class="btn btn-success btn-small" onclick="approveAgent('${agentName}', '${result.approval_token}')">
                    ✅ Aprobar
                </button>
                <small style="display: block; margin-top: 10px;">Duración: ${result.duration_seconds?.toFixed(2)}s</small>
            </div>
        `;
    } else {
        resultDiv.className = "result-area success";
        resultDiv.innerHTML = `
            <div>
                <p>✅ Completado exitosamente</p>
                <pre style="margin-top: 10px; background: white; padding: 10px; border-radius: 4px; font-size: 0.85em; max-height: 200px; overflow-y: auto;">
${JSON.stringify(result.output, null, 2)}
                </pre>
                <small>Duración: ${result.duration_seconds?.toFixed(2)}s</small>
            </div>
        `;
    }
}

function renderLeadsTable(leads) {
    const container = document.getElementById("leads-table");
    
    if (!leads || leads.length === 0) {
        container.innerHTML = "<p>Sin leads registrados aún</p>";
        return;
    }
    
    let html = `
        <table>
            <thead>
                <tr>
                    <th>Agencia</th>
                    <th>Contacto</th>
                    <th>Email</th>
                    <th>Ciudad</th>
                    <th>Estado</th>
                    <th>Fecha Envío</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    leads.forEach(lead => {
        const status = lead.send_status || "Pendiente";
        const badgeClass = status === "Pendiente" ? "pending" : 
                          status === "Enviado" ? "sent" : "replied";
        
        html += `
            <tr>
                <td><strong>${lead.business_name}</strong></td>
                <td>${lead.contact_name}</td>
                <td><a href="mailto:${lead.email}">${lead.email}</a></td>
                <td>${lead.city}</td>
                <td><span class="badge ${badgeClass}">${status}</span></td>
                <td>${lead.send_date ? new Date(lead.send_date).toLocaleDateString() : "-"}</td>
            </tr>
        `;
    });
    
    html += `
            </tbody>
        </table>
    `;
    
    container.innerHTML = html;
}

function getButtonText(agentName) {
    const texts = {
        "agent_0": "🔍 Estudiar Web Ahora",
        "agent_1": "🔎 Buscar Leads",
        "agent_2": "✉️ Preparar Mails",
        "agent_3": "💰 Armar Presupuesto",
    };
    return texts[agentName] || "Ejecutar";
}
