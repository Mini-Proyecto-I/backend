from rest_framework import serializers
from models import Course, Activity, Subtask, ReprogrammingLog

class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id", "name"]

class ActivitySerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    class Meta:
        model = Activity
        fields = ["id", "title", "description", "course", 
                  "created_at", "event_datetime", "deadline"]
        
class SubtaskSerializer(serializers.ModelSerializer):
    activity = ActivitySerializer(read_only=True)
    class Meta:
        model = Subtask
        fields = ["id", "title", "activity", "status", "estimated_hours",
                  "target_date", "order", "is_conflicted", "execution_note"]

class ReprogrammingLogSerializer(serializers.ModelSerializer):
    subtask = SubtaskSerializer(read_only=True)
    class Meta: 
        model = ReprogrammingLog
        fields = ["id", "subtask", "previous_date",
                  "new_date", "reason", "created_at"]
