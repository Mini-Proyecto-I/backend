from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import Course, Activity, Subtask, ReprogrammingLog
from .serializers import CourseSerializer, ActivitySerializer, SubtaskSerializer, ReprogrammingLogSerializer

# Create your views here.

class CourseViewSet(ModelViewSet):
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        return Course.objects.filter(user=self.request.user)

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
        return Subtask.objects.filter(user=self.request.user)
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
class ReprogrammingLogViewSet(ModelViewSet):
    serializer_class = ReprogrammingLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ReprogrammingLog.objects.filter(
            subtask__user=self.request.user
        )