from django.shortcuts import render
from django.contrib.auth import get_user_model
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from django.utils import timezone
from datetime import timedelta
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
)
from drf_spectacular.types import OpenApiTypes
from .models import Course, Activity, Subtask, ReprogrammingLog, PosponedLog
from .serializers import (
    CourseSerializer,
    ActivitySerializer,
    SubtaskSerializer,
    ReprogrammingLogSerializer,
    TodaySubtaskSerializer,
    TodayStudyTimeSerializer,
    PostponeSubtaskSerializer,
    CompletionPercentSerializer,
    PosponedLogSerializer,
)
from datetime import datetime
from uuid import UUID
from django.shortcuts import get_object_or_404
from .serializers import SubtaskSerializer
from django.db.models import Sum
from decimal import Decimal
from collections import defaultdict
from rest_framework.decorators import action
from django.db.models import Count, Q
User = get_user_model()

_BASE = "Todas las rutas del planner bajo el prefijo **`/api/`** (p. ej. `https://tu-dominio/api/...`). Requiere **JWT** salvo que se indique lo contrario."

_SUBTASK_NESTED_SECURITY = (
    "\n\n**Seguridad:** El queryset solo incluye subtareas **`user=request.user`** y de la **`activity_id`** del path. "
    "Si el `id` de la subtarea no existe, es de otro usuario o no pertenece a esa actividad → **404**."
)

_SUBTASK_EDIT_INTRO = (
    "### Cambio reciente\n"
    "Si el cuerpo incluye el campo **`title`**, el servidor comprueba que **ninguna otra subtarea** "
    "de la **misma actividad** tenga ya **exactamente** ese texto: la comparación **distingue mayúsculas "
    "y minúsculas** (por ejemplo, `Leer` y `leer` son títulos distintos). La subtarea que se está editando "
    "**se excluye** de la búsqueda, de modo que puedes guardar sin cambiar el título. Si hay conflicto → "
    "**400** y el error aparece bajo la clave **`title`**.\n\n"
)

_SUBTASK_EDIT_VALIDATIONS = (
    "### Validaciones\n"
    "- **`title`** (si se envía): no vacío; máximo **100** caracteres; **único por actividad** "
    "entre subtareas distintas (**comparación exacta**, distingue mayúsculas).\n"
    "- **`estimated_hours`** (si se envía): debe ser **> 0**.\n"
    "- **Límite diario de horas** (si la subtarea tiene **`target_date`** y el estado resultante no es **`DONE`**): "
    "la suma de horas estimadas de todas las subtareas **del mismo usuario** en esa fecha "
    "(excluyendo `DONE` y excluyendo la fila actual al recalcular) más las horas de esta subtarea "
    "no puede superar **`daily_hours_limit`** del usuario.\n"
    "- Si el estado pasa a **`DONE`**, no se aplica la validación del límite diario.\n\n"
)

_SUBTASK_EDIT_IO = (
    "### Entrada\n"
    "- **`PATCH`**: JSON parcial; solo los campos enviados se validan y actualizan.\n"
    "- **`PUT`**: JSON con la representación completa de los campos editables (mismo serializer).\n"
    "- Campos típicos: `title`, `estimated_hours`, `target_date`, `status`, `order`.\n"
    "- **`title`**: al enviarlo, se eliminan espacios al inicio y al final (`strip`); la unicidad en la "
    "actividad se compara contra el valor ya normalizado, con **igualdad exacta** (sensible a mayúsculas).\n"
    "- `activity` es de solo lectura en la respuesta (no se reasigna por este endpoint).\n\n"
    "### Salida\n"
    "- **`200 OK`**: cuerpo = objeto **`Subtask`** serializado (incluye `activity` anidada, `is_conflicted`, "
    "`posponed_note`, etc.).\n"
    "- **`400`**: errores de validación (objeto con claves de campo o `non_field_errors`).\n"
    "- **`401`**: no autenticado.\n"
    "- **`404`**: subtarea o combinación actividad/subtarea no válida para el usuario.\n\n"
)

_SUBTASK_EDIT_EXAMPLE = (
    "### Ejemplo\n"
    "1. Petición `PATCH /api/activity/3fa85f64-5717-4562-b3fc-2c963f66afa6/subtasks/"
    "6ba7b810-9dad-11d1-80b4-00c04fd430c8/` con cabecera `Authorization: Bearer …` y cuerpo:\n"
    "```json\n"
    '{ "title": "Repasar tema 3", "estimated_hours": 2.5 }\n'
    "```\n"
    "2. **Duplicado exacto (misma cadena, misma capitalización):** si otra subtarea de esa actividad ya "
    "se llama exactamente `Repasar tema 3`, respuesta **400**:\n"
    "```json\n"
    '{ "title": ["Ya existe una subtarea con este título en la misma actividad."] }\n'
    "```\n"
    "3. **Misma frase, distinta capitalización:** si la otra subtarea se llama `repasar tema 3` (solo "
    "cambia mayúsculas/minúsculas) y envías `Repasar tema 3`, **no** hay conflicto → **200** (la regla es "
    "comparación **literal** / case-sensitive).\n"
    "4. Si no hay duplicado exacto y el día no supera el límite de horas, respuesta **200** con el objeto "
    "actualizado (misma forma que en `GET` de la subtarea).\n"
)

_SUBTASK_PATCH_DOC = (
    f"{_BASE}\n\n**URL:** `PATCH /api/activity/{{activity_id}}/subtasks/{{id}}/`\n\n"
    f"{_SUBTASK_EDIT_INTRO}"
    f"{_SUBTASK_EDIT_VALIDATIONS}"
    f"{_SUBTASK_EDIT_IO}"
    f"{_SUBTASK_EDIT_EXAMPLE}"
    f"{_SUBTASK_NESTED_SECURITY}"
)

