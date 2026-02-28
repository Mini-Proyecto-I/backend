from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedDefaultRouter 
from .views import *

# Router principal
router = DefaultRouter()
router.register(r'course', CourseViewSet, basename='course')
router.register(r'activity', ActivityViewSet, basename='activity')
router.register(r'reprogramming_log', ReprogrammingLogViewSet, basename='reprogramming_log')

# Router anidado: subtasks dentro de activities
activity_router = NestedDefaultRouter(router, r'activity', lookup='activity')
activity_router.register(r'subtasks', SubtaskViewSet, basename='activity-subtasks')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(activity_router.urls)),
]