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
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter, OpenApiResponse
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
        Endpoint que devuelve subtareas agrupadas y ordenadas según reglas específicas de priorización.
        
        ## Funcionalidad
        
        Este endpoint implementa la vista "Hoy" que agrupa las subtareas del usuario en tres categorías:
        - **Vencidas**: Subtareas con fecha objetivo anterior a hoy
        - **Para hoy**: Subtareas con fecha objetivo igual a hoy
        - **Próximas**: Subtareas con fecha objetivo posterior a hoy
        
        ## Reglas de Ordenamiento (Backend)
        
        Las subtareas se ordenan automáticamente según estas reglas:
        
        ### Vencidas (`target_date < fecha_referencia`)
        - **Primer criterio**: Fecha más antigua primero (ascendente)
        - **Desempate**: Menor esfuerzo estimado primero
        
        ### Para hoy (`target_date == fecha_referencia`)
        - **Único criterio**: Menor esfuerzo estimado primero
        
        ### Próximas (`target_date > fecha_referencia`)
        - **Primer criterio**: Fecha más cercana primero (ascendente)
        - **Desempate**: Menor esfuerzo estimado primero
        
        ## Filtros Disponibles
        
        Los filtros se pueden combinar para obtener resultados más específicos:
        
        - **status**: Filtrar por estado de la subtarea
        - **course**: Filtrar por curso específico (solo cursos del usuario)
        - **days_ahead**: Limitar el rango de días futuros en "Próximas"
        
        ## Respuesta Consistente
        
        La respuesta siempre mantiene la misma estructura, incluso cuando no hay subtareas:
        - Arrays siempre presentes (pueden estar vacíos)
        - Campos de metadatos siempre incluidos
        - Formato de fechas consistente (ISO 8601: YYYY-MM-DD)
        """,
        parameters=[
            OpenApiParameter(
                name='status',
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Filtrar subtareas por estado. Solo se incluirán subtareas con el estado especificado.',
                enum=['PENDING', 'DONE', 'WAITING', 'POSTPONED'],
                examples=[
                    OpenApiExample('Pendientes', value='PENDING'),
                    OpenApiExample('Completadas', value='DONE'),
                    OpenApiExample('En espera', value='WAITING'),
                    OpenApiExample('Pospuestas', value='POSTPONED'),
                ],
            ),
            OpenApiParameter(
                name='days_ahead',
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Limitar cuántos días hacia adelante incluir en "Próximas". Debe ser un número entero positivo. Si no se especifica, se incluyen todas las subtareas futuras.',
                examples=[
                    OpenApiExample('Próximos 7 días', value=7),
                    OpenApiExample('Próximos 14 días', value=14),
                    OpenApiExample('Próximos 30 días', value=30),
                ],
            ),
            OpenApiParameter(
                name='course',
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Filtrar subtareas por ID de curso (UUID). Solo se incluirán subtareas de actividades pertenecientes al curso especificado. El curso debe pertenecer al usuario autenticado.',
                examples=[
                    OpenApiExample('UUID de curso', value='e5961b9a-16aa-41d2-a76d-57a9654de911'),
                ],
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Respuesta exitosa con subtareas agrupadas y ordenadas',
                examples=[
                    OpenApiExample(
                        'Respuesta exitosa con datos',
                        value={
                            'vencidas': [
                                {
                                    'id': '97a49b2e-2b2c-45aa-b1f0-f9a4be81c2bf',
                                    'title': 'Revisar apuntes de clase',
                                    'status': 'PENDING',
                                    'estimated_hours': '2.00',
                                    'target_date': '2026-02-28',
                                    'is_conflicted': False,
                                    'execution_note': None,
                                    'activity': {
                                        'id': '5c62607b-fa63-4d74-8cc3-ea010b79c9b2',
                                        'title': 'Examen parcial',
                                        'description': 'Examen intermedio de ecuaciones diferenciales',
                                        'course': {
                                            'id': 'e5961b9a-16aa-41d2-a76d-57a9654de911',
                                            'name': 'Cálculo diferencial'
                                        },
                                        'type': 'examen',
                                        'created_at': '2026-02-28T08:03:56.026837Z',
                                        'event_datetime': None,
                                        'deadline': '2026-03-02'
                                    }
                                }
                            ],
                            'para_hoy': [
                                {
                                    'id': '856eb101-0258-40ac-ac16-f54e59439050',
                                    'title': 'Estudiar diapositivas',
                                    'status': 'PENDING',
                                    'estimated_hours': '1.00',
                                    'target_date': '2026-03-01',
                                    'is_conflicted': False,
                                    'execution_note': None,
                                    'activity': {
                                        'id': 'b9073b63-e239-47a5-818c-961975153eff',
                                        'title': 'Examen parcial',
                                        'description': 'Examen intermedio de ecuaciones diferenciales',
                                        'course': {
                                            'id': '196b2fa8-fc94-47f9-b0d6-586aba131ce3',
                                            'name': 'Cálculo diferencial'
                                        },
                                        'type': 'examen',
                                        'created_at': '2026-02-28T08:03:56.026837Z',
                                        'event_datetime': None,
                                        'deadline': '2026-03-02'
                                    }
                                }
                            ],
                            'proximas': [
                                {
                                    'id': '1cdf1183-652b-4fdd-bb38-a1aac239d806',
                                    'title': 'Subtarea próxima cercana',
                                    'status': 'PENDING',
                                    'estimated_hours': '1.00',
                                    'target_date': '2026-03-03',
                                    'is_conflicted': False,
                                    'execution_note': None,
                                    'activity': {
                                        'id': 'aaa3ef81-4f72-431f-a6d8-02e4722ef6e4',
                                        'title': 'Prueba Ordenamiento',
                                        'description': 'Actividad para probar el endpoint',
                                        'course': {
                                            'id': 'f3f30254-522a-4b5a-b626-acd4a054761c',
                                            'name': 'Cálculo'
                                        },
                                        'type': 'taller',
                                        'created_at': '2026-03-02T00:39:21.496531Z',
                                        'event_datetime': None,
                                        'deadline': '2026-03-31'
                                    }
                                }
                            ],
                            'regla_ordenamiento': 'Vencidas primero (más antiguas arriba), luego Para hoy, luego Próximas por fecha más cercana. Desempate: menor esfuerzo estimado primero.',
                            'fecha_referencia': '2026-03-01',
                            'total_vencidas': 1,
                            'total_para_hoy': 1,
                            'total_proximas': 1
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        'Respuesta sin subtareas',
                        value={
                            'vencidas': [],
                            'para_hoy': [],
                            'proximas': [],
                            'regla_ordenamiento': 'Vencidas primero (más antiguas arriba), luego Para hoy, luego Próximas por fecha más cercana. Desempate: menor esfuerzo estimado primero.',
                            'fecha_referencia': '2026-03-01',
                            'total_vencidas': 0,
                            'total_para_hoy': 0,
                            'total_proximas': 0
                        },
                        response_only=True,
                    ),
                ],
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Error de validación en los parámetros de consulta',
                examples=[
                    OpenApiExample(
                        'Estado inválido',
                        value={'error': 'status debe ser uno de: PENDING, DONE, WAITING, POSTPONED'},
                        response_only=True,
                    ),
                    OpenApiExample(
                        'days_ahead inválido',
                        value={'error': 'days_ahead debe ser un número entero positivo.'},
                        response_only=True,
                    ),
                    OpenApiExample(
                        'UUID inválido',
                        value={'error': 'course debe ser un UUID válido.'},
                        response_only=True,
                    ),
                ],
            ),
            401: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='No autenticado. Se requiere token JWT válido.',
                examples=[
                    OpenApiExample(
                        'Error de autenticación',
                        value={'detail': 'Las credenciales de autenticación no se proveyeron.'},
                        response_only=True,
                    ),
                    OpenApiExample(
                        'Token inválido',
                        value={'detail': 'Token inválado o expirado.'},
                        response_only=True,
                    ),
                ],
            ),
        },
        examples=[
            OpenApiExample(
                'Request básico sin filtros',
                description='Obtiene todas las subtareas del usuario agrupadas y ordenadas',
                value={},
                request_only=True,
            ),
            OpenApiExample(
                'Request con filtro de estado',
                description='Obtiene solo las subtareas pendientes',
                value={'status': 'PENDING'},
                request_only=True,
            ),
            OpenApiExample(
                'Request con filtro de curso',
                description='Obtiene solo las subtareas de un curso específico',
                value={'course': 'e5961b9a-16aa-41d2-a76d-57a9654de911'},
                request_only=True,
            ),
            OpenApiExample(
                'Request con límite de días',
                description='Obtiene subtareas limitando "Próximas" a los próximos 7 días',
                value={'days_ahead': 7},
                request_only=True,
            ),
            OpenApiExample(
                'Request con múltiples filtros',
                description='Combina filtros: solo pendientes de un curso específico en los próximos 14 días',
                value={
                    'status': 'PENDING',
                    'course': 'e5961b9a-16aa-41d2-a76d-57a9654de911',
                    'days_ahead': 14
                },
                request_only=True,
            ),
        ],
    )
    def get(self, request):
        """
        Obtener subtareas agrupadas y ordenadas para la vista "Hoy".
        
        Este método implementa la lógica completa de la vista "Hoy":
        
        1. **Obtención de datos**: Filtra subtareas del usuario autenticado que tienen fecha objetivo
        2. **Aplicación de filtros**: Aplica filtros opcionales (status, course, days_ahead)
        3. **Clasificación**: Agrupa subtareas en tres categorías según su fecha objetivo:
           - Vencidas: target_date < fecha_referencia
           - Para hoy: target_date == fecha_referencia
           - Próximas: target_date > fecha_referencia
        4. **Ordenamiento**: Ordena cada grupo según reglas específicas de priorización
        5. **Respuesta**: Devuelve estructura JSON consistente con metadatos
        
        **Validaciones realizadas:**
        - Autenticación requerida (manejada por permission_classes)
        - Validación de formato UUID para course
        - Validación de valores permitidos para status
        - Validación de rango positivo para days_ahead
        
        **Optimizaciones:**
        - Uso de select_related() para evitar N+1 queries
        - Filtrado en base de datos antes de procesar en Python
        
        Args:
            request: Request HTTP con query parameters opcionales:
                - status (str, opcional): Estado de la subtarea (PENDING, DONE, WAITING, POSTPONED)
                - course (str, opcional): UUID del curso para filtrar
                - days_ahead (int, opcional): Límite de días futuros para "Próximas"
        
        Returns:
            Response: JSON con estructura:
                - vencidas (list): Array de subtareas vencidas ordenadas
                - para_hoy (list): Array de subtareas para hoy ordenadas
                - proximas (list): Array de subtareas próximas ordenadas
                - regla_ordenamiento (str): Descripción de las reglas aplicadas
                - fecha_referencia (str): Fecha usada como referencia (ISO format)
                - total_vencidas (int): Cantidad de subtareas vencidas
                - total_para_hoy (int): Cantidad de subtareas para hoy
                - total_proximas (int): Cantidad de subtareas próximas
        
        Raises:
            400 Bad Request: Si los parámetros de consulta son inválidos
            401 Unauthorized: Si no se proporciona token de autenticación válido
        """
        user = request.user
        
        # Obtener query params opcionales con validación
        status_filter = request.query_params.get('status', None)
        days_ahead_param = request.query_params.get('days_ahead', None)
        course_filter = request.query_params.get('course', None)
        
        # Validar y convertir days_ahead
        days_ahead = None
        if days_ahead_param is not None:
            try:
                days_ahead = int(days_ahead_param)
                if days_ahead < 1:
                    return Response(
                        {'error': 'days_ahead debe ser un número entero positivo.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except (ValueError, TypeError):
                return Response(
                    {'error': 'days_ahead debe ser un número entero válido.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Validar status si se proporciona
        valid_statuses = ['PENDING', 'DONE', 'WAITING', 'POSTPONED']
        if status_filter and status_filter not in valid_statuses:
            return Response(
                {'error': f'status debe ser uno de: {", ".join(valid_statuses)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar formato UUID de course si se proporciona
        if course_filter:
            try:
                from uuid import UUID
                UUID(course_filter)  # Valida formato UUID
            except (ValueError, TypeError):
                return Response(
                    {'error': 'course debe ser un UUID válido.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Obtener fecha de referencia (hoy)
        today = timezone.localdate()
        
        # Obtener subtareas del usuario
        queryset = Subtask.objects.filter(
            user=user,
            target_date__isnull=False  # Solo subtareas con fecha
        )
        
        # Filtrar por estado si se proporciona
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filtrar por curso si se proporciona
        if course_filter:
            # Verificar que el curso pertenece al usuario
            course_exists = Course.objects.filter(id=course_filter, user=user).exists()
            if course_exists:
                queryset = queryset.filter(activity__course_id=course_filter)
            else:
                # Si el curso no existe o no pertenece al usuario, retornar vacío
                return Response({
                    'vencidas': [],
                    'para_hoy': [],
                    'proximas': [],
                    'regla_ordenamiento': 'Vencidas primero (más antiguas arriba), luego Para hoy, luego Próximas por fecha más cercana. Desempate: menor esfuerzo estimado primero.',
                    'fecha_referencia': today.isoformat(),
                    'total_vencidas': 0,
                    'total_para_hoy': 0,
                    'total_proximas': 0,
                }, status=status.HTTP_200_OK)
        
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
        vencidas.sort(key=lambda x: (x.target_date, float(x.estimated_hours)))
        
        # Para hoy: ordenar solo por menor esfuerzo (todas tienen la misma fecha)
        para_hoy.sort(key=lambda x: float(x.estimated_hours))
        
        # Próximas: ordenar por fecha más cercana primero, luego por menor esfuerzo
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