_SUBTASK_PUT_DOC = (
    f"{_BASE}\n\n**URL:** `PUT /api/activity/{{activity_id}}/subtasks/{{id}}/`\n\n"
    "**Nota:** Sustituye todos los campos obligatorios del serializer; misma validación que `PATCH` "
    "(título único por actividad con **comparación exacta** / case-sensitive, horas > 0, límite diario cuando "
    "aplica).\n\n"
    f"{_SUBTASK_EDIT_INTRO}"
    f"{_SUBTASK_EDIT_VALIDATIONS}"
    f"{_SUBTASK_EDIT_IO}"
    f"{_SUBTASK_EDIT_EXAMPLE}"
    f"{_SUBTASK_NESTED_SECURITY}"
)


@extend_schema_view(
    list=extend_schema(
        summary="Listar cursos del usuario",
        description=f"{_BASE}\n\n**URL:** `GET /api/course/`",
        tags=["Cursos"],
    ),
    create=extend_schema(
        summary="Crear curso",
        description=f"{_BASE}\n\n**URL:** `POST /api/course/`",
        tags=["Cursos"],
    ),
    retrieve=extend_schema(
        summary="Detalle de curso",
        description=f"{_BASE}\n\n**URL:** `GET /api/course/{{id}}/`",
        tags=["Cursos"],
    ),
    update=extend_schema(
        summary="Reemplazar curso",
        description=f"{_BASE}\n\n**URL:** `PUT /api/course/{{id}}/`",
        tags=["Cursos"],
    ),
    partial_update=extend_schema(
        summary="Actualizar curso (parcial)",
        description=f"{_BASE}\n\n**URL:** `PATCH /api/course/{{id}}/`",
        tags=["Cursos"],
    ),
    destroy=extend_schema(
        summary="Eliminar curso",
        description=f"{_BASE}\n\n**URL:** `DELETE /api/course/{{id}}/`\n\nRespuesta típica: `204` con mensaje en cuerpo según implementación.",
        tags=["Cursos"],
    ),
)
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


@extend_schema_view(
    list=extend_schema(
        summary="Listar actividades del usuario",
        description=f"{_BASE}\n\n**URL:** `GET /api/activity/`\n\nIncluye anotaciones `total_subtasks`, `total_subtasks_done` y `completion_percent` por actividad.",
        tags=["Actividades"],
    ),
    create=extend_schema(
        summary="Crear actividad",
        description=f"{_BASE}\n\n**URL:** `POST /api/activity/`",
        tags=["Actividades"],
    ),
    update=extend_schema(
        summary="Reemplazar actividad",
        description=f"{_BASE}\n\n**URL:** `PUT /api/activity/{{id}}/`",
        tags=["Actividades"],
    ),
    partial_update=extend_schema(
        summary="Actualizar actividad (parcial)",
        description=f"{_BASE}\n\n**URL:** `PATCH /api/activity/{{id}}/`",
        tags=["Actividades"],
    ),
    destroy=extend_schema(
        summary="Eliminar actividad",
        description=f"{_BASE}\n\n**URL:** `DELETE /api/activity/{{id}}/`",
        tags=["Actividades"],
    ),
)
class ActivityViewSet(ModelViewSet):
    serializer_class = ActivitySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Devuelve únicamente actividades pertenecientes al usuario autenticado.
        Además, anota el total de subtareas y las completadas para poder
        calcular el porcentaje de completitud por actividad.
        """
        user = self.request.user
        base_qs = Activity.objects.filter(user=user)

        return base_qs.annotate(
            total_subtasks=Count('subtasks'),
            total_subtasks_done=Count(
                'subtasks',
                filter=Q(subtasks__status=Subtask.Status.REALIZADO)
            ),
        ).prefetch_related('subtasks')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(
        summary="Porcentaje global de completitud de subtareas",
        description=f"""
{_BASE}

### URL
`GET /api/activity/completion-percent/`

Calcula el porcentaje de subtareas completadas **exclusivamente para actividades
        pertenecientes al usuario autenticado**.

        Opcionalmente se puede limitar el cálculo a un rango de fechas usando:

        - `from_date`: fecha mínima de `target_date` (incluida).
        - `to_date`: fecha máxima de `target_date` (incluida).

        Si no existen subtareas en el rango, devuelve `completion_percent = 0.0`.

        ### Ejemplos de uso

        - **Mes completo**: marzo de 2026

          `GET /api/activity/completion-percent/?from_date=2026-03-01&to_date=2026-03-31`

        - **Semana concreta**: del 9 al 15 de marzo de 2026

          `GET /api/activity/completion-percent/?from_date=2026-03-09&to_date=2026-03-15`

        - **Un solo día**: 10 de marzo de 2026

          `GET /api/activity/completion-percent/?from_date=2026-03-10&to_date=2026-03-10`

        - **Desde una fecha hasta hoy** (sin `to_date`):

          `GET /api/activity/completion-percent/?from_date=2026-03-01`
        """,
        parameters=[
            OpenApiParameter(
                name="from_date",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Fecha inicial (YYYY-MM-DD) para filtrar por `target_date`.",
            ),
            OpenApiParameter(
                name="to_date",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Fecha final (YYYY-MM-DD) para filtrar por `target_date`.",
            ),
        ],
        responses={200: CompletionPercentSerializer},
        tags=["Actividades"],
    )
    @action(methods=['get'], detail=False, url_path='completion-percent')
    def get_completion_percent(self, request):
        """
        Devuelve el porcentaje global de avance de las subtareas del usuario
        autenticado, considerando solo actividades que le pertenecen y un
        rango de fechas opcional.
        """
        # Validar e interpretar parámetros de entrada
        input_serializer = CompletionPercentSerializer(data=request.query_params)
        input_serializer.is_valid(raise_exception=True)

        from_date = input_serializer.validated_data.get("from_date")
        to_date = input_serializer.validated_data.get("to_date")

        # Construir queryset base de subtareas del usuario y de sus actividades
        qs = Subtask.objects.filter(user=request.user, activity__user=request.user)
        if from_date:
            qs = qs.filter(target_date__gte=from_date)
        if to_date:
            qs = qs.filter(target_date__lte=to_date)

        total_subtasks = qs.count()
        total_subtasks_done = qs.filter(status=Subtask.Status.REALIZADO).count()

        if total_subtasks == 0:
            completion_percent = 0.0
        else:
            completion_percent = float((total_subtasks_done / total_subtasks) * 100)

        # Serializar salida con los campos calculados
        output_serializer = CompletionPercentSerializer(
            {
                "completion_percent": completion_percent,
                "from_date": from_date,
                "to_date": to_date,
                "total_subtasks": total_subtasks,
                "total_subtasks_done": total_subtasks_done,
            }
        )
        return Response(output_serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Obtener actividad del usuario con porcentaje de completitud",
        description=f"""
{_BASE}

