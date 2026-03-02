from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework.exceptions import NotFound
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from drf_spectacular.utils import extend_schema, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from .models import Course, Activity, Subtask, ReprogrammingLog
from .serializers import (
    CourseSerializer, ActivitySerializer, SubtaskSerializer, 
    ReprogrammingLogSerializer, TodaySubtaskSerializer
)



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


class TodayView(APIView):
    """
    Vista "Hoy" - Endpoint para obtener subtareas agrupadas y ordenadas.
    
    Este endpoint implementa la lógica de ordenamiento en el backend según las reglas:
    1. Agrupa en: Vencidas / Para hoy / Próximas
    2. Orden: Vencidas primero (más antiguas arriba), luego Para hoy, luego Próximas por fecha más cercana
    3. Desempate: menor esfuerzo estimado primero
    
    Requiere autenticación: solo usuarios autenticados pueden ver sus propias subtareas.
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Obtener subtareas para la vista 'Hoy'",
        description="""
        Endpoint que devuelve subtareas agrupadas y ordenadas según reglas específicas.
        
        **Regla de ordenamiento (implementada en backend):**
        - Vencidas: ordenadas por fecha más antigua primero, luego por menor esfuerzo
        - Para hoy: ordenadas por menor esfuerzo primero
        - Próximas: ordenadas por fecha más cercana primero, luego por menor esfuerzo
        
        **Query params opcionales:**
        - status: Filtrar por estado (PENDING, DONE, WAITING, POSTPONED)
        - days_ahead: Limitar cuántos días hacia adelante incluir en "Próximas" (si no se envía, se incluyen todas desde mañana)
        """,
        responses={
            200: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                'Respuesta exitosa',
                value={
                    'vencidas': [
                        {
                            'id': 'uuid',
                            'title': 'Subtarea vencida',
                            'target_date': '2024-01-10',
                            'estimated_hours': '2.00',
                            'status': 'PENDING',
                            'activity': {
                                'id': 'uuid',
                                'title': 'Actividad',
                                'course': {'id': 'uuid', 'name': 'Curso'}
                            }
                        }
                    ],
                    'para_hoy': [],
                    'proximas': [],
                    'regla_ordenamiento': 'Vencidas primero (más antiguas arriba), luego Para hoy, luego Próximas por fecha más cercana. Desempate: menor esfuerzo estimado primero.',
                    'fecha_referencia': '2026-01-15'
                },
                response_only=True,
            ),
        ],
    )
    def get(self, request):
        """
        Obtener subtareas agrupadas y ordenadas para la vista "Hoy".
        1. Se obtienen todas las subtareas del usuario
        2. Se clasifican en grupos (Vencidas, Para hoy, Próximas)
        3. Se ordenan según las reglas especificadas
        4. Se devuelven agrupadas con la regla de ordenamiento visible
        
        Returns:
            Response: JSON con subtareas agrupadas y ordenadas
        """
        user = request.user
        
        # Obtener query params opcionales
        # - status: filtra subtareas por estado (PENDING, DONE, WAITING, POSTPONED)
        # - days_ahead: si se envía, limita "próximas" a N días; si no, incluye todas desde mañana
        status_filter = request.query_params.get('status', None)
        days_ahead_param = request.query_params.get('days_ahead', None)
        days_ahead = int(days_ahead_param) if days_ahead_param is not None else None
        
        # btener fecha de referencia (hoy) 
        today = timezone.localdate()
        
        # Obtener subtareas del usuario 
        queryset = Subtask.objects.filter(
            user=user,
            target_date__isnull=False  # Solo subtareas con fecha
        )
        
        # Filtrar por estado si se proporciona el query param status
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Obtener todas las subtareas con sus relaciones (activity, course)
        # select_related() optimiza las consultas a la BD
        subtasks = queryset.select_related('activity', 'activity__course').all()

        # Separar subtareas en tres grupos según su fecha objetivo
        vencidas = []      # target_date < today
        para_hoy = []      # target_date == today
        proximas = []      # target_date > today (desde mañana en adelante)

        # Si se envió days_ahead, calculamos fecha límite de "próximas"
        # Si no se envió, incluir todas las próximas sin límite
        max_upcoming_date = (
            today + timedelta(days=days_ahead)
            if days_ahead is not None
            else None
        )
        
        for subtask in subtasks:
            target_date = subtask.target_date
            
            if target_date < today:
                vencidas.append(subtask)
            elif target_date == today:
                para_hoy.append(subtask)
            elif target_date > today:
                # Por defecto: incluir todas las próximas (desde mañana)
                # Si hay days_ahead: incluir solo hasta la fecha límite
                if max_upcoming_date is None or target_date <= max_upcoming_date:
                    proximas.append(subtask)
        
        # LÓGICA DE ORDENAMIENTO EN BACKEND 
        # Vencidas: ordenar por fecha más antigua primero, luego por menor esfuerzo
        # key=lambda x: (x.target_date, float(x.estimated_hours))
        # - Primero ordena por target_date (ascendente = más antiguas primero)
        # - Si hay empate en fecha, ordena por estimated_hours (ascendente = menor esfuerzo primero)
        vencidas.sort(key=lambda x: (x.target_date, float(x.estimated_hours)))
        
        # Para hoy: ordenar solo por menor esfuerzo (todas tienen la misma fecha)
        para_hoy.sort(key=lambda x: float(x.estimated_hours))
        
        # Próximas: ordenar por fecha más cercana primero, luego por menor esfuerzo
        # key=lambda x: (x.target_date, float(x.estimated_hours))
        # - Primero ordena por target_date (ascendente = más cercanas primero)
        # - Si hay empate en fecha, ordena por estimated_hours (ascendente = menor esfuerzo primero)
        proximas.sort(key=lambda x: (x.target_date, float(x.estimated_hours)))
        
        # Serializar los datos 
        serializer = TodaySubtaskSerializer
        
        # Regla de ordenamiento para mostrar en la UI 
        regla_ordenamiento = (
            "Vencidas primero (más antiguas arriba), luego Para hoy, "
            "luego Próximas por fecha más cercana. Desempate: menor esfuerzo estimado primero."
        )
        
        # Devolver respuesta con subtareas agrupadas y ordenadas
        return Response({
            'vencidas': serializer(vencidas, many=True).data,
            'para_hoy': serializer(para_hoy, many=True).data,
            'proximas': serializer(proximas, many=True).data,
            'regla_ordenamiento': regla_ordenamiento,
            'fecha_referencia': today.isoformat(),
            'total_vencidas': len(vencidas),
            'total_para_hoy': len(para_hoy),
            'total_proximas': len(proximas),
        }, status=status.HTTP_200_OK)