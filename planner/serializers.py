from rest_framework import serializers
from .models import Course, Activity, Subtask, ReprogrammingLog
from django.utils import timezone

class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id", "name"]

class ActivitySerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    course_id = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all(), write_only=True, required=False, allow_null=True)

    class Meta:
        model = Activity
        fields = ["id", "title", "description", "course", "course_id",
                  "user", "created_at", "event_datetime", "deadline"]
        extra_kwargs = {
            "user": {"required": True},
            "title": {"required": True, "allow_blank": False}
            }
        
        #Validacion titulo
    def validate_title(self, value):
        if not value.strip():
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
        validated_data["course"] = validated_data.pop("course_id", None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "course_id" in validated_data:
            validated_data["course"] = validated_data.pop("course_id")
        return super().update(instance, validated_data)


class SubtaskSerializer(serializers.ModelSerializer):
    activity = ActivitySerializer(read_only=True)
    activity_id = serializers.PrimaryKeyRelatedField(queryset=Activity.objects.all(), write_only=True)

    class Meta:
        model = Subtask
        fields = ["id", "title", "activity", "activity_id", "user", "status", "estimated_hours",
                  "target_date", "order", "is_conflicted", "execution_note"]
        extra_kwargs = {
            "user": {"required": True},
            "title": {"required": True, "allow_blank": False}
        }

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError("El título de la subtarea no puede estar vacío.")
        return value
    
    def validate_estimated_hours(self, value):
        if value <= 0:
            raise serializers.ValidationError("Las horas estimadas deben ser mayores a 0.")
        return value

    def create(self, validated_data):
        validated_data["activity"] = validated_data.pop("activity_id")
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