### URL
`GET /api/activity/{{id}}/`

Devuelve el detalle de una actividad perteneciente **al usuario autenticado**,
        incluyendo:

        - Datos básicos de la actividad y su curso.
        - `total_subtasks`: total de subtareas hijas.
        - `total_subtasks_done`: subtareas hijas completadas.
        - `completion_percent`: porcentaje de avance de la actividad.

        No permite acceder a actividades de otros usuarios.
        """,
        responses={200: ActivitySerializer},
        tags=["Actividades"],
    )
    def retrieve(self, request, *args, **kwargs):
        """
        Recupera una actividad que pertenece al usuario autenticado.
        La seguridad se garantiza filtrando siempre por `user` en `get_queryset`.
        """
        return super().retrieve(request, *args, **kwargs)


@extend_schema_view(
    list=extend_schema(
        summary="Listar subtareas (anidadas en actividad)",
        description=f"{_BASE}\n\n**URL:** `GET /api/activity/{{activity_id}}/subtasks/`\n\nSolo subtareas del usuario; `activity_id` en la ruta acota a esa actividad.{_SUBTASK_NESTED_SECURITY}",
        tags=["Subtareas"],
    ),
    create=extend_schema(
        summary="Crear subtarea en una actividad",
        description=f"{_BASE}\n\n**URL:** `POST /api/activity/{{activity_id}}/subtasks/`\n\nLa actividad del path debe ser del usuario.{_SUBTASK_NESTED_SECURITY}",
        tags=["Subtareas"],
    ),
    retrieve=extend_schema(
        summary="Detalle de subtarea",
        description=f"{_BASE}\n\n**URL:** `GET /api/activity/{{activity_id}}/subtasks/{{id}}/`{_SUBTASK_NESTED_SECURITY}",
        tags=["Subtareas"],
    ),
    update=extend_schema(
        summary="Reemplazar subtarea",
        description=_SUBTASK_PUT_DOC,
        tags=["Subtareas"],
        request=SubtaskSerializer,
        responses={
            200: SubtaskSerializer,
            400: OpenApiResponse(
                description="Validación fallida (título duplicado en la actividad, horas, límite diario, etc.).",
            ),
            401: OpenApiResponse(description="No autenticado (JWT inválido o ausente)."),
            404: OpenApiResponse(description="Subtarea no encontrada o no pertenece al usuario/actividad del path."),
        },
        examples=[
            OpenApiExample(
                "PUT — cuerpo de ejemplo (título y horas)",
                value={"title": "Repasar tema 3", "estimated_hours": 2.5},
                request_only=True,
            ),
            OpenApiExample(
                "400 — título duplicado en la actividad",
                value={"title": ["Ya existe una subtarea con este título en la misma actividad."]},
                response_only=True,
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Actualizar subtarea (parcial)",
        description=_SUBTASK_PATCH_DOC,
        tags=["Subtareas"],
        request=SubtaskSerializer,
        responses={
            200: SubtaskSerializer,
            400: OpenApiResponse(
                description="Validación fallida (título duplicado en la actividad, horas, límite diario, etc.).",
            ),
            401: OpenApiResponse(description="No autenticado (JWT inválido o ausente)."),
            404: OpenApiResponse(description="Subtarea no encontrada o no pertenece al usuario/actividad del path."),
        },
        examples=[
            OpenApiExample(
                "PATCH — actualizar título y horas",
                value={"title": "Repasar tema 3", "estimated_hours": 2.5},
                request_only=True,
            ),
            OpenApiExample(
                "400 — título duplicado en la actividad",
                value={"title": ["Ya existe una subtarea con este título en la misma actividad."]},
                response_only=True,
            ),
        ],
    ),
    destroy=extend_schema(
        summary="Eliminar subtarea",
        description=f"{_BASE}\n\n**URL:** `DELETE /api/activity/{{activity_id}}/subtasks/{{id}}/`{_SUBTASK_NESTED_SECURITY}",
        tags=["Subtareas"],
    ),
)
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

    def retrieve(self, request, *args, **kwargs):
        """
        Obtiene una subtarea por id y expone su información detallada.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def perform_create(self, serializer):
        activity_id = self.kwargs.get("activity_pk")
        activity = Activity.objects.filter(id=activity_id, user=self.request.user).first()
        if not activity:
            raise NotFound("Actividad no encontrada o no tienes permisos.")
        serializer.save(user=self.request.user, activity=activity)

    def perform_update(self, serializer):
        # Capturamos la fecha actual de la instancia antes de que el serializer la actualice
        old_date = serializer.instance.target_date
        
        # Guardamos los cambios
        updated_instance = serializer.save()
        new_date = updated_instance.target_date
        
        # Si la fecha cambió y ya tenía una fecha previa registrada, creamos un log de reprogramación
        if old_date is not None and new_date is not None and old_date != new_date:
            reason = self.request.data.get("reason", "Reprogramación manual")
            ReprogrammingLog.objects.create(
                subtask=updated_instance,
                previous_date=old_date,
                new_date=new_date,
                reason=reason
            )

    @extend_schema(
        summary="Posponer una subtarea",
        description=f"""
{_BASE}

### Comportamiento
- Pone la subtarea en estado **`POSTPONED`**.
- Crea un registro en **`PosponedLog`** con el texto enviado en `execution_note` (campo persistido como `note` en el log).
- La respuesta **`201`** incluye el objeto **`subtask`** (serializado) y **`posponed_log`** con `note` y `created_at`.

### Seguridad
La subtarea se resuelve con **`get_queryset()`**: debe ser **del usuario autenticado** y pertenecer a la **`activity_id`** de la URL. Si el `subtask_id` no existe, es de otro usuario o no está bajo esa actividad → **404** (`Not found`).

### URL
`PATCH /api/activity/{{activity_id}}/subtasks/{{subtask_id}}/postpone/`
        """,
        request=PostponeSubtaskSerializer,
        responses={
            201: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Subtarea pospuesta y log de posposición creado.",
                examples=[
                    OpenApiExample(
                        "201 — subtarea + log",
                        value={
                            "subtask": {
                                "id": "01b73f4a-8805-49f5-8b8e-03aa702d7a6b",
                                "title": "Resolver guía",
                                "status": "POSTPONED",
                                "estimated_hours": "2.00",
                                "target_date": "2026-03-07",
                                "order": 0,
                                "is_conflicted": False,
                            },
                            "posponed_log": {
                                "note": "Pospuesta por falta de tiempo",
                                "created_at": "2026-03-21T14:30:00Z",
                            },
                        },
                        response_only=True,
                    ),
                ],
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Cuerpo JSON inválido según validación del serializer.",
            ),
            401: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="No autenticado. Se requiere JWT válido.",
                examples=[OpenApiExample("Sin credenciales", value={"detail": "Authentication credentials were not provided."})],
            ),
            404: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Subtarea inexistente, de otro usuario o no asociada a la actividad del path.",
                examples=[OpenApiExample("No encontrada o no autorizada", value={"detail": "Not found."})],
            ),
        },
        examples=[
            OpenApiExample(
                "Request — motivo de posposición",
                value={"execution_note": "Pospuesta por falta de tiempo"},
                request_only=True,
            ),
        ],
        tags=["Subtareas"],
    )
    @action(detail=True, methods=['patch'], url_path='postpone')
    def postpone(self, request, pk=None, *args, **kwargs):
        subtask = self.get_object()
        input_ser = PostponeSubtaskSerializer(data=request.data)
        input_ser.is_valid(raise_exception=True)

        subtask.status = Subtask.Status.POSPUESTO 
        subtask.save(update_fields=['status'])
   
        posponed_log = PosponedLog.objects.create(
            subtask=subtask,
            note=input_ser.validated_data.get("execution_note") or "",
        ) 
        output_data = {
            'subtask': self.get_serializer(subtask).data,
            'posponed_log': {
                'note': posponed_log.note,
                'created_at': posponed_log.created_at,
            },
        }
        return Response(output_data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    list=extend_schema(
        summary="Listar logs de posposición",
        description=f"{_BASE}\n\n**URL:** `GET /api/posponed_log/`\n\nSolo logs cuya subtarea pertenece al usuario autenticado.",
        tags=["Posposiciones"],
    ),
    create=extend_schema(
        summary="Crear log de posposición (CRUD)",
        description=f"{_BASE}\n\n**URL:** `POST /api/posponed_log/`",
        tags=["Posposiciones"],
    ),
    retrieve=extend_schema(
        summary="Detalle de un log de posposición",
        description=f"{_BASE}\n\n**URL:** `GET /api/posponed_log/{{id}}/`",
        tags=["Posposiciones"],
    ),
    update=extend_schema(
        summary="Reemplazar log de posposición",
        description=f"{_BASE}\n\n**URL:** `PUT /api/posponed_log/{{id}}/`",
        tags=["Posposiciones"],
    ),
    partial_update=extend_schema(
        summary="Actualizar log (parcial)",
        description=f"{_BASE}\n\n**URL:** `PATCH /api/posponed_log/{{id}}/`",
        tags=["Posposiciones"],
    ),
    destroy=extend_schema(
        summary="Eliminar log de posposición",
        description=f"{_BASE}\n\n**URL:** `DELETE /api/posponed_log/{{id}}/`",
        tags=["Posposiciones"],
    ),
)
class PosponedLogViewSet(ModelViewSet):
    serializer_class = PosponedLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PosponedLog.objects.filter(subtask__user=self.request.user)

    @extend_schema(
        summary="Notas de posposición de una subtarea",
        description=f"""
{_BASE}

Primero verifica que **`subtask_id`** sea un UUID válido y que la subtarea **exista y pertenezca al usuario autenticado**; si no → **404**. Si es válida y es tuya pero no hay logs, responde **200** con **`[]`**.

### URL
`GET /api/posponed_log/notes-of-subtask/{{subtask_id}}/`

- `subtask_id`: UUID de la subtarea.
        """,
        parameters=[
            OpenApiParameter(
                name="subtask_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                required=True,
                description="UUID de la subtarea (debe ser del usuario autenticado).",
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Array JSON de logs; **`[]`** si la subtarea es tuya pero no hay registros.",
                examples=[
                    OpenApiExample(
                        "200 — varias notas",
                        value=[
                            {
                                "id": 1,
                                "subtask": {"id": "01b73f4a-8805-49f5-8b8e-03aa702d7a6b", "title": "Resolver guía"},
                                "note": "Sin tiempo hoy",
                                "created_at": "2026-03-20T10:00:00Z",
                            },
                            {
                                "id": 2,
                                "subtask": {"id": "01b73f4a-8805-49f5-8b8e-03aa702d7a6b", "title": "Resolver guía"},
                                "note": "Reagendar para el finde",
                                "created_at": "2026-03-21T15:00:00Z",
                            },
                        ],
                        response_only=True,
                    ),
                    OpenApiExample(
                        "200 — sin registros",
                        value=[],
                        response_only=True,
                    ),
                ],
            ),
            401: OpenApiResponse(
                description="JWT requerido.",
                examples=[OpenApiExample("Sin JWT", value={"detail": "Authentication credentials were not provided."})],
            ),
            404: OpenApiResponse(
                description="Subtarea inexistente o no pertenece al usuario (mismo cuerpo genérico que Django REST).",
                examples=[OpenApiExample("No encontrada", value={"detail": "Not found."}, response_only=True)],
            ),
            400: OpenApiResponse(
                description="`subtask_id` no es un UUID válido.",
                examples=[
                    OpenApiExample(
                        "UUID inválido",
                        value={"subtask_id": ["Debe ser un UUID válido."]},
                        response_only=True,
                    ),
                ],
            ),
        },
        tags=["Posposiciones"],
    )
    @action(detail=False, methods=['get'], url_path='notes-of-subtask/(?P<subtask_id>[^/.]+)')
    def get_notes_of_subtask(self, request, *args, **kwargs):
        subtask_id = self.kwargs.get('subtask_id')
        try:
            UUID(str(subtask_id))
        except ValueError:
            raise ValidationError({'subtask_id': 'Debe ser un UUID válido.'})
        get_object_or_404(Subtask, id=subtask_id, user=request.user)
        logs = self.get_queryset().filter(subtask_id=subtask_id)
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(
        summary="Listar logs de reprogramación",
        description=f"{_BASE}\n\n**URL:** `GET /api/reprogramming_log/`",
        tags=["Reprogramación"],
    ),
    create=extend_schema(
        summary="Crear log de reprogramación",
        description=f"{_BASE}\n\n**URL:** `POST /api/reprogramming_log/`",
        tags=["Reprogramación"],
    ),
    retrieve=extend_schema(
        summary="Detalle de log de reprogramación",
        description=f"{_BASE}\n\n**URL:** `GET /api/reprogramming_log/{{id}}/`",
        tags=["Reprogramación"],
    ),
    update=extend_schema(
        summary="Reemplazar log de reprogramación",
        description=f"{_BASE}\n\n**URL:** `PUT /api/reprogramming_log/{{id}}/`",
        tags=["Reprogramación"],
    ),
    partial_update=extend_schema(
        summary="Actualizar log (parcial)",
        description=f"{_BASE}\n\n**URL:** `PATCH /api/reprogramming_log/{{id}}/`",
        tags=["Reprogramación"],
    ),
    destroy=extend_schema(
        summary="Eliminar log de reprogramación",
        description=f"{_BASE}\n\n**URL:** `DELETE /api/reprogramming_log/{{id}}/`",
        tags=["Reprogramación"],
    ),
)
class ReprogrammingLogViewSet(ModelViewSet):
    serializer_class = ReprogrammingLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Solo logs de subtareas pertenecientes al usuario autenticado
        return ReprogrammingLog.objects.filter(subtask__user=self.request.user)

    @extend_schema(
        summary="Logs de reprogramación de una subtarea",
        description=f"""
{_BASE}

Verifica que **`subtask_id`** sea un UUID válido y que la subtarea **exista y pertenezca al usuario autenticado**.
        """,
        parameters=[
            OpenApiParameter(
                name="subtask_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                required=True,
                description="UUID de la subtarea (debe ser del usuario autenticado).",
            ),
        ],
        responses={200: ReprogrammingLogSerializer(many=True)},
        tags=["Reprogramación"],
    )
    @action(detail=False, methods=['get'], url_path='notes-of-subtask/(?P<subtask_id>[^/.]+)')
    def get_notes_of_subtask(self, request, *args, **kwargs):
        subtask_id = self.kwargs.get('subtask_id')
        try:
            UUID(str(subtask_id))
        except ValueError:
            raise ValidationError({'subtask_id': 'Debe ser un UUID válido.'})
        get_object_or_404(Subtask, id=subtask_id, user=request.user)
        logs = self.get_queryset().filter(subtask_id=subtask_id).order_by('-created_at')
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


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
        description=f"""
{_BASE}

### URL
`GET /api/hoy/`

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
        tags=["Vista Hoy"],
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

        # Serializar los datos usando el nuevo serializer que calcula is_conflicted automáticamente
        context = {'request': request}
        data_vencidas = TodaySubtaskSerializer(vencidas, many=True, context=context).data
        data_para_hoy = TodaySubtaskSerializer(para_hoy, many=True, context=context).data
        data_proximas = TodaySubtaskSerializer(proximas, many=True, context=context).data

        # Regla de ordenamiento para mostrar en la UI
        regla_ordenamiento = (
            "Vencidas primero (más antiguas arriba), luego Para hoy, "
            "luego Próximas por fecha más cercana. Desempate: menor esfuerzo estimado primero."
        )

        # Devolver respuesta con subtareas agrupadas y ordenadas
        return Response({
            'vencidas': data_vencidas,
            'para_hoy': data_para_hoy,
            'proximas': data_proximas,
            'regla_ordenamiento': regla_ordenamiento,
            'fecha_referencia': today.isoformat(),
            'total_vencidas': len(vencidas),
            'total_para_hoy': len(para_hoy),
            'total_proximas': len(proximas),
        }, status=status.HTTP_200_OK)
class TodayStudyTimeView(APIView):
    """
    Endpoint para obtener las subtareas de HOY, devolviendo solo
    el tiempo estimado y el estado de cada una.

    Respuesta: lista de objetos con:
      - status
      - estimated_hours
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Tiempo de estudio de hoy (subtareas del día)",
        description=f"""
{_BASE}

### URL
`GET /api/hoy/tiempo/`

Devuelve las subtareas del usuario con **`target_date` = hoy** (solo `status` y `estimated_hours` por ítem).
        """,
        responses={
            200: OpenApiResponse(
                response=TodayStudyTimeSerializer,
                description="Array JSON: `status`, `estimated_hours` por subtarea de hoy (puede ser `[]`).",
                examples=[
                    OpenApiExample(
                        "200",
                        value=[
                            {"status": "PENDING", "estimated_hours": "2.00"},
                            {"status": "DONE", "estimated_hours": "1.50"},
                        ],
                        response_only=True,
                    ),
                ],
            ),
            401: OpenApiResponse(description="JWT requerido."),
        },
        tags=["Vista Hoy"],
    )
    def get(self, request):
        user = request.user
        today = timezone.localdate()

        # Subtareas del usuario cuya fecha objetivo es hoy
        queryset = Subtask.objects.filter(
            user=user,
            target_date=today,
            target_date__isnull=False,
        )

        serializer = TodayStudyTimeSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UpdateSubtaskTargetDateView(APIView):
    """
    Endpoint para actualizar la fecha objetivo (target_date) de una subtarea.
    Valida que la subtarea pertenezca al usuario y que la nueva fecha tenga sentido
    con respecto a la actividad padre.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Reprogramar subtarea (fecha y/o horas estimadas)",
        description=f"""
{_BASE}

