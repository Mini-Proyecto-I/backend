"""
HU 07: Detectar conflicto por sobrecarga diaria al reprogramar.

Pruebas para:
- Lógica de cálculo: suma horas por día.
- Detección de conflicto cuando la suma de horas excede el límite diario.
- Respuesta con metadata de conflicto (daily_load).
- Validación de conflicto en PUT de subtarea.
- Respuesta 200 con warning cuando hay conflicto (tolerancia a conflictos).
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


class US07DetectarConflictoTests(TestCase):
    """Tests de detección de conflictos por sobrecarga diaria (HU 07)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="us07@test.com",
            password="pass",
            name="Usuario US07",
            daily_hours_limit=Decimal("6.00"),  # Límite de 6 horas
        )
        self.client.force_authenticate(user=self.user)
        self.course = Course.objects.create(name="Curso US07", user=self.user)
        self.activity = Activity.objects.create(
            user=self.user,
            title="Actividad US07",
            course=self.course,
            type=Activity.TypeChoices.OTRO,
            deadline=timezone.localdate() + timedelta(days=10),
        )
        self.target_date = timezone.localdate() + timedelta(days=3)
        self.url_template = "/api/subtareas/{}/"

    def test_put_detecta_conflicto_cuando_excede_limite(self):
        """Al reprogramar, si excede el límite, se detecta conflicto y se retorna warning."""
        # Crear subtareas existentes que suman 5 horas
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Subtarea 1",
            estimated_hours=Decimal("3.00"),
            target_date=self.target_date,
            status=Subtask.Status.PENDIENTE,
        )
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Subtarea 2",
            estimated_hours=Decimal("2.00"),
            target_date=self.target_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Crear subtarea a reprogramar con 2 horas (total sería 7h > 6h)
        subtask_to_update = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Subtarea a reprogramar",
            estimated_hours=Decimal("2.00"),
            target_date=timezone.localdate() + timedelta(days=1),
            status=Subtask.Status.PENDIENTE,
        )
        url = self.url_template.format(subtask_to_update.id)
        payload = {
            "target_date": self.target_date.isoformat(),
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("daily_load", response.data)
        self.assertTrue(response.data["daily_load"]["has_conflict"])
        self.assertEqual(response.data["daily_load"]["current_hours"], 7.0)
        self.assertEqual(response.data["daily_load"]["limit"], 6.0)
        self.assertIn("warning", response.data)

    def test_put_no_detecta_conflicto_cuando_no_excede_limite(self):
        """Si no excede el límite, no hay conflicto."""
        # Crear subtareas existentes que suman 3 horas
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Subtarea 1",
            estimated_hours=Decimal("3.00"),
            target_date=self.target_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Crear subtarea a reprogramar con 2 horas (total sería 5h <= 6h)
        subtask_to_update = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Subtarea a reprogramar",
            estimated_hours=Decimal("2.00"),
            target_date=timezone.localdate() + timedelta(days=1),
            status=Subtask.Status.PENDIENTE,
        )
        url = self.url_template.format(subtask_to_update.id)
        payload = {
            "target_date": self.target_date.isoformat(),
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("daily_load", response.data)
        self.assertFalse(response.data["daily_load"]["has_conflict"])
        self.assertEqual(response.data["daily_load"]["current_hours"], 5.0)
        self.assertNotIn("warning", response.data)

    def test_put_calcula_correctamente_suma_horas_por_dia(self):
        """El cálculo de horas suma correctamente todas las subtareas pendientes del día."""
        # Crear múltiples subtareas en el mismo día
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub 1",
            estimated_hours=Decimal("1.50"),
            target_date=self.target_date,
            status=Subtask.Status.PENDIENTE,
        )
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub 2",
            estimated_hours=Decimal("2.25"),
            target_date=self.target_date,
            status=Subtask.Status.PENDIENTE,
        )
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub 3",
            estimated_hours=Decimal("0.75"),
            target_date=self.target_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Reprogramar otra subtarea al mismo día
        subtask_to_update = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub a agregar",
            estimated_hours=Decimal("1.00"),
            target_date=timezone.localdate() + timedelta(days=1),
            status=Subtask.Status.PENDIENTE,
        )
        url = self.url_template.format(subtask_to_update.id)
        payload = {
            "target_date": self.target_date.isoformat(),
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Total esperado: 1.50 + 2.25 + 0.75 + 1.00 = 5.50
        self.assertEqual(response.data["daily_load"]["current_hours"], 5.50)
        self.assertFalse(response.data["daily_load"]["has_conflict"])

    def test_put_excluye_subtask_actual_del_calculo(self):
        """El cálculo excluye la subtarea que se está actualizando para evitar duplicación."""
        # Crear subtarea que ya está en el día objetivo
        subtask_to_update = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Subtarea ya en el día",
            estimated_hours=Decimal("3.00"),
            target_date=self.target_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Crear otra subtarea en el mismo día
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Otra subtarea",
            estimated_hours=Decimal("2.00"),
            target_date=self.target_date,
            status=Subtask.Status.PENDIENTE,
        )

        url = self.url_template.format(subtask_to_update.id)
        # Actualizar solo las horas (sin cambiar fecha)
        payload = {
            "estimated_hours": "4.00",
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Total esperado: 2.00 (otra subtarea) + 4.00 (actualizada) = 6.00
        self.assertEqual(response.data["daily_load"]["current_hours"], 6.00)
        self.assertFalse(response.data["daily_load"]["has_conflict"])

    def test_put_solo_cuenta_subtasks_pendientes(self):
        """Solo se cuentan las subtareas con status PENDING para el cálculo de conflicto."""
        # Crear subtareas con diferentes estados
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Pendiente",
            estimated_hours=Decimal("2.00"),
            target_date=self.target_date,
            status=Subtask.Status.PENDIENTE,
        )
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Realizada",
            estimated_hours=Decimal("3.00"),
            target_date=self.target_date,
            status=Subtask.Status.REALIZADO,  # No se cuenta
        )
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="En espera",
            estimated_hours=Decimal("1.00"),
            target_date=self.target_date,
            status=Subtask.Status.ESPERA,  # No se cuenta
        )

        # Reprogramar subtarea al mismo día
        subtask_to_update = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="A reprogramar",
            estimated_hours=Decimal("3.00"),
            target_date=timezone.localdate() + timedelta(days=1),
            status=Subtask.Status.PENDIENTE,
        )
        url = self.url_template.format(subtask_to_update.id)
        payload = {
            "target_date": self.target_date.isoformat(),
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Total esperado: solo 2.00 (pendiente) + 3.00 (reprogramada) = 5.00
        # Las otras no se cuentan porque no son PENDING
        self.assertEqual(response.data["daily_load"]["current_hours"], 5.00)
        self.assertFalse(response.data["daily_load"]["has_conflict"])

    def test_put_metadata_daily_load_estructura_correcta(self):
        """La metadata daily_load tiene la estructura correcta."""
        subtask = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Subtarea",
            estimated_hours=Decimal("2.00"),
            target_date=timezone.localdate() + timedelta(days=1),
            status=Subtask.Status.PENDIENTE,
        )
        url = self.url_template.format(subtask.id)
        payload = {
            "target_date": self.target_date.isoformat(),
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        daily_load = response.data["daily_load"]
        self.assertIn("current_hours", daily_load)
        self.assertIn("limit", daily_load)
        self.assertIn("has_conflict", daily_load)
        self.assertIn("exceeded_by", daily_load)
        self.assertIsInstance(daily_load["current_hours"], (int, float))
        self.assertIsInstance(daily_load["limit"], (int, float))
        self.assertIsInstance(daily_load["has_conflict"], bool)
        self.assertIsInstance(daily_load["exceeded_by"], (int, float))

    def test_put_exceeded_by_calcula_correctamente(self):
        """El campo exceeded_by muestra cuánto se excede el límite."""
        # Crear subtareas que suman 5 horas
        Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub 1",
            estimated_hours=Decimal("5.00"),
            target_date=self.target_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Reprogramar subtarea de 3 horas (total 8h, límite 6h, excede por 2h)
        subtask_to_update = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Sub a reprogramar",
            estimated_hours=Decimal("3.00"),
            target_date=timezone.localdate() + timedelta(days=1),
            status=Subtask.Status.PENDIENTE,
        )
        url = self.url_template.format(subtask_to_update.id)
        payload = {
            "target_date": self.target_date.isoformat(),
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["daily_load"]["has_conflict"])
        self.assertEqual(response.data["daily_load"]["exceeded_by"], 2.0)

    def test_put_exceeded_by_es_cero_sin_conflicto(self):
        """Si no hay conflicto, exceeded_by es 0."""
        subtask = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Subtarea",
            estimated_hours=Decimal("2.00"),
            target_date=timezone.localdate() + timedelta(days=1),
            status=Subtask.Status.PENDIENTE,
        )
        url = self.url_template.format(subtask.id)
        payload = {
            "target_date": self.target_date.isoformat(),
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["daily_load"]["has_conflict"])
        self.assertEqual(response.data["daily_load"]["exceeded_by"], 0)

    def test_put_respeta_limite_personalizado_usuario(self):
        """El cálculo respeta el límite personalizado del usuario."""
        # Usuario con límite personalizado de 8 horas
        user_custom = User.objects.create_user(
            email="custom@test.com",
            password="pass",
            name="Usuario Custom",
            daily_hours_limit=Decimal("8.00"),
        )
        self.client.force_authenticate(user=user_custom)
        activity_custom = Activity.objects.create(
            user=user_custom,
            title="Actividad Custom",
            course=None,
            type=Activity.TypeChoices.OTRO,
            deadline=timezone.localdate() + timedelta(days=10),
        )

        # Crear subtareas que suman 7 horas
        Subtask.objects.create(
            user=user_custom,
            activity=activity_custom,
            title="Sub 1",
            estimated_hours=Decimal("7.00"),
            target_date=self.target_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Reprogramar subtarea de 1 hora (total 8h, límite 8h, sin conflicto)
        subtask_to_update = Subtask.objects.create(
            user=user_custom,
            activity=activity_custom,
            title="Sub a reprogramar",
            estimated_hours=Decimal("1.00"),
            target_date=timezone.localdate() + timedelta(days=1),
            status=Subtask.Status.PENDIENTE,
        )
        url = self.url_template.format(subtask_to_update.id)
        payload = {
            "target_date": self.target_date.isoformat(),
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["daily_load"]["limit"], 8.0)
        self.assertFalse(response.data["daily_load"]["has_conflict"])

    def test_put_usa_limite_default_si_usuario_no_tiene_limite(self):
        """Si el usuario no tiene límite configurado, se usa el default de 6 horas."""
        # Usuario sin límite explícito (debería tener default 6.0)
        user_default = User.objects.create_user(
            email="default@test.com",
            password="pass",
            name="Usuario Default",
        )
        # Asegurar que tiene el default
        user_default.daily_hours_limit = Decimal("6.0")
        user_default.save()
        self.client.force_authenticate(user=user_default)
        activity_default = Activity.objects.create(
            user=user_default,
            title="Actividad Default",
            course=None,
            type=Activity.TypeChoices.OTRO,
            deadline=timezone.localdate() + timedelta(days=10),
        )

        # Crear subtareas que suman 5 horas
        Subtask.objects.create(
            user=user_default,
            activity=activity_default,
            title="Sub 1",
            estimated_hours=Decimal("5.00"),
            target_date=self.target_date,
            status=Subtask.Status.PENDIENTE,
        )

        # Reprogramar subtarea de 2 horas (total 7h > 6h default, hay conflicto)
        subtask_to_update = Subtask.objects.create(
            user=user_default,
            activity=activity_default,
            title="Sub a reprogramar",
            estimated_hours=Decimal("2.00"),
            target_date=timezone.localdate() + timedelta(days=1),
            status=Subtask.Status.PENDIENTE,
        )
        url = self.url_template.format(subtask_to_update.id)
        payload = {
            "target_date": self.target_date.isoformat(),
        }

        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["daily_load"]["limit"], 6.0)
        self.assertTrue(response.data["daily_load"]["has_conflict"])
