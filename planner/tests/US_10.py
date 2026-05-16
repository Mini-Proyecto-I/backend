"""
US 10: Porcentaje global de avance.

Pruebas para:
- Obtener el porcentaje de completitud global de subtareas.
- Calcular correctamente el porcentaje según subtareas 'DONE' (REALIZADO).
- Manejo cuando no existen subtareas (0%).
- Filtrar correctamente las subtareas usando los parámetros 'from_date' y 'to_date'.
- Aislamiento de información del usuario (no incluir subtareas de otros usuarios).
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from planner.models import Activity, Course, Subtask

User = get_user_model()


class US10CompletionPercentTests(TestCase):
    """Pruebas del endpoint /api/activity/completion-percent/ (US 10)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="us10@test.com",
            password="pass",
            name="Usuario US10",
            daily_hours_limit=Decimal("6.00"),
        )
        self.other_user = User.objects.create_user(
            email="other10@test.com",
            password="pass",
            name="Otro Usuario",
            daily_hours_limit=Decimal("6.00"),
        )
        
        self.client.force_authenticate(user=self.user)
        self.course = Course.objects.create(name="Curso US10", user=self.user)
        self.activity_deadline = timezone.localdate() + timedelta(days=20)
        self.activity = Activity.objects.create(
            user=self.user,
            title="Actividad US10",
            course=self.course,
            type=Activity.TypeChoices.OTRO,
            deadline=self.activity_deadline,
        )
        self.base_url = "/api/activity/completion-percent/"
        
    def _create_subtask(self, title, days_offset, subtask_status, user=None, activity=None):
        if user is None:
            user = self.user
        if activity is None:
            activity = self.activity
            
        return Subtask.objects.create(
            user=user,
            activity=activity,
            title=title,
            estimated_hours=Decimal("1.00"),
            target_date=timezone.localdate() + timedelta(days=days_offset),
            status=subtask_status,
        )

    def test_completion_percent_sin_subtareas(self):
        """Si no hay subtareas vinculadas, el porcentaje debe ser 0.0."""
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["completion_percent"], 0.0)
        self.assertEqual(response.data["total_subtasks"], 0)
        self.assertEqual(response.data["total_subtasks_done"], 0)

    def test_completion_percent_todas_completadas(self):
        """Si todas las subtareas están REALIZADO, porcentaje es 100.0."""
        self._create_subtask("T1", 1, Subtask.Status.REALIZADO)
        self._create_subtask("T2", 2, Subtask.Status.REALIZADO)
        
        response = self.client.get(self.base_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_subtasks"], 2)
        self.assertEqual(response.data["total_subtasks_done"], 2)
        self.assertEqual(response.data["completion_percent"], 100.0)

    def test_completion_percent_parcialmente_completadas(self):
        """Cálculo correcto si hay mix de subtareas REALIZADO y PENDIENTE."""
        self._create_subtask("T1", 1, Subtask.Status.REALIZADO)
        self._create_subtask("T2", 2, Subtask.Status.PENDIENTE)
        self._create_subtask("T3", 3, Subtask.Status.POSPUESTO)
        self._create_subtask("T4", 4, Subtask.Status.REALIZADO)
        
        # 2 realizadas de 4 totales -> 50%
        response = self.client.get(self.base_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_subtasks"], 4)
        self.assertEqual(response.data["total_subtasks_done"], 2)
        self.assertEqual(response.data["completion_percent"], 50.0)

    def test_completion_percent_con_from_date(self):
        """Filtro solo por from_date: toma subtareas desde esa fecha en adelante."""
        today = timezone.localdate()
        self._create_subtask("Ayer", -1, Subtask.Status.REALIZADO)
        self._create_subtask("Hoy", 0, Subtask.Status.PENDIENTE)
        self._create_subtask("Mañana", 1, Subtask.Status.REALIZADO)
        
        today_str = today.isoformat()
        response = self.client.get(f"{self.base_url}?from_date={today_str}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Omitimos la de Ayer. Total: 2. Realizadas: 1 -> 50%
        self.assertEqual(response.data["total_subtasks"], 2)
        self.assertEqual(response.data["total_subtasks_done"], 1)
        self.assertEqual(response.data["completion_percent"], 50.0)

    def test_completion_percent_con_to_date(self):
        """Filtro solo por to_date: toma subtareas hasta esa fecha inclusive."""
        today = timezone.localdate()
        self._create_subtask("Ayer", -1, Subtask.Status.PENDIENTE)
        self._create_subtask("Hoy", 0, Subtask.Status.REALIZADO)
        self._create_subtask("Mañana", 1, Subtask.Status.REALIZADO)
        
        today_str = today.isoformat()
        response = self.client.get(f"{self.base_url}?to_date={today_str}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Omitimos la de Mañana. Total: 2. Realizadas: 1 -> 50%
        self.assertEqual(response.data["total_subtasks"], 2)
        self.assertEqual(response.data["total_subtasks_done"], 1)
        self.assertEqual(response.data["completion_percent"], 50.0)

    def test_completion_percent_con_rango_fechas(self):
        """Filtro combinando from_date y to_date."""
        today = timezone.localdate()
        self._create_subtask("Día -2", -2, Subtask.Status.REALIZADO)
        self._create_subtask("Día 0", 0, Subtask.Status.REALIZADO)
        self._create_subtask("Día 2", 2, Subtask.Status.PENDIENTE)
        self._create_subtask("Día 5", 5, Subtask.Status.PENDIENTE)
        
        from_str = today.isoformat()
        to_str = (today + timedelta(days=3)).isoformat()
        url = f"{self.base_url}?from_date={from_str}&to_date={to_str}"
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Solo caen en el rango "Día 0" y "Día 2". Total: 2. Realizadas: 1 -> 50%
        self.assertEqual(response.data["total_subtasks"], 2)
        self.assertEqual(response.data["total_subtasks_done"], 1)
        self.assertEqual(response.data["completion_percent"], 50.0)

    def test_completion_percent_aislamiento_usuario(self):
        """No debe incluir subtareas de otros usuarios en el cálculo."""
        # Usuario normal
        self._create_subtask("T1_yo", 1, Subtask.Status.PENDIENTE)
        
        # Otro usuario
        other_course = Course.objects.create(name="Otro Curso", user=self.other_user)
        other_activity = Activity.objects.create(
            user=self.other_user,
            title="Act",
            course=other_course,
            type=Activity.TypeChoices.OTRO,
            deadline=self.activity_deadline,
        )
        self._create_subtask("T_otro1", 1, Subtask.Status.REALIZADO, user=self.other_user, activity=other_activity)
        self._create_subtask("T_otro2", 2, Subtask.Status.REALIZADO, user=self.other_user, activity=other_activity)
        
        # El mío tiene 1 pendiente y 0 realizadas. (0%)
        # El otro tiene 2 realizadas. No deben afectar.
        response = self.client.get(self.base_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_subtasks"], 1)
        self.assertEqual(response.data["total_subtasks_done"], 0)
        self.assertEqual(response.data["completion_percent"], 0.0)

    def test_completion_percent_formato_fecha_invalido(self):
        """Validar que devuelva bad request cuando se manda una fecha errónea."""
        url = f"{self.base_url}?from_date=2026-fecha-123"
        response = self.client.get(url)
        
        # El serializer debería retornar error 400
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)