### URL
`PUT /api/subtareas/{{subtask_id}}/`  
`subtask_id` = UUID de la subtarea (no usa la ruta anidada de actividad).

### Comportamiento
- Actualiza **`target_date`** y/o **`estimated_hours`** si envías cambios respecto a los valores actuales.
- **`reason`**: opcional; si cambia la fecha y la subtarea ya tenía `target_date`, se crea un **`ReprogrammingLog`** (`previous_date`, `new_date`, `reason`; por defecto motivo `"Reprogramación manual"`).
- Si la subtarea estaba **`POSTPONED`**, al guardar pasa a **`PENDING`** (reactivación al reprogramar).
- **`daily_load`**: carga planificada en el día objetivo (suma de otras subtareas NO completadas ese día + esta subtarea) frente al **`daily_hours_limit`** del usuario. Solo considera subtareas en estado pendiente, en espera o pospuestas para la suma de “vecinas”.
- Si superas el límite, la operación **igual se aplica** (`200`) y se añade **`warning`** con el texto de conflicto.

### Sin cambios
Si el body no altera fecha ni horas respecto al estado actual, responde `200` con mensaje `"No se realizaron cambios."` y el mismo `daily_load` calculado.

### Seguridad
El **`subtask_id`** del path debe corresponder a una subtarea **del usuario autenticado**. Si el id no existe o pertenece a otro usuario → **404** (`Not found`).
        """,
        parameters=[
            OpenApiParameter(
                name="pk",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                required=True,
                description="UUID de la subtarea (solo si es del usuario autenticado).",
            ),
        ],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "target_date": {"type": "string", "format": "date", "description": "Nueva fecha objetivo (YYYY-MM-DD)"},
                    "estimated_hours": {"type": "number", "format": "float", "description": "Nuevas horas estimadas (> 0)"},
                    "reason": {"type": "string", "description": "Motivo de la reprogramación (opcional)"},
                },
            }
        },
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Subtarea actualizada (o sin cambios). Incluye campos del serializer de subtarea más `message`, `daily_load` y opcionalmente `warning`.",
                examples=[
                    OpenApiExample(
                        "200 — éxito con posible warning",
                        value={
                            "id": "01b73f4a-8805-49f5-8b8e-03aa702d7a6b",
                            "title": "Resolver guía",
                            "status": "PENDING",
                            "estimated_hours": "2.00",
                            "target_date": "2026-03-25",
                            "message": "Subtarea actualizada correctamente.",
                            "daily_load": {
                                "current_hours": 7.0,
                                "limit": 6.0,
                                "has_conflict": True,
                                "exceeded_by": 1.0,
                            },
                            "warning": "Conflicto de sobrecarga. Quedarías con 7.0h planificadas (límite 6.0h).",
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        "200 — sin cambios",
                        value={
                            "id": "01b73f4a-8805-49f5-8b8e-03aa702d7a6b",
                            "title": "Resolver guía",
                            "message": "No se realizaron cambios.",
                            "daily_load": {
                                "current_hours": 4.0,
                                "limit": 6.0,
                                "has_conflict": False,
                                "exceeded_by": 0,
                            },
                        },
                        response_only=True,
                    ),
                ],
            ),
            400: OpenApiResponse(
                description="Validación fallida (fecha pasada, formato, horas ≤ 0, fecha posterior al deadline de la actividad, etc.).",
                examples=[
                    OpenApiExample(
                        "Fecha inválida",
                        value={"error": "La fecha no puede ser anterior a hoy."},
                        response_only=True,
                    ),
                ],
            ),
            404: OpenApiResponse(
                description="Subtarea inexistente o el id no pertenece al usuario autenticado.",
                examples=[OpenApiExample("No encontrada o no autorizada", value={"detail": "Not found."}, response_only=True)],
            ),
        },
        tags=["Subtareas"],
    )
    def put(self, request, pk):
        # Valida que la tarea sea del usuario logueado
        subtask = get_object_or_404(Subtask, id=pk, user=request.user)

        # Guardar valores originales para detectar cambios reales
        original_target_date = subtask.target_date
        original_estimated_hours = subtask.estimated_hours
        # Obtener fecha de la request
        target_date_str = request.data.get('target_date')
        estimated_hours = request.data.get('estimated_hours')
            
        # Validar fecha
        target_date = None
        if target_date_str:
            try:
                target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Formato de fecha inválido. Use YYYY-MM-DD."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validar no sea fecha pasada
            if target_date < timezone.localdate():
                return Response(
                    {"error": "La fecha no puede ser anterior a hoy."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validar coherencia con Actividad Padre
            activity = subtask.activity
            if activity.deadline and target_date > activity.deadline:
                return Response(
                    {"error": "La fecha no puede superar el límite de la actividad."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Validar horas estimadas 
        if estimated_hours is not None:
            try:
                estimated_hours = Decimal(str(estimated_hours))
                if estimated_hours <= 0:
                    return Response(
                        {"error": "Las horas estimadas deben ser mayores a 0."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except (ValueError, TypeError):
                return Response(
                    {"error": "Las horas estimadas deben ser un número válido."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Actualizamos en memoria; se persistirá solo si se detecta cambio real
            subtask.estimated_hours = estimated_hours

        # Calcular carga diaria para validación
        date_to_check = target_date if target_date else subtask.target_date

        carga_data = Subtask.objects.filter(
            user=request.user,
            target_date=date_to_check
        ).exclude(status=Subtask.Status.REALIZADO).exclude(id=subtask.id).aggregate(total=Sum('estimated_hours'))

        carga_actual = carga_data['total'] or Decimal('0')

        nueva_carga = carga_actual + subtask.estimated_hours

        # Obtener límite diario

        try:
            limite_diario = Decimal(str(request.user.daily_hours_limit))
        except (AttributeError, TypeError):
            limite_diario = Decimal('6.0')

        # Preparar metadata de carga diaria
        daily_load = {
            "current_hours": float(nueva_carga),
            "limit": float(limite_diario),
            "has_conflict": nueva_carga > limite_diario,
            "exceeded_by": float(nueva_carga - limite_diario) if nueva_carga > limite_diario else 0
        }

        # Detectar cambios comparando contra los valores originales
        has_date_change = target_date is not None and target_date != original_target_date
        has_hours_change = estimated_hours is not None and estimated_hours != original_estimated_hours
        
        # Validar si hay cambios reales
        if not has_date_change and not has_hours_change:
            serializer = SubtaskSerializer(subtask, context={'request': request})
            return Response({
                **serializer.data,
                "message": "No se realizaron cambios.",
                "daily_load": daily_load,
                "is_conflicted": daily_load["has_conflict"]
            }, status=status.HTTP_200_OK)

        # Guardar cambios
        old_date = subtask.target_date
        if target_date:
            subtask.target_date = target_date
        
        if subtask.status == Subtask.Status.POSPUESTO:
            subtask.status = Subtask.Status.PENDIENTE
            
        subtask.save()

        # Crear log solo si ya tenía fecha (previous_date es obligatorio en el modelo)
        if has_date_change and old_date is not None:
            reason = request.data.get('reason', 'Reprogramación manual')
            ReprogrammingLog.objects.create(
                subtask=subtask,
                previous_date=old_date,
                new_date=subtask.target_date,
                reason=reason
            )

        # Retornar respuesta
        serializer = SubtaskSerializer(subtask, context={'request': request})
        response_data = {
            **serializer.data,
            "daily_load": daily_load,
            "is_conflicted": daily_load["has_conflict"],
            "message": "Subtarea actualizada correctamente."
        }

        if daily_load['has_conflict']:
            response_data["warning"] = f"Conflicto de sobrecarga. Quedarías con {daily_load['current_hours']}h planificadas (límite {daily_load['limit']}h)."

        return Response(response_data, status=status.HTTP_200_OK)


class ConfiguracionView(APIView):
    """
    Endpoint para obtener y actualizar la configuración del usuario (ej: daily_hours_limit).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Obtener configuración de usuario",
        description=f"""
{_BASE}

### URL
`GET /api/configuracion/`

Retorna el límite de horas planificables por día **`daily_hours_limit`** del usuario.
        """,
        responses={
            200: OpenApiResponse(
                description="Límite actual.",
                examples=[
                    OpenApiExample(
                        "200",
                        value={"daily_hours_limit": 6.0},
                        response_only=True,
                    ),
                ],
            ),
            401: OpenApiResponse(description="JWT requerido."),
        },
        tags=["Configuración"],
    )
    def get(self, request):
        user = request.user
        return Response({
            "daily_hours_limit": float(user.daily_hours_limit)
        }, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Actualizar configuración de usuario",
        description=f"""
{_BASE}

### URL
`PUT /api/configuracion/`

Permite ajustar **`daily_hours_limit`** entre **0.5** y **24.0** (horas planificables por día).
        """,
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "daily_hours_limit": {"type": "number", "format": "float", "description": "Nuevo límite de horas (0.5 a 24.0)."}
                },
                "required": ["daily_hours_limit"]
            }
        },
        examples=[
            OpenApiExample("Request", value={"daily_hours_limit": 8.0}, request_only=True),
        ],
        responses={
            200: OpenApiResponse(
                description="Configuración actualizada.",
                examples=[
                    OpenApiExample(
                        "200",
                        value={"daily_hours_limit": 8.0, "message": "Configuración actualizada correctamente."},
                        response_only=True,
                    ),
                ],
            ),
            400: OpenApiResponse(
                description="Límite faltante, inválido o fuera de rango.",
                examples=[
                    OpenApiExample(
                        "Error de rango",
                        value={"error": "El límite de horas debe ser un valor entre 0.5 y 24.0."},
                        response_only=True,
                    ),
                ],
            ),
            401: OpenApiResponse(description="JWT requerido."),
        },
        tags=["Configuración"],
    )
    def put(self, request):
        user = request.user
        limit_val = request.data.get("daily_hours_limit")
        
        if limit_val is None:
            return Response(
                {"error": "Se requiere 'daily_hours_limit' en el cuerpo de la petición."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            from decimal import Decimal
            limit = Decimal(str(limit_val))
            if limit < Decimal("0.5") or limit > Decimal("24.0"):
                return Response(
                    {"error": "El límite de horas debe ser un valor entre 0.5 y 24.0."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError, ArithmeticError):
            return Response(
                {"error": "Valor de horas inválido."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        user.daily_hours_limit = limit
        user.save(update_fields=["daily_hours_limit"])
        
        return Response({
            "daily_hours_limit": float(user.daily_hours_limit),
            "message": "Configuración actualizada correctamente."
        }, status=status.HTTP_200_OK)

class SubtaskCalendarView(APIView):
    """
    Endpoint para evaluar si una subtarea en particular cabe o no en cada día de una semana (lunes a domingo).
    Devuelve las tareas planificadas por día y un booleano indicando riesgo de conflicto por sobrecarga o límites.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Consultar disponibilidad en el calendario (1 semana)",
        description=f"""
{_BASE}

### URL
`GET /api/subtareas/{{subtask_id}}/calendar/?date=YYYY-MM-DD`  
- `date` (query, opcional): semana que contiene esa fecha; si se omite, usa la semana de **hoy**.

Devuelve **7 días** (lunes–domingo). Por día: tareas planificadas (`PENDING`), carga y si la subtarea del path **cabría** (`fits`) con su `estimated_hours`, más `reason` si no cabe (fecha pasada, deadline de actividad, evento o sobrecarga diaria).

### Seguridad
**`subtask_id`** del path debe ser una subtarea **del usuario autenticado**; en caso contrario → **404**.
        """,
        parameters=[
            OpenApiParameter(
                name='pk',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                required=True,
                description='UUID de la subtarea a evaluar (solo si es del usuario autenticado).',
            ),
            OpenApiParameter(
                name='date',
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Fecha pivote para calcular la semana (YYYY-MM-DD). Si no se pasa, asume hoy.',
            )
        ],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Resumen de subtarea + rango de semana + `calendar` por día.",
                examples=[
                    OpenApiExample(
                        "200 — fragmento",
                        value={
                            "subtask": {"id": "01b73f4a-8805-49f5-8b8e-03aa702d7a6b", "title": "Estudiar", "estimated_hours": 2.0},
                            "start_date": "2026-03-17",
                            "end_date": "2026-03-23",
                            "calendar": [
                                {
                                    "date": "2026-03-17",
                                    "tasks": [],
                                    "fits": True,
                                    "reason": "",
                                    "current_load": 0.0,
                                    "limit": 6.0,
                                },
                            ],
                        },
                        response_only=True,
                    ),
                ],
            ),
            404: OpenApiResponse(
                description="Subtarea inexistente o el id no pertenece al usuario autenticado.",
                examples=[OpenApiExample("No encontrada o no autorizada", value={"detail": "Not found."}, response_only=True)],
            ),
            401: OpenApiResponse(description="JWT requerido."),
        },
        tags=["Subtareas"],
    )
    def get(self, request, pk):
        from django.shortcuts import get_object_or_404
        from datetime import datetime, timedelta
        from django.utils import timezone
        from decimal import Decimal
        from .serializers import SubtaskSerializer
        
        subtask = get_object_or_404(Subtask, id=pk, user=request.user)
        
        date_param = request.query_params.get('date')
        today = timezone.localdate()
        if date_param:
            try:
                base_date = datetime.strptime(date_param, "%Y-%m-%d").date()
            except ValueError:
                base_date = today
        else:
            base_date = today
            
        # Lunes a Domingo (weekday 0 a 6)
        start_of_week = base_date - timedelta(days=base_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        try:
            limite_diario = Decimal(str(request.user.daily_hours_limit))
        except (AttributeError, TypeError):
            limite_diario = Decimal('6.0')
            
        tasks_in_week = Subtask.objects.filter(
            user=request.user,
            target_date__gte=start_of_week,
            target_date__lte=end_of_week
        ).exclude(status=Subtask.Status.REALIZADO).select_related('activity')
        
        tasks_by_day = {start_of_week + timedelta(days=i): [] for i in range(7)}
        for t in tasks_in_week:
            tasks_by_day[t.target_date].append(t)
            
        calendar_days = []
        for i in range(7):
            current_date = start_of_week + timedelta(days=i)
            day_tasks = tasks_by_day[current_date]
            
            # Excluir la subtarea actual si ya está planificada este día
            carga_actual = sum((t.estimated_hours for t in day_tasks if t.id != subtask.id), Decimal('0'))
            nueva_carga = carga_actual + subtask.estimated_hours
            
            fits = True
            reason = ""
            
            if current_date < today:
                fits = False
                reason = "La fecha ya pasó."
            elif subtask.activity.deadline and current_date > subtask.activity.deadline:
                fits = False
                reason = "Supera la fecha límite de la actividad."
            elif subtask.activity.event_datetime and current_date > subtask.activity.event_datetime.date():
                fits = False
                reason = "Supera la fecha del evento."
            elif nueva_carga > limite_diario:
                fits = False
                reason = "Excede el límite de horas diarias (sobrecarga)."
                
            calendar_days.append({
                "date": str(current_date),
                "tasks": SubtaskSerializer(day_tasks, many=True).data,
                "fits": fits,
                "reason": reason,
                "current_load": float(carga_actual),
                "limit": float(limite_diario)
            })
            
        return Response({
            "subtask": {
                "id": subtask.id,
                "title": subtask.title,
                "estimated_hours": float(subtask.estimated_hours)
            },
            "start_date": str(start_of_week),
            "end_date": str(end_of_week),
            "calendar": calendar_days
        }, status=status.HTTP_200_OK)
