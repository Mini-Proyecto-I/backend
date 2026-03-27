from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import Course, Activity, Subtask, ReprogrammingLog, PosponedLog


User = get_user_model()


class CourseSerializer(serializers.ModelSerializer):

    name = serializers.CharField(
        max_length=200,
        required=True,
        allow_blank=False,
        trim_whitespace=True
    )

    class Meta:
        model = Course
        fields = ["id", "name"]

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError(
                "El nombre del curso no puede estar vacío."
            )

        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            # En modo desarrollo, si no hay usuario autenticado,
            # el chequeo de unicidad por usuario se omite.
            return value.strip()

        if Course.objects.filter(name=value.strip(), user=user).exists():
            raise serializers.ValidationError(
                "Ya tienes un curso con ese nombre."
            )

        return value.strip()

    def create(self, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            # Usuario "genérico" para entorno de desarrollo sin autenticación
            user, _ = User.objects.get_or_create(
                email="dev@example.com",
                defaults={"password": "devpass", "name": "Dev User"},
            )
        validated_data["user"] = user
        return super().create(validated_data)

class SubtaskSimpleSerializer(serializers.ModelSerializer):
    is_conflicted = serializers.SerializerMethodField()
    posponed_note = serializers.SerializerMethodField()
    class Meta:
        model = Subtask
        fields = [
            "id", "title", "status", "estimated_hours",
            "target_date", "order", "is_conflicted", "posponed_note"
        ]

    def get_posponed_note(self, obj):
        if obj.status == "POSTPONED":
            ultimo_log = obj.posponed_logs.order_by("-created_at").first()
            return ultimo_log.note if ultimo_log else None
        return None

    def get_is_conflicted(self, obj):
        if obj.status == "DONE":
            return False
        
        target_date = obj.target_date
        if not target_date:
            return False
            
        request = self.context.get('request')
        if not request:
            return False
            
        user = (request.user if request.user.is_authenticated else None)
        if not user:
            return False
            
        if not hasattr(request, '_overloaded_dates'):
            from django.db.models import Sum
            limit = float(user.daily_hours_limit) if hasattr(user, "daily_hours_limit") else 6.0
                
            loads = Subtask.objects.filter(
                user=user, 
                target_date__isnull=False
            ).exclude(status="DONE").values('target_date').annotate(total=Sum('estimated_hours')).filter(total__gt=limit)
            
            request._overloaded_dates = {l['target_date'] for l in loads}
            
        return target_date in request._overloaded_dates

class ActivitySerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    subtasks = SubtaskSimpleSerializer(many=True, read_only=True)
    title = serializers.CharField(
        max_length=100,
        required=True,
        allow_blank=True,
        trim_whitespace=False,
    )
    course_id = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    total_subtasks = serializers.IntegerField(read_only=True)
    total_subtasks_done = serializers.IntegerField(read_only=True)
    completion_percent = serializers.SerializerMethodField()


    class Meta:
        model = Activity
        fields = [
            "id",
            "title",
            "description",
            "course",
            "course_id",
            "type",
            "created_at",
            "event_datetime",
            "deadline",
            "total_subtasks",
            "total_subtasks_done",
            "completion_percent",
            "subtasks",
        ]
        read_only_fields = ["id", "created_at", "total_subtasks", "total_subtasks_done", "completion_percent"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            self.fields["course_id"].queryset = Course.objects.filter(user=user)

    #Validacion titulo
    def validate_title(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("El título no puede estar vacío.")
        return value.strip()
    
    #Validación global
    def validate(self, data):
        event_datetime = data.get("event_datetime")
        deadline = data.get("deadline")
        title = data.get("title")
        # Si no se proporciona title en la actualización, usar el de la instancia
        if title is None and self.instance:
            title = self.instance.title
        # Normalizar el título
        if title:
            title = str(title).strip()
        
        # Nota: en este serializer el campo de escritura es course_id (PKRelatedField)
        course = data.get("course_id")
        # Si no se proporciona course_id en la actualización, usar el de la instancia
        if course is None and self.instance:
            course = self.instance.course

        # Resolver usuario (en dev sin auth usamos el usuario genérico)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):    
            user, _ = User.objects.get_or_create(
                email="dev@example.com",
                defaults={"password": "devpass", "name": "Dev User"},
            )

        # Evitar duplicados: mismo curso + mismo título (por usuario)
        # Solo validar si hay curso y título, y si estamos creando o si el título/course cambió
        if course and title:
            # Verificar si el título o curso cambió en una actualización
            title_changed = not self.instance or (self.instance.title.strip() != title)
            
            # Comparar course_id: course puede ser un objeto Course o None
            course_id = course.id if hasattr(course, 'id') else course
            instance_course_id = self.instance.course_id if self.instance and self.instance.course_id else None
            course_changed = not self.instance or (instance_course_id != course_id)
            
            # Solo validar duplicados si estamos creando o si el título/course cambió
            if not self.instance or title_changed or course_changed:
                qs = Activity.objects.filter(user=user, course=course, title__iexact=title)
                if self.instance:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    raise serializers.ValidationError(
                        {"title": "Ya existe una actividad con este título en el curso seleccionado."}
                    )

        if event_datetime and event_datetime < timezone.now():
            raise serializers.ValidationError({
                "event_datetime": "La fecha de la actividad no puede ser anterior a la actual."
            })

        if deadline and deadline < timezone.localdate():
            raise serializers.ValidationError({
                "deadline": "La fecha límite de la actividad no puede ser anterior a la actual."
            })

        return data


    def create(self, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            user, _ = User.objects.get_or_create(
                email="dev@example.com",
                defaults={"password": "devpass", "name": "Dev User"},
            )
        validated_data["user"] = user
        validated_data["course"] = validated_data.pop("course_id", None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "course_id" in validated_data:
            validated_data["course"] = validated_data.pop("course_id")
        return super().update(instance, validated_data)
            
    def get_completion_percent(self, obj):
        total = getattr(obj, "total_subtasks", 0) or 0
        done = getattr(obj, "total_subtasks_done", 0) or 0
        if total == 0:
            return 0.0
        return round((done / total) * 100, 2)

class SubtaskSerializer(serializers.ModelSerializer):
    activity = ActivitySerializer(read_only=True)
    is_conflicted = serializers.SerializerMethodField()
    posponed_note = serializers.SerializerMethodField()

    title = serializers.CharField(
        max_length=100,
        required=True,
        allow_blank=True,
        trim_whitespace=False,
    )

    class Meta:
        model = Subtask
        fields = [
            "id", "title", "activity", "status", "estimated_hours",
            "target_date", "order", "is_conflicted",
            "posponed_note",
        ]
        read_only_fields = ["id", "activity", "posponed_note"]

    def get_is_conflicted(self, obj):
        if obj.status == "DONE":
            return False
        
        target_date = obj.target_date
        if not target_date:
            return False
            
        request = self.context.get('request')
        if not request:
            # Fallback if no request context
            return False
            
        user = request.user
        if not user or not user.is_authenticated:
            return False
            
        # Use request-level cache to store overloaded dates
        if not hasattr(request, '_overloaded_dates'):
            from django.db.models import Sum
            try:
                limit = float(user.daily_hours_limit)
            except (AttributeError, TypeError):
                limit = 6.0
                
            loads = Subtask.objects.filter(
                user=user, 
                target_date__isnull=False
            ).exclude(status="DONE").values('target_date').annotate(total=Sum('estimated_hours')).filter(total__gt=limit)
            
            request._overloaded_dates = {l['target_date'] for l in loads}
            
        return target_date in request._overloaded_dates

    def get_posponed_note(self, obj):
        if obj.status == "POSTPONED":
            ultimo_log = obj.posponed_logs.order_by("-created_at").first()
            return ultimo_log.note if ultimo_log else None
        return None


    def validate_title(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError(
                "El título de la subtarea no puede estar vacío."
            )
        return value.strip()

    def validate_estimated_hours(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Las horas estimadas deben ser mayores a 0."
            )
        return value

    def validate(self, data):
        request = self.context.get("request")
        view = self.context.get("view")

        # Obtener activity desde la URL
        activity_id = view.kwargs.get("activity_pk") if view else None
        activity = None

        if activity_id:
            activity = Activity.objects.filter(id=activity_id).first()
        elif self.instance:
            activity = self.instance.activity

        target_date = data.get("target_date", getattr(self.instance, "target_date", None))
        new_status = data.get("status", getattr(self.instance, "status", None))
        estimated_hours = data.get(
            "estimated_hours", getattr(self.instance, "estimated_hours", 0)
        )

        # Si marcamos como DONE, no aplicamos validación de límite de horas.
        # Las tareas realizadas ya no ocupan espacio en la planificación.
        if new_status == "DONE":
            return data

        if target_date and activity:
            ## OBtener subtareas del mismo día (excluyendo realizadas).
            subtasks_same_day = Subtask.objects.filter(
                activity__user=activity.user,
                target_date=target_date
            ).exclude(status="DONE")

            ## Si se está haciendo una actualización se excluye la misma tarea.
            if self.instance:
                subtasks_same_day = subtasks_same_day.exclude(id=self.instance.id)

            total_hours = sum(s.estimated_hours for s in subtasks_same_day)

            # Límite diario
            daily_limit = activity.user.daily_hours_limit

            if total_hours + estimated_hours > daily_limit:
                raise serializers.ValidationError({
                    "estimated_hours": "Se excede el límite diario de horas planificadas."
                })
            
        return data



class TodaySubtaskSerializer(SubtaskSerializer):
    """
    Serializer para subtareas en la vista "Hoy".
    Incluye información completa de la actividad y curso para contexto.
    """
    class Meta(SubtaskSerializer.Meta):
        fields = [
            "id", "title", "activity", "status", "estimated_hours",
            "target_date", "is_conflicted", "posponed_note", "order",
        ]


class TodayStudyTimeSerializer(serializers.ModelSerializer):
    """
    Serializer simple para el endpoint de tiempo de estudio de hoy.
    Solo expone el estado y las horas estimadas de cada subtarea.
    """

    class Meta:
        model = Subtask
        fields = ["status", "estimated_hours"]
        read_only_fields = ["status", "estimated_hours"]


class ReprogrammingLogSerializer(serializers.ModelSerializer):
    subtask = SubtaskSerializer(read_only=True)
    subtask_id = serializers.PrimaryKeyRelatedField(
        queryset=Subtask.objects.all(), write_only=True
    )

    class Meta:
        model = ReprogrammingLog
        fields = ["id", "subtask", "subtask_id", "previous_date",
                  "new_date", "reason", "created_at"]

    def create(self, validated_data):
        validated_data["subtask"] = validated_data.pop("subtask_id")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "subtask_id" in validated_data:
            validated_data["subtask"] = validated_data.pop("subtask_id")
        return super().update(instance, validated_data)

class PostponeSubtaskSerializer(serializers.Serializer):
    execution_note = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    class Meta:
        model = Subtask
        fields = ["execution_note"]


class CompletionPercentSerializer(serializers.Serializer):
    completion_percent = serializers.FloatField(read_only=True)
    from_date = serializers.DateField(required=False)
    to_date = serializers.DateField(required=False)
    total_subtasks = serializers.IntegerField(read_only=True)
    total_subtasks_done = serializers.IntegerField(read_only=True)
 

    class Meta:
        model = Activity
        fields = ["completion_percent", "from_date", "to_date", "total_subtasks", "total_subtasks_done"]


class PosponedLogSerializer(serializers.ModelSerializer):
    subtask = SubtaskSerializer(read_only=True)
    class Meta:
        model = PosponedLog
        fields = ["id", "subtask", "note", "created_at"]
        read_only_fields = ["id", "subtask", "note","created_at"]