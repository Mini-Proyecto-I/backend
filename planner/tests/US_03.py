"""
HU 03: Edición y eliminación de actividades y subtareas.

Pruebas para:
- Actualización (PATCH/PUT) de actividades: título, descripción, curso, fechas.
- Eliminación (DELETE) de actividades e integridad del endpoint.
- Actualización (PATCH/PUT) de subtareas: título, status, estimated_hours, etc.
- Eliminación (DELETE) de subtareas e integridad del endpoint.
- Comportamiento en cascada: eliminar actividad elimina sus subtareas.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from planner.models import Activity, Course, Subtask

User = get_user_model()


class US03ActivityUpdateDeleteTests(TestCase):
    """Tests de edición y eliminación de actividades (HU 03)."""

    def setUp(self):
        self.client = APIClient()
        self.base_url = "/api/activity/"
        self.user = User.objects.create_user(
            email="us03act@test.com",
            password="pass",
            name="Usuario US03 Activity",
        )
        self.course = Course.objects.create(name="Curso US03")
        self.activity = Activity.objects.create(
            user=self.user,
            title="Actividad a editar/eliminar",
            description="Descripción original",
            course=self.course,
        )

    def test_patch_activity_title_success(self):
        """PATCH actualiza solo el título y devuelve 200."""
        response = self.client.patch(
            f"{self.base_url}{self.activity.id}/",
            {"title": "Título actualizado por PATCH"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Título actualizado por PATCH")
        self.activity.refresh_from_db()
        self.assertEqual(self.activity.title, "Título actualizado por PATCH")

    def test_patch_activity_description_success(self):
        """PATCH actualiza solo la descripción."""
        response = self.client.patch(
            f"{self.base_url}{self.activity.id}/",
            {"description": "Nueva descripción"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["description"], "Nueva descripción")

    def test_put_activity_full_update_success(self):
        """PUT con todos los campos actualiza la actividad correctamente."""
        payload = {
            "title": "Título PUT completo",
            "description": "Desc PUT",
            "user": self.user.id,
            "course_id": str(self.course.id),
        }
        response = self.client.put(
            f"{self.base_url}{self.activity.id}/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Título PUT completo")
        self.assertEqual(response.data["description"], "Desc PUT")
        self.activity.refresh_from_db()
        self.assertEqual(self.activity.title, "Título PUT completo")

    def test_delete_activity_returns_204_and_removes_from_db(self):
        """DELETE devuelve 204 y la actividad deja de existir en la BD."""
        activity_id = self.activity.id
        response = self.client.delete(f"{self.base_url}{activity_id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Activity.objects.filter(id=activity_id).exists())

    def test_retrieve_activity_after_update_returns_updated_data(self):
        """Tras un PATCH, GET del detalle devuelve los datos actualizados."""
        self.client.patch(
            f"{self.base_url}{self.activity.id}/",
            {"title": "Título para retrieve"},
            format="json",
        )
        response = self.client.get(f"{self.base_url}{self.activity.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Título para retrieve")

    def test_update_activity_invalid_title_returns_400(self):
        """PATCH con título vacío devuelve 400."""
        response = self.client.patch(
            f"{self.base_url}{self.activity.id}/",
            {"title": ""},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)


class US03SubtaskUpdateDeleteTests(TestCase):
    """Tests de edición y eliminación de subtareas (HU 03)."""

    def setUp(self):
        self.client = APIClient()
        self.base_url = "/api/subtask/"
        self.user = User.objects.create_user(
            email="us03sub@test.com",
            password="pass",
            name="Usuario US03 Subtask",
        )
        self.activity = Activity.objects.create(
            user=self.user,
            title="Actividad para subtareas US03",
            course=None,
        )
        self.subtask = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Subtarea a editar/eliminar",
            status=Subtask.Status.PENDIENTE,
            estimated_hours=2.00,
        )

    def test_patch_subtask_title_success(self):
        """PATCH actualiza solo el título de la subtarea."""
        response = self.client.patch(
            f"{self.base_url}{self.subtask.id}/",
            {"title": "Subtarea título actualizado"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Subtarea título actualizado")
        self.subtask.refresh_from_db()
        self.assertEqual(self.subtask.title, "Subtarea título actualizado")

    def test_patch_subtask_status_success(self):
        """PATCH actualiza el status de la subtarea."""
        response = self.client.patch(
            f"{self.base_url}{self.subtask.id}/",
            {"status": Subtask.Status.REALIZADO},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], Subtask.Status.REALIZADO)
        self.subtask.refresh_from_db()
        self.assertEqual(self.subtask.status, Subtask.Status.REALIZADO)

    def test_patch_subtask_estimated_hours_success(self):
        """PATCH actualiza las horas estimadas."""
        response = self.client.patch(
            f"{self.base_url}{self.subtask.id}/",
            {"estimated_hours": "3.50"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.subtask.refresh_from_db()
        self.assertEqual(float(self.subtask.estimated_hours), 3.50)

    def test_put_subtask_full_update_success(self):
        """PUT con campos completos actualiza la subtarea."""
        payload = {
            "title": "Subtarea PUT completa",
            "user": self.user.id,
            "activity_id": str(self.activity.id),
            "status": Subtask.Status.ESPERA,
            "estimated_hours": "1.25",
        }
        response = self.client.put(
            f"{self.base_url}{self.subtask.id}/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Subtarea PUT completa")
        self.assertEqual(response.data["status"], Subtask.Status.ESPERA)
        self.subtask.refresh_from_db()
        self.assertEqual(self.subtask.title, "Subtarea PUT completa")

    def test_delete_subtask_returns_204_and_removes_from_db(self):
        """DELETE devuelve 204 y la subtarea deja de existir en la BD."""
        subtask_id = self.subtask.id
        response = self.client.delete(f"{self.base_url}{subtask_id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Subtask.objects.filter(id=subtask_id).exists())

    def test_retrieve_subtask_after_update_returns_updated_data(self):
        """Tras un PATCH, GET del detalle devuelve los datos actualizados."""
        self.client.patch(
            f"{self.base_url}{self.subtask.id}/",
            {"title": "Subtarea para retrieve"},
            format="json",
        )
        response = self.client.get(f"{self.base_url}{self.subtask.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Subtarea para retrieve")

    def test_update_subtask_invalid_estimated_hours_returns_400(self):
        """PATCH con estimated_hours <= 0 devuelve 400."""
        response = self.client.patch(
            f"{self.base_url}{self.subtask.id}/",
            {"estimated_hours": "0"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("estimated_hours", response.data)


class US03ActivitySubtaskCascadeTests(TestCase):
    """Integridad: eliminar una actividad elimina sus subtareas (CASCADE)."""

    def setUp(self):
        self.client = APIClient()
        self.activity_url = "/api/activity/"
        self.subtask_url = "/api/subtask/"
        self.user = User.objects.create_user(
            email="us03cascade@test.com",
            password="pass",
            name="Usuario US03 Cascade",
        )
        self.activity = Activity.objects.create(
            user=self.user,
            title="Actividad con subtareas para borrar",
            course=None,
        )
        self.subtask1 = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub 1",
            estimated_hours=1,
        )
        self.subtask2 = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub 2",
            estimated_hours=2,
        )

    def test_delete_activity_cascades_to_subtasks(self):
        """Al eliminar la actividad, sus subtareas también se eliminan."""
        activity_id = self.activity.id
        subtask1_id = self.subtask1.id
        subtask2_id = self.subtask2.id
        response = self.client.delete(f"{self.activity_url}{activity_id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Activity.objects.filter(id=activity_id).exists())
        self.assertFalse(Subtask.objects.filter(id=subtask1_id).exists())
        self.assertFalse(Subtask.objects.filter(id=subtask2_id).exists())

    def test_delete_subtask_does_not_delete_activity(self):
        """Eliminar una subtarea no elimina la actividad."""
        activity_id = self.activity.id
        self.client.delete(f"{self.subtask_url}{self.subtask1.id}/")
        self.assertTrue(Activity.objects.filter(id=activity_id).exists())
        self.assertFalse(Subtask.objects.filter(id=self.subtask1.id).exists())
        self.assertTrue(Subtask.objects.filter(id=self.subtask2.id).exists())
