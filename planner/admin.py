from re import A
from django.contrib import admin
from models import Course, Activity, Subtask, ReprogrammingLog

# Register your models here.
admin.site.register(Course, Activity, Subtask, ReprogrammingLog)