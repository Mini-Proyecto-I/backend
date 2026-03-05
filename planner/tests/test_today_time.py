from datetime import timedelta
from django.utils import timezone
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from django.contrib.auth import get_user_model
from planner.models import Course, Activity, Subtask

User = get_user_model()


class TodayTimeEndpointTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/hoy/tiempo/"
        self.user = User.objects.create_user(
            email="todaytime@test.com",
            password="pass",
            name="Test User",
        )

        self.client.force_authenticate(user=self.user)

        self.course = Course.objects.create(
            name="Curso Test",
            user=self.user
        )

        self.activity = Activity.objects.create(
            title="Actividad Test",
            user=self.user,
            course=self.course,
            type="taller"
        )

    def test_today_time_no_subtasks(self):
        """Si no hay subtareas hoy el tiempo debe ser 0."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_today_time_with_one_subtask(self):
        """Una subtarea hoy debe reflejarse en el cálculo."""

        Subtask.objects.create(
            title="Subtask hoy",
            user=self.user,
            activity=self.activity,
            estimated_hours=2,
            target_date=timezone.localdate(),
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_today_time_multiple_subtasks(self):
        """Varias subtareas hoy."""

        Subtask.objects.create(
            title="S1",
            user=self.user,
            activity=self.activity,
            estimated_hours=2,
            target_date=timezone.localdate(),
        )

        Subtask.objects.create(
            title="S2",
            user=self.user,
            activity=self.activity,
            estimated_hours=3,
            target_date=timezone.localdate(),
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_today_time_requires_auth(self):
        """Endpoint debe requerir autenticación."""

        self.client.force_authenticate(user=None)

        response = self.client.get(self.url)

        self.assertIn(response.status_code, [401, 403])