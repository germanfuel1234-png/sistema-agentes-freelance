# Dashboard liviano - solo Python + FastAPI + httpx, sin Chrome/Node
# (eso lo tiene el runner). Build context = raiz de sistema_agentes_freelance/.
FROM python:3.12-slim

RUN pip install --no-cache-dir fastapi "uvicorn[standard]" httpx python-multipart

WORKDIR /app
COPY n8n/dashboard/app.py /app/app.py

EXPOSE 8000
CMD ["python3", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
