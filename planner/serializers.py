from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from .models import Course, Activity, Subtask, ReprogrammingLog
from django.utils import timezone


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

        user = self.context["request"].user

        if Course.objects.filter(name=value.strip(), user=user).exists():
            raise serializers.ValidationError(
                "Ya tienes un curso con ese nombre."
            )

        return value.strip()

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)

class ActivitySerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
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

        #Validacion titulo
    def validate_title(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("El título no puede estar vacío.")
        return value
    
    #Validación global
    def validate(self, data):
        event_datetime = data.get("event_datetime")
        deadline = data.get("deadline")
        if event_datetime and event_datetime < timezone.now():
            raise serializers.ValidationError({
                "event_datetime": "La fecha de la actividad no puede ser anterior a la actual."
            })
        if event_datetime and deadline:
            if deadline < event_datetime.date():
                raise serializers.ValidationError({
                    "deadline": "La fecha límite de la actividad no puede ser anterior a la actual."
            })
        return data


    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        validated_data["course"] = validated_data.pop("course_id", None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "course_id" in validated_data:
            validated_data["course"] = validated_data.pop("course_id")
        return super().update(instance, validated_data)


class SubtaskSerializer(serializers.ModelSerializer):
    activity = ActivitySerializer(read_only=True)
    activity_id = serializers.PrimaryKeyRelatedField(queryset=Activity.objects.all(), write_only=True)
    title = serializers.CharField(
        max_length=100,
        required=True,
        allow_blank=False,
        trim_whitespace=False,
    )

    class Meta:
        model = Subtask
        fields = ["id", "title", "activity", "activity_id", "user", "status", "estimated_hours",
                  "target_date", "order", "is_conflicted", "execution_note"]
        extra_kwargs = {
            "user": {"read_only": True},
            "title": {"required": True},
        }

    def validate_title(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("El título de la subtarea no puede estar vacío.")
        return value
    
    def validate_estimated_hours(self, value):
        if value <= 0:
            raise serializers.ValidationError("Las horas estimadas deben ser mayores a 0.")
        return value

    def create(self, validated_data):
        validated_data["activity"] = validated_data.pop("activity_id")
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "activity_id" in validated_data:
            validated_data["activity"] = validated_data.pop("activity_id")
        return super().update(instance, validated_data)


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
