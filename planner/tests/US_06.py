"""
HU 06: Reprogramar subtarea/actividad.

Pruebas para:
- Actualización de fecha objetivo (target_date) de una subtarea mediante PUT.
- Validación de que la fecha no sea anterior a hoy.
- Validación de coherencia con la fecha límite de la actividad padre.
- Creación automática de log de reprogramación.
- Actualización de horas estimadas.
- Validación de autenticación y permisos.
"""
from datetime import timedelta, date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from planner.models import Activity, Subtask, ReprogrammingLog, Course

User = get_user_model()


class US06ReprogramarSubtaskTests(TestCase):
    """Tests de reprogramación de subtareas (HU 06)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="us06@test.com",
            password="pass",
            name="Usuario US06",
        )
        self.client.force_authenticate(user=self.user)
        self.course = Course.objects.create(name="Curso US06", user=self.user)
        self.activity = Activity.objects.create(
            user=self.user,
            title="Actividad US06",
            course=self.course,
            type=Activity.TypeChoices.OTRO,
            deadline=(timezone.localdate() + timedelta(days=10)),
        )
        self.subtask = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Subtarea a reprogramar",
            estimated_hours=Decimal("2.00"),
            target_date=timezone.localdate() + timedelta(days=2),
        )
        self.url = f"/api/subtareas/{self.subtask.id}/"

    def test_put_update_target_date_success(self):
        """PUT actualiza la fecha objetivo correctamente."""
        new_date = timezone.localdate() + timedelta(days=5)
        payload = {
            "target_date": new_date.isoformat(),
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.subtask.refresh_from_db()
        self.assertEqual(self.subtask.target_date, new_date)
        self.assertIn("message", response.data)
        self.assertIn("daily_load", response.data)

    def test_put_update_target_date_creates_reprogramming_log(self):
        """Al cambiar la fecha, se crea un log de reprogramación."""
        old_date = self.subtask.target_date
        new_date = timezone.localdate() + timedelta(days=3)
        payload = {
            "target_date": new_date.isoformat(),
            "reason": "Reprogramación por conflicto",
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        log = ReprogrammingLog.objects.filter(subtask=self.subtask).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.previous_date, old_date)
        self.assertEqual(log.new_date, new_date)
        self.assertEqual(log.reason, "Reprogramación por conflicto")

    def test_put_update_target_date_with_default_reason(self):
        """Si no se proporciona razón, se usa 'Reprogramación manual'."""
        new_date = timezone.localdate() + timedelta(days=4)
        payload = {
            "target_date": new_date.isoformat(),
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        log = ReprogrammingLog.objects.filter(subtask=self.subtask).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.reason, "Reprogramación manual")

    def test_put_update_target_date_past_date_returns_400(self):
        """No se permite actualizar a una fecha anterior a hoy."""
        past_date = timezone.localdate() - timedelta(days=1)
        payload = {
            "target_date": past_date.isoformat(),
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("no puede ser anterior", response.data["error"])

    def test_put_update_target_date_exceeds_activity_deadline_returns_400(self):
        """No se permite actualizar a una fecha que supere el deadline de la actividad."""
        future_date = self.activity.deadline + timedelta(days=1)
        payload = {
            "target_date": future_date.isoformat(),
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("límite de la actividad", response.data["error"])

    def test_put_update_target_date_within_activity_deadline_success(self):
        """Se permite actualizar a una fecha dentro del deadline de la actividad."""
        valid_date = self.activity.deadline - timedelta(days=1)
        payload = {
            "target_date": valid_date.isoformat(),
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.subtask.refresh_from_db()
        self.assertEqual(self.subtask.target_date, valid_date)

    def test_put_update_estimated_hours_success(self):
        """PUT actualiza las horas estimadas correctamente."""
        payload = {
            "estimated_hours": "3.50",
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.subtask.refresh_from_db()
        self.assertEqual(float(self.subtask.estimated_hours), 3.50)

    def test_put_update_estimated_hours_zero_returns_400(self):
        """Las horas estimadas deben ser mayores a 0."""
        payload = {
            "estimated_hours": "0",
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("mayores a 0", response.data["error"])

    def test_put_update_estimated_hours_negative_returns_400(self):
        """Las horas estimadas negativas no son permitidas."""
        payload = {
            "estimated_hours": "-1.00",
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_put_update_both_target_date_and_estimated_hours_success(self):
        """Se pueden actualizar fecha y horas estimadas simultáneamente."""
        new_date = timezone.localdate() + timedelta(days=6)
        payload = {
            "target_date": new_date.isoformat(),
            "estimated_hours": "4.00",
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.subtask.refresh_from_db()
        self.assertEqual(self.subtask.target_date, new_date)
        self.assertEqual(float(self.subtask.estimated_hours), 4.00)

    def test_put_update_invalid_date_format_returns_400(self):
        """Formato de fecha inválido devuelve 400."""
        payload = {
            "target_date": "2025-13-45",  # Fecha inválida
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("Formato de fecha inválido", response.data["error"])

    def test_put_update_subtask_not_found_returns_404(self):
        """Si la subtarea no existe, devuelve 404."""
        from uuid import uuid4
        fake_id = uuid4()
        url = f"/api/subtareas/{fake_id}/"
        payload = {
            "target_date": (timezone.localdate() + timedelta(days=1)).isoformat(),
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_put_update_subtask_other_user_returns_404(self):
        """No se puede actualizar una subtarea de otro usuario."""
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
        url = f"/api/subtareas/{other_subtask.id}/"
        payload = {
            "target_date": (timezone.localdate() + timedelta(days=1)).isoformat(),
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_put_update_no_changes_returns_200_with_message(self):
        """Si no hay cambios, devuelve 200 con mensaje indicando que no hubo cambios."""
        current_date = self.subtask.target_date
        payload = {
            "target_date": current_date.isoformat(),
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        self.assertIn("No se realizaron cambios", response.data["message"])

    def test_put_update_requires_authentication(self):
        """El endpoint requiere autenticación."""
        self.client.force_authenticate(user=None)
        payload = {
            "target_date": (timezone.localdate() + timedelta(days=1)).isoformat(),
        }

        response = self.client.put(self.url, payload, format="json")

        self.assertIn(response.status_code, [401, 403])

    def test_put_update_activity_without_deadline_allows_any_future_date(self):
        """Si la actividad no tiene deadline, se permite cualquier fecha futura."""
        activity_no_deadline = Activity.objects.create(
            user=self.user,
            title="Actividad sin deadline",
            course=self.course,
            type=Activity.TypeChoices.OTRO,
            deadline=None,
        )
        subtask_no_deadline = Subtask.objects.create(
            user=self.user,
            activity=activity_no_deadline,
            title="Subtarea sin deadline",
            estimated_hours=Decimal("1.00"),
            target_date=timezone.localdate() + timedelta(days=1),
        )
        url = f"/api/subtareas/{subtask_no_deadline.id}/"
        future_date = timezone.localdate() + timedelta(days=30)
        payload = {
            "target_date": future_date.isoformat(),
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        subtask_no_deadline.refresh_from_db()
        self.assertEqual(subtask_no_deadline.target_date, future_date)
