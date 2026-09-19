# Dashboard liviano - solo Python + FastAPI + httpx, sin Chrome/Node
# (eso lo tiene el runner). Build context = raiz de sistema_agentes_freelance/.
FROM python:3.12-slim

RUN pip install --no-cache-dir fastapi "uvicorn[standard]" httpx python-multipart

# Mismo motivo que en el runner: sin esto queda en UTC, desfasado 3hs
# contra la hora de Argentina que usa todo lo demás.
ENV TZ=America/Argentina/Buenos_Aires
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY n8n/dashboard/app.py /app/app.py

EXPOSE 8000
CMD ["python3", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
