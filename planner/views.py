from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import NotFound
from django.contrib.auth import get_user_model
from .models import Course, Activity, Subtask, ReprogrammingLog
from .serializers import CourseSerializer, ActivitySerializer, SubtaskSerializer, ReprogrammingLogSerializer



User = get_user_model()


class CourseViewSet(ModelViewSet):
    serializer_class = CourseSerializer
    permission_classes = [AllowAny]
    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            return Course.objects.filter(user=user)
        # En desarrollo, sin autenticación se devuelven todos los cursos
        return Course.objects.all()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"detail": "Curso eliminado correctamente."},
            status=204
        )
    
class ActivityViewSet(ModelViewSet):
    serializer_class = ActivitySerializer
    permission_classes = [AllowAny]
    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            return Activity.objects.filter(user=user)
        return Activity.objects.all()
    

class SubtaskViewSet(ModelViewSet):
    serializer_class = SubtaskSerializer
    permission_classes = [AllowAny]
    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            queryset = Subtask.objects.filter(user=user)
        else:
            queryset = Subtask.objects.all()
        activity_id = self.kwargs.get("activity_pk") 
        if activity_id:
            queryset = queryset.filter(activity_id=activity_id)
        return queryset

    def perform_create(self, serializer):
        activity_id = self.kwargs.get("activity_pk")
        user = getattr(self.request, "user", None)
        is_auth = user and getattr(user, "is_authenticated", False)

        if not is_auth:
            # Usuario genérico para entorno de desarrollo sin autenticación
            user, _ = User.objects.get_or_create(
                email="dev@example.com",
                defaults={"password": "devpass", "name": "Dev User"},
            )
            activity_qs = Activity.objects.filter(id=activity_id)
        else:
            activity_qs = Activity.objects.filter(id=activity_id, user=user)

        activity = activity_qs.first()
        if not activity:
            raise NotFound("Actividad no encontrada o no tienes permisos.")
        serializer.save(user=user, activity=activity)
    
class ReprogrammingLogViewSet(ModelViewSet):
    serializer_class = ReprogrammingLogSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            return ReprogrammingLog.objects.filter(subtask__user=user)
        return ReprogrammingLog.objects.all()