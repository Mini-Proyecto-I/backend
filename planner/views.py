from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import Course, Activity, Subtask, ReprogrammingLog
from .serializers import CourseSerializer, ActivitySerializer, SubtaskSerializer, ReprogrammingLogSerializer

# Create your views here.

class CourseViewSet(ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [AllowAny]
    
class ActivityViewSet(ModelViewSet):
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer
    permission_classes = [AllowAny]

class SubtaskViewSet(ModelViewSet):
    queryset = Subtask.objects.all()
    serializer_class = SubtaskSerializer
    permission_classes = [AllowAny]
    
class ReprogrammingLogViewSet(ModelViewSet):
    queryset = ReprogrammingLog.objects.all()
    serializer_class = ReprogrammingLogSerializer
    permission_classes = [AllowAny]