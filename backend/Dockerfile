# =====================================================================
# Backend — FastAPI (MegaSoft CRM)
# Corre uvicorn en el puerto 8001 con UN solo worker (APScheduler ejecuta
# tareas programadas; con varios workers se duplicarían los jobs).
# =====================================================================
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Dependencias de sistema:
#  - WeasyPrint 68 (PDFs): libpango / cairo / gdk-pixbuf / harfbuzz / fonts
#  - Pillow / reportlab: libjpeg, zlib, fontconfig
#  - Toolchain mínimo por si algún paquete no tiene wheel
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    libharfbuzz0b \
    libjpeg62-turbo \
    zlib1g \
    libglib2.0-0 \
    shared-mime-info \
    fontconfig \
    fonts-dejavu-core \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# El código vive en /app/backend (algunas rutas usan esa ruta absoluta)
WORKDIR /app/backend

# Instalar dependencias primero (mejor cache). emergentintegrations requiere el
# índice extra de Emergent; el resto se resuelve desde PyPI.
COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt \
      --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/

# Copiar el resto del código
COPY . .

EXPOSE 8001

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
