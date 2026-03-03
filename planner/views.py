from django.shortcuts import render
from django.contrib.auth import get_user_model
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound

from .models import Course, Activity, Subtask, ReprogrammingLog
from .serializers import CourseSerializer, ActivitySerializer, SubtaskSerializer, ReprogrammingLogSerializer


User = get_user_model()


class CourseViewSet(ModelViewSet):
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Siempre se filtra por el usuario autenticado
        return Course.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"detail": "Curso eliminado correctamente."},
            status=204
        )
    
class ActivityViewSet(ModelViewSet):
    serializer_class = ActivitySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Activity.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SubtaskViewSet(ModelViewSet):
    serializer_class = SubtaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Devuelve solo las subtareas del usuario autenticado y, si se pasa activity_pk,
        las filtra por esa actividad.
        """
        queryset = Subtask.objects.filter(user=self.request.user)
        activity_id = self.kwargs.get("activity_pk")
        if activity_id:
            queryset = queryset.filter(activity_id=activity_id)
        return queryset

    def perform_create(self, serializer):
        activity_id = self.kwargs.get("activity_pk")
        activity = Activity.objects.filter(id=activity_id, user=self.request.user).first()
        if not activity:
            raise NotFound("Actividad no encontrada o no tienes permisos.")
        serializer.save(user=self.request.user, activity=activity)


class ReprogrammingLogViewSet(ModelViewSet):
    serializer_class = ReprogrammingLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Solo logs de subtareas pertenecientes al usuario autenticado
        return ReprogrammingLog.objects.filter(subtask__user=self.request.user)