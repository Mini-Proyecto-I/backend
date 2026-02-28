"""
Pruebas unitarias de la app planner.

Los endpoints se testean con APIClient (peticiones HTTP reales), igual que con
Postman: list, create, retrieve, update, delete. No se requiere sesión ni
usuario autenticado (AllowAny). Desarrollados por: QA Leader (Juan Sebastian Sierra)
"""

from decimal import Decimal
from datetime import date, datetime

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from models import Course, Activity, Subtask, ReprogrammingLog

User = get_user_model()


class CourseModelTests(TestCase):
    """Tests del modelo Course."""

    def test_create_course(self):
        c = Course.objects.create(name="Matemáticas")
        self.assertEqual(c.name, "Matemáticas")
        self.assertIsNotNone(c.id)

    def test_course_str(self):
        c = Course.objects.create(name="Física")
        self.assertEqual(str(c), "Física")

    def test_course_name_unique(self):
        Course.objects.create(name="Único")
        with self.assertRaises(Exception):
            Course.objects.create(name="Único")


class ActivityModelTests(TestCase):
    """Tests del modelo Activity."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="pass", name="Test User"
        )
        self.course = Course.objects.create(name="Curso Test")

    def test_create_activity(self):
        a = Activity.objects.create(
            user=self.user,
            title="Tarea 1",
            description="Desc",
            course=self.course,
        )
        self.assertEqual(a.title, "Tarea 1")
        self.assertEqual(a.user, self.user)
        self.assertEqual(a.course, self.course)


class SubtaskModelTests(TestCase):
    """Tests del modelo Subtask."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="sub@example.com", password="pass", name="User"
        )
        self.activity = Activity.objects.create(
            user=self.user, title="Actividad", course=None
        )

    def test_create_subtask(self):
        s = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Subtarea",
            status=Subtask.Status.PENDIENTE,
        )
        self.assertEqual(s.title, "Subtarea")
        self.assertEqual(s.status, Subtask.Status.PENDIENTE)


