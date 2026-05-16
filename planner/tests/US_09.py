"""
US 09: Posponer subtarea (Posponed Log).

Pruebas para:
- Posponer una subtarea mediante el endpoint personalizado.
- Verificar que se cambie el estado a POSPUESTO.
- Verificar que se cree el registro en PosponedLog.
- Listar notas de posposición por subtarea.
- Validaciones de seguridad en el acceso a los logs.
"""
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from planner.models import Activity, Course, PosponedLog, Subtask

User = get_user_model()


class US09PosponedLogTests(TestCase):
    """Tests de posposición de subtareas y PosponedLog (US 09)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="us09@test.com",
            password="pass",
            name="Usuario US09",
            daily_hours_limit=Decimal("6.00"),
        )
        self.other_user = User.objects.create_user(
            email="other09@test.com",
            password="pass",
            name="Otro Usuario",
            daily_hours_limit=Decimal("6.00"),
        )
        self.client.force_authenticate(user=self.user)
        self.course = Course.objects.create(name="Curso US09", user=self.user)
        self.activity_deadline = timezone.localdate() + timedelta(days=10)
        self.activity = Activity.objects.create(
            user=self.user,
            title="Actividad US09",
            course=self.course,
            type=Activity.TypeChoices.OTRO,
            deadline=self.activity_deadline,
        )
        self.subtask_target_date = timezone.localdate() + timedelta(days=1)
        self.subtask = Subtask.objects.create(
            user=self.user,
            activity=self.activity,
            title="Subtarea a posponer",
            estimated_hours=Decimal("2.00"),
            target_date=self.subtask_target_date,
            status=Subtask.Status.PENDIENTE,
        )
        self.postpone_url = f"/api/activity/{self.activity.id}/subtasks/{self.subtask.id}/postpone/"

    def test_posponer_subtarea_exitoso(self):
        """Validar que una subtarea se puede posponer y genera el log adecuadamente."""
        payload = {
            "execution_note": "No tuve tiempo hoy."
        }
        response = self.client.patch(self.postpone_url, payload, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("subtask", response.data)
        self.assertIn("posponed_log", response.data)
        self.assertEqual(response.data["subtask"]["status"], Subtask.Status.POSPUESTO)
        self.assertEqual(response.data["posponed_log"]["note"], "No tuve tiempo hoy.")
        
        self.subtask.refresh_from_db()
        self.assertEqual(self.subtask.status, Subtask.Status.POSPUESTO)
        
        logs = PosponedLog.objects.filter(subtask=self.subtask)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().note, "No tuve tiempo hoy.")

    def test_posponer_subtarea_sin_nota(self):
        """Validar que se puede posponer sin nota, asumiendo string vacío."""
        payload = {
            "execution_note": ""
        }
        response = self.client.patch(self.postpone_url, payload, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.subtask.refresh_from_db()
        self.assertEqual(self.subtask.status, Subtask.Status.POSPUESTO)
        
        log = PosponedLog.objects.get(subtask=self.subtask)
        self.assertEqual(log.note, "")

    def test_obtener_notas_por_subtarea(self):
        """Validar que se pueden listar las notas de una subtarea específica."""
        PosponedLog.objects.create(subtask=self.subtask, note="Primera vez pospuesta")
        PosponedLog.objects.create(subtask=self.subtask, note="Sigo sin tiempo")
        
        url = f"/api/posponed_log/notes-of-subtask/{self.subtask.id}/"
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Deberían retornar las dos notas creadas
        self.assertEqual(len(response.data), 2)
        notes = [item["note"] for item in response.data]
        self.assertIn("Primera vez pospuesta", notes)
        self.assertIn("Sigo sin tiempo", notes)

    def test_obtener_notas_subtarea_otro_usuario(self):
        """Validar seguridad al obtener notas de una subtarea que no es del usuario."""
        other_course = Course.objects.create(name="Otro Curso", user=self.other_user)
        other_activity = Activity.objects.create(
            user=self.other_user, title="Otra Act", course=other_course,
            type=Activity.TypeChoices.OTRO, deadline=timezone.localdate() + timedelta(days=10)
        )
        other_subtask = Subtask.objects.create(
            user=self.other_user, activity=other_activity, title="Privado",
            estimated_hours=Decimal("1.00"), target_date=timezone.localdate(),
            status=Subtask.Status.PENDIENTE
        )
        PosponedLog.objects.create(subtask=other_subtask, note="Debería estar oculto")
        
        url = f"/api/posponed_log/notes-of-subtask/{other_subtask.id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_obtener_notas_subtarea_invalida_o_inexistente(self):
        """Validar que devuelva el código correcto con UUID inválido o inexistente."""
        url_invalido = "/api/posponed_log/notes-of-subtask/no-es-uuid/"
        response = self.client.get(url_invalido)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        url_inexistente = f"/api/posponed_log/notes-of-subtask/{uuid.uuid4()}/"
        response = self.client.get(url_inexistente)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_posponer_subtarea_de_otro_usuario(self):
        """Validar que no se pueda posponer la subtarea de otra persona."""
        other_course = Course.objects.create(name="Otro Curso", user=self.other_user)
        other_activity = Activity.objects.create(
            user=self.other_user, title="Otra Act", course=other_course,
            type=Activity.TypeChoices.OTRO, deadline=timezone.localdate() + timedelta(days=10)
        )
        other_subtask = Subtask.objects.create(
            user=self.other_user, activity=other_activity, title="Privado",
            estimated_hours=Decimal("1.00"), target_date=timezone.localdate(),
            status=Subtask.Status.PENDIENTE
        )
        
        postpone_other_url = f"/api/activity/{other_activity.id}/subtasks/{other_subtask.id}/postpone/"
        payload = {"execution_note": "Ataque"}
        response = self.client.patch(postpone_other_url, payload, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_listar_mis_posponed_logs(self):
        """El endpoint general de PosponedLog devuelve solo los logs del usuario."""
        PosponedLog.objects.create(subtask=self.subtask, note="Mi log")
        
        other_course = Course.objects.create(name="O", user=self.other_user)
        other_act = Activity.objects.create(
            user=self.other_user, title="O", course=other_course,
            type=Activity.TypeChoices.OTRO, deadline=timezone.localdate() + timedelta(days=5)
        )
        other_sub = Subtask.objects.create(
            user=self.other_user, activity=other_act, title="O",
            estimated_hours=Decimal("1.00"), target_date=timezone.localdate(),
            status=Subtask.Status.PENDIENTE
        )
        PosponedLog.objects.create(subtask=other_sub, note="Log del otro")
        
        response = self.client.get("/api/posponed_log/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Debo ver solo 1 log, el asociado a self.subtask
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["note"], "Mi log")

