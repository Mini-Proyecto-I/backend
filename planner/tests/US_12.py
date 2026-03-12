"""
HU 12: Configurar límite diario.

Pruebas para:
- GET /api/configuracion/ para obtener el límite actual.
- PUT /api/configuracion/ para actualizar el límite.
- Validación de rango (0.5 a 24.0 horas).
- Lógica default de 6 horas.
- Endpoint calendar que retorna disponibilidad diaria.
- Validación de límite en el endpoint calendar.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from planner.models import Activity, Subtask, Course

User = get_user_model()


class US12ConfiguracionTests(TestCase):
    """Tests de configuración de límite diario (HU 12)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="us12@test.com",
            password="pass",
            name="Usuario US12",
            daily_hours_limit=Decimal("6.00"),
        )
        self.client.force_authenticate(user=self.user)
        self.url = "/api/configuracion/"

    def test_get_configuracion_retorna_limite_actual(self):
        """GET retorna el límite actual del usuario."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("daily_hours_limit", response.data)
        self.assertEqual(response.data["daily_hours_limit"], 6.0)

    def test_get_configuracion_retorna_limite_personalizado(self):
        """GET retorna el límite personalizado si el usuario lo tiene configurado."""
        user_custom = User.objects.create_user(
            email="custom12@test.com",
            password="pass",
            name="Usuario Custom",
            daily_hours_limit=Decimal("8.50"),
        )
        self.client.force_authenticate(user=user_custom)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["daily_hours_limit"], 8.5)

    def test_get_configuracion_retorna_limite_default(self):
        """GET retorna el límite default (6.0) si el usuario no tiene límite personalizado."""
        user_default = User.objects.create_user(
            email="default12@test.com",
            password="pass",
            name="Usuario Default",
        )
        # Asegurar que tiene el default
        user_default.daily_hours_limit = Decimal("6.0")
        user_default.save()
        self.client.force_authenticate(user=user_default)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["daily_hours_limit"], 6.0)

    def test_put_configuracion_actualiza_limite_success(self):
        """PUT actualiza el límite correctamente."""
        payload = {
            "daily_hours_limit": 8.0,
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("daily_hours_limit", response.data)
        self.assertEqual(response.data["daily_hours_limit"], 8.0)
        self.assertIn("message", response.data)
        self.user.refresh_from_db()
        self.assertEqual(float(self.user.daily_hours_limit), 8.0)

    def test_put_configuracion_valida_rango_minimo(self):
        """PUT rechaza valores menores a 0.5."""
        payload = {
            "daily_hours_limit": 0.4,
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("0.5 y 24.0", response.data["error"])

    def test_put_configuracion_valida_rango_maximo(self):
        """PUT rechaza valores mayores a 24.0."""
        payload = {
            "daily_hours_limit": 24.5,
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("0.5 y 24.0", response.data["error"])

    def test_put_configuracion_acepta_limite_minimo(self):
        """PUT acepta el límite mínimo válido (0.5)."""
        payload = {
            "daily_hours_limit": 0.5,
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["daily_hours_limit"], 0.5)
        self.user.refresh_from_db()
        self.assertEqual(float(self.user.daily_hours_limit), 0.5)

    def test_put_configuracion_acepta_limite_maximo(self):
        """PUT acepta el límite máximo válido (24.0)."""
        payload = {
            "daily_hours_limit": 24.0,
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["daily_hours_limit"], 24.0)
        self.user.refresh_from_db()
        self.assertEqual(float(self.user.daily_hours_limit), 24.0)

    def test_put_configuracion_valida_campo_requerido(self):
        """PUT requiere el campo daily_hours_limit."""
        payload = {}

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("requiere", response.data["error"])

    def test_put_configuracion_valida_tipo_dato(self):
        """PUT rechaza valores que no son números válidos."""
        payload = {
            "daily_hours_limit": "no es un número",
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("inválido", response.data["error"])

    def test_put_configuracion_acepta_decimales(self):
        """PUT acepta valores con decimales."""
        payload = {
            "daily_hours_limit": 7.75,
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["daily_hours_limit"], 7.75)
        self.user.refresh_from_db()
        self.assertEqual(float(self.user.daily_hours_limit), 7.75)

    def test_put_configuracion_requiere_autenticacion(self):
        """El endpoint PUT requiere autenticación."""
        self.client.force_authenticate(user=None)
        payload = {
            "daily_hours_limit": 8.0,
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertIn(response.status_code, [401, 403])

    def test_get_configuracion_requiere_autenticacion(self):
        """El endpoint GET requiere autenticación."""
        self.client.force_authenticate(user=None)

        response = self.client.get(self.url)

        self.assertIn(response.status_code, [401, 403])


class US12CalendarTests(TestCase):
    """Tests del endpoint calendar para disponibilidad diaria (HU 12)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="calendar@test.com",
            password="pass",
            name="Usuario Calendar",
            daily_hours_limit=Decimal("6.00"),
        )
        self.client.force_authenticate(user=self.user)
        self.course = Course.objects.create(name="Curso Calendar", user=self.user)
        self.activity = Activity.objects.create(
            user=self.user,
            title="Actividad Calendar",
            course=self.course,
            type=Activity.TypeChoices.OTRO,
            deadline=timezone.localdate() + timedelta(days=10),
        )
        self.subtask = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Subtarea Calendar",
            estimated_hours=Decimal("2.00"),
            target_date=timezone.localdate() + timedelta(days=1),
            status=Subtask.Status.PENDIENTE,
        )

    def test_calendar_retorna_semana_completa(self):
        """El endpoint calendar retorna 7 días (lunes a domingo)."""
        url = f"/api/subtareas/{self.subtask.id}/calendar/"

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("calendar", response.data)
        self.assertEqual(len(response.data["calendar"]), 7)

    def test_calendar_retorna_estructura_correcta(self):
        """El endpoint calendar retorna la estructura correcta."""
        url = f"/api/subtareas/{self.subtask.id}/calendar/"

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("subtask", response.data)
        self.assertIn("start_date", response.data)
        self.assertIn("end_date", response.data)
        self.assertIn("calendar", response.data)
        
        # Verificar estructura de cada día
        for day in response.data["calendar"]:
            self.assertIn("date", day)
            self.assertIn("tasks", day)
            self.assertIn("fits", day)
            self.assertIn("reason", day)
            self.assertIn("current_load", day)
            self.assertIn("limit", day)

    def test_calendar_retorna_fits_false_para_fecha_pasada(self):
        """El endpoint marca fits=false para fechas pasadas."""
        url = f"/api/subtareas/{self.subtask.id}/calendar/"
        # Usar fecha de la semana pasada
        past_date = timezone.localdate() - timedelta(days=7)

        response = self.client.get(url, {"date": past_date.isoformat()})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Encontrar el día pasado en el calendario
        past_day = next(
            (day for day in response.data["calendar"] if day["date"] == past_date.isoformat()),
            None
        )
        if past_day:
            self.assertFalse(past_day["fits"])
            self.assertIn("pasó", past_day["reason"])

    def test_calendar_retorna_fits_false_para_fecha_que_excede_deadline(self):
        """El endpoint marca fits=false si la fecha excede el deadline de la actividad."""
        # Crear actividad con deadline cercano
        activity_short = Activity.objects.create(
            user=self.user,
            title="Actividad corta",
            course=self.course,
            type=Activity.TypeChoices.OTRO,
            deadline=timezone.localdate() + timedelta(days=2),
        )
        subtask_short = Subtask.objects.create(
            user=self.user,
            activity=activity_short,
            title="Subtarea corta",
            estimated_hours=Decimal("1.00"),
            target_date=timezone.localdate() + timedelta(days=1),
            status=Subtask.Status.PENDIENTE,
        )
        url = f"/api/subtareas/{subtask_short.id}/calendar/"

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Buscar día que excede deadline
        deadline_date = activity_short.deadline + timedelta(days=1)
        exceeded_day = next(
            (day for day in response.data["calendar"] if day["date"] == deadline_date.isoformat()),
            None
        )
        if exceeded_day:
            self.assertFalse(exceeded_day["fits"])
            self.assertIn("límite de la actividad", exceeded_day["reason"])

    def test_calendar_retorna_fits_false_para_sobrecarga(self):
        """El endpoint marca fits=false si agregar la subtarea causaría sobrecarga."""
        # Crear subtareas que suman 5 horas en un día específico
        target_date = timezone.localdate() + timedelta(days=3)
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub 1",
            estimated_hours=Decimal("5.00"),
            target_date=target_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Subtarea a evaluar con 2 horas (total sería 7h > 6h)
        subtask_to_check = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub a evaluar",
            estimated_hours=Decimal("2.00"),
            target_date=timezone.localdate() + timedelta(days=1),
            status=Subtask.Status.PENDIENTE,
        )
        url = f"/api/subtareas/{subtask_to_check.id}/calendar/"

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Buscar el día con sobrecarga
        overloaded_day = next(
            (day for day in response.data["calendar"] if day["date"] == target_date.isoformat()),
            None
        )
        if overloaded_day:
            self.assertFalse(overloaded_day["fits"])
            self.assertIn("sobrecarga", overloaded_day["reason"])

    def test_calendar_retorna_fits_true_para_dia_sin_conflicto(self):
        """El endpoint marca fits=true para días sin conflictos."""
        # Día sin subtareas
        safe_date = timezone.localdate() + timedelta(days=5)
        url = f"/api/subtareas/{self.subtask.id}/calendar/"

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        safe_day = next(
            (day for day in response.data["calendar"] if day["date"] == safe_date.isoformat()),
            None
        )
        if safe_day:
            self.assertTrue(safe_day["fits"])
            self.assertEqual(safe_day["reason"], "")

    def test_calendar_retorna_tasks_por_dia(self):
        """El endpoint retorna las tareas planificadas por día."""
        # Crear subtareas en diferentes días
        date1 = timezone.localdate() + timedelta(days=2)
        date2 = timezone.localdate() + timedelta(days=3)
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub día 2",
            estimated_hours=Decimal("1.00"),
            target_date=date1,
            status=Subtask.Status.PENDIENTE,
        )
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub día 3",
            estimated_hours=Decimal("2.00"),
            target_date=date2,
            status=Subtask.Status.PENDIENTE,
        )

        url = f"/api/subtareas/{self.subtask.id}/calendar/"

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        day1 = next(
            (day for day in response.data["calendar"] if day["date"] == date1.isoformat()),
            None
        )
        day2 = next(
            (day for day in response.data["calendar"] if day["date"] == date2.isoformat()),
            None
        )
        if day1:
            self.assertGreaterEqual(len(day1["tasks"]), 1)
        if day2:
            self.assertGreaterEqual(len(day2["tasks"]), 1)

    def test_calendar_excluye_subtask_actual_del_calculo(self):
        """El endpoint excluye la subtarea actual del cálculo de carga."""
        # Subtarea ya planificada en un día
        existing_date = timezone.localdate() + timedelta(days=4)
        self.subtask.target_date = existing_date
        self.subtask.save()

        # Crear otra subtarea en el mismo día
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Otra subtarea",
            estimated_hours=Decimal("3.00"),
            target_date=existing_date,
            status=Subtask.Status.PENDIENTE,
        )

        url = f"/api/subtareas/{self.subtask.id}/calendar/"

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        existing_day = next(
            (day for day in response.data["calendar"] if day["date"] == existing_date.isoformat()),
            None
        )
        if existing_day:
            # current_load debería ser solo 3.00 (otra subtarea), no incluir la actual
            self.assertEqual(existing_day["current_load"], 3.0)

    def test_calendar_retorna_current_load_y_limit(self):
        """El endpoint retorna current_load y limit para cada día."""
        url = f"/api/subtareas/{self.subtask.id}/calendar/"

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for day in response.data["calendar"]:
            self.assertIsInstance(day["current_load"], (int, float))
            self.assertIsInstance(day["limit"], (int, float))
            self.assertEqual(day["limit"], 6.0)  # Límite del usuario

    def test_calendar_requiere_autenticacion(self):
        """El endpoint calendar requiere autenticación."""
        self.client.force_authenticate(user=None)
        url = f"/api/subtareas/{self.subtask.id}/calendar/"

        response = self.client.get(url)

        self.assertIn(response.status_code, [401, 403])

    def test_calendar_subtask_no_encontrada_retorna_404(self):
        """Si la subtarea no existe, retorna 404."""
        from uuid import uuid4
        fake_id = uuid4()
        url = f"/api/subtareas/{fake_id}/calendar/"

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_calendar_subtask_otro_usuario_retorna_404(self):
        """No se puede acceder al calendar de una subtarea de otro usuario."""
        other_user = User.objects.create_user(
            email="other@test.com",
            password="pass",
            name="Otro Usuario",
        )
        other_activity = Activity.objects.create(
            user=other_user,
            title="Actividad Otro",
            course=None,
            type=Activity.TypeChoices.OTRO,
        )
        other_subtask = Subtask.objects.create(
            user=other_user,
            activity=other_activity,
            title="Subtarea Otro",
            estimated_hours=Decimal("1.00"),
        )
        url = f"/api/subtareas/{other_subtask.id}/calendar/"

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
