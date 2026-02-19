# Smart Planner API - Backend

Este repositorio contiene la lógica de negocio y la API REST para el sistema de planificación académica. El backend está diseñado para gestionar el ciclo de vida de actividades evaluativas, detectar conflictos de sobrecarga y garantizar la persistencia de datos por usuario.

## 🛠️ Tecnologías Principales

* **Framework:** Django 5.x + Django REST Framework (DRF)
* **Base de Datos:** PostgreSQL (vía Supabase o Docker local)
* **Autenticación:** JWT (JSON Web Tokens)
* **Contenedores:** Docker & Docker Compose

---

## 🏗️ Arquitectura de la API

El proyecto está organizado en dos aplicaciones principales para separar las responsabilidades de identidad y planificación:

### 1. App `usuarios`
Se ha sobrescrito el modelo de usuario por defecto de Django para adaptar el sistema a las necesidades del proyecto:
* **Modelo de Usuario Personalizado:** Hereda de `AbstractUser` e integra el campo `daily_hour_limit` (capacidad diaria), permitiendo que la lógica de conflictos sea específica para cada estudiante.

### 2. App `planner`
Contiene la lógica core y el motor de cálculo de prioridades:
* **Activity:** Entidad para el registro de actividades evaluativas (Título, tipo, fecha límite).
* **Subtask:** Desglose de tareas con horas estimadas, fechas objetivo y estados de ejecución.
* **Course:** Maestro de cursos/materias para categorización.
* **ReprogrammingLog:** Histórico de auditoría para registrar cada vez que una fecha original es modificada por imprevistos.



---

## 🚀 Instalación y Despliegue

Para levantar el entorno de desarrollo de forma local (incluyendo base de datos, servidor de aplicaciones y dependencias), asegúrate de tener instalado Docker y Docker Compose:

1. **Clonar el repositorio e ingresar a la carpeta:**
   ```bash
   cd backend-planner

2. **Levantar los servicios**
    ```bash
    docker compose up --build

El servidor estará escuchando en http://localhost:8000.
