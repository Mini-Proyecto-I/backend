from datetime import timedelta, date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from planner.models import Activity, Course


User = get_user_model()


class US01ActivityCreationValidationTests(TestCase):
    """
    HU 01: Validación de creación de actividades.

    Estas pruebas verifican:
    - Campos obligatorios (user, title).
    - Validación de título (no vacío / solo espacios).
    - Restricción de fecha de evento en el pasado.
    - Coherencia entre fecha de evento y deadline.
    - Integridad general del endpoint de creación.
    """

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/activity/"
        self.user = User.objects.create_user(
            email="us01@test.com",
            password="pass",
            name="Usuario US01",
        )
        self.client.force_authenticate(user=self.user)
        self.course = Course.objects.create(name="Curso US01", user=self.user)

    def test_create_activity_with_minimal_required_fields_success(self):
        """Se puede crear una actividad solo con los campos obligatorios."""
        payload = {
            "title": "Actividad mínima",
            "type": Activity.TypeChoices.OTRO,
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Actividad mínima")
        self.assertIsNone(response.data.get("event_datetime"))
        self.assertIsNone(response.data.get("deadline"))
        self.assertIsNone(response.data.get("course"))
        self.assertTrue(
            Activity.objects.filter(title="Actividad mínima", user=self.user).exists()
        )

    def test_create_activity_missing_title_returns_400(self):
        """El título es obligatorio: si falta, se devuelve 400."""
        payload = {
            "type": Activity.TypeChoices.OTRO,
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)

    def test_create_activity_blank_title_returns_400(self):
        """El título vacío ('') no es permitido."""
        payload = {
            "title": "",
            "type": Activity.TypeChoices.OTRO,
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)

    def test_create_activity_whitespace_title_uses_custom_validation(self):
        """Título solo con espacios dispara la validación personalizada."""
        payload = {
            "title": "   ",
            "type": Activity.TypeChoices.OTRO,
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)
        # Mensaje definido en ActivitySerializer.validate_title
        self.assertIn("El título no puede estar vacío.", response.data["title"])

    def test_create_activity_without_auth_in_dev_mode_creates_successfully(self):
        """En modo desarrollo, sin autenticación también se puede crear la actividad."""
        self.client.force_authenticate(user=None)
        payload = {
            "title": "Sin usuario",
            "type": Activity.TypeChoices.OTRO,
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_activity_with_past_event_datetime_returns_400(self):
        """No se permite crear una actividad con fecha de evento en el pasado."""
        past_datetime = timezone.now() - timedelta(hours=1)

        payload = {
            "title": "Evento pasado",
            "type": Activity.TypeChoices.OTRO,
            "course_id": str(self.course.id),
            "event_datetime": past_datetime.isoformat().replace("+00:00", "Z"),
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("event_datetime", response.data)
        self.assertIn(
            "La fecha de la actividad no puede ser anterior a la actual.",
            response.data["event_datetime"],
        )

    def test_create_activity_with_deadline_before_event_datetime_returns_400(self):
        """
        Si se envía deadline antes que la fecha del evento,
        se rechaza la creación con error en deadline.
        """
        future_datetime = timezone.now() + timedelta(days=2)
        # Deadline ANTES del día del evento
        invalid_deadline = (future_datetime - timedelta(days=1)).date()

        payload = {
            "title": "Fechas inconsistentes",
            "type": Activity.TypeChoices.OTRO,
            "course_id": str(self.course.id),
            "event_datetime": future_datetime.isoformat().replace("+00:00", "Z"),
            "deadline": invalid_deadline.isoformat(),
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("deadline", response.data)
        self.assertIn(
            "La fecha límite no puede ser anterior a la fecha del evento.",
            response.data["deadline"],
        )

    def test_create_activity_with_valid_event_and_deadline_success(self):
        """Con fechas coherentes, la actividad se crea correctamente."""
        future_datetime = timezone.now() + timedelta(days=1)
        valid_deadline = (future_datetime + timedelta(days=1)).date()

        payload = {
            "title": "Actividad con fechas válidas",
            "type": Activity.TypeChoices.OTRO,
            "course_id": str(self.course.id),
            "event_datetime": future_datetime.isoformat().replace("+00:00", "Z"),
            "deadline": valid_deadline.isoformat(),
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Actividad con fechas válidas")
        self.assertIsNotNone(response.data["event_datetime"])
        self.assertEqual(response.data["deadline"], valid_deadline.isoformat())

    def test_create_activity_with_course_id_sets_course(self):
        """Al enviar course_id se asocia correctamente el curso a la actividad."""
        payload = {
            "title": "Actividad con curso",
            "type": Activity.TypeChoices.OTRO,
            "course_id": str(self.course.id),
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        activity_id = response.data["id"]
        activity = Activity.objects.get(id=activity_id)
        self.assertEqual(activity.course, self.course)

    def test_create_activity_with_duplicated_title_is_allowed(self):
        """El modelo no define unicidad de título, así que se permite duplicar."""
        payload = {
            "title": "Título único",
            "type": Activity.TypeChoices.OTRO,
        }

        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

