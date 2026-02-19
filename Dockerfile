FROM python:3.11-slim

# Salida de Python sin buffer para ver logs al instante
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Instalar dependencias primero (capa en caché si no cambia requirements.txt) (mejor caché: solo rebuild si cambia requirements)
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# Código de la app
COPY . .

# Puerto por defecto
EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
