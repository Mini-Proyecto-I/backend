from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import Course, Activity, Subtask, ReprogrammingLog


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

class ActivitySerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
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
        ]
        read_only_fields = ["id", "created_at"]

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
        title = data.get("title", getattr(self.instance, "title", None))
        # Nota: en este serializer el campo de escritura es course_id (PKRelatedField)
        course = data.get("course_id", getattr(self.instance, "course", None))

        # Resolver usuario (en dev sin auth usamos el usuario genérico)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):    
            user, _ = User.objects.get_or_create(
                email="dev@example.com",
                defaults={"password": "devpass", "name": "Dev User"},
            )

        # Evitar duplicados: mismo curso + mismo título (por usuario)
        if course and title and str(title).strip():
            qs = Activity.objects.filter(user=user, course=course, title__iexact=str(title).strip())
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

        if event_datetime and deadline and deadline < event_datetime.date():
            raise serializers.ValidationError({
                "deadline": "La fecha límite no puede ser anterior a la fecha del evento."
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


class SubtaskSerializer(serializers.ModelSerializer):
    activity = ActivitySerializer(read_only=True)

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
            "target_date", "order", "is_conflicted", "execution_note"
        ]
        read_only_fields = ["id", "activity"]

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

    # Quita el create/update que usaba activity_id


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
