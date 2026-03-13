"""
HU 08: Resolver conflicto.

Pruebas para:
- Resolver conflicto moviendo subtarea a otro día (PUT con target_date diferente).
- Resolver conflicto reduciendo horas estimadas (PUT con estimated_hours menor).
- Verificar que después de resolver, el conflicto desaparece.
- Validar que se puede resolver conflicto de múltiples formas.
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


class US08ResolverConflictoTests(TestCase):
    """Tests de resolución de conflictos (HU 08)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="us08@test.com",
            password="pass",
            name="Usuario US08",
            daily_hours_limit=Decimal("6.00"),
        )
        self.client.force_authenticate(user=self.user)
        self.course = Course.objects.create(name="Curso US08", user=self.user)
        self.activity = Activity.objects.create(
            user=self.user,
            title="Actividad US08",
            course=self.course,
            type=Activity.TypeChoices.OTRO,
            deadline=timezone.localdate() + timedelta(days=10),
        )
        self.conflicted_date = timezone.localdate() + timedelta(days=3)
        self.url_template = "/api/subtareas/{}/"

    def test_resolver_conflicto_moviendo_a_otro_dia(self):
        """Se puede resolver conflicto moviendo la subtarea a otro día sin conflicto."""
        # Crear subtareas que suman 5 horas en conflicto_date
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub 1",
            estimated_hours=Decimal("5.00"),
            target_date=self.conflicted_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Subtarea que causa conflicto (2h, total sería 7h > 6h)
        subtask_conflicted = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub con conflicto",
            estimated_hours=Decimal("2.00"),
            target_date=self.conflicted_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Mover a otro día sin conflictos
        new_date = timezone.localdate() + timedelta(days=5)
        url = self.url_template.format(subtask_conflicted.id)
        payload = {
            "target_date": new_date.isoformat(),
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["daily_load"]["has_conflict"])
        subtask_conflicted.refresh_from_db()
        self.assertEqual(subtask_conflicted.target_date, new_date)

    def test_resolver_conflicto_reduciendo_horas(self):
        """Se puede resolver conflicto reduciendo las horas estimadas."""
        # Crear subtareas que suman 5 horas
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub 1",
            estimated_hours=Decimal("5.00"),
            target_date=self.conflicted_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Subtarea que causa conflicto (2h, total sería 7h > 6h)
        subtask_conflicted = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub con conflicto",
            estimated_hours=Decimal("2.00"),
            target_date=self.conflicted_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Reducir horas a 0.5 (total sería 5.5h <= 6h)
        url = self.url_template.format(subtask_conflicted.id)
        payload = {
            "estimated_hours": "0.50",
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["daily_load"]["has_conflict"])
        subtask_conflicted.refresh_from_db()
        self.assertEqual(float(subtask_conflicted.estimated_hours), 0.50)

    def test_resolver_conflicto_moviendo_y_reduciendo_horas(self):
        """Se puede resolver conflicto combinando mover fecha y reducir horas."""
        # Crear subtareas que suman 5 horas
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub 1",
            estimated_hours=Decimal("5.00"),
            target_date=self.conflicted_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Subtarea que causa conflicto (2h, total sería 7h > 6h)
        subtask_conflicted = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub con conflicto",
            estimated_hours=Decimal("2.00"),
            target_date=self.conflicted_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Mover a otro día Y reducir horas
        new_date = timezone.localdate() + timedelta(days=6)
        url = self.url_template.format(subtask_conflicted.id)
        payload = {
            "target_date": new_date.isoformat(),
            "estimated_hours": "1.00",
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["daily_load"]["has_conflict"])
        subtask_conflicted.refresh_from_db()
        self.assertEqual(subtask_conflicted.target_date, new_date)
        self.assertEqual(float(subtask_conflicted.estimated_hours), 1.00)

    def test_resolver_conflicto_moviendo_a_dia_con_menos_carga(self):
        """Se puede resolver conflicto moviendo a un día con menos carga."""
        # Día con conflicto: 5 horas
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub día conflicto",
            estimated_hours=Decimal("5.00"),
            target_date=self.conflicted_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Día sin conflicto: 2 horas
        safe_date = timezone.localdate() + timedelta(days=4)
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub día seguro",
            estimated_hours=Decimal("2.00"),
            target_date=safe_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Subtarea con conflicto (2h en conflicto_date = 7h total)
        subtask_conflicted = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub a mover",
            estimated_hours=Decimal("2.00"),
            target_date=self.conflicted_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Mover a safe_date (total sería 4h <= 6h)
        url = self.url_template.format(subtask_conflicted.id)
        payload = {
            "target_date": safe_date.isoformat(),
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["daily_load"]["has_conflict"])
        self.assertEqual(response.data["daily_load"]["current_hours"], 4.0)

    def test_conflicto_persiste_si_no_se_resuelve(self):
        """Si no se resuelve el conflicto, el warning persiste."""
        # Crear subtareas que suman 5 horas
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub 1",
            estimated_hours=Decimal("5.00"),
            target_date=self.conflicted_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Subtarea que causa conflicto (2h, total sería 7h > 6h)
        subtask_conflicted = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub con conflicto",
            estimated_hours=Decimal("2.00"),
            target_date=self.conflicted_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Intentar reducir a 1.5h (total sería 6.5h > 6h, conflicto persiste)
        url = self.url_template.format(subtask_conflicted.id)
        payload = {
            "estimated_hours": "1.50",
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["daily_load"]["has_conflict"])
        self.assertIn("warning", response.data)

    def test_resolver_conflicto_moviendo_a_dia_vacio(self):
        """Se puede resolver conflicto moviendo a un día completamente vacío."""
        # Subtarea con conflicto en conflicto_date (junto con otras)
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub existente",
            estimated_hours=Decimal("5.00"),
            target_date=self.conflicted_date,
            status=Subtask.Status.PENDIENTE,
        )

        subtask_conflicted = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub a mover",
            estimated_hours=Decimal("2.00"),
            target_date=self.conflicted_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Mover a día vacío
        empty_date = timezone.localdate() + timedelta(days=7)
        url = self.url_template.format(subtask_conflicted.id)
        payload = {
            "target_date": empty_date.isoformat(),
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["daily_load"]["has_conflict"])
        self.assertEqual(response.data["daily_load"]["current_hours"], 2.0)

    def test_resolver_conflicto_reduciendo_horas_al_minimo(self):
        """Se puede resolver conflicto reduciendo horas al mínimo válido (0.5)."""
        # Crear subtareas que suman 5.5 horas
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub 1",
            estimated_hours=Decimal("5.50"),
            target_date=self.conflicted_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Subtarea que causa conflicto (1h, total sería 6.5h > 6h)
        subtask_conflicted = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub con conflicto",
            estimated_hours=Decimal("1.00"),
            target_date=self.conflicted_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Reducir a 0.5h (total sería 6.0h <= 6h)
        url = self.url_template.format(subtask_conflicted.id)
        payload = {
            "estimated_hours": "0.50",
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["daily_load"]["has_conflict"])
        self.assertEqual(response.data["daily_load"]["current_hours"], 6.0)

    def test_resolver_conflicto_moviendo_a_dia_con_otra_subtask_mismo_usuario(self):
        """Se puede resolver conflicto moviendo a un día con otra subtarea del mismo usuario."""
        # Día destino con 3 horas
        destination_date = timezone.localdate() + timedelta(days=5)
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub destino",
            estimated_hours=Decimal("3.00"),
            target_date=destination_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Subtarea con conflicto (2h en conflicto_date con 5h existentes = 7h)
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub conflicto",
            estimated_hours=Decimal("5.00"),
            target_date=self.conflicted_date,
            status=Subtask.Status.PENDIENTE,
        )

        subtask_to_move = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub a mover",
            estimated_hours=Decimal("2.00"),
            target_date=self.conflicted_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Mover a destination_date (total sería 5h <= 6h)
        url = self.url_template.format(subtask_to_move.id)
        payload = {
            "target_date": destination_date.isoformat(),
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["daily_load"]["has_conflict"])
        self.assertEqual(response.data["daily_load"]["current_hours"], 5.0)

    def test_resolver_conflicto_verifica_que_conflicto_desaparece(self):
        """Después de resolver, el conflicto desaparece en la respuesta."""
        # Crear situación de conflicto
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub 1",
            estimated_hours=Decimal("5.00"),
            target_date=self.conflicted_date,
            status=Subtask.Status.PENDIENTE,
        )

        subtask_conflicted = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub conflicto",
            estimated_hours=Decimal("2.00"),
            target_date=self.conflicted_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Primera actualización: conflicto presente
        url = self.url_template.format(subtask_conflicted.id)
        payload1 = {
            "estimated_hours": "1.50",  # Total 6.5h, aún conflicto
        }
        response1 = self.client.put(url, payload1, format="json")
        self.assertTrue(response1.data["daily_load"]["has_conflict"])

        # Segunda actualización: resolver conflicto
        payload2 = {
            "estimated_hours": "0.50",  # Total 5.5h, sin conflicto
        }
        response2 = self.client.put(url, payload2, format="json")

        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertFalse(response2.data["daily_load"]["has_conflict"])
        self.assertNotIn("warning", response2.data)
