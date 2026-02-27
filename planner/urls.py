from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r'course', CourseViewSet, basename='course')
router.register(r'activity', ActivityViewSet, basename='activity')
router.register(r'subtask', SubtaskViewSet, basename='subtask')
router.register(r'reprogramming_log', ReprogrammingLogViewSet, basename='reprogramming_log')

urlpatterns = [
    path('', include(router.urls)), 
]