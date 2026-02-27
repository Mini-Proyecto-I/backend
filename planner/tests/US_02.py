"""
HU 02: Creación y validación de subtareas.

Pruebas para:
- Creación de subtareas con datos válidos.
- Campos obligatorios: user, title, activity_id.
- Validación de título (no vacío, no solo espacios).
- Validación de estimated_hours (> 0).
- Vinculación correcta a actividades.
- Integridad del endpoint POST /api/subtask/.
"""
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from planner.models import Activity, Subtask

User = get_user_model()


class US02SubtaskCreationValidationTests(TestCase):
    """Tests de creación y validación de subtareas (HU 02)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="us02@test.com",
            password="pass",
            name="Usuario US02",
        )
        self.client.force_authenticate(user=self.user)
        self.activity = Activity.objects.create(
            user=self.user,
            title="Actividad para subtareas US02",
            course=None,
            type=Activity.TypeChoices.OTRO,
        )
        self.url = f"/api/activity/{self.activity.id}/subtasks/"

    def test_create_subtask_with_required_fields_success(self):
        """Se puede crear una subtarea con user, title, activity_id y estimated_hours > 0."""
        payload = {
            "title": "Subtarea mínima",
            "estimated_hours": "1.50",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Subtarea mínima")
        self.assertEqual(response.data["status"], Subtask.Status.PENDIENTE)
        self.assertTrue(
            Subtask.objects.filter(
                title="Subtarea mínima", activity=self.activity, user=self.user
            ).exists()
        )

    def test_create_subtask_is_linked_to_activity(self):
        """La subtarea creada queda vinculada a la actividad indicada en activity_id."""
        payload = {
            "title": "Subtarea vinculada",
            "estimated_hours": "2.00",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("activity", response.data)
        self.assertEqual(response.data["activity"]["id"], str(self.activity.id))
        self.assertEqual(response.data["activity"]["title"], self.activity.title)
        subtask_id = response.data["id"]
        subtask = Subtask.objects.get(id=subtask_id)
        self.assertEqual(subtask.activity_id, self.activity.id)

    def test_create_subtask_missing_title_returns_400(self):
        """El título es obligatorio: si falta, se devuelve 400."""
        payload = {
            "estimated_hours": "1.00",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)

    def test_create_subtask_blank_title_returns_400(self):
        """El título vacío no es permitido."""
        payload = {
            "title": "",
            "estimated_hours": "1.00",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)

    def test_create_subtask_whitespace_title_returns_400(self):
        """Título solo con espacios dispara la validación personalizada."""
        payload = {
            "title": "   ",
            "estimated_hours": "1.00",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)
        self.assertIn(
            "El título de la subtarea no puede estar vacío.",
            response.data["title"],
        )

    def test_create_subtask_without_auth_returns_401(self):
        """El endpoint anidado de subtareas requiere autenticación."""
        self.client.force_authenticate(user=None)
        payload = {
            "title": "Sin auth",
            "estimated_hours": "1.00",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_subtask_estimated_hours_zero_returns_400(self):
        """Las horas estimadas deben ser mayores a 0."""
        payload = {
            "title": "Horas cero",
            "user": self.user.id,
            "activity_id": str(self.activity.id),
            "estimated_hours": "0.00",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("estimated_hours", response.data)
        self.assertIn(
            "Las horas estimadas deben ser mayores a 0.",
            response.data["estimated_hours"],
        )

    def test_create_subtask_estimated_hours_negative_returns_400(self):
        """Horas estimadas negativas no son permitidas."""
        payload = {
            "title": "Horas negativas",
            "user": self.user.id,
            "activity_id": str(self.activity.id),
            "estimated_hours": "-1.00",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("estimated_hours", response.data)

    def test_create_subtask_with_status_success(self):
        """Se puede crear una subtarea con un status válido."""
        payload = {
            "title": "Subtarea en espera",
            "user": self.user.id,
            "activity_id": str(self.activity.id),
            "estimated_hours": "1.00",
            "status": Subtask.Status.ESPERA,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], Subtask.Status.ESPERA)

    def test_list_subtasks_includes_activity(self):
        """Al listar subtareas, cada una incluye la actividad vinculada."""
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub 1",
            estimated_hours=1,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)
        first = response.data[0]
        self.assertIn("activity", first)
        self.assertIn("id", first["activity"])
        self.assertIn("title", first["activity"])
