from django.contrib import admin
from .models import Course, Activity, Subtask, ReprogrammingLog

admin.site.register([Course, Activity, Subtask, ReprogrammingLog])