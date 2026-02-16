from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager as AuthUserManager
from django.core.validators import MinValueValidator, MaxValueValidator


class UserManager(AuthUserManager):
    """Manager que usa email como identificador en lugar de username."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("El correo electrónico es obligatorio.")
        email = self.normalize_email(email)
        extra_fields.setdefault("username", email)
        return super().create_user(username=email, email=email, password=password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser debe tener is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser debe tener is_superuser=True.")
        return self.create_user(email, password=password, **extra_fields)


class User(AbstractUser):
    """
    Usuario personalizado de la aplicación.
    Campos: id, nombre, correo (login), contraseña, límite de horas diarias.
    """

    email = models.EmailField("correo", unique=True)
    name = models.CharField("nombre", max_length=150)
    daily_hours_limit = models.DecimalField(
        "límite de horas diarias",
        max_digits=4,
        decimal_places=2,
        default=8.0,
        validators=[MinValueValidator(0.5), MaxValueValidator(24.0)],
        help_text="Horas de estudio configuradas para planificar tareas (0.5–24).",
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email
