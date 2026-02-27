from django.db import models
from django.conf import settings
from uuid import uuid4

from django.utils.http import MAX_URL_LENGTH

class Course(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cursos"
    )

    def __str__(self):
        return self.name
    

class Activity(models.Model):
    class TypeChoices(models.TextChoices):
        EXAMEN = "examen", "Examen"
        QUIZ = "quiz", "Quiz"
        TALLER = "taller", "Taller"
        PROYECTO = "proyecto", "Proyecto"
        OTRO = "otro", "Otro"
        
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activities")
    title = models.CharField(max_length=100, unique=False, blank=False, null=False)
    description = models.TextField(blank=True, null=True)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, related_name="activities")
    created_at = models.DateTimeField(auto_now_add=True)
    event_datetime = models.DateTimeField(null=True, blank=True)
    deadline = models.DateField(null=True, blank=True)
    type = models.CharField(max_length=20, choices=TypeChoices.choices)
    
    def __str__(self):
        return self.title
    
class Subtask(models.Model):
    
    class Status(models.TextChoices):
        REALIZADO = "DONE", "Realizado"
        PENDIENTE = "PENDING", "Pendiente"
        ESPERA = "WAITING", "En espera"
        POSPUESTO = "POSTPONED", "Pospuesto"
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subtasks")
    title = models.CharField(max_length=100, blank=False, null=False)
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="subtasks")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDIENTE)
    estimated_hours = models.DecimalField(max_digits=4, decimal_places=2)
    target_date = models.DateField(null=True, blank=True)
    order = models.PositiveBigIntegerField(default=0)
    is_conflicted = models.BooleanField(default=False)
    execution_note = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.title

class ReprogrammingLog(models.Model):
    subtask = models.ForeignKey(Subtask, on_delete=models.CASCADE, related_name='logs')
    previous_date = models.DateField()
    new_date = models.DateField()
    reason = models.TextField() 
    created_at = models.DateTimeField(auto_now_add=True)

