from datetime import timedelta
from django.utils import timezone
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

from planner.models import Course, Activity, Subtask


User = get_user_model()


class TodayViewTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/hoy/"

        self.user = User.objects.create_user(
            email="test@test.com",
            password="pass",
            name="Test User"
        )

        self.client.force_authenticate(user=self.user)

        self.course = Course.objects.create(
            name="Matematicas",
            user=self.user
        )

        self.activity = Activity.objects.create(
            title="Examen",
            user=self.user,
            course=self.course,
            type="examen"
        )

    def test_returns_empty_when_no_subtasks(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_vencidas"], 0)
        self.assertEqual(response.data["total_para_hoy"], 0)
        self.assertEqual(response.data["total_proximas"], 0)

    def test_subtask_for_today(self):
        Subtask.objects.create(
            title="Estudiar",
            user=self.user,
            activity=self.activity,
            estimated_hours=2,
            target_date=timezone.localdate()
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_para_hoy"], 1)

    def test_overdue_subtask(self):
        Subtask.objects.create(
            title="Tarea vieja",
            user=self.user,
            activity=self.activity,
            estimated_hours=1,
            target_date=timezone.localdate() - timedelta(days=1)
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_vencidas"], 1)

    def test_future_subtask(self):
        Subtask.objects.create(
            title="Tarea futura",
            user=self.user,
            activity=self.activity,
            estimated_hours=3,
            target_date=timezone.localdate() + timedelta(days=3)
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_proximas"], 1)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.url)

        self.assertIn(response.status_code, [401, 403])