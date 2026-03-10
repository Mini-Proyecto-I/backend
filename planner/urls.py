from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedDefaultRouter
from .views import (
    CourseViewSet,
    ActivityViewSet,
    SubtaskViewSet,
    ReprogrammingLogViewSet,
    TodayView,
    TodayStudyTimeView,
    UpdateSubtaskTargetDateView,
    ConfiguracionView,
    SubtaskCalendarView,
)

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
    # Endpoint para vista "Hoy" con ordenamiento en backend
    path('hoy/', TodayView.as_view(), name='today'),
    # Endpoint para tiempo de estudio de hoy (solo tiempo y estado)
    path('hoy/tiempo/', TodayStudyTimeView.as_view(), name='today-study-time'),
    # Endpoint PUT /api/subtareas/<id>/
    path('subtareas/<uuid:pk>/', UpdateSubtaskTargetDateView.as_view(), name='update-subtask-target-date'),
    # Endpoint GET /api/subtareas/<id>/calendar/
    path('subtareas/<uuid:pk>/calendar/', SubtaskCalendarView.as_view(), name='subtask-calendar'),
    # Endpoint GET y PUT /api/configuracion/
    path('configuracion/', ConfiguracionView.as_view(), name='configuracion'),
]