class ReprogrammingLogModelTests(TestCase):
    """Tests del modelo ReprogrammingLog."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="log@example.com", password="pass", name="User"
        )
        self.activity = Activity.objects.create(
            user=self.user, title="Act", course=None
        )
        self.subtask = Subtask.objects.create(
            user=self.user, activity=self.activity, title="Sub"
        )

    def test_create_log(self):
        log = ReprogrammingLog.objects.create(
            subtask=self.subtask,
            previous_date=date(2025, 1, 1),
            new_date=date(2025, 1, 5),
            reason="Conflictos",
        )
        self.assertEqual(log.subtask, self.subtask)
        self.assertEqual(log.new_date, date(2025, 1, 5))


# --- Tests de endpoints (API) con APIClient, sin autenticación ---

class CourseEndpointTests(TestCase):
    """Tests de los endpoints de Course (GET list, POST, GET detail, PUT, DELETE)."""

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/course/"

    def test_list_courses_empty(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_list_courses(self):
        Course.objects.create(name="A")
        Course.objects.create(name="B")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_create_course(self):
        response = self.client.post(
            self.url, {"name": "Nuevo curso"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Nuevo curso")
        self.assertIn("id", response.data)

    def test_retrieve_course(self):
        c = Course.objects.create(name="Retrieve")
        response = self.client.get(f"{self.url}{c.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Retrieve")

    def test_update_course(self):
        c = Course.objects.create(name="Antes")
        response = self.client.put(
            f"{self.url}{c.id}/", {"name": "Después"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Después")

    def test_delete_course(self):
        c = Course.objects.create(name="Borrar")
        response = self.client.delete(f"{self.url}{c.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Course.objects.filter(id=c.id).exists())


class ActivityEndpointTests(TestCase):
    """Tests de los endpoints de Activity (sin autenticación; se envía user en el body)."""

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/activity/"
        self.user = User.objects.create_user(
            email="activity@test.com", password="pass", name="Activity User"
        )
        self.course = Course.objects.create(name="Curso API")

    def test_list_activities(self):
        Activity.objects.create(
            user=self.user, title="A1", course=self.course
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "A1")

    def test_create_activity(self):
        payload = {
            "title": "Nueva actividad",
            "description": "Desc",
            "user": self.user.id,
            "course_id": str(self.course.id),
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Nueva actividad")
        self.assertTrue(
            Activity.objects.filter(title="Nueva actividad").exists()
        )

    def test_retrieve_activity(self):
        a = Activity.objects.create(
            user=self.user, title="Detalle", course=self.course
        )
        response = self.client.get(f"{self.url}{a.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Detalle")

    def test_update_activity(self):
        a = Activity.objects.create(
            user=self.user, title="Viejo", course=self.course
        )
        response = self.client.patch(
            f"{self.url}{a.id}/",
            {"title": "Actualizado"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Actualizado")

    def test_delete_activity(self):
        a = Activity.objects.create(
            user=self.user, title="Eliminar", course=self.course
        )
        response = self.client.delete(f"{self.url}{a.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Activity.objects.filter(id=a.id).exists())


class SubtaskEndpointTests(TestCase):
    """Tests de los endpoints de Subtask."""

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/subtask/"
        self.user = User.objects.create_user(
            email="subtask@test.com", password="pass", name="Subtask User"
        )
        self.activity = Activity.objects.create(
            user=self.user, title="Actividad subtask", course=None
        )

    def test_list_subtasks(self):
        Subtask.objects.create(
            user=self.user, activity=self.activity, title="S1"
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_create_subtask(self):
        payload = {
            "title": "Nueva subtarea",
            "user": self.user.id,
            "activity_id": str(self.activity.id),
            "status": "PENDING",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Nueva subtarea")

    def test_retrieve_subtask(self):
        s = Subtask.objects.create(
            user=self.user, activity=self.activity, title="Sub"
        )
        response = self.client.get(f"{self.url}{s.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Sub")

    def test_update_subtask(self):
        s = Subtask.objects.create(
            user=self.user, activity=self.activity, title="Sub"
        )
        response = self.client.patch(
            f"{self.url}{s.id}/",
            {"status": "DONE"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "DONE")

    def test_delete_subtask(self):
        s = Subtask.objects.create(
            user=self.user, activity=self.activity, title="Borrar"
        )
        response = self.client.delete(f"{self.url}{s.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Subtask.objects.filter(id=s.id).exists())


class ReprogrammingLogEndpointTests(TestCase):
    """Tests de los endpoints de ReprogrammingLog."""

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/reprogramming_log/"
        self.user = User.objects.create_user(
            email="log@test.com", password="pass", name="Log User"
        )
        self.activity = Activity.objects.create(
            user=self.user, title="Act", course=None
        )
        self.subtask = Subtask.objects.create(
            user=self.user, activity=self.activity, title="Sub"
        )

    def test_list_logs(self):
        ReprogrammingLog.objects.create(
            subtask=self.subtask,
            previous_date=date(2025, 1, 1),
            new_date=date(2025, 1, 5),
            reason="Razón",
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_create_reprogramming_log(self):
        payload = {
            "subtask_id": str(self.subtask.id),
            "previous_date": "2025-01-01",
            "new_date": "2025-01-10",
            "reason": "Reprogramado por conflicto",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["reason"], "Reprogramado por conflicto")

    def test_retrieve_log(self):
        log = ReprogrammingLog.objects.create(
            subtask=self.subtask,
            previous_date=date(2025, 1, 1),
            new_date=date(2025, 1, 5),
            reason="Ver detalle",
        )
        response = self.client.get(f"{self.url}{log.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["reason"], "Ver detalle")

    def test_delete_log(self):
        log = ReprogrammingLog.objects.create(
            subtask=self.subtask,
            previous_date=date(2025, 1, 1),
            new_date=date(2025, 1, 5),
            reason="Borrar",
        )
        response = self.client.delete(f"{self.url}{log.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ReprogrammingLog.objects.filter(id=log.id).exists())


class NoAuthenticationRequiredTests(TestCase):
    """Comprueba que los endpoints responden sin autenticación (AllowAny)."""

    def setUp(self):
        self.client = APIClient()
        # No se llama a client.credentials() ni client.force_authenticate()

    def test_course_list_without_auth(self):
        response = self.client.get("/api/course/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_activity_list_without_auth(self):
        response = self.client.get("/api/activity/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_subtask_list_without_auth(self):
        response = self.client.get("/api/subtask/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_reprogramming_log_list_without_auth(self):
        response = self.client.get("/api/reprogramming_log